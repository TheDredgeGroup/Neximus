"""
Introspection Module
Allows the agent to read and analyze its own source code and structure
Read-only access for now, with future self-modification capabilities
"""

import os
import re
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class Introspection:
    """
    Provides the agent with self-awareness of its own code structure
    """
    
    def __init__(self, agent_root_path: str):
        """
        Initialize introspection module
        
        Args:
            agent_root_path: Path to the root agent directory (e.g., 'C:/grok_agent/agent')
        """
        self.root_path = Path(agent_root_path)
        self.architecture_doc = None  # Will store the flow chart if available
        
        # Verify path exists
        if not self.root_path.exists():
            raise FileNotFoundError(f"Agent root path not found: {agent_root_path}")
        
        logger.info(f"Introspection initialized at: {self.root_path}")
    
    def list_modules(self) -> List[Dict[str, Any]]:
        """
        List all Python modules in the agent directory
        
        Returns:
            List of dicts with module info: {'name': str, 'path': str, 'size_kb': float}
        """
        modules = []
        
        try:
            for py_file in self.root_path.glob("*.py"):
                if py_file.name.startswith("__"):
                    continue  # Skip __init__.py and __pycache__
                
                size_bytes = py_file.stat().st_size
                size_kb = round(size_bytes / 1024, 2)
                
                modules.append({
                    'name': py_file.stem,
                    'filename': py_file.name,
                    'path': str(py_file),
                    'size_kb': size_kb
                })
            
            modules.sort(key=lambda x: x['name'])
            logger.info(f"Found {len(modules)} modules")
            return modules
            
        except Exception as e:
            logger.error(f"Error listing modules: {e}")
            return []
    
    def read_source_file(self, filename: str) -> Optional[Dict[str, Any]]:
        """
        Read the contents of a source file
        
        Args:
            filename: Name of the file (e.g., 'core.py' or just 'core')
        
        Returns:
            Dict with file info and contents, or None if not found
        """
        try:
            # Handle both 'core' and 'core.py'
            if not filename.endswith('.py'):
                filename = f"{filename}.py"
            
            file_path = self.root_path / filename
            
            if not file_path.exists():
                logger.warning(f"File not found: {filename}")
                return None
            
            # Read file contents
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Get basic stats
            lines = content.split('\n')
            line_count = len(lines)
            size_kb = round(file_path.stat().st_size / 1024, 2)
            
            return {
                'filename': filename,
                'path': str(file_path),
                'content': content,
                'line_count': line_count,
                'size_kb': size_kb
            }
            
        except Exception as e:
            logger.error(f"Error reading file {filename}: {e}")
            return None
    
    def get_module_info(self, filename: str) -> Optional[Dict[str, Any]]:
        """
        Extract structural information from a module (imports, classes, functions)
        
        Args:
            filename: Name of the file
        
        Returns:
            Dict with module structure info
        """
        file_data = self.read_source_file(filename)
        if not file_data:
            return None
        
        content = file_data['content']
        
        # Extract imports
        import_pattern = r'^(?:from\s+[\w.]+\s+)?import\s+.+$'
        imports = re.findall(import_pattern, content, re.MULTILINE)
        
        # Extract class definitions
        class_pattern = r'^class\s+(\w+).*?:.*?(?:"""(.*?)"""|\'\'\'(.*?)\'\'\')?'
        classes = []
        for match in re.finditer(class_pattern, content, re.MULTILINE | re.DOTALL):
            class_name = match.group(1)
            docstring = match.group(2) or match.group(3) or ""
            # Get first line of docstring only
            docstring = docstring.strip().split('\n')[0] if docstring else ""
            classes.append({'name': class_name, 'docstring': docstring})
        
        # Extract function/method definitions
        func_pattern = r'^(?:    )?def\s+(\w+)\(([^)]*)\).*?:.*?(?:"""(.*?)"""|\'\'\'(.*?)\'\'\')?'
        functions = []
        for match in re.finditer(func_pattern, content, re.MULTILINE | re.DOTALL):
            func_name = match.group(1)
            params = match.group(2)
            docstring = match.group(3) or match.group(4) or ""
            # Get first line of docstring only
            docstring = docstring.strip().split('\n')[0] if docstring else ""
            
            # Skip private methods for cleaner output
            if not func_name.startswith('_'):
                functions.append({
                    'name': func_name,
                    'params': params,
                    'docstring': docstring
                })
        
        return {
            'filename': file_data['filename'],
            'path': file_data['path'],
            'line_count': file_data['line_count'],
            'size_kb': file_data['size_kb'],
            'imports': imports[:10],  # Limit to first 10
            'classes': classes,
            'functions': functions
        }
    
    def find_function(self, function_name: str) -> List[Dict[str, Any]]:
        """
        Search for a function across all modules
        
        Args:
            function_name: Name of function to find
        
        Returns:
            List of dicts with location info
        """
        results = []
        modules = self.list_modules()
        
        for module in modules:
            file_data = self.read_source_file(module['filename'])
            if not file_data:
                continue
            
            content = file_data['content']
            lines = content.split('\n')
            
            # Search for function definition
            pattern = rf'^(?:    )?def\s+{function_name}\('
            for i, line in enumerate(lines, 1):
                if re.match(pattern, line):
                    # Get a few lines of context
                    context_start = max(0, i-2)
                    context_end = min(len(lines), i+3)
                    context = '\n'.join(lines[context_start:context_end])
                    
                    results.append({
                        'module': module['name'],
                        'filename': module['filename'],
                        'line_number': i,
                        'definition': line.strip(),
                        'context': context
                    })
        
        logger.info(f"Found {len(results)} occurrences of function '{function_name}'")
        return results
    
    def find_class(self, class_name: str) -> List[Dict[str, Any]]:
        """
        Search for a class across all modules
        
        Args:
            class_name: Name of class to find
        
        Returns:
            List of dicts with location info
        """
        results = []
        modules = self.list_modules()
        
        for module in modules:
            file_data = self.read_source_file(module['filename'])
            if not file_data:
                continue
            
            content = file_data['content']
            lines = content.split('\n')
            
            # Search for class definition
            pattern = rf'^class\s+{class_name}[\(:]'
            for i, line in enumerate(lines, 1):
                if re.match(pattern, line):
                    # Get docstring if available
                    docstring = ""
                    if i < len(lines) and '"""' in lines[i]:
                        for j in range(i, min(i+10, len(lines))):
                            if lines[j].strip().endswith('"""'):
                                docstring = lines[j].strip().strip('"""')
                                break
                    
                    results.append({
                        'module': module['name'],
                        'filename': module['filename'],
                        'line_number': i,
                        'definition': line.strip(),
                        'docstring': docstring
                    })
        
        logger.info(f"Found {len(results)} occurrences of class '{class_name}'")
        return results
    
    def search_code(self, keyword: str, case_sensitive: bool = False) -> List[Dict[str, Any]]:
        """
        Search for a keyword across all modules
        
        Args:
            keyword: Keyword to search for
            case_sensitive: Whether search should be case-sensitive
        
        Returns:
            List of matches with context
        """
        results = []
        modules = self.list_modules()
        
        for module in modules:
            file_data = self.read_source_file(module['filename'])
            if not file_data:
                continue
            
            content = file_data['content']
            lines = content.split('\n')
            
            # Search each line
            for i, line in enumerate(lines, 1):
                search_line = line if case_sensitive else line.lower()
                search_keyword = keyword if case_sensitive else keyword.lower()
                
                if search_keyword in search_line:
                    results.append({
                        'module': module['name'],
                        'filename': module['filename'],
                        'line_number': i,
                        'line': line.strip(),
                        'match_count': search_line.count(search_keyword)
                    })
        
        logger.info(f"Found {len(results)} occurrences of keyword '{keyword}'")
        return results[:50]  # Limit to 50 results
    
    def get_architecture_summary(self, architecture_file_path: Optional[str] = None) -> Optional[str]:
        """
        Read the architecture documentation/flow chart
        
        Args:
            architecture_file_path: Optional path to architecture doc
        
        Returns:
            Architecture documentation content
        """
        if architecture_file_path:
            try:
                with open(architecture_file_path, 'r', encoding='utf-8') as f:
                    self.architecture_doc = f.read()
                logger.info("Architecture documentation loaded")
                return self.architecture_doc
            except Exception as e:
                logger.error(f"Error reading architecture doc: {e}")
                return None
        
        return self.architecture_doc
    
    def get_file_dependencies(self, filename: str) -> Dict[str, Any]:
        """
        Analyze what other modules a file imports
        
        Args:
            filename: Name of file to analyze
        
        Returns:
            Dict with dependency info
        """
        file_data = self.read_source_file(filename)
        if not file_data:
            return {'error': 'File not found'}
        
        content = file_data['content']
        
        # Find all imports
        internal_imports = []
        external_imports = []
        
        # Pattern: from agent.xxx import yyy
        internal_pattern = r'from\s+agent\.(\w+)\s+import'
        for match in re.finditer(internal_pattern, content):
            module_name = match.group(1)
            if module_name not in internal_imports:
                internal_imports.append(module_name)
        
        # Pattern: import xxx
        external_pattern = r'^import\s+([\w.]+)'
        for match in re.finditer(external_pattern, content, re.MULTILINE):
            lib_name = match.group(1).split('.')[0]
            if lib_name not in external_imports and lib_name != 'agent':
                external_imports.append(lib_name)
        
        return {
            'filename': filename,
            'internal_dependencies': internal_imports,
            'external_dependencies': external_imports,
            'total_dependencies': len(internal_imports) + len(external_imports)
        }
    
    def open_file_in_editor(self, filename: str, editor: str = "notepad") -> Dict[str, Any]:
        """
        Open a source file in a text editor
        
        Args:
            filename: Name of file to open
            editor: Editor command (notepad, code, notepad++, etc.)
        
        Returns:
            Dict with execution result
        """
        try:
            if not filename.endswith('.py'):
                filename = f"{filename}.py"
            
            file_path = self.root_path / filename
            
            # If file not found with spaces, try with underscores (for Siri transcription)
            if not file_path.exists():
                filename_with_underscores = filename.replace(' ', '_')
                file_path_underscore = self.root_path / filename_with_underscores
                if file_path_underscore.exists():
                    file_path = file_path_underscore
                    filename = filename_with_underscores
            
            if not file_path.exists():
                return {'success': False, 'error': f"File not found: {filename}"}
            
            # Use action_executor's Win+R method
            import subprocess
            command = f'{editor} "{file_path}"'
            
            subprocess.Popen(command, shell=True)
            
            logger.info(f"Opened {filename} in {editor}")
            return {
                'success': True,
                'filename': filename,
                'editor': editor,
                'path': str(file_path)
            }
            
        except Exception as e:
            logger.error(f"Error opening file {filename}: {e}")
            return {'success': False, 'error': str(e)}
    
    def open_my_folder(self) -> Dict[str, Any]:
        """
        Open the agent's root directory in File Explorer
        
        Returns:
            Dict with execution result
        """
        try:
            import subprocess
            import platform
            
            system = platform.system()
            
            if system == "Windows":
                # Open in Windows Explorer
                subprocess.Popen(f'explorer "{self.root_path}"', shell=True)
            elif system == "Darwin":  # macOS
                subprocess.Popen(['open', str(self.root_path)])
            else:  # Linux
                subprocess.Popen(['xdg-open', str(self.root_path)])
            
            logger.info(f"Opened agent folder: {self.root_path}")
            return {
                'success': True,
                'path': str(self.root_path),
                'action': 'opened_folder'
            }
            
        except Exception as e:
            logger.error(f"Error opening folder: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_system_overview(self) -> Dict[str, Any]:
        """
        Get a complete overview of the agent's code structure
        
        Returns:
            Dict with system overview
        """
        modules = self.list_modules()
        
        total_lines = 0
        total_size_kb = 0
        all_classes = []
        all_functions = []
        
        for module in modules:
            info = self.get_module_info(module['filename'])
            if info:
                total_lines += info['line_count']
                total_size_kb += info['size_kb']
                
                for cls in info['classes']:
                    all_classes.append(f"{module['name']}.{cls['name']}")
                
                for func in info['functions']:
                    all_functions.append(f"{module['name']}.{func['name']}")
        
        return {
            'total_modules': len(modules),
            'total_lines': total_lines,
            'total_size_kb': round(total_size_kb, 2),
            'total_classes': len(all_classes),
            'total_functions': len(all_functions),
            'modules': [m['name'] for m in modules],
            'classes': all_classes[:20],  # First 20
            'functions': all_functions[:20]  # First 20
        }


def initialize_introspection(agent_root_path: str) -> Introspection:
    """
    Initialize and return introspection module
    
    Args:
        agent_root_path: Path to agent directory
    
    Returns:
        Introspection instance
    """
    try:
        introspection = Introspection(agent_root_path)
        logger.info("Introspection module initialized")
        return introspection
    except Exception as e:
        logger.error(f"Failed to initialize introspection: {e}")
        raise