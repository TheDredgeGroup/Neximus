"""
PLC Parser Module - UPDATED
Parses natural language PLC commands using separate keyword columns
Integrates with Grok API for conversational responses
"""

import re
import logging
from typing import Optional, Dict, Tuple, Any, List

logger = logging.getLogger(__name__)


class PLCParser:
    """
    Parses natural language PLC commands using keyword matching.
    Keywords are now stored in separate database columns:
    - read_keywords: For reading tag values
    - write_keywords: For writing tag values (extracts number from message)
    - on_keywords: For turning BOOL tags ON (state=1)
    - off_keywords: For turning BOOL tags OFF (state=0)
    """
    
    def __init__(self, chore_db, plc_comm):
        """
        Initialize PLC parser
        
        Args:
            chore_db: ChoreDatabase instance
            plc_comm: PLCCommunicator instance
        """
        self.chore_db = chore_db
        self.plc_comm = plc_comm
        logger.info("PLCParser initialized with separate keyword columns")
    
    def _keywords_match(self, message: str, keywords: List[str]) -> bool:
        """
        Check if ALL keywords exist in the message (like VB InStr)
        
        Args:
            message: User's message
            keywords: List of keywords to find
            
        Returns:
            True if ALL keywords found in message
        """
        message_lower = message.lower()
        
        for keyword in keywords:
            if keyword not in message_lower:
                return False
        
        return True
    
    def _find_matching_tag(self, message: str) -> Optional[Dict]:
        """
        Find a tag whose keywords match the message
        
        Args:
            message: User's message
            
        Returns:
            Dict with 'plc', 'tag', 'value', 'action' or None
        """
        plcs = self.chore_db.get_all_plcs(enabled_only=True)
        
        if not plcs:
            return None
        
        best_match = None
        best_keyword_count = 0
        message_lower = message.lower()
        
        # Check keyword matches
        for plc in plcs:
            tags = self.chore_db.get_tags_for_plc(plc['id'])
            
            for tag in tags:
                # Get keywords from separate columns
                on_keywords = tag.get('on_keywords') or ''
                off_keywords = tag.get('off_keywords') or ''
                write_keywords = tag.get('write_keywords') or ''
                read_keywords = tag.get('read_keywords') or ''
                
                # Check ON keywords (state=1)
                if on_keywords:
                    keywords = [k.strip().lower() for k in on_keywords.split(',') if k.strip()]
                    if keywords and self._keywords_match(message, keywords):
                        keyword_count = len(keywords)
                        if keyword_count > best_keyword_count:
                            best_keyword_count = keyword_count
                            best_match = {
                                'plc': plc,
                                'tag': tag,
                                'value': True,  # ON
                                'action': 'write',
                                'matched_keywords': keywords
                            }
                
                # Check OFF keywords (state=0)
                if off_keywords:
                    keywords = [k.strip().lower() for k in off_keywords.split(',') if k.strip()]
                    if keywords and self._keywords_match(message, keywords):
                        keyword_count = len(keywords)
                        if keyword_count > best_keyword_count:
                            best_keyword_count = keyword_count
                            best_match = {
                                'plc': plc,
                                'tag': tag,
                                'value': False,  # OFF
                                'action': 'write',
                                'matched_keywords': keywords
                            }
                
                # Check WRITE keywords (extract value from message)
                if write_keywords:
                    keywords = [k.strip().lower() for k in write_keywords.split(',') if k.strip()]
                    if keywords and self._keywords_match(message, keywords):
                        keyword_count = len(keywords)
                        if keyword_count > best_keyword_count:
                            best_keyword_count = keyword_count
                            best_match = {
                                'plc': plc,
                                'tag': tag,
                                'value': None,  # Will extract from message
                                'action': 'write',
                                'matched_keywords': keywords
                            }
                
                # Check READ keywords (multiple alternatives separated by |)
                if read_keywords:
                    # Split by | for alternative phrasings
                    for group in read_keywords.split('|'):
                        keywords = [k.strip().lower() for k in group.split(',') if k.strip()]
                        if keywords and self._keywords_match(message, keywords):
                            keyword_count = len(keywords)
                            if keyword_count > best_keyword_count:
                                best_keyword_count = keyword_count
                                best_match = {
                                    'plc': plc,
                                    'tag': tag,
                                    'value': None,
                                    'action': 'read',
                                    'matched_keywords': keywords
                                }
        
        # If keyword match found, return it
        if best_match:
            return best_match
        
        # Fallback - check if tag name + action word appears in message
        read_words = ['read', 'get', 'check', 'what', 'show', 'tell', 'value']
        write_words = ['write', 'set', 'change', 'update', 'put']
        
        for plc in plcs:
            tags = self.chore_db.get_tags_for_plc(plc['id'])
            
            for tag in tags:
                tag_name = tag['tag_name'].lower()
                
                # Check if tag name appears in message
                if tag_name in message_lower:
                    # Determine action from message
                    action = 'read'  # Default
                    value = None
                    
                    for word in write_words:
                        if word in message_lower:
                            action = 'write'
                            value = self._extract_write_value_from_message(message)
                            break
                    
                    if action == 'read':
                        for word in read_words:
                            if word in message_lower:
                                action = 'read'
                                break
                    
                    logger.info(f"Fallback match: tag={tag['tag_name']}, action={action}")
                    return {
                        'plc': plc,
                        'tag': tag,
                        'value': value,
                        'action': action,
                        'matched_keywords': [tag_name]
                    }
        
        return None
    
    def is_plc_request(self, message: str) -> bool:
        """
        Check if a message matches any configured tag keywords
        
        Args:
            message: User's message
        
        Returns:
            True if message matches any tag keywords
        """
        match = self._find_matching_tag(message)
        return match is not None
    
    def _extract_write_value_from_message(self, message: str) -> Optional[Any]:
        """
        Extract a numeric value from the message (for analog writes)
        
        Args:
            message: User's message
        
        Returns:
            Numeric value or None
        """
        message_lower = message.lower()
        
        # Pattern: "value of X"
        match = re.search(r'\bvalue\s+of\s+(\d+\.?\d*)', message_lower)
        if match:
            value_str = match.group(1)
            if '.' in value_str:
                return float(value_str)
            return int(value_str)
        
        # Pattern: "to X"
        match = re.search(r'\bto\s+(\d+\.?\d*)', message_lower)
        if match:
            value_str = match.group(1)
            if '.' in value_str:
                return float(value_str)
            return int(value_str)
        
        # Pattern: "set X" or "write X"
        match = re.search(r'\b(?:set|write)\s+(\d+\.?\d*)', message_lower)
        if match:
            value_str = match.group(1)
            if '.' in value_str:
                return float(value_str)
            return int(value_str)
        
        return None
    
    def execute_command(self, message: str) -> Tuple[bool, str, Optional[Dict]]:
        """
        Parse and execute a PLC command based on keyword matching
        
        Args:
            message: User's PLC command
        
        Returns:
            Tuple of (success, status_message, result_data)
        """
        match = self._find_matching_tag(message)
        
        if not match:
            return False, "I couldn't match your request to any configured tag keywords.", None
        
        plc = match['plc']
        tag = match['tag']
        action = match['action']
        value = match['value']
        
        logger.info(f"Keyword match: {match['matched_keywords']} -> tag={tag['tag_name']}, action={action}, value={value}")
        
        try:
            if action == 'read':
                # Read the tag
                result = self.plc_comm.read_tag(
                    plc['ip_address'],
                    tag['tag_name'],
                    plc['slot'],
                    plc['plc_type']
                )
                
                if result.success:
                    logger.info(f"PLC READ SUCCESS: {tag['tag_name']} = {result.value} (fresh from PLC)")
                    
                    if tag.get('id'):
                        self.chore_db.update_tag_value(tag['id'], str(result.value))
                    
                    return True, f"Tag '{tag['tag_name']}' on {plc['name']} = {result.value}", {
                        'action': 'read',
                        'tag_name': tag['tag_name'],
                        'plc_name': plc['name'],
                        'value': result.value,
                        'data_type': result.data_type
                    }
                else:
                    return False, f"Failed to read tag '{tag['tag_name']}': {result.error}", None
            
            elif action == 'write':
                # For analog tags without explicit value, try to extract value from message
                if value is None:
                    value = self._extract_write_value_from_message(message)
                
                if value is None:
                    return False, f"I matched tag '{tag['tag_name']}' but couldn't determine what value to write.", None
                
                result = self.plc_comm.write_tag(
                    plc['ip_address'],
                    tag['tag_name'],
                    value,
                    plc['slot'],
                    plc['plc_type']
                )
                
                if result.success:
                    if tag.get('id'):
                        self.chore_db.update_tag_value(tag['id'], str(value))
                    
                    return True, f"Wrote {value} to tag '{tag['tag_name']}' on {plc['name']}", {
                        'action': 'write',
                        'tag_name': tag['tag_name'],
                        'plc_name': plc['name'],
                        'value': value
                    }
                else:
                    return False, f"Failed to write to tag '{tag['tag_name']}': {result.error}", None
            
            else:
                return False, f"Unknown action type: {action}", None
                
        except Exception as e:
            logger.error(f"Error executing PLC command: {e}")
            return False, f"Error communicating with PLC: {e}", None
    
    def process_message(self, message: str, agent=None) -> Tuple[bool, Optional[str]]:
        """
        Process a message - check if it matches keywords and handle accordingly
        
        Args:
            message: User's message
            agent: Optional GrokAgent for getting conversational response
        
        Returns:
            Tuple of (was_plc_command, response)
        """
        if not self.is_plc_request(message):
            return False, None
        
        # It's a PLC request - execute it
        success, status, result_data = self.execute_command(message)
        
        # Build context for Grok API
        if success and agent and result_data:
            action = result_data.get('action', 'unknown')
            tag_name = result_data.get('tag_name', 'unknown')
            plc_name = result_data.get('plc_name', 'unknown')
            value = result_data.get('value', 'unknown')
            
            if action == 'read':
                context = f"""IMPORTANT: I just read FRESH data from the PLC right now. 
The CURRENT value is: {value}

CRITICAL INSTRUCTION: You MUST report this exact value ({value}) to the user. 
DO NOT use any previous values from conversation history. 
The value {value} was just read from the PLC at this moment.

Tag: {tag_name}
PLC: {plc_name}
CURRENT VALUE: {value}

Tell the user this current reading in a brief, natural way."""
            else:
                context = f"""I just executed a PLC command successfully.
- PLC: {plc_name}
- Tag: {tag_name}
- Action: {action}
- New Value: {value}

Confirm this action briefly."""
            
            try:
                logger.info(f"Sending to Grok with value={value} for tag={tag_name}")
                grok_response = agent.chat(f"{message}\n\n[SYSTEM: {context}]")
                return True, grok_response
            except Exception as e:
                logger.error(f"Error getting Grok response: {e}")
                return True, status
        
        elif success:
            return True, status
        
        else:
            # Failed
            if agent:
                try:
                    grok_response = agent.chat(f"{message}\n\n[SYSTEM: The user tried to interact with a PLC but it failed. Error: {status}. Please help them understand the issue.]")
                    return True, grok_response
                except:
                    pass
            return True, status
    
    def get_all_keyword_mappings(self) -> List[Dict]:
        """
        Get all configured keyword mappings for debugging/display
        
        Returns:
            List of all tag keyword configurations
        """
        mappings = []
        
        plcs = self.chore_db.get_all_plcs(enabled_only=True)
        
        for plc in plcs:
            tags = self.chore_db.get_tags_for_plc(plc['id'])
            
            for tag in tags:
                mapping = {
                    'plc_name': plc['name'],
                    'tag_name': tag['tag_name'],
                    'tag_type': tag['tag_type']
                }
                
                # Add keyword info from separate columns
                if tag.get('read_keywords'):
                    mapping['read_keywords'] = tag['read_keywords']
                if tag.get('write_keywords'):
                    mapping['write_keywords'] = tag['write_keywords']
                if tag.get('on_keywords'):
                    mapping['on_keywords'] = tag['on_keywords']
                if tag.get('off_keywords'):
                    mapping['off_keywords'] = tag['off_keywords']
                
                # Only add if has some keywords
                if any(k in mapping for k in ['read_keywords', 'write_keywords', 'on_keywords', 'off_keywords']):
                    mappings.append(mapping)
        
        return mappings


def initialize_plc_parser(chore_db, plc_comm) -> PLCParser:
    """
    Initialize and return a PLCParser instance
    
    Args:
        chore_db: ChoreDatabase instance
        plc_comm: PLCCommunicator instance
    
    Returns:
        PLCParser instance
    """
    return PLCParser(chore_db, plc_comm)
