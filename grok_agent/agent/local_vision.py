"""
Local Vision Model Module
CPU-ONLY VERSION - Reliable, no GPU issues
Uses Moondream2 - tiny vision model (1.6B parameters)
Analysis time: 10-30 seconds per image
"""

import torch
from PIL import Image
from transformers import AutoModelForCausalLM, AutoTokenizer
import time
from typing import Optional
import warnings

# Suppress the GenerationMixin warning
warnings.filterwarnings("ignore", message=".*GenerationMixin.*")

class LocalVisionModel:
    """
    Handles local vision model inference on CPU
    Reliable and works on any system
    """
    
    def __init__(self, model_path: Optional[str] = None, device: str = "cpu"):
        """
        Initialize vision model (CPU only)
        
        Args:
            model_path: Path to local model, or None to download
            device: Always uses "cpu" (ignores this parameter)
        """
        self.model = None
        self.tokenizer = None
        self.device = "cpu"  # Always CPU
        self.model_loaded = False
        
        print(f"Vision Model initialized (CPU mode)")
        print(f"Device: CPU")
        print(f"Note: Analysis takes 10-30 seconds per screen")
        print(f"Model will be loaded on first use (saves startup time)")
    
    def _setup_device(self, device: str) -> str:
        """Always returns CPU"""
        return "cpu"
    
    def load_model(self, model_name: str = "vikhyatk/moondream2", revision: str = "2024-08-26"):
        """
        Load vision model to CPU
        
        Args:
            model_name: HuggingFace model ID
            revision: Model version
        """
        if self.model_loaded:
            print("Model already loaded")
            return
        
        print(f"Loading vision model: {model_name}")
        print("Loading to CPU (avoiding GPU memory issues)...")
        print("This may take 30-60 seconds on first run...")
        print("(Model will be cached for future use)")
        
        start_time = time.time()
        
        try:
            # Load model to CPU with minimal memory usage
            print("Loading model to CPU...")
            self.model = AutoModelForCausalLM.from_pretrained(
                model_name,
                revision=revision,
                trust_remote_code=True,
                torch_dtype=torch.float32,
                device_map="cpu",
                low_cpu_mem_usage=True
            )
            
            # Load tokenizer
            print("Loading tokenizer...")
            self.tokenizer = AutoTokenizer.from_pretrained(
                model_name,
                revision=revision,
                trust_remote_code=True
            )
            
            print("✓ Model loaded to CPU")
            
            self.model.eval()
            self.model_loaded = True
            
            elapsed = time.time() - start_time
            print(f"✓ Model loaded in {elapsed:.1f} seconds")
            print("✓ Ready for screen analysis (10-30 sec per image)")
            
        except Exception as e:
            print(f"✗ Error loading model: {e}")
            print("\nTroubleshooting:")
            print("1. Install required packages: pip install transformers torch pillow einops")
            print("2. First run will download ~3.5GB model")
            print("3. Ensure you have 5GB+ free disk space")
            raise
    
    def describe_screen(self, image: Image.Image, prompt: Optional[str] = None) -> str:
        """
        Generate description of screen image
        
        Args:
            image: PIL Image of screen
            prompt: Custom prompt, or None for default
        
        Returns: Text description of screen
        """
        # Lazy load model on first use
        if not self.model_loaded:
            self.load_model()
        
        # Default prompt for computer screen description
        if prompt is None:
            prompt = """Describe this computer screen in detail for someone controlling it remotely.

Focus on:
1. What application or window is open
2. Location of icons, buttons, and UI elements (use percentages like "Chrome icon at 15% from left, 20% from top")
3. Any visible text
4. What actions are available (clickable buttons, text fields, menus)
5. Current state (is something loading, selected, typed, etc.)

Be precise with locations using percentage coordinates."""
        
        print("Analyzing screen on CPU...")
        print("This will take 10-30 seconds...")
        start_time = time.time()
        
        try:
            # Encode image
            enc_image = self.model.encode_image(image)
            
            # Generate description
            description = self.model.answer_question(
                enc_image,
                prompt,
                self.tokenizer
            )
            
            elapsed = time.time() - start_time
            print(f"✓ Analysis complete in {elapsed:.1f} seconds")
            
            return description
            
        except Exception as e:
            print(f"✗ Error during inference: {e}")
            import traceback
            traceback.print_exc()
            return f"Error: Unable to analyze screen - {str(e)}"
    
    def describe_with_focus(self, image: Image.Image, focus_area: str) -> str:
        """
        Describe screen with focus on specific area or element
        
        Args:
            image: PIL Image of screen
            focus_area: What to focus on (e.g., "the text editor", "the top menu bar")
        
        Returns: Text description focused on specified area
        """
        prompt = f"""Describe this computer screen, focusing specifically on {focus_area}.

Provide:
1. Detailed description of {focus_area}
2. Exact location using percentage coordinates
3. State and available actions
4. Any relevant text or content"""
        
        return self.describe_screen(image, prompt=prompt)
    
    def get_model_info(self) -> dict:
        """Get information about loaded model"""
        return {
            "loaded": self.model_loaded,
            "device": self.device,
            "gpu_available": False,  # Always False in CPU mode
            "model_type": "Moondream2-1.6B (CPU)" if self.model_loaded else "Not loaded"
        }


def test_vision_model():
    """Test vision model with current screen"""
    print("Testing Vision Model (CPU Mode)...")
    print("=" * 70)
    
    # Import screen capture
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from agent.screen_capture import ScreenCapture
    
    # Initialize
    print("\n1. Initializing components...")
    sc = ScreenCapture()
    vision = LocalVisionModel(device="cpu")
    
    # Get model info
    print("\n2. Model information:")
    info = vision.get_model_info()
    for key, value in info.items():
        print(f"   {key}: {value}")
    
    # Capture screen
    print("\n3. Capturing current screen...")
    image = sc.capture()
    print(f"   Image size: {image.size}")
    
    # Save test image
    image.save("test_vision_input.png")
    print("   Saved as: test_vision_input.png")
    
    # Analyze screen
    print("\n4. Analyzing screen with vision model...")
    print("   (This will take 10-30 seconds on CPU)")
    description = vision.describe_screen(image)
    
    print("\n5. Vision model output:")
    print("   " + "=" * 66)
    print(f"   {description}")
    print("   " + "=" * 66)
    
    # Test focused description
    print("\n6. Testing focused description...")
    focused = vision.describe_with_focus(image, "any text editors or code windows")
    print(f"   {focused}")
    
    print("\n" + "=" * 70)
    print("✓ Vision model test complete!")
    print("\nNext steps:")
    print("1. Check test_vision_input.png to see what was analyzed")
    print("2. Vision model is now loaded and ready for use")
    print("3. Integrate with agent using vision_integration.py")


if __name__ == "__main__":
    test_vision_model()