"""
Database Operations Module - Phase 3
Chores, Reminders, PLC Configuration
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import uuid

logger = logging.getLogger(__name__)


class ChoreDatabase:
    """
    Database operations for chores, reminders, and PLC configuration.
    Works alongside the existing Database class.
    """
    
    def __init__(self, connection):
        """
        Initialize with existing database connection
        
        Args:
            connection: psycopg2 connection from main Database class
        """
        self.conn = connection
        logger.info("ChoreDatabase initialized")
    
    # ==========================================
    # PLC CONFIGURATION OPERATIONS
    # ==========================================
    
    def add_plc(self, name: str, ip_address: str, plc_type: str, 
                slot: int = 0, description: str = None) -> str:
        """
        Add a new PLC configuration
        
        Args:
            name: Friendly name for the PLC
            ip_address: IP address of the PLC
            plc_type: Type (CompactLogix, ControlLogix, MicroLogix, Micro800)
            slot: Slot number (default 0)
            description: Optional description
        
        Returns:
            UUID of the new PLC config
        """
        plc_id = str(uuid.uuid4())
        
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO plc_config (id, name, ip_address, plc_type, slot, description)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (plc_id, name, ip_address, plc_type, slot, description))
            self.conn.commit()
        
        logger.info(f"Added PLC: {name} ({ip_address})")
        return plc_id
    
    def update_plc(self, plc_id: str, **kwargs) -> bool:
        """
        Update PLC configuration
        
        Args:
            plc_id: UUID of the PLC
            **kwargs: Fields to update (name, ip_address, plc_type, slot, description, enabled)
        
        Returns:
            True if updated successfully
        """
        allowed_fields = ['name', 'ip_address', 'plc_type', 'slot', 'description', 'enabled']
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
        
        if not updates:
            return False
        
        set_clause = ", ".join([f"{k} = %s" for k in updates.keys()])
        values = list(updates.values()) + [plc_id]
        
        with self.conn.cursor() as cur:
            cur.execute(f"""
                UPDATE plc_config 
                SET {set_clause}, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, values)
            self.conn.commit()
        
        logger.info(f"Updated PLC {plc_id}")
        return True
    
    def delete_plc(self, plc_id: str) -> bool:
        """Delete a PLC configuration (cascades to tags)"""
        with self.conn.cursor() as cur:
            cur.execute("DELETE FROM plc_config WHERE id = %s", (plc_id,))
            self.conn.commit()
        
        logger.info(f"Deleted PLC {plc_id}")
        return True
    
    def get_plc(self, plc_id: str) -> Optional[Dict]:
        """Get a single PLC configuration by ID"""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT id, name, description, ip_address, slot, plc_type, 
                       enabled, connection_status, last_connected, last_error,
                       created_at, updated_at
                FROM plc_config WHERE id = %s
            """, (plc_id,))
            row = cur.fetchone()
        
        if row:
            return {
                'id': str(row[0]),
                'name': row[1],
                'description': row[2],
                'ip_address': row[3],
                'slot': row[4],
                'plc_type': row[5],
                'enabled': row[6],
                'connection_status': row[7],
                'last_connected': row[8],
                'last_error': row[9],
                'created_at': row[10],
                'updated_at': row[11]
            }
        return None
    
    def get_all_plcs(self, enabled_only: bool = False) -> List[Dict]:
        """Get all PLC configurations"""
        query = """
            SELECT id, name, description, ip_address, slot, plc_type, 
                   enabled, connection_status, last_connected
            FROM plc_config
        """
        if enabled_only:
            query += " WHERE enabled = true"
        query += " ORDER BY name"
        
        with self.conn.cursor() as cur:
            cur.execute(query)
            rows = cur.fetchall()
        
        return [{
            'id': str(row[0]),
            'name': row[1],
            'description': row[2],
            'ip_address': row[3],
            'slot': row[4],
            'plc_type': row[5],
            'enabled': row[6],
            'connection_status': row[7],
            'last_connected': row[8]
        } for row in rows]
    
    def update_plc_status(self, plc_id: str, status: str, error: str = None):
        """Update PLC connection status"""
        with self.conn.cursor() as cur:
            if status == 'connected':
                cur.execute("""
                    UPDATE plc_config 
                    SET connection_status = %s, last_connected = CURRENT_TIMESTAMP, last_error = NULL
                    WHERE id = %s
                """, (status, plc_id))
            else:
                cur.execute("""
                    UPDATE plc_config 
                    SET connection_status = %s, last_error = %s
                    WHERE id = %s
                """, (status, error, plc_id))
            self.conn.commit()
    
    # ==========================================
    # PLC TAGS OPERATIONS
    # ==========================================
    
    def add_tag(self, plc_id: str, tag_name: str, tag_type: str,
                description: str = None, access_type: str = 'read_write',
                monitor: bool = False, read_keywords: str = None,
                write_keywords: str = None, on_keywords: str = None,
                off_keywords: str = None) -> str:
        """
        Add a tag to a PLC
        
        Args:
            plc_id: UUID of the PLC
            tag_name: Name of the tag in the PLC
            tag_type: Data type (BOOL, SINT, INT, DINT, REAL, STRING)
            description: Optional description
            access_type: read_only, write_only, read_write
            monitor: Whether to continuously monitor this tag
            read_keywords: Keywords for reading (pipe-separated alternatives)
            write_keywords: Keywords for writing (comma-separated)
            on_keywords: Keywords for ON/state=1 (comma-separated)
            off_keywords: Keywords for OFF/state=0 (comma-separated)
        
        Returns:
            UUID of the new tag
        """
        tag_id = str(uuid.uuid4())
        
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO plc_tags (id, plc_id, tag_name, tag_type, description, access_type, monitor,
                                     read_keywords, write_keywords, on_keywords, off_keywords)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (tag_id, plc_id, tag_name, tag_type, description, access_type, monitor,
                  read_keywords, write_keywords, on_keywords, off_keywords))
            self.conn.commit()
        
        logger.info(f"Added tag: {tag_name} to PLC {plc_id}")
        return tag_id
    
    def update_tag(self, tag_id: str, **kwargs) -> bool:
        """Update tag configuration"""
        allowed_fields = ['tag_name', 'tag_type', 'description', 'access_type', 'monitor', 'monitor_interval',
                         'read_keywords', 'write_keywords', 'on_keywords', 'off_keywords']
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
        
        if not updates:
            return False
        
        set_clause = ", ".join([f"{k} = %s" for k in updates.keys()])
        values = list(updates.values()) + [tag_id]
        
        with self.conn.cursor() as cur:
            cur.execute(f"UPDATE plc_tags SET {set_clause} WHERE id = %s", values)
            self.conn.commit()
        
        logger.info(f"Updated tag {tag_id}")
        return True
    
    def delete_tag(self, tag_id: str) -> bool:
        """Delete a tag"""
        with self.conn.cursor() as cur:
            cur.execute("DELETE FROM plc_tags WHERE id = %s", (tag_id,))
            self.conn.commit()
        
        logger.info(f"Deleted tag {tag_id}")
        return True
    
    def get_tags_for_plc(self, plc_id: str) -> List[Dict]:
        """Get all tags for a PLC"""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT id, tag_name, tag_type, description, access_type, 
                       monitor, monitor_interval, last_value, last_read,
                       read_keywords, write_keywords, on_keywords, off_keywords
                FROM plc_tags
                WHERE plc_id = %s
                ORDER BY tag_name
            """, (plc_id,))
            rows = cur.fetchall()
        
        return [{
            'id': str(row[0]),
            'tag_name': row[1],
            'tag_type': row[2],
            'description': row[3],
            'access_type': row[4],
            'monitor': row[5],
            'monitor_interval': row[6],
            'last_value': row[7],
            'last_read': row[8],
            'read_keywords': row[9],
            'write_keywords': row[10],
            'on_keywords': row[11],
            'off_keywords': row[12]
        } for row in rows] 

    def get_tag_by_id(self, tag_id: str) -> Optional[Dict]:
        """Get a single tag by ID"""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT id, plc_id, tag_name, tag_type, description, access_type, 
                   monitor, monitor_interval, last_value, last_read,
                   read_keywords, write_keywords, on_keywords, off_keywords
                FROM plc_tags
                WHERE id = %s
            """, (tag_id,))
            row = cur.fetchone()
    
        if row:
            return {
            'id': str(row[0]),
            'plc_id': str(row[1]),
            'tag_name': row[2],
            'tag_type': row[3],
            'description': row[4],
            'access_type': row[5],
            'monitor': row[6],
            'monitor_interval': row[7],
            'last_value': row[8],
            'last_read': row[9],
            'read_keywords': row[10],
            'write_keywords': row[11],
            'on_keywords': row[12],
            'off_keywords': row[13]
            }
        return None
    
    def get_monitored_tags(self) -> List[Dict]:
        """Get all tags that should be monitored"""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT t.id, t.tag_name, t.tag_type, t.monitor_interval,
                       p.id as plc_id, p.ip_address, p.slot, p.plc_type
                FROM plc_tags t
                JOIN plc_config p ON t.plc_id = p.id
                WHERE t.monitor = true AND p.enabled = true
                ORDER BY p.ip_address, t.tag_name
            """)
            rows = cur.fetchall()
        
        return [{
            'tag_id': str(row[0]),
            'tag_name': row[1],
            'tag_type': row[2],
            'monitor_interval': row[3],
            'plc_id': str(row[4]),
            'ip_address': row[5],
            'slot': row[6],
            'plc_type': row[7]
        } for row in rows]
    
    def update_tag_value(self, tag_id: str, value: str):
        """Update the last read value for a tag"""
        with self.conn.cursor() as cur:
            cur.execute("""
                UPDATE plc_tags 
                SET last_value = %s, last_read = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (value, tag_id))
            self.conn.commit()
    
    # ==========================================
    # CHORES OPERATIONS
    # ==========================================
    
    def add_chore(self, name: str, plc_id: str, tag_name: str, action: str,
                  schedule_type: str, schedule_value: str,
                  description: str = None, action_value: str = None,
                  days_of_week: str = 'all', tag_id: str = None) -> str:
        """
        Add a new chore
        
        Args:
            name: Friendly name for the chore
            plc_id: UUID of the PLC
            tag_name: Tag name to control
            action: toggle, set_on, set_off, set_value, read
            schedule_type: time, sunrise, sunset, interval, cron
            schedule_value: Time or offset value
            description: Optional description
            action_value: Value for set_value action
            days_of_week: When to run (all, weekdays, weekends, or mon,tue,wed...)
            tag_id: Optional UUID of the tag
        
        Returns:
            UUID of the new chore
        """
        chore_id = str(uuid.uuid4())
        
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO chores (id, name, description, plc_id, tag_id, tag_name,
                                   action, action_value, schedule_type, schedule_value, days_of_week)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (chore_id, name, description, plc_id, tag_id, tag_name,
                  action, action_value, schedule_type, schedule_value, days_of_week))
            self.conn.commit()
        
        logger.info(f"Added chore: {name}")
        return chore_id
    
    def update_chore(self, chore_id: str, **kwargs) -> bool:
        """Update chore configuration"""
        allowed_fields = ['name', 'description', 'plc_id', 'tag_id', 'tag_name',
                         'action', 'action_value', 'schedule_type', 'schedule_value',
                         'days_of_week', 'enabled']
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
        
        if not updates:
            return False
        
        set_clause = ", ".join([f"{k} = %s" for k in updates.keys()])
        values = list(updates.values()) + [chore_id]
        
        with self.conn.cursor() as cur:
            cur.execute(f"""
                UPDATE chores 
                SET {set_clause}, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, values)
            self.conn.commit()
        
        logger.info(f"Updated chore {chore_id}")
        return True
    
    def delete_chore(self, chore_id: str) -> bool:
        """Delete a chore"""
        with self.conn.cursor() as cur:
            cur.execute("DELETE FROM chores WHERE id = %s", (chore_id,))
            self.conn.commit()
        
        logger.info(f"Deleted chore {chore_id}")
        return True
    
    def get_chore(self, chore_id: str) -> Optional[Dict]:
        """Get a single chore by ID"""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT c.id, c.name, c.description, c.plc_id, c.tag_id, c.tag_name,
                       c.action, c.action_value, c.schedule_type, c.schedule_value,
                       c.days_of_week, c.enabled, c.last_run, c.last_result,
                       c.last_error, c.next_run, c.run_count, c.created_at,
                       p.name as plc_name, p.ip_address
                FROM chores c
                LEFT JOIN plc_config p ON c.plc_id = p.id
                WHERE c.id = %s
            """, (chore_id,))
            row = cur.fetchone()
        
        if row:
            return {
                'id': str(row[0]),
                'name': row[1],
                'description': row[2],
                'plc_id': str(row[3]) if row[3] else None,
                'tag_id': str(row[4]) if row[4] else None,
                'tag_name': row[5],
                'action': row[6],
                'action_value': row[7],
                'schedule_type': row[8],
                'schedule_value': row[9],
                'days_of_week': row[10],
                'enabled': row[11],
                'last_run': row[12],
                'last_result': row[13],
                'last_error': row[14],
                'next_run': row[15],
                'run_count': row[16],
                'created_at': row[17],
                'plc_name': row[18],
                'plc_ip': row[19]
            }
        return None
    
    def get_all_chores(self, enabled_only: bool = False) -> List[Dict]:
        """Get all chores"""
        query = """
            SELECT c.id, c.name, c.description, c.tag_name, c.action,
                   c.schedule_type, c.schedule_value, c.days_of_week,
                   c.enabled, c.last_run, c.last_result, c.next_run,
                   p.name as plc_name, p.ip_address
            FROM chores c
            LEFT JOIN plc_config p ON c.plc_id = p.id
        """
        if enabled_only:
            query += " WHERE c.enabled = true"
        query += " ORDER BY c.name"
        
        with self.conn.cursor() as cur:
            cur.execute(query)
            rows = cur.fetchall()
        
        return [{
            'id': str(row[0]),
            'name': row[1],
            'description': row[2],
            'tag_name': row[3],
            'action': row[4],
            'schedule_type': row[5],
            'schedule_value': row[6],
            'days_of_week': row[7],
            'enabled': row[8],
            'last_run': row[9],
            'last_result': row[10],
            'next_run': row[11],
            'plc_name': row[12],
            'plc_ip': row[13]
        } for row in rows]
    
    def get_due_chores(self) -> List[Dict]:
        """Get chores that are due to run"""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT c.id, c.name, c.tag_name, c.action, c.action_value,
                       c.schedule_type, c.schedule_value,
                       p.id as plc_id, p.ip_address, p.slot, p.plc_type
                FROM chores c
                JOIN plc_config p ON c.plc_id = p.id
                WHERE c.enabled = true 
                AND p.enabled = true
                AND c.next_run <= CURRENT_TIMESTAMP
                ORDER BY c.next_run
            """)
            rows = cur.fetchall()
        
        return [{
            'chore_id': str(row[0]),
            'name': row[1],
            'tag_name': row[2],
            'action': row[3],
            'action_value': row[4],
            'schedule_type': row[5],
            'schedule_value': row[6],
            'plc_id': str(row[7]),
            'ip_address': row[8],
            'slot': row[9],
            'plc_type': row[10]
        } for row in rows]
    
    def update_chore_run(self, chore_id: str, result: str, next_run: datetime,
                         error: str = None):
        """Update chore after execution"""
        with self.conn.cursor() as cur:
            cur.execute("""
                UPDATE chores 
                SET last_run = CURRENT_TIMESTAMP,
                    last_result = %s,
                    last_error = %s,
                    next_run = %s,
                    run_count = run_count + 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (result, error, next_run, chore_id))
            self.conn.commit()
    
    def log_chore_execution(self, chore_id: str, chore_name: str, plc_name: str,
                           tag_name: str, action: str, result: str,
                           action_value: str = None, error: str = None,
                           execution_time_ms: int = None):
        """Log a chore execution"""
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO chore_log (chore_id, chore_name, plc_name, tag_name,
                                      action, action_value, result, error_message, execution_time_ms)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (chore_id, chore_name, plc_name, tag_name, action, action_value,
                  result, error, execution_time_ms))
            self.conn.commit()
    
    # ==========================================
    # REMINDERS OPERATIONS
    # ==========================================
    
    def add_reminder(self, message: str, trigger_time: datetime,
                     notify_voice: bool = True, notify_email: bool = False,
                     notify_sms: bool = False, repeat_type: str = 'once',
                     repeat_days: str = None) -> str:
        """
        Add a new reminder
        
        Args:
            message: Reminder message
            trigger_time: When to trigger the reminder
            notify_voice: Send voice notification
            notify_email: Send email notification
            notify_sms: Send SMS notification
            repeat_type: once, daily, weekly, monthly
            repeat_days: For weekly - comma-separated days
        
        Returns:
            UUID of the new reminder
        """
        reminder_id = str(uuid.uuid4())
        
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO reminders (id, message, trigger_time, notify_voice,
                                      notify_email, notify_sms, repeat_type, repeat_days)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (reminder_id, message, trigger_time, notify_voice, notify_email,
                  notify_sms, repeat_type, repeat_days))
            self.conn.commit()
        
        logger.info(f"Added reminder: {message[:50]}... for {trigger_time}")
        return reminder_id
    
    def update_reminder(self, reminder_id: str, **kwargs) -> bool:
        """Update reminder configuration"""
        allowed_fields = ['message', 'trigger_time', 'notify_voice', 'notify_email',
                         'notify_sms', 'repeat_type', 'repeat_days', 'status']
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
        
        if not updates:
            return False
        
        set_clause = ", ".join([f"{k} = %s" for k in updates.keys()])
        values = list(updates.values()) + [reminder_id]
        
        with self.conn.cursor() as cur:
            cur.execute(f"""
                UPDATE reminders 
                SET {set_clause}, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, values)
            self.conn.commit()
        
        return True
    
    def delete_reminder(self, reminder_id: str) -> bool:
        """Delete a reminder"""
        with self.conn.cursor() as cur:
            cur.execute("DELETE FROM reminders WHERE id = %s", (reminder_id,))
            self.conn.commit()
        
        logger.info(f"Deleted reminder {reminder_id}")
        return True
    
    def get_reminder(self, reminder_id: str) -> Optional[Dict]:
        """Get a single reminder by ID"""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT id, message, trigger_time, notify_voice, notify_email,
                       notify_sms, repeat_type, repeat_days, status, created_at
                FROM reminders WHERE id = %s
            """, (reminder_id,))
            row = cur.fetchone()
        
        if row:
            return {
                'id': str(row[0]),
                'message': row[1],
                'trigger_time': row[2],
                'notify_voice': row[3],
                'notify_email': row[4],
                'notify_sms': row[5],
                'repeat_type': row[6],
                'repeat_days': row[7],
                'status': row[8],
                'created_at': row[9]
            }
        return None
    
    def get_pending_reminders(self) -> List[Dict]:
        """Get all pending reminders"""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT id, message, trigger_time, notify_voice, notify_email,
                       notify_sms, repeat_type
                FROM reminders
                WHERE status = 'pending'
                ORDER BY trigger_time
            """)
            rows = cur.fetchall()
        
        return [{
            'id': str(row[0]),
            'message': row[1],
            'trigger_time': row[2],
            'notify_voice': row[3],
            'notify_email': row[4],
            'notify_sms': row[5],
            'repeat_type': row[6]
        } for row in rows]
    
    def get_due_reminders(self) -> List[Dict]:
        """Get reminders that are due to trigger"""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT id, message, trigger_time, notify_voice, notify_email,
                       notify_sms, repeat_type, repeat_days
                FROM reminders
                WHERE status = 'pending'
                AND trigger_time <= CURRENT_TIMESTAMP
                ORDER BY trigger_time
            """)
            rows = cur.fetchall()
        
        return [{
            'id': str(row[0]),
            'message': row[1],
            'trigger_time': row[2],
            'notify_voice': row[3],
            'notify_email': row[4],
            'notify_sms': row[5],
            'repeat_type': row[6],
            'repeat_days': row[7]
        } for row in rows]
    
    def mark_reminder_sent(self, reminder_id: str, next_trigger: datetime = None):
        """Mark reminder as sent, optionally reschedule for repeat"""
        with self.conn.cursor() as cur:
            if next_trigger:
                # Reschedule for next occurrence
                cur.execute("""
                    UPDATE reminders 
                    SET sent_at = CURRENT_TIMESTAMP,
                        trigger_time = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (next_trigger, reminder_id))
            else:
                # Mark as sent (no repeat)
                cur.execute("""
                    UPDATE reminders 
                    SET status = 'sent',
                        sent_at = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (reminder_id,))
            self.conn.commit()
    
    def snooze_reminder(self, reminder_id: str, snooze_minutes: int = 5):
        """Snooze a reminder"""
        snooze_until = datetime.now() + timedelta(minutes=snooze_minutes)
        
        with self.conn.cursor() as cur:
            cur.execute("""
                UPDATE reminders 
                SET status = 'snoozed',
                    snooze_until = %s,
                    trigger_time = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (snooze_until, snooze_until, reminder_id))
            self.conn.commit()
        
        logger.info(f"Snoozed reminder {reminder_id} for {snooze_minutes} minutes")
    
    def log_reminder_notification(self, reminder_id: str, message: str,
                                  channel: str, result: str, error: str = None):
        """Log a reminder notification"""
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO reminder_log (reminder_id, message, channel, result, error_message)
                VALUES (%s, %s, %s, %s, %s)
            """, (reminder_id, message, channel, result, error))
            self.conn.commit()
    
    # ==========================================
    # USER SETTINGS OPERATIONS
    # ==========================================
    
    def get_setting(self, key: str) -> Optional[str]:
        """Get a user setting value"""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT setting_value FROM user_settings WHERE setting_key = %s
            """, (key,))
            row = cur.fetchone()
        
        return row[0] if row else None
    
    def set_setting(self, key: str, value: str, setting_type: str = 'string'):
        """Set a user setting value"""
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO user_settings (setting_key, setting_value, setting_type)
                VALUES (%s, %s, %s)
                ON CONFLICT (setting_key) 
                DO UPDATE SET setting_value = %s, updated_at = CURRENT_TIMESTAMP
            """, (key, value, setting_type, value))
            self.conn.commit()
        
        logger.info(f"Set setting {key} = {value}")
    
    def get_all_settings(self) -> Dict[str, str]:
        """Get all user settings as a dictionary"""
        with self.conn.cursor() as cur:
            cur.execute("SELECT setting_key, setting_value FROM user_settings")
            rows = cur.fetchall()
        
        return {row[0]: row[1] for row in rows}
    
    def get_location(self) -> Dict[str, str]:
        """Get location settings"""
        return {
            'city': self.get_setting('location_city'),
            'zip': self.get_setting('location_zip'),
            'lat': self.get_setting('location_lat'),
            'lon': self.get_setting('location_lon'),
            'timezone': self.get_setting('location_timezone')
        }
    
    def set_location(self, city: str = None, zip_code: str = None,
                     lat: str = None, lon: str = None, timezone: str = None):
        """Set location settings"""
        if city:
            self.set_setting('location_city', city)
        if zip_code:
            self.set_setting('location_zip', zip_code)
        if lat:
            self.set_setting('location_lat', lat)
        if lon:
            self.set_setting('location_lon', lon)
        if timezone:
            self.set_setting('location_timezone', timezone)


def initialize_chore_database(db_connection) -> ChoreDatabase:
    """
    Initialize the chore database with an existing connection
    
    Args:
        db_connection: Existing psycopg2 connection
    
    Returns:
        ChoreDatabase instance
    """
    return ChoreDatabase(db_connection)
