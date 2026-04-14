"""
Multi-Monitor Floating Input Widgets
Creates slide-out input boxes on each detected monitor
"""

import tkinter as tk
from tkinter import font as tkfont
import threading
import logging

logger = logging.getLogger(__name__)


class MonitorInputWidget:
    """
    Slide-out input widget for a single monitor
    0.5" x 0.5" collapsed, expands right with text
    """
    
    def __init__(self, monitor_info, monitor_index, on_message_callback, parent_gui):
        """
        Initialize widget for one monitor
        
        Args:
            monitor_info: Dict with 'left', 'top', 'width', 'height' in pixels
            monitor_index: Monitor number (0, 1, 2, etc.)
            on_message_callback: Function to call when message sent
            parent_gui: Reference to main GUI for syncing
        """
        self.monitor_info = monitor_info
        self.monitor_index = monitor_index
        self.on_message_callback = on_message_callback
        self.parent_gui = parent_gui
        
        # State
        self.is_expanded = False
        self.has_focus = False
        
        # Create window
        self.window = tk.Toplevel()
        self.window.title(f"Monitor {monitor_index + 1}")
        
        # Remove window decorations
        self.window.overrideredirect(True)
        
        # Always on top
        self.window.attributes('-topmost', True)
        
        # Calculate position (bottom left of this monitor)
        # 0.5 inches at 96 DPI = 48 pixels
        self.collapsed_size = 48
        self.tab_width = 8  # Small tab when hidden
        
        # Position at bottom left of monitor
        x_pos = monitor_info['left']
        y_pos = monitor_info['top'] + monitor_info['height'] - self.collapsed_size - 40  # 40px above taskbar
        
        self.window.geometry(f"{self.collapsed_size}x{self.collapsed_size}+{x_pos}+{y_pos}")
        
        # Create UI
        self._create_widgets()
        
        logger.info(f"Monitor input widget created for Monitor {monitor_index + 1}")
    
    def _create_widgets(self):
        """Create the widget UI"""
        
        # Main frame
        self.main_frame = tk.Frame(
            self.window,
            bg='#1e1e1e',
            relief=tk.RAISED,
            borderwidth=2
        )
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Tab (visible when collapsed)
        self.tab_label = tk.Label(
            self.main_frame,
            text=f"M{self.monitor_index + 1}",
            bg='#0066cc',
            fg='white',
            font=('Arial', 8, 'bold'),
            cursor='hand2'
        )
        self.tab_label.pack(fill=tk.BOTH, expand=True)
        self.tab_label.bind('<Button-1>', self._toggle_expand)
        
        # Text input (hidden initially)
        self.text_input = tk.Text(
            self.main_frame,
            bg='#2b2b2b',
            fg='white',
            font=('Arial', 10),
            insertbackground='white',
            wrap=tk.WORD,
            width=40,  # 40 characters
            height=1,  # Start with 1 line
            relief=tk.FLAT,
            padx=5,
            pady=5
        )
        
        # Bind events
        self.text_input.bind('<Return>', self._on_enter)
        self.text_input.bind('<Shift-Return>', lambda e: None)  # Allow newline
        self.text_input.bind('<KeyPress>', self._on_key_press)
        self.text_input.bind('<FocusIn>', self._on_focus_in)
        self.text_input.bind('<FocusOut>', self._on_focus_out)
    
    def _toggle_expand(self, event=None):
        """Toggle between collapsed and expanded states"""
        if self.is_expanded:
            self._collapse()
        else:
            self._expand()
    
    def _expand(self):
        """Expand the widget to show input"""
        if self.is_expanded:
            return
        
        self.is_expanded = True
        
        # Hide tab
        self.tab_label.pack_forget()
        
        # Show input
        self.text_input.pack(fill=tk.BOTH, expand=True)
        
        # Calculate expanded size
        # Width: 40 chars * ~8px per char = 320px + padding
        # Height: auto-expand based on content (start with 1 line)
        expanded_width = 340
        expanded_height = 40  # Start small, will grow
        
        # Update geometry
        x_pos = self.monitor_info['left']
        y_pos = self.monitor_info['top'] + self.monitor_info['height'] - expanded_height - 40
        
        self.window.geometry(f"{expanded_width}x{expanded_height}+{x_pos}+{y_pos}")
        
        # Focus input
        self.text_input.focus_set()
        
        logger.info(f"Monitor {self.monitor_index + 1} input expanded")
    
    def _collapse(self):
        """Collapse the widget to tab only"""
        if not self.is_expanded:
            return
        
        self.is_expanded = False
        
        # Clear and hide input
        self.text_input.delete(1.0, tk.END)
        self.text_input.pack_forget()
        
        # Show tab
        self.tab_label.pack(fill=tk.BOTH, expand=True)
        
        # Reset geometry
        x_pos = self.monitor_info['left']
        y_pos = self.monitor_info['top'] + self.monitor_info['height'] - self.collapsed_size - 40
        
        self.window.geometry(f"{self.collapsed_size}x{self.collapsed_size}+{x_pos}+{y_pos}")
        
        logger.info(f"Monitor {self.monitor_index + 1} input collapsed")
    
    def _on_key_press(self, event):
        """Handle key press - auto-expand height"""
        # Expand height based on content
        self.window.after(10, self._adjust_height)
    
    def _adjust_height(self):
        """Adjust window height based on text content"""
        if not self.is_expanded:
            return
        
        # Get number of lines
        num_lines = int(self.text_input.index('end-1c').split('.')[0])
        
        # Cap at 10 lines
        num_lines = min(num_lines, 10)
        
        # Calculate height (roughly 20px per line + padding)
        new_height = max(40, num_lines * 22 + 10)
        
        # Update geometry
        x_pos = self.monitor_info['left']
        y_pos = self.monitor_info['top'] + self.monitor_info['height'] - new_height - 40
        
        self.window.geometry(f"340x{new_height}+{x_pos}+{y_pos}")
    
    def _on_enter(self, event):
        """Handle Enter key - send message"""
        # Don't send on Shift+Enter
        if event.state & 0x1:
            return
        
        # Get message
        message = self.text_input.get(1.0, tk.END).strip()
        
        if not message:
            return 'break'
        
        # Send message with monitor info
        self.on_message_callback(message, self.monitor_index)
        
        # Clear input
        self.clear()
        
        # Collapse after sending
        self._collapse()
        
        return 'break'  # Prevent newline
    
    def _on_focus_in(self, event):
        """Handle focus in - mark this monitor as active"""
        self.has_focus = True
        self.main_frame.config(bg='#0066cc', borderwidth=3)
        logger.info(f"Monitor {self.monitor_index + 1} input has focus")
    
    def _on_focus_out(self, event):
        """Handle focus out"""
        self.has_focus = False
        self.main_frame.config(bg='#1e1e1e', borderwidth=2)
    
    def clear(self):
        """Clear the text input"""
        self.text_input.delete(1.0, tk.END)
    
    def destroy(self):
        """Destroy the widget"""
        try:
            self.window.destroy()
        except:
            pass


class MultiMonitorInput:
    """
    Manages input widgets across multiple monitors
    """
    
    def __init__(self, agent, voice_interface, message_display_callback):
        """
        Initialize multi-monitor input system
        
        Args:
            agent: GrokAgent instance
            voice_interface: VoiceInterface instance
            message_display_callback: Function to display messages in main GUI
        """
        self.agent = agent
        self.voice = voice_interface
        self.message_display_callback = message_display_callback
        
        self.widgets = []
        self.monitors = []
        
        # Detect monitors
        self._detect_monitors()
        
        # Create widgets
        self._create_widgets()
    
    def _detect_monitors(self):
        """Detect all connected monitors"""
        try:
            import screeninfo
            monitors = screeninfo.get_monitors()
            
            for i, monitor in enumerate(monitors):
                mon_info = {
                    'left': monitor.x,
                    'top': monitor.y,
                    'width': monitor.width,
                    'height': monitor.height,
                    'name': monitor.name
                }
                self.monitors.append(mon_info)
                logger.info(f"Detected Monitor {i + 1}: {monitor.width}x{monitor.height} at ({monitor.x}, {monitor.y})")
            
        except ImportError:
            logger.warning("screeninfo not installed - using single monitor")
            logger.warning("Install with: pip install screeninfo")
            # Fallback to primary monitor
            import tkinter as tk
            root = tk.Tk()
            root.withdraw()
            self.monitors.append({
                'left': 0,
                'top': 0,
                'width': root.winfo_screenwidth(),
                'height': root.winfo_screenheight(),
                'name': 'Primary'
            })
        except Exception as e:
            logger.error(f"Monitor detection error: {e}")
            # Fallback
            import tkinter as tk
            root = tk.Tk()
            root.withdraw()
            self.monitors.append({
                'left': 0,
                'top': 0,
                'width': root.winfo_screenwidth(),
                'height': root.winfo_screenheight(),
                'name': 'Primary'
            })
    
    def _create_widgets(self):
        """Create input widget for each monitor"""
        for i, monitor in enumerate(self.monitors):
            widget = MonitorInputWidget(
                monitor_info=monitor,
                monitor_index=i,
                on_message_callback=self._on_message_sent,
                parent_gui=self
            )
            self.widgets.append(widget)
        
        logger.info(f"Created {len(self.widgets)} monitor input widgets")
    
    def _on_message_sent(self, message, monitor_index):
        """
        Handle message sent from a widget
        
        Args:
            message: Message text
            monitor_index: Which monitor sent it
        """
        # Display user message
        self.message_display_callback("You", message, "#00aaff")
        
        # Process in thread
        threading.Thread(
            target=self._process_message,
            args=(message, monitor_index),
            daemon=True
        ).start()
    
    def _process_message(self, message, monitor_index):
        """
        Process message from specific monitor
        
        Args:
            message: Message text
            monitor_index: Which monitor the message came from
        """
        try:
            # Automatically select the monitor where the message was sent
            if hasattr(self.agent, 'vision'):
                self.agent.vision.select_monitor(monitor_index + 1)  # Vision uses 1-based indexing
                logger.info(f"Vision focused on Monitor {monitor_index + 1}")
            
            # Check if user is explicitly asking about the screen
            message_lower = message.lower()
            # Trigger words include spelled numbers: "two" -> "2", "three" -> "3", etc.
            trigger_phrases = ['what', 'see', 'screen', 'on this', 'monitor', 'display', 'look', 'show', 'view', 'whats', "what's", 'to',
                             'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten',
                             '1', '2', '3', '4', '5', '6', '7', '8', '9', '10']
            if any(phrase in message_lower for phrase in trigger_phrases):
                # Get vision data and add to context
                if hasattr(self.agent, 'vision'):
                    self.message_display_callback("System", 
                        f"👁️  Analyzing Monitor {monitor_index + 1}...", 
                        "#ffaa00")
                    
                    vision_description = self.agent.get_screen_vision()
                    
                    # Enhance the message with vision context
                    enhanced_message = f"{message}\n\n[SCREEN CONTEXT - Monitor {monitor_index + 1}]\n{vision_description}"
                    
                    response = self.agent.chat(enhanced_message)
                else:
                    # No vision available
                    response = self.agent.chat(message)
            else:
                # Normal message without explicit screen request
                response = self.agent.chat(message)
            
            self.message_display_callback("Agent", response, "#ffffff")
            
            if self.voice.voice_output_enabled:
                self.voice.speak(response)
                    
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            self.message_display_callback("Error", str(e), "#ff0000")
    
    def clear_all(self):
        """Clear all input widgets"""
        for widget in self.widgets:
            widget.clear()
    
    def destroy_all(self):
        """Destroy all widgets"""
        for widget in self.widgets:
            widget.destroy()
        self.widgets.clear()