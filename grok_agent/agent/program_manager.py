"""
Program Manager - PostgreSQL Version
Manages PLC program uploads, versioning, and comparisons
"""

import logging
import hashlib
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class ProgramManager:
    """
    Manages PLC program versions and provides access to program structure
    """
    
    def __init__(self, chore_db):
        """
        Initialize with existing database connection
        
        Args:
            chore_db: ChoreDatabase instance with PostgreSQL connection
        """
        self.conn = chore_db.conn
        logger.info("ProgramManager initialized")
    
    # ==========================================
    # PROGRAM VERSION OPERATIONS
    # ==========================================
    
    def upload_program(self, plc_id: str, l5x_file_path: str, 
                      uploaded_by: str, version_name: str = None,
                      notes: str = None, archive_dir: str = None) -> int:
        """
        Upload and parse a new program version
        
        Args:
            plc_id: UUID of the PLC
            l5x_file_path: Path to L5X file
            uploaded_by: Who uploaded it
            version_name: Optional version name
            notes: Optional notes
            archive_dir: Where to archive L5X file
        
        Returns:
            version_id of the new program version
        """
        from agent.l5x_parser import L5XParser
        
        # Parse the L5X file
        logger.info(f"Parsing L5X file: {l5x_file_path}")
        parser = L5XParser()
        program_data = parser.parse_file(l5x_file_path)

        # ADD THIS LOGGING
        controller_info = program_data.get('controller', {})
        logger.info(f"Controller info from parser: {controller_info}")
        
        # Calculate checksum
        checksum = self._calculate_file_checksum(l5x_file_path)
        
        # Archive the file
        archived_path = None
        if archive_dir:
            archived_path = self._archive_file(l5x_file_path, archive_dir, plc_id)
        
        # Auto-generate version name if not provided
        if not version_name:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            version_name = f"Upload_{timestamp}"
        
        # Create program version record with controller info
        controller_info = program_data.get('controller', {})
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO program_versions 
                (plc_id, version_name, uploaded_by, file_path, checksum, notes,
                 controller_name, processor_type, major_revision, minor_revision)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING version_id
            """, (plc_id, version_name, uploaded_by, archived_path, checksum, notes,
                  controller_info.get('name'), controller_info.get('processor_type'),
                  controller_info.get('major_revision'), controller_info.get('minor_revision')))
            
            version_id = cur.fetchone()[0]
            self.conn.commit()
        
        logger.info(f"Created program version {version_id}: {version_name}")
        
        # Store program structure
        self._store_program_structure(version_id, program_data)
        
        return version_id
    
    def _calculate_file_checksum(self, file_path: str) -> str:
        """Calculate SHA256 checksum of file"""
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256.update(chunk)
        return sha256.hexdigest()
    
    def _archive_file(self, source_path: str, archive_dir: str, plc_id: str) -> str:
        """Archive L5X file with timestamp"""
        archive_path = Path(archive_dir)
        archive_path.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = Path(source_path).name
        archived_file = archive_path / f"{plc_id}_{timestamp}_{filename}"
        
        shutil.copy2(source_path, archived_file)
        logger.info(f"Archived file to: {archived_file}")
        
        return str(archived_file)
    
    def _store_program_structure(self, version_id: int, program_data: Dict):
        """Store parsed program structure in database"""
        
        try:
            with self.conn.cursor() as cur:
                # Store tags - parser returns 'tag_name' not 'name'
                tags = program_data.get('tags', [])
                logger.info(f"Storing {len(tags)} tags")
                for tag in tags:
                    try:
                        cur.execute("""
                            INSERT INTO program_tags 
                            (version_id, tag_name, tag_type, scope, description)
                            VALUES (%s, %s, %s, %s, %s)
                        """, (
                            version_id,
                            tag.get('tag_name'),
                            tag.get('data_type'),
                            tag.get('scope'),
                            tag.get('description')
                        ))
                    except Exception as e:
                        logger.error(f"Error inserting tag {tag.get('tag_name')}: {e}")
                
                # Get all rungs from top level
                all_rungs = program_data.get('rungs', [])
                
                # Store routines and their rungs
                routines = program_data.get('routines', [])
                logger.info(f"Storing {len(routines)} routines")
                for routine in routines:
                    try:
                        routine_name = routine.get('name')
                        
                        # Create routine
                        cur.execute("""
                            INSERT INTO program_routines 
                            (version_id, routine_name, routine_type, description)
                            VALUES (%s, %s, %s, %s)
                            RETURNING routine_id
                        """, (
                            version_id,
                            routine_name,
                            routine.get('type'),
                            routine.get('description')
                        ))
                        
                        routine_id = cur.fetchone()[0]
                        
                        # Find rungs that belong to this routine from the top-level rungs list
                        routine_rungs = [r for r in all_rungs if r.get('routine') == routine_name]
                        
                        logger.info(f"Storing {len(routine_rungs)} rungs for routine {routine_name}")
                        for rung in routine_rungs:
                            cur.execute("""
                                INSERT INTO program_rungs 
                                (routine_id, rung_number, rung_text, comment, 
                                 tags_read, tags_written)
                                VALUES (%s, %s, %s, %s, %s, %s)
                            """, (
                                routine_id,
                                rung.get('rung_number'),
                                rung.get('rung_text'),
                                rung.get('comment'),
                                ','.join(rung.get('tags_read', [])),
                                ','.join(rung.get('tags_written', []))
                            ))
                    except Exception as e:
                        logger.error(f"Error inserting routine {routine.get('name')}: {e}")
                        import traceback
                        logger.error(traceback.format_exc())
                
                self.conn.commit()
                logger.info(f"Successfully stored program structure for version {version_id}")
            
        except Exception as e:
            logger.error(f"Error storing program structure: {e}")
            import traceback
            logger.error(traceback.format_exc())
            self.conn.rollback()
            raise
    
    def get_program_versions(self, plc_id: str) -> List[Dict]:
        """Get all program versions for a PLC"""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT version_id, version_name, upload_timestamp, 
                       uploaded_by, notes, is_active
                FROM program_versions
                WHERE plc_id = %s
                ORDER BY upload_timestamp DESC
            """, (plc_id,))
            
            rows = cur.fetchall()
        
        return [{
            'version_id': row[0],
            'version_name': row[1],
            'upload_timestamp': row[2],
            'uploaded_by': row[3],
            'notes': row[4],
            'is_active': row[5]
        } for row in rows]
    
    def get_program_version(self, version_id: int) -> Optional[Dict]:
        """Get a single program version by ID"""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT version_id, plc_id, version_name, upload_timestamp, 
                       uploaded_by, file_path, checksum, notes, is_active,
                       controller_name, processor_type, major_revision, minor_revision
                FROM program_versions
                WHERE version_id = %s
            """, (version_id,))
            
            row = cur.fetchone()
        
        if row:
            return {
                'version_id': row[0],
                'plc_id': str(row[1]),
                'version_name': row[2],
                'upload_timestamp': row[3],
                'uploaded_by': row[4],
                'file_path': row[5],
                'checksum': row[6],
                'notes': row[7],
                'is_active': row[8],
                'controller_name': row[9],
                'processor_type': row[10],
                'major_revision': row[11],
                'minor_revision': row[12]
            }
        return None
    
    def set_active_version(self, version_id: int, plc_id: str):
        """Set a version as the active one for analysis"""
        with self.conn.cursor() as cur:
            # Deactivate all versions for this PLC
            cur.execute("""
                UPDATE program_versions 
                SET is_active = FALSE 
                WHERE plc_id = %s
            """, (plc_id,))
            
            # Activate the selected version
            cur.execute("""
                UPDATE program_versions 
                SET is_active = TRUE 
                WHERE version_id = %s
            """, (version_id,))
            
            self.conn.commit()
        
        logger.info(f"Set version {version_id} as active")
    
    def delete_version(self, version_id: int):
        """Delete a program version (cascades to routines/rungs/tags)"""
        with self.conn.cursor() as cur:
            cur.execute("DELETE FROM program_versions WHERE version_id = %s", (version_id,))
            self.conn.commit()
        
        logger.info(f"Deleted program version {version_id}")
    
    # ==========================================
    # PROGRAM STRUCTURE QUERIES
    # ==========================================
    
    def get_routines(self, version_id: int) -> List[Dict]:
        """Get all routines in a program version"""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT r.routine_id, r.routine_name, r.routine_type, r.description,
                       COUNT(rg.rung_id) as rung_count
                FROM program_routines r
                LEFT JOIN program_rungs rg ON r.routine_id = rg.routine_id
                WHERE r.version_id = %s
                GROUP BY r.routine_id, r.routine_name, r.routine_type, r.description
                ORDER BY r.routine_name
            """, (version_id,))
            
            rows = cur.fetchall()
        
        return [{
            'routine_id': row[0],
            'routine_name': row[1],
            'routine_type': row[2],
            'description': row[3],
            'rung_count': row[4],
            'program_name': ''  # Not stored in schema yet
        } for row in rows]
    
    def get_rungs(self, routine_id: int) -> List[Dict]:
        """Get all rungs in a routine"""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT rung_id, rung_number, rung_text, comment,
                       tags_read, tags_written
                FROM program_rungs
                WHERE routine_id = %s
                ORDER BY rung_number
            """, (routine_id,))
            
            rows = cur.fetchall()
        
        return [{
            'rung_id': row[0],
            'rung_number': row[1],
            'rung_text': row[2],
            'comment': row[3],
            'tags_read': row[4].split(',') if row[4] else [],
            'tags_written': row[5].split(',') if row[5] else []
        } for row in rows]
    
    def get_program_tags(self, version_id: int) -> List[Dict]:
        """Get all tags in a program version"""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT tag_name, tag_type, scope, description
                FROM program_tags
                WHERE version_id = %s
                ORDER BY tag_name
            """, (version_id,))
            
            rows = cur.fetchall()
        
        return [{
            'tag_name': row[0],
            'data_type': row[1],
            'scope': row[2],
            'description': row[3]
        } for row in rows]
    
    def find_rungs_affecting_tag(self, version_id: int, tag_name: str) -> List[Dict]:
        """Find all rungs that read or write a specific tag"""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT r.routine_name, rg.rung_number, rg.rung_text, 
                       rg.comment, rg.tags_read, rg.tags_written
                FROM program_rungs rg
                JOIN program_routines r ON rg.routine_id = r.routine_id
                WHERE r.version_id = %s
                AND (rg.tags_read LIKE %s OR rg.tags_written LIKE %s)
                ORDER BY r.routine_name, rg.rung_number
            """, (version_id, f'%{tag_name}%', f'%{tag_name}%'))
            
            rows = cur.fetchall()
        
        return [{
            'routine_name': row[0],
            'rung_number': row[1],
            'rung_text': row[2],
            'comment': row[3],
            'tags_read': row[4].split(',') if row[4] else [],
            'tags_written': row[5].split(',') if row[5] else []
        } for row in rows]
    
    def get_active_version_id(self, plc_id: str) -> Optional[int]:
        """Get the active version ID for a PLC"""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT version_id FROM program_versions
                WHERE plc_id = %s AND is_active = TRUE
                LIMIT 1
            """, (plc_id,))
            
            row = cur.fetchone()
        
        return row[0] if row else None
    
    # ==========================================
    # VERSION COMPARISON
    # ==========================================
    
    def compare_versions(self, version_id_1: int, version_id_2: int) -> Dict:
        """
        Compare two program versions
        
        Returns:
            Dict with added, deleted, and modified rungs
        """
        # Get routines from both versions
        routines_1 = {r['routine_name']: r for r in self.get_routines(version_id_1)}
        routines_2 = {r['routine_name']: r for r in self.get_routines(version_id_2)}
        
        added_routines = set(routines_2.keys()) - set(routines_1.keys())
        deleted_routines = set(routines_1.keys()) - set(routines_2.keys())
        common_routines = set(routines_1.keys()) & set(routines_2.keys())
        
        # Compare rungs in common routines
        modified_rungs = []
        
        for routine_name in common_routines:
            r1_id = routines_1[routine_name]['routine_id']
            r2_id = routines_2[routine_name]['routine_id']
            
            rungs_1 = {r['rung_number']: r for r in self.get_rungs(r1_id)}
            rungs_2 = {r['rung_number']: r for r in self.get_rungs(r2_id)}
            
            for rung_num in rungs_1.keys() & rungs_2.keys():
                if rungs_1[rung_num]['rung_text'] != rungs_2[rung_num]['rung_text']:
                    modified_rungs.append({
                        'routine': routine_name,
                        'rung_number': rung_num,
                        'old_text': rungs_1[rung_num]['rung_text'],
                        'new_text': rungs_2[rung_num]['rung_text']
                    })
        
        return {
            'added_routines': list(added_routines),
            'deleted_routines': list(deleted_routines),
            'modified_rungs': modified_rungs
        }


def initialize_program_manager(chore_db) -> ProgramManager:
    """
    Initialize the program manager
    
    Args:
        chore_db: ChoreDatabase instance
    
    Returns:
        ProgramManager instance
    """
    return ProgramManager(chore_db)