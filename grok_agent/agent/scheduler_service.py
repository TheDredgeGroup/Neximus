"""
Scheduler Service
Background process that runs chores and sends reminders
Supports multiple email recipients
"""

import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Optional, Callable, Dict, Any, List
import queue

logger = logging.getLogger(__name__)


class SchedulerService:
    """
    Background scheduler for running chores and reminders
    """
    
    def __init__(self, chore_db, plc_comm, voice_interface=None):
        """
        Initialize scheduler
        
        Args:
            chore_db: ChoreDatabase instance
            plc_comm: PLCCommunicator instance
            voice_interface: Optional VoiceInterface for voice reminders
        """
        self.chore_db = chore_db
        self.plc_comm = plc_comm
        self.voice = voice_interface
        
        # Scheduler state
        self.running = False
        self.paused = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        
        # Check interval (seconds)
        self.check_interval = 10  # Check every 10 seconds
        
        # Callbacks for notifications
        self.on_chore_executed: Optional[Callable] = None
        self.on_reminder_triggered: Optional[Callable] = None
        self.on_error: Optional[Callable] = None
        
        # Sun times cache
        self._sun_times: Dict[str, datetime] = {}
        self._sun_times_date: Optional[datetime] = None
        
        logger.info("Scheduler service initialized")
    
    def start(self):
        """Start the scheduler service"""
        if self.running:
            logger.warning("Scheduler already running")
            return
        
        self.running = True
        self._stop_event.clear()
        
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        
        logger.info("Scheduler service started")
    
    def stop(self):
        """Stop the scheduler service"""
        if not self.running:
            return
        
        self.running = False
        self._stop_event.set()
        
        if self._thread:
            self._thread.join(timeout=5)
        
        logger.info("Scheduler service stopped")
    
    def pause(self):
        """Pause the scheduler (still running but not executing)"""
        self.paused = True
        logger.info("Scheduler paused")
    
    def resume(self):
        """Resume the scheduler"""
        self.paused = False
        logger.info("Scheduler resumed")
    
    def _run_loop(self):
        """Main scheduler loop"""
        logger.info("Scheduler loop started")
        
        while self.running and not self._stop_event.is_set():
            try:
                if not self.paused:
                    # Check and execute due chores
                    self._process_chores()
                    
                    # Check and send due reminders
                    self._process_reminders()
                
                # Wait for next check interval
                self._stop_event.wait(timeout=self.check_interval)
                
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
                if self.on_error:
                    self.on_error(f"Scheduler error: {e}")
                time.sleep(5)  # Wait before retrying
        
        logger.info("Scheduler loop ended")
    
    def _process_chores(self):
        """Process all due chores"""
        try:
            # Update sun times if needed
            self._update_sun_times()
            
            # Get due chores
            due_chores = self.chore_db.get_due_chores()
            
            for chore in due_chores:
                self._execute_chore(chore)
                
        except Exception as e:
            logger.error(f"Error processing chores: {e}")
    
    def _execute_chore(self, chore: Dict):
        """Execute a single chore"""
        chore_id = chore['chore_id']
        name = chore['name']
        
        logger.info(f"Executing chore: {name}")
        
        start_time = time.time()
        
        try:
            # Execute PLC action
            result = self.plc_comm.execute_chore_action(
                ip_address=chore['ip_address'],
                tag_name=chore['tag_name'],
                action=chore['action'],
                action_value=chore.get('action_value'),
                slot=chore['slot'],
                plc_type=chore['plc_type']
            )
            
            execution_time = int((time.time() - start_time) * 1000)
            
            if result.success:
                status = 'success'
                error = None
                logger.info(f"Chore '{name}' completed successfully")
            else:
                status = 'failed'
                error = result.error
                logger.error(f"Chore '{name}' failed: {error}")
            
            # Calculate next run time
            next_run = self._calculate_next_run(chore)
            
            # Update chore in database
            self.chore_db.update_chore_run(chore_id, status, next_run, error)
            
            # Log execution
            self.chore_db.log_chore_execution(
                chore_id=chore_id,
                chore_name=name,
                plc_name=chore.get('plc_name', 'Unknown'),
                tag_name=chore['tag_name'],
                action=chore['action'],
                result=status,
                action_value=str(chore.get('action_value')),
                error=error,
                execution_time_ms=execution_time
            )
            
            # Callback
            if self.on_chore_executed:
                self.on_chore_executed(chore, status, error)
                
        except Exception as e:
            logger.error(f"Exception executing chore '{name}': {e}")
            
            # Update as failed
            next_run = self._calculate_next_run(chore)
            self.chore_db.update_chore_run(chore_id, 'failed', next_run, str(e))
    
    def _calculate_next_run(self, chore: Dict) -> datetime:
        """Calculate the next run time for a chore"""
        schedule_type = chore['schedule_type']
        schedule_value = chore['schedule_value']
        
        now = datetime.now()
        
        if schedule_type == 'time':
            # Fixed time - schedule for same time tomorrow
            try:
                hour, minute = map(int, schedule_value.split(':'))
                next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                
                if next_run <= now:
                    next_run += timedelta(days=1)
                
                return next_run
            except:
                return now + timedelta(days=1)
        
        elif schedule_type == 'sunrise':
            # Sunrise-based - schedule for tomorrow's sunrise
            sunrise = self._sun_times.get('sunrise')
            if sunrise:
                # Apply offset
                offset = self._parse_offset(schedule_value)
                next_sunrise = sunrise + timedelta(days=1) + timedelta(minutes=offset)
                return next_sunrise
            return now + timedelta(days=1)
        
        elif schedule_type == 'sunset':
            # Sunset-based - schedule for tomorrow's sunset
            sunset = self._sun_times.get('sunset')
            if sunset:
                offset = self._parse_offset(schedule_value)
                next_sunset = sunset + timedelta(days=1) + timedelta(minutes=offset)
                return next_sunset
            return now + timedelta(days=1)
        
        elif schedule_type == 'interval':
            # Interval - run again after specified minutes
            try:
                minutes = int(schedule_value)
                return now + timedelta(minutes=minutes)
            except:
                return now + timedelta(hours=1)
        
        else:
            # Default: tomorrow at same time
            return now + timedelta(days=1)
    
    def _parse_offset(self, value: str) -> int:
        """Parse offset value like '+30' or '-15' to minutes"""
        if not value:
            return 0
        
        try:
            value = value.strip()
            if value.startswith('+'):
                return int(value[1:])
            elif value.startswith('-'):
                return -int(value[1:])
            else:
                return int(value)
        except:
            return 0
    
    def _update_sun_times(self):
        """Update cached sunrise/sunset times"""
        today = datetime.now().date()
        
        # Only update once per day
        if self._sun_times_date == today:
            return
        
        try:
            from astral import LocationInfo
            from astral.sun import sun
            import pytz
            
            # Get location from DB, fall back to config.py defaults
            location = self.chore_db.get_location()
            
            if not location.get('lat') or not location.get('lon'):
                try:
                    from config.config import LOCATION_LAT, LOCATION_LON, LOCATION_TIMEZONE
                    lat = float(LOCATION_LAT)
                    lon = float(LOCATION_LON)
                    tz_name = LOCATION_TIMEZONE
                    city = "Home"
                    logger.info("Using location from config.py")
                except (ImportError, AttributeError):
                    logger.warning("No location set - sunrise/sunset chores won't work")
                    return
            else:
                lat = float(location['lat'])
                lon = float(location['lon'])
                tz_name = location.get('timezone', 'America/Los_Angeles')
                city = location.get('city', 'Home')
            
            tz = pytz.timezone(tz_name)
            loc = LocationInfo(city, "USA", tz_name, lat, lon)
            
            s = sun(loc.observer, date=today, tzinfo=tz)
            
            self._sun_times = {
                'sunrise': s['sunrise'],
                'sunset': s['sunset'],
                'dawn': s['dawn'],
                'dusk': s['dusk']
            }
            self._sun_times_date = today
            
            logger.info(f"Updated sun times - Sunrise: {s['sunrise'].strftime('%H:%M')}, Sunset: {s['sunset'].strftime('%H:%M')}")
            
        except ImportError:
            logger.warning("astral not installed - sunrise/sunset chores unavailable")
        except Exception as e:
            logger.error(f"Error calculating sun times: {e}")
    
    def _process_reminders(self):
        """Process all due reminders"""
        try:
            due_reminders = self.chore_db.get_due_reminders()
            
            for reminder in due_reminders:
                self._send_reminder(reminder)
                
        except Exception as e:
            logger.error(f"Error processing reminders: {e}")
    
    def _send_reminder(self, reminder: Dict):
        """Send a single reminder"""
        reminder_id = reminder['id']
        message = reminder['message']
        
        logger.info(f"Sending reminder: {message[:50]}...")
        
        # Voice notification - only if no callback (callback handles voice via GUI)
        if reminder.get('notify_voice') and self.voice and not self.on_reminder_triggered:
            try:
                self.voice.speak(f"Reminder: {message}")
                self.chore_db.log_reminder_notification(
                    reminder_id, message, 'voice', 'sent'
                )
                logger.info("Voice reminder sent")
            except Exception as e:
                logger.error(f"Voice reminder failed: {e}")
                self.chore_db.log_reminder_notification(
                    reminder_id, message, 'voice', 'failed', str(e)
                )
        elif reminder.get('notify_voice') and self.on_reminder_triggered:
            # Callback will handle voice - just log it
            self.chore_db.log_reminder_notification(
                reminder_id, message, 'voice', 'sent (via callback)'
            )
            logger.info("Voice reminder delegated to callback")
        
        # Email notification (to multiple recipients)
        if reminder.get('notify_email'):
            self._send_email_reminder(reminder_id, message)
        
        # Calculate next trigger for repeating reminders
        next_trigger = self._calculate_next_reminder(reminder)
        
        # Mark as sent
        self.chore_db.mark_reminder_sent(reminder_id, next_trigger)
        
        # Callback
        if self.on_reminder_triggered:
            self.on_reminder_triggered(reminder)
    
    def _send_email_reminder(self, reminder_id: str, message: str):
        """Send email reminder to all configured recipients"""
        try:
            # Get email settings
            email_enabled = self.chore_db.get_setting('email_enabled')
            if email_enabled != 'true':
                return
            
            email = self.chore_db.get_setting('email_address')
            password = self.chore_db.get_setting('email_password')
            
            # Get recipient list (comma-separated)
            recipients_str = self.chore_db.get_setting('email_recipients')
            if not recipients_str:
                # Fallback to single recipient setting for backwards compatibility
                recipients_str = self.chore_db.get_setting('email_recipient') or email
            
            recipients = [r.strip() for r in recipients_str.split(',') if r.strip()]
            
            if not email or not password:
                logger.warning("Email not configured")
                return
            
            if not recipients:
                logger.warning("No email recipients configured")
                return
            
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            
            msg = MIMEMultipart()
            msg['From'] = email
            msg['To'] = ', '.join(recipients)
            msg['Subject'] = "Grok Agent Reminder"
            
            body = f"""
REMINDER FROM GROK AGENT
========================

{message}

---
Sent at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Recipients: {', '.join(recipients)}
            """
            msg.attach(MIMEText(body, 'plain'))
            
            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            server.login(email, password)
            server.send_message(msg)
            server.quit()
            
            self.chore_db.log_reminder_notification(
                reminder_id, message, 'email', 'sent'
            )
            logger.info(f"Email reminder sent to {len(recipients)} recipient(s)")
            
        except Exception as e:
            logger.error(f"Email reminder failed: {e}")
            self.chore_db.log_reminder_notification(
                reminder_id, message, 'email', 'failed', str(e)
            )
    
    def _calculate_next_reminder(self, reminder: Dict) -> Optional[datetime]:
        """Calculate next trigger time for repeating reminders"""
        repeat_type = reminder.get('repeat_type', 'once')
        
        if repeat_type == 'once':
            return None  # No repeat
        
        now = datetime.now()
        
        if repeat_type == 'daily':
            return now + timedelta(days=1)
        
        elif repeat_type == 'weekly':
            return now + timedelta(weeks=1)
        
        elif repeat_type == 'monthly':
            # Add roughly a month
            return now + timedelta(days=30)
        
        return None
    
    def get_status(self) -> Dict[str, Any]:
        """Get scheduler status"""
        return {
            'running': self.running,
            'paused': self.paused,
            'check_interval': self.check_interval,
            'sun_times': {
                k: v.strftime('%H:%M') if v else None 
                for k, v in self._sun_times.items()
            } if self._sun_times else None
        }
    
    def set_check_interval(self, seconds: int):
        """Set the check interval"""
        self.check_interval = max(1, seconds)
        logger.info(f"Check interval set to {self.check_interval} seconds")
    
    def run_chore_now(self, chore_id: str) -> Dict[str, Any]:
        """Manually run a chore immediately"""
        chore = self.chore_db.get_chore(chore_id)
        
        if not chore:
            return {'success': False, 'error': 'Chore not found'}
        
        # Get PLC info
        plc = self.chore_db.get_plc(chore['plc_id'])
        
        if not plc:
            return {'success': False, 'error': 'PLC not found'}
        
        # Build chore dict for execution
        chore_exec = {
            'chore_id': chore_id,
            'name': chore['name'],
            'tag_name': chore['tag_name'],
            'action': chore['action'],
            'action_value': chore.get('action_value'),
            'schedule_type': chore['schedule_type'],
            'schedule_value': chore['schedule_value'],
            'ip_address': plc['ip_address'],
            'slot': plc['slot'],
            'plc_type': plc['plc_type'],
            'plc_name': plc['name']
        }
        
        # Execute
        self._execute_chore(chore_exec)
        
        return {'success': True}
    
    def add_quick_reminder(self, message: str, minutes: int = 5,
                           voice: bool = True, email: bool = True) -> str:
        """
        Add a quick reminder for X minutes from now
        
        Args:
            message: Reminder message
            minutes: Minutes from now
            voice: Send voice notification
            email: Send email notification
        
        Returns:
            Reminder ID
        """
        trigger_time = datetime.now() + timedelta(minutes=minutes)
        
        reminder_id = self.chore_db.add_reminder(
            message=message,
            trigger_time=trigger_time,
            notify_voice=voice,
            notify_email=email
        )
        
        logger.info(f"Quick reminder set for {minutes} minutes: {message[:30]}...")
        return reminder_id


# Global scheduler instance
_scheduler: Optional[SchedulerService] = None


def get_scheduler() -> Optional[SchedulerService]:
    """Get the global scheduler instance"""
    return _scheduler


def initialize_scheduler(chore_db, plc_comm, voice_interface=None) -> SchedulerService:
    """
    Initialize and return the scheduler service
    
    Args:
        chore_db: ChoreDatabase instance
        plc_comm: PLCCommunicator instance
        voice_interface: Optional VoiceInterface for voice reminders
    
    Returns:
        SchedulerService instance
    """
    global _scheduler
    _scheduler = SchedulerService(chore_db, plc_comm, voice_interface)
    return _scheduler


def start_scheduler():
    """Start the global scheduler"""
    if _scheduler:
        _scheduler.start()


def stop_scheduler():
    """Stop the global scheduler"""
    if _scheduler:
        _scheduler.stop()