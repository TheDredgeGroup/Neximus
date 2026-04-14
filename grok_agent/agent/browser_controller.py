"""
Browser Controller Module
Phase 5 - Advanced web automation using Playwright (100% local, no cloud API)
Enables AI agent to navigate, click, type, and extract data from web pages
"""

import logging
import asyncio
from typing import Dict, Optional, List

logger = logging.getLogger(__name__)

# Try to import Playwright for local browser automation
try:
    from playwright.async_api import async_playwright
    from playwright.sync_api import sync_playwright
    BROWSER_USE_AVAILABLE = True
    logger.info("Playwright is available for browser automation")
except ImportError as e:
    BROWSER_USE_AVAILABLE = False
    logger.warning(f"Playwright not available: {e}")
    logger.warning("Install with: pip install playwright && playwright install chromium")


class BrowserController:
    """
    Advanced browser automation using Playwright (100% local)
    Handles complex multi-step navigation, clicking, form filling, and data extraction
    No cloud API required - runs entirely on your machine
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the browser controller with local Playwright
        
        Args:
            api_key: Not needed for local automation (kept for compatibility)
        """
        self.browser_use_available = BROWSER_USE_AVAILABLE
        self.agent = None
        self.api_key = api_key
        
        if not self.browser_use_available:
            logger.warning("BrowserController initialized but Playwright is not available")
            logger.warning("Install with: pip install playwright")
            logger.warning("Then run: playwright install chromium")
            return
        
        # Browser lock flag
        self.enabled = True
        
        logger.info("BrowserController initialized with local Playwright (no cloud API needed)")
    
    def is_available(self) -> bool:
        """Check if browser-use is installed and available"""
        return self.browser_use_available
    
    async def execute_task(self, task: str) -> Dict:
        """
        Execute a browser automation task using local Playwright
        
        Args:
            task: Natural language description of task
            
        Returns:
            Dict with execution result
        """
        if not self.browser_use_available:
            return {
                'success': False,
                'error': 'Browser automation not available',
                'message': 'Install with: pip install playwright && playwright install chromium'
            }
        
        # Define at function level so error handler can access them
        p = None
        browser = None
        context = None
        page = None
        
        try:
            logger.info(f"Starting browser task: {task}")
            
            # Use Playwright without context manager to keep browser open
            from playwright.async_api import async_playwright
            
            # Launch browser and keep it open
            p = await async_playwright().start()
            
            # Launch with stealth settings to avoid bot detection
            browser = await p.chromium.launch(
                headless=False,
                args=[
                    '--disable-blink-features=AutomationControlled',  # Hide automation
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-web-security',
                    '--disable-features=IsolateOrigins,site-per-process'
                ]
            )
            
            # Create context with human-like settings
            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080},
                locale='en-US',
                timezone_id='America/Los_Angeles'
            )
            
            # Remove webdriver flag
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)
            
            page = await context.new_page()
            
            # Parse the task and execute
            task_lower = task.lower()
            
            # Navigate to site
            if 'amazon' in task_lower:
                await page.goto('https://www.amazon.com', wait_until='domcontentloaded')
                logger.info("Navigated to Amazon")
                
                # Wait for page to fully load
                await page.wait_for_timeout(2000)
                
                # Search for product
                if 'search' in task_lower:
                    # Extract search query
                    words = task_lower.split()
                    if 'for' in words:
                        query_start = words.index('for') + 1
                        query = ' '.join(words[query_start:])
                    else:
                        # Try to extract after "search"
                        search_idx = words.index('search')
                        query = ' '.join(words[search_idx + 1:])
                        if not query:
                            query = 'headphones'  # default
                    
                    logger.info(f"Looking for search box and typing: {query}")
                    
                    # Human-like delay before interacting
                    await page.wait_for_timeout(500)
                    
                    # Try multiple selectors for Amazon search box
                    search_selectors = [
                        '#twotabsearchtextbox',
                        'input[type="text"][name="field-keywords"]',
                        'input#nav-search-bar-input',
                        'input[placeholder*="Search"]'
                    ]
                    
                    search_found = False
                    for selector in search_selectors:
                        try:
                            await page.wait_for_selector(selector, timeout=5000)
                            # Type slowly like a human (100ms between characters)
                            await page.type(selector, query, delay=100)
                            await page.press(selector, 'Enter')
                            logger.info(f"Searched for: {query} using selector: {selector}")
                            search_found = True
                            break
                        except Exception as e:
                            logger.info(f"Selector {selector} didn't work, trying next...")
                            continue
                    
                    if not search_found:
                        logger.error("Could not find Amazon search box with any selector")
                        return {
                            'success': False,
                            'error': 'Could not find search box on Amazon',
                            'task': task
                        }
                    
                    # Wait for search results to load (page will redirect)
                    try:
                        await page.wait_for_load_state('domcontentloaded', timeout=10000)
                        logger.info("Search results loaded")
                    except Exception as e:
                        # If wait fails, that's okay - search probably still worked
                        logger.info(f"Wait for results completed with: {e}")
                    
                    # Small delay so user can see the search happened
                    await page.wait_for_timeout(1000)

            
            elif 'google' in task_lower:
                await page.goto('https://www.google.com', wait_until='domcontentloaded')
                logger.info("Navigated to Google")
                
                await page.wait_for_timeout(2000)
                
                if 'search' in task_lower:
                    words = task_lower.split()
                    if 'for' in words:
                        query_start = words.index('for') + 1
                        query = ' '.join(words[query_start:])
                    else:
                        search_idx = words.index('search')
                        query = ' '.join(words[search_idx + 1:])
                        if not query:
                            query = task_lower.replace('google', '').replace('search', '').strip()
                    
                    logger.info(f"Looking for Google search box and typing: {query}")
                    
                    # Human-like delay before interacting
                    await page.wait_for_timeout(500)
                    
                    # Try multiple selectors for Google search
                    search_selectors = [
                        'textarea[name="q"]',
                        'input[name="q"]',
                        'textarea[title*="Search"]',
                        'input[title*="Search"]'
                    ]
                    
                    search_found = False
                    for selector in search_selectors:
                        try:
                            await page.wait_for_selector(selector, timeout=5000)
                            # Type slowly like a human (100ms between characters)
                            await page.type(selector, query, delay=100)
                            await page.press(selector, 'Enter')
                            logger.info(f"Searched for: {query} using selector: {selector}")
                            search_found = True
                            break
                        except Exception:
                            continue
                    
                    if not search_found:
                        logger.error("Could not find Google search box")
                        return {
                            'success': False,
                            'error': 'Could not find search box on Google',
                            'task': task
                        }
                    
                    # Wait for search results to load
                    try:
                        await page.wait_for_load_state('domcontentloaded', timeout=10000)
                        logger.info("Search results loaded")
                    except Exception as e:
                        logger.info(f"Wait for results completed with: {e}")
                    
                    # Small delay so user can see the search happened
                    await page.wait_for_timeout(1000)
            
            else:
                # Generic URL navigation
                logger.info(f"Attempting to navigate based on task: {task}")
                # Extract potential URLs or keywords
                # For now, just log that we couldn't handle it
                return {
                    'success': False,
                    'error': f'Site not yet supported: {task}',
                    'task': task
                }
            
            # Browser stays open - don't close it
            # Store references to prevent garbage collection
            if not hasattr(self, 'browsers'):
                self.browsers = []
            self.browsers.append((p, browser, context, page))
            
            # CRITICAL: Do NOT call p.stop(), browser.close(), or page.close()
            # Browser must stay open for user interaction
            
            logger.info(f"Browser task completed: {task}")
            logger.info("Browser window left open for user interaction")
            
            return {
                'success': True,
                'result': 'Task completed successfully',
                'task': task
            }
            
        except Exception as e:
            logger.error(f"Browser task failed: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            # Even if task failed, keep browser open if it was created
            if p and browser and context and page:
                try:
                    if not hasattr(self, 'browsers'):
                        self.browsers = []
                    self.browsers.append((p, browser, context, page))
                    logger.info("Browser window left open despite error")
                except Exception as store_error:
                    logger.warning(f"Could not store browser reference: {store_error}")
            
            return {
                'success': False,
                'error': str(e),
                'task': task
            }
    
    def execute_task_sync(self, task: str) -> Dict:
        """
        Synchronous wrapper for execute_task
        
        Args:
            task: Natural language description of task
            
        Returns:
            Dict with execution result
        """
        return asyncio.run(self.execute_task(task))
    
    def detect_complex_command(self, message: str) -> Optional[Dict]:
        """
        Detect if message contains a complex browser automation command
        
        Args:
            message: User's message
            
        Returns:
            Dict with task details if detected, None otherwise
        """
        message_lower = message.lower().strip()
      
        # Quick check for actual browser intent - skip if none
        browser_keywords = ['open', 'go to', 'navigate', 'visit', 'search', 'browse', 'website', 'url', 'amazon', 'google', 'click', 'type', 'fill', 'extract']
        if not any(keyword in message_lower for keyword in browser_keywords):
              logger.info("No browser keywords detected - skipping complex command")
        return None
       



        
        # Pattern 1: Multi-step with explicit connectors
        explicit_multistep = [' and ', ' then ', ', then']
        if any(connector in message_lower for connector in explicit_multistep):
            logger.info(f"Detected complex command: multi-step with connector")
            return {
                'task': message,
                'type': 'complex_navigation',
                'original_message': message
            }
        
        # Pattern 2: Navigation + search (with or without "and")
        # Examples: "open amazon search for X", "go to google search X"
        nav_words = ['open', 'go to', 'navigate to', 'visit']
        for nav_word in nav_words:
            if message_lower.startswith(nav_word) and 'search' in message_lower:
                logger.info(f"Detected complex command: navigation + search")
                return {
                    'task': message,
                    'type': 'complex_navigation',
                    'original_message': message
                }
        
        # Pattern 3: Direct page actions (click, fill, extract, etc.)
        action_patterns = [
            'click the', 'click on', 'press the', 'press button',
            'fill in', 'fill the', 'type in', 'type into', 'enter in',
            'extract', 'scrape', 'get the', 'what is', 'what\'s the'
        ]
        if any(pattern in message_lower for pattern in action_patterns):
            logger.info(f"Detected complex command: page action")
            return {
                'task': message,
                'type': 'page_action',
                'original_message': message
            }
        
        return None
    
    def process_command(self, user_message: str) -> Dict:
        """
        Process a browser automation command
        
        Args:
            user_message: User's message
            
        Returns:
            Dict with processing result
        """
        # Browser lock check
        if not self.enabled:
            return {'executed': False, 'reason': 'browser_locked'}
        
        # Check if browser-use is available
        if not self.is_available():
            return {
                'executed': False,
                'reason': 'browser_use_not_installed',
                'message': 'Install with: pip install browser-use playwright'
            }
        
        # Detect if this is a complex command
        complex_data = self.detect_complex_command(user_message)
        
        if not complex_data:
            return {
                'executed': False,
                'reason': 'not_a_complex_command'
            }
        
        # Execute the task
        logger.info(f"Executing complex browser task: {complex_data['task']}")
        result = self.execute_task_sync(complex_data['task'])
        
        return {
            'executed': True,
            'success': result['success'],
            'action': 'browser_automation',
            'target': complex_data['task'],
            'method': 'browser_use',
            'result': result.get('result', None),
            'error': result.get('error', None)
        }


class BrowserControllerSimple:
    """
    Simplified browser controller that doesn't require browser-use
    Uses basic Playwright commands for simple automation
    """
    
    def __init__(self):
        """Initialize simple browser controller"""
        try:
            from playwright.sync_api import sync_playwright
            self.playwright_available = True
            self.playwright = None
            self.browser = None
            self.page = None
            logger.info("BrowserControllerSimple initialized with Playwright")
        except ImportError:
            self.playwright_available = False
            logger.warning("Playwright not installed. Install with: pip install playwright")
    
    def is_available(self) -> bool:
        """Check if Playwright is available"""
        return self.playwright_available
    
    def start_browser(self):
        """Start browser instance"""
        if not self.playwright_available:
            return False
        
        try:
            from playwright.sync_api import sync_playwright
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(headless=False)
            self.page = self.browser.new_page()
            logger.info("Browser started")
            return True
        except Exception as e:
            logger.error(f"Failed to start browser: {e}")
            return False
    
    def close_browser(self):
        """Close browser instance"""
        try:
            if self.page:
                self.page.close()
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
            logger.info("Browser closed")
        except Exception as e:
            logger.error(f"Error closing browser: {e}")
    
    def navigate(self, url: str) -> Dict:
        """Navigate to URL"""
        try:
            if not self.page:
                self.start_browser()
            
            self.page.goto(url)
            logger.info(f"Navigated to {url}")
            return {'success': True, 'url': url}
        except Exception as e:
            logger.error(f"Navigation failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def click_element(self, selector: str) -> Dict:
        """Click an element"""
        try:
            if not self.page:
                return {'success': False, 'error': 'No browser instance'}
            
            self.page.click(selector)
            logger.info(f"Clicked element: {selector}")
            return {'success': True, 'selector': selector}
        except Exception as e:
            logger.error(f"Click failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def type_text(self, selector: str, text: str) -> Dict:
        """Type text into element"""
        try:
            if not self.page:
                return {'success': False, 'error': 'No browser instance'}
            
            self.page.fill(selector, text)
            logger.info(f"Typed text into {selector}")
            return {'success': True, 'selector': selector, 'text': text}
        except Exception as e:
            logger.error(f"Type failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def extract_text(self, selector: str) -> Dict:
        """Extract text from element"""
        try:
            if not self.page:
                return {'success': False, 'error': 'No browser instance'}
            
            text = self.page.text_content(selector)
            logger.info(f"Extracted text from {selector}: {text[:50]}...")
            return {'success': True, 'selector': selector, 'text': text}
        except Exception as e:
            logger.error(f"Extract failed: {e}")
            return {'success': False, 'error': str(e)}