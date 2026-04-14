"""
Vision Integration Module - COMPLETE REPLACEMENT
Provides deep screen inspection using Windows UI Automation + Screenshot fallback
Supports multi-monitor setups with per-monitor selection
"""

import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import json
import time

logger = logging.getLogger(__name__)

# Check if UI Automation is available (but don't import yet - lazy load to avoid COM conflicts)
try:
    import importlib.util
    spec = importlib.util.find_spec("pywinauto")
    UI_AUTOMATION_AVAILABLE = spec is not None
    if UI_AUTOMATION_AVAILABLE:
        logger.info("OK - UI Automation available (pywinauto)")
except ImportError:
    UI_AUTOMATION_AVAILABLE = False
    logger.warning("UI Automation not available - install: pip install pywinauto")

# Try to import screenshot capability (fallback method)
try:
    import mss
    from PIL import Image
    SCREENSHOT_AVAILABLE = True
    logger.info("OK - Screenshot capability available (mss)")
except ImportError:
    SCREENSHOT_AVAILABLE = False
    logger.warning("Screenshot not available - install: pip install mss pillow")

# Try to import OCR (for screenshot text extraction)
try:
    import easyocr
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    logger.warning("OCR not available - install: pip install easyocr")


@dataclass
class UIElement:
    """Represents a UI element with all its properties"""
    name: str
    control_type: str
    automation_id: str
    class_name: str
    rectangle: Tuple[int, int, int, int]  # (left, top, right, bottom)
    is_enabled: bool
    is_visible: bool
    is_keyboard_focusable: bool
    value: Optional[str] = None
    children_count: int = 0
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "name": self.name,
            "type": self.control_type,
            "automation_id": self.automation_id,
            "class": self.class_name,
            "coords": {
                "left": self.rectangle[0],
                "top": self.rectangle[1],
                "right": self.rectangle[2],
                "bottom": self.rectangle[3],
                "width": self.rectangle[2] - self.rectangle[0],
                "height": self.rectangle[3] - self.rectangle[1]
            },
            "enabled": self.is_enabled,
            "visible": self.is_visible,
            "focusable": self.is_keyboard_focusable,
            "value": self.value,
            "children": self.children_count
        }
    
    def center_point(self) -> Tuple[int, int]:
        """Get center coordinates of element"""
        x = (self.rectangle[0] + self.rectangle[2]) // 2
        y = (self.rectangle[1] + self.rectangle[3]) // 2
        return (x, y)


@dataclass
class MonitorInfo:
    """Information about a monitor"""
    index: int
    left: int
    top: int
    width: int
    height: int
    is_primary: bool
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "monitor": self.index,
            "left": self.left,
            "top": self.top,
            "width": self.width,
            "height": self.height,
            "primary": self.is_primary,
            "right": self.left + self.width,
            "bottom": self.top + self.height
        }


class VisionIntegration:
    """
    Provides deep screen vision using UI Automation + Screenshot fallback
    Supports multi-monitor setups
    """
    
    def __init__(self):
        """Initialize vision integration"""
        self.capabilities = {
            "ui_automation": UI_AUTOMATION_AVAILABLE,
            "screenshot": SCREENSHOT_AVAILABLE,
            "ocr": OCR_AVAILABLE
        }
        
        # Multi-monitor support
        self.monitors: List[MonitorInfo] = []
        self.selected_monitor: Optional[int] = None  # None = all monitors
        
        # OCR reader (lazy loaded)
        self.ocr_reader = None
        
        # Initialize monitors
        self._detect_monitors()
        
        logger.info(f"Vision Integration initialized - Capabilities: {self.capabilities}")
        logger.info(f"Detected {len(self.monitors)} monitor(s)")
    
    def _detect_monitors(self):
        """Detect all available monitors"""
        if not SCREENSHOT_AVAILABLE:
            logger.warning("Cannot detect monitors - mss not available")
            return
        
        try:
            with mss.mss() as sct:
                # Monitor 0 is the combined virtual screen
                # Monitors 1+ are individual displays
                for i, monitor in enumerate(sct.monitors[1:], start=1):
                    monitor_info = MonitorInfo(
                        index=i,
                        left=monitor['left'],
                        top=monitor['top'],
                        width=monitor['width'],
                        height=monitor['height'],
                        is_primary=(i == 1)  # First monitor is typically primary
                    )
                    self.monitors.append(monitor_info)
                    logger.info(f"  Monitor {i}: {monitor['width']}x{monitor['height']} at ({monitor['left']}, {monitor['top']})")
        except Exception as e:
            logger.error(f"Monitor detection failed: {e}")
    
    def get_monitors(self) -> List[Dict]:
        """
        Get list of all available monitors
        
        Returns:
            List of monitor information dictionaries
        """
        return [m.to_dict() for m in self.monitors]
    
    def select_monitor(self, monitor_index: Optional[int] = None):
        """
        Select which monitor to focus vision on
        
        Args:
            monitor_index: Monitor number (1, 2, 3...) or None for all monitors
        """
        if monitor_index is None:
            self.selected_monitor = None
            logger.info("Vision set to ALL monitors")
        elif 1 <= monitor_index <= len(self.monitors):
            self.selected_monitor = monitor_index
            logger.info(f"Vision set to Monitor {monitor_index}")
        else:
            raise ValueError(f"Invalid monitor index: {monitor_index}. Available: 1-{len(self.monitors)}")
    
    def get_selected_monitor_info(self) -> Optional[Dict]:
        """Get information about currently selected monitor"""
        if self.selected_monitor is None:
            return {"mode": "all_monitors", "count": len(self.monitors)}
        
        for monitor in self.monitors:
            if monitor.index == self.selected_monitor:
                return monitor.to_dict()
        return None
    
    def _init_ocr(self):
        """Lazy load OCR reader"""
        if not OCR_AVAILABLE:
            return
        
        if self.ocr_reader is None:
            try:
                logger.info("Initializing OCR... (first run may download model)")
                self.ocr_reader = easyocr.Reader(['en'], gpu=False, verbose=False)
                logger.info("OK - OCR ready")
            except Exception as e:
                logger.error(f"OCR initialization failed: {e}")
                self.ocr_reader = False
    
    def inspect_window(self, window_title: Optional[str] = None) -> Dict:
        """
        Deep inspection of window using UI Automation
        
        Args:
            window_title: Window title to inspect (None = active window)
        
        Returns:
            Dictionary with complete UI tree and element details
        """
        if not UI_AUTOMATION_AVAILABLE:
            return {
                "error": "UI Automation not available",
                "suggestion": "Install pywinauto: pip install pywinauto",
                "fallback": "Use capture_screen_with_ocr() instead"
            }
        
        try:
            # Lazy import to avoid COM conflicts with tkinterdnd2
            from pywinauto import Desktop
            
            desktop = Desktop(backend="uia")
            
            # Get target window
            if window_title:
                windows = desktop.windows()
                window = None
                for w in windows:
                    try:
                        if window_title.lower() in w.window_text().lower():
                            window = w
                            break
                    except:
                        continue
                
                if window is None:
                    return {"error": f"Window containing '{window_title}' not found"}
            else:
                # Get active window
                try:
                    window = desktop.top_window()
                except:
                    return {"error": "No active window found"}
            
            # Build UI tree
            ui_tree = self._build_ui_tree(window)
            
            # Get window bounds
            rect = window.rectangle()
            
            result = {
                "window_title": window.window_text(),
                "window_class": window.class_name(),
                "window_bounds": {
                    "left": rect.left,
                    "top": rect.top,
                    "right": rect.right,
                    "bottom": rect.bottom,
                    "width": rect.width(),
                    "height": rect.height()
                },
                "element_count": ui_tree["element_count"],
                "ui_tree": ui_tree["tree"][:50],  # Limit tree depth for performance
                "clickable_elements": ui_tree["clickable"],
                "editable_elements": ui_tree["editable"],
                "method": "ui_automation"
            }
            
            logger.info(f"Window inspection complete: {ui_tree['element_count']} elements found")
            return result
            
        except Exception as e:
            logger.error(f"Window inspection failed: {e}")
            return {
                "error": str(e),
                "suggestion": "Try capture_screen_with_ocr() for fallback"
            }
    
    def _build_ui_tree(self, window, max_depth: int = 5, current_depth: int = 0) -> Dict:
        """
        Recursively build UI element tree
        
        Args:
            window: pywinauto window/control
            max_depth: Maximum depth to traverse
            current_depth: Current recursion depth
        
        Returns:
            Dictionary with tree structure and categorized elements
        """
        tree = []
        clickable = []
        editable = []
        element_count = 0
        
        if current_depth >= max_depth:
            return {
                "tree": tree,
                "clickable": clickable,
                "editable": editable,
                "element_count": element_count
            }
        
        try:
            # Get all child elements
            children = window.children()
            
            for child in children:
                try:
                    element_count += 1
                    
                    # Extract element info
                    elem_info = child.element_info
                    rect = child.rectangle()
                    
                    # Check if element is on selected monitor
                    if self.selected_monitor:
                        monitor = self.monitors[self.selected_monitor - 1]
                        # Check if element rectangle overlaps with selected monitor
                        if not self._rect_overlaps_monitor(rect, monitor):
                            continue
                    
                    element = UIElement(
                        name=elem_info.name or "",
                        control_type=elem_info.control_type or "Unknown",
                        automation_id=elem_info.automation_id or "",
                        class_name=elem_info.class_name or "",
                        rectangle=(rect.left, rect.top, rect.right, rect.bottom),
                        is_enabled=child.is_enabled(),
                        is_visible=child.is_visible(),
                        is_keyboard_focusable=child.is_keyboard_focusable()
                    )
                    
                    # Try to get value for text inputs
                    try:
                        if hasattr(child, 'get_value'):
                            element.value = child.get_value()
                    except:
                        pass
                    
                    # Categorize elements
                    element_dict = element.to_dict()
                    tree.append(element_dict)
                    
                    # Track clickable elements (buttons, links, etc.)
                    if element.control_type in ["Button", "MenuItem", "Hyperlink", "RadioButton", 
                                                  "CheckBox", "TabItem", "ListItem", "TreeItem"]:
                        if element.is_enabled and element.is_visible:
                            clickable.append({
                                "name": element.name,
                                "type": element.control_type,
                                "center": element.center_point(),
                                "automation_id": element.automation_id,
                                "coords": element_dict["coords"]
                            })
                    
                    # Track editable elements (text boxes, combo boxes)
                    if element.control_type in ["Edit", "Document", "ComboBox", "Text"]:
                        if element.is_enabled and element.is_visible:
                            editable.append({
                                "name": element.name,
                                "type": element.control_type,
                                "center": element.center_point(),
                                "current_value": element.value,
                                "coords": element_dict["coords"]
                            })
                    
                    # Recurse for children (limited depth)
                    if current_depth < 3:  # Limit recursion depth
                        child_result = self._build_ui_tree(child, max_depth, current_depth + 1)
                        clickable.extend(child_result["clickable"])
                        editable.extend(child_result["editable"])
                        element_count += child_result["element_count"]
                    
                except Exception as e:
                    logger.debug(f"Error processing child element: {e}")
                    continue
        
        except Exception as e:
            logger.debug(f"Error getting children: {e}")
        
        return {
            "tree": tree,
            "clickable": clickable,
            "editable": editable,
            "element_count": element_count
        }
    
    def _rect_overlaps_monitor(self, rect, monitor: MonitorInfo) -> bool:
        """Check if rectangle overlaps with monitor bounds"""
        return not (
            rect.right < monitor.left or
            rect.left > (monitor.left + monitor.width) or
            rect.bottom < monitor.top or
            rect.top > (monitor.top + monitor.height)
        )
    
    def find_elements(
        self, 
        name: Optional[str] = None,
        control_type: Optional[str] = None,
        window_title: Optional[str] = None
    ) -> List[Dict]:
        """
        Find UI elements by criteria
        
        Args:
            name: Element name to search for (partial match)
            control_type: Control type (Button, Edit, etc.)
            window_title: Window to search in (None = active)
        
        Returns:
            List of matching elements
        """
        inspection = self.inspect_window(window_title)
        
        if "error" in inspection:
            return []
        
        matches = []
        
        def search_tree(elements):
            for elem in elements:
                # Check name match
                if name and name.lower() not in elem.get("name", "").lower():
                    continue
                
                # Check type match
                if control_type and elem.get("type") != control_type:
                    continue
                
                matches.append(elem)
                
                # Search children
                if "children" in elem:
                    search_tree(elem["children"])
        
        search_tree(inspection.get("ui_tree", []))
        
        logger.info(f"Found {len(matches)} matching elements")
        return matches
    
    def capture_screen(self, monitor: Optional[int] = None) -> Optional[Image.Image]:
        """
        Capture screenshot of specified monitor
        
        Args:
            monitor: Monitor index (1, 2, 3...) or None for selected monitor
        
        Returns:
            PIL Image or None if capture fails
        """
        if not SCREENSHOT_AVAILABLE:
            logger.error("Screenshot not available - mss not installed")
            return None
        
        try:
            # Determine which monitor to capture
            target_monitor = monitor or self.selected_monitor or 1
            
            with mss.mss() as sct:
                # Validate monitor index
                if target_monitor < 1 or target_monitor > len(sct.monitors) - 1:
                    logger.error(f"Invalid monitor index: {target_monitor}")
                    return None
                
                # Capture
                monitor_data = sct.monitors[target_monitor]
                screenshot = sct.grab(monitor_data)
                
                # Convert to PIL Image
                img = Image.frombytes('RGB', screenshot.size, screenshot.rgb)
                
                logger.info(f"Screenshot captured from Monitor {target_monitor}: {img.size}")
                return img
        
        except Exception as e:
            logger.error(f"Screenshot capture failed: {e}")
            return None
    
    def capture_screen_with_ocr(self, monitor: Optional[int] = None) -> Dict:
        """
        Capture screenshot and extract text with OCR
        
        Args:
            monitor: Monitor index or None for selected monitor
        
        Returns:
            Dictionary with screenshot info and OCR results
        """
        img = self.capture_screen(monitor)
        
        if img is None:
            return {"error": "Screenshot capture failed"}
        
        result = {
            "monitor": monitor or self.selected_monitor or 1,
            "size": {"width": img.width, "height": img.height},
            "method": "screenshot_ocr"
        }
        
        # Run OCR if available
        if OCR_AVAILABLE:
            self._init_ocr()
            
            if self.ocr_reader and self.ocr_reader is not False:
                try:
                    import numpy as np
                    from PIL import ImageEnhance
                    
                    # Enhance image for better OCR
                    enhanced = img.copy()
                    
                    # Increase contrast
                    enhancer = ImageEnhance.Contrast(enhanced)
                    enhanced = enhancer.enhance(1.5)
                    
                    # Increase sharpness
                    enhancer = ImageEnhance.Sharpness(enhanced)
                    enhanced = enhancer.enhance(2.0)
                    
                    image_np = np.array(enhanced)
                    
                    logger.info("Running OCR on screenshot...")
                    # Aggressive OCR parameters to capture ALL text
                    ocr_results = self.ocr_reader.readtext(
                        image_np,
                        detail=1,
                        paragraph=False,
                        contrast_ths=0.1,  # Very low - catch even low contrast
                        adjust_contrast=0.5,  # More aggressive adjustment
                        text_threshold=0.4,  # Lower threshold - catch more text
                        low_text=0.2,  # Detect very faint text
                        width_ths=0.5  # Allow wider text spacing
                    )
                    
                    # Format results
                    text_elements = []
                    max_y = 0
                    min_y = 9999
                    for bbox, text, confidence in ocr_results:
                        # Calculate center point
                        x_coords = [point[0] for point in bbox]
                        y_coords = [point[1] for point in bbox]
                        center_x = int(sum(x_coords) / 4)
                        center_y = int(sum(y_coords) / 4)
                        
                        # Track Y range
                        max_y = max(max_y, center_y)
                        min_y = min(min_y, center_y)
                        
                        text_elements.append({
                            "text": text,
                            "confidence": round(confidence, 3),
                            "center": (center_x, center_y),
                            "bbox": bbox
                        })
                    
                    result["text_elements"] = text_elements
                    result["text_count"] = len(text_elements)
                    logger.info(f"OCR extracted {len(text_elements)} text elements")
                    logger.info(f"OCR Y-range: {min_y} to {max_y} (screen height: {img.height})")
                    logger.info(f"OCR coverage: {(max_y / img.height * 100):.1f}% of screen height")
                
                except Exception as e:
                    logger.error(f"OCR processing failed: {e}")
                    result["ocr_error"] = str(e)
        else:
            result["ocr_available"] = False
        
        return result
    
    def get_complete_vision(self, window_title: Optional[str] = None) -> Dict:
        """
        Get most complete vision possible using all available methods
        
        Tries UI Automation first, falls back to screenshot + OCR
        
        Args:
            window_title: Window to inspect (None = active window)
        
        Returns:
            Dictionary with all available vision data
        """
        result = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "selected_monitor": self.get_selected_monitor_info(),
            "capabilities": self.capabilities
        }
        
        # Try UI Automation first (best method)
        if UI_AUTOMATION_AVAILABLE:
            ui_data = self.inspect_window(window_title)
            if "error" not in ui_data:
                result["ui_automation"] = ui_data
                logger.info("Complete vision acquired via UI Automation")
                return result
            else:
                result["ui_automation_error"] = ui_data.get("error")
        
        # Fallback to screenshot + OCR
        if SCREENSHOT_AVAILABLE:
            screenshot_data = self.capture_screen_with_ocr()
            if "error" not in screenshot_data:
                result["screenshot"] = screenshot_data
                logger.info("Complete vision acquired via Screenshot + OCR")
                return result
            else:
                result["screenshot_error"] = screenshot_data.get("error")
        
        # No method worked
        result["error"] = "No vision method available"
        logger.error("Failed to acquire vision - no methods available")
        return result
    
    def format_vision_for_agent(self, vision_data: Dict) -> str:
        """
        Format vision data into human-readable text for AI agent
        
        Args:
            vision_data: Vision data from get_complete_vision()
        
        Returns:
            Formatted string description
        """
        lines = []
        lines.append("=== SCREEN VISION ===\n")
        
        # Monitor info
        monitor_info = vision_data.get("selected_monitor", {})
        if monitor_info.get("mode") == "all_monitors":
            lines.append(f"Viewing: All {monitor_info['count']} monitors")
        elif "monitor" in monitor_info:
            lines.append(f"Viewing: Monitor {monitor_info['monitor']} ({monitor_info['width']}x{monitor_info['height']})")
        
        # UI Automation data (preferred)
        if "ui_automation" in vision_data:
            ui_data = vision_data["ui_automation"]
            lines.append(f"\nWindow: \"{ui_data['window_title']}\"")
            lines.append(f"Size: {ui_data['window_bounds']['width']}x{ui_data['window_bounds']['height']}")
            lines.append(f"Elements detected: {ui_data['element_count']}")
            
            # Clickable elements
            clickable = ui_data.get("clickable_elements", [])
            if clickable:
                lines.append(f"\nClickable elements ({len(clickable)}):")
                for elem in clickable[:15]:  # Limit to first 15
                    name = elem['name'] if elem['name'] else f"[{elem['type']}]"
                    lines.append(f"  • {elem['type']}: \"{name}\" at position {elem['center']}")
            
            # Editable elements
            editable = ui_data.get("editable_elements", [])
            if editable:
                lines.append(f"\nEditable fields ({len(editable)}):")
                for elem in editable[:10]:  # Limit to first 10
                    name = elem['name'] if elem['name'] else f"[{elem['type']}]"
                    value_text = f" = \"{elem['current_value']}\"" if elem['current_value'] else ""
                    lines.append(f"  • {elem['type']}: \"{name}\"{value_text} at {elem['center']}")
        
        # Screenshot + OCR data (fallback)
        elif "screenshot" in vision_data:
            screenshot = vision_data["screenshot"]
            lines.append(f"\nScreenshot: {screenshot['size']['width']}x{screenshot['size']['height']}")
            
            text_elements = screenshot.get("text_elements", [])
            if text_elements:
                lines.append(f"\nDetected text ({len(text_elements)} elements - ALL SHOWN):")
                for elem in text_elements:  # Show ALL elements, no limit
                    lines.append(f"  • \"{elem['text']}\" at {elem['center']} (conf: {elem['confidence']})")
        
        # Error case
        else:
            lines.append("\n❌ ERROR: No vision data available")
            if "error" in vision_data:
                lines.append(f"Reason: {vision_data['error']}")
        
        return "\n".join(lines)
    
    def get_capabilities_report(self) -> str:
        """Get human-readable report of vision capabilities"""
        lines = []
        lines.append("=== VISION CAPABILITIES ===")
        lines.append(f"UI Automation: {'OK - Available' if self.capabilities['ui_automation'] else 'ERROR - Not available'}")
        lines.append(f"Screenshot: {'OK - Available' if self.capabilities['screenshot'] else 'ERROR - Not available'}")
        lines.append(f"OCR: {'OK - Available' if self.capabilities['ocr'] else 'ERROR - Not available'}")
        lines.append(f"\nMonitors detected: {len(self.monitors)}")
        for monitor in self.monitors:
            primary = " (PRIMARY)" if monitor.is_primary else ""
            lines.append(f"  Monitor {monitor.index}: {monitor.width}x{monitor.height}{primary}")
        
        if self.selected_monitor:
            lines.append(f"\nCurrently viewing: Monitor {self.selected_monitor}")
        else:
            lines.append(f"\nCurrently viewing: All monitors")
        
        return "\n".join(lines)


# Legacy compatibility function (for existing code that calls add_vision_to_agent)
def add_vision_to_agent(agent, device="auto"):
    """
    Legacy compatibility: Add vision capabilities to agent
    
    Args:
        agent: GrokAgent instance
        device: Unused (kept for backwards compatibility)
    
    Returns:
        Agent with vision initialized
    """
    if not hasattr(agent, 'vision'):
        agent.vision = VisionIntegration()
        logger.info("Vision system added to agent")
    return agent


# Test function
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    print("Testing Vision Integration...")
    print("=" * 70)
    
    vision = VisionIntegration()
    print("\n" + vision.get_capabilities_report())
    
    print("\n" + "=" * 70)
    print("Getting complete vision of active window...")
    complete_vision = vision.get_complete_vision()
    formatted = vision.format_vision_for_agent(complete_vision)
    print("\n" + formatted)
    
    print("\n" + "=" * 70)
    print("OK - Vision integration test complete!")