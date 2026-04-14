"""
Database module for Grok Agent
Handles all PostgreSQL operations
"""

import psycopg2
from psycopg2.extras import RealDictCursor, Json
from psycopg2.pool import SimpleConnectionPool
from datetime import datetime, timedelta
import uuid
import os
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class Database:
    """PostgreSQL database connection and operations"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize database connection pool"""
        self.config = config
        # Get password from environment variable
        password = os.getenv("DB_PASSWORD", config.get("password", ""))
        
        self.pool = SimpleConnectionPool(
            minconn=1,
            maxconn=10,
            host=config["host"],
            port=config["port"],
            database=config["database"],
            user=config["user"],
            password=password
        )
        logger.info("Database connection pool initialized")
    
    def get_connection(self):
        """Get a connection from the pool"""
        return self.pool.getconn()
    
    def release_connection(self, conn):
        """Return a connection to the pool"""
        self.pool.putconn(conn)
    
    def execute_query(self, query: str, params: tuple = None, fetch: bool = True):
        """Execute a query and return results"""
        conn = self.get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, params)
                if fetch:
                    result = cursor.fetchall()
                    # Commit for INSERT/UPDATE/DELETE even when fetching results
                    if query.strip().upper().startswith(('INSERT', 'UPDATE', 'DELETE')):
                        conn.commit()
                else:
                    conn.commit()
                    result = cursor.rowcount
                return result
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            self.release_connection(conn)
    
    # Conversation Operations
    
    def create_conversation(self, title: Optional[str] = None, tags: List[str] = None) -> str:
        """Create a new conversation and return its ID"""
        conversation_id = str(uuid.uuid4())
        query = """
            INSERT INTO conversations (id, title, tags)
            VALUES (%s, %s, %s)
            RETURNING id
        """
        result = self.execute_query(query, (conversation_id, title, tags))
        logger.info(f"Created conversation: {conversation_id}")
        return result[0]["id"]
    
    def get_conversation(self, conversation_id: str) -> Optional[Dict]:
        """Get conversation by ID"""
        query = "SELECT * FROM conversations WHERE id = %s"
        result = self.execute_query(query, (conversation_id,))
        return result[0] if result else None
    
    def get_recent_conversations(self, limit: int = 10) -> List[Dict]:
        """Get most recent conversations"""
        query = """
            SELECT * FROM conversation_summary
            ORDER BY updated_at DESC
            LIMIT %s
        """
        return self.execute_query(query, (limit,))
    
    def update_conversation_title(self, conversation_id: str, title: str):
        """Update conversation title"""
        query = "UPDATE conversations SET title = %s WHERE id = %s"
        self.execute_query(query, (title, conversation_id), fetch=False)
        logger.info(f"Updated conversation title: {conversation_id}")
    
    # Message Operations
    
    def add_message(
        self, 
        conversation_id: str, 
        role: str, 
        content: str,
        token_count: Optional[int] = None,
        metadata: Optional[Dict] = None
    ) -> str:
        """Add a message to a conversation"""
        message_id = str(uuid.uuid4())
        query = """
            INSERT INTO messages (id, conversation_id, role, content, token_count, metadata)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        """
        result = self.execute_query(
            query, 
            (message_id, conversation_id, role, content, token_count, Json(metadata) if metadata else None)
        )
        logger.info(f"Added {role} message to conversation: {conversation_id}")
        return result[0]["id"]
    
    def get_conversation_messages(
        self, 
        conversation_id: str, 
        limit: Optional[int] = None
    ) -> List[Dict]:
        """Get all messages in a conversation"""
        query = """
            SELECT * FROM messages 
            WHERE conversation_id = %s 
            ORDER BY created_at ASC
        """
        if limit:
            query += f" LIMIT {limit}"
        return self.execute_query(query, (conversation_id,))
    
    def get_recent_messages(self, conversation_id: str, limit: int = 10) -> List[Dict]:
        """Get the N most recent messages from a conversation"""
        query = """
            SELECT * FROM messages 
            WHERE conversation_id = %s 
            ORDER BY created_at DESC
            LIMIT %s
        """
        messages = self.execute_query(query, (conversation_id, limit))
        # Reverse to get chronological order
        return list(reversed(messages))
    
    # TIME-BASED QUERY FUNCTIONS (NEW)
    
    def get_last_conversation(self) -> Optional[Dict]:
        """Get the most recent conversation with its messages"""
        query = """
            SELECT c.*, 
                   (SELECT json_agg(m ORDER BY m.created_at)
                    FROM messages m 
                    WHERE m.conversation_id = c.id) as messages
            FROM conversations c
            ORDER BY c.updated_at DESC
            LIMIT 1
        """
        result = self.execute_query(query)
        return result[0] if result else None
    
    def get_conversations_by_date(self, target_date: datetime) -> List[Dict]:
        """Get all conversations that occurred on a specific date"""
        start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = target_date.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        query = """
            SELECT c.id, c.title, c.created_at, c.updated_at, c.message_count,
                   (SELECT json_agg(m ORDER BY m.created_at)
                    FROM messages m 
                    WHERE m.conversation_id = c.id) as messages
            FROM conversations c
            WHERE c.created_at >= %s AND c.created_at <= %s
            ORDER BY c.created_at DESC
        """
        result = self.execute_query(query, (start_of_day, end_of_day))
        logger.info(f"Found {len(result)} conversations on {target_date.strftime('%Y-%m-%d')}")
        return result
    
    def get_messages_by_time_range(self, start_time: datetime, end_time: datetime) -> List[Dict]:
        """Get all messages within a specific time range across all conversations"""
        query = """
            SELECT m.*, c.title as conversation_title
            FROM messages m
            JOIN conversations c ON m.conversation_id = c.id
            WHERE m.created_at >= %s AND m.created_at <= %s
            ORDER BY m.created_at ASC
        """
        result = self.execute_query(query, (start_time, end_time))
        logger.info(f"Found {len(result)} messages between {start_time} and {end_time}")
        return result
    
    def get_messages_around_timestamp(self, target_time: datetime, window_minutes: int = 30) -> List[Dict]:
        """
        Get messages around a specific timestamp (within a time window)
        
        Args:
            target_time: The target timestamp
            window_minutes: Minutes before and after (default: 30 minutes window)
        """
        start_time = target_time - timedelta(minutes=window_minutes)
        end_time = target_time + timedelta(minutes=window_minutes)
        
        query = """
            SELECT m.*, c.title as conversation_title
            FROM messages m
            JOIN conversations c ON m.conversation_id = c.id
            WHERE m.created_at >= %s AND m.created_at <= %s
            ORDER BY m.created_at ASC
        """
        result = self.execute_query(query, (start_time, end_time))
        logger.info(f"Found {len(result)} messages around {target_time} (±{window_minutes} min)")
        return result
    
    def get_conversations_by_date_range(self, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Get all conversations within a date range"""
        query = """
            SELECT c.id, c.title, c.created_at, c.updated_at, c.message_count,
                   (SELECT json_agg(m ORDER BY m.created_at)
                    FROM messages m 
                    WHERE m.conversation_id = c.id) as messages
            FROM conversations c
            WHERE c.created_at >= %s AND c.created_at <= %s
            ORDER BY c.created_at DESC
        """
        result = self.execute_query(query, (start_date, end_date))
        logger.info(f"Found {len(result)} conversations between {start_date} and {end_date}")
        return result
    
    # Memory/Search Operations (Basic for Phase 1)
    
    def search_conversations_by_keyword(self, keyword: str, limit: int = 5) -> List[Dict]:
        """Simple keyword search across conversations (Phase 1 version)"""
        query = """
            SELECT DISTINCT c.*, m.content as matching_content
            FROM conversations c
            JOIN messages m ON c.id = m.conversation_id
            WHERE m.content ILIKE %s
            ORDER BY c.updated_at DESC
            LIMIT %s
        """
        search_term = f"%{keyword}%"
        return self.execute_query(query, (search_term, limit))
    
    def get_all_messages_text(self, limit: int = 100) -> List[Dict]:
        """Get recent messages for context building"""
        query = """
            SELECT m.id, m.conversation_id, m.role, m.content, m.created_at, c.title
            FROM messages m
            JOIN conversations c ON m.conversation_id = c.id
            ORDER BY m.created_at DESC
            LIMIT %s
        """
        return self.execute_query(query, (limit,))
    
    # System Logging
    
    def log_system_event(self, level: str, message: str, details: Optional[Dict] = None):
        """Log system events to database"""
        query = """
            INSERT INTO system_logs (log_level, message, details)
            VALUES (%s, %s, %s)
        """
        self.execute_query(query, (level, message, Json(details) if details else None), fetch=False)
    
    def close(self):
        """Close all connections in the pool"""
        self.pool.closeall()
        logger.info("Database connection pool closed")


def initialize_database(db_config: Dict[str, Any]) -> Database:
    """Initialize and return database connection"""
    try:
        db = Database(db_config)
        logger.info("Database initialized successfully")
        return db
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise
