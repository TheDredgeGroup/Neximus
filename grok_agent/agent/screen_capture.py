"""
Screen Capture Module with OCR
Captures screenshots, extracts text, provides coordinate utilities
THREAD-SAFE VERSION for GUI usage
"""

import mss
import mss.tools
from PIL import Image
import io
import time
from datetime import datetime
from typing import Tuple, Optional, List, Dict
import logging

logger = logging.getLogger(__name__)


class ScreenCapture:
    """
    Handles screen capture and OCR operations
    Thread-safe - creates new MSS instance per capture
    """
    
    def __init__(self):
        """Initialize screen capture"""
        # Get screen dimensions using a temporary MSS instance
        with mss.mss() as sct:
            monitor = sct.monitors[1]  # Primary monitor
            self.width = monitor['width']
            self.height = monitor['height']
        
        # OCR reader (lazy loaded)
        self.ocr_reader = None
        
        print(f"Screen capture initialized: {self.width}x{self.height}")
    
    def _init_ocr(self):
        """Lazy load OCR reader"""
        if self.ocr_reader is None:
            try:
                import easyocr
                print("Initializing OCR... (first run may download model ~50MB)")
                self.ocr_reader = easyocr.Reader(['en'], gpu=False, verbose=False)
                print("✓ OCR ready")
            except ImportError:
                logger.warning("easyocr not installed - OCR disabled")
                logger.warning("Install with: pip install easyocr")
                self.ocr_reader = False  # Mark as unavailable
            except Exception as e:
                logger.error(f"OCR initialization failed: {e}")
                self.ocr_reader = False
    
    def smart_resize_for_vision(self, image: Image.Image, target_width: int = 1920, 
                                target_height: int = 1080) -> Tuple[Image.Image, float]:
        """
        Intelligently resize image for vision analysis
        Only downscales if too large, preserves aspect ratio
        
        Args:
            image: PIL Image
            target_width: Target max width (default 1920)
            target_height: Target max height (default 1080)
        
        Returns: (resized_image, scale_factor)
        """
        width, height = image.size
        
        # Calculate if we need to scale
        if width <= target_width and height <= target_height:
            # Already small enough - no resize needed
            logger.info(f"Image {width}x{height} already optimal size")
            return image, 1.0
        
        # Calculate scale factor to fit within target
        scale = min(target_width / width, target_height / height)
        new_width = int(width * scale)
        new_height = int(height * scale)
        
        logger.info(f"Resizing {width}x{height} → {new_width}x{new_height} (scale: {scale:.2f})")
        
        # High-quality resize using LANCZOS
        resized = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        return resized, scale
    
    def enhance_for_vision(self, image: Image.Image) -> Image.Image:
        """
        Enhance image for better vision/OCR detection
        
        Args:
            image: PIL Image
        
        Returns: Enhanced PIL Image
        """
        try:
            from PIL import ImageEnhance
            
            # Increase sharpness (makes text crisper)
            sharpener = ImageEnhance.Sharpness(image)
            image = sharpener.enhance(1.5)  # 50% more sharp
            
            # Increase contrast (makes text stand out)
            contrast = ImageEnhance.Contrast(image)
            image = contrast.enhance(1.2)  # 20% more contrast
            
            logger.info("Image enhanced for vision analysis")
            
        except Exception as e:
            logger.warning(f"Enhancement failed: {e}")
        
        return image
    
    def capture(self) -> Image.Image:
        """
        Capture current screen
        Thread-safe - creates new MSS instance
        
        Returns: PIL Image of screen
        """
        start_time = time.time()
        
        # Create new MSS instance for this thread
        with mss.mss() as sct:
            # Capture primary monitor
            monitor = sct.monitors[1]
            screenshot = sct.grab(monitor)
            
            # Convert to PIL Image
            img = Image.frombytes('RGB', screenshot.size, screenshot.rgb)
        
        elapsed = int((time.time() - start_time) * 1000)
        print(f"Screenshot captured in {elapsed}ms")
        
        return img
    
    def extract_text_with_ocr(self, image: Image.Image) -> List[Dict]:
        """
        Extract text from image using OCR
        
        Args:
            image: PIL Image
        
        Returns: List of detected text elements with positions
                 [{'text': str, 'bbox': [[x1,y1], [x2,y2], [x3,y3], [x4,y4]], 
                   'confidence': float, 'center_px': (x, y), 'center_pct': (x%, y%)}]
        """
        self._init_ocr()
        
        if self.ocr_reader is False:
            logger.warning("OCR not available")
            return []
        
        try:
            print("Extracting text with OCR...")
            start_time = time.time()
            
            # Convert PIL Image to numpy array for EasyOCR
            import numpy as np
            image_np = np.array(image)
            
            # Run OCR
            results = self.ocr_reader.readtext(image_np)
            
            # Format results with pixel and percentage coordinates
            formatted_results = []
            for bbox, text, confidence in results:
                # Calculate center point
                x_coords = [point[0] for point in bbox]
                y_coords = [point[1] for point in bbox]
                center_x = int(sum(x_coords) / 4)
                center_y = int(sum(y_coords) / 4)
                
                # Convert to percentages
                center_x_pct = (center_x / self.width) * 100
                center_y_pct = (center_y / self.height) * 100
                
                formatted_results.append({
                    'text': text,
                    'bbox': bbox,
                    'confidence': confidence,
                    'center_px': (center_x, center_y),
                    'center_pct': (round(center_x_pct, 1), round(center_y_pct, 1))
                })
            
            elapsed = time.time() - start_time
            print(f"✓ OCR extracted {len(formatted_results)} text elements in {elapsed:.1f}s")
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"OCR extraction error: {e}")
            return []
    
    def capture_with_ocr(self) -> Tuple[Image.Image, List[Dict]]:
        """
        Capture screen and extract text in one call
        
        Returns: (PIL Image, OCR results)
        """
        img = self.capture()
        ocr_results = self.extract_text_with_ocr(img)
        return img, ocr_results
    
    def capture_with_grid(self, grid_size: int = 10) -> Tuple[Image.Image, dict]:
        """
        Capture screen with coordinate grid overlay
        
        Args:
            grid_size: Grid spacing in percentage (10 = 10% grid)
        
        Returns: (PIL Image with grid, grid info dict)
        """
        # Capture base image
        img = self.capture()
        
        # Create grid info
        grid_info = {
            'width': self.width,
            'height': self.height,
            'grid_size': grid_size,
            'grid_lines_x': list(range(0, 101, grid_size)),
            'grid_lines_y': list(range(0, 101, grid_size))
        }
        
        return img, grid_info
    
    def save_screenshot(self, filename: Optional[str] = None) -> str:
        """
        Capture and save screenshot
        
        Args:
            filename: Output filename, or None for auto-generated name
        
        Returns: Saved filename
        """
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"screenshot_{timestamp}.png"
        
        img = self.capture()
        img.save(filename)
        
        print(f"Screenshot saved: {filename}")
        return filename
    
    def percent_to_pixels(self, x_percent: float, y_percent: float) -> Tuple[int, int]:
        """
        Convert percentage coordinates to pixel coordinates
        
        Args:
            x_percent: X position as percentage (0-100)
            y_percent: Y position as percentage (0-100)
        
        Returns: (x_pixels, y_pixels)
        """
        x_pixels = int((x_percent / 100.0) * self.width)
        y_pixels = int((y_percent / 100.0) * self.height)
        
        return x_pixels, y_pixels
    
    def pixels_to_percent(self, x_pixels: int, y_pixels: int) -> Tuple[float, float]:
        """
        Convert pixel coordinates to percentage coordinates
        
        Args:
            x_pixels: X position in pixels
            y_pixels: Y position in pixels
        
        Returns: (x_percent, y_percent)
        """
        x_percent = (x_pixels / self.width) * 100.0
        y_percent = (y_pixels / self.height) * 100.0
        
        return x_percent, y_percent
    
    def format_ocr_results(self, ocr_results: List[Dict]) -> str:
        """
        Format OCR results as readable text
        
        Args:
            ocr_results: List of OCR detections
        
        Returns: Formatted string
        """
        if not ocr_results:
            return "No text detected"
        
        lines = []
        lines.append(f"=== DETECTED TEXT ({len(ocr_results)} elements) ===\n")
        
        for i, result in enumerate(ocr_results, 1):
            text = result['text']
            px = result['center_px']
            pct = result['center_pct']
            conf = result['confidence']
            
            lines.append(f"{i}. \"{text}\"")
            lines.append(f"   Position: {pct[0]}% from left, {pct[1]}% from top")
            lines.append(f"   Pixels: ({px[0]}, {px[1]})")
            lines.append(f"   Confidence: {conf:.2f}\n")
        
        return '\n'.join(lines)
    
    def get_screen_info(self) -> dict:
        """Get screen information"""
        return {
            'width': self.width,
            'height': self.height,
            'aspect_ratio': f"{self.width}:{self.height}",
            'ocr_available': self.ocr_reader is not False if self.ocr_reader is not None else 'Not initialized'
        }


def test_screen_capture():
    """Test screen capture functionality with OCR"""
    print("Testing Screen Capture with OCR...")
    print("=" * 70)
    
    # Initialize
    sc = ScreenCapture()
    
    # Show screen info
    print("\n1. Screen Information:")
    info = sc.get_screen_info()
    for key, value in info.items():
        print(f"   {key}: {value}")
    
    # Test capture
    print("\n2. Capturing screen...")
    img = sc.capture()
    print(f"   Captured image size: {img.size}")
    
    # Test OCR
    print("\n3. Testing OCR extraction...")
    ocr_results = sc.extract_text_with_ocr(img)
    if ocr_results:
        print(f"   Found {len(ocr_results)} text elements")
        formatted = sc.format_ocr_results(ocr_results[:5])  # Show first 5
        print("\n" + formatted)
    else:
        print("   No text detected or OCR unavailable")
    
    # Test combined capture
    print("\n4. Testing combined capture + OCR...")
    img2, ocr2 = sc.capture_with_ocr()
    print(f"   Captured {img2.size} with {len(ocr2)} text elements")
    
    # Test save
    print("\n5. Saving screenshot...")
    filename = sc.save_screenshot("test_capture_ocr.png")
    print(f"   Saved as: {filename}")
    
    print("\n" + "=" * 70)
    print("✓ Screen capture with OCR test complete!")


if __name__ == "__main__":
    test_screen_capture()