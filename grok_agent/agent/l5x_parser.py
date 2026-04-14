"""
L5X Program Parser
Parses Allen-Bradley L5X/L5K files to extract program structure, routines, rungs, and tags
"""

import xml.etree.ElementTree as ET
import logging
import re
from typing import Dict, List, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class L5XParser:
    """Parse Allen-Bradley L5X program files"""
    
    def __init__(self):
        self.controller_info = {}
        self.tags = []
        self.programs = []
        self.routines = []
        self.rungs = []
        self.data_types = []
        self.aoi_definitions = []
    
    def parse_file(self, file_path: str) -> Dict:
        """
        Parse L5X file and extract all program information
        
        Args:
            file_path: Path to L5X file
            
        Returns:
            Dict with parsed program data
        """
        logger.info(f"Parsing L5X file: {file_path}")
        
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            
            # Extract controller info
            self._parse_controller(root)
            
            # Extract tags
            self._parse_tags(root)
            
            # Extract programs and routines
            self._parse_programs(root)
            
            # Extract data types
            self._parse_data_types(root)
            
            # Extract Add-On Instructions
            self._parse_aoi(root)
            
            result = {
                'controller': self.controller_info,
                'tags': self.tags,
                'programs': self.programs,
                'routines': self.routines,
                'rungs': self.rungs,
                'data_types': self.data_types,
                'aoi_definitions': self.aoi_definitions,
                'parse_timestamp': datetime.now().isoformat()
            }
            
            logger.info(f"Parsed: {len(self.tags)} tags, {len(self.routines)} routines, {len(self.rungs)} rungs")
            return result
            
        except Exception as e:
            logger.error(f"Error parsing L5X file: {e}")
            raise
    
    def _parse_controller(self, root):
        """Extract controller information"""
        controller = root.find('.//Controller')
        if controller is not None:
            self.controller_info = {
                'name': controller.get('Name', 'Unknown'),
                'processor_type': controller.get('ProcessorType', 'Unknown'),
                'major_revision': controller.get('MajorRev', '0'),
                'minor_revision': controller.get('MinorRev', '0'),
                'time_slice': controller.get('TimeSlice', '20'),
                'use': controller.get('Use', 'Target')
            }
    
    def _parse_tags(self, root):
        """Extract all tags from controller and programs"""
        # Controller-scoped tags
        controller_tags = root.find('.//Controller/Tags')
        if controller_tags is not None:
            for tag in controller_tags.findall('Tag'):
                tag_info = self._extract_tag_info(tag, 'controller')
                if tag_info:
                    self.tags.append(tag_info)
        
        # Program-scoped tags
        programs = root.findall('.//Programs/Program')
        for program in programs:
            program_name = program.get('Name', 'Unknown')
            program_tags = program.find('Tags')
            if program_tags is not None:
                for tag in program_tags.findall('Tag'):
                    tag_info = self._extract_tag_info(tag, 'program', program_name)
                    if tag_info:
                        self.tags.append(tag_info)
    
    def _extract_tag_info(self, tag_element, scope: str, parent: str = None) -> Optional[Dict]:
        """Extract information from a tag element"""
        try:
            tag_name = tag_element.get('Name')
            tag_type = tag_element.get('TagType', 'Base')
            data_type = tag_element.get('DataType', 'UNKNOWN')
            
            # Get description if available
            description = ''
            desc_element = tag_element.find('Description')
            if desc_element is not None and desc_element.text:
                description = desc_element.text.strip()
            
            # Get initial value if available
            data_element = tag_element.find('Data')
            initial_value = None
            if data_element is not None:
                initial_value = self._extract_data_value(data_element, data_type)
            
            # Determine if it's constant
            constant = tag_element.get('Constant', 'false').lower() == 'true'
            
            # Determine if it's external (I/O)
            external = tag_element.get('ExternalAccess', 'Read/Write')
            
            return {
                'tag_name': tag_name,
                'tag_type': tag_type,
                'data_type': data_type,
                'scope': scope,
                'parent': parent,
                'description': description,
                'initial_value': initial_value,
                'constant': constant,
                'external_access': external,
                'is_alias': tag_type == 'Alias',
                'is_consumed': tag_type == 'Consumed',
                'is_produced': tag_type == 'Produced'
            }
        except Exception as e:
            logger.warning(f"Error extracting tag info: {e}")
            return None
    
    def _extract_data_value(self, data_element, data_type: str):
        """Extract value from data element"""
        try:
            # Simple types
            if data_type in ['BOOL', 'SINT', 'INT', 'DINT', 'LINT']:
                return data_element.get('Value')
            elif data_type in ['REAL']:
                return data_element.get('Value')
            elif data_type == 'STRING':
                # String data is in nested structure
                return None  # Complex, handle later if needed
            else:
                # Complex types - return None for now
                return None
        except:
            return None
    
    def _parse_programs(self, root):
        """Extract programs, routines, and rungs"""
        programs = root.findall('.//Programs/Program')
        
        for program in programs:
            program_name = program.get('Name', 'Unknown')
            program_type = program.get('Type', 'Normal')
            
            # Store program info
            program_info = {
                'name': program_name,
                'type': program_type,
                'disabled': program.get('Disabled', 'false').lower() == 'true',
                'routines': []
            }
            
            # Get main routine name
            main_routine_name = program.get('MainRoutineName', '')
            if main_routine_name:
                program_info['main_routine'] = main_routine_name
            
            # Parse routines in this program
            routines = program.findall('.//Routines/Routine')
            for routine in routines:
                routine_info = self._parse_routine(routine, program_name)
                if routine_info:
                    program_info['routines'].append(routine_info['name'])
                    self.routines.append(routine_info)
            
            self.programs.append(program_info)
    
    def _parse_routine(self, routine_element, program_name: str) -> Optional[Dict]:
        """Parse a routine and its rungs"""
        try:
            routine_name = routine_element.get('Name', 'Unknown')
            routine_type = routine_element.get('Type', 'RLL')  # RLL = Ladder Logic
            
            routine_info = {
                'name': routine_name,
                'program': program_name,
                'type': routine_type,
                'rungs': []
            }
            
            # Get description
            desc_element = routine_element.find('Description')
            if desc_element is not None and desc_element.text:
                routine_info['description'] = desc_element.text.strip()
            
            # Parse rungs for ladder logic
            if routine_type == 'RLL':
                rll_content = routine_element.find('RLLContent')
                if rll_content is not None:
                    rungs = rll_content.findall('Rung')
                    for rung_num, rung in enumerate(rungs):
                        rung_info = self._parse_rung(rung, routine_name, rung_num)
                        if rung_info:
                            routine_info['rungs'].append(rung_num)
                            self.rungs.append(rung_info)
            
            # Parse structured text
            elif routine_type == 'ST':
                st_content = routine_element.find('STContent')
                if st_content is not None:
                    routine_info['st_code'] = st_content.text
            
            return routine_info
            
        except Exception as e:
            logger.warning(f"Error parsing routine: {e}")
            return None
    
    def _parse_rung(self, rung_element, routine_name: str, rung_number: int) -> Optional[Dict]:
        """Parse a single rung"""
        try:
            rung_type = rung_element.get('Type', 'N')
            
            # Get rung comment
            comment = ''
            comment_element = rung_element.find('Comment')
            if comment_element is not None and comment_element.text:
                comment = comment_element.text.strip()
            
            # Get rung text (ASCII representation)
            text_element = rung_element.find('Text')
            rung_text = ''
            if text_element is not None and text_element.text:
                rung_text = text_element.text.strip()
            
            # Extract tags referenced in this rung
            tags_read, tags_written = self._extract_rung_tags(rung_text)
            
            return {
                'routine': routine_name,
                'rung_number': rung_number,
                'rung_type': rung_type,
                'comment': comment,
                'rung_text': rung_text,
                'tags_read': tags_read,
                'tags_written': tags_written
            }
            
        except Exception as e:
            logger.warning(f"Error parsing rung: {e}")
            return None
    
    def _extract_rung_tags(self, rung_text: str) -> Tuple[List[str], List[str]]:
        """
        Extract tag names from rung text
        Returns: (tags_read, tags_written)
        """
        tags_read = []
        tags_written = []
        
        if not rung_text:
            return tags_read, tags_written
        
        try:
            # Common ladder logic instructions
            # XIC, XIO - examine (read)
            # OTE, OTL, OTU - output (write)
            # MOV, CPT - move/compute (read source, write dest)
            
            # Pattern for tag names (alphanumeric, underscore, may have array indices or bit references)
            tag_pattern = r'\b([A-Za-z_][A-Za-z0-9_]*(?:\[[^\]]+\])?(?:\.\d+)?)\b'
            
            # Split rung text by instructions
            instructions = rung_text.split(';')
            
            for instruction in instructions:
                instruction = instruction.strip()
                
                # Output instructions (write)
                if instruction.startswith(('OTE(', 'OTL(', 'OTU(')):
                    # Extract tag being written
                    match = re.search(r'\(([^)]+)\)', instruction)
                    if match:
                        tag = match.group(1).strip()
                        if tag and tag not in tags_written:
                            tags_written.append(tag)
                
                # Input instructions (read)
                elif instruction.startswith(('XIC(', 'XIO(')):
                    # Extract tag being read
                    match = re.search(r'\(([^)]+)\)', instruction)
                    if match:
                        tag = match.group(1).strip()
                        if tag and tag not in tags_read:
                            tags_read.append(tag)
                
                # MOV instruction (read source, write dest)
                elif instruction.startswith('MOV('):
                    # MOV(source,dest)
                    match = re.search(r'\(([^,]+),([^)]+)\)', instruction)
                    if match:
                        source = match.group(1).strip()
                        dest = match.group(2).strip()
                        if source and source not in tags_read:
                            tags_read.append(source)
                        if dest and dest not in tags_written:
                            tags_written.append(dest)
                
                # CPT instruction (compute)
                elif instruction.startswith('CPT('):
                    # CPT(dest,expression)
                    match = re.search(r'\(([^,]+),(.+)\)', instruction)
                    if match:
                        dest = match.group(1).strip()
                        expression = match.group(2).strip()
                        
                        if dest and dest not in tags_written:
                            tags_written.append(dest)
                        
                        # Extract all tags from expression
                        expr_tags = re.findall(tag_pattern, expression)
                        for tag in expr_tags:
                            if tag and tag not in tags_read:
                                tags_read.append(tag)
                
                # Timer/Counter instructions
                elif instruction.startswith(('TON(', 'TOF(', 'RTO(', 'CTU(', 'CTD(')):
                    # Extract timer/counter tag
                    match = re.search(r'\(([^,]+)', instruction)
                    if match:
                        tag = match.group(1).strip()
                        if tag and tag not in tags_read:
                            tags_read.append(tag)
                        if tag and tag not in tags_written:
                            tags_written.append(tag)  # Timers/counters are read/write
        
        except Exception as e:
            logger.warning(f"Error extracting tags from rung: {e}")
        
        return tags_read, tags_written
    
    def _parse_data_types(self, root):
        """Extract user-defined data types"""
        data_types = root.findall('.//DataTypes/DataType')
        
        for dt in data_types:
            dt_name = dt.get('Name', 'Unknown')
            dt_family = dt.get('Family', 'NoFamily')
            
            members = []
            member_elements = dt.findall('.//Members/Member')
            for member in member_elements:
                member_info = {
                    'name': member.get('Name', ''),
                    'data_type': member.get('DataType', ''),
                    'dimension': member.get('Dimension', '0'),
                    'radix': member.get('Radix', 'Decimal')
                }
                members.append(member_info)
            
            self.data_types.append({
                'name': dt_name,
                'family': dt_family,
                'members': members
            })
    
    def _parse_aoi(self, root):
        """Extract Add-On Instruction definitions"""
        aoi_defs = root.findall('.//AddOnInstructionDefinitions/AddOnInstructionDefinition')
        
        for aoi in aoi_defs:
            aoi_name = aoi.get('Name', 'Unknown')
            aoi_revision = aoi.get('Revision', '1.0')
            
            # Get parameters
            parameters = []
            param_elements = aoi.findall('.//Parameters/Parameter')
            for param in param_elements:
                param_info = {
                    'name': param.get('Name', ''),
                    'tag_type': param.get('TagType', ''),
                    'data_type': param.get('DataType', ''),
                    'usage': param.get('Usage', 'Input'),
                    'required': param.get('Required', 'false').lower() == 'true'
                }
                parameters.append(param_info)
            
            self.aoi_definitions.append({
                'name': aoi_name,
                'revision': aoi_revision,
                'parameters': parameters
            })


def parse_l5x_file(file_path: str) -> Dict:
    """
    Parse an L5X file and return structured data
    
    Args:
        file_path: Path to L5X file
        
    Returns:
        Dict with parsed program data
    """
    parser = L5XParser()
    return parser.parse_file(file_path)
