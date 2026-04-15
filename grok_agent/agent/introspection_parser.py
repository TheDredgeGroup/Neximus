"""
Introspection Parser Module
Detects and handles self-inspection commands for the agent
"""

import logging
import re
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class IntrospectionParser:
    """
    Parses user messages to detect introspection commands
    """
    
    def __init__(self, agent):
        """
        Initialize introspection parser
        
        Args:
            agent: GrokAgent instance with introspection capability
        """
        self.agent = agent
        
        # Command patterns for introspection
        self.patterns = {
            'list_modules': [
                r'list.*your.*modules?',
                r'show.*your.*modules?',
                r'what.*modules.*do.*you.*have',
                r'list.*your.*files?',
                r'show.*your.*code.*files?',
                r'give.*me.*all.*your.*files',
                r'give.*me.*your.*files',
                r'show.*all.*your.*files',
                r'what.*files.*do.*you.*have',
                r'show.*me.*(?:a\s+)?list.*(?:of\s+)?(?:all\s+)?(?:the\s+)?files',
                r'list.*(?:all\s+)?(?:the\s+)?files.*in.*(?:your|the).*(?:agent\s+)?folder',
                r'show.*(?:all\s+)?(?:the\s+)?files.*in.*(?:your|the).*(?:agent\s+)?folder',
                r'what.*files.*(?:are\s+)?in.*(?:your|the).*folder',
            ],
            'open_folder': [
                r'open.*your.*folder',
                r'show.*me.*where.*you.*live',
                r'where.*are.*you.*located',
                r'open.*your.*code.*folder',
                r'show.*your.*location',
                r'where.*is.*your.*code',
            ],
            'open_in_editor': [
                r'open\s+(?:your\s+|my\s+|the\s+)?([\w\s_-]+?)\.(?:py|pie|p\s*y|5)',
                r'show\s+me\s+(?:your\s+|my\s+|the\s+)?([\w\s_-]+?)\.(?:py|pie|p\s*y|5)',
                r'edit\s+(?:your\s+|my\s+|the\s+)?([\w\s_-]+?)\.(?:py|pie|p\s*y|5)',
                r'open\s+([\w\s_-]+?)\s+(?:dot\s+)?(?:py|pie|p\s*y)\s*(?:file|holder)?',
                r'show\s+me\s+([\w\s_-]+?)\s+(?:dot\s+)?(?:py|pie|p\s*y)\s*(?:file|holder)?',
                r'open\s+([\w\s_-]+?)\s+in\s+(?:an?\s+)?editor',
                r'open\s+([\w\s_-]+?)\s+in\s+notepad',
            ],
            'read_file': [
                r'read.*your.*?([\w_]+?)(?:\.py|\.pie)?(?:\s+file)?$',
                r'what.*is.*in.*your.*?([\w_]+?)(?:\.py|\.pie)?(?:\s+file)?$',
                r'show.*contents.*of.*?([\w_]+?)(?:\.py)?(?:\s+file)?$',
                r'display.*?([\w_]+?)(?:\.py)(?:\s+file)?$',
            ],
            'module_info': [
                r'structure.*of.*?([\w_]+?)(?:\.py)?(?:\s+module)?$',
                r'what.*functions.*in.*?([\w_]+?)(?:\.py)?(?:\s+module)?$',
                r'what.*does.*your.*?([\w_]+?)(?:\.py)?\s+(?:module\s+)?do',
                r'explain.*your.*?([\w_]+?)(?:\.py)?\s+module',
                r'describe.*your.*?([\w_]+?)(?:\.py)?\s+module',
                r'tell.*me.*about.*your.*?([\w_]+?)(?:\.py)?\s+module',
            ],
            'find_function': [
                r'find.*function.*?([\w_]+)$',
                r'where.*is.*function.*?([\w_]+)$',
                r'show.*me.*function.*?([\w_]+)$',
            ],
            'find_class': [
                r'find.*class.*?([\w_]+)$',
                r'where.*is.*class.*?([\w_]+)$',
                r'show.*me.*class.*?([\w_]+)$',
            ],
            'search_code': [
                r'search.*your.*code.*for.*?([\w_]+)$',
                r'find.*?([\w_]+).*in.*your.*code',
                r'where.*do.*you.*use.*?([\w_]+)$',
            ],
            'system_overview': [
                r'system.*overview',
                r'what.*is.*your.*structure',
                r'how.*are.*you.*built',
                r'show.*me.*your.*architecture',
                r'what.*are.*you.*made.*of',
            ],
        }
        
        logger.info("Introspection parser initialized")
    
    def _find_module_in_message(self, message: str) -> Optional[str]:
        """
        Compare words in message against actual module names on disk.
        Much more reliable than regex extraction.
        Returns the matching module name (without .py) or None.
        """
        try:
            modules = self.agent.list_my_modules()
            if not modules:
                return None

            module_names = [m['name'].lower() for m in modules]
            words = message.lower().replace('.py', '').replace('.pie', '').split()

            # Direct word match
            for word in words:
                if word in module_names:
                    return word

            # Multi-word match — try joining consecutive words
            # e.g. "action executor" -> "action_executor"
            for i in range(len(words) - 1):
                joined = f"{words[i]}_{words[i+1]}"
                if joined in module_names:
                    return joined

            # Partial match — word is contained in a module name
            for word in words:
                if len(word) > 4:
                    for name in module_names:
                        if word in name:
                            return name

        except Exception as e:
            logger.warning(f"_find_module_in_message failed: {e}")

        return None

    def is_introspection_command(self, message: str) -> bool:
        """
        Check if message is an introspection command
        
        Args:
            message: User message
        
        Returns:
            True if introspection command detected
        """
        message_lower = message.lower()
        
        # Check all patterns
        for command_type, patterns in self.patterns.items():
            for pattern in patterns:
                if re.search(pattern, message_lower):
                    return True
        
        return False
    
    def parse_and_execute(self, message: str) -> Tuple[bool, Optional[str]]:
        """
        Parse and execute introspection command
        
        Args:
            message: User message
        
        Returns:
            Tuple of (was_introspection_command, response_text)
        """
        if not self.agent.introspection:
            return False, None
        
        message_lower = message.lower()
        
        # List modules
        for pattern in self.patterns['list_modules']:
            if re.search(pattern, message_lower):
                modules = self.agent.list_my_modules()
                
                # Check if user wants to filter by prefix (e.g., "files that start with pre")
                prefix_match = re.search(r'(?:start|begin)(?:s|ing)?\s+with\s+(?:the\s+word\s+)?["\']?([a-zA-Z0-9_-]+)', message_lower)
                if prefix_match:
                    prefix = prefix_match.group(1).lower()
                    # Remove trailing hyphen if present (e.g., "pre-" becomes "pre")
                    prefix = prefix.rstrip('-')
                    modules = [m for m in modules if m['name'].lower().startswith(prefix)]
                    response = f"Here are my modules that start with '{prefix}':\n\n"
                else:
                    response = "Here are my modules:\n\n"
                
                if modules:
                    for mod in modules:
                        response += f"• {mod['name']}.py ({mod['size_kb']} KB)\n"
                else:
                    response += "(No matching files found)"
                
                logger.info("Listed agent modules")
                return True, response
        
        # Open folder
        for pattern in self.patterns['open_folder']:
            if re.search(pattern, message_lower):
                result = self.agent.open_my_folder()
                
                if result.get('success'):
                    response = f"I've opened my code folder in File Explorer. I'm located at:\n{result['path']}"
                else:
                    response = f"I couldn't open my folder: {result.get('error')}"
                
                logger.info("Opened agent folder")
                return True, response
        
        # Open file in editor (NEW - opens file in Notepad/editor)
        for pattern in self.patterns['open_in_editor']:
            match = re.search(pattern, message_lower)
            if match:
                filename = self._find_module_in_message(message_lower) or match.group(1)
                
                # Use introspection's open_file_in_editor method
                if self.agent.introspection:
                    result = self.agent.introspection.open_file_in_editor(filename, editor="notepad")
                    
                    if result.get('success'):
                        response = f"Opened {result['filename']} in {result['editor']}."
                    else:
                        response = f"I couldn't open {filename}.py: {result.get('error')}"
                else:
                    response = "Introspection not available."
                
                logger.info(f"Opened file in editor: {filename}")
                return True, response
        
        # Read file
        for pattern in self.patterns['read_file']:
            match = re.search(pattern, message_lower)
            if match:
                filename = self._find_module_in_message(message_lower) or match.group(1)
                file_data = self.agent.read_my_code(filename)
                
                if file_data:
                    response = f"File: {file_data['filename']}\n"
                    response += f"Lines: {file_data['line_count']}\n"
                    response += f"Size: {file_data['size_kb']} KB\n\n"
                    response += "Here's the beginning:\n\n"
                    response += "\n".join(file_data['content'].split('\n')[:30])
                    response += f"\n\n... (showing first 30 lines of {file_data['line_count']})"
                else:
                    response = f"I couldn't find {filename}.py in my code."
                
                logger.info(f"Read file: {filename}")
                return True, response
        
        # Module info — read actual code and send to Grok for intelligent analysis
        for pattern in self.patterns['module_info']:
            match = re.search(pattern, message_lower)
            if match:
                module_name = self._find_module_in_message(message_lower) or match.group(1)
                file_data = self.agent.introspection.read_source_file(module_name)

                if file_data:
                    # Call Grok directly — bypass chat() to avoid saving augmented message to DB
                    code_context = (
                        f"The following is the complete source code of {file_data['filename']} "
                        f"({file_data['line_count']} lines, {file_data['size_kb']} KB):\n\n"
                        f"{file_data['content'][:6000]}"
                    )
                    if len(file_data['content']) > 6000:
                        code_context += f"\n\n... (truncated, showing first 6000 chars of {file_data['line_count']} lines)"

                    try:
                        grok_response = self.agent.grok.chat_with_context(
                            user_message=(
                                f"{message}\n\n"
                                f"[Here is the actual source code of {file_data['filename']} "
                                f"to use for your answer:]\n\n{code_context}"
                            ),
                            conversation_history=[],
                            system_prompt=self.agent.base_system_prompt
                        )
                        response = grok_response["choices"][0]["message"]["content"]
                    except Exception as ge:
                        logger.error(f"Grok call failed in introspection: {ge}")
                        response = f"I read {file_data['filename']} but couldn't get a response from Grok: {ge}"
                else:
                    response = f"I couldn't find {module_name}.py in my code folder."

                logger.info(f"Sent module to Grok for analysis: {module_name}")
                return True, response
        
        # Find function
        for pattern in self.patterns['find_function']:
            match = re.search(pattern, message_lower)
            if match:
                func_name = match.group(1)
                results = self.agent.find_my_function(func_name)
                
                if results:
                    response = f"Found function '{func_name}' in {len(results)} location(s):\n\n"
                    for res in results[:5]:  # Limit to 5
                        response += f"• {res['module']}.py (line {res['line_number']})\n"
                        response += f"  {res['definition']}\n\n"
                else:
                    response = f"I couldn't find function '{func_name}' in my code."
                
                logger.info(f"Found function: {func_name}")
                return True, response
        
        # Find class
        for pattern in self.patterns['find_class']:
            match = re.search(pattern, message_lower)
            if match:
                class_name = match.group(1)
                results = self.agent.find_my_class(class_name)
                
                if results:
                    response = f"Found class '{class_name}' in {len(results)} location(s):\n\n"
                    for res in results:
                        response += f"• {res['module']}.py (line {res['line_number']})\n"
                        response += f"  {res['definition']}\n"
                        if res['docstring']:
                            response += f"  {res['docstring']}\n"
                        response += "\n"
                else:
                    response = f"I couldn't find class '{class_name}' in my code."
                
                logger.info(f"Found class: {class_name}")
                return True, response
        
        # Search code
        for pattern in self.patterns['search_code']:
            match = re.search(pattern, message_lower)
            if match:
                keyword = match.group(1)
                results = self.agent.search_my_code(keyword)
                
                if results:
                    response = f"Found '{keyword}' in {len(results)} place(s):\n\n"
                    for res in results[:10]:  # Limit to 10
                        response += f"• {res['module']}.py (line {res['line_number']})\n"
                        response += f"  {res['line']}\n\n"
                else:
                    response = f"I couldn't find '{keyword}' in my code."
                
                logger.info(f"Searched code for: {keyword}")
                return True, response
        
        # System overview
        for pattern in self.patterns['system_overview']:
            if re.search(pattern, message_lower):
                overview = self.agent.get_my_system_overview()
                
                response = "System Overview:\n\n"
                response += f"Total Modules: {overview['total_modules']}\n"
                response += f"Total Lines: {overview['total_lines']:,}\n"
                response += f"Total Size: {overview['total_size_kb']:.2f} KB\n"
                response += f"Total Classes: {overview['total_classes']}\n"
                response += f"Total Functions: {overview['total_functions']}\n\n"
                
                response += "Modules:\n"
                for mod in overview['modules']:
                    response += f"  • {mod}\n"
                
                logger.info("Got system overview")
                return True, response
        
        return False, None
    
    def process_message(self, message: str, agent) -> Tuple[bool, Optional[str]]:
        """
        Main entry point - check if introspection command and execute
        
        Args:
            message: User message
            agent: Agent instance (for compatibility with other parsers)
        
        Returns:
            Tuple of (was_introspection_command, response_text)
        """
        return self.parse_and_execute(message)


def initialize_introspection_parser(agent):
    """
    Initialize and return introspection parser
    
    Args:
        agent: GrokAgent instance
    
    Returns:
        IntrospectionParser instance
    """
    try:
        parser = IntrospectionParser(agent)
        logger.info("Introspection parser initialized")
        return parser
    except Exception as e:
        logger.error(f"Failed to initialize introspection parser: {e}")
        raise