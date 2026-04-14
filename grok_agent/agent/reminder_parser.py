"""
Reminder Parser Module
Parses natural language reminder requests and creates reminders
Integrates with Grok API for conversational responses
"""

import re
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple, Any

logger = logging.getLogger(__name__)


class ReminderParser:
    """
    Parses natural language reminder requests and creates reminders.
    Works with the scheduler service and chore database.
    """
    
    # Trigger phrases that indicate a reminder request
    TRIGGER_PHRASES = [
        r'remind me',
        r'set a reminder',
        r'reminder for',
        r'remind me to',
        r'set reminder',
        r'create a reminder',
        r'add a reminder'
    ]
    
    # Days of the week
    DAYS_OF_WEEK = {
        'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
        'friday': 4, 'saturday': 5, 'sunday': 6,
        'mon': 0, 'tue': 1, 'wed': 2, 'thu': 3, 'fri': 4, 'sat': 5, 'sun': 6
    }
    
    # Month names
    MONTHS = {
        'january': 1, 'february': 2, 'march': 3, 'april': 4,
        'may': 5, 'june': 6, 'july': 7, 'august': 8,
        'september': 9, 'october': 10, 'november': 11, 'december': 12,
        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'jun': 6, 'jul': 7,
        'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
    }
    
    def __init__(self, chore_db, scheduler=None):
        """
        Initialize reminder parser
        
        Args:
            chore_db: ChoreDatabase instance
            scheduler: Optional SchedulerService instance
        """
        self.chore_db = chore_db
        self.scheduler = scheduler
        logger.info("ReminderParser initialized")
    
    def is_reminder_request(self, message: str) -> bool:
        """
        Check if a message is a reminder request
        
        Args:
            message: User's message
        
        Returns:
            True if message contains reminder trigger phrases
        """
        message_lower = message.lower()
        
        for phrase in self.TRIGGER_PHRASES:
            if re.search(phrase, message_lower):
                return True
        
        return False
    
    def parse_reminder(self, message: str) -> Optional[Dict[str, Any]]:
        """
        Parse a reminder request into components
        
        Args:
            message: User's reminder request
        
        Returns:
            Dict with: message, trigger_time, repeat_type, or None if parsing fails
        """
        message_lower = message.lower()
        
        # Determine repeat type
        repeat_type = self._parse_repeat_type(message_lower)
        
        # Parse the time/schedule
        trigger_time = self._parse_time(message_lower, repeat_type)
        
        if trigger_time is None:
            logger.warning(f"Could not parse time from: {message}")
            return None
        
        # Extract the reminder message (what to remind about)
        reminder_message = self._extract_reminder_message(message)
        
        if not reminder_message:
            reminder_message = "Reminder"
        
        return {
            'message': reminder_message,
            'trigger_time': trigger_time,
            'repeat_type': repeat_type,
            'original_request': message
        }
    
    def _parse_repeat_type(self, message: str) -> str:
        """
        Determine the repeat type from message
        
        Returns:
            'once', 'daily', or 'weekly'
        """
        # Check for daily patterns
        if re.search(r'every\s*day|daily|each\s*day', message):
            return 'daily'
        
        # Check for weekly patterns
        if re.search(r'every\s*week|weekly|each\s*week', message):
            return 'weekly'
        
        # Check for specific day patterns (every Monday, etc.)
        for day in self.DAYS_OF_WEEK.keys():
            if re.search(rf'every\s*{day}', message):
                return 'weekly'
        
        return 'once'
    
    def _parse_time(self, message: str, repeat_type: str) -> Optional[datetime]:
        """
        Parse the time from a reminder message
        
        Args:
            message: Lowercase message
            repeat_type: 'once', 'daily', or 'weekly'
        
        Returns:
            datetime for when reminder should trigger
        """
        now = datetime.now()
        
        # Pattern: "in X seconds/minutes/hours/days"
        match = re.search(r'in\s+(\d+)\s*(second|sec|minute|min|hour|hr|day)s?', message)
        if match:
            amount = int(match.group(1))
            unit = match.group(2)
            
            if unit in ['second', 'sec']:
                return now + timedelta(seconds=amount)
            elif unit in ['minute', 'min']:
                return now + timedelta(minutes=amount)
            elif unit in ['hour', 'hr']:
                return now + timedelta(hours=amount)
            elif unit == 'day':
                return now + timedelta(days=amount)
        
        # Pattern: "in an hour" / "in a minute"
        if re.search(r'in\s+an?\s+hour', message):
            return now + timedelta(hours=1)
        if re.search(r'in\s+an?\s+minute', message):
            return now + timedelta(minutes=1)
        
        # Pattern: "at X:XX" or "at X pm/am"
        time_match = re.search(r'at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', message)
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2)) if time_match.group(2) else 0
            period = time_match.group(3)
            
            if period:
                if period == 'pm' and hour != 12:
                    hour += 12
                elif period == 'am' and hour == 12:
                    hour = 0
            
            target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            
            # If time has passed today, schedule for tomorrow (for one-time reminders)
            if target <= now and repeat_type == 'once':
                target += timedelta(days=1)
            
            # For weekly, find the next occurrence of the specified day
            if repeat_type == 'weekly':
                target = self._find_next_weekday(message, target)
            
            return target
        
        # Pattern: "on [month] [day]" or "on the [day]th"
        date_match = re.search(r'on\s+(?:the\s+)?(\d{1,2})(?:st|nd|rd|th)?(?:\s+of)?(?:\s+(\w+))?', message)
        if date_match:
            day = int(date_match.group(1))
            month_str = date_match.group(2)
            
            if month_str and month_str.lower() in self.MONTHS:
                month = self.MONTHS[month_str.lower()]
            else:
                month = now.month
            
            year = now.year
            if month < now.month or (month == now.month and day < now.day):
                year += 1
            
            # Check for time in the message
            time_in_date = re.search(r'at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', message)
            if time_in_date:
                hour = int(time_in_date.group(1))
                minute = int(time_in_date.group(2)) if time_in_date.group(2) else 0
                period = time_in_date.group(3)
                
                if period:
                    if period == 'pm' and hour != 12:
                        hour += 12
                    elif period == 'am' and hour == 12:
                        hour = 0
            else:
                hour, minute = 9, 0  # Default to 9 AM
            
            try:
                return datetime(year, month, day, hour, minute, 0)
            except ValueError:
                logger.warning(f"Invalid date: {year}-{month}-{day}")
                return None
        
        # Pattern: "on [day of week]"
        for day_name, day_num in self.DAYS_OF_WEEK.items():
            if re.search(rf'\bon\s+{day_name}\b', message):
                # Find the next occurrence of this day
                days_ahead = day_num - now.weekday()
                if days_ahead <= 0:
                    days_ahead += 7
                
                target = now + timedelta(days=days_ahead)
                target = target.replace(hour=9, minute=0, second=0, microsecond=0)
                
                # Check for specific time
                time_match = re.search(r'at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', message)
                if time_match:
                    hour = int(time_match.group(1))
                    minute = int(time_match.group(2)) if time_match.group(2) else 0
                    period = time_match.group(3)
                    
                    if period:
                        if period == 'pm' and hour != 12:
                            hour += 12
                        elif period == 'am' and hour == 12:
                            hour = 0
                    
                    target = target.replace(hour=hour, minute=minute)
                
                return target
        
        # Pattern: "tonight"
        if 'tonight' in message:
            return now.replace(hour=20, minute=0, second=0, microsecond=0)
        
        # Pattern: "tomorrow"
        if 'tomorrow' in message:
            target = now + timedelta(days=1)
            target = target.replace(hour=9, minute=0, second=0, microsecond=0)
            
            # Check for specific time
            time_match = re.search(r'at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', message)
            if time_match:
                hour = int(time_match.group(1))
                minute = int(time_match.group(2)) if time_match.group(2) else 0
                period = time_match.group(3)
                
                if period:
                    if period == 'pm' and hour != 12:
                        hour += 12
                    elif period == 'am' and hour == 12:
                        hour = 0
                
                target = target.replace(hour=hour, minute=minute)
            
            return target
        
        # Default: 5 minutes from now if no time specified
        logger.info("No specific time found, defaulting to 5 minutes")
        return now + timedelta(minutes=5)
    
    def _find_next_weekday(self, message: str, base_time: datetime) -> datetime:
        """
        Find the next occurrence of a weekday mentioned in the message
        
        Args:
            message: Message to search for day names
            base_time: Base datetime with the desired time
        
        Returns:
            datetime of next occurrence of that weekday
        """
        now = datetime.now()
        
        for day_name, day_num in self.DAYS_OF_WEEK.items():
            if day_name in message:
                days_ahead = day_num - now.weekday()
                if days_ahead <= 0:
                    days_ahead += 7
                
                target = now + timedelta(days=days_ahead)
                return target.replace(
                    hour=base_time.hour,
                    minute=base_time.minute,
                    second=0,
                    microsecond=0
                )
        
        return base_time
    
    def _extract_reminder_message(self, message: str) -> str:
        """
        Extract what the reminder is about from the message
        
        Args:
            message: Original reminder request
        
        Returns:
            The extracted reminder message
        """
        # Remove trigger phrases
        result = message
        for phrase in self.TRIGGER_PHRASES:
            result = re.sub(phrase, '', result, flags=re.IGNORECASE)
        
        # Remove time-related phrases
        time_patterns = [
            r'in\s+\d+\s*(?:second|sec|minute|min|hour|hr|day)s?',
            r'in\s+an?\s+(?:hour|minute)',
            r'at\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?',
            r'on\s+(?:the\s+)?\d{1,2}(?:st|nd|rd|th)?(?:\s+of)?(?:\s+\w+)?',
            r'on\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)',
            r'every\s*(?:day|week|monday|tuesday|wednesday|thursday|friday|saturday|sunday)',
            r'daily|weekly',
            r'tomorrow|tonight'
        ]
        
        for pattern in time_patterns:
            result = re.sub(pattern, '', result, flags=re.IGNORECASE)
        
        # Remove common filler words
        result = re.sub(r'\bto\b', '', result, count=1)
        result = re.sub(r'\babout\b', '', result, count=1)
        result = re.sub(r'\bthat\b', '', result, count=1)
        
        # Clean up whitespace
        result = ' '.join(result.split())
        result = result.strip(' .,!?')
        
        return result.strip()
    
    def create_reminder(self, message: str, notify_voice: bool = True, 
                       notify_email: bool = True) -> Tuple[bool, str, Optional[Dict]]:
        """
        Parse and create a reminder from a natural language request
        
        Args:
            message: User's reminder request
            notify_voice: Enable voice notification
            notify_email: Enable email notification
        
        Returns:
            Tuple of (success, status_message, reminder_data)
        """
        # Parse the reminder
        parsed = self.parse_reminder(message)
        
        if parsed is None:
            return False, "I couldn't understand the time for this reminder. Try saying something like 'remind me in 30 minutes' or 'remind me at 3pm'.", None
        
        try:
            # Create the reminder in database
            reminder_id = self.chore_db.add_reminder(
                message=parsed['message'],
                trigger_time=parsed['trigger_time'],
                notify_voice=notify_voice,
                notify_email=notify_email,
                repeat_type=parsed['repeat_type']
            )
            
            # Format confirmation message
            time_str = parsed['trigger_time'].strftime('%I:%M %p on %B %d, %Y')
            
            if parsed['repeat_type'] == 'daily':
                schedule_str = f"every day at {parsed['trigger_time'].strftime('%I:%M %p')}"
            elif parsed['repeat_type'] == 'weekly':
                schedule_str = f"every {parsed['trigger_time'].strftime('%A')} at {parsed['trigger_time'].strftime('%I:%M %p')}"
            else:
                schedule_str = time_str
            
            status = f"Reminder set for '{parsed['message']}' - {schedule_str}"
            
            logger.info(f"Created reminder: {status}")
            
            return True, status, {
                'reminder_id': reminder_id,
                'message': parsed['message'],
                'trigger_time': parsed['trigger_time'],
                'repeat_type': parsed['repeat_type'],
                'schedule_str': schedule_str
            }
            
        except Exception as e:
            logger.error(f"Error creating reminder: {e}")
            return False, f"Error creating reminder: {e}", None
    
    def process_message(self, message: str, agent=None) -> Tuple[bool, Optional[str]]:
        """
        Process a message - check if it's a reminder and handle accordingly
        
        Args:
            message: User's message
            agent: Optional GrokAgent for getting conversational response
        
        Returns:
            Tuple of (was_reminder, response)
            - If was_reminder is True, response contains the agent's reply
            - If was_reminder is False, response is None (message should go to normal processing)
        """
        if not self.is_reminder_request(message):
            return False, None
        
        # It's a reminder request - parse and create it
        success, status, reminder_data = self.create_reminder(message)
        
        # Build context for Grok API
        if success and agent:
            # Send to Grok with context about the reminder
            context = f"""The user asked to set a reminder. I have successfully created it with the following details:
- Reminder message: "{reminder_data['message']}"
- Scheduled for: {reminder_data['schedule_str']}
- Repeat type: {reminder_data['repeat_type']}

Please acknowledge the reminder was set and respond naturally. Be helpful and friendly."""
            
            # Get Grok's conversational response
            try:
                grok_response = agent.chat(f"{message}\n\n[SYSTEM: {context}]")
                return True, grok_response
            except Exception as e:
                logger.error(f"Error getting Grok response: {e}")
                return True, f"Got it! {status}"
        
        elif success:
            return True, f"Got it! {status}"
        
        else:
            # Failed to parse/create reminder
            if agent:
                try:
                    grok_response = agent.chat(f"{message}\n\n[SYSTEM: The user tried to set a reminder but I couldn't parse it. Error: {status}. Please help them rephrase their reminder request.]")
                    return True, grok_response
                except:
                    pass
            return True, status


def initialize_reminder_parser(chore_db, scheduler=None) -> ReminderParser:
    """
    Initialize and return a ReminderParser instance
    
    Args:
        chore_db: ChoreDatabase instance
        scheduler: Optional SchedulerService instance
    
    Returns:
        ReminderParser instance
    """
    return ReminderParser(chore_db, scheduler)
