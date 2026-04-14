"""
Optimization Suggestions Manager for PostgreSQL
Handles database operations for optimization suggestions
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import json
import logging
from datetime import datetime
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class OptimizationManager:
    """Manages optimization suggestions in PostgreSQL database"""
    
    def __init__(self, db_connection_params):
        """
        Initialize optimization manager
        
        Args:
            db_connection_params: Dict with host, database, user, password, port
        """
        self.db_params = db_connection_params
        self._ensure_tables()
    
    def _get_connection(self):
        """Get database connection"""
        return psycopg2.connect(**self.db_params)
    
    def _ensure_tables(self):
       """Ensure optimization tables exist"""
       # Tables already created via pgAdmin - no action needed
       pass
    
    # ========== CREATE ==========
    
    def add_suggestion(self, suggestion_data: Dict) -> int:
        """
        Add a new optimization suggestion
        
        Args:
            suggestion_data: Dict with suggestion fields
            
        Returns:
            suggestion_id of created suggestion
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Convert lists to JSON strings
        related_tags = json.dumps(suggestion_data.get('related_tags', []))
        related_routines = json.dumps(suggestion_data.get('related_routines', []))
        
        cursor.execute("""
            INSERT INTO optimization_suggestions (
                title, detailed_description, category, priority, status,
                related_tags, related_routines, conditions, expected_benefit,
                estimated_savings_amount, estimated_savings_period,
                implementation_details, created_by, agent_can_suggest,
                requires_approval, plc_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING suggestion_id
        """, (
            suggestion_data.get('title'),
            suggestion_data.get('detailed_description'),
            suggestion_data.get('category'),
            suggestion_data.get('priority'),
            suggestion_data.get('status', 'Idea'),
            related_tags,
            related_routines,
            suggestion_data.get('conditions'),
            suggestion_data.get('expected_benefit'),
            suggestion_data.get('estimated_savings_amount'),
            suggestion_data.get('estimated_savings_period'),
            suggestion_data.get('implementation_details'),
            suggestion_data.get('created_by'),
            suggestion_data.get('agent_can_suggest', True),
            suggestion_data.get('requires_approval', True),
            suggestion_data.get('plc_id')
        ))
        
        suggestion_id = cursor.fetchone()[0]
        
        # Log creation
        self._add_history(
            cursor,
            suggestion_id,
            'created',
            suggestion_data.get('created_by'),
            f"Created suggestion: {suggestion_data.get('title')}"
        )
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info(f"Added suggestion #{suggestion_id}: {suggestion_data.get('title')}")
        return suggestion_id
    
    # ========== READ ==========
    
    def get_all_suggestions(self, filters: Optional[Dict] = None) -> List[Dict]:
        """
        Get all suggestions with optional filters
        
        Args:
            filters: Dict with category, status, priority, search_text
            
        Returns:
            List of suggestion dicts
        """
        conn = self._get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        query = "SELECT * FROM optimization_suggestions WHERE 1=1"
        params = []
        
        if filters:
            if filters.get('category') and filters['category'] != 'All':
                query += " AND category = %s"
                params.append(filters['category'])
            
            if filters.get('status') and filters['status'] != 'All':
                query += " AND status = %s"
                params.append(filters['status'])
            
            if filters.get('priority') and filters['priority'] != 'All':
                query += " AND priority = %s"
                params.append(filters['priority'])
            
            if filters.get('search_text'):
                search = f"%{filters['search_text']}%"
                query += """ AND (
                    title ILIKE %s OR 
                    detailed_description ILIKE %s OR 
                    related_tags ILIKE %s OR
                    created_by ILIKE %s
                )"""
                params.extend([search, search, search, search])
            
            if filters.get('plc_id'):
                query += " AND (plc_id = %s OR plc_id IS NULL)"
                params.append(filters['plc_id'])
        
        query += " ORDER BY created_timestamp DESC"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        suggestions = []
        for row in rows:
            suggestion = dict(row)
            # Parse JSON fields
            suggestion['related_tags'] = json.loads(suggestion['related_tags'] or '[]')
            suggestion['related_routines'] = json.loads(suggestion['related_routines'] or '[]')
            suggestions.append(suggestion)
        
        return suggestions
    
    def get_suggestion(self, suggestion_id: int) -> Optional[Dict]:
        """Get a single suggestion by ID"""
        conn = self._get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("""
            SELECT * FROM optimization_suggestions WHERE suggestion_id = %s
        """, (suggestion_id,))
        
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if row:
            suggestion = dict(row)
            suggestion['related_tags'] = json.loads(suggestion['related_tags'] or '[]')
            suggestion['related_routines'] = json.loads(suggestion['related_routines'] or '[]')
            return suggestion
        return None
    
    def get_suggestions_for_tag(self, tag_name: str) -> List[Dict]:
        """Get all suggestions related to a specific tag"""
        all_suggestions = self.get_all_suggestions()
        related = []
        
        for suggestion in all_suggestions:
            if tag_name in suggestion.get('related_tags', []):
                related.append(suggestion)
        
        return related
    
    def get_agent_suggestions(self) -> List[Dict]:
        """Get suggestions that agent can auto-suggest"""
        conn = self._get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("""
            SELECT * FROM optimization_suggestions 
            WHERE agent_can_suggest = TRUE 
            AND status IN ('Approved', 'Verified')
            ORDER BY priority DESC
        """)
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        suggestions = []
        for row in rows:
            suggestion = dict(row)
            suggestion['related_tags'] = json.loads(suggestion['related_tags'] or '[]')
            suggestion['related_routines'] = json.loads(suggestion['related_routines'] or '[]')
            suggestions.append(suggestion)
        
        return suggestions
    
    # ========== UPDATE ==========
    
    def update_suggestion(self, suggestion_id: int, updates: Dict, updated_by: str) -> bool:
        """
        Update a suggestion
        
        Args:
            suggestion_id: ID of suggestion to update
            updates: Dict with fields to update
            updated_by: Username performing update
            
        Returns:
            True if successful
        """
        try:
            # Get old values for history
            old_suggestion = self.get_suggestion(suggestion_id)
            if not old_suggestion:
                return False
            
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Convert lists to JSON if present
            if 'related_tags' in updates and isinstance(updates['related_tags'], list):
                updates['related_tags'] = json.dumps(updates['related_tags'])
            if 'related_routines' in updates and isinstance(updates['related_routines'], list):
                updates['related_routines'] = json.dumps(updates['related_routines'])
            
            # Build update query
            set_clause = ', '.join([f"{key} = %s" for key in updates.keys()])
            query = f"UPDATE optimization_suggestions SET {set_clause} WHERE suggestion_id = %s"
            
            cursor.execute(query, list(updates.values()) + [suggestion_id])
            
            # Log changes
            for key, new_value in updates.items():
                old_value = old_suggestion.get(key)
                if old_value != new_value:
                    self._add_history(
                        cursor,
                        suggestion_id,
                        'modified',
                        updated_by,
                        f"Changed {key}",
                        str(old_value),
                        str(new_value)
                    )
            
            conn.commit()
            cursor.close()
            conn.close()
            
            logger.info(f"Updated suggestion #{suggestion_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating suggestion: {e}")
            return False
    
    def change_status(self, suggestion_id: int, new_status: str, changed_by: str, notes: str = "") -> bool:
        """
        Change suggestion status with logging
        
        Args:
            suggestion_id: ID of suggestion
            new_status: New status value
            changed_by: Username
            notes: Optional notes about status change
            
        Returns:
            True if successful
        """
        try:
            old_suggestion = self.get_suggestion(suggestion_id)
            if not old_suggestion:
                return False
            
            old_status = old_suggestion['status']
            
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE optimization_suggestions 
                SET status = %s 
                WHERE suggestion_id = %s
            """, (new_status, suggestion_id))
            
            # Log status change
            self._add_history(
                cursor,
                suggestion_id,
                'status_changed',
                changed_by,
                notes or f"Status changed from {old_status} to {new_status}",
                old_status,
                new_status
            )
            
            # If implemented, set implementation date
            if new_status == 'Implemented':
                cursor.execute("""
                    UPDATE optimization_suggestions 
                    SET implemented_date = NOW() 
                    WHERE suggestion_id = %s
                """, (suggestion_id,))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            logger.info(f"Changed status for suggestion #{suggestion_id}: {old_status} → {new_status}")
            return True
            
        except Exception as e:
            logger.error(f"Error changing status: {e}")
            return False
    
    def update_results(self, suggestion_id: int, results: str, updated_by: str) -> bool:
        """Update implementation results"""
        return self.update_suggestion(
            suggestion_id,
            {'results': results},
            updated_by
        )
    
    # ========== DELETE ==========
    
    def delete_suggestion(self, suggestion_id: int, deleted_by: str) -> bool:
        """
        Delete a suggestion (with history preservation)
        
        Args:
            suggestion_id: ID to delete
            deleted_by: Username
            
        Returns:
            True if successful
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Log deletion
            self._add_history(
                cursor,
                suggestion_id,
                'deleted',
                deleted_by,
                "Suggestion deleted"
            )
            
            # Delete the suggestion (history will be preserved due to ON DELETE CASCADE)
            cursor.execute("""
                DELETE FROM optimization_suggestions WHERE suggestion_id = %s
            """, (suggestion_id,))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            logger.info(f"Deleted suggestion #{suggestion_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting suggestion: {e}")
            return False
    
    # ========== HISTORY ==========
    
    def _add_history(self, cursor, suggestion_id: int, action: str, performed_by: str, 
                     notes: str = "", old_value: str = "", new_value: str = ""):
        """Internal method to add history entry"""
        cursor.execute("""
            INSERT INTO suggestion_history (
                suggestion_id, action, performed_by, notes, old_status, new_status
            ) VALUES (%s, %s, %s, %s, %s, %s)
        """, (suggestion_id, action, performed_by, notes, old_value, new_value))
    
    def get_suggestion_history(self, suggestion_id: int) -> List[Dict]:
        """Get full history for a suggestion"""
        conn = self._get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("""
            SELECT * FROM suggestion_history 
            WHERE suggestion_id = %s 
            ORDER BY timestamp DESC
        """, (suggestion_id,))
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return [dict(row) for row in rows]
    
    # ========== AGENT PENDING ==========
    
    def add_agent_pending(self, pending_data: Dict) -> int:
        """Add an agent-discovered suggestion to pending review"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Convert lists to JSON
        related_tags = json.dumps(pending_data.get('related_tags', []))
        related_routines = json.dumps(pending_data.get('related_routines', []))
        
        cursor.execute("""
            INSERT INTO agent_pending_suggestions (
                title, description, confidence_level, expected_savings,
                related_tags, related_routines, conditions, raw_data
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING pending_id
        """, (
            pending_data.get('title'),
            pending_data.get('description'),
            pending_data.get('confidence_level', 'Medium'),
            pending_data.get('expected_savings'),
            related_tags,
            related_routines,
            pending_data.get('conditions'),
            json.dumps(pending_data.get('raw_data', {}))
        ))
        
        pending_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info(f"Added agent pending suggestion #{pending_id}")
        return pending_id
    
    def get_agent_pending(self, reviewed: bool = False) -> List[Dict]:
        """Get agent pending suggestions"""
        conn = self._get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("""
            SELECT * FROM agent_pending_suggestions 
            WHERE reviewed = %s 
            ORDER BY detected_timestamp DESC
        """, (reviewed,))
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        pending = []
        for row in rows:
            item = dict(row)
            item['related_tags'] = json.loads(item['related_tags'] or '[]')
            item['related_routines'] = json.loads(item['related_routines'] or '[]')
            item['raw_data'] = json.loads(item['raw_data'] or '{}')
            pending.append(item)
        
        return pending
    
    def import_agent_pending(self, pending_id: int, created_by: str) -> Optional[int]:
        """Import agent pending into main suggestions"""
        pending = self.get_agent_pending_by_id(pending_id)
        if not pending:
            return None
        
        # Create suggestion from pending
        suggestion_data = {
            'title': pending['title'],
            'detailed_description': pending['description'],
            'category': 'Efficiency',  # Default, can be changed later
            'priority': 'Medium',
            'status': 'Proposed',
            'related_tags': pending['related_tags'],
            'related_routines': pending['related_routines'],
            'conditions': pending['conditions'],
            'expected_benefit': pending['expected_savings'],
            'created_by': f"Agent (imported by {created_by})",
            'agent_can_suggest': True,
            'requires_approval': True
        }
        
        suggestion_id = self.add_suggestion(suggestion_data)
        
        # Mark pending as reviewed and imported
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE agent_pending_suggestions 
            SET reviewed = TRUE, imported_as_suggestion_id = %s 
            WHERE pending_id = %s
        """, (suggestion_id, pending_id))
        conn.commit()
        cursor.close()
        conn.close()
        
        return suggestion_id
    
    def get_agent_pending_by_id(self, pending_id: int) -> Optional[Dict]:
        """Get single pending suggestion by ID"""
        conn = self._get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("""
            SELECT * FROM agent_pending_suggestions WHERE pending_id = %s
        """, (pending_id,))
        
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if row:
            item = dict(row)
            item['related_tags'] = json.loads(item['related_tags'] or '[]')
            item['related_routines'] = json.loads(item['related_routines'] or '[]')
            item['raw_data'] = json.loads(item['raw_data'] or '{}')
            return item
        return None
    
    # ========== STATISTICS ==========
    
    def get_statistics(self) -> Dict:
        """Get summary statistics"""
        conn = self._get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        stats = {}
        
        # Total suggestions
        cursor.execute("SELECT COUNT(*) as count FROM optimization_suggestions")
        stats['total'] = cursor.fetchone()['count']
        
        # By status
        cursor.execute("""
            SELECT status, COUNT(*) as count FROM optimization_suggestions GROUP BY status
        """)
        stats['by_status'] = {row['status']: row['count'] for row in cursor.fetchall()}
        
        # By category
        cursor.execute("""
            SELECT category, COUNT(*) as count FROM optimization_suggestions GROUP BY category
        """)
        stats['by_category'] = {row['category']: row['count'] for row in cursor.fetchall()}
        
        # By priority
        cursor.execute("""
            SELECT priority, COUNT(*) as count FROM optimization_suggestions GROUP BY priority
        """)
        stats['by_priority'] = {row['priority']: row['count'] for row in cursor.fetchall()}
        
        # Total estimated savings
        cursor.execute("""
            SELECT SUM(estimated_savings_amount) as total FROM optimization_suggestions
            WHERE estimated_savings_period = 'Year'
        """)
        result = cursor.fetchone()['total']
        stats['estimated_annual_savings'] = float(result) if result else 0
        
        # Pending agent suggestions
        cursor.execute("""
            SELECT COUNT(*) as count FROM agent_pending_suggestions WHERE reviewed = FALSE
        """)
        stats['pending_agent'] = cursor.fetchone()['count']
        
        cursor.close()
        conn.close()
        return stats


def initialize_optimization_manager(db_connection_params):
    """
    Initialize and return OptimizationManager instance
    
    Args:
        db_connection_params: Dict with PostgreSQL connection params
        
    Returns:
        OptimizationManager instance
    """
    return OptimizationManager(db_connection_params)
