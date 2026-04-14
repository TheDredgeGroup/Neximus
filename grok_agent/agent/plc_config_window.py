"""
PLC Configuration Window - Enhanced with Optimizations
Tabbed interface for PLC management, optimization suggestions, and version control
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import threading
import logging
import json
from typing import Optional, Callable, Dict, List
from datetime import datetime

# Import the optimization manager
try:
    from optimization_manager import OptimizationManager
except ImportError:
    OptimizationManager = None

# Import control loop
try:
    from controlloop import get_loop, initialize_control_loop
    CONTROLLOOP_AVAILABLE = True
except ImportError:
    CONTROLLOOP_AVAILABLE = False

# Import program manager
try:
    from program_manager import ProgramManager
except ImportError:
    ProgramManager = None

logger = logging.getLogger(__name__)

# Categories for optimization suggestions
CATEGORIES = ['Energy', 'Efficiency', 'Quality', 'Safety', 'Maintenance', 'Cost', 'Environmental', 'Operational']
PRIORITIES = ['Low', 'Medium', 'High', 'Critical']
STATUSES = ['Idea', 'Proposed', 'Approved', 'Implemented', 'Monitoring', 'Verified', 'Rejected', 'OnHold']


class PLCConfigWindow:
    """Enhanced PLC Configuration Window with tabs"""
    
    def __init__(self, chore_db, plc_comm, on_close_callback: Callable = None):
        """
        Initialize PLC Configuration Window
        
        Args:
            chore_db: ChoreDatabase instance
            plc_comm: PLCCommunicator instance
            on_close_callback: Optional callback when window closes
        """
        self.chore_db = chore_db
        self.plc_comm = plc_comm
        self.on_close_callback = on_close_callback
        
        # Initialize optimization manager
        if OptimizationManager:
            self.opt_manager = OptimizationManager(chore_db)
        else:
            self.opt_manager = None
            logger.warning("OptimizationManager not available")
        
        # Initialize program manager
        if ProgramManager:
            self.program_manager = ProgramManager(chore_db)
        else:
            self.program_manager = None
            logger.warning("ProgramManager not available")
        
        # Currently selected PLC
        self.selected_plc_id = None
        
        # Currently selected suggestion
        self.selected_suggestion_id = None
        
        # Currently selected version
        self.selected_version_id = None
        
        # Create window
        self.window = tk.Toplevel()
        self.window.title("PLC Configuration & Optimization")
        self.window.geometry("1200x800")
        self.window.configure(bg='#2b2b2b')
        
        # Handle window close
        self.window.protocol("WM_DELETE_WINDOW", self._on_closing)
        
        # Build UI
        self._create_widgets()
        
        # Load existing PLCs
        self._refresh_plc_list()
    
    def _create_widgets(self):
        """Create all GUI widgets with tabbed interface"""
        
        # Main container with PLC list on left
        main_frame = tk.Frame(self.window, bg='#2b2b2b')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # ===== LEFT PANEL: PLC List (same for all tabs) =====
        left_frame = tk.Frame(main_frame, bg='#1e1e1e', width=250)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        left_frame.pack_propagate(False)
        
        self._create_plc_list_panel(left_frame)
        
        # ===== RIGHT PANEL: Tabbed Interface =====
        right_frame = tk.Frame(main_frame, bg='#1e1e1e')
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Create notebook for tabs
        style = ttk.Style()
        style.theme_use('default')
        style.configure('TNotebook', background='#1e1e1e', borderwidth=0)
        style.configure('TNotebook.Tab', background='#2b2b2b', foreground='white', 
                       padding=[20, 10], font=('Arial', 10, 'bold'))
        style.map('TNotebook.Tab', background=[('selected', '#0066cc')])
        
        self.notebook = ttk.Notebook(right_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Tab 1: PLC & Tags
        self.plc_tags_frame = tk.Frame(self.notebook, bg='#1e1e1e')
        self.notebook.add(self.plc_tags_frame, text=" PLC & Tags ")
        self._create_plc_tags_tab()
        
        # Tab 2: Optimizations
        self.optimizations_frame = tk.Frame(self.notebook, bg='#1e1e1e')
        self.notebook.add(self.optimizations_frame, text="  Optimizations ")
        self._create_optimizations_tab()
        
        # Tab 3: Versions (placeholder for future program upload feature)
        self.versions_frame = tk.Frame(self.notebook, bg='#1e1e1e')
        self.notebook.add(self.versions_frame, text=" Versions ")
        self._create_versions_tab()

        # Tab 4: Control Loop
        self.control_loop_frame = tk.Frame(self.notebook, bg='#1e1e1e')
        self.notebook.add(self.control_loop_frame, text=" Control Loop ")
        self._create_control_loop_tab()
    
    def _create_plc_list_panel(self, parent):
        """Create the PLC list panel (left side)"""
        # Header
        header_frame = tk.Frame(parent, bg='#1e1e1e')
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Label(
            header_frame,
            text=" PLC Connections",
            bg='#1e1e1e',
            fg='white',
            font=('Arial', 12, 'bold')
        ).pack(side=tk.LEFT)
        
        # Add PLC button
        tk.Button(
            header_frame,
            text="+ Add",
            command=self._add_plc,
            bg='#00aa00',
            fg='white',
            font=('Arial', 10, 'bold'),
            width=8
        ).pack(side=tk.RIGHT)
        
        # PLC Listbox with scrollbar
        list_frame = tk.Frame(parent, bg='#1e1e1e')
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.plc_listbox = tk.Listbox(
            list_frame,
            bg='#2b2b2b',
            fg='white',
            font=('Consolas', 10),
            selectbackground='#0066cc',
            selectforeground='white',
            yscrollcommand=scrollbar.set,
            height=20
        )
        self.plc_listbox.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.plc_listbox.yview)
        
        self.plc_listbox.bind('<<ListboxSelect>>', self._on_plc_select)
        
        # Delete PLC button
        tk.Button(
            parent,
            text=" Delete Selected PLC",
            command=self._delete_plc,
            bg='#aa0000',
            fg='white',
            font=('Arial', 10, 'bold')
        ).pack(fill=tk.X, padx=10, pady=(0, 10))
    
    def _create_plc_tags_tab(self):
        """Create Tab 1: PLC & Tags (existing functionality)"""
        # This contains the existing PLC details and tag management
        # I'll keep the structure similar to your original file
        
        # ===== PLC Details Section =====
        details_frame = tk.LabelFrame(
            self.plc_tags_frame,
            text="PLC Details",
            bg='#1e1e1e',
            fg='white',
            font=('Arial', 11, 'bold')
        )
        details_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Form grid
        form_frame = tk.Frame(details_frame, bg='#1e1e1e')
        form_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Row 0: Name
        tk.Label(form_frame, text="Name:", bg='#1e1e1e', fg='white', font=('Arial', 10)).grid(row=0, column=0, sticky='e', padx=5, pady=5)
        self.name_entry = tk.Entry(form_frame, bg='#2b2b2b', fg='white', font=('Arial', 10), width=30, insertbackground='white')
        self.name_entry.grid(row=0, column=1, sticky='w', padx=5, pady=5)
        
        # Row 1: IP Address
        tk.Label(form_frame, text="IP Address:", bg='#1e1e1e', fg='white', font=('Arial', 10)).grid(row=1, column=0, sticky='e', padx=5, pady=5)
        self.ip_entry = tk.Entry(form_frame, bg='#2b2b2b', fg='white', font=('Arial', 10), width=30, insertbackground='white')
        self.ip_entry.grid(row=1, column=1, sticky='w', padx=5, pady=5)
        
        # Row 2: Slot
        tk.Label(form_frame, text="Slot:", bg='#1e1e1e', fg='white', font=('Arial', 10)).grid(row=2, column=0, sticky='e', padx=5, pady=5)
        self.slot_entry = tk.Entry(form_frame, bg='#2b2b2b', fg='white', font=('Arial', 10), width=10, insertbackground='white')
        self.slot_entry.insert(0, "0")
        self.slot_entry.grid(row=2, column=1, sticky='w', padx=5, pady=5)
        
        # Row 3: PLC Type
        tk.Label(form_frame, text="PLC Type:", bg='#1e1e1e', fg='white', font=('Arial', 10)).grid(row=3, column=0, sticky='e', padx=5, pady=5)
        self.type_combo = ttk.Combobox(form_frame, values=['CompactLogix', 'ControlLogix', 'MicroLogix', 'Micro800'], width=27, state='readonly')
        self.type_combo.set('CompactLogix')
        self.type_combo.grid(row=3, column=1, sticky='w', padx=5, pady=5)
        
        # Row 4: Description
        tk.Label(form_frame, text="Description:", bg='#1e1e1e', fg='white', font=('Arial', 10)).grid(row=4, column=0, sticky='e', padx=5, pady=5)
        self.desc_entry = tk.Entry(form_frame, bg='#2b2b2b', fg='white', font=('Arial', 10), width=40, insertbackground='white')
        self.desc_entry.grid(row=4, column=1, sticky='w', padx=5, pady=5)

        # Row 5: Collaborate Output - PLC dropdown
        tk.Label(form_frame, text="Collab PLC:", bg='#1e1e1e', fg='white', font=('Arial', 10)).grid(row=5, column=0, sticky='e', padx=5, pady=5)
        self.collab_plc_combo = ttk.Combobox(form_frame, width=28, state='readonly', font=('Consolas', 10))
        self.collab_plc_combo.grid(row=5, column=1, sticky='w', padx=5, pady=5)
        self.collab_plc_combo.bind('<<ComboboxSelected>>', self._on_collab_plc_selected)

        # Row 6: Collaborate Output - Tag dropdown
        tk.Label(form_frame, text="Collab Tag:", bg='#1e1e1e', fg='white', font=('Arial', 10)).grid(row=6, column=0, sticky='e', padx=5, pady=5)
        collab_tag_frame = tk.Frame(form_frame, bg='#1e1e1e')
        collab_tag_frame.grid(row=6, column=1, sticky='w', padx=5, pady=5)
        self.collab_tag_combo = ttk.Combobox(collab_tag_frame, width=28, state='readonly', font=('Consolas', 10))
        self.collab_tag_combo.pack(side=tk.LEFT, padx=(0, 5))
        tk.Button(collab_tag_frame, text="Save", command=self._save_collab_format,
                  bg='#0066cc', fg='white', font=('Arial', 9, 'bold'), width=6).pack(side=tk.LEFT)

        # Internal storage for collab plc list
        self._collab_plc_list = []

        # Load PLCs and restore saved selection
        self._load_collab_plcs()

        # Buttons row
        btn_frame = tk.Frame(details_frame, bg='#1e1e1e')
        btn_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        tk.Button(
            btn_frame,
            text=" Save PLC",
            command=self._save_plc,
            bg='#0066cc',
            fg='white',
            font=('Arial', 10, 'bold'),
            width=12
        ).pack(side=tk.LEFT, padx=5)
        
        tk.Button(
            btn_frame,
            text=" Test Connection",
            command=self._test_connection,
            bg='#006600',
            fg='white',
            font=('Arial', 10, 'bold'),
            width=15
        ).pack(side=tk.LEFT, padx=5)
        
        # Connection status label
        self.status_label = tk.Label(
            btn_frame,
            text="",
            bg='#1e1e1e',
            fg='#aaaaaa',
            font=('Arial', 10)
        )
        self.status_label.pack(side=tk.LEFT, padx=20)
        
        # ===== Tags Section =====
        tags_frame = tk.LabelFrame(
            self.plc_tags_frame,
            text="PLC Tags",
            bg='#1e1e1e',
            fg='white',
            font=('Arial', 11, 'bold')
        )
        tags_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        # Tags toolbar
        tags_toolbar = tk.Frame(tags_frame, bg='#1e1e1e')
        tags_toolbar.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Button(
            tags_toolbar,
            text="+ Add Tag",
            command=self._add_tag,
            bg='#00aa00',
            fg='white',
            font=('Arial', 10, 'bold'),
            width=10
        ).pack(side=tk.LEFT, padx=5)
        
        tk.Button(
            tags_toolbar,
            text=" Edit",
            command=self._edit_tag,
            bg='#0066cc',
            fg='white',
            font=('Arial', 10, 'bold'),
            width=10
        ).pack(side=tk.LEFT, padx=5)
        
        tk.Button(
            tags_toolbar,
            text=" Delete",
            command=self._delete_tag,
            bg='#aa0000',
            fg='white',
            font=('Arial', 10, 'bold'),
            width=10
        ).pack(side=tk.LEFT, padx=5)
        
        tk.Button(
            tags_toolbar,
            text=" Read",
            command=self._read_tag_value,
            bg='#006666',
            fg='white',
            font=('Arial', 10, 'bold'),
            width=10
        ).pack(side=tk.LEFT, padx=5)
        
        # Tags table
        table_frame = tk.Frame(tags_frame, bg='#1e1e1e')
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        # Scrollbars
        y_scroll = tk.Scrollbar(table_frame, orient=tk.VERTICAL)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        x_scroll = tk.Scrollbar(table_frame, orient=tk.HORIZONTAL)
        x_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Treeview for tags
        self.tags_tree = ttk.Treeview(
            table_frame,
            columns=('tag_name', 'type', 'access', 'value', 'keywords'),
            show='headings',
            yscrollcommand=y_scroll.set,
            xscrollcommand=x_scroll.set,
            height=15
        )
        
        self.tags_tree.heading('tag_name', text='Tag Name')
        self.tags_tree.heading('type', text='Type')
        self.tags_tree.heading('access', text='Access')
        self.tags_tree.heading('value', text='Value')
        self.tags_tree.heading('keywords', text='Keywords')
        
        self.tags_tree.column('tag_name', width=150)
        self.tags_tree.column('type', width=80)
        self.tags_tree.column('access', width=100)
        self.tags_tree.column('value', width=100)
        self.tags_tree.column('keywords', width=300)
        
        self.tags_tree.pack(fill=tk.BOTH, expand=True)
        
        y_scroll.config(command=self.tags_tree.yview)
        x_scroll.config(command=self.tags_tree.xview)
        
        # Double-click to edit
        self.tags_tree.bind('<Double-1>', lambda e: self._edit_tag())
    
    def _create_optimizations_tab(self):
        """Create Tab 2: Optimization Suggestions"""
        
        # Toolbar at top
        toolbar = tk.Frame(self.optimizations_frame, bg='#1e1e1e')
        toolbar.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Button(
            toolbar,
            text=" Add Suggestion",
            command=self._add_suggestion,
            bg='#00aa00',
            fg='white',
            font=('Arial', 10, 'bold'),
            width=15
        ).pack(side=tk.LEFT, padx=5)
        
        tk.Button(
            toolbar,
            text=" Import from Agent",
            command=self._import_agent_suggestions,
            bg='#0066cc',
            fg='white',
            font=('Arial', 10, 'bold'),
            width=18
        ).pack(side=tk.LEFT, padx=5)
        
        tk.Button(
            toolbar,
            text=" Export",
            command=self._export_suggestions,
            bg='#666666',
            fg='white',
            font=('Arial', 10, 'bold'),
            width=10
        ).pack(side=tk.LEFT, padx=5)
        
        # Filter controls
        filter_frame = tk.Frame(self.optimizations_frame, bg='#1e1e1e')
        filter_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        tk.Label(filter_frame, text="Category:", bg='#1e1e1e', fg='white').pack(side=tk.LEFT, padx=5)
        self.opt_category_combo = ttk.Combobox(filter_frame, values=['All'] + CATEGORIES, width=12, state='readonly')
        self.opt_category_combo.set('All')
        self.opt_category_combo.pack(side=tk.LEFT, padx=5)
        self.opt_category_combo.bind('<<ComboboxSelected>>', lambda e: self._refresh_suggestions_list())
        
        tk.Label(filter_frame, text="Status:", bg='#1e1e1e', fg='white').pack(side=tk.LEFT, padx=5)
        self.opt_status_combo = ttk.Combobox(filter_frame, values=['All'] + STATUSES, width=12, state='readonly')
        self.opt_status_combo.set('All')
        self.opt_status_combo.pack(side=tk.LEFT, padx=5)
        self.opt_status_combo.bind('<<ComboboxSelected>>', lambda e: self._refresh_suggestions_list())
        
        tk.Label(filter_frame, text="Priority:", bg='#1e1e1e', fg='white').pack(side=tk.LEFT, padx=5)
        self.opt_priority_combo = ttk.Combobox(filter_frame, values=['All'] + PRIORITIES, width=12, state='readonly')
        self.opt_priority_combo.set('All')
        self.opt_priority_combo.pack(side=tk.LEFT, padx=5)
        self.opt_priority_combo.bind('<<ComboboxSelected>>', lambda e: self._refresh_suggestions_list())
        
        tk.Label(filter_frame, text="Search:", bg='#1e1e1e', fg='white').pack(side=tk.LEFT, padx=5)
        self.opt_search_entry = tk.Entry(filter_frame, bg='#2b2b2b', fg='white', width=20, insertbackground='white')
        self.opt_search_entry.pack(side=tk.LEFT, padx=5)
        self.opt_search_entry.bind('<KeyRelease>', lambda e: self._refresh_suggestions_list())
        
        # Suggestions list (table)
        list_frame = tk.Frame(self.optimizations_frame, bg='#1e1e1e')
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        # Scrollbars
        y_scroll = tk.Scrollbar(list_frame, orient=tk.VERTICAL)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Treeview for suggestions
        self.suggestions_tree = ttk.Treeview(
            list_frame,
            columns=('id', 'title', 'category', 'priority', 'status'),
            show='headings',
            yscrollcommand=y_scroll.set,
            height=10
        )
        
        self.suggestions_tree.heading('id', text='ID')
        self.suggestions_tree.heading('title', text='Title')
        self.suggestions_tree.heading('category', text='Category')
        self.suggestions_tree.heading('priority', text='Priority')
        self.suggestions_tree.heading('status', text='Status')
        
        self.suggestions_tree.column('id', width=50)
        self.suggestions_tree.column('title', width=300)
        self.suggestions_tree.column('category', width=100)
        self.suggestions_tree.column('priority', width=80)
        self.suggestions_tree.column('status', width=100)
        
        self.suggestions_tree.pack(fill=tk.BOTH, expand=True)
        y_scroll.config(command=self.suggestions_tree.yview)
        
        self.suggestions_tree.bind('<<TreeviewSelect>>', self._on_suggestion_select)
        self.suggestions_tree.bind('<Double-1>', lambda e: self._edit_suggestion())
        
        # Details panel
        details_frame = tk.LabelFrame(
            self.optimizations_frame,
            text="Selected Suggestion Details",
            bg='#1e1e1e',
            fg='white',
            font=('Arial', 11, 'bold')
        )
        details_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        # Scrollable text for details
        self.suggestion_details_text = scrolledtext.ScrolledText(
            details_frame,
            bg='#2b2b2b',
            fg='white',
            font=('Consolas', 10),
            wrap=tk.WORD,
            height=10
        )
        self.suggestion_details_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Action buttons
        actions_frame = tk.Frame(self.optimizations_frame, bg='#1e1e1e')
        actions_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        tk.Button(
            actions_frame,
            text=" Edit",
            command=self._edit_suggestion,
            bg='#0066cc',
            fg='white',
            font=('Arial', 10, 'bold'),
            width=12
        ).pack(side=tk.LEFT, padx=5)
        
        tk.Button(
            actions_frame,
            text=" Delete",
            command=self._delete_suggestion,
            bg='#aa0000',
            fg='white',
            font=('Arial', 10, 'bold'),
            width=12
        ).pack(side=tk.LEFT, padx=5)
        
        tk.Button(
            actions_frame,
            text=" Change Status",
            command=self._change_suggestion_status,
            bg='#cc6600',
            fg='white',
            font=('Arial', 10, 'bold'),
            width=15
        ).pack(side=tk.LEFT, padx=5)
        
        tk.Button(
            actions_frame,
            text=" View History",
            command=self._view_suggestion_history,
            bg='#666666',
            fg='white',
            font=('Arial', 10, 'bold'),
            width=15
        ).pack(side=tk.LEFT, padx=5)
        
        # Load suggestions
        self._refresh_suggestions_list()
    
    def _create_versions_tab(self):
        """Create Tab 3: Program Versions"""
        
        # Toolbar
        toolbar = tk.Frame(self.versions_frame, bg='#1e1e1e')
        toolbar.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Button(
            toolbar,
            text=" Upload Program",
            command=self._upload_program,
            bg='#0066cc',
            fg='white',
            font=('Arial', 10, 'bold'),
            width=15
        ).pack(side=tk.LEFT, padx=5)
        
        tk.Button(
            toolbar,
            text=" Compare Versions",
            command=self._compare_versions,
            bg='#006600',
            fg='white',
            font=('Arial', 10, 'bold'),
            width=18
        ).pack(side=tk.LEFT, padx=5)
        
        tk.Button(
            toolbar,
            text=" Delete",
            command=self._delete_version,
            bg='#aa0000',
            fg='white',
            font=('Arial', 10, 'bold'),
            width=12
        ).pack(side=tk.LEFT, padx=5)
        
        # Version list
        list_frame = tk.Frame(self.versions_frame, bg='#1e1e1e')
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        # Scrollbars
        y_scroll = tk.Scrollbar(list_frame, orient=tk.VERTICAL)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Treeview for versions
        self.versions_tree = ttk.Treeview(
            list_frame,
            columns=('version', 'program', 'timestamp', 'uploaded_by', 'revision'),
            show='headings',
            yscrollcommand=y_scroll.set,
            height=10
        )
        
        self.versions_tree.heading('version', text='Version')
        self.versions_tree.heading('program', text='Program Name')
        self.versions_tree.heading('timestamp', text='Upload Time')
        self.versions_tree.heading('uploaded_by', text='Uploaded By')
        self.versions_tree.heading('revision', text='Revision')
        
        self.versions_tree.column('version', width=80)
        self.versions_tree.column('program', width=200)
        self.versions_tree.column('timestamp', width=150)
        self.versions_tree.column('uploaded_by', width=120)
        self.versions_tree.column('revision', width=100)
        
        self.versions_tree.pack(fill=tk.BOTH, expand=True)
        y_scroll.config(command=self.versions_tree.yview)
        
        self.versions_tree.bind('<<TreeviewSelect>>', self._on_version_select)
        self.versions_tree.bind('<Double-1>', lambda e: self._view_version_details())
        
        # Details panel
        details_frame = tk.LabelFrame(
            self.versions_frame,
            text="Version Details",
            bg='#1e1e1e',
            fg='white',
            font=('Arial', 11, 'bold')
        )
        details_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        self.version_details_text = scrolledtext.ScrolledText(
            details_frame,
            bg='#2b2b2b',
            fg='white',
            font=('Consolas', 10),
            wrap=tk.WORD,
            height=8
        )
        self.version_details_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Action buttons
        actions_frame = tk.Frame(self.versions_frame, bg='#1e1e1e')
        actions_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        tk.Button(
            actions_frame,
            text=" View Details",
            command=self._view_version_details,
            bg='#0066cc',
            fg='white',
            font=('Arial', 10, 'bold'),
            width=15
        ).pack(side=tk.LEFT, padx=5)
        
        tk.Button(
            actions_frame,
            text=" Browse Routines",
            command=self._browse_routines,
            bg='#006600',
            fg='white',
            font=('Arial', 10, 'bold'),
            width=15
        ).pack(side=tk.LEFT, padx=5)
        
        tk.Button(
            actions_frame,
            text=" View Tags",
            command=self._view_program_tags,
            bg='#666666',
            fg='white',
            font=('Arial', 10, 'bold'),
            width=15
        ).pack(side=tk.LEFT, padx=5)
        
        # Load versions
        self._refresh_versions_list()
    
    # ========== PLC Management Methods (Tab 1) ==========
    
    def _refresh_plc_list(self):
        """Refresh the PLC list"""
        self.plc_listbox.delete(0, tk.END)
        
        plcs = self.chore_db.get_all_plcs()
        for plc in plcs:
            enabled_marker = "âœ“" if plc.get('enabled', True) else "âœ—"
            display = f"{enabled_marker} {plc['name']} ({plc['ip_address']})"
            self.plc_listbox.insert(tk.END, display)
    
    def _on_plc_select(self, event):
        """Handle PLC selection"""
        selection = self.plc_listbox.curselection()
        if not selection:
            return
        
        plcs = self.chore_db.get_all_plcs()
        if selection[0] < len(plcs):
            plc = plcs[selection[0]]
            self.selected_plc_id = plc['id']
            
            # Update form fields
            self.name_entry.delete(0, tk.END)
            self.name_entry.insert(0, plc.get('name', ''))
            
            self.ip_entry.delete(0, tk.END)
            self.ip_entry.insert(0, plc.get('ip_address', ''))
            
            self.slot_entry.delete(0, tk.END)
            self.slot_entry.insert(0, str(plc.get('slot', 0)))
            
            self.type_combo.set(plc.get('plc_type', 'CompactLogix'))
            
            self.desc_entry.delete(0, tk.END)
            self.desc_entry.insert(0, plc.get('description', ''))
            
            # Refresh tags
            self._refresh_tags_list()
            
            # Refresh versions list
            self._refresh_versions_list()
    
    def _add_plc(self):
        """Add new PLC"""
        # Clear form
        self.name_entry.delete(0, tk.END)
        self.ip_entry.delete(0, tk.END)
        self.slot_entry.delete(0, tk.END)
        self.slot_entry.insert(0, "0")
        self.type_combo.set('CompactLogix')
        self.desc_entry.delete(0, tk.END)
        self.selected_plc_id = None
        
        # Clear tags
        for item in self.tags_tree.get_children():
            self.tags_tree.delete(item)
    
    def _save_plc(self):
        """Save PLC configuration"""
        name = self.name_entry.get().strip()
        ip = self.ip_entry.get().strip()
        
        if not name or not ip:
            messagebox.showerror("Error", "Name and IP address are required")
            return
        
        try:
            slot = int(self.slot_entry.get())
        except:
            slot = 0
        
        plc_data = {
            'name': name,
            'ip_address': ip,
            'slot': slot,
            'plc_type': self.type_combo.get(),
            'description': self.desc_entry.get().strip(),
            'enabled': True
        }
        
        if self.selected_plc_id:
            # Update existing
            self.chore_db.update_plc(self.selected_plc_id, **plc_data)
            messagebox.showinfo("Success", f"Updated PLC: {name}")
        else:
            # Add new
            plc_id = self.chore_db.add_plc(
                name=plc_data['name'],
                ip_address=plc_data['ip_address'],
                plc_type=plc_data['plc_type'],
                slot=plc_data['slot'],
                description=plc_data['description']
            )
            self.selected_plc_id = plc_id
            messagebox.showinfo("Success", f"Added PLC: {name}")
        
        self._refresh_plc_list()
    
    def _load_collab_plcs(self):
        """Populate collab PLC dropdown and restore saved selections."""
        try:
            plcs = self.chore_db.get_all_plcs(enabled_only=False)
            self._collab_plc_list = plcs
            names = [f"{p['name']} ({p['ip_address']})" for p in plcs]
            self.collab_plc_combo['values'] = names

            # Restore saved PLC
            saved_plc_id  = self.chore_db.get_setting('cl_collab_plc_id')
            saved_tag_name = self.chore_db.get_setting('cl_collab_tag_name')

            selected_idx = 0
            if saved_plc_id:
                for i, p in enumerate(plcs):
                    if p['id'] == saved_plc_id:
                        selected_idx = i
                        break
            if names:
                self.collab_plc_combo.current(selected_idx)
                # Load tags for selected PLC
                plc = self._collab_plc_list[selected_idx]
                tags = self.chore_db.get_tags_for_plc(plc['id'])
                tag_names = [t['tag_name'] for t in tags]
                self.collab_tag_combo['values'] = tag_names
                # Restore saved tag
                if saved_tag_name and saved_tag_name in tag_names:
                    self.collab_tag_combo.current(tag_names.index(saved_tag_name))
                elif tag_names:
                    self.collab_tag_combo.current(0)
        except Exception as e:
            pass  # Non-fatal on startup

    def _on_collab_plc_selected(self, event=None):
        """Refresh tag dropdown when collab PLC changes."""
        idx = self.collab_plc_combo.current()
        if idx < 0 or idx >= len(self._collab_plc_list):
            return
        try:
            plc = self._collab_plc_list[idx]
            tags = self.chore_db.get_tags_for_plc(plc['id'])
            tag_names = [t['tag_name'] for t in tags]
            self.collab_tag_combo['values'] = tag_names
            if tag_names:
                self.collab_tag_combo.current(0)
        except Exception as e:
            pass

    def _save_collab_format(self):
        """Build and save collaborate format from selected PLC and tag."""
        idx = self.collab_plc_combo.current()
        tag_name = self.collab_tag_combo.get().strip()
        if idx < 0 or not tag_name:
            messagebox.showerror("Error", "Select a PLC and tag first")
            return
        try:
            plc = self._collab_plc_list[idx]
            # Build the format string
            fmt = f"[PLC:{plc['name']}|Tag:{tag_name}|Value:{{value}}]"
            self.chore_db.set_setting('cl_collaborate_format', fmt)
            self.chore_db.set_setting('cl_collab_plc_id', plc['id'])
            self.chore_db.set_setting('cl_collab_tag_name', tag_name)
            messagebox.showinfo("Saved", f"Collaborate format saved:\n{fmt}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save: {e}")

    def _delete_plc(self):
        """Delete selected PLC"""
        if not self.selected_plc_id:
            messagebox.showwarning("Warning", "No PLC selected")
            return
        
        plc = self.chore_db.get_plc(self.selected_plc_id)
        if not plc:
            return
        
        confirm = messagebox.askyesno(
            "Confirm Delete",
            f"Delete PLC '{plc['name']}' and all its tags?\nThis cannot be undone."
        )
        
        if confirm:
            self.chore_db.delete_plc(self.selected_plc_id)
            self.selected_plc_id = None
            self._refresh_plc_list()
            self._add_plc()  # Clear form
    
    def _test_connection(self):
        """Test PLC connection"""
        if not self.selected_plc_id:
            messagebox.showwarning("Warning", "Please save PLC first")
            return
        
        plc = self.chore_db.get_plc(self.selected_plc_id)
        if not plc:
            return
        
        self.status_label.config(text="Testing...", fg='#ffaa00')
        self.window.update()
        
        # Test in thread to avoid blocking
        def test_thread():
            try:
                result = self.plc_comm.test_connection(
                    plc['ip_address'],
                    plc['slot'],
                    plc['plc_type']
                )
                
                if result:
                    self.status_label.config(text=" Connected", fg='#00ff00')
                else:
                    self.status_label.config(text=" Failed", fg='#ff0000')
            except Exception as e:
                self.status_label.config(text=f"âœ— Error: {e}", fg='#ff0000')
        
        threading.Thread(target=test_thread, daemon=True).start()
    
    def _refresh_tags_list(self):
        """Refresh tags list for selected PLC"""
        # Clear existing
        for item in self.tags_tree.get_children():
            self.tags_tree.delete(item)
        
        if not self.selected_plc_id:
            return
        
        tags = self.chore_db.get_tags_for_plc(self.selected_plc_id)
        for tag in tags:
            # Truncate keywords for display
            keywords = tag.get('description', '')
            if keywords and len(keywords) > 50:
                keywords = keywords[:47] + "..."
            
            self.tags_tree.insert('', tk.END, values=(
                tag.get('tag_name', ''),
                tag.get('tag_type', ''),
                tag.get('access_type', ''),
                tag.get('last_value', ''),
                keywords
            ), tags=(tag.get('id'),))
    
    def _add_tag(self):
        """Add new tag"""
        if not self.selected_plc_id:
            messagebox.showwarning("Warning", "Please select a PLC first")
            return
        
        dialog = TagEditDialog(self.window, None)
        self.window.wait_window(dialog.dialog)
        
        if dialog.result:
            tag_data = dialog.result
            tag_data['plc_id'] = self.selected_plc_id
            tag_id = self.chore_db.add_tag(
                plc_id=tag_data['plc_id'],
                tag_name=tag_data['tag_name'],
                tag_type=tag_data['tag_type'],
                description=tag_data.get('description'),
                access_type=tag_data.get('access_type', 'read_write'),
                monitor=tag_data.get('monitor', False),
                read_keywords=tag_data.get('read_keywords'),
                write_keywords=tag_data.get('write_keywords'),
                on_keywords=tag_data.get('on_keywords'),
                off_keywords=tag_data.get('off_keywords')
            )
            self._refresh_tags_list()
    
    def _edit_tag(self):
        """Edit selected tag"""
        selection = self.tags_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a tag")
            return
        
        item = self.tags_tree.item(selection[0])
        tag_id = item['tags'][0]
        tag = self.chore_db.get_tag_by_id(tag_id)
        
        if tag:
            dialog = TagEditDialog(self.window, tag)
            self.window.wait_window(dialog.dialog)
            
            if dialog.result:
                self.chore_db.update_tag(tag_id, **dialog.result)
                self._refresh_tags_list()
    
    def _delete_tag(self):
        """Delete selected tag"""
        selection = self.tags_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a tag")
            return
        
        item = self.tags_tree.item(selection[0])
        tag_id = item['tags'][0]
        tag = self.chore_db.get_tag_by_id(tag_id)
        
        if tag:
            confirm = messagebox.askyesno(
                "Confirm Delete",
                f"Delete tag '{tag['tag_name']}'?"
            )
            
            if confirm:
                self.chore_db.delete_tag(tag_id)
                self._refresh_tags_list()
    
    def _read_tag_value(self):
        """Read current value of selected tag from PLC"""
        selection = self.tags_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a tag")
            return
        
        item = self.tags_tree.item(selection[0])
        tag_id = item['tags'][0]
        tag = self.chore_db.get_tag_by_id(tag_id)
        
        if not tag:
            return
        
        # Get PLC info
        plc = self.chore_db.get_plc(tag['plc_id'])
        if not plc:
            messagebox.showerror("Error", "PLC not found")
            return
        
        # Read tag value
        try:
            result = self.plc_comm.read_tag(plc['ip_address'], tag['tag_name'], int(plc['slot']), plc['plc_type'])
            if result.success:
                # Update last value in database
                self.chore_db.update_tag_value(tag_id, str(result.value))
                # Refresh display
                self._refresh_tags_list()
                messagebox.showinfo("Tag Value", f"{tag['tag_name']}: {result.value}")
            else:
                messagebox.showerror("Error", f"Failed to read tag: {result.error}")
        except Exception as e:
            messagebox.showerror("Error", f"Error reading tag: {e}")
    
    # ========== Optimization Management Methods (Tab 2) ==========
    
    def _refresh_suggestions_list(self):
        """Refresh optimization suggestions list with filters"""
        # Clear existing
        for item in self.suggestions_tree.get_children():
            self.suggestions_tree.delete(item)
        
        if not self.opt_manager:
            return
        
        # Build filters
        filters = {}
        
        category = self.opt_category_combo.get()
        if category != 'All':
            filters['category'] = category
        
        status = self.opt_status_combo.get()
        if status != 'All':
            filters['status'] = status
        
        priority = self.opt_priority_combo.get()
        if priority != 'All':
            filters['priority'] = priority
        
        search_text = self.opt_search_entry.get().strip()
        if search_text:
            filters['search_text'] = search_text
        
        # Get filtered suggestions
        suggestions = self.opt_manager.get_all_suggestions(filters)
        
        # Populate table
        for suggestion in suggestions:
            self.suggestions_tree.insert('', tk.END, values=(
                f"#{suggestion['suggestion_id']:03d}",
                suggestion['title'],
                suggestion['category'],
                suggestion['priority'],
                suggestion['status']
            ), tags=(suggestion['suggestion_id'],))
    
    def _on_suggestion_select(self, event):
        """Handle suggestion selection"""
        selection = self.suggestions_tree.selection()
        if not selection:
            return
        
        item = self.suggestions_tree.item(selection[0])
        suggestion_id = item['tags'][0]
        self.selected_suggestion_id = suggestion_id
        
        # Display details
        self._display_suggestion_details(suggestion_id)
    
    def _display_suggestion_details(self, suggestion_id: int):
        """Display suggestion details in text area"""
        suggestion = self.opt_manager.get_suggestion(suggestion_id)
        if not suggestion:
            return
        
        # Clear and populate
        self.suggestion_details_text.delete('1.0', tk.END)
        
        details = f"""Title: {suggestion['title']}
Category: {suggestion['category']}  |  Priority: {suggestion['priority']}  |  Status: {suggestion['status']}
Created by: {suggestion['created_by']} on {suggestion['created_timestamp']}

Description:
{suggestion['detailed_description'] or 'No description provided'}

Related Tags: {', '.join(suggestion['related_tags']) if suggestion['related_tags'] else 'None'}
Related Routines: {', '.join(suggestion['related_routines']) if suggestion['related_routines'] else 'None'}

Conditions:
{suggestion['conditions'] or 'Not specified'}

Expected Benefits:
{suggestion['expected_benefit'] or 'Not specified'}

Implementation Details:
{suggestion['implementation_details'] or 'Not specified'}

Estimated Savings: ${suggestion['estimated_savings_amount'] or 0} per {suggestion['estimated_savings_period'] or 'Year'}

"""
        
        if suggestion['implemented_date']:
            details += f"\nImplemented: {suggestion['implemented_date']}\n"
        
        if suggestion['results']:
            details += f"\nActual Results:\n{suggestion['results']}\n"
        
        details += f"\nAgent can auto-suggest: {'Yes' if suggestion['agent_can_suggest'] else 'No'}"
        details += f"\nRequires approval: {'Yes' if suggestion['requires_approval'] else 'No'}"
        
        self.suggestion_details_text.insert('1.0', details)
    
    def _add_suggestion(self):
        """Add new optimization suggestion"""
        dialog = OptimizationSuggestionDialog(self.window, self.opt_manager, None)
        self.window.wait_window(dialog.dialog)
        
        if dialog.result:
            self.opt_manager.add_suggestion(dialog.result)
            self._refresh_suggestions_list()
            messagebox.showinfo("Success", "Optimization suggestion added")
    
    def _edit_suggestion(self):
        """Edit selected suggestion"""
        if not self.selected_suggestion_id:
            messagebox.showwarning("Warning", "Please select a suggestion")
            return
        
        suggestion = self.opt_manager.get_suggestion(self.selected_suggestion_id)
        if not suggestion:
            return
        
        dialog = OptimizationSuggestionDialog(self.window, self.opt_manager, suggestion)
        self.window.wait_window(dialog.dialog)
        
        if dialog.result:
            self.opt_manager.update_suggestion(
                self.selected_suggestion_id,
                dialog.result,
                dialog.result.get('created_by', 'Unknown')
            )
            self._refresh_suggestions_list()
            self._display_suggestion_details(self.selected_suggestion_id)
            messagebox.showinfo("Success", "Suggestion updated")
    
    def _delete_suggestion(self):
        """Delete selected suggestion"""
        if not self.selected_suggestion_id:
            messagebox.showwarning("Warning", "Please select a suggestion")
            return
        
        suggestion = self.opt_manager.get_suggestion(self.selected_suggestion_id)
        if not suggestion:
            return
        
        confirm = messagebox.askyesno(
            "Confirm Delete",
            f"Delete suggestion '{suggestion['title']}'?\n\nThis will preserve the history but remove the suggestion."
        )
        
        if confirm:
            self.opt_manager.delete_suggestion(self.selected_suggestion_id, "Operator")
            self.selected_suggestion_id = None
            self._refresh_suggestions_list()
            self.suggestion_details_text.delete('1.0', tk.END)
    
    def _change_suggestion_status(self):
        """Change status of selected suggestion"""
        if not self.selected_suggestion_id:
            messagebox.showwarning("Warning", "Please select a suggestion")
            return
        
        suggestion = self.opt_manager.get_suggestion(self.selected_suggestion_id)
        if not suggestion:
            return
        
        dialog = StatusChangeDialog(self.window, suggestion['status'])
        self.window.wait_window(dialog.dialog)
        
        if dialog.result:
            self.opt_manager.change_status(
                self.selected_suggestion_id,
                dialog.result['new_status'],
                dialog.result['changed_by'],
                dialog.result['notes']
            )
            self._refresh_suggestions_list()
            self._display_suggestion_details(self.selected_suggestion_id)
            messagebox.showinfo("Success", f"Status changed to {dialog.result['new_status']}")
    
    def _view_suggestion_history(self):
        """View change history for selected suggestion"""
        if not self.selected_suggestion_id:
            messagebox.showwarning("Warning", "Please select a suggestion")
            return
        
        suggestion = self.opt_manager.get_suggestion(self.selected_suggestion_id)
        if not suggestion:
            return
        
        history = self.opt_manager.get_suggestion_history(self.selected_suggestion_id)
        HistoryViewerDialog(self.window, suggestion['title'], history)
    
    def _import_agent_suggestions(self):
        """Import agent-discovered suggestions"""
        if not self.opt_manager:
            return
        
        pending = self.opt_manager.get_agent_pending(reviewed=False)
        
        if not pending:
            messagebox.showinfo("No Suggestions", "No pending agent suggestions to import")
            return
        
        dialog = AgentPendingDialog(self.window, self.opt_manager, pending)
        self.window.wait_window(dialog.dialog)
        
        if dialog.imported_count > 0:
            self._refresh_suggestions_list()
            messagebox.showinfo("Success", f"Imported {dialog.imported_count} suggestion(s)")
    
    def _export_suggestions(self):
        """Export suggestions to file"""
        messagebox.showinfo("Export", "Export feature coming soon")
    
    # ========== Program Version Management Methods (Tab 3) ==========
    
    def _refresh_versions_list(self):
        """Refresh program versions list"""
        if not self.program_manager:
            return
        
        # Clear existing
        for item in self.versions_tree.get_children():
            self.versions_tree.delete(item)
        
        if not self.selected_plc_id:
            return
        
        # Get versions for selected PLC
        versions = self.program_manager.get_program_versions(self.selected_plc_id)
        
        for version in versions:
            revision = f"{version.get('major_revision', '?')}.{version.get('minor_revision', '?')}"
            self.versions_tree.insert('', tk.END, values=(
                f"v{version['version_id']}",
                version.get('program_name', 'Unknown'),
                version.get('upload_timestamp', ''),
                version.get('uploaded_by', ''),
                revision
            ), tags=(version['version_id'],))
    
    def _on_version_select(self, event):
        """Handle version selection"""
        selection = self.versions_tree.selection()
        if not selection:
            return
        
        item = self.versions_tree.item(selection[0])
        version_id = item['tags'][0]
        self.selected_version_id = version_id
        
        # Display version details
        self._display_version_details(version_id)
    
    def _display_version_details(self, version_id: int):
        """Display version details in text area"""
        version = self.program_manager.get_program_version(version_id)
        if not version:
            return
        
        routines = self.program_manager.get_routines(version_id)
        tags = self.program_manager.get_program_tags(version_id)
        
        details = f"""Program Version: v{version['version_id']}
Controller Name: {version.get('controller_name', 'Unknown')}
Processor Type: {version.get('processor_type', 'Unknown')}
Revision: {version.get('major_revision', '?')}.{version.get('minor_revision', '?')}

Upload Time: {version.get('upload_timestamp', 'Unknown')}
Uploaded By: {version.get('uploaded_by', 'Unknown')}

File: {version.get('file_path', 'None')}
Checksum: {version.get('checksum', 'Unknown')[:16] if version.get('checksum') else 'Unknown'}...

Statistics:
- {len(routines)} routines
- {len(tags)} tags
- {sum(r['rung_count'] for r in routines)} total rungs

Notes: {version.get('notes', 'None')}
"""
        
        self.version_details_text.delete('1.0', tk.END)
        self.version_details_text.insert('1.0', details)
    
    def _upload_program(self):
        """Upload a new program version"""
        if not self.selected_plc_id:
            messagebox.showwarning("Warning", "Please select a PLC first")
            return
        
        if not self.program_manager:
            messagebox.showerror("Error", "Program manager not available")
            return
        
        # Open file dialog
        file_path = filedialog.askopenfilename(
            title="Select L5X Program File",
            filetypes=[("L5X Files", "*.L5X"), ("All Files", "*.*")]
        )
        
        if not file_path:
            return
        
        # Get upload notes
        dialog = UploadNotesDialog(self.window)
        self.window.wait_window(dialog.dialog)
        
        if not dialog.result:
            return
        
        uploaded_by = dialog.result['uploaded_by']
        notes = dialog.result['notes']
        
        # Upload in thread to avoid blocking
        def upload_thread():
            try:
                self.status_label.config(text="Uploading program...", fg='#ffaa00')
                self.window.update()
                
                version_id = self.program_manager.upload_program(
                    self.selected_plc_id,
                    file_path,
                    uploaded_by,
                    notes
                )
                
                self.window.after(0, lambda: self._on_upload_complete(version_id))
                
            except Exception as e:
                error_msg = str(e)
                self.window.after(0, lambda: self._on_upload_error(error_msg))
        
        threading.Thread(target=upload_thread, daemon=True).start()
    
    def _on_upload_complete(self, version_id: int):
        """Handle successful upload"""
        self.status_label.config(text=f"âœ“ Upload complete (v{version_id})", fg='#00ff00')
        self._refresh_versions_list()
        messagebox.showinfo("Success", f"Program uploaded as version {version_id}")
    
    def _on_upload_error(self, error_msg: str):
        """Handle upload error"""
        self.status_label.config(text=" Upload failed", fg='#ff0000')
        messagebox.showerror("Upload Error", f"Failed to upload program:\n{error_msg}")
    
    def _view_version_details(self):
        """View detailed version information"""
        if not self.selected_version_id:
            messagebox.showwarning("Warning", "Please select a version")
            return
        
        version = self.program_manager.get_program_version(self.selected_version_id)
        if not version:
            return
        
        VersionDetailsDialog(self.window, self.program_manager, self.selected_version_id)
    
    def _browse_routines(self):
        """Browse routines in selected version"""
        if not self.selected_version_id:
            messagebox.showwarning("Warning", "Please select a version")
            return
        
        RoutineBrowserDialog(self.window, self.program_manager, self.selected_version_id)
    
    def _view_program_tags(self):
        """View all tags in selected version"""
        if not self.selected_version_id:
            messagebox.showwarning("Warning", "Please select a version")
            return
        
        ProgramTagsDialog(self.window, self.program_manager, self.selected_version_id)
    
    def _compare_versions(self):
        """Compare two program versions"""
        if not self.program_manager:
            return
        
        versions = self.program_manager.get_program_versions(self.selected_plc_id)
        if len(versions) < 2:
            messagebox.showinfo("Info", "Need at least 2 versions to compare")
            return
        
        VersionCompareDialog(self.window, self.program_manager, versions)
    
    def _delete_version(self):
        """Delete selected version"""
        if not self.selected_version_id:
            messagebox.showwarning("Warning", "Please select a version")
            return
        
        version = self.program_manager.get_program_version(self.selected_version_id)
        if not version:
            return
        
        confirm = messagebox.askyesno(
            "Confirm Delete",
            f"Delete program version v{version['version_id']} ({version.get('program_name', 'Unknown')})?\n\n" +
            f"Uploaded: {version.get('upload_timestamp', 'Unknown')}\n" +
            "This cannot be undone."
        )
        
        if confirm:
            if self.program_manager.delete_version(self.selected_version_id):
                self.selected_version_id = None
                self._refresh_versions_list()
                self.version_details_text.delete('1.0', tk.END)
                messagebox.showinfo("Success", "Version deleted")
            else:
                messagebox.showerror("Error", "Failed to delete version")
    
    # ========== Window Management ==========
    
    def _on_closing(self):
        """Handle window close"""
        if self.on_close_callback:
            self.on_close_callback()
        self.window.destroy()


# ========== Dialog Classes ==========

class TagEditDialog:
    """Dialog for adding/editing tags (simplified from original)"""
    
    def __init__(self, parent, tag: Optional[Dict]):
        self.result = None
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Edit Tag" if tag else "Add Tag")
        self.dialog.geometry("600x650")
        self.dialog.configure(bg='#2b2b2b')
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Form
        form = tk.Frame(self.dialog, bg='#2b2b2b')
        form.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Tag Name
        tk.Label(form, text="Tag Name:", bg='#2b2b2b', fg='white').grid(row=0, column=0, sticky='w', pady=5)
        self.name_entry = tk.Entry(form, bg='#1e1e1e', fg='white', width=40, insertbackground='white')
        self.name_entry.grid(row=0, column=1, pady=5, sticky='w')
        
        # Type
        tk.Label(form, text="Tag Type:", bg='#2b2b2b', fg='white').grid(row=1, column=0, sticky='w', pady=5)
        self.type_combo = ttk.Combobox(form, values=['BOOL', 'SINT', 'INT', 'DINT', 'REAL', 'STRING'], width=37, state='readonly')
        self.type_combo.set('BOOL')
        self.type_combo.grid(row=1, column=1, pady=5, sticky='w')
        
        # Access Type
        tk.Label(form, text="Access Type:", bg='#2b2b2b', fg='white').grid(row=2, column=0, sticky='w', pady=5)
        self.access_combo = ttk.Combobox(form, values=['read', 'write', 'read_write'], width=37, state='readonly')
        self.access_combo.set('read_write')
        self.access_combo.grid(row=2, column=1, pady=5, sticky='w')
        
        # Keywords section (simplified)
        tk.Label(form, text="State1 Keywords:", bg='#2b2b2b', fg='white').grid(row=3, column=0, sticky='w', pady=5)
        self.state1_entry = tk.Entry(form, bg='#1e1e1e', fg='#66ff66', width=40, insertbackground='white')
        self.state1_entry.grid(row=3, column=1, pady=5, sticky='w')
        
        tk.Label(form, text="State0 Keywords:", bg='#2b2b2b', fg='white').grid(row=4, column=0, sticky='w', pady=5)
        self.state0_entry = tk.Entry(form, bg='#1e1e1e', fg='#ff6666', width=40, insertbackground='white')
        self.state0_entry.grid(row=4, column=1, pady=5, sticky='w')
        
        # Read Keywords
        tk.Label(form, text="Read Keywords:", bg='#2b2b2b', fg='white').grid(row=5, column=0, sticky='w', pady=5)
        self.read_entry = tk.Entry(form, bg='#1e1e1e', fg='white', width=40, insertbackground='white')
        self.read_entry.grid(row=5, column=1, pady=5, sticky='w')
        
        # Write Keywords
        tk.Label(form, text="Write Keywords:", bg='#2b2b2b', fg='white').grid(row=6, column=0, sticky='w', pady=5)
        self.write_entry = tk.Entry(form, bg='#1e1e1e', fg='white', width=40, insertbackground='white')
        self.write_entry.grid(row=6, column=1, pady=5, sticky='w')
        
        # Monitor checkbox
        self.monitor_var = tk.BooleanVar()
        tk.Checkbutton(
            form, text="Monitor this tag", variable=self.monitor_var,
            bg='#2b2b2b', fg='white', selectcolor='#1e1e1e'
        ).grid(row=7, column=1, sticky='w', pady=5)
        
        # Load existing data
        if tag:
            self.name_entry.insert(0, tag.get('tag_name', ''))
            self.type_combo.set(tag.get('tag_type', 'BOOL'))
            self.access_combo.set(tag.get('access_type', 'read_write'))
            self.monitor_var.set(tag.get('monitor', False))
            
            # Parse keywords
            on_kw = tag.get('on_keywords', '')
            off_kw = tag.get('off_keywords', '')
            read_kw = tag.get('read_keywords', '')
            write_kw = tag.get('write_keywords', '')
            if on_kw:
                self.state1_entry.insert(0, on_kw)
            if off_kw:
                self.state0_entry.insert(0, off_kw)
            if read_kw:
                self.read_entry.insert(0, read_kw)
            if write_kw:
                self.write_entry.insert(0, write_kw)
        
        # Buttons
        btn_frame = tk.Frame(self.dialog, bg='#2b2b2b')
        btn_frame.pack(fill=tk.X, padx=20, pady=10)
        
        tk.Button(
            btn_frame, text="Cancel", command=self.dialog.destroy,
            bg='#666666', fg='white', width=10
        ).pack(side=tk.RIGHT, padx=5)
        
        tk.Button(
            btn_frame, text="Save", command=self._save,
            bg='#0066cc', fg='white', width=10
        ).pack(side=tk.RIGHT, padx=5)
    
    def _save(self):
        tag_name = self.name_entry.get().strip()
        if not tag_name:
            messagebox.showerror("Error", "Tag name is required")
            return
        
        self.result = {
            'tag_name': tag_name,
            'tag_type': self.type_combo.get(),
            'access_type': self.access_combo.get(),
            'monitor': self.monitor_var.get(),
            'on_keywords': self.state1_entry.get().strip() or None,
            'off_keywords': self.state0_entry.get().strip() or None,
            'read_keywords': self.read_entry.get().strip() or None,
            'write_keywords': self.write_entry.get().strip() or None
        }
        self.dialog.destroy()


class OptimizationSuggestionDialog:
    """Dialog for adding/editing optimization suggestions"""
    
    def __init__(self, parent, opt_manager, suggestion: Optional[Dict]):
        self.result = None
        self.opt_manager = opt_manager
        self.editing = suggestion is not None
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Edit Suggestion" if self.editing else "Add Optimization Suggestion")
        self.dialog.geometry("700x800")
        self.dialog.configure(bg='#2b2b2b')
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Scrollable frame
        canvas = tk.Canvas(self.dialog, bg='#2b2b2b')
        scrollbar = tk.Scrollbar(self.dialog, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='#2b2b2b')
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        scrollbar.pack(side="right", fill="y")
        
        form = scrollable_frame
        
        # Title
        tk.Label(form, text="Title:", bg='#2b2b2b', fg='white', font=('Arial', 10, 'bold')).pack(anchor='w', padx=10, pady=(10, 0))
        self.title_entry = tk.Entry(form, bg='#1e1e1e', fg='white', font=('Arial', 10), insertbackground='white')
        self.title_entry.pack(fill=tk.X, padx=10, pady=5)
        
        # Category and Priority
        row1 = tk.Frame(form, bg='#2b2b2b')
        row1.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Label(row1, text="Category:", bg='#2b2b2b', fg='white').pack(side=tk.LEFT, padx=(0, 5))
        self.category_combo = ttk.Combobox(row1, values=CATEGORIES, width=15, state='readonly')
        self.category_combo.set('Efficiency')
        self.category_combo.pack(side=tk.LEFT, padx=5)
        
        tk.Label(row1, text="Priority:", bg='#2b2b2b', fg='white').pack(side=tk.LEFT, padx=(20, 5))
        self.priority_combo = ttk.Combobox(row1, values=PRIORITIES, width=10, state='readonly')
        self.priority_combo.set('Medium')
        self.priority_combo.pack(side=tk.LEFT, padx=5)
        
        tk.Label(row1, text="Status:", bg='#2b2b2b', fg='white').pack(side=tk.LEFT, padx=(20, 5))
        self.status_combo = ttk.Combobox(row1, values=STATUSES, width=10, state='readonly')
        self.status_combo.set('Idea')
        self.status_combo.pack(side=tk.LEFT, padx=5)
        
        # Description
        tk.Label(form, text="Detailed Description:", bg='#2b2b2b', fg='white', font=('Arial', 10, 'bold')).pack(anchor='w', padx=10, pady=(10, 0))
        self.description_text = scrolledtext.ScrolledText(form, bg='#1e1e1e', fg='white', height=6, wrap=tk.WORD, insertbackground='white')
        self.description_text.pack(fill=tk.X, padx=10, pady=5)
        
        # Related Tags
        tk.Label(form, text="Related Tags (comma separated):", bg='#2b2b2b', fg='white', font=('Arial', 10, 'bold')).pack(anchor='w', padx=10, pady=(10, 0))
        self.tags_entry = tk.Entry(form, bg='#1e1e1e', fg='white', insertbackground='white')
        self.tags_entry.pack(fill=tk.X, padx=10, pady=5)
        
        # Related Routines
        tk.Label(form, text="Related Routines (comma separated):", bg='#2b2b2b', fg='white', font=('Arial', 10, 'bold')).pack(anchor='w', padx=10, pady=(10, 0))
        self.routines_entry = tk.Entry(form, bg='#1e1e1e', fg='white', insertbackground='white')
        self.routines_entry.pack(fill=tk.X, padx=10, pady=5)
        
        # Conditions
        tk.Label(form, text="Conditions (when to apply):", bg='#2b2b2b', fg='white', font=('Arial', 10, 'bold')).pack(anchor='w', padx=10, pady=(10, 0))
        self.conditions_entry = tk.Entry(form, bg='#1e1e1e', fg='white', insertbackground='white')
        self.conditions_entry.pack(fill=tk.X, padx=10, pady=5)
        
        # Expected Benefits
        tk.Label(form, text="Expected Benefits:", bg='#2b2b2b', fg='white', font=('Arial', 10, 'bold')).pack(anchor='w', padx=10, pady=(10, 0))
        self.benefits_text = scrolledtext.ScrolledText(form, bg='#1e1e1e', fg='white', height=4, wrap=tk.WORD, insertbackground='white')
        self.benefits_text.pack(fill=tk.X, padx=10, pady=5)
        
        # Implementation Details
        tk.Label(form, text="Implementation Details:", bg='#2b2b2b', fg='white', font=('Arial', 10, 'bold')).pack(anchor='w', padx=10, pady=(10, 0))
        self.implementation_text = scrolledtext.ScrolledText(form, bg='#1e1e1e', fg='white', height=4, wrap=tk.WORD, insertbackground='white')
        self.implementation_text.pack(fill=tk.X, padx=10, pady=5)
        
        # Estimated Savings
        row2 = tk.Frame(form, bg='#2b2b2b')
        row2.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Label(row2, text="Estimated Savings: $", bg='#2b2b2b', fg='white').pack(side=tk.LEFT, padx=(0, 5))
        self.savings_entry = tk.Entry(row2, bg='#1e1e1e', fg='white', width=15, insertbackground='white')
        self.savings_entry.insert(0, "0")
        self.savings_entry.pack(side=tk.LEFT, padx=5)
        
        tk.Label(row2, text="per", bg='#2b2b2b', fg='white').pack(side=tk.LEFT, padx=5)
        self.period_combo = ttk.Combobox(row2, values=['Year', 'Month', 'Week', 'Day', 'Batch'], width=10, state='readonly')
        self.period_combo.set('Year')
        self.period_combo.pack(side=tk.LEFT, padx=5)
        
        # Created by
        tk.Label(form, text="Created by:", bg='#2b2b2b', fg='white', font=('Arial', 10, 'bold')).pack(anchor='w', padx=10, pady=(10, 0))
        self.created_by_entry = tk.Entry(form, bg='#1e1e1e', fg='white', insertbackground='white')
        self.created_by_entry.insert(0, "Operator")
        self.created_by_entry.pack(fill=tk.X, padx=10, pady=5)
        
        # Options
        self.agent_suggest_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            form, text="Allow agent to suggest this automatically", 
            variable=self.agent_suggest_var, bg='#2b2b2b', fg='white', selectcolor='#1e1e1e'
        ).pack(anchor='w', padx=10, pady=5)
        
        self.requires_approval_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            form, text="Requires operator approval before implementation",
            variable=self.requires_approval_var, bg='#2b2b2b', fg='white', selectcolor='#1e1e1e'
        ).pack(anchor='w', padx=10, pady=5)
        
        # Load existing data if editing
        if suggestion:
            self.title_entry.insert(0, suggestion.get('title', ''))
            self.category_combo.set(suggestion.get('category', 'Efficiency'))
            self.priority_combo.set(suggestion.get('priority', 'Medium'))
            self.status_combo.set(suggestion.get('status', 'Idea'))
            self.description_text.insert('1.0', suggestion.get('detailed_description', ''))
            self.tags_entry.insert(0, ', '.join(suggestion.get('related_tags', [])))
            self.routines_entry.insert(0, ', '.join(suggestion.get('related_routines', [])))
            self.conditions_entry.insert(0, suggestion.get('conditions', ''))
            self.benefits_text.insert('1.0', suggestion.get('expected_benefit', ''))
            self.implementation_text.insert('1.0', suggestion.get('implementation_details', ''))
            self.savings_entry.delete(0, tk.END)
            self.savings_entry.insert(0, str(suggestion.get('estimated_savings_amount', 0)))
            self.period_combo.set(suggestion.get('estimated_savings_period', 'Year'))
            self.created_by_entry.delete(0, tk.END)
            self.created_by_entry.insert(0, suggestion.get('created_by', 'Operator'))
            self.agent_suggest_var.set(suggestion.get('agent_can_suggest', True))
            self.requires_approval_var.set(suggestion.get('requires_approval', True))
        
        # Buttons
        btn_frame = tk.Frame(form, bg='#2b2b2b')
        btn_frame.pack(fill=tk.X, padx=10, pady=20)
        
        tk.Button(
            btn_frame, text="Cancel", command=self.dialog.destroy,
            bg='#666666', fg='white', width=15, font=('Arial', 10, 'bold')
        ).pack(side=tk.RIGHT, padx=5)
        
        tk.Button(
            btn_frame, text="Save", command=self._save,
            bg='#0066cc', fg='white', width=15, font=('Arial', 10, 'bold')
        ).pack(side=tk.RIGHT, padx=5)
    
    def _save(self):
        title = self.title_entry.get().strip()
        if not title:
            messagebox.showerror("Error", "Title is required")
            return
        
        # Parse tags and routines
        tags_str = self.tags_entry.get().strip()
        tags = [t.strip() for t in tags_str.split(',') if t.strip()]
        
        routines_str = self.routines_entry.get().strip()
        routines = [r.strip() for r in routines_str.split(',') if r.strip()]
        
        # Parse savings
        try:
            savings = float(self.savings_entry.get())
        except:
            savings = 0.0
        
        self.result = {
            'title': title,
            'detailed_description': self.description_text.get('1.0', tk.END).strip(),
            'category': self.category_combo.get(),
            'priority': self.priority_combo.get(),
            'status': self.status_combo.get(),
            'related_tags': tags,
            'related_routines': routines,
            'conditions': self.conditions_entry.get().strip(),
            'expected_benefit': self.benefits_text.get('1.0', tk.END).strip(),
            'implementation_details': self.implementation_text.get('1.0', tk.END).strip(),
            'estimated_savings_amount': savings,
            'estimated_savings_period': self.period_combo.get(),
            'created_by': self.created_by_entry.get().strip(),
            'agent_can_suggest': self.agent_suggest_var.get(),
            'requires_approval': self.requires_approval_var.get()
        }
        
        self.dialog.destroy()


class StatusChangeDialog:
    """Dialog for changing suggestion status"""
    
    def __init__(self, parent, current_status: str):
        self.result = None
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Change Status")
        self.dialog.geometry("400x300")
        self.dialog.configure(bg='#2b2b2b')
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        form = tk.Frame(self.dialog, bg='#2b2b2b')
        form.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        tk.Label(
            form, text=f"Current Status: {current_status}",
            bg='#2b2b2b', fg='white', font=('Arial', 11, 'bold')
        ).pack(anchor='w', pady=10)
        
        tk.Label(form, text="New Status:", bg='#2b2b2b', fg='white').pack(anchor='w', pady=(10, 0))
        self.status_combo = ttk.Combobox(form, values=STATUSES, width=25, state='readonly')
        self.status_combo.set(current_status)
        self.status_combo.pack(fill=tk.X, pady=5)
        
        tk.Label(form, text="Notes:", bg='#2b2b2b', fg='white').pack(anchor='w', pady=(10, 0))
        self.notes_text = scrolledtext.ScrolledText(form, bg='#1e1e1e', fg='white', height=5, wrap=tk.WORD, insertbackground='white')
        self.notes_text.pack(fill=tk.BOTH, expand=True, pady=5)
        
        tk.Label(form, text="Changed by:", bg='#2b2b2b', fg='white').pack(anchor='w', pady=(10, 0))
        self.changed_by_entry = tk.Entry(form, bg='#1e1e1e', fg='white', insertbackground='white')
        self.changed_by_entry.insert(0, "Operator")
        self.changed_by_entry.pack(fill=tk.X, pady=5)
        
        # Buttons
        btn_frame = tk.Frame(self.dialog, bg='#2b2b2b')
        btn_frame.pack(fill=tk.X, padx=20, pady=10)
        
        tk.Button(
            btn_frame, text="Cancel", command=self.dialog.destroy,
            bg='#666666', fg='white', width=12
        ).pack(side=tk.RIGHT, padx=5)
        
        tk.Button(
            btn_frame, text="Save", command=self._save,
            bg='#0066cc', fg='white', width=12
        ).pack(side=tk.RIGHT, padx=5)
    
    def _save(self):
        self.result = {
            'new_status': self.status_combo.get(),
            'notes': self.notes_text.get('1.0', tk.END).strip(),
            'changed_by': self.changed_by_entry.get().strip()
        }
        self.dialog.destroy()


class HistoryViewerDialog:
    """Dialog for viewing suggestion history"""
    
    def __init__(self, parent, suggestion_title: str, history: List[Dict]):
        dialog = tk.Toplevel(parent)
        dialog.title(f"History: {suggestion_title}")
        dialog.geometry("700x500")
        dialog.configure(bg='#2b2b2b')
        dialog.transient(parent)
        
        tk.Label(
            dialog,
            text=f"Change History for: {suggestion_title}",
            bg='#2b2b2b',
            fg='white',
            font=('Arial', 12, 'bold')
        ).pack(pady=10)
        
        # History text
        text = scrolledtext.ScrolledText(
            dialog,
            bg='#1e1e1e',
            fg='white',
            font=('Consolas', 10),
            wrap=tk.WORD
        )
        text.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 10))
        
        # Format and display history
        if history:
            for entry in history:
                timestamp = entry.get('timestamp', 'Unknown')
                action = entry.get('action', 'unknown')
                performed_by = entry.get('performed_by', 'Unknown')
                notes = entry.get('notes', '')
                old_status = entry.get('old_status', '')
                new_status = entry.get('new_status', '')
                
                text.insert(tk.END, f"{timestamp} - {action.upper()}\n", 'timestamp')
                text.insert(tk.END, f"By: {performed_by}\n")
                
                if old_status and new_status:
                    text.insert(tk.END, f"Status: {old_status} â†’ {new_status}\n")
                
                if notes:
                    text.insert(tk.END, f"{notes}\n")
                
                text.insert(tk.END, "\n")
        else:
            text.insert(tk.END, "No history available.\n")
        
        text.config(state='disabled')
        
        # Close button
        tk.Button(
            dialog,
            text="Close",
            command=dialog.destroy,
            bg='#666666',
            fg='white',
            width=15
        ).pack(pady=10)


class AgentPendingDialog:
    """Dialog for reviewing agent-discovered suggestions"""
    
    def __init__(self, parent, opt_manager, pending_list: List[Dict]):
        self.opt_manager = opt_manager
        self.pending_list = pending_list
        self.imported_count = 0
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Agent-Discovered Optimizations")
        self.dialog.geometry("800x600")
        self.dialog.configure(bg='#2b2b2b')
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        tk.Label(
            self.dialog,
            text=" Agent-Discovered Optimization Suggestions",
            bg='#2b2b2b',
            fg='white',
            font=('Arial', 14, 'bold')
        ).pack(pady=10)
        
        tk.Label(
            self.dialog,
            text=f"{len(pending_list)} pending suggestions awaiting review",
            bg='#2b2b2b',
            fg='#aaaaaa',
            font=('Arial', 10)
        ).pack(pady=(0, 10))
        
        # List of pending suggestions
        list_frame = tk.Frame(self.dialog, bg='#1e1e1e')
        list_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 10))
        
        # Scrollbar
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.pending_listbox = tk.Listbox(
            list_frame,
            bg='#2b2b2b',
            fg='white',
            font=('Consolas', 10),
            selectmode=tk.SINGLE,
            yscrollcommand=scrollbar.set
        )
        self.pending_listbox.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.pending_listbox.yview)
        
        # Populate list
        for pending in pending_list:
            confidence = pending.get('confidence_level', 'Unknown')
            title = pending.get('title', 'Untitled')
            display = f"[{confidence}] {title}"
            self.pending_listbox.insert(tk.END, display)
        
        self.pending_listbox.bind('<<ListboxSelect>>', self._on_select)
        
        # Details panel
        details_frame = tk.LabelFrame(
            self.dialog,
            text="Details",
            bg='#1e1e1e',
            fg='white',
            font=('Arial', 11, 'bold')
        )
        details_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 10))
        
        self.details_text = scrolledtext.ScrolledText(
            details_frame,
            bg='#2b2b2b',
            fg='white',
            font=('Consolas', 9),
            wrap=tk.WORD,
            height=8
        )
        self.details_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Buttons
        btn_frame = tk.Frame(self.dialog, bg='#2b2b2b')
        btn_frame.pack(fill=tk.X, padx=20, pady=10)
        
        tk.Button(
            btn_frame,
            text=" Import Selected",
            command=self._import_selected,
            bg='#00aa00',
            fg='white',
            font=('Arial', 10, 'bold'),
            width=15
        ).pack(side=tk.LEFT, padx=5)
        
        tk.Button(
            btn_frame,
            text=" Import All",
            command=self._import_all,
            bg='#0066cc',
            fg='white',
            font=('Arial', 10, 'bold'),
            width=15
        ).pack(side=tk.LEFT, padx=5)
        
        tk.Button(
            btn_frame,
            text="Close",
            command=self.dialog.destroy,
            bg='#666666',
            fg='white',
            font=('Arial', 10, 'bold'),
            width=15
        ).pack(side=tk.RIGHT, padx=5)
        
        # Select first item
        if pending_list:
            self.pending_listbox.selection_set(0)
            self._on_select(None)
    
    def _on_select(self, event):
        """Display details of selected pending suggestion"""
        selection = self.pending_listbox.curselection()
        if not selection:
            return
        
        pending = self.pending_list[selection[0]]
        
        details = f"""Title: {pending.get('title', 'Untitled')}
Confidence: {pending.get('confidence_level', 'Unknown')}
Detected: {pending.get('detected_timestamp', 'Unknown')}

Description:
{pending.get('description', 'No description')}

Expected Savings: {pending.get('expected_savings', 'Not specified')}

Related Tags: {', '.join(pending.get('related_tags', []))}
Related Routines: {', '.join(pending.get('related_routines', []))}

Conditions: {pending.get('conditions', 'Not specified')}
"""
        
        self.details_text.delete('1.0', tk.END)
        self.details_text.insert('1.0', details)
    
    def _import_selected(self):
        """Import selected pending suggestion"""
        selection = self.pending_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a suggestion")
            return
        
        pending = self.pending_list[selection[0]]
        pending_id = pending['pending_id']
        
        suggestion_id = self.opt_manager.import_agent_pending(pending_id, "Operator")
        if suggestion_id:
            self.imported_count += 1
            self.pending_listbox.delete(selection[0])
            self.pending_list.pop(selection[0])
            messagebox.showinfo("Success", f"Imported as Suggestion #{suggestion_id}")
            
            if not self.pending_list:
                self.dialog.destroy()
    
    def _import_all(self):
        """Import all pending suggestions"""
        confirm = messagebox.askyesno(
            "Confirm",
            f"Import all {len(self.pending_list)} suggestions?"
        )
        
        if confirm:
            for pending in self.pending_list:
                self.opt_manager.import_agent_pending(pending['pending_id'], "Operator")
                self.imported_count += 1
            
            messagebox.showinfo("Success", f"Imported {self.imported_count} suggestions")
            self.dialog.destroy()




class UploadNotesDialog:
    """Dialog for entering notes when uploading a program"""
    
    def __init__(self, parent):
        self.result = None
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Upload Program")
        self.dialog.geometry("450x250")
        self.dialog.configure(bg='#2b2b2b')
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        form = tk.Frame(self.dialog, bg='#2b2b2b')
        form.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        tk.Label(form, text="Uploaded by:", bg='#2b2b2b', fg='white').pack(anchor='w', pady=(0, 5))
        self.uploaded_by_entry = tk.Entry(form, bg='#1e1e1e', fg='white', insertbackground='white')
        self.uploaded_by_entry.insert(0, "Operator")
        self.uploaded_by_entry.pack(fill=tk.X, pady=(0, 10))
        
        tk.Label(form, text="Notes:", bg='#2b2b2b', fg='white').pack(anchor='w', pady=(0, 5))
        self.notes_text = scrolledtext.ScrolledText(form, bg='#1e1e1e', fg='white', height=5, wrap=tk.WORD, insertbackground='white')
        self.notes_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Buttons
        btn_frame = tk.Frame(self.dialog, bg='#2b2b2b')
        btn_frame.pack(fill=tk.X, padx=20, pady=10)
        
        tk.Button(
            btn_frame, text="Cancel", command=self.dialog.destroy,
            bg='#666666', fg='white', width=12
        ).pack(side=tk.RIGHT, padx=5)
        
        tk.Button(
            btn_frame, text="Upload", command=self._save,
            bg='#0066cc', fg='white', width=12
        ).pack(side=tk.RIGHT, padx=5)
    
    def _save(self):
        self.result = {
            'uploaded_by': self.uploaded_by_entry.get().strip(),
            'notes': self.notes_text.get('1.0', tk.END).strip()
        }
        self.dialog.destroy()


class VersionDetailsDialog:
    """Dialog showing detailed version information"""
    
    def __init__(self, parent, program_manager, version_id: int):
        dialog = tk.Toplevel(parent)
        dialog.title(f"Version Details - v{version_id}")
        dialog.geometry("800x600")
        dialog.configure(bg='#2b2b2b')
        dialog.transient(parent)
        
        version = program_manager.get_program_version(version_id)
        routines = program_manager.get_routines(version_id)
        tags = program_manager.get_program_tags(version_id)
        
        # Header
        header = tk.Frame(dialog, bg='#1e1e1e')
        header.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Label(
            header,
            text=f"Version {version_id}: {version.get('controller_name', 'Unknown')}",
            bg='#1e1e1e',
            fg='white',
            font=('Arial', 14, 'bold')
        ).pack(anchor='w')
        
        tk.Label(
            header,
            text=f"Uploaded: {version.get('upload_timestamp', 'Unknown')} by {version.get('uploaded_by', 'Unknown')}",
            bg='#1e1e1e',
            fg='#aaaaaa',
            font=('Arial', 10)
        ).pack(anchor='w')
        
        # Notebook with tabs
        notebook = ttk.Notebook(dialog)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        # Tab 1: Routines
        routines_frame = tk.Frame(notebook, bg='#2b2b2b')
        notebook.add(routines_frame, text=f"Routines ({len(routines)})")
        
        routines_text = scrolledtext.ScrolledText(routines_frame, bg='#1e1e1e', fg='white', font=('Consolas', 10))
        routines_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        for routine in routines:
            routines_text.insert(tk.END, f"{routine['routine_name']} ({routine['routine_type']})\n")
            routines_text.insert(tk.END, f"  Program: {routine['program_name']}\n")
            routines_text.insert(tk.END, f"  Rungs: {routine['rung_count']}\n")
            if routine.get('description'):
                routines_text.insert(tk.END, f"  Description: {routine['description']}\n")
            routines_text.insert(tk.END, "\n")
        
        routines_text.config(state='disabled')
        
        # Tab 2: Tags Summary
        tags_frame = tk.Frame(notebook, bg='#2b2b2b')
        notebook.add(tags_frame, text=f"Tags ({len(tags)})")
        
        tags_text = scrolledtext.ScrolledText(tags_frame, bg='#1e1e1e', fg='white', font=('Consolas', 10))
        tags_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Group tags by scope
        controller_tags = [t for t in tags if t['scope'] == 'controller']
        program_tags = [t for t in tags if t['scope'] == 'program']
        
        tags_text.insert(tk.END, f"CONTROLLER-SCOPED TAGS ({len(controller_tags)}):\n\n")
        for tag in controller_tags[:50]:  # Limit to first 50
            tags_text.insert(tk.END, f"{tag['tag_name']} ({tag['data_type']})\n")
        if len(controller_tags) > 50:
            tags_text.insert(tk.END, f"\n...and {len(controller_tags) - 50} more\n")
        
        tags_text.insert(tk.END, f"\n\nPROGRAM-SCOPED TAGS ({len(program_tags)}):\n\n")
        for tag in program_tags[:50]:
            tags_text.insert(tk.END, f"{tag['tag_name']} ({tag['data_type']}) - {tag.get('parent', '')}\n")
        if len(program_tags) > 50:
            tags_text.insert(tk.END, f"\n...and {len(program_tags) - 50} more\n")
        
        tags_text.config(state='disabled')
        
        # Close button
        tk.Button(
            dialog,
            text="Close",
            command=dialog.destroy,
            bg='#666666',
            fg='white',
            width=15
        ).pack(pady=10)


class RoutineBrowserDialog:
    """Dialog for browsing routines and rungs"""
    
    def __init__(self, parent, program_manager, version_id: int):
        self.program_manager = program_manager
        self.version_id = version_id
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Routine Browser")
        self.dialog.geometry("1000x700")
        self.dialog.configure(bg='#2b2b2b')
        self.dialog.transient(parent)
        
        # Left panel: Routine list
        left_frame = tk.Frame(self.dialog, bg='#1e1e1e', width=250)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(10, 5), pady=10)
        left_frame.pack_propagate(False)
        
        tk.Label(
            left_frame,
            text="Routines",
            bg='#1e1e1e',
            fg='white',
            font=('Arial', 12, 'bold')
        ).pack(pady=10)
        
        list_frame = tk.Frame(left_frame, bg='#1e1e1e')
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.routine_listbox = tk.Listbox(
            list_frame,
            bg='#2b2b2b',
            fg='white',
            font=('Consolas', 10),
            yscrollcommand=scrollbar.set
        )
        self.routine_listbox.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.routine_listbox.yview)
        
        self.routine_listbox.bind('<<ListboxSelect>>', self._on_routine_select)
        
        # Right panel: Rungs
        right_frame = tk.Frame(self.dialog, bg='#1e1e1e')
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 10), pady=10)
        
        tk.Label(
            right_frame,
            text="Rungs",
            bg='#1e1e1e',
            fg='white',
            font=('Arial', 12, 'bold')
        ).pack(pady=10)
        
        self.rungs_text = scrolledtext.ScrolledText(
            right_frame,
            bg='#2b2b2b',
            fg='white',
            font=('Consolas', 9),
            wrap=tk.NONE
        )
        self.rungs_text.pack(fill=tk.BOTH, expand=True)
        
        # Load routines
        self._load_routines()
    
    def _load_routines(self):
        """Load routine list"""
        routines = self.program_manager.get_routines(self.version_id)
        
        for routine in routines:
            display = f"{routine['routine_name']} ({routine['rung_count']} rungs)"
            self.routine_listbox.insert(tk.END, display)
    
    def _on_routine_select(self, event):
        """Handle routine selection"""
        selection = self.routine_listbox.curselection()
        if not selection:
            return
        
        routines = self.program_manager.get_routines(self.version_id)
        routine = routines[selection[0]]
        
        # Display rungs
        self.rungs_text.delete('1.0', tk.END)
        
        rungs = self.program_manager.get_rungs(routine['routine_id'])
        
        self.rungs_text.insert(tk.END, f"Routine: {routine['routine_name']}\n")
        if routine.get('description'):
            self.rungs_text.insert(tk.END, f"Description: {routine['description']}\n")
        self.rungs_text.insert(tk.END, f"Type: {routine['routine_type']}\n")
        self.rungs_text.insert(tk.END, f"Rungs: {len(rungs)}\n")
        self.rungs_text.insert(tk.END, "=" * 80 + "\n\n")
        
        for rung in rungs:
            self.rungs_text.insert(tk.END, f"Rung {rung['rung_number']}")
            if rung.get('rung_comment'):
                self.rungs_text.insert(tk.END, f" - {rung['rung_comment']}")
            self.rungs_text.insert(tk.END, "\n")
            
            self.rungs_text.insert(tk.END, f"{rung.get('rung_text', 'No text available')}\n")
            
            if rung.get('tags_read'):
                self.rungs_text.insert(tk.END, f"  Reads: {', '.join(rung['tags_read'])}\n")
            if rung.get('tags_written'):
                self.rungs_text.insert(tk.END, f"  Writes: {', '.join(rung['tags_written'])}\n")
            
            self.rungs_text.insert(tk.END, "\n" + "-" * 80 + "\n\n")


class ProgramTagsDialog:
    """Dialog showing all program tags"""
    
    def __init__(self, parent, program_manager, version_id: int):
        dialog = tk.Toplevel(parent)
        dialog.title("Program Tags")
        dialog.geometry("900x600")
        dialog.configure(bg='#2b2b2b')
        dialog.transient(parent)
        
        # Search bar
        search_frame = tk.Frame(dialog, bg='#2b2b2b')
        search_frame.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Label(search_frame, text="Search:", bg='#2b2b2b', fg='white').pack(side=tk.LEFT, padx=5)
        search_entry = tk.Entry(search_frame, bg='#1e1e1e', fg='white', insertbackground='white')
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Tags table
        table_frame = tk.Frame(dialog, bg='#2b2b2b')
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        scrollbar = tk.Scrollbar(table_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        tags_tree = ttk.Treeview(
            table_frame,
            columns=('name', 'data_type', 'scope'),
            show='headings',
            yscrollcommand=scrollbar.set
        )
        
        tags_tree.heading('name', text='Tag Name')
        tags_tree.heading('data_type', text='Data Type')
        tags_tree.heading('scope', text='Scope')
        
        tags_tree.column('name', width=250)
        tags_tree.column('data_type', width=150)
        tags_tree.column('scope', width=150)
        
        tags_tree.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=tags_tree.yview)
        
        # Load tags
        tags = program_manager.get_program_tags(version_id)
        
        for tag in tags:
            tags_tree.insert('', tk.END, values=(
                tag['tag_name'],
                tag['data_type'],
                tag['scope']
            ))
        
        # Search functionality
        def search_tags(*args):
            search_text = search_entry.get().lower()
            for item in tags_tree.get_children():
                tags_tree.delete(item)
            
            for tag in tags:
                if search_text in tag['tag_name'].lower():
                    tags_tree.insert('', tk.END, values=(
                        tag['tag_name'],
                        tag['data_type'],
                        tag['scope']
                    ))
        
        search_entry.bind('<KeyRelease>', search_tags)
        
        # Close button
        tk.Button(
            dialog,
            text="Close",
            command=dialog.destroy,
            bg='#666666',
            fg='white',
            width=15
        ).pack(pady=10)


class VersionCompareDialog:
    """Dialog for comparing two program versions"""
    
    def __init__(self, parent, program_manager, versions: List[Dict]):
        self.program_manager = program_manager
        self.versions = versions
        
        dialog = tk.Toplevel(parent)
        dialog.title("Compare Program Versions")
        dialog.geometry("700x600")
        dialog.configure(bg='#2b2b2b')
        dialog.transient(parent)
        
        # Version selectors
        selector_frame = tk.Frame(dialog, bg='#2b2b2b')
        selector_frame.pack(fill=tk.X, padx=20, pady=20)
        
        tk.Label(selector_frame, text="Old Version:", bg='#2b2b2b', fg='white').grid(row=0, column=0, padx=5, pady=5, sticky='e')
        
        version_names = [f"v{v['version_id']} - {v.get('program_name', 'Unknown')} ({v.get('upload_timestamp', '')})" for v in versions]
        
        self.old_combo = ttk.Combobox(selector_frame, values=version_names, width=50, state='readonly')
        if len(versions) >= 2:
            self.old_combo.current(1)
        self.old_combo.grid(row=0, column=1, padx=5, pady=5)
        
        tk.Label(selector_frame, text="New Version:", bg='#2b2b2b', fg='white').grid(row=1, column=0, padx=5, pady=5, sticky='e')
        
        self.new_combo = ttk.Combobox(selector_frame, values=version_names, width=50, state='readonly')
        if len(versions) >= 1:
            self.new_combo.current(0)
        self.new_combo.grid(row=1, column=1, padx=5, pady=5)
        
        tk.Button(
            selector_frame,
            text="Compare",
            command=lambda: self._compare(dialog),
            bg='#0066cc',
            fg='white',
            width=15
        ).grid(row=2, column=1, pady=10)
        
        # Results area
        results_frame = tk.Frame(dialog, bg='#2b2b2b')
        results_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        
        self.results_text = scrolledtext.ScrolledText(
            results_frame,
            bg='#1e1e1e',
            fg='white',
            font=('Consolas', 10),
            wrap=tk.WORD
        )
        self.results_text.pack(fill=tk.BOTH, expand=True)
        
        # Close button
        tk.Button(
            dialog,
            text="Close",
            command=dialog.destroy,
            bg='#666666',
            fg='white',
            width=15
        ).pack(pady=10)
    
    def _compare(self, dialog):
        """Perform version comparison"""
        old_idx = self.old_combo.current()
        new_idx = self.new_combo.current()
        
        if old_idx == -1 or new_idx == -1:
            messagebox.showwarning("Warning", "Please select both versions")
            return
        
        old_version = self.versions[old_idx]
        new_version = self.versions[new_idx]
        
        comparison = self.program_manager.compare_versions(
            old_version['version_id'],
            new_version['version_id']
        )
        
        # Display results
        self.results_text.delete('1.0', tk.END)
        
        self.results_text.insert(tk.END, f"Comparing:\n")
        self.results_text.insert(tk.END, f"  Old: v{old_version['version_id']} ({old_version.get('upload_timestamp', '')})\n")
        self.results_text.insert(tk.END, f"  New: v{new_version['version_id']} ({new_version.get('upload_timestamp', '')})\n\n")
        self.results_text.insert(tk.END, "=" * 70 + "\n\n")
        
        # Routines (program_manager returns 'added_routines', 'deleted_routines')
        self.results_text.insert(tk.END, "ROUTINE CHANGES:\n\n")
        
        added = comparison.get('added_routines', [])
        if added:
            self.results_text.insert(tk.END, f"+ Added ({len(added)}):\n")
            for routine in added:
                self.results_text.insert(tk.END, f"  + {routine}\n")
            self.results_text.insert(tk.END, "\n")
        
        deleted = comparison.get('deleted_routines', [])
        if deleted:
            self.results_text.insert(tk.END, f"- Deleted ({len(deleted)}):\n")
            for routine in deleted:
                self.results_text.insert(tk.END, f"  - {routine}\n")
            self.results_text.insert(tk.END, "\n")
        
        # Modified rungs
        modified = comparison.get('modified_rungs', [])
        if modified:
            self.results_text.insert(tk.END, f"~ Modified Rungs ({len(modified)}):\n")
            for change in modified:
                self.results_text.insert(tk.END, f"  ~ {change['routine']} - Rung {change['rung_number']}\n")
                self.results_text.insert(tk.END, f"      Old: {change['old_text'][:80]}...\n")
                self.results_text.insert(tk.END, f"      New: {change['new_text'][:80]}...\n\n")
        
        if not added and not deleted and not modified:
            self.results_text.insert(tk.END, "No changes detected between versions.\n") 


# ============================================================
# Control Loop Tab - attached to PLCConfigWindow via monkey-patch
# ============================================================

# Settings keys for user_settings table
_CL_KEYS = [
    'cl_plc_id', 'cl_tag_feedback', 'cl_tag_output', 'cl_tag_setpoint',
    'cl_setpoint', 'cl_gain', 'cl_ki', 'cl_output_min', 'cl_output_max', 'cl_direction'
]


def _create_control_loop_tab(self):
    """Create Tab 4: Proportional Control Loop"""
    import tkinter.scrolledtext as st

    bg        = '#1e1e1e'
    fg        = 'white'
    ent_bg    = '#2b2b2b'
    btn_green = '#00aa00'
    btn_red   = '#aa0000'
    btn_blue  = '#0066cc'
    font_lbl  = ('Arial', 10)
    font_bold = ('Arial', 10, 'bold')
    font_mono = ('Consolas', 11)

    parent = self.control_loop_frame

    if not CONTROLLOOP_AVAILABLE:
        tk.Label(
            parent,
            text="controlloop.py not found.\nPlace controlloop.py in the agent folder and restart.",
            bg=bg, fg='#ff6666', font=font_bold, justify=tk.CENTER
        ).pack(expand=True)
        return

    # ---- PLC & Tag Selection ----
    sel_frame = tk.LabelFrame(parent, text="PLC & Tag Selection", bg=bg, fg=fg, font=font_bold)
    sel_frame.pack(fill=tk.X, padx=15, pady=(15, 5))

    grid = tk.Frame(sel_frame, bg=bg)
    grid.pack(fill=tk.X, padx=10, pady=10)

    def lbl(text, row, col):
        tk.Label(grid, text=text, bg=bg, fg=fg, font=font_lbl).grid(
            row=row, column=col, sticky='e', padx=6, pady=4)

    def combo(row, col, width=28):
        c = ttk.Combobox(grid, width=width, state='readonly', font=font_mono)
        c.grid(row=row, column=col, sticky='w', padx=6, pady=4)
        return c

    lbl("PLC:", 0, 0)
    self.cl_plc_combo = combo(0, 1, width=32)
    self.cl_plc_combo.bind('<<ComboboxSelected>>', self._cl_on_plc_selected)

    lbl("Feedback Tag:",  1, 0);  self.cl_fb_combo  = combo(1, 1)
    lbl("Output Tag:",    2, 0);  self.cl_out_combo = combo(2, 1)
    lbl("Setpoint Tag:",  3, 0);  self.cl_sp_combo  = combo(3, 1)

    # ---- Loop Parameters ----
    param_frame = tk.LabelFrame(parent, text="Loop Parameters", bg=bg, fg=fg, font=font_bold)
    param_frame.pack(fill=tk.X, padx=15, pady=5)

    pgrid = tk.Frame(param_frame, bg=bg)
    pgrid.pack(fill=tk.X, padx=10, pady=10)

    def plbl(text, row, col):
        tk.Label(pgrid, text=text, bg=bg, fg=fg, font=font_lbl).grid(
            row=row, column=col, sticky='e', padx=6, pady=4)

    def pent(row, col, width=12, default=''):
        e = tk.Entry(pgrid, bg=ent_bg, fg=fg, font=font_mono, width=width,
                     insertbackground='white')
        e.grid(row=row, column=col, sticky='w', padx=6, pady=4)
        e.insert(0, default)
        return e

    plbl("Setpoint:",   0, 0);  self.cl_sp_entry  = pent(0, 1, default='50.0')
    plbl("Gain (Kp):",  0, 2);  self.cl_kp_entry  = pent(0, 3, width=8, default='1.0')
    plbl("Ki:",         1, 0);  self.cl_ki_entry  = pent(1, 1, default='0.0')
    plbl("Output Min:", 2, 0);  self.cl_min_entry = pent(2, 1, default='0.0')
    plbl("Output Max:", 2, 2);  self.cl_max_entry = pent(2, 3, width=8, default='100.0')

    # Direction
    plbl("Direction:", 3, 0)
    self.cl_direction_var = tk.StringVar(value='direct')
    dir_frame = tk.Frame(pgrid, bg=bg)
    dir_frame.grid(row=3, column=1, columnspan=3, sticky='w', padx=6, pady=4)
    tk.Radiobutton(dir_frame, text="Direct",  variable=self.cl_direction_var,
                   value='direct',  bg=bg, fg=fg, selectcolor='#444444',
                   font=font_lbl, activebackground=bg).pack(side=tk.LEFT, padx=(0, 20))
    tk.Radiobutton(dir_frame, text="Reverse", variable=self.cl_direction_var,
                   value='reverse', bg=bg, fg=fg, selectcolor='#444444',
                   font=font_lbl, activebackground=bg).pack(side=tk.LEFT)

    # Reset integral on Start checkbox
    self.cl_reset_integral_var = tk.BooleanVar(value=False)
    tk.Checkbutton(
        pgrid, text="Reset integral on Start",
        variable=self.cl_reset_integral_var,
        bg=bg, fg=fg, selectcolor='#444444', activebackground=bg,
        font=font_lbl
    ).grid(row=4, column=0, columnspan=4, sticky='w', padx=6, pady=4)

    # ---- Buttons ----
    btn_frame = tk.Frame(parent, bg=bg)
    btn_frame.pack(fill=tk.X, padx=15, pady=5)

    self.cl_start_btn = tk.Button(
        btn_frame, text="▶  Start Loop", font=font_bold,
        bg=btn_green, fg='white', width=16, command=self._cl_start)
    self.cl_start_btn.pack(side=tk.LEFT, padx=(0, 8))

    self.cl_stop_btn = tk.Button(
        btn_frame, text="■  Stop Loop", font=font_bold,
        bg=btn_red, fg='white', width=16, command=self._cl_stop, state=tk.DISABLED)
    self.cl_stop_btn.pack(side=tk.LEFT, padx=(0, 8))

    tk.Button(
        btn_frame, text="Apply SP / Gain", font=font_bold,
        bg=btn_blue, fg='white', width=16, command=self._cl_apply
    ).pack(side=tk.LEFT, padx=(0, 8))

    tk.Button(
        btn_frame, text="Reset Integral", font=font_bold,
        bg='#886600', fg='white', width=14, command=self._cl_reset_integral
    ).pack(side=tk.LEFT)

    # ---- Live Readout ----
    live_frame = tk.LabelFrame(parent, text="Live Status", bg=bg, fg=fg, font=font_bold)
    live_frame.pack(fill=tk.X, padx=15, pady=5)

    lgrid = tk.Frame(live_frame, bg=bg)
    lgrid.pack(fill=tk.X, padx=10, pady=10)

    def stat(label, row, col):
        tk.Label(lgrid, text=label, bg=bg, fg='#aaaaaa', font=font_lbl).grid(
            row=row, column=col, sticky='e', padx=6)
        var = tk.StringVar(value='---')
        tk.Label(lgrid, textvariable=var, bg=bg, fg='#00ff88',
                 font=font_mono, width=14, anchor='w').grid(
            row=row, column=col+1, sticky='w', padx=6)
        return var

    self.cl_var_feedback  = stat("Feedback:",  0, 0)
    self.cl_var_setpoint  = stat("Setpoint:",  0, 2)
    self.cl_var_error     = stat("Error:",     1, 0)
    self.cl_var_output    = stat("Output:",    1, 2)
    self.cl_var_integral  = stat("Integral:",  2, 0)
    self.cl_var_cycletime = stat("Cycle ms:",  2, 2)
    self.cl_var_cycles    = stat("Cycles:",    3, 0)

    self.cl_status_label = tk.Label(
        live_frame, text="Stopped", bg=bg, fg='#ffaa00', font=font_bold)
    self.cl_status_label.pack(pady=(0, 8))

    # ---- Event Log (errors and events only - no cycle spam) ----
    log_frame = tk.LabelFrame(parent, text="Event Log", bg=bg, fg=fg, font=font_bold)
    log_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=(5, 15))

    self.cl_log = st.ScrolledText(
        log_frame, bg='#0d0d0d', fg='#00ff88', font=('Consolas', 9),
        wrap=tk.WORD, height=6, state=tk.DISABLED)
    self.cl_log.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    # Internal state
    self._control_loop    = None
    self._cl_poll_running = False
    self._cl_last_error   = ''
    self._cl_plc_list     = []
    self._cl_loading_settings = False   # guard against combo triggers during load

    # Load PLCs then restore saved config
    self._cl_load_plcs()
    self._cl_restore_settings()


def _cl_load_plcs(self):
    """Populate PLC dropdown from database - does NOT reset tag combos."""
    try:
        plcs = self.chore_db.get_all_plcs(enabled_only=False)
        self._cl_plc_list = plcs
        names = [f"{p['name']} ({p['ip_address']})" for p in plcs]
        self.cl_plc_combo['values'] = names
    except Exception as e:
        self._cl_log(f"Error loading PLCs: {e}")


def _cl_restore_settings(self):
    """Restore last saved config from user_settings. Called once on tab open."""
    self._cl_loading_settings = True
    try:
        saved_plc_id   = self.chore_db.get_setting('cl_plc_id')
        saved_fb       = self.chore_db.get_setting('cl_tag_feedback')
        saved_out      = self.chore_db.get_setting('cl_tag_output')
        saved_sp_tag   = self.chore_db.get_setting('cl_tag_setpoint')
        saved_sp       = self.chore_db.get_setting('cl_setpoint')
        saved_kp       = self.chore_db.get_setting('cl_gain')
        saved_ki       = self.chore_db.get_setting('cl_ki')
        saved_min      = self.chore_db.get_setting('cl_output_min')
        saved_max      = self.chore_db.get_setting('cl_output_max')
        saved_dir      = self.chore_db.get_setting('cl_direction')

        # Restore numeric fields
        if saved_sp:
            self.cl_sp_entry.delete(0, tk.END)
            self.cl_sp_entry.insert(0, saved_sp)
        if saved_kp:
            self.cl_kp_entry.delete(0, tk.END)
            self.cl_kp_entry.insert(0, saved_kp)
        if saved_ki:
            self.cl_ki_entry.delete(0, tk.END)
            self.cl_ki_entry.insert(0, saved_ki)
        if saved_min:
            self.cl_min_entry.delete(0, tk.END)
            self.cl_min_entry.insert(0, saved_min)
        if saved_max:
            self.cl_max_entry.delete(0, tk.END)
            self.cl_max_entry.insert(0, saved_max)
        if saved_dir:
            self.cl_direction_var.set(saved_dir)

        # Restore PLC selection
        if saved_plc_id and self._cl_plc_list:
            for i, p in enumerate(self._cl_plc_list):
                if p['id'] == saved_plc_id:
                    self.cl_plc_combo.current(i)
                    break
            else:
                self.cl_plc_combo.current(0)
        elif self._cl_plc_list:
            self.cl_plc_combo.current(0)

        # Load tags for selected PLC then restore tag selections
        idx = self.cl_plc_combo.current()
        if idx >= 0 and idx < len(self._cl_plc_list):
            plc  = self._cl_plc_list[idx]
            tags = self.chore_db.get_tags_for_plc(plc['id'])
            tag_names = [t['tag_name'] for t in tags]

            for combo, saved_val in [
                (self.cl_fb_combo,  saved_fb),
                (self.cl_out_combo, saved_out),
                (self.cl_sp_combo,  saved_sp_tag),
            ]:
                combo['values'] = tag_names
                if saved_val and saved_val in tag_names:
                    combo.current(tag_names.index(saved_val))
                elif tag_names:
                    combo.current(0)

    except Exception as e:
        self._cl_log(f"Error restoring settings: {e}")
    finally:
        self._cl_loading_settings = False


def _cl_on_plc_selected(self, event=None):
    """Refresh tag dropdowns when user manually changes PLC selection."""
    if self._cl_loading_settings:
        return  # Don't fire during settings restore
    idx = self.cl_plc_combo.current()
    if idx < 0 or idx >= len(self._cl_plc_list):
        return
    plc = self._cl_plc_list[idx]
    try:
        tags      = self.chore_db.get_tags_for_plc(plc['id'])
        tag_names = [t['tag_name'] for t in tags]
        for combo in [self.cl_fb_combo, self.cl_out_combo, self.cl_sp_combo]:
            combo['values'] = tag_names
            if tag_names:
                combo.current(0)
    except Exception as e:
        self._cl_log(f"Error loading tags: {e}")


def _cl_save_settings(self):
    """Persist current config to user_settings table."""
    try:
        idx = self.cl_plc_combo.current()
        plc_id = self._cl_plc_list[idx]['id'] if idx >= 0 and self._cl_plc_list else ''
        self.chore_db.set_setting('cl_plc_id',       plc_id)
        self.chore_db.set_setting('cl_tag_feedback',  self.cl_fb_combo.get())
        self.chore_db.set_setting('cl_tag_output',    self.cl_out_combo.get())
        self.chore_db.set_setting('cl_tag_setpoint',  self.cl_sp_combo.get())
        self.chore_db.set_setting('cl_setpoint',      self.cl_sp_entry.get())
        self.chore_db.set_setting('cl_gain',          self.cl_kp_entry.get())
        self.chore_db.set_setting('cl_ki',            self.cl_ki_entry.get())
        self.chore_db.set_setting('cl_output_min',    self.cl_min_entry.get())
        self.chore_db.set_setting('cl_output_max',    self.cl_max_entry.get())
        self.chore_db.set_setting('cl_direction',     self.cl_direction_var.get())
    except Exception as e:
        self._cl_log(f"Error saving settings: {e}")


def _cl_log(self, msg: str):
    """Append event/error line to log. NOT called every cycle."""
    from datetime import datetime
    ts   = datetime.now().strftime('%H:%M:%S.%f')[:-3]
    line = f"[{ts}] {msg}\n"
    self.cl_log.config(state=tk.NORMAL)
    self.cl_log.insert(tk.END, line)
    self.cl_log.see(tk.END)
    self.cl_log.config(state=tk.DISABLED)


def _cl_start(self):
    """Start the proportional control loop."""
    idx = self.cl_plc_combo.current()
    if idx < 0 or idx >= len(self._cl_plc_list):
        self._cl_log("No PLC selected")
        return

    plc     = self._cl_plc_list[idx]
    tag_fb  = self.cl_fb_combo.get().strip()
    tag_out = self.cl_out_combo.get().strip()
    tag_sp  = self.cl_sp_combo.get().strip()

    if not tag_fb or not tag_out or not tag_sp:
        self._cl_log("Select all three tags before starting")
        return

    try:
        sp        = float(self.cl_sp_entry.get().strip())
        kp        = float(self.cl_kp_entry.get().strip())
        ki        = float(self.cl_ki_entry.get().strip())
        o_min     = float(self.cl_min_entry.get().strip())
        o_max     = float(self.cl_max_entry.get().strip())
        direction = self.cl_direction_var.get()
        reset_int = self.cl_reset_integral_var.get()
    except ValueError as e:
        self._cl_log(f"Parameter error: {e}")
        return

    # Save config before starting
    self._cl_save_settings()

    self._control_loop = initialize_control_loop(
        ip=plc['ip_address'], slot=int(plc['slot']))
    self._control_loop.set_output_limits(o_min, o_max)

    ok = self._control_loop.start(
        tag_feedback=tag_fb,
        tag_output=tag_out,
        tag_setpoint=tag_sp,
        setpoint=sp,
        gain=kp,
        ki=ki,
        direction=direction,
        reset_integral=reset_int
    )

    if ok:
        self.cl_start_btn.config(state=tk.DISABLED)
        self.cl_stop_btn.config(state=tk.NORMAL)
        self.cl_status_label.config(text="● Running", fg='#00ff00')
        self._cl_log(
            f"Started | PLC={plc['name']} | "
            f"FB={tag_fb} OUT={tag_out} SP={tag_sp} | "
            f"SP={sp} Kp={kp} Ki={ki} dir={direction} "
            f"limits=[{o_min},{o_max}] integral={'reset' if reset_int else 'held'}"
        )
        self._cl_last_error   = ''
        self._cl_poll_running = True
        self._cl_poll()
    else:
        self._cl_log("Failed to start - check PyLogix and PLC connection")


def _cl_stop(self):
    """Stop the control loop."""
    self._cl_poll_running = False
    if self._control_loop:
        self._control_loop.stop()
    self.cl_start_btn.config(state=tk.NORMAL)
    self.cl_stop_btn.config(state=tk.DISABLED)
    self.cl_status_label.config(text="Stopped", fg='#ffaa00')
    self._cl_log("Loop stopped - output zeroed")


def _cl_apply(self):
    """Apply setpoint/gain/direction changes to a running loop."""
    if not self._control_loop or not self._control_loop.is_running():
        self._cl_log("Loop not running")
        return
    try:
        sp        = float(self.cl_sp_entry.get().strip())
        kp        = float(self.cl_kp_entry.get().strip())
        ki        = float(self.cl_ki_entry.get().strip())
        direction = self.cl_direction_var.get()
    except ValueError as e:
        self._cl_log(f"Invalid value: {e}")
        return
    self._control_loop.set_setpoint(sp)
    self._control_loop.set_gain(kp)
    self._control_loop.set_ki(ki)
    self._control_loop.set_direction(direction)
    self._cl_save_settings()
    self._cl_log(f"Applied SP={sp} Kp={kp} Ki={ki} dir={direction}")


def _cl_reset_integral(self):
    """Zero the integrator while running."""
    if not self._control_loop or not self._control_loop.is_running():
        self._cl_log("Loop not running")
        return
    self._control_loop.reset_integral()
    self._cl_log("Integral reset to 0")


def _cl_poll(self):
    """Poll loop status every 250ms - updates live readout only. No log spam."""
    if not self._cl_poll_running or not self._control_loop:
        return

    status = self._control_loop.get_status()

    self.cl_var_feedback.set(f"{status['feedback']:.4f}")
    self.cl_var_setpoint.set(f"{status['setpoint']:.4f}")
    self.cl_var_error.set(f"{status['error']:.4f}")
    self.cl_var_output.set(f"{status['output']:.4f}")
    self.cl_var_integral.set(f"{status['integral']:.4f}")
    self.cl_var_cycletime.set(f"{status['cycle_time_ms']:.2f} ms")
    self.cl_var_cycles.set(str(status['cycle_count']))

    # Only log NEW errors - never repeat
    err = status['last_error']
    if err and err != self._cl_last_error:
        self._cl_log(f"PLC error: {err}")
        self._cl_last_error = err
    elif not err:
        self._cl_last_error = ''

    # Detect unexpected stop
    if not status['running'] and self._cl_poll_running:
        self._cl_poll_running = False
        self.cl_start_btn.config(state=tk.NORMAL)
        self.cl_stop_btn.config(state=tk.DISABLED)
        self.cl_status_label.config(text="Stopped (error)", fg='#ff4444')
        self._cl_log("Loop stopped unexpectedly")
        return

    self.window.after(250, self._cl_poll)


# Attach all methods to PLCConfigWindow
PLCConfigWindow._create_control_loop_tab = _create_control_loop_tab
PLCConfigWindow._cl_load_plcs            = _cl_load_plcs
PLCConfigWindow._cl_restore_settings     = _cl_restore_settings
PLCConfigWindow._cl_on_plc_selected      = _cl_on_plc_selected
PLCConfigWindow._cl_save_settings        = _cl_save_settings
PLCConfigWindow._cl_log                  = _cl_log
PLCConfigWindow._cl_start                = _cl_start
PLCConfigWindow._cl_stop                 = _cl_stop
PLCConfigWindow._cl_apply                = _cl_apply
PLCConfigWindow._cl_reset_integral       = _cl_reset_integral
PLCConfigWindow._cl_poll                 = _cl_poll


def open_plc_config_window(chore_db, plc_comm, on_close=None):
    """
    Open the PLC Configuration window
    
    Args:
        chore_db: ChoreDatabase instance
        plc_comm: PLCCommunicator instance
        on_close: Optional callback when window closes
    
    Returns:
        PLCConfigWindow instance
    """
    return PLCConfigWindow(chore_db, plc_comm, on_close)