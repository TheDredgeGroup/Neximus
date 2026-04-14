"""
Action Executor Module
Handles voice-controlled system actions (opening browsers, files, applications)
Phase 4 - Immediate execution with ctypes user32.dll SendInput
Phase 5 - Advanced browser automation with Browser-use
"""

import logging
import webbrowser
import ctypes
import time
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Try to import browser controller for Phase 5
try:
    from agent.browser_controller import BrowserController
    BROWSER_CONTROLLER_AVAILABLE = True
except ImportError:
    BROWSER_CONTROLLER_AVAILABLE = False
    logger.info("BrowserController not available (Phase 5 not installed)")

# Windows API constants
VK_LWIN = 0x5B  # Left Windows key
VK_R = 0x52     # R key
VK_RETURN = 0x0D  # Enter key
VK_CONTROL = 0x11  # Ctrl key
VK_L = 0x4C     # L key

# Input types
INPUT_KEYBOARD = 1

# Key event flags
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004

# Windows API structures
class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))
    ]

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))
    ]

class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", ctypes.c_ulong),
        ("wParamL", ctypes.c_ushort),
        ("wParamH", ctypes.c_ushort)
    ]

class _INPUTunion(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
        ("hi", HARDWAREINPUT)
    ]

class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_ulong),
        ("union", _INPUTunion)
    ]

# Load user32.dll
user32 = ctypes.windll.user32


def press_key(vk_code):
    """Press a key down"""
    extra = ctypes.c_ulong(0)
    ii_ = INPUT()
    ii_.type = INPUT_KEYBOARD
    ii_.union.ki = KEYBDINPUT(wVk=vk_code, wScan=0, dwFlags=0, time=0, dwExtraInfo=ctypes.pointer(extra))
    user32.SendInput(1, ctypes.byref(ii_), ctypes.sizeof(ii_))


def release_key(vk_code):
    """Release a key"""
    extra = ctypes.c_ulong(0)
    ii_ = INPUT()
    ii_.type = INPUT_KEYBOARD
    ii_.union.ki = KEYBDINPUT(wVk=vk_code, wScan=0, dwFlags=KEYEVENTF_KEYUP, time=0, dwExtraInfo=ctypes.pointer(extra))
    user32.SendInput(1, ctypes.byref(ii_), ctypes.sizeof(ii_))


def tap_key(vk_code):
    """Press and release a key"""
    press_key(vk_code)
    time.sleep(0.05)
    release_key(vk_code)
    time.sleep(0.05)


def type_text(text):
    """Type text using Unicode input"""
    for char in text:
        extra = ctypes.c_ulong(0)
        
        # Press
        ii_ = INPUT()
        ii_.type = INPUT_KEYBOARD
        ii_.union.ki = KEYBDINPUT(wVk=0, wScan=ord(char), dwFlags=KEYEVENTF_UNICODE, time=0, dwExtraInfo=ctypes.pointer(extra))
        user32.SendInput(1, ctypes.byref(ii_), ctypes.sizeof(ii_))
        
        # Release
        ii_ = INPUT()
        ii_.type = INPUT_KEYBOARD
        ii_.union.ki = KEYBDINPUT(wVk=0, wScan=ord(char), dwFlags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, time=0, dwExtraInfo=ctypes.pointer(extra))
        user32.SendInput(1, ctypes.byref(ii_), ctypes.sizeof(ii_))
        
        time.sleep(0.02)


def type_text_vk(text):
    """Type text using VK codes for ASCII characters - more reliable for dialogs"""
    VK_MAP = {
        'a': 0x41, 'b': 0x42, 'c': 0x43, 'd': 0x44, 'e': 0x45, 'f': 0x46, 'g': 0x47,
        'h': 0x48, 'i': 0x49, 'j': 0x4A, 'k': 0x4B, 'l': 0x4C, 'm': 0x4D, 'n': 0x4E,
        'o': 0x4F, 'p': 0x50, 'q': 0x51, 'r': 0x52, 's': 0x53, 't': 0x54, 'u': 0x55,
        'v': 0x56, 'w': 0x57, 'x': 0x58, 'y': 0x59, 'z': 0x5A,
        '0': 0x30, '1': 0x31, '2': 0x32, '3': 0x33, '4': 0x34,
        '5': 0x35, '6': 0x36, '7': 0x37, '8': 0x38, '9': 0x39,
        ' ': 0x20, '.': 0xBE, '-': 0xBD, '\\': 0xDC, '/': 0xBF
    }
    
    logger.info(f"type_text_vk starting to type: '{text}'")
    
    for i, char in enumerate(text.lower()):
        if char in VK_MAP:
            tap_key(VK_MAP[char])
            time.sleep(0.05)
        else:
            # Fall back to Unicode for special characters
            logger.info(f"Using Unicode fallback for char '{char}' at position {i}")
            extra = ctypes.c_ulong(0)
            
            ii_ = INPUT()
            ii_.type = INPUT_KEYBOARD
            ii_.union.ki = KEYBDINPUT(wVk=0, wScan=ord(char), dwFlags=KEYEVENTF_UNICODE, time=0, dwExtraInfo=ctypes.pointer(extra))
            user32.SendInput(1, ctypes.byref(ii_), ctypes.sizeof(ii_))
            
            ii_ = INPUT()
            ii_.type = INPUT_KEYBOARD
            ii_.union.ki = KEYBDINPUT(wVk=0, wScan=ord(char), dwFlags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, time=0, dwExtraInfo=ctypes.pointer(extra))
            user32.SendInput(1, ctypes.byref(ii_), ctypes.sizeof(ii_))
            
            time.sleep(0.05)
    
    logger.info("type_text_vk completed")


class ActionExecutor:
    """
    Detects and executes system actions from voice commands
    Supports opening websites (webbrowser) and applications (Win+R)
    """
    
    def __init__(self):
        """Initialize the action executor"""
        
        # Action trigger words
        self.action_keywords = [
            'open', 'launch', 'start', 'run', 'execute',
            'browse', 'go to', 'pull up', 'display',
            'load', 'visit', 'navigate to'
        ]
        
        # Search trigger words (separate handling)
        self.search_keywords = [
            'search', 'search for', 'look up', 'find', 'google', 'youtube search'
        ]
        
        # Known websites (will use webbrowser method)
        self.known_websites = {
            'google': 'https://www.google.com',
            'youtube': 'https://www.youtube.com',
            'facebook': 'https://www.facebook.com',
            'twitter': 'https://www.twitter.com',
            'reddit': 'https://www.reddit.com',
            'github': 'https://www.github.com',
            'stackoverflow': 'https://stackoverflow.com',
            'amazon': 'https://www.amazon.com',
            'netflix': 'https://www.netflix.com',
            'spotify': 'https://open.spotify.com',
            'linkedin': 'https://www.linkedin.com',
            'instagram': 'https://www.instagram.com',
            'gmail': 'https://mail.google.com',
            'outlook': 'https://outlook.live.com',
            'yahoo': 'https://www.yahoo.com',
            'bing': 'https://www.bing.com',
            'wikipedia': 'https://www.wikipedia.org',
            'twitch': 'https://www.twitch.tv',
            'discord': 'https://discord.com',
            'tiktok': 'https://www.tiktok.com'
        }
        
        # Known applications (will use Win+R method)
        self.known_applications = {
            'notepad': 'notepad',
            'calculator': 'calc',
            'calc': 'calc',
            'paint': 'mspaint',
            'mspaint': 'mspaint',
            'cmd': 'cmd',
            'command prompt': 'cmd',
            'powershell': 'powershell',
            'chrome': 'chrome',
            'firefox': 'firefox',
            'edge': 'msedge',
            'explorer': 'explorer',
            'file explorer': 'explorer',
            'task manager': 'taskmgr',
            'taskmgr': 'taskmgr',
            'control panel': 'control',
            'settings': 'ms-settings:',
            'excel': 'excel',
            'word': 'winword',
            'outlook app': 'outlook',
            'spotify app': 'spotify'
        }
        
        # Browser lock flag - set to False to disable all browser/app actions
        self.enabled = True
        
        logger.info("ActionExecutor initialized")
        
        # Phase 5: Initialize browser controller if available
        if BROWSER_CONTROLLER_AVAILABLE:
            self.browser_controller = BrowserController()
            logger.info("Phase 5 BrowserController initialized")
        else:
            self.browser_controller = None
            logger.info("Phase 5 not available - browser automation disabled")
    
    def detect_action_command(self, message: str) -> Optional[Dict]:
        """
        Detect if message contains an action command
        
        Args:
            message: User's message
            
        Returns:
            Dict with action details if detected, None otherwise
        """
        message_lower = message.lower().strip()
        
        # Check for action keywords
        detected_keyword = None
        for keyword in self.action_keywords:
            if message_lower.startswith(keyword):
                detected_keyword = keyword
                break
        
        if not detected_keyword:
            return None
        
        # Extract target (everything after the keyword)
        target = message_lower.replace(detected_keyword, '').strip()
        
        # Remove common filler words
        filler_words = ['the', 'a', 'an', 'my', 'please']
        target_words = [word for word in target.split() if word not in filler_words]
        target = ' '.join(target_words)
        
        if not target:
            return None
        
        return {
            'keyword': detected_keyword,
            'target': target,
            'original_message': message
        }
    
    def detect_search_command(self, message: str) -> Optional[Dict]:
        """
        Detect if message contains a search command (including natural language)
        
        Args:
            message: User's message
            
        Returns:
            Dict with search details if detected, None otherwise
        """
        message_lower = message.lower().strip()
        logger.info(f"Checking for search command in: '{message_lower}'")
        
        # AGGRESSIVE CHECK: If message contains "search" or "google" or "youtube", treat as search
        # This prevents it from being treated as a URL by action_command
        search_indicators = ['search', 'google', 'youtube']
        has_search_word = any(word in message_lower for word in search_indicators)
        
        # Exclude internal commands that contain "search" but aren't web searches
        internal_search_phrases = [
            'search your', 'search my', 'search the database', 'search the memory',
            'search your database', 'search your memory', 'search your code',
            'search your files', 'search your logs', 'search your history',
        ]
        if has_search_word and any(phrase in message_lower for phrase in internal_search_phrases):
            logger.info("Search word detected but internal command - skipping browser search")
            return None

        if has_search_word:
            logger.info("Message contains search indicator - treating as search")
            
            # Extract query by removing ALL command words
            query = message_lower
            
            # Remove ALL these phrases in order
            remove_phrases = [
                'open the google search for',
                'open a google search for', 
                'open google search for',
                'open the search for',
                'open a search for',
                'open search for',
                'do a google search for',
                'do google search for',
                'do a search for',
                'do search for',
                'google search for',
                'search google for',
                'search for',
                'open google',
                'open youtube',
                'open',
                'do',
                'the',
                'a ',
            ]
            
            for phrase in remove_phrases:
                query = query.replace(phrase, ' ').strip()
            
            # Clean up multiple spaces
            query = ' '.join(query.split())
            
            # Determine engine
            search_engine = 'youtube' if 'youtube' in message_lower else 'google'
            
            if query and len(query) > 1:  # Make sure we have actual content
                logger.info(f"Extracted search query: '{query}' engine={search_engine}")
                return {
                    'keyword': 'natural_language_search',
                    'query': query,
                    'search_engine': search_engine,
                    'original_message': message
                }
        
        # PATTERN 1: "search [for] X" - traditional (for messages that start with search)
        detected_keyword = None
        for keyword in self.search_keywords:
            if message_lower.startswith(keyword):
                detected_keyword = keyword
                logger.info(f"Found search keyword: '{keyword}'")
                break
        
        if detected_keyword:
            # Extract search query (everything after the keyword)
            query = message_lower.replace(detected_keyword, '').strip()
            
            # Determine search engine
            search_engine = 'google'
            if 'on youtube' in query:
                search_engine = 'youtube'
                query = query.replace('on youtube', '').strip()
            elif 'youtube' in detected_keyword:
                search_engine = 'youtube'
            
            # Remove common filler words
            filler_words = ['for', 'the', 'a', 'an']
            query_words = [word for word in query.split() if word not in filler_words]
            query = ' '.join(query_words)
            
            if query:
                return {
                    'keyword': detected_keyword,
                    'query': query,
                    'search_engine': search_engine,
                    'original_message': message
                }
        
        logger.info("No search command detected")
        return None
        """
        Detect if message contains a search command (including natural language)
        
        Args:
            message: User's message
            
        Returns:
            Dict with search details if detected, None otherwise
        """
        message_lower = message.lower().strip()
        logger.info(f"Checking for search command in: '{message_lower}'")
        
        # PATTERN 1: "search [for] X" - traditional
        detected_keyword = None
        for keyword in self.search_keywords:
            if message_lower.startswith(keyword):
                detected_keyword = keyword
                logger.info(f"Found search keyword: '{keyword}'")
                break
        
        if detected_keyword:
            # Extract search query (everything after the keyword)
            query = message_lower.replace(detected_keyword, '').strip()
            logger.info(f"Extracted initial query: '{query}'")
            
            # Determine search engine (check for "on youtube" pattern)
            search_engine = 'google'
            if 'on youtube' in query:
                search_engine = 'youtube'
                query = query.replace('on youtube', '').strip()
            elif 'youtube' in detected_keyword:
                search_engine = 'youtube'
            
            # Remove common filler words
            filler_words = ['for', 'the', 'a', 'an']
            query_words = [word for word in query.split() if word not in filler_words]
            query = ' '.join(query_words)
            logger.info(f"Final query after cleanup: '{query}'")
            
            if not query:
                logger.info("Query is empty after cleanup")
                return None
            
            return {
                'keyword': detected_keyword,
                'query': query,
                'search_engine': search_engine,
                'original_message': message
            }
        
        # PATTERN 2: "open a search for X" - natural language
        import re
        logger.info("Checking natural language search patterns...")
        natural_patterns = [
            (r'open\s+(?:a\s+)?search\s+(?:for\s+)?(.+)', 'google'),
            (r'(?:do\s+)?(?:a\s+)?(?:google\s+)?search\s+(?:for\s+)?(.+)', 'google'),
            (r'look\s+up\s+(.+?)(?:\s+on\s+(?:google|youtube|the\s+internet))?', 'google'),
            (r'find\s+(?:information\s+)?(?:about\s+)?(.+?)(?:\s+on\s+(?:google|youtube))?', 'google'),
            (r'search\s+(?:google|youtube)\s+for\s+(.+)', None),  # Will determine below
            (r'youtube\s+search\s+(?:for\s+)?(.+)', 'youtube'),
            (r'look\s+up\s+(.+?)\s+on\s+youtube', 'youtube'),
        ]
        
        for pattern, default_engine in natural_patterns:
            logger.info(f"Trying pattern: {pattern}")
            match = re.match(pattern, message_lower)
            if match:
                logger.info(f"PATTERN MATCHED!")
                query = match.group(1).strip()
                logger.info(f"Extracted query: '{query}'")
                
                # Determine search engine
                search_engine = default_engine
                if not search_engine:
                    # Check if youtube is mentioned in the original message
                    if 'youtube' in message_lower:
                        search_engine = 'youtube'
                    else:
                        search_engine = 'google'
                
                # Check if youtube mentioned in query itself
                if 'on youtube' in query:
                    search_engine = 'youtube'
                    query = query.replace('on youtube', '').strip()
                elif 'on google' in query:
                    search_engine = 'google'
                    query = query.replace('on google', '').strip()
                
                # Clean up query
                query = query.strip()
                
                if query:
                    logger.info(f"Natural language search detected: '{query}' on {search_engine}")
                    return {
                        'keyword': 'natural_language_search',
                        'query': query,
                        'search_engine': search_engine,
                        'original_message': message
                    }
        
        logger.info("No search command detected")
        return None
    
    def classify_target(self, target: str) -> Dict:
        """
        Classify the target and determine execution method
        
        Args:
            target: The target to open (website, app, file)
            
        Returns:
            Dict with classification and execution details
        """
        target_lower = target.lower().strip()
        
        # Check if it's a known website
        if target_lower in self.known_websites:
            return {
                'type': 'website',
                'method': 'webbrowser',
                'url': self.known_websites[target_lower],
                'display_name': target_lower
            }
        
        # Check if it contains URL indicators
        url_patterns = ['.com', '.org', '.net', '.edu', '.gov', '.io', 'http://', 'https://']
        if any(pattern in target_lower for pattern in url_patterns):
            # It's a URL
            url = target if target.startswith('http') else f'https://{target}'
            return {
                'type': 'website',
                'method': 'webbrowser',
                'url': url,
                'display_name': target
            }
        
        # Check if it's a known application
        if target_lower in self.known_applications:
            return {
                'type': 'application',
                'method': 'win_r',
                'command': self.known_applications[target_lower],
                'display_name': target_lower
            }
        
        # Check for file extensions (likely a file)
        file_extensions = ['.txt', '.pdf', '.docx', '.xlsx', '.exe', '.bat', '.py']
        if any(ext in target_lower for ext in file_extensions):
            return {
                'type': 'file',
                'method': 'win_r',
                'command': target,
                'display_name': target
            }
        
        # Check if it looks like a file path
        if '\\' in target or '/' in target or ':' in target:
            return {
                'type': 'file',
                'method': 'win_r',
                'command': target,
                'display_name': target
            }
        
        # Unknown - try as website with .com
        return {
            'type': 'website',
            'method': 'webbrowser',
            'url': f'https://{target}.com',
            'display_name': f'{target}.com'
        }
    
    def execute_webbrowser(self, url: str) -> Dict:
        """
        Open URL using webbrowser module
        
        Args:
            url: URL to open
            
        Returns:
            Dict with execution result
        """
        try:
            webbrowser.open_new_tab(url)
            logger.info(f"Opened {url}")
            return {'success': True, 'method': 'webbrowser', 'url': url}
        except Exception as e:
            logger.error(f"Failed to open {url}: {e}")
            return {'success': False, 'method': 'webbrowser', 'url': url, 'error': str(e)}
    
    def execute_win_r(self, command: str) -> Dict:
        """
        Execute command using Windows Run dialog (Win+R) via user32.dll SendInput
        
        Args:
            command: Command to execute
            
        Returns:
            Dict with execution result
        """
        try:
            # Press and hold Win key
            press_key(VK_LWIN)
            time.sleep(0.1)
            
            # Tap R while Win is held
            tap_key(VK_R)
            time.sleep(0.1)
            
            # Release Win key
            release_key(VK_LWIN)
            
            # Wait longer for Run dialog to fully open
            time.sleep(1.5)
            
            # Type the command using VK codes (more reliable for Run dialog)
            type_text_vk(command)
            
            # Wait before Enter
            time.sleep(0.3)
            
            # Press Enter
            tap_key(VK_RETURN)
            
            logger.info(f"Executed '{command}' via Win+R")
            return {'success': True, 'method': 'win_r', 'command': command}
        except Exception as e:
            logger.error(f"Failed to execute '{command}': {e}")
            return {'success': False, 'method': 'win_r', 'command': command, 'error': str(e)}
    
    def execute_search(self, query: str, search_engine: str = 'google') -> Dict:
        """
        Execute a search query on Google or YouTube
        
        Args:
            query: Search query
            search_engine: 'google' or 'youtube'
            
        Returns:
            Dict with execution result
        """
        try:
            import urllib.parse
            
            # Encode the query for URL
            encoded_query = urllib.parse.quote_plus(query)
            
            # Build search URL
            if search_engine == 'youtube':
                search_url = f'https://www.youtube.com/results?search_query={encoded_query}'
            else:  # default to google
                search_url = f'https://www.google.com/search?q={encoded_query}'
            
            logger.info(f"ABOUT TO OPEN BROWSER WITH URL: {search_url}")
            
            # Open search in browser
            import webbrowser
            webbrowser.open_new_tab(search_url)
            
            logger.info(f"WEBBROWSER.OPEN_NEW_TAB CALLED SUCCESSFULLY")
            logger.info(f"Searched {search_engine} for: {query}")
            return {
                'success': True,
                'method': 'search',
                'query': query,
                'search_engine': search_engine,
                'url': search_url
            }
        except Exception as e:
            logger.error(f"EXCEPTION IN EXECUTE_SEARCH: {e}")
            logger.error(f"Failed to search for '{query}': {e}")
            return {
                'success': False,
                'method': 'search',
                'query': query,
                'error': str(e)
            }
    
    def is_browser_open(self) -> bool:
        """
        Check if any browser window is currently open
        
        Returns:
            True if browser detected, False otherwise
        """
        # Common browser window class names and titles
        browser_classes = [
            b'Chrome_WidgetWin_1',  # Chrome
            b'MozillaWindowClass',  # Firefox
            b'ApplicationFrameWindow'  # Edge
        ]
        
        for class_name in browser_classes:
            hwnd = user32.FindWindowA(class_name, None)
            if hwnd != 0:
                return True
        
        return False
    
    def search_in_browser_addressbar(self, query: str, search_engine: str = 'google') -> Dict:
        """
        Type search into browser address bar using Ctrl+L (works on any open page)
        
        Args:
            query: Search query
            search_engine: 'google' or 'youtube'
            
        Returns:
            Dict with execution result
        """
        try:
            # Build search query
            if search_engine == 'youtube':
                # For YouTube, prefix with "youtube" so browser searches YouTube
                full_query = f'youtube {query}'
            else:
                # For Google, just type the query (browser will auto-search)
                full_query = query
            
            logger.info(f"Starting address bar search, query: '{full_query}'")
            
            # Focus address bar with Ctrl+L
            logger.info("Pressing Ctrl+L")
            press_key(VK_CONTROL)
            time.sleep(0.05)
            tap_key(VK_L)
            time.sleep(0.05)
            release_key(VK_CONTROL)
            
            # Wait for address bar to focus
            time.sleep(0.3)
            
            # Type the query
            logger.info(f"Typing query: '{full_query}'")
            type_text_vk(full_query)
            
            # Press Enter
            logger.info("Pressing Enter")
            time.sleep(0.2)
            tap_key(VK_RETURN)
            
            logger.info(f"Searched {search_engine} in address bar for: {query}")
            return {
                'success': True,
                'method': 'addressbar_search',
                'query': query,
                'search_engine': search_engine
            }
        except Exception as e:
            logger.error(f"Failed to search in address bar for '{query}': {e}")
            return {
                'success': False,
                'method': 'addressbar_search',
                'query': query,
                'error': str(e)
            }
    
    def process_command(self, user_message: str) -> Dict:
        """
        Main entry point - process and execute action commands immediately
        
        Args:
            user_message: User's message
            
        Returns:
            Dict with processing result
        """
        # Browser lock check
        if not self.enabled:
            return {'executed': False, 'reason': 'browser_locked'}
        
        # Phase 5: Check for complex browser automation commands FIRST
        if self.browser_controller and self.browser_controller.is_available():
            complex_result = self.browser_controller.process_command(user_message)
            if complex_result['executed']:
                logger.info(f"Phase 5: Executed complex browser command")
                return complex_result
        
        # Phase 4: Check for search command
        search_data = self.detect_search_command(user_message)
        
        if search_data:
            logger.info(f"Detected search: query='{search_data['query']}' engine={search_data['search_engine']}")
            
            # ALWAYS open in new tab - more reliable than Ctrl+L
            logger.info("Opening new browser tab")
            result = self.execute_search(search_data['query'], search_data['search_engine'])
            
            return {
                'executed': True,
                'success': result['success'],
                'action': 'search',
                'target': f"{search_data['query']} on {search_data['search_engine']}",
                'method': result.get('method', 'search')
            }
        
        # Check for regular action command
        action_data = self.detect_action_command(user_message)
        
        if not action_data:
            return {'executed': False, 'reason': 'not_an_action_command'}
        
        # Classify the target
        classification = self.classify_target(action_data['target'])
        
        # Execute immediately
        if classification['method'] == 'webbrowser':
            result = self.execute_webbrowser(classification['url'])
        else:  # win_r
            result = self.execute_win_r(classification['command'])
        
        return {
            'executed': True,
            'success': result['success'],
            'action': action_data['keyword'],
            'target': classification['display_name'],
            'method': classification['method']
        }