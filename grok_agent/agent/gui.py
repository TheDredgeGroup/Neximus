"""
GUI Module for Grok Agent
Provides graphical interface with drag-drop document support, TTS toggle,
PLC Config and Settings windows
"""

import tkinter as tk
from tkinter import scrolledtext, messagebox
from tkinterdnd2 import DND_FILES, TkinterDnD
import threading
import queue
import logging

logger = logging.getLogger(__name__)


class AgentGUI:
    """GUI for the Grok Agent"""
    
    def __init__(self, agent, voice_interface, chore_db=None, plc_comm=None, 
                 scheduler=None, reminder_parser=None, plc_parser=None, introspection_parser=None):
        """
        Initialize GUI
        
        Args:
            agent: GrokAgent instance
            voice_interface: VoiceInterface instance
            chore_db: ChoreDatabase instance (optional, for PLC/Settings windows)
            plc_comm: PLCCommunicator instance (optional, for PLC window)
            scheduler: SchedulerService instance (optional)
            reminder_parser: ReminderParser instance (optional, for natural language reminders)
            plc_parser: PLCParser instance (optional, for natural language PLC commands)
        """
        self.agent = agent
        self.voice = voice_interface
        self.chore_db = chore_db
        self.plc_comm = plc_comm
        self.scheduler = scheduler
        self.reminder_parser = reminder_parser
        self.plc_parser = plc_parser
        self.introspection_parser = introspection_parser
        
        self.voice_mode = False
        self.running = True
        
        # Track open windows
        self.plc_config_window = None
        self.settings_window = None
        
        # Multi-monitor floating input widgets
        self.mm_widgets = None
        
        # Code mode - Notepad writer
        self.code_mode_enabled = False
        self.code_write_stop_event = threading.Event()
        self.code_writing_active = False
        
        # Collaboration and browser lock state
        self.collaborate_enabled = True
        self.browser_locked = False
        self.ai_enabled = False
        self.agent.ai_enabled = False  # Sync agent to GUI starting state — button shows OFF at launch
        
        # Message queue for thread-safe GUI updates
        self.message_queue = queue.Queue()
        
        # Create main window
        self.root = TkinterDnD.Tk()
        self.root.title("Grok Agent - Phase 3")
        self.root.update_idletasks()
        screen_width = self.root.winfo_screenwidth()
        win_width = screen_width - 100
        self.root.geometry(f"{win_width}x750")
        self.root.minsize(800, 600)
        self.root.configure(bg='#2d2d2d')
        
        # Setup GUI components
        self._create_widgets()
        
        # Start message queue processor
        self.root.after(100, self._process_queue)
        
        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
        
        # Welcome message
        self.add_message("System", "Grok Agent Ready! Type or use voice mode.", "#00ff00")
        self.add_message("System", f"TTS Mode: {self.voice.get_tts_mode().upper()} (offline)" if self.voice.get_tts_mode() == 'piper' else f"TTS Mode: {self.voice.get_tts_mode().upper()} (online)", "#00aaff")
        
        # Set initial model button state to match config
        starting_model = self.agent.grok.model
        if starting_model == "grok-4":
            self.model_btn.config(text="🧠 Reasoning", bg='#4a90b8')
            self.add_message("System", f"Model: {starting_model} (Reasoning)", "#cc88ff")
        else:
            self.model_btn.config(text="⚡ Fast Mode", bg='#00aa00')
            self.add_message("System", f"Model: {starting_model} (Fast)", "#00ff00")
        
        if self.scheduler and self.scheduler.running:
            self.add_message("System", "Scheduler is running.", "#00ff00")
            # Set up reminder callback to inject into chat
            self.scheduler.on_reminder_triggered = self._on_reminder_triggered

        # Auto-enable collaboration mode on startup
        try:
            import requests as _req
            _req.post("http://localhost:5000/collaborate", json={"enabled": True}, timeout=2)
            self.add_message("System", "Collaboration: ON", "#0066cc")
        except Exception:
            pass  # Web server may not be ready yet — button state is already set
    
    def _create_widgets(self):
        """Create all GUI widgets"""
        
        # ===== TOP CONTROL PANEL =====
        control_frame = tk.Frame(self.root, bg='#1a1a1a', height=80)
        control_frame.pack(fill=tk.X, padx=5, pady=5)
        control_frame.pack_propagate(False)
        
        # Voice button
        self.voice_btn = tk.Button(
            control_frame,
            text="🎤 Voice: OFF",
            command=self._toggle_voice,
            bg='#333333',
            fg='white',
            font=('Arial', 10, 'bold'),
            width=12,
            height=2
        )
        self.voice_btn.pack(side=tk.LEFT, padx=3, pady=10)
        
        # Mute button
        self.mute_btn = tk.Button(
            control_frame,
            text="🔊 Audio: ON",
            command=self._toggle_mute,
            bg='#333333',
            fg='white',
            font=('Arial', 10, 'bold'),
            width=12,
            height=2
        )
        self.mute_btn.pack(side=tk.LEFT, padx=3, pady=10)
        
        # TTS toggle button
        tts_mode = self.voice.get_tts_mode().upper()
        self.tts_btn = tk.Button(
            control_frame,
            text=f"🎙️ TTS: {tts_mode}",
            command=self._toggle_tts,
            bg='#4a90b8',
            fg='white',
            font=('Arial', 10, 'bold'),
            width=12,
            height=2
        )
        self.tts_btn.pack(side=tk.LEFT, padx=3, pady=10)
        
        # Clear chat button
        clear_btn = tk.Button(
            control_frame,
            text="🗑️ Clear",
            command=self._clear_chat,
            bg='#333333',
            fg='white',
            font=('Arial', 10, 'bold'),
            width=10,
            height=2
        )
        clear_btn.pack(side=tk.LEFT, padx=3, pady=10)
        
        # New conversation button
        new_btn = tk.Button(
            control_frame,
            text="📝 New Chat",
            command=self._new_conversation,
            bg='#333333',
            fg='white',
            font=('Arial', 10, 'bold'),
            width=10,
            height=2
        )
        new_btn.pack(side=tk.LEFT, padx=3, pady=10)
        
        # Multi-Monitor Widgets button
        mm_btn = tk.Button(
            control_frame,
            text="📺 Multi-Mon",
            command=self._toggle_multi_monitor_widgets,
            bg='#333333',
            fg='white',
            font=('Arial', 10, 'bold'),
            width=11,
            height=2
        )
        mm_btn.pack(side=tk.LEFT, padx=3, pady=10)
        
        # Separator
        sep = tk.Frame(control_frame, bg='#4a90b8', width=2)
        sep.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=15)
        
        # Code mode button
        self.code_btn = tk.Button(
            control_frame,
            text="💻 Code: OFF",
            command=self._toggle_code_mode,
            bg='#333333',
            fg='white',
            font=('Arial', 10, 'bold'),
            width=11,
            height=2
        )
        self.code_btn.pack(side=tk.LEFT, padx=3, pady=10)
        
        # PLC Config button
        plc_btn = tk.Button(
            control_frame,
            text="📡 PLC Config",
            command=self._open_plc_config,
            bg='#006600',
            fg='white',
            font=('Arial', 10, 'bold'),
            width=12,
            height=2
        )
        plc_btn.pack(side=tk.LEFT, padx=3, pady=10)
        
        # Settings button
        settings_btn = tk.Button(
            control_frame,
            text="⚙️ Settings",
            command=self._open_settings,
            bg='#4a90b8',
            fg='white',
            font=('Arial', 10, 'bold'),
            width=10,
            height=2
        )
        settings_btn.pack(side=tk.LEFT, padx=3, pady=10)
        
        # Separator
        sep2 = tk.Frame(control_frame, bg='#4a90b8', width=2)
        sep2.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=15)
        
        # Browser lock button
        self.browser_lock_btn = tk.Button(
            control_frame,
            text="🌐 Browser: ON",
            command=self._toggle_browser_lock,
            bg='#006600',
            fg='white',
            font=('Arial', 10, 'bold'),
            width=13,
            height=2
        )
        self.browser_lock_btn.pack(side=tk.LEFT, padx=3, pady=10)
        
        # Collaborate button
        self.collaborate_btn = tk.Button(
            control_frame,
            text="🤝 Collab: ON",
            command=self._toggle_collaborate,
            bg='#4a90b8',
            fg='white',
            font=('Arial', 10, 'bold'),
            width=13,
            height=2
        )
        self.collaborate_btn.pack(side=tk.LEFT, padx=3, pady=10)
        
        # Model toggle button (Fast vs Reasoning)
        self.model_btn = tk.Button(
            control_frame,
            text="⚡ Fast Mode",
            command=self._toggle_model,
            bg='#00aa00',
            fg='white',
            font=('Arial', 10, 'bold'),
            width=13,
            height=2
        )
        self.model_btn.pack(side=tk.LEFT, padx=3, pady=10)
        
        # AI toggle button
        self.ai_btn = tk.Button(
            control_frame,
            text="🤖 AI: OFF",
            command=self._toggle_ai,
            bg='#aa0000',
            fg='white',
            font=('Arial', 10, 'bold'),
            width=10,
            height=2
        )
        self.ai_btn.pack(side=tk.LEFT, padx=3, pady=10)
        
        # ===== MAIN CONTENT AREA =====
        content_frame = tk.Frame(self.root, bg='#2d2d2d')
        content_frame.pack(fill=tk.BOTH, expand=True, padx=5)
        
        # Left side: Chat display
        left_frame = tk.Frame(content_frame, bg='#2d2d2d')
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Chat display label
        chat_label = tk.Label(
            left_frame,
            text="💬 Chat",
            bg='#2d2d2d',
            fg='white',
            font=('Arial', 12, 'bold')
        )
        chat_label.pack(anchor=tk.W, pady=(0, 5))
        
        # Chat display (scrollable text with copy support)
        self.chat_display = scrolledtext.ScrolledText(
            left_frame,
            wrap=tk.WORD,
            bg='#1a1a1a',
            fg='#ffffff',
            font=('Consolas', 10),
            insertbackground='white',
            selectbackground='#4a90b8',
            selectforeground='white',
            state=tk.DISABLED
        )
        self.chat_display.pack(fill=tk.BOTH, expand=True)
        
        # Right side: Drop zones
        right_frame = tk.Frame(content_frame, bg='#2d2d2d', width=250)
        right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
        right_frame.pack_propagate(False)
        
        # Drop zone 1: Add to database
        db_label = tk.Label(
            right_frame,
            text="📄 Add to Database",
            bg='#2d2d2d',
            fg='white',
            font=('Arial', 10, 'bold')
        )
        db_label.pack(pady=(0, 5))
        
        self.db_drop_zone = tk.Label(
            right_frame,
            text="Drop .txt file here\nto add to\nDATABASE",
            bg='#333333',
            fg='#b0c8d8',
            font=('Arial', 10),
            relief=tk.RAISED,
            borderwidth=2,
            height=6
        )
        self.db_drop_zone.pack(fill=tk.X, pady=(0, 20))
        
        # Register drop zone 1
        self.db_drop_zone.drop_target_register(DND_FILES)
        self.db_drop_zone.dnd_bind('<<Drop>>', self._on_drop_database)
        
        # Drop zone 2: Send as message
        chat_label2 = tk.Label(
            right_frame,
            text="💬 Send as Message",
            bg='#2d2d2d',
            fg='white',
            font=('Arial', 10, 'bold')
        )
        chat_label2.pack(pady=(0, 5))
        
        self.chat_drop_zone = tk.Label(
            right_frame,
            text="Drop .txt file here\nto send as\nMESSAGE",
            bg='#333333',
            fg='#b0c8d8',
            font=('Arial', 10),
            relief=tk.RAISED,
            borderwidth=2,
            height=6
        )
        self.chat_drop_zone.pack(fill=tk.X)
        
        # Register drop zone 2
        self.chat_drop_zone.drop_target_register(DND_FILES)
        self.chat_drop_zone.dnd_bind('<<Drop>>', self._on_drop_chat)
        
        # ===== QUICK REMINDER SECTION =====
        reminder_frame = tk.LabelFrame(
            right_frame,
            text="⏰ Quick Reminder",
            bg='#1a1a1a',
            fg='white',
            font=('Arial', 10, 'bold')
        )
        reminder_frame.pack(fill=tk.X, pady=(20, 0))
        
        tk.Label(
            reminder_frame,
            text="Say 'remind me' in chat\nor use keywords like:",
            bg='#1a1a1a',
            fg='#b0c8d8',
            font=('Arial', 9),
            justify=tk.LEFT
        ).pack(padx=10, pady=5, anchor='w')
        
        examples = [
            "• remind me in 5 minutes",
            "• remind me at 3pm",
            "• remind me every day at 8am",
            "• remind me on Monday at 9am"
        ]
        for ex in examples:
            tk.Label(
                reminder_frame,
                text=ex,
                bg='#1a1a1a',
                fg='#00aaff',
                font=('Consolas', 8),
                anchor='w'
            ).pack(padx=10, anchor='w')
        
        tk.Label(reminder_frame, text="", bg='#1a1a1a').pack(pady=3)
        
        # ===== BOTTOM INPUT AREA =====
        input_frame = tk.Frame(self.root, bg='#1a1a1a')
        input_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Text input
        self.text_input = tk.Text(
            input_frame,
            height=3,
            bg='#2d2d2d',
            fg='white',
            font=('Arial', 10),
            insertbackground='white',
            wrap=tk.WORD
        )
        self.text_input.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        self.text_input.bind('<Return>', self._on_enter_key)
        self.text_input.bind('<Shift-Return>', lambda e: None)  # Allow Shift+Enter for newline
        
        # Send button
        send_btn = tk.Button(
            input_frame,
            text="Send",
            command=self._send_message,
            bg='#4a90b8',
            fg='white',
            font=('Arial', 11, 'bold'),
            width=10,
            height=2
        )
        send_btn.pack(side=tk.RIGHT)
    
    def _on_enter_key(self, event):
        """Handle Enter key - send message"""
        if not event.state & 0x1:  # If Shift is not held
            self._send_message()
            return 'break'  # Prevent newline
    
    def _toggle_voice(self):
        """Toggle voice mode"""
        self.voice_mode = not self.voice_mode
        
        if self.voice_mode:
            self.voice_btn.config(text="🎤 Voice: ON", bg='#00aa00')
            self.add_message("System", "Voice mode activated. Listening...", "#00ff00")
            # Start voice listening in thread
            threading.Thread(target=self._voice_loop, daemon=True).start()
        else:
            self.voice_btn.config(text="🎤 Voice: OFF", bg='#333333')
            self.add_message("System", "Voice mode deactivated.", "#ffaa00")
    
    def _toggle_mute(self):
        """Toggle audio output"""
        if self.voice.voice_output_enabled:
            self.voice.disable_voice_output()
            self.mute_btn.config(text="🔇 Audio: OFF", bg='#aa0000')
        else:
            self.voice.enable_voice_output()
            self.mute_btn.config(text="🔊 Audio: ON", bg='#333333')
    
    def _toggle_tts(self):
        """Toggle TTS mode between Piper and gTTS"""
        # Toggle the mode
        self.voice.toggle_tts_mode()
        
        # Update button appearance
        tts_mode = self.voice.get_tts_mode().upper()
        
        if tts_mode == 'PIPER':
            # Offline mode - Blue
            self.tts_btn.config(
                text=f"🎙️ TTS: {tts_mode}",
                bg='#4a90b8'
            )
            self.add_message("System", "TTS Mode: PIPER (offline)", "#00aaff")
        else:
            # Online mode - Green
            self.tts_btn.config(
                text=f"🎙️ TTS: {tts_mode}",
                bg='#00aa00'
            )
            self.add_message("System", "TTS Mode: GTTS (online)", "#00ff00")
        
        # Test the new TTS mode with a short message
        self.voice.speak("TTS mode changed")
    
    def _toggle_model(self):
        """Toggle between fast model (grok-3-fast) and reasoning model (grok-4)"""
        current_model = self.agent.grok.model
        
        if current_model == "grok-3-fast":
            # Switch to reasoning model
            self.agent.grok.model = "grok-4"
            self.model_btn.config(text="🧠 Reasoning", bg='#4a90b8')
            self.add_message("System", "Model: grok-4 (Reasoning) — best for projects & complex tasks", "#cc88ff")
        else:
            # Switch to fast model
            self.agent.grok.model = "grok-3-fast"
            self.model_btn.config(text="⚡ Fast Mode", bg='#00aa00')
            self.add_message("System", "Model: grok-3-fast — best for everyday conversation", "#00ff00")
    
    def _clear_chat(self):
        """Clear chat display"""
        self.chat_display.config(state=tk.NORMAL)
        self.chat_display.delete(1.0, tk.END)
        self.chat_display.config(state=tk.DISABLED)
        self.add_message("System", "Chat cleared.", "#ffaa00")
    
    def _new_conversation(self):
        """Start new conversation"""
        self.agent.start_conversation()
        self.add_message("System", "Started new conversation.", "#00ff00")
    
    def _toggle_multi_monitor_widgets(self):
        """Toggle multi-monitor floating input widgets"""
        if self.mm_widgets is None:
            # Create widgets
            try:
                from agent.multi_monitor_input import MultiMonitorInput
                self.mm_widgets = MultiMonitorInput(
                    agent=self.agent,
                    voice_interface=self.voice,
                    message_display_callback=self.add_message
                )
                self.add_message("System", 
                    f"Multi-monitor input active ({len(self.mm_widgets.monitors)} monitors detected)", 
                    "#00ff00")
            except Exception as e:
                self.add_message("Error", f"Failed to create multi-monitor widgets: {e}", "#ff0000")
                logger.error(f"Multi-monitor error: {e}")
                import traceback
                traceback.print_exc()
        else:
            # Destroy widgets
            self.mm_widgets.destroy_all()
            self.mm_widgets = None
            self.add_message("System", "Multi-monitor input closed", "#888888")
    
    def _open_plc_config(self):
        """Open PLC Configuration window"""
        if not self.chore_db or not self.plc_comm:
            messagebox.showwarning("Not Available", "PLC configuration not initialized")
            return
        
        # Don't open multiple instances
        if self.plc_config_window:
            try:
                self.plc_config_window.window.lift()
                self.plc_config_window.window.focus_force()
                return
            except:
                pass  # Window was closed, create new one
        
        try:
            from agent.plc_config_window import PLCConfigWindow
            self.plc_config_window = PLCConfigWindow(
                self.chore_db, 
                self.plc_comm,
                on_close_callback=lambda: setattr(self, 'plc_config_window', None)
            )
            self.add_message("System", "Opened PLC Configuration window.", "#00aaff")
        except Exception as e:
            logger.error(f"Error opening PLC config: {e}")
            messagebox.showerror("Error", f"Failed to open PLC Config: {e}")
    
    def _open_settings(self):
        """Open Settings window"""
        if not self.chore_db:
            messagebox.showwarning("Not Available", "Settings not initialized")
            return
        
        # Don't open multiple instances
        if self.settings_window:
            try:
                self.settings_window.window.lift()
                self.settings_window.window.focus_force()
                return
            except:
                pass  # Window was closed, create new one
        
        try:
            from agent.settings_window import SettingsWindow
            self.settings_window = SettingsWindow(
                self.chore_db,
                on_close_callback=lambda: setattr(self, 'settings_window', None)
            )
            self.add_message("System", "Opened Settings window.", "#00aaff")
        except Exception as e:
            logger.error(f"Error opening settings: {e}")
            messagebox.showerror("Error", f"Failed to open Settings: {e}")
    
    def _send_message(self):
        """Send text message to agent"""
        message = self.text_input.get(1.0, tk.END).strip()
        
        if not message:
            return
        
        # Clear input
        self.text_input.delete(1.0, tk.END)
        
        # Process in thread
        threading.Thread(target=self._process_message, args=(message,), daemon=True).start()
    
    def _process_message(self, message):
        """Process message with agent (runs in thread)"""
        try:
            # Display user message
            self.message_queue.put(("You", message, "#00aaff"))
            
            # Check for reminder request first
            
            # VISION: Check for vision commands first
            cmd = message.lower().strip()
            
            if cmd == 'see':
                # Check if agent has vision capability
                if not hasattr(self.agent, 'see_screen'):
                    self.message_queue.put(("Error", "Vision not enabled", "#ff0000"))
                    return
                    
                # Capture and describe screen with vision
                self.message_queue.put(("System", "👁️  Capturing screen... (10-30 seconds)", "#ffaa00"))
                description = self.agent.see_screen(save_screenshot=True)
                
                # Format as memory document with timestamp
                from datetime import datetime
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                message_to_agent = f"[SCREEN CAPTURE - {timestamp}]\n\n{description}"
                
                # Send to agent for analysis and storage in memory
                self.message_queue.put(("System", "🧠 Sending to Grok for analysis...", "#ffaa00"))
                response = self.agent.chat(message_to_agent)
                
                # Display Grok's response
                self.message_queue.put(("Agent", response, "#ffffff"))
                if self.voice.voice_output_enabled:
                    self.voice.speak(response)
                return
            
            if cmd == 'screenshot':
                # Check if agent has vision capability
                if not hasattr(self.agent, 'screen_capture'):
                    self.message_queue.put(("Error", "Vision not enabled", "#ff0000"))
                    return
                    
                # Save screenshot only
                from datetime import datetime
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"screen_{timestamp}.png"
                self.agent.screen_capture.save_screenshot(filename)
                response = f"📸 Screenshot saved: {filename}"
                self.message_queue.put(("System", response, "#00ff00"))
                if self.voice.voice_output_enabled:
                    self.voice.speak("Screenshot saved")
                return
            
            # Check for reminder request first
            # Check for introspection command FIRST (before action_executor can intercept)
            if self.introspection_parser and self.introspection_parser.is_introspection_command(message):
                was_introspection, response = self.introspection_parser.process_message(message, self.agent)
                if was_introspection and response:
                    # Display agent response
                    self.message_queue.put(("Agent", response, "#ffffff"))
                    
                    # Speak response if enabled
                    if self.voice.voice_output_enabled:
                        self.voice.speak(response)
                    return
            
            if self.reminder_parser and self.reminder_parser.is_reminder_request(message):
                was_reminder, response = self.reminder_parser.process_message(message, self.agent)
                if was_reminder and response:
                    # Display agent response
                    self.message_queue.put(("Agent", response, "#ffffff"))
                    
                    # Speak response if enabled
                    if self.voice.voice_output_enabled:
                        self.voice.speak(response)
                    return
            
            # Check for PLC command
            if self.plc_parser and self.plc_parser.is_plc_request(message):
                was_plc, response = self.plc_parser.process_message(message, self.agent)
                if was_plc and response:
                    # Display agent response
                    self.message_queue.put(("Agent", response, "#ffffff"))
                    
                    # Speak response if enabled
                    if self.voice.voice_output_enabled:
                        self.voice.speak(response)
                    return
            
            # Gate Grok: if AI is off, only local commands (introspection, PLC, reminders) run
            if not self.agent.ai_enabled:
                self.message_queue.put(("System", "AI is off. Local commands still active.", "#ff4444"))
                return
            
            # Normal message processing
            response = self.agent.chat(message)
            
            # Display agent response
            self.message_queue.put(("Agent", response, "#ffffff"))
            
            # Code mode: check for code blocks and write to Notepad
            if self.code_mode_enabled and not self.code_writing_active:
                code_blocks = self._extract_code_blocks(response)
                if code_blocks:
                    self.code_write_stop_event.clear()
                    threading.Thread(
                        target=self._notepad_writer_thread,
                        args=(code_blocks,),
                        daemon=True
                    ).start()
            
            # Speak response if enabled
            if self.voice.voice_output_enabled:
                self.voice.speak(response)
            
            # Send to peer if collaboration enabled
            self._send_to_peer(response)
                
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            self.message_queue.put(("Error", str(e), "#ff0000"))
    
    def _on_reminder_triggered(self, reminder: dict):
        """Handle reminder triggered by scheduler - inject into chat flow"""
        try:
            message = reminder.get('message', 'You have a reminder')
            
            # Display reminder in chat
            self.message_queue.put(("⏰ Reminder", message, "#ffaa00"))
            
            # Process through agent in a thread so Grok responds
            threading.Thread(
                target=self._process_reminder_with_agent, 
                args=(message,), 
                daemon=True
            ).start()
            
        except Exception as e:
            logger.error(f"Error handling reminder: {e}")
    
    def _process_reminder_with_agent(self, reminder_message: str):
        """Process reminder through Grok agent for conversational response"""
        try:
            # Give Grok context that this is a reminder to announce
            context_message = f"[SYSTEM: A scheduled reminder just triggered. Please announce this reminder to the user in a friendly, conversational way.]\n\nReminder: {reminder_message}"
            
            response = self.agent.chat(context_message)
            
            # Display agent response
            self.message_queue.put(("Agent", response, "#ffffff"))
            
            # Speak response
            if self.voice.voice_output_enabled:
                self.voice.speak(response)
                
        except Exception as e:
            logger.error(f"Error processing reminder with agent: {e}")
            # Fallback - just speak the raw reminder
            if self.voice.voice_output_enabled:
                self.voice.speak(f"Reminder: {reminder_message}")
    
    def _voice_loop(self):
        """Voice listening loop (runs in thread)"""
        while self.voice_mode and self.running:
            try:
                # Listen for speech
                text = self.voice.listen(timeout=10, phrase_time_limit=30)
                
                if text and self.voice_mode:
                    # Process message
                    self._process_message(text)
                    
            except Exception as e:
                logger.error(f"Voice loop error: {e}")
    
    def _on_drop_database(self, event):
        """Handle file drop on database zone"""
        try:
            # Get file path (remove curly braces if present)
            file_path = event.data.strip('{}')
            
            if not file_path.lower().endswith('.txt'):
                messagebox.showerror("Error", "Only .txt files are supported")
                return
            
            # Read file
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Add to database as a stored document
            # For now, just send as a message with special prefix
            message = f"[DOCUMENT TO REMEMBER]\n{content}"
            
            threading.Thread(target=self._process_message, args=(message,), daemon=True).start()
            
            self.add_message("System", f"Added document to database: {file_path.split('/')[-1]}", "#00ff00")
            
        except Exception as e:
            logger.error(f"Error dropping file on database: {e}")
            messagebox.showerror("Error", f"Failed to add document: {e}")
    
    def _on_drop_chat(self, event):
        """Handle file drop on chat zone"""
        try:
            # Get file path
            file_path = event.data.strip('{}')
            
            if not file_path.lower().endswith('.txt'):
                messagebox.showerror("Error", "Only .txt files are supported")
                return
            
            # Read file
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Send as message
            threading.Thread(target=self._process_message, args=(content,), daemon=True).start()
            
            self.add_message("System", f"Sent document as message: {file_path.split('/')[-1]}", "#00ff00")
            
        except Exception as e:
            logger.error(f"Error dropping file on chat: {e}")
            messagebox.showerror("Error", f"Failed to send document: {e}")
    
    def add_message(self, sender, message, color='#ffffff'):
        """
        Add message to chat display (thread-safe)
        
        Args:
            sender: Message sender
            message: Message text
            color: Text color
        """
        self.message_queue.put((sender, message, color))
    
    def _process_queue(self):
        """Process message queue and update GUI"""
        try:
            while True:
                sender, message, color = self.message_queue.get_nowait()
                
                # Enable editing
                self.chat_display.config(state=tk.NORMAL)
                
                # Add message
                self.chat_display.insert(tk.END, f"{sender}: ", 'sender')
                self.chat_display.insert(tk.END, f"{message}\n\n", 'message')
                
                # Configure tags
                self.chat_display.tag_config('sender', foreground=color, font=('Arial', 10, 'bold'))
                self.chat_display.tag_config('message', foreground='#ffffff')
                
                # Disable editing
                self.chat_display.config(state=tk.DISABLED)
                
                # Auto-scroll to bottom
                self.chat_display.see(tk.END)
                
        except queue.Empty:
            pass
        
        # Schedule next check
        if self.running:
            self.root.after(100, self._process_queue)
    
    def _toggle_code_mode(self):
        """Toggle code mode - or stop an active write if one is running"""
        if self.code_writing_active:
            # Writing is in progress - this click means STOP
            self.code_write_stop_event.set()
            return
        
        self.code_mode_enabled = not self.code_mode_enabled
        
        if self.code_mode_enabled:
            self.code_btn.config(text="💻 Code: ON", bg='#00aa00')
            self.add_message("System", "Code mode ON - code blocks will be written to Notepad.", "#00ff00")
        else:
            self.code_btn.config(text="💻 Code: OFF", bg='#333333')
            self.add_message("System", "Code mode OFF.", "#ffaa00")
    
    def _toggle_browser_lock(self):
        """Toggle browser/action executor lock"""
        self.browser_locked = not self.browser_locked
        
        if self.agent and hasattr(self.agent, 'action_executor'):
            self.agent.action_executor.enabled = not self.browser_locked
        
        if self.agent and hasattr(self.agent, 'action_executor') and            hasattr(self.agent.action_executor, 'browser_controller') and            self.agent.action_executor.browser_controller:
            self.agent.action_executor.browser_controller.enabled = not self.browser_locked
        
        if self.browser_locked:
            self.browser_lock_btn.config(text="🌐 Browser: OFF", bg='#aa0000')
            self.add_message("System", "Browser locked - actions disabled.", "#ff4444")
        else:
            self.browser_lock_btn.config(text="🌐 Browser: ON", bg='#006600')
            self.add_message("System", "Browser unlocked - actions enabled.", "#00ff00")
    
    def _toggle_collaborate(self):
        """Toggle AI collaboration mode with peer agent"""
        self.collaborate_enabled = not self.collaborate_enabled
        
        try:
            import requests
            requests.post(
                "http://localhost:5000/collaborate",
                json={"enabled": self.collaborate_enabled},
                timeout=5
            )
        except Exception as e:
            logger.error(f"Could not update collaborate flag: {e}")
        
        if self.collaborate_enabled:
            self.collaborate_btn.config(text="🤝 Collab: ON", bg='#4a90b8')
            from config.config import PEER_DISPLAY_NAME, PEER_URL
            self.add_message("System", f"Collaboration ON - responses sent to {PEER_DISPLAY_NAME} at {PEER_URL}", "#00aaff")
        else:
            self.collaborate_btn.config(text="🤝 Collab: OFF", bg='#333333')
            self.add_message("System", "Collaboration OFF.", "#ffaa00")
    
    def _send_to_peer(self, response):
        """Send agent response to peer if collaboration is enabled"""
        if not self.collaborate_enabled:
            return
        import threading
        def send_when_done():
            import time
            import requests
            while self.voice.is_speaking:
                time.sleep(0.5)
            time.sleep(0.5)
            try:
                from config.config import PEER_URL, AGENT_DISPLAY_NAME
                requests.post(
                    f"{PEER_URL}/agent_message",
                    json={"text": response, "sender": AGENT_DISPLAY_NAME},
                    timeout=120
                )
            except Exception as e:
                logger.error(f"Failed to send to peer: {e}")
        threading.Thread(target=send_when_done, daemon=True).start()
    
    def _toggle_ai(self):
        """Toggle Grok AI on or off"""
        self.ai_enabled = not self.ai_enabled
        self.agent.ai_enabled = self.ai_enabled
        
        if self.ai_enabled:
            self.ai_btn.config(text="🤖 AI: ON", bg='#006600')
            self.add_message("System", "AI enabled - Grok will respond.", "#00ff00")
        else:
            self.ai_btn.config(text="🤖 AI: OFF", bg='#aa0000')
            self.add_message("System", "AI disabled - local commands only.", "#ff4444")
    
    def _extract_code_blocks(self, text):
        """
        Extract code blocks from response text.
        Strips triple backticks and language tags.
        Multiple blocks are joined with a separator comment.
        
        Args:
            text: Agent response text
            
        Returns:
            Combined code string, or None if no code blocks found
        """
        import re
        # Match closed code blocks: ```[optional language tag]\n...\n```
        blocks = re.findall(r'```(?:[a-zA-Z0-9+#]*)\n?(.*?)```', text, re.DOTALL)
        
        # Fallback: match unclosed code block (``` at start, no closing ```)
        if not blocks:
            unclosed = re.findall(r'```(?:[a-zA-Z0-9+#]*)\n?(.*)', text, re.DOTALL)
            if unclosed:
                blocks = unclosed
                logger.info("Code mode: matched unclosed code block")
        
        if not blocks:
            logger.info("Code mode: no code blocks found in response")
            return None
        
        logger.info(f"Code mode: extracted {len(blocks)} code block(s)")
        
        # Strip leading/trailing whitespace from each block
        blocks = [block.strip() for block in blocks if block.strip()]
        
        if not blocks:
            return None
        
        # Join multiple blocks with a separator
        if len(blocks) == 1:
            return blocks[0]
        
        separator = "\n\n# --- Code Block Separator ---\n\n"
        return separator.join(blocks)
    
    def _notepad_writer_thread(self, code_text):
        """
        Background thread: opens Notepad if needed, appends code via clipboard paste.
        Checks stop_event before each major step for interrupt support.
        
        Args:
            code_text: Extracted code string to write
        """
        import ctypes
        import time
        from agent.action_executor import press_key, release_key, tap_key
        
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        
        # Critical: set return types to c_void_p so 64-bit pointers aren't truncated
        # Set return types to c_void_p - critical on 64-bit Windows
        # Without this, ctypes defaults to c_int and truncates pointers
        kernel32.GlobalAlloc.restype = ctypes.c_void_p
        kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
        kernel32.GlobalLock.restype = ctypes.c_void_p
        kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
        kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
        kernel32.GlobalFree.argtypes = [ctypes.c_void_p]
        user32.FindWindowW.restype = ctypes.c_void_p
        user32.FindWindowExW.restype = ctypes.c_void_p
        user32.SetClipboardData.restype = ctypes.c_void_p
        user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
        
        # Flip button to stop mode
        self.code_writing_active = True
        self.message_queue.put(("System", "📝 Writing code to Notepad...", "#ffaa00"))
        self.code_btn.config(text="⛹ Stop", bg='#aa0000')
        
        try:
            # --- Step 1: Open Notepad via Win+R, then wait for it ---
            if self.code_write_stop_event.is_set():
                return
            
            logger.info("Code mode: launching Notepad via Win+R")
            self.agent.action_executor.execute_win_r("notepad")
            
            # Wait patiently for Notepad to appear - no rush
            logger.info("Code mode: waiting for Notepad window...")
            deadline = time.time() + 15
            hwnd = None
            while time.time() < deadline:
                if self.code_write_stop_event.is_set():
                    return
                hwnd = user32.FindWindowW("Notepad", None)
                if hwnd:
                    logger.info(f"Code mode: Notepad found, hwnd={hwnd}")
                    break
                time.sleep(0.5)
            
            if not hwnd:
                self.message_queue.put(("Error", "Notepad did not open in time.", "#ff0000"))
                return
            
            # Give Notepad a moment to fully settle before we touch it
            time.sleep(2.0)
            
            # --- Step 2: Put code on clipboard (CF_UNICODETEXT) ---
            if self.code_write_stop_event.is_set():
                return
            
            # Encode as UTF-16LE null-terminated for CF_UNICODETEXT
            encoded = (code_text + "\0").encode("utf-16-le")
            size = len(encoded)
            
            # GlobalAlloc with GMEM_MOVEABLE (0x0002)
            hMem = kernel32.GlobalAlloc(0x0002, size)
            if not hMem:
                self.message_queue.put(("Error", "Clipboard: GlobalAlloc failed.", "#ff0000"))
                return
            
            pMem = kernel32.GlobalLock(hMem)
            if not pMem:
                kernel32.GlobalFree(hMem)
                self.message_queue.put(("Error", "Clipboard: GlobalLock failed.", "#ff0000"))
                return
            
            ctypes.memmove(pMem, encoded, size)
            kernel32.GlobalUnlock(hMem)
            
            # CF_UNICODETEXT = 13
            if not user32.OpenClipboard(0):
                kernel32.GlobalFree(hMem)
                self.message_queue.put(("Error", "Clipboard: OpenClipboard failed.", "#ff0000"))
                return
            
            user32.EmptyClipboard()
            result = user32.SetClipboardData(13, hMem)  # 13 = CF_UNICODETEXT
            user32.CloseClipboard()
            
            if not result:
                self.message_queue.put(("Error", "Clipboard: SetClipboardData failed.", "#ff0000"))
                return
            
            # --- Step 3: Bring Notepad to foreground, click into edit, go to end ---
            if self.code_write_stop_event.is_set():
                return
            
            user32.SetForegroundWindow(hwnd)
            time.sleep(0.4)
            
            # Find the Edit control inside Notepad by class name
            edit_hwnd = user32.FindWindowExW(hwnd, 0, "Edit", None)
            
            if edit_hwnd != 0:
                # Get edit control rect so we can click into it
                class RECT(ctypes.Structure):
                    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]
                
                rect = RECT()
                user32.GetWindowRect(edit_hwnd, ctypes.byref(rect))
                
                # Click center of edit control to focus it
                cx = (rect.left + rect.right) // 2
                cy = (rect.top + rect.bottom) // 2
                user32.SetCursorPos(cx, cy)
                user32.mouse_event(0x0002, 0, 0)  # MOUSEEVENTF_LEFTDOWN
                time.sleep(0.05)
                user32.mouse_event(0x0004, 0, 0)  # MOUSEEVENTF_LEFTUP
                time.sleep(0.2)
                
                # Ctrl+End to move cursor to end of existing content
                press_key(0x11)   # Ctrl down
                tap_key(0x23)     # VK_END
                release_key(0x11) # Ctrl up
                time.sleep(0.2)
                
                # Two newlines to separate from existing content
                tap_key(0x0D)  # Enter
                tap_key(0x0D)  # Enter
                time.sleep(0.1)
            
            # --- Step 4: Paste via Ctrl+V ---
            if self.code_write_stop_event.is_set():
                return
            
            press_key(0x11)   # Ctrl down
            tap_key(0x56)     # V
            release_key(0x11) # Ctrl up
            
            time.sleep(0.5)
            self.message_queue.put(("System", "✅ Code written to Notepad.", "#00ff00"))
            logger.info("Code mode: paste to Notepad complete")
            
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            logger.error(f"Notepad writer thread error: {e}\n{tb}")
            self.message_queue.put(("Error", f"Code write failed: {e}\n{tb}", "#ff0000"))
        
        finally:
            # Always reset button state when thread exits (normal or interrupted)
            self.code_writing_active = False
            if self.code_mode_enabled:
                self.code_btn.config(text="💻 Code: ON", bg='#00aa00')
            else:
                self.code_btn.config(text="💻 Code: OFF", bg='#333333')
    
    def _on_closing(self):
        """Handle window close"""
        self.running = False
        self.voice_mode = False
        
        # Stop scheduler
        if self.scheduler:
            self.scheduler.stop()
        
        # Close child windows
        if self.plc_config_window:
            try:
                self.plc_config_window.window.destroy()
            except:
                pass
        
        if self.settings_window:
            try:
                self.settings_window.window.destroy()
            except:
                pass
        
        # Close multi-monitor widgets if active
        if self.mm_widgets:
            try:
                self.mm_widgets.destroy_all()
            except:
                pass
        
        self.agent.shutdown()
        self.root.destroy()
    
    def run(self):
        """Start GUI main loop"""
        self.root.mainloop()