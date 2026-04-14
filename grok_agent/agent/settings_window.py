"""
Settings Configuration Window
Standalone GUI for managing location and email settings
Supports multiple email recipients for reminders
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import threading
import logging
from typing import Optional, Callable, Dict, List

logger = logging.getLogger(__name__)


class SettingsWindow:
    """Standalone window for system settings (location, email)"""
    
    def __init__(self, chore_db, on_close_callback: Callable = None):
        """
        Initialize Settings Window
        
        Args:
            chore_db: ChoreDatabase instance
            on_close_callback: Optional callback when window closes
        """
        self.chore_db = chore_db
        self.on_close_callback = on_close_callback
        
        # Email list
        self.email_list: List[str] = []
        
        # Geocoding availability
        self._geocoder_available = False
        self._astral_available = False
        self._check_dependencies()
        
        # Create window
        self.window = tk.Toplevel()
        self.window.title("Settings - Location & Email")
        self.window.geometry("650x750")
        self.window.configure(bg='#2b2b2b')
        
        # Handle window close
        self.window.protocol("WM_DELETE_WINDOW", self._on_closing)
        
        # Build UI
        self._create_widgets()
        
        # Load current settings
        self._load_settings()
    
    def _check_dependencies(self):
        """Check if optional dependencies are available"""
        try:
            from geopy.geocoders import Nominatim
            self._geocoder_available = True
            logger.info("geopy available for geocoding")
        except ImportError:
            logger.warning("geopy not installed. Location lookup will be limited.")
        
        try:
            from astral import LocationInfo
            from astral.sun import sun
            self._astral_available = True
            logger.info("astral available for sunrise/sunset calculations")
        except ImportError:
            logger.warning("astral not installed. Sunrise/sunset calculations will be unavailable.")
    
    def _create_widgets(self):
        """Create all GUI widgets"""
        
        # Create notebook for tabs
        notebook = ttk.Notebook(self.window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Style for dark theme
        style = ttk.Style()
        style.configure('TNotebook', background='#2b2b2b')
        style.configure('TNotebook.Tab', padding=[10, 5])
        
        # ===== LOCATION TAB =====
        location_frame = tk.Frame(notebook, bg='#2b2b2b')
        notebook.add(location_frame, text='📍 Location')
        self._create_location_tab(location_frame)

        # ===== IDENTITY TAB =====
        identity_frame = tk.Frame(notebook, bg='#2b2b2b')
        notebook.add(identity_frame, text='Identity')
        self._create_identity_tab(identity_frame)

        # ===== EMAIL TAB =====
        email_frame = tk.Frame(notebook, bg='#2b2b2b')
        notebook.add(email_frame, text='📧 Email')
        self._create_email_tab(email_frame)
        
        # ===== SCHEDULES TAB =====
        schedules_frame = tk.Frame(notebook, bg='#2b2b2b')
        notebook.add(schedules_frame, text='⏰ Schedules')
        self._create_schedules_tab(schedules_frame)
        
        # ===== ABOUT TAB =====
        about_frame = tk.Frame(notebook, bg='#2b2b2b')
        notebook.add(about_frame, text='ℹ️ About')
        self._create_about_tab(about_frame)
    
    def _create_location_tab(self, parent):
        """Create location settings tab"""
        
        # Header
        tk.Label(
            parent,
            text="📍 Location Settings",
            bg='#2b2b2b',
            fg='white',
            font=('Arial', 14, 'bold')
        ).pack(pady=20)
        
        tk.Label(
            parent,
            text="Set your location for sunrise/sunset calculations",
            bg='#2b2b2b',
            fg='#aaaaaa',
            font=('Arial', 10)
        ).pack()
        
        # Form frame
        form = tk.Frame(parent, bg='#2b2b2b')
        form.pack(fill=tk.X, padx=40, pady=20)
        
        # City
        tk.Label(form, text="City:", bg='#2b2b2b', fg='white', font=('Arial', 11)).grid(row=0, column=0, sticky='e', padx=10, pady=10)
        self.city_entry = tk.Entry(form, bg='#1e1e1e', fg='white', font=('Arial', 11), width=30, insertbackground='white')
        self.city_entry.grid(row=0, column=1, pady=10)
        
        # State/Region
        tk.Label(form, text="State/Region:", bg='#2b2b2b', fg='white', font=('Arial', 11)).grid(row=1, column=0, sticky='e', padx=10, pady=10)
        self.state_entry = tk.Entry(form, bg='#1e1e1e', fg='white', font=('Arial', 11), width=30, insertbackground='white')
        self.state_entry.grid(row=1, column=1, pady=10)
        
        # ZIP Code
        tk.Label(form, text="ZIP Code:", bg='#2b2b2b', fg='white', font=('Arial', 11)).grid(row=2, column=0, sticky='e', padx=10, pady=10)
        self.zip_entry = tk.Entry(form, bg='#1e1e1e', fg='white', font=('Arial', 11), width=15, insertbackground='white')
        self.zip_entry.grid(row=2, column=1, sticky='w', pady=10)
        
        # Lookup button
        lookup_btn = tk.Button(
            form,
            text="🔍 Lookup Coordinates",
            command=self._lookup_location,
            bg='#0066cc',
            fg='white',
            font=('Arial', 10, 'bold')
        )
        lookup_btn.grid(row=3, column=1, sticky='w', pady=10)
        
        # Separator
        tk.Frame(form, bg='#444444', height=2).grid(row=4, column=0, columnspan=2, sticky='ew', pady=20)
        
        # Manual coordinates
        tk.Label(
            form, text="Or enter coordinates manually:",
            bg='#2b2b2b', fg='#aaaaaa', font=('Arial', 10)
        ).grid(row=5, column=0, columnspan=2, sticky='w', pady=5)
        
        # Latitude
        tk.Label(form, text="Latitude:", bg='#2b2b2b', fg='white', font=('Arial', 11)).grid(row=6, column=0, sticky='e', padx=10, pady=10)
        self.lat_entry = tk.Entry(form, bg='#1e1e1e', fg='white', font=('Arial', 11), width=15, insertbackground='white')
        self.lat_entry.grid(row=6, column=1, sticky='w', pady=10)
        
        # Longitude
        tk.Label(form, text="Longitude:", bg='#2b2b2b', fg='white', font=('Arial', 11)).grid(row=7, column=0, sticky='e', padx=10, pady=10)
        self.lon_entry = tk.Entry(form, bg='#1e1e1e', fg='white', font=('Arial', 11), width=15, insertbackground='white')
        self.lon_entry.grid(row=7, column=1, sticky='w', pady=10)
        
        # Timezone
        tk.Label(form, text="Timezone:", bg='#2b2b2b', fg='white', font=('Arial', 11)).grid(row=8, column=0, sticky='e', padx=10, pady=10)
        
        # Common US timezones
        timezones = [
            'America/New_York',
            'America/Chicago',
            'America/Denver',
            'America/Los_Angeles',
            'America/Phoenix',
            'America/Anchorage',
            'Pacific/Honolulu',
            'UTC'
        ]
        self.tz_combo = ttk.Combobox(form, values=timezones, width=25)
        self.tz_combo.set('America/Chicago')
        self.tz_combo.grid(row=8, column=1, sticky='w', pady=10)
        
        # Status/Preview
        self.location_status = tk.Label(
            parent,
            text="",
            bg='#2b2b2b',
            fg='#00ff00',
            font=('Arial', 10)
        )
        self.location_status.pack(pady=10)
        
        # Test sunrise/sunset button
        tk.Button(
            parent,
            text="🌅 Test Sunrise/Sunset",
            command=self._test_sun_times,
            bg='#cc6600',
            fg='white',
            font=('Arial', 10, 'bold')
        ).pack(pady=5)
        
        # Save button
        tk.Button(
            parent,
            text="💾 Save Location Settings",
            command=self._save_location,
            bg='#00aa00',
            fg='white',
            font=('Arial', 12, 'bold'),
            width=25
        ).pack(pady=20)
    
    def _create_identity_tab(self, parent):
        """Create identity settings tab - user name and agent name"""
        tk.Label(parent, text="Identity Settings",
                 bg='#2b2b2b', fg='white',
                 font=('Arial', 13, 'bold')).pack(pady=(20, 4))
        tk.Label(parent,
                 text="Changes take effect after restarting the agent.",
                 bg='#2b2b2b', fg='#aaaaaa',
                 font=('Arial', 9)).pack(pady=(0, 16))

        form = tk.Frame(parent, bg='#2b2b2b')
        form.pack(fill=tk.X, padx=40)

        # User name
        tk.Label(form, text="Your name:", bg='#2b2b2b', fg='#aaaaaa',
                 font=('Arial', 10)).grid(row=0, column=0, sticky='w', pady=8)
        self.user_name_entry = tk.Entry(form, bg='#1e1e1e', fg='white',
                                        insertbackground='white',
                                        font=('Arial', 10), width=30)
        self.user_name_entry.grid(row=0, column=1, sticky='w', padx=12, pady=8)

        # Agent name
        tk.Label(form, text="Agent name:", bg='#2b2b2b', fg='#aaaaaa',
                 font=('Arial', 10)).grid(row=1, column=0, sticky='w', pady=8)
        self.agent_name_entry = tk.Entry(form, bg='#1e1e1e', fg='white',
                                          insertbackground='white',
                                          font=('Arial', 10), width=30)
        self.agent_name_entry.grid(row=1, column=1, sticky='w', padx=12, pady=8)

        # Load current values
        try:
            from config.config import AGENT_DISPLAY_NAME
            self.agent_name_entry.insert(0, AGENT_DISPLAY_NAME)
        except Exception:
            self.agent_name_entry.insert(0, saved_agent or "Agent")

        saved_user = self.chore_db.get_setting('user_name')
        saved_agent = self.chore_db.get_setting('agent_display_name')
        if saved_user:
            self.user_name_entry.insert(0, saved_user)

        # Save button
        def _save_identity():
            user_name  = self.user_name_entry.get().strip()
            agent_name = self.agent_name_entry.get().strip()
            if not user_name or not agent_name:
                from tkinter import messagebox
                messagebox.showerror("Required", "Both fields are required.")
                return
            try:
                # Save to chore_db
                self.chore_db.set_setting('user_name', user_name)
                self.chore_db.set_setting('agent_display_name', agent_name)

                # Patch config.py
                import os, re
                config_path = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    'config', 'config.py')
                if os.path.isfile(config_path):
                    with open(config_path, 'r', encoding='utf-8') as f:
                        cfg = f.read()
                    cfg = re.sub(r'AGENT_DISPLAY_NAME\s*=\s*"[^"]*"',
                                 f'AGENT_DISPLAY_NAME = "{agent_name}"', cfg)
                    cfg = re.sub(r"AGENT_DISPLAY_NAME\s*=\s*'[^']*'",
                                 f'AGENT_DISPLAY_NAME = "{agent_name}"', cfg)
                    # Add USER_NAME if not present
                    if 'USER_NAME' not in cfg:
                        cfg += f'\nUSER_NAME = "{user_name}"\n'
                    else:
                        cfg = re.sub(r'USER_NAME\s*=\s*"[^"]*"',
                                     f'USER_NAME = "{user_name}"', cfg)
                        cfg = re.sub(r"USER_NAME\s*=\s*'[^']*'",
                                     f'USER_NAME = "{user_name}"', cfg)
                    with open(config_path, 'w', encoding='utf-8') as f:
                        f.write(cfg)

                status_lbl.config(text="Saved. Restart the agent to apply.", fg='#00ff00')
            except Exception as e:
                status_lbl.config(text=f"Error: {e}", fg='#ff4444')

        tk.Button(parent, text="Save Identity",
                  command=_save_identity,
                  bg='#0066cc', fg='white',
                  font=('Arial', 10, 'bold'),
                  relief=tk.FLAT, padx=20, pady=8).pack(pady=16)

        status_lbl = tk.Label(parent, text="", bg='#2b2b2b', fg='#aaaaaa',
                              font=('Arial', 9))
        status_lbl.pack()

    def _create_email_tab(self, parent):
        """Create email settings tab with multiple recipient support"""
        
        # Header
        tk.Label(
            parent,
            text="📧 Email Settings",
            bg='#2b2b2b',
            fg='white',
            font=('Arial', 14, 'bold')
        ).pack(pady=15)
        
        tk.Label(
            parent,
            text="Configure Gmail for sending reminder notifications",
            bg='#2b2b2b',
            fg='#aaaaaa',
            font=('Arial', 10)
        ).pack()
        
        # Enable checkbox
        self.email_enabled_var = tk.BooleanVar()
        tk.Checkbutton(
            parent,
            text="Enable Email Notifications",
            variable=self.email_enabled_var,
            bg='#2b2b2b',
            fg='white',
            selectcolor='#1e1e1e',
            font=('Arial', 11),
            command=self._toggle_email_fields
        ).pack(pady=10)
        
        # Sender settings frame
        sender_frame = tk.LabelFrame(
            parent,
            text="Sender Account (Gmail)",
            bg='#1e1e1e',
            fg='white',
            font=('Arial', 10, 'bold')
        )
        sender_frame.pack(fill=tk.X, padx=20, pady=10)
        
        sender_inner = tk.Frame(sender_frame, bg='#1e1e1e')
        sender_inner.pack(fill=tk.X, padx=10, pady=10)
        
        # Gmail address
        tk.Label(sender_inner, text="Gmail Address:", bg='#1e1e1e', fg='white', font=('Arial', 10)).grid(row=0, column=0, sticky='e', padx=5, pady=5)
        self.email_entry = tk.Entry(sender_inner, bg='#2b2b2b', fg='white', font=('Arial', 10), width=35, insertbackground='white')
        self.email_entry.grid(row=0, column=1, pady=5, sticky='w')
        
        # App Password
        tk.Label(sender_inner, text="App Password:", bg='#1e1e1e', fg='white', font=('Arial', 10)).grid(row=1, column=0, sticky='e', padx=5, pady=5)
        self.password_entry = tk.Entry(sender_inner, bg='#2b2b2b', fg='white', font=('Arial', 10), width=35, show='*', insertbackground='white')
        self.password_entry.grid(row=1, column=1, pady=5, sticky='w')
        
        # Show/hide password
        self.show_pass_var = tk.BooleanVar()
        tk.Checkbutton(
            sender_inner,
            text="Show",
            variable=self.show_pass_var,
            bg='#1e1e1e',
            fg='#aaaaaa',
            selectcolor='#2b2b2b',
            command=self._toggle_password_visibility
        ).grid(row=1, column=2, padx=5)
        
        # ===== RECIPIENTS SECTION =====
        recipients_frame = tk.LabelFrame(
            parent,
            text="📬 Recipient Email Addresses",
            bg='#1e1e1e',
            fg='white',
            font=('Arial', 10, 'bold')
        )
        recipients_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Recipients list with scrollbar
        list_frame = tk.Frame(recipients_frame, bg='#1e1e1e')
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.recipients_listbox = tk.Listbox(
            list_frame,
            bg='#2b2b2b',
            fg='white',
            font=('Consolas', 10),
            selectbackground='#0066cc',
            selectforeground='white',
            yscrollcommand=scrollbar.set,
            height=6
        )
        self.recipients_listbox.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.recipients_listbox.yview)
        
        # Buttons for managing recipients
        btn_frame = tk.Frame(recipients_frame, bg='#1e1e1e')
        btn_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        tk.Button(
            btn_frame,
            text="+ Add Email",
            command=self._add_recipient,
            bg='#00aa00',
            fg='white',
            font=('Arial', 10, 'bold'),
            width=12
        ).pack(side=tk.LEFT, padx=5)
        
        tk.Button(
            btn_frame,
            text="- Remove Selected",
            command=self._remove_recipient,
            bg='#aa0000',
            fg='white',
            font=('Arial', 10, 'bold'),
            width=15
        ).pack(side=tk.LEFT, padx=5)
        
        tk.Label(
            btn_frame,
            text="(All addresses receive reminders)",
            bg='#1e1e1e',
            fg='#666666',
            font=('Arial', 9)
        ).pack(side=tk.LEFT, padx=10)
        
        # Instructions
        instructions = tk.LabelFrame(
            parent,
            text="📋 Gmail App Password Instructions",
            bg='#1e1e1e',
            fg='white',
            font=('Arial', 10, 'bold')
        )
        instructions.pack(fill=tk.X, padx=20, pady=10)
        
        instructions_text = """1. Go to Google Account → Security → 2-Step Verification (enable it)
2. At the bottom, click "App passwords"
3. Select "Mail" and "Windows Computer" → Generate
4. Copy the 16-character password into "App Password" above
Note: Use App Password, NOT your regular Gmail password!"""
        
        tk.Label(
            instructions,
            text=instructions_text,
            bg='#1e1e1e',
            fg='#aaaaaa',
            font=('Consolas', 9),
            justify=tk.LEFT
        ).pack(padx=10, pady=10, anchor='w')
        
        # Bottom buttons
        bottom_frame = tk.Frame(parent, bg='#2b2b2b')
        bottom_frame.pack(fill=tk.X, padx=20, pady=10)
        
        tk.Button(
            bottom_frame,
            text="📤 Send Test Email",
            command=self._test_email,
            bg='#0066cc',
            fg='white',
            font=('Arial', 10, 'bold')
        ).pack(side=tk.LEFT, padx=5)
        
        tk.Button(
            bottom_frame,
            text="💾 Save Email Settings",
            command=self._save_email,
            bg='#00aa00',
            fg='white',
            font=('Arial', 10, 'bold')
        ).pack(side=tk.LEFT, padx=5)
        
        # Status
        self.email_status = tk.Label(
            parent,
            text="",
            bg='#2b2b2b',
            fg='#aaaaaa',
            font=('Arial', 10)
        )
        self.email_status.pack(pady=5)
    
    def _add_recipient(self):
        """Add a new recipient email address"""
        email = simpledialog.askstring(
            "Add Recipient",
            "Enter email address:",
            parent=self.window
        )
        
        if email:
            email = email.strip()
            if '@' not in email or '.' not in email:
                messagebox.showerror("Invalid Email", "Please enter a valid email address")
                return
            
            if email in self.email_list:
                messagebox.showwarning("Duplicate", "This email is already in the list")
                return
            
            self.email_list.append(email)
            self.recipients_listbox.insert(tk.END, email)
            logger.info(f"Added recipient: {email}")
    
    def _remove_recipient(self):
        """Remove selected recipient email address"""
        selection = self.recipients_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Select an email to remove")
            return
        
        index = selection[0]
        email = self.email_list[index]
        
        del self.email_list[index]
        self.recipients_listbox.delete(index)
        logger.info(f"Removed recipient: {email}")
    
    def _create_schedules_tab(self, parent):
        """Create schedules management tab"""
        
        # Header
        header = tk.Label(
            parent,
            text="⏰ Scheduled Tasks Management",
            font=('Arial', 16, 'bold'),
            bg='#2b2b2b',
            fg='#ffffff'
        )
        header.pack(pady=(10, 5))
        
        subtitle = tk.Label(
            parent,
            text="Enable/disable automated tasks, PLC monitoring, and reminders",
            font=('Arial', 10),
            bg='#2b2b2b',
            fg='#888888'
        )
        subtitle.pack(pady=(0, 15))
        
        # Main container
        main_frame = tk.Frame(parent, bg='#2b2b2b')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Schedules list frame with scrollbar
        list_frame = tk.Frame(main_frame, bg='#1e1e1e', relief=tk.SUNKEN, bd=2)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create canvas and scrollbar for schedules
        canvas = tk.Canvas(list_frame, bg='#1e1e1e', highlightthickness=0)
        scrollbar = tk.Scrollbar(list_frame, orient='vertical', command=canvas.yview)
        self.schedules_container = tk.Frame(canvas, bg='#1e1e1e')
        
        self.schedules_container.bind(
            '<Configure>',
            lambda e: canvas.configure(scrollregion=canvas.bbox('all'))
        )
        
        canvas.create_window((0, 0), window=self.schedules_container, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Store schedule widgets for updates
        self.schedule_widgets = []
        
        # Button frame
        button_frame = tk.Frame(parent, bg='#2b2b2b')
        button_frame.pack(fill=tk.X, padx=20, pady=10)
        
        refresh_btn = tk.Button(
            button_frame,
            text="🔄 Refresh List",
            font=('Arial', 11),
            bg='#3a3a3a',
            fg='#ffffff',
            activebackground='#4a4a4a',
            relief=tk.FLAT,
            padx=20,
            pady=8,
            command=self._refresh_schedules
        )
        refresh_btn.pack(side=tk.LEFT, padx=5)
        
        add_btn = tk.Button(
            button_frame,
            text="➕ Add New Schedule",
            font=('Arial', 11),
            bg='#0066cc',
            fg='#ffffff',
            activebackground='#0077dd',
            relief=tk.FLAT,
            padx=20,
            pady=8,
            command=self._add_new_schedule
        )
        add_btn.pack(side=tk.LEFT, padx=5)
        
        # Load schedules
        self._load_schedules()
    
    def _load_schedules(self):
        """Load all chores/schedules from database and display them"""
        try:
            # Clear existing widgets
            for widget in self.schedule_widgets:
                widget.destroy()
            self.schedule_widgets.clear()
            
            # Get all chores from database (these ARE the schedules)
            with self.chore_db.conn.cursor() as cursor:
                cursor.execute("""
                    SELECT c.id, c.name, c.description, c.action, c.schedule_type, 
                           c.schedule_value, c.enabled, c.last_run, c.next_run,
                           p.name as plc_name, c.tag_name
                    FROM chores c
                    LEFT JOIN plc_config p ON c.plc_id = p.id
                    ORDER BY c.enabled DESC, c.name
                """)
                
                chores = cursor.fetchall()
            
            if not chores:
                # Show "no schedules" message
                empty_label = tk.Label(
                    self.schedules_container,
                    text="No scheduled tasks found.\n\nCreate PLC monitoring chores to see them here.",
                    font=('Arial', 12),
                    bg='#1e1e1e',
                    fg='#888888',
                    pady=50
                )
                empty_label.pack(fill=tk.BOTH, expand=True)
                self.schedule_widgets.append(empty_label)
                return
            
            # Display each chore as a schedule
            for chore in chores:
                self._create_schedule_widget(chore)
                
            logger.info(f"Loaded {len(chores)} scheduled chores")
            
        except Exception as e:
            logger.error(f"Error loading schedules: {e}")
            messagebox.showerror("Error", f"Failed to load schedules:\n{e}")
    
    def _create_schedule_widget(self, chore):
        """Create a widget for a single chore/schedule"""
        # Unpack chore data: id, name, description, action, schedule_type, schedule_value, enabled, last_run, next_run, plc_name, tag_name
        chore_id, name, description, action, schedule_type, schedule_value, enabled, last_run, next_run, plc_name, tag_name = chore
        
        # Container frame for this schedule
        frame = tk.Frame(
            self.schedules_container,
            bg='#2b2b2b',
            relief=tk.RAISED,
            bd=1
        )
        frame.pack(fill=tk.X, padx=10, pady=5)
        self.schedule_widgets.append(frame)
        
        # Left side - checkbox and info
        left_frame = tk.Frame(frame, bg='#2b2b2b')
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Checkbox for enable/disable
        var = tk.BooleanVar(value=enabled)
        checkbox = tk.Checkbutton(
            left_frame,
            text="",
            variable=var,
            bg='#2b2b2b',
            fg='#ffffff',
            selectcolor='#1e1e1e',
            activebackground='#2b2b2b',
            command=lambda: self._toggle_schedule(chore_id, var.get())
        )
        checkbox.pack(side=tk.LEFT, padx=(0, 10))
        
        # Schedule info
        info_frame = tk.Frame(left_frame, bg='#2b2b2b')
        info_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Task description (bold)
        desc_text = f"{name} - {tag_name}"
        if description:
            desc_text = f"{name}: {description}"
        desc_label = tk.Label(
            info_frame,
            text=desc_text,
            font=('Arial', 11, 'bold'),
            bg='#2b2b2b',
            fg='#ffffff' if enabled else '#666666',
            anchor='w'
        )
        desc_label.pack(anchor='w')
        
        # Schedule details - based on schedule_type and schedule_value
        if schedule_type == 'interval':
            # Parse interval from schedule_value (e.g., "30m", "1h", "2h30m")
            interval_text = f"Every {schedule_value}"
        elif schedule_type == 'time':
            interval_text = f"Daily at {schedule_value}"
        elif schedule_type == 'sunrise':
            interval_text = f"At sunrise {schedule_value}" if schedule_value != "0" else "At sunrise"
        elif schedule_type == 'sunset':
            interval_text = f"At sunset {schedule_value}" if schedule_value != "0" else "At sunset"
        else:
            interval_text = f"{schedule_type}: {schedule_value}"
        
        last_run_text = f"Last: {last_run.strftime('%I:%M %p')}" if last_run else "Never run"
        plc_info = f"PLC: {plc_name}" if plc_name else ""
        
        details_label = tk.Label(
            info_frame,
            text=f"⏱️ {interval_text}  |  🕐 {last_run_text}  |  {plc_info}",
            font=('Arial', 9),
            bg='#2b2b2b',
            fg='#888888',
            anchor='w'
        )
        details_label.pack(anchor='w')
        
        # Action type badge
        action_colors = {
            'read': '#ff6b35',
            'toggle': '#4ecdc4',
            'set_on': '#95e1d3',
            'set_off': '#ffd700',
            'set_value': '#ff9ff3'
        }
        type_color = action_colors.get(action, '#888888')
        
        type_label = tk.Label(
            info_frame,
            text=f"📋 {action.replace('_', ' ').title()}",
            font=('Arial', 8),
            bg=type_color,
            fg='#000000',
            padx=8,
            pady=2
        )
        type_label.pack(anchor='w', pady=(5, 0))
        
        # Right side - action buttons
        button_frame = tk.Frame(frame, bg='#2b2b2b')
        button_frame.pack(side=tk.RIGHT, padx=10, pady=10)
        
        edit_btn = tk.Button(
            button_frame,
            text="✏️ Edit",
            font=('Arial', 9),
            bg='#3a3a3a',
            fg='#ffffff',
            activebackground='#4a4a4a',
            relief=tk.FLAT,
            padx=15,
            pady=5,
            command=lambda: self._edit_schedule(chore_id)
        )
        edit_btn.pack(side=tk.TOP, pady=2)
        
        delete_btn = tk.Button(
            button_frame,
            text="🗑️ Delete",
            font=('Arial', 9),
            bg='#cc0000',
            fg='#ffffff',
            activebackground='#dd0000',
            relief=tk.FLAT,
            padx=15,
            pady=5,
            command=lambda: self._delete_schedule(chore_id, name)
        )
        delete_btn.pack(side=tk.TOP, pady=2)
    
    def _toggle_schedule(self, chore_id, enabled):
        """Enable or disable a chore/schedule"""
        try:
            with self.chore_db.conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE chores 
                    SET enabled = %s 
                    WHERE id = %s
                """, (enabled, chore_id))
                
                self.chore_db.conn.commit()
            
            status = "enabled" if enabled else "disabled"
            logger.info(f"Chore {chore_id} {status}")
            
            # Refresh display
            self._load_schedules()
            
        except Exception as e:
            logger.error(f"Error toggling schedule: {e}")
            messagebox.showerror("Error", f"Failed to update schedule:\n{e}")
    
    def _edit_schedule(self, chore_id):
        """Edit a chore/schedule - FULL IMPLEMENTATION"""
        try:
            # Get current chore data
            with self.chore_db.conn.cursor() as cursor:
                cursor.execute("""
                    SELECT name, description, schedule_type, schedule_value, action
                    FROM chores
                    WHERE id = %s
                """, (chore_id,))
                
                result = cursor.fetchone()
            
            if not result:
                messagebox.showerror("Error", "Chore not found")
                return
            
            name, description, schedule_type, schedule_value, action = result
            
            # Create edit dialog
            dialog = tk.Toplevel(self.window)
            dialog.title(f"Edit: {name}")
            dialog.geometry("500x400")
            dialog.configure(bg='#2b2b2b')
            dialog.transient(self.window)
            dialog.grab_set()
            
            tk.Label(
                dialog,
                text=f"Edit Chore: {name}",
                font=('Arial', 14, 'bold'),
                bg='#2b2b2b',
                fg='#ffffff'
            ).pack(pady=15)
            
            # Schedule Type dropdown
            type_frame = tk.Frame(dialog, bg='#2b2b2b')
            type_frame.pack(pady=10, padx=20, fill=tk.X)
            
            tk.Label(
                type_frame,
                text="Schedule Type:",
                font=('Arial', 10),
                bg='#2b2b2b',
                fg='#ffffff'
            ).pack(side=tk.LEFT, padx=5)
            
            schedule_type_var = tk.StringVar(value=schedule_type)
            type_dropdown = ttk.Combobox(
                type_frame,
                textvariable=schedule_type_var,
                values=['interval', 'time', 'sunrise', 'sunset'],
                state='readonly',
                width=15
            )
            type_dropdown.pack(side=tk.LEFT, padx=5)
            
            # Schedule Value input
            value_frame = tk.Frame(dialog, bg='#2b2b2b')
            value_frame.pack(pady=10, padx=20, fill=tk.X)
            
            tk.Label(
                value_frame,
                text="Schedule Value:",
                font=('Arial', 10),
                bg='#2b2b2b',
                fg='#ffffff'
            ).pack(side=tk.LEFT, padx=5)
            
            schedule_value_var = tk.StringVar(value=schedule_value)
            value_entry = tk.Entry(
                value_frame,
                textvariable=schedule_value_var,
                font=('Arial', 10),
                width=20
            )
            value_entry.pack(side=tk.LEFT, padx=5)
            
            # Help text
            help_label = tk.Label(
                dialog,
                text="Examples: '30m', '1h', '2h30m' for interval\n'08:00' for time\n'+30m' or '-15m' for sunrise/sunset offset",
                font=('Arial', 8),
                bg='#2b2b2b',
                fg='#888888'
            )
            help_label.pack(pady=5)
            
            # Quick interval buttons (only for interval type)
            quick_frame = tk.Frame(dialog, bg='#2b2b2b')
            quick_frame.pack(pady=10)
            
            tk.Label(
                quick_frame,
                text="Quick intervals:",
                font=('Arial', 9),
                bg='#2b2b2b',
                fg='#888888'
            ).pack()
            
            buttons_frame = tk.Frame(quick_frame, bg='#2b2b2b')
            buttons_frame.pack(pady=5)
            
            for interval, label in [('15m', '15 min'), ('30m', '30 min'), ('1h', '1 hour'), 
                                   ('2h', '2 hours'), ('6h', '6 hours'), ('24h', '24 hours')]:
                tk.Button(
                    buttons_frame,
                    text=label,
                    command=lambda i=interval: schedule_value_var.set(i),
                    bg='#3a3a3a',
                    fg='#ffffff',
                    relief=tk.FLAT,
                    padx=10,
                    pady=5
                ).pack(side=tk.LEFT, padx=2)
            
            # Save button
            def save_changes():
                try:
                    new_type = schedule_type_var.get()
                    new_value = schedule_value_var.get()
                    
                    if not new_value:
                        messagebox.showerror("Error", "Schedule value cannot be empty")
                        return
                    
                    with self.chore_db.conn.cursor() as cursor:
                        cursor.execute("""
                            UPDATE chores 
                            SET schedule_type = %s, schedule_value = %s
                            WHERE id = %s
                        """, (new_type, new_value, chore_id))
                        
                        self.chore_db.conn.commit()
                    
                    logger.info(f"Updated chore {chore_id}: {new_type} = {new_value}")
                    messagebox.showinfo("Success", "Chore schedule updated!")
                    dialog.destroy()
                    self._load_schedules()
                    
                except Exception as e:
                    logger.error(f"Error saving chore: {e}")
                    messagebox.showerror("Error", f"Failed to save:\n{e}")
            
            # Button frame
            btn_frame = tk.Frame(dialog, bg='#2b2b2b')
            btn_frame.pack(pady=20)
            
            tk.Button(
                btn_frame,
                text="💾 Save Changes",
                font=('Arial', 11, 'bold'),
                bg='#0066cc',
                fg='#ffffff',
                activebackground='#0077dd',
                relief=tk.FLAT,
                padx=30,
                pady=10,
                command=save_changes
            ).pack(side=tk.LEFT, padx=5)
            
            tk.Button(
                btn_frame,
                text="❌ Cancel",
                font=('Arial', 11),
                bg='#666666',
                fg='#ffffff',
                activebackground='#777777',
                relief=tk.FLAT,
                padx=30,
                pady=10,
                command=dialog.destroy
            ).pack(side=tk.LEFT, padx=5)
            
        except Exception as e:
            logger.error(f"Error editing chore: {e}")
            messagebox.showerror("Error", f"Failed to edit chore:\n{e}")
            
            tk.Label(
                dialog,
                text=f"Edit: {task_desc}",
                font=('Arial', 12, 'bold'),
                bg='#2b2b2b',
                fg='#ffffff'
            ).pack(pady=10)
            
            # Interval input
            interval_frame = tk.Frame(dialog, bg='#2b2b2b')
            interval_frame.pack(pady=10)
            
            tk.Label(
                interval_frame,
                text="Interval (minutes):",
                font=('Arial', 10),
                bg='#2b2b2b',
                fg='#ffffff'
            ).pack(side=tk.LEFT, padx=5)
            
            interval_var = tk.StringVar(value=str(current_interval) if current_interval else "30")
            interval_entry = tk.Entry(
                interval_frame,
                textvariable=interval_var,
                font=('Arial', 10),
                width=10
            )
            interval_entry.pack(side=tk.LEFT, padx=5)
            
            # Common intervals buttons
            common_frame = tk.Frame(dialog, bg='#2b2b2b')
            common_frame.pack(pady=10)
            
            tk.Label(
                common_frame,
                text="Quick select:",
                font=('Arial', 9),
                bg='#2b2b2b',
                fg='#888888'
            ).pack()
            
            buttons_frame = tk.Frame(common_frame, bg='#2b2b2b')
            buttons_frame.pack(pady=5)
            
            for minutes, label in [(15, "15 min"), (30, "30 min"), (60, "1 hour"), (120, "2 hours"), (360, "6 hours"), (1440, "Daily")]:
                tk.Button(
                    buttons_frame,
                    text=label,
                    command=lambda m=minutes: interval_var.set(str(m)),
                    bg='#3a3a3a',
                    fg='#ffffff',
                    relief=tk.FLAT,
                    padx=10,
                    pady=5
                ).pack(side=tk.LEFT, padx=2)
            
            # Save button
            def save_changes():
                try:
                    new_interval = int(interval_var.get())
                    if new_interval < 1:
                        messagebox.showerror("Error", "Interval must be at least 1 minute")
                        return
                    
                    with self.chore_db.conn.cursor() as cursor:
                        cursor.execute("""
                            UPDATE schedules 
                            SET interval_minutes = %s
                            WHERE id = %s
                        """, (new_interval, schedule_id))
                        
                        self.chore_db.conn.commit()
                    
                    logger.info(f"Updated schedule {schedule_id} interval to {new_interval} minutes")
                    dialog.destroy()
                    self._load_schedules()
                    
                except ValueError:
                    messagebox.showerror("Error", "Please enter a valid number")
                except Exception as e:
                    logger.error(f"Error saving schedule: {e}")
                    messagebox.showerror("Error", f"Failed to save:\n{e}")
            
            tk.Button(
                dialog,
                text="💾 Save Changes",
                font=('Arial', 11),
                bg='#0066cc',
                fg='#ffffff',
                activebackground='#0077dd',
                relief=tk.FLAT,
                padx=30,
                pady=10,
                command=save_changes
            ).pack(pady=20)
            
        except Exception as e:
            logger.error(f"Error editing schedule: {e}")
            messagebox.showerror("Error", f"Failed to edit schedule:\n{e}")
    
    def _delete_schedule(self, chore_id, chore_name):
        """Delete a chore/schedule"""
        result = messagebox.askyesno(
            "Confirm Delete",
            f"Are you sure you want to delete this chore?\n\n{chore_name}\n\nThis cannot be undone."
        )
        
        if not result:
            return
        
        try:
            with self.chore_db.conn.cursor() as cursor:
                cursor.execute("DELETE FROM chores WHERE id = %s", (chore_id,))
                self.chore_db.conn.commit()
            
            logger.info(f"Deleted chore {chore_id}")
            messagebox.showinfo("Success", "Chore deleted successfully")
            
            # Refresh display
            self._load_schedules()
            
        except Exception as e:
            logger.error(f"Error deleting chore: {e}")
            messagebox.showerror("Error", f"Failed to delete chore:\n{e}")
    
    def _refresh_schedules(self):
        """Refresh the schedules list"""
        self._load_schedules()
        messagebox.showinfo("Refreshed", "Schedules list has been refreshed")
    
    def _add_new_schedule(self):
        """Open dialog to add a new schedule"""
        messagebox.showinfo(
            "Coming Soon",
            "Add New Schedule feature coming soon!\n\nFor now, schedules are created automatically when you:\n• Set reminders\n• Configure PLC monitoring\n• Enable automated tasks"
        )
    
    def _create_about_tab(self, parent):
        """Create about/info tab"""
        
        tk.Label(
            parent,
            text="Grok Agent - Phase 3",
            bg='#2b2b2b',
            fg='white',
            font=('Arial', 16, 'bold')
        ).pack(pady=30)
        
        tk.Label(
            parent,
            text="Embodied AI Agent with PLC Control",
            bg='#2b2b2b',
            fg='#aaaaaa',
            font=('Arial', 12)
        ).pack()
        
        # Dependencies status
        status_frame = tk.LabelFrame(
            parent,
            text="Dependencies Status",
            bg='#1e1e1e',
            fg='white',
            font=('Arial', 10, 'bold')
        )
        status_frame.pack(fill=tk.X, padx=40, pady=30)
        
        deps = [
            ("pycomm3 (PLC Communication)", self._check_pycomm3()),
            ("geopy (Location Lookup)", self._geocoder_available),
            ("astral (Sunrise/Sunset)", self._astral_available),
            ("gtts (Online TTS)", self._check_gtts()),
            ("pydub (Audio Processing)", self._check_pydub()),
        ]
        
        for name, available in deps:
            color = '#00ff00' if available else '#ff0000'
            status = "✅ Installed" if available else "❌ Not Installed"
            
            row = tk.Frame(status_frame, bg='#1e1e1e')
            row.pack(fill=tk.X, padx=10, pady=5)
            
            tk.Label(row, text=name, bg='#1e1e1e', fg='white', font=('Arial', 10), width=30, anchor='w').pack(side=tk.LEFT)
            tk.Label(row, text=status, bg='#1e1e1e', fg=color, font=('Arial', 10)).pack(side=tk.LEFT)
        
        # Install commands
        tk.Label(
            parent,
            text="Install missing dependencies with:",
            bg='#2b2b2b',
            fg='#aaaaaa',
            font=('Arial', 10)
        ).pack(pady=(20, 5))
        
        cmd_text = "pip install pycomm3 geopy astral gtts pydub"
        cmd_label = tk.Label(
            parent,
            text=cmd_text,
            bg='#1e1e1e',
            fg='#00ff00',
            font=('Consolas', 10),
            padx=10,
            pady=5
        )
        cmd_label.pack()
    
    def _check_pycomm3(self) -> bool:
        """Check if pycomm3 is available"""
        try:
            import pycomm3
            return True
        except ImportError:
            return False
    
    def _check_gtts(self) -> bool:
        """Check if gtts is available"""
        try:
            from gtts import gTTS
            return True
        except ImportError:
            return False
    
    def _check_pydub(self) -> bool:
        """Check if pydub is available"""
        try:
            from pydub import AudioSegment
            return True
        except ImportError:
            return False
    
    def _load_settings(self):
        """Load current settings from database"""
        try:
            # Location settings
            location = self.chore_db.get_location()
            
            if location.get('city'):
                self.city_entry.insert(0, location['city'])
            if location.get('zip'):
                self.zip_entry.insert(0, location['zip'])
            if location.get('lat'):
                self.lat_entry.insert(0, location['lat'])
            if location.get('lon'):
                self.lon_entry.insert(0, location['lon'])
            if location.get('timezone'):
                self.tz_combo.set(location['timezone'])
            
            # Email settings
            email_enabled = self.chore_db.get_setting('email_enabled')
            self.email_enabled_var.set(email_enabled == 'true')
            
            email_addr = self.chore_db.get_setting('email_address')
            if email_addr:
                self.email_entry.insert(0, email_addr)
            
            email_pass = self.chore_db.get_setting('email_password')
            if email_pass:
                self.password_entry.insert(0, email_pass)
            
            # Load recipient list
            recipients_str = self.chore_db.get_setting('email_recipients')
            if recipients_str:
                self.email_list = [e.strip() for e in recipients_str.split(',') if e.strip()]
                for email in self.email_list:
                    self.recipients_listbox.insert(tk.END, email)
            
            # Update email fields state
            self._toggle_email_fields()
            
            # Identity settings
            saved_user = self.chore_db.get_setting('user_name')
            if saved_user and hasattr(self, 'user_name_entry'):
                self.user_name_entry.delete(0, tk.END)
                self.user_name_entry.insert(0, saved_user)

        except Exception as e:
            logger.error(f"Error loading settings: {e}")
    
    def _toggle_email_fields(self):
        """Enable/disable email fields based on checkbox"""
        state = tk.NORMAL if self.email_enabled_var.get() else tk.DISABLED
        
        self.email_entry.config(state=state)
        self.password_entry.config(state=state)
    
    def _toggle_password_visibility(self):
        """Show/hide password"""
        if self.show_pass_var.get():
            self.password_entry.config(show='')
        else:
            self.password_entry.config(show='*')
    
    def _lookup_location(self):
        """Look up coordinates from city/zip"""
        if not self._geocoder_available:
            messagebox.showwarning(
                "Not Available",
                "geopy is not installed.\nInstall with: pip install geopy"
            )
            return
        
        city = self.city_entry.get().strip()
        state = self.state_entry.get().strip()
        zip_code = self.zip_entry.get().strip()
        
        if not city and not zip_code:
            messagebox.showwarning("Warning", "Enter a city or ZIP code")
            return
        
        # Build query
        if zip_code:
            query = f"{zip_code}, USA"
        elif state:
            query = f"{city}, {state}, USA"
        else:
            query = f"{city}, USA"
        
        self.location_status.config(text="🔍 Looking up location...", fg='#ffaa00')
        self.window.update()
        
        def do_lookup():
            try:
                from geopy.geocoders import Nominatim
                
                geolocator = Nominatim(user_agent="grok_agent")
                location = geolocator.geocode(query)
                
                if location:
                    result = {
                        'lat': location.latitude,
                        'lon': location.longitude,
                        'address': location.address
                    }
                    self.window.after(0, lambda: self._handle_lookup_result(result))
                else:
                    self.window.after(0, lambda: self._handle_lookup_result(None))
                    
            except Exception as e:
                self.window.after(0, lambda: self._handle_lookup_error(str(e)))
        
        threading.Thread(target=do_lookup, daemon=True).start()
    
    def _handle_lookup_result(self, result: Optional[Dict]):
        """Handle geocoding result"""
        if result:
            # Update entries
            self.lat_entry.delete(0, tk.END)
            self.lat_entry.insert(0, f"{result['lat']:.6f}")
            
            self.lon_entry.delete(0, tk.END)
            self.lon_entry.insert(0, f"{result['lon']:.6f}")
            
            self.location_status.config(
                text=f"✅ Found: {result['address'][:60]}...",
                fg='#00ff00'
            )
        else:
            self.location_status.config(text="❌ Location not found", fg='#ff0000')
    
    def _handle_lookup_error(self, error: str):
        """Handle geocoding error"""
        self.location_status.config(text=f"❌ Error: {error}", fg='#ff0000')
    
    def _test_sun_times(self):
        """Test sunrise/sunset calculation"""
        if not self._astral_available:
            messagebox.showwarning(
                "Not Available",
                "astral is not installed.\nInstall with: pip install astral"
            )
            return
        
        try:
            lat = float(self.lat_entry.get())
            lon = float(self.lon_entry.get())
        except ValueError:
            messagebox.showwarning("Warning", "Enter valid coordinates first")
            return
        
        try:
            from astral import LocationInfo
            from astral.sun import sun
            from datetime import datetime
            import pytz
            
            # Get timezone
            tz_name = self.tz_combo.get()
            tz = pytz.timezone(tz_name)
            
            # Create location
            city = self.city_entry.get() or "Location"
            loc = LocationInfo(city, "USA", tz_name, lat, lon)
            
            # Get sun times for today
            s = sun(loc.observer, date=datetime.now(tz).date(), tzinfo=tz)
            
            sunrise = s['sunrise'].strftime('%I:%M %p')
            sunset = s['sunset'].strftime('%I:%M %p')
            
            self.location_status.config(
                text=f"🌅 Sunrise: {sunrise}  |  🌇 Sunset: {sunset}",
                fg='#00ff00'
            )
            
        except Exception as e:
            self.location_status.config(text=f"❌ Error: {e}", fg='#ff0000')
    
    def _save_location(self):
        """Save location settings"""
        try:
            city = self.city_entry.get().strip()
            zip_code = self.zip_entry.get().strip()
            lat = self.lat_entry.get().strip()
            lon = self.lon_entry.get().strip()
            timezone = self.tz_combo.get()
            
            self.chore_db.set_location(
                city=city,
                zip_code=zip_code,
                lat=lat,
                lon=lon,
                timezone=timezone
            )
            
            self.location_status.config(text="✅ Location settings saved!", fg='#00ff00')
            logger.info("Location settings saved")
            
        except Exception as e:
            self.location_status.config(text=f"❌ Error saving: {e}", fg='#ff0000')
            logger.error(f"Error saving location: {e}")
    
    def _test_email(self):
        """Send a test email to all recipients"""
        if not self.email_enabled_var.get():
            messagebox.showwarning("Warning", "Enable email first")
            return
        
        email = self.email_entry.get().strip()
        password = self.password_entry.get().strip()
        
        if not email or not password:
            messagebox.showwarning("Warning", "Enter sender email and password")
            return
        
        if not self.email_list:
            messagebox.showwarning("Warning", "Add at least one recipient email")
            return
        
        self.email_status.config(text="📤 Sending test email...", fg='#ffaa00')
        self.window.update()
        
        def do_send():
            try:
                import smtplib
                from email.mime.text import MIMEText
                from email.mime.multipart import MIMEMultipart
                from datetime import datetime
                
                # Create message
                msg = MIMEMultipart()
                msg['From'] = email
                msg['To'] = ', '.join(self.email_list)
                msg['Subject'] = "Grok Agent - Test Email"
                
                body = f"""
Hello!

This is a test email from Grok Agent.

If you received this, your email settings are configured correctly!

Recipients: {', '.join(self.email_list)}

Sent at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

- Grok Agent
                """
                msg.attach(MIMEText(body, 'plain'))
                
                # Send via Gmail SMTP
                server = smtplib.SMTP('smtp.gmail.com', 587)
                server.starttls()
                server.login(email, password)
                server.send_message(msg)
                server.quit()
                
                self.window.after(0, lambda: self._handle_email_success())
                
            except Exception as e:
                self.window.after(0, lambda: self._handle_email_error(str(e)))
        
        threading.Thread(target=do_send, daemon=True).start()
    
    def _handle_email_success(self):
        """Handle successful email send"""
        count = len(self.email_list)
        self.email_status.config(text=f"✅ Test email sent to {count} recipient(s)!", fg='#00ff00')
    
    def _handle_email_error(self, error: str):
        """Handle email error"""
        self.email_status.config(text=f"❌ Failed: {error[:50]}...", fg='#ff0000')
        
        if "Username and Password not accepted" in error:
            messagebox.showerror(
                "Authentication Failed",
                "Gmail rejected the login.\n\nMake sure you're using an App Password, not your regular password.\n\nSee the instructions below the form."
            )
    
    def _save_email(self):
        """Save email settings"""
        try:
            enabled = 'true' if self.email_enabled_var.get() else 'false'
            email = self.email_entry.get().strip()
            password = self.password_entry.get().strip()
            
            # Save as comma-separated list
            recipients_str = ','.join(self.email_list)
            
            self.chore_db.set_setting('email_enabled', enabled, 'boolean')
            self.chore_db.set_setting('email_address', email)
            self.chore_db.set_setting('email_password', password)  # Note: In production, encrypt this!
            self.chore_db.set_setting('email_recipients', recipients_str)
            self.chore_db.set_setting('email_smtp_server', 'smtp.gmail.com')
            self.chore_db.set_setting('email_smtp_port', '587', 'integer')
            
            self.email_status.config(text="✅ Email settings saved!", fg='#00ff00')
            logger.info(f"Email settings saved with {len(self.email_list)} recipients")
            
        except Exception as e:
            self.email_status.config(text=f"❌ Error saving: {e}", fg='#ff0000')
            logger.error(f"Error saving email: {e}")
    
    def _on_closing(self):
        """Handle window close"""
        if self.on_close_callback:
            self.on_close_callback()
        self.window.destroy()
    
    def show(self):
        """Show the window"""
        self.window.deiconify()
        self.window.lift()
        self.window.focus_force()


def open_settings_window(chore_db, on_close=None):
    """
    Open the Settings window
    
    Args:
        chore_db: ChoreDatabase instance
        on_close: Optional callback when window closes
    
    Returns:
        SettingsWindow instance
    """
    return SettingsWindow(chore_db, on_close)