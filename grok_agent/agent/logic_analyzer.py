"""
PLC Logic Analyzer
Analyzes PLC program logic and monitors real-time status to generate control narratives
"""

import logging
from typing import Dict, List, Optional, Tuple
from program_manager import ProgramManager

logger = logging.getLogger(__name__)


class LogicAnalyzer:
    """Analyze PLC logic and generate control narratives"""
    
    def __init__(self, chore_db, plc_comm, program_manager: ProgramManager):
        """
        Initialize logic analyzer
        
        Args:
            chore_db: ChoreDatabase instance
            plc_comm: PLCCommunicator instance
            program_manager: ProgramManager instance
        """
        self.chore_db = chore_db
        self.plc_comm = plc_comm
        self.program_manager = program_manager
        
        # Cache of current program versions per PLC
        self.plc_versions = {}
    
    def set_plc_version(self, plc_id: int, version_id: int):
        """Set which program version to use for a PLC"""
        self.plc_versions[plc_id] = version_id
        logger.info(f"PLC {plc_id} now using program version {version_id}")
    
    def trace_tag_status(self, plc_id: int, tag_name: str) -> Dict:
        """
        Trace why a tag has its current value
        
        Args:
            plc_id: PLC ID
            tag_name: Tag name to trace
            
        Returns:
            Dict with trace information
        """
        # Get current value from PLC
        plc = self.chore_db.get_plc_by_id(plc_id)
        if not plc:
            return {'error': 'PLC not found'}
        
        result = self.plc_comm.read_tag(
            plc['ip_address'],
            tag_name,
            plc['slot'],
            plc['plc_type']
        )
        
        if not result.success:
            return {'error': f'Failed to read tag: {result.error}'}
        
        current_value = result.value
        
        # Get program version for this PLC
        version_id = self.plc_versions.get(plc_id)
        if not version_id:
            # Get most recent version
            versions = self.program_manager.get_program_versions(plc_id)
            if versions:
                version_id = versions[0]['version_id']
                self.plc_versions[plc_id] = version_id
            else:
                return {
                    'tag_name': tag_name,
                    'current_value': current_value,
                    'error': 'No program uploaded for this PLC'
                }
        
        # Find rungs that write to this tag
        affecting_rungs = self.program_manager.find_rungs_affecting_tag(version_id, tag_name)
        write_rungs = [r for r in affecting_rungs if r['affects_type'] == 'write']
        
        if not write_rungs:
            return {
                'tag_name': tag_name,
                'current_value': current_value,
                'controlled_by': 'Unknown (no rungs found that write to this tag)'
            }
        
        # Evaluate each rung to see which one is active
        active_rungs = []
        for rung in write_rungs:
            evaluation = self._evaluate_rung_conditions(plc, rung)
            if evaluation['is_active']:
                active_rungs.append({
                    'routine': rung['routine_name'],
                    'rung_number': rung['rung_number'],
                    'comment': rung['rung_comment'],
                    'conditions': evaluation['conditions']
                })
        
        return {
            'tag_name': tag_name,
            'current_value': current_value,
            'controlled_by_rungs': len(write_rungs),
            'active_rungs': active_rungs,
            'all_controlling_rungs': write_rungs
        }
    
    def _evaluate_rung_conditions(self, plc: Dict, rung: Dict) -> Dict:
        """
        Evaluate if a rung's conditions are currently true
        
        Args:
            plc: PLC info dict
            rung: Rung dict with tags_read
            
        Returns:
            Dict with evaluation results
        """
        tags_to_check = rung.get('tags_read', [])
        conditions = []
        all_true = True
        
        for tag_name in tags_to_check:
            # Read tag value
            result = self.plc_comm.read_tag(
                plc['ip_address'],
                tag_name,
                plc['slot'],
                plc['plc_type']
            )
            
            if result.success:
                value = result.value
                # For boolean logic, check if true
                is_true = self._evaluate_tag_value(value)
                conditions.append({
                    'tag': tag_name,
                    'value': value,
                    'state': 'TRUE' if is_true else 'FALSE'
                })
                if not is_true:
                    all_true = False
            else:
                conditions.append({
                    'tag': tag_name,
                    'value': 'ERROR',
                    'state': 'UNKNOWN'
                })
                all_true = False
        
        return {
            'is_active': all_true,
            'conditions': conditions
        }
    
    def _evaluate_tag_value(self, value) -> bool:
        """Evaluate if a tag value is 'true' for logic purposes"""
        if isinstance(value, bool):
            return value
        elif isinstance(value, (int, float)):
            return value != 0
        elif isinstance(value, str):
            return value.lower() in ['true', '1', 'on']
        return False
    
    def generate_control_narrative(self, plc_id: int, tag_name: str) -> str:
        """
        Generate human-readable narrative explaining tag status
        
        Args:
            plc_id: PLC ID
            tag_name: Tag to explain
            
        Returns:
            Narrative string
        """
        trace = self.trace_tag_status(plc_id, tag_name)
        
        if 'error' in trace:
            return f"Unable to trace {tag_name}: {trace['error']}"
        
        current_value = trace['current_value']
        active_rungs = trace.get('active_rungs', [])
        
        if not active_rungs:
            return f"{tag_name} is currently {current_value}. No active control logic found."
        
        # Build narrative
        narrative = f"{tag_name} is currently {current_value} because:\n\n"
        
        for i, rung in enumerate(active_rungs, 1):
            narrative += f"{i}. Routine '{rung['routine']}', Rung {rung['rung_number']}"
            if rung['comment']:
                narrative += f" ({rung['comment']})"
            narrative += " is active.\n"
            
            narrative += "   Conditions:\n"
            for cond in rung['conditions']:
                narrative += f"   • {cond['tag']} = {cond['value']} ({cond['state']})\n"
            narrative += "\n"
        
        return narrative.strip()
    
    def find_controlling_logic(self, plc_id: int, tag_name: str) -> List[Dict]:
        """
        Find all logic that controls a tag
        
        Args:
            plc_id: PLC ID
            tag_name: Tag name
            
        Returns:
            List of rungs that control this tag
        """
        version_id = self.plc_versions.get(plc_id)
        if not version_id:
            versions = self.program_manager.get_program_versions(plc_id)
            if versions:
                version_id = versions[0]['version_id']
            else:
                return []
        
        affecting_rungs = self.program_manager.find_rungs_affecting_tag(version_id, tag_name)
        return [r for r in affecting_rungs if r['affects_type'] == 'write']
    
    def analyze_routine(self, plc_id: int, routine_name: str) -> Dict:
        """
        Analyze a routine and explain what it does
        
        Args:
            plc_id: PLC ID
            routine_name: Routine name
            
        Returns:
            Dict with routine analysis
        """
        version_id = self.plc_versions.get(plc_id)
        if not version_id:
            versions = self.program_manager.get_program_versions(plc_id)
            if versions:
                version_id = versions[0]['version_id']
            else:
                return {'error': 'No program uploaded'}
        
        # Find routine
        routines = self.program_manager.get_routines(version_id)
        routine = None
        for r in routines:
            if r['routine_name'] == routine_name:
                routine = r
                break
        
        if not routine:
            return {'error': f'Routine {routine_name} not found'}
        
        # Get rungs
        rungs = self.program_manager.get_rungs(routine['routine_id'])
        
        # Analyze what tags are controlled
        tags_written = set()
        tags_read = set()
        for rung in rungs:
            tags_written.update(rung['tags_written'])
            tags_read.update(rung['tags_read'])
        
        return {
            'routine_name': routine_name,
            'routine_type': routine['routine_type'],
            'description': routine.get('description', ''),
            'rung_count': len(rungs),
            'controls_tags': list(tags_written),
            'reads_tags': list(tags_read),
            'rungs': rungs
        }
    
    def get_tag_dependencies(self, plc_id: int, tag_name: str) -> Dict:
        """
        Get all tags that this tag depends on (reads) and affects (writes)
        
        Args:
            plc_id: PLC ID
            tag_name: Tag name
            
        Returns:
            Dict with dependencies and dependents
        """
        version_id = self.plc_versions.get(plc_id)
        if not version_id:
            versions = self.program_manager.get_program_versions(plc_id)
            if versions:
                version_id = versions[0]['version_id']
            else:
                return {'error': 'No program uploaded'}
        
        # Find rungs that write to this tag
        write_rungs = self.program_manager.find_rungs_affecting_tag(version_id, tag_name)
        write_rungs = [r for r in write_rungs if r['affects_type'] == 'write']
        
        # Find rungs that read this tag
        read_rungs = self.program_manager.find_rungs_affecting_tag(version_id, tag_name)
        read_rungs = [r for r in read_rungs if r['affects_type'] == 'read']
        
        # Get all tags this tag depends on (tags read in rungs that write to this tag)
        depends_on = set()
        for rung in write_rungs:
            depends_on.update(rung['tags_read'])
        
        # Get all tags that depend on this tag (tags written in rungs that read this tag)
        affects_tags = set()
        for rung in read_rungs:
            affects_tags.update(rung['tags_written'])
        
        return {
            'tag_name': tag_name,
            'depends_on': list(depends_on),
            'affects': list(affects_tags),
            'controlled_by_rungs': len(write_rungs),
            'used_by_rungs': len(read_rungs)
        }
    
    def explain_tag_change(self, plc_id: int, tag_name: str, old_value, new_value) -> str:
        """
        Explain why a tag changed from old_value to new_value
        
        Args:
            plc_id: PLC ID
            tag_name: Tag name
            old_value: Previous value
            new_value: Current value
            
        Returns:
            Explanation string
        """
        trace = self.trace_tag_status(plc_id, tag_name)
        
        if 'error' in trace:
            return f"Unable to explain change: {trace['error']}"
        
        active_rungs = trace.get('active_rungs', [])
        
        if not active_rungs:
            return f"{tag_name} changed from {old_value} to {new_value}, but no active control logic found. May be set externally or by operator."
        
        explanation = f"{tag_name} changed from {old_value} to {new_value} because:\n\n"
        
        for rung in active_rungs:
            explanation += f"Routine '{rung['routine']}', Rung {rung['rung_number']}"
            if rung['comment']:
                explanation += f" ({rung['comment']})"
            explanation += " executed with all conditions true:\n"
            
            for cond in rung['conditions']:
                explanation += f"  • {cond['tag']} = {cond['value']}\n"
            explanation += "\n"
        
        return explanation.strip()
    
    def suggest_optimizations_for_routine(self, plc_id: int, routine_name: str) -> List[Dict]:
        """
        Analyze routine and suggest potential optimizations
        
        Args:
            plc_id: PLC ID
            routine_name: Routine name
            
        Returns:
            List of optimization suggestions
        """
        analysis = self.analyze_routine(plc_id, routine_name)
        
        if 'error' in analysis:
            return []
        
        suggestions = []
        rungs = analysis['rungs']
        
        # Check for repeated tag reads (could use temp variable)
        tag_read_counts = {}
        for rung in rungs:
            for tag in rung['tags_read']:
                tag_read_counts[tag] = tag_read_counts.get(tag, 0) + 1
        
        for tag, count in tag_read_counts.items():
            if count > 5:
                suggestions.append({
                    'type': 'efficiency',
                    'description': f"Tag '{tag}' is read {count} times in this routine. Consider using a temporary variable to reduce PLC scan time.",
                    'severity': 'low',
                    'potential_improvement': f"Reduce scan time by ~{count - 1} tag read operations"
                })
        
        # Check for complex rungs (many conditions)
        for rung in rungs:
            if len(rung['tags_read']) > 10:
                suggestions.append({
                    'type': 'readability',
                    'description': f"Rung {rung['rung_number']} has {len(rung['tags_read'])} conditions. Consider breaking into multiple rungs for better clarity.",
                    'severity': 'low',
                    'potential_improvement': 'Improve code maintainability'
                })
        
        # Check for missing comments
        uncommented_rungs = [r['rung_number'] for r in rungs if not r['rung_comment']]
        if len(uncommented_rungs) > len(rungs) * 0.5:
            suggestions.append({
                'type': 'documentation',
                'description': f"{len(uncommented_rungs)} of {len(rungs)} rungs lack comments. Adding comments improves maintainability.",
                'severity': 'medium',
                'potential_improvement': 'Better documentation for future troubleshooting'
            })
        
        return suggestions
    
    def monitor_tag_continuously(self, plc_id: int, tag_name: str, callback):
        """
        Monitor a tag continuously and call callback when it changes
        
        Args:
            plc_id: PLC ID
            tag_name: Tag to monitor
            callback: Function to call with (tag_name, old_value, new_value, explanation)
        """
        # This would run in a separate thread in production
        # For now, just returns the monitoring setup
        
        plc = self.chore_db.get_plc_by_id(plc_id)
        if not plc:
            return
        
        logger.info(f"Starting continuous monitoring of {tag_name} on PLC {plc_id}")
        
        # In production, this would:
        # 1. Read tag value periodically
        # 2. Compare to last value
        # 3. If changed, generate explanation and call callback
        # 4. Run in background thread


def initialize_logic_analyzer(chore_db, plc_comm, program_manager):
    """
    Initialize and return LogicAnalyzer instance
    
    Args:
        chore_db: ChoreDatabase instance
        plc_comm: PLCCommunicator instance
        program_manager: ProgramManager instance
        
    Returns:
        LogicAnalyzer instance
    """
    return LogicAnalyzer(chore_db, plc_comm, program_manager)
