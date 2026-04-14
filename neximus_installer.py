"""
Neximus AI Agent - Installer
Full clean rewrite - non-blocking, streaming output, cancellable
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import subprocess
import threading
import sys
import os
import shutil
import winreg
import queue

# ── Locate installer directory from __file__ (always correct) ─────────────
INSTALLER_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Source paths (all relative to installer folder) ───────────────────────
GROK_PHASE2 = os.path.join(INSTALLER_DIR, "grok_agent")
DB_BACKUP   = os.path.join(INSTALLER_DIR, "grok_agent_03142026.sql")
PIPER_SRC   = os.path.join(INSTALLER_DIR, "piper tts")

# ── Nested agent path inside grok_phase2 ──────────────────────────────────
AGENT_REL = "agent"

# ── All packages to install ───────────────────────────────────────────────
PACKAGES = [
    "sentence-transformers",
    "chromadb",
    "SpeechRecognition",
    "openai-whisper",
    "gtts",
    "pydub",
    "sounddevice",
    "tkinterdnd2",
    "pycomm3",
    "pvporcupine",
    "keyboard",
    "psycopg2-binary",
    "mss",
    "Pillow",
    "torch",
    "transformers",
    "accelerate",
    "flask",
    "apscheduler",
    "geopy",
    "astral",
    "pytz",
    "requests",
    "pylogix",
]

# ── Colors ────────────────────────────────────────────────────────────────
BG     = '#1a1a1a'
BG2    = '#252525'
BG3    = '#333333'
BLUE   = '#0066cc'
GREEN  = '#00aa00'
ORANGE = '#cc6600'
RED    = '#cc2200'
WHITE  = '#ffffff'
GRAY   = '#777777'
LGRAY  = '#cccccc'
CYAN   = '#00aaff'
YELLOW = '#ffcc00'


def detect_pg_bin():
    for ver in ['18', '17', '16', '15', '14']:
        p = rf"C:\Program Files\PostgreSQL\{ver}\bin"
        if os.path.isfile(os.path.join(p, "psql.exe")):
            return p
    for hive in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
        try:
            k = winreg.OpenKey(hive, r"SOFTWARE\PostgreSQL\Installations")
            for i in range(winreg.QueryInfoKey(k)[0]):
                sub = winreg.EnumKey(k, i)
                sk = winreg.OpenKey(k, sub)
                try:
                    base, _ = winreg.QueryValueEx(sk, "Base Directory")
                    p = os.path.join(base, "bin")
                    if os.path.isfile(os.path.join(p, "psql.exe")):
                        return p
                except:
                    pass
        except:
            pass
    return r"C:\Program Files\PostgreSQL\18\bin"


class NeximusInstaller(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("Neximus AI Agent - Installer")
        self.geometry("860x780")
        self.configure(bg=BG)
        self.resizable(True, True)

        self.install_path  = tk.StringVar(value=r"C:\Neximus")
        self.piper_dest    = tk.StringVar(value=r"C:\Neximus\piper tts")
        self.grok_api_key  = tk.StringVar()
        self.db_password   = tk.StringVar()
        self.db_name       = tk.StringVar(value="grok_agent_db")
        self.db_port       = tk.StringVar(value="5433")
        self.pg_bin        = tk.StringVar(value=detect_pg_bin())
        self.mic_index     = tk.StringVar(value="0")

        self.steps_done    = {}
        self.cancel_event  = threading.Event()
        self.log_queue     = queue.Queue()
        self.current_step  = 0

        self._build_ui()
        self._poll_log()
        self._show_step(0)

    def log(self, msg, tag=None):
        self.log_queue.put((msg, tag))

    def _poll_log(self):
        try:
            while True:
                msg, tag = self.log_queue.get_nowait()
                self._log_box.config(state=tk.NORMAL)
                if tag:
                    self._log_box.insert(tk.END, msg + "\n", tag)
                else:
                    self._log_box.insert(tk.END, msg + "\n")
                self._log_box.see(tk.END)
                self._log_box.config(state=tk.DISABLED)
        except queue.Empty:
            pass
        self.after(50, self._poll_log)

    def _build_ui(self):
        hdr = tk.Frame(self, bg='#111111', height=60)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)
        tk.Label(hdr, text="NEXIMUS  AI  AGENT", bg='#111111', fg=WHITE,
                 font=('Helvetica', 17, 'bold')).pack(side=tk.LEFT, padx=20)
        tk.Label(hdr, text="Installer", bg='#111111', fg=GRAY,
                 font=('Helvetica', 11)).pack(side=tk.LEFT)

        body = tk.Frame(self, bg=BG)
        body.pack(fill=tk.BOTH, expand=True)

        sb = tk.Frame(body, bg='#111111', width=180)
        sb.pack(side=tk.LEFT, fill=tk.Y)
        sb.pack_propagate(False)
        tk.Label(sb, text="STEPS", bg='#111111', fg=GRAY,
                 font=('Helvetica', 7, 'bold')).pack(anchor='w', padx=14, pady=(12, 4))
        self._step_btns = []
        for i, name in enumerate([
            "1  Detect paths",
            "2  Install location",
            "3  Copy agent files",
            "4  Copy Piper TTS",
            "5  API key & env",
            "6  Database restore",
            "7  Python packages",
            "8  Update config",
            "9  Verify & launch",
        ]):
            lbl = tk.Label(sb, text=name, bg='#111111', fg=GRAY,
                           font=('Helvetica', 9), anchor='w', padx=14)
            lbl.pack(fill=tk.X, pady=1)
            self._step_btns.append(lbl)

        self._content = tk.Frame(body, bg=BG)
        self._content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        log_outer = tk.Frame(self, bg=BG2)
        log_outer.pack(fill=tk.BOTH, side=tk.BOTTOM, expand=True)

        log_hdr = tk.Frame(log_outer, bg=BG2)
        log_hdr.pack(fill=tk.X)
        tk.Label(log_hdr, text="Install log", bg=BG2, fg=GRAY,
                 font=('Helvetica', 8)).pack(side=tk.LEFT, padx=10, pady=(5, 0))
        self._cancel_btn = tk.Button(log_hdr, text="Cancel current step",
                                     command=self._cancel,
                                     bg=BG3, fg=GRAY, font=('Helvetica', 8),
                                     relief=tk.FLAT, padx=8, pady=2, state=tk.DISABLED)
        self._cancel_btn.pack(side=tk.RIGHT, padx=10, pady=(5, 0))

        sb2 = tk.Scrollbar(log_outer)
        sb2.pack(side=tk.RIGHT, fill=tk.Y)
        self._log_box = tk.Text(log_outer, bg='#0d0d0d', fg=CYAN,
                                font=('Courier', 9), state=tk.DISABLED,
                                relief=tk.FLAT, yscrollcommand=sb2.set, height=18)
        self._log_box.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 6))
        self._log_box.tag_config('ok',   foreground=GREEN)
        self._log_box.tag_config('err',  foreground=RED)
        self._log_box.tag_config('warn', foreground=YELLOW)
        self._log_box.tag_config('hdr',  foreground=WHITE)
        sb2.config(command=self._log_box.yview)

        self._progress = ttk.Progressbar(self, maximum=9, value=0)
        self._progress.pack(fill=tk.X, side=tk.BOTTOM)

    def _cancel(self):
        self.cancel_event.set()
        self.log("-- Cancel requested --", 'warn')
        self._cancel_btn.config(state=tk.DISABLED)

    def _enable_cancel(self):
        self.cancel_event.clear()
        self._cancel_btn.config(state=tk.NORMAL)

    def _disable_cancel(self):
        self._cancel_btn.config(state=tk.DISABLED)

    def _highlight_step(self, idx):
        for i, lbl in enumerate(self._step_btns):
            if i < idx:
                lbl.config(fg=GREEN, font=('Helvetica', 9))
            elif i == idx:
                lbl.config(fg=WHITE, font=('Helvetica', 9, 'bold'))
            else:
                lbl.config(fg=GRAY, font=('Helvetica', 9))
        self._progress['value'] = idx

    def _clear(self):
        for w in self._content.winfo_children():
            w.destroy()

    def _show_step(self, idx):
        self.current_step = idx
        self._highlight_step(idx)
        self._clear()
        [
            self._step_detect,
            self._step_location,
            self._step_copy_agent,
            self._step_copy_piper,
            self._step_env,
            self._step_database,
            self._step_packages,
            self._step_config,
            self._step_verify,
        ][idx]()

    def _title(self, text, sub=""):
        tk.Label(self._content, text=text, bg=BG, fg=WHITE,
                 font=('Helvetica', 13, 'bold')).pack(anchor='w', padx=20, pady=(18, 2))
        if sub:
            tk.Label(self._content, text=sub, bg=BG, fg=GRAY,
                     font=('Helvetica', 9)).pack(anchor='w', padx=20, pady=(0, 8))
        ttk.Separator(self._content).pack(fill=tk.X, padx=20, pady=(0, 12))

    def _field(self, parent, label, var, browse=False, show=None):
        tk.Label(parent, text=label, bg=BG, fg=LGRAY,
                 font=('Helvetica', 9)).pack(anchor='w', pady=(4, 1))
        row = tk.Frame(parent, bg=BG)
        row.pack(fill=tk.X, pady=(0, 6))
        e = tk.Entry(row, textvariable=var, bg=BG2, fg=WHITE,
                     insertbackground=WHITE, font=('Courier', 9),
                     relief=tk.FLAT, show=show)
        e.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=6, padx=(0, 4))
        if browse:
            def _pick(v=var):
                p = filedialog.askdirectory()
                if p:
                    v.set(p.replace('/', '\\'))
            tk.Button(row, text="Browse", command=_pick, bg=BG3, fg=WHITE,
                      font=('Helvetica', 8), relief=tk.FLAT, padx=10,
                      pady=6).pack(side=tk.RIGHT)

    def _status(self, parent):
        lbl = tk.Label(parent, text="", bg=BG, fg=GRAY,
                       font=('Helvetica', 9), wraplength=560, justify='left')
        lbl.pack(anchor='w', pady=4)
        return lbl

    def _btn_row(self, action_label, action_cmd, action_color=BLUE, next_step=None):
        row = tk.Frame(self._content, bg=BG)
        row.pack(anchor='e', padx=20, pady=12)
        action = tk.Button(row, text=action_label, command=action_cmd,
                           bg=action_color, fg=WHITE, font=('Helvetica', 10, 'bold'),
                           relief=tk.FLAT, padx=20, pady=8)
        action.pack(side=tk.LEFT, padx=(0, 8))
        nxt = tk.Button(row, text="Next ->",
                        command=lambda: self._show_step(next_step) if next_step is not None else None,
                        bg=BG3, fg=WHITE, font=('Helvetica', 10),
                        relief=tk.FLAT, padx=20, pady=8,
                        state=tk.DISABLED)
        nxt.pack(side=tk.LEFT)
        return action, nxt

    def _check_row(self, parent, label, ok):
        row = tk.Frame(parent, bg=BG2)
        row.pack(fill=tk.X, pady=2)
        tk.Label(row, text="OK" if ok else "X", bg=BG2,
                 fg=GREEN if ok else RED,
                 font=('Helvetica', 11, 'bold'), width=3).pack(side=tk.LEFT, padx=6)
        tk.Label(row, text=label, bg=BG2, fg=LGRAY,
                 font=('Helvetica', 9)).pack(side=tk.LEFT, pady=6)

    # ── STEP 0 — DETECT ───────────────────────────────────────────────────

    def _step_detect(self):
        self._title("Step 1 - Detecting files on drive",
                    "Checking what was found in the installer folder.")
        f = tk.Frame(self._content, bg=BG)
        f.pack(fill=tk.X, padx=20)

        items = [
            ("grok_agent folder",                  os.path.isdir(GROK_PHASE2)),
            ("DB backup: grok_agent_03142026.sql",  os.path.isfile(DB_BACKUP)),
            ("Piper TTS folder",                    os.path.isdir(PIPER_SRC)),
        ]
        all_ok = all(ok for _, ok in items)
        for label, ok in items:
            self._check_row(f, label, ok)
            self.log(f"{'OK' if ok else 'NOT FOUND'}: {label}")

        self.log(f"Installer dir: {INSTALLER_DIR}", 'hdr')

        # Check Python version
        ver = sys.version_info
        self.log(f"Python version: {ver.major}.{ver.minor}.{ver.micro}", 'hdr')
        if ver.major == 3 and ver.minor >= 14:
            self.log("WARNING: Python 3.14+ detected. PyAudio and other packages", 'warn')
            self.log("may not install correctly. Python 3.11-3.13 is recommended.", 'warn')
            tk.Label(f, text="WARNING: Python 3.14+ detected!\nPyAudio requires Python 3.11-3.13.\nDowngrade Python before continuing.",
                     bg=BG, fg=RED, font=('Helvetica', 9, 'bold'),
                     wraplength=560, justify='left').pack(anchor='w', pady=8)

        if not all_ok:
            tk.Label(f, text=(
                "One or more required files were not found.\n"
                "Make sure INSTALL_NEXIMUS.bat, neximus_installer.py, grok_agent, "
                "piper tts, and grok_agent_03142026.sql are all in the same folder."
            ), bg=BG, fg=YELLOW, font=('Helvetica', 8),
                wraplength=560, justify='left').pack(anchor='w', pady=8)

        pg = detect_pg_bin()
        self.pg_bin.set(pg)
        pg_found = os.path.isfile(os.path.join(pg, "psql.exe"))
        tk.Label(f,
                 text=f"PostgreSQL detected: {pg}" if pg_found
                      else f"PostgreSQL not found at {pg} - set path manually in Step 6",
                 bg=BG, fg=GREEN if pg_found else YELLOW,
                 font=('Helvetica', 8)).pack(anchor='w', pady=4)

        _, nxt = self._btn_row("Refresh", self._step_detect, action_color=BG3, next_step=1)
        nxt.config(state=tk.NORMAL, bg=BLUE)

    # ── STEP 1 — LOCATION ─────────────────────────────────────────────────

    def _step_location(self):
        self._title("Step 2 - Choose install location",
                    "Where should Neximus be installed on this PC?")
        f = tk.Frame(self._content, bg=BG)
        f.pack(fill=tk.X, padx=20)
        self._field(f, "Install folder (grok_agent will be copied here):",
                    self.install_path, browse=True)
        tk.Label(f, text="Example:  C:\\Neximus   or   C:\\Users\\YourName\\Desktop",
                 bg=BG, fg=GRAY, font=('Helvetica', 8)).pack(anchor='w')
        self._field(f, "Microphone device index (0 = default, 1 = Focusrite etc.):",
                    self.mic_index)

        def _validate():
            if not self.install_path.get().strip():
                messagebox.showerror("Required", "Please enter an install folder.")
                return
            self.piper_dest.set(os.path.join(self.install_path.get(), "piper tts"))
            self._show_step(2)

        _, nxt = self._btn_row("Confirm", _validate, next_step=None)
        nxt.pack_forget()
        tk.Button(self._content, text="Confirm & Next ->", command=_validate,
                  bg=BLUE, fg=WHITE, font=('Helvetica', 10, 'bold'),
                  relief=tk.FLAT, padx=20, pady=8).pack(anchor='e', padx=20, pady=12)

    # ── STEP 2 — COPY AGENT ───────────────────────────────────────────────

    def _step_copy_agent(self):
        self._title("Step 3 - Copy agent files",
                    "Copy grok_agent from the drive to this PC.")
        f = tk.Frame(self._content, bg=BG)
        f.pack(fill=tk.X, padx=20)

        dest = os.path.join(self.install_path.get(), "grok_agent")
        tk.Label(f, text=f"From:  {GROK_PHASE2}", bg=BG, fg=CYAN,
                 font=('Courier', 8)).pack(anchor='w', pady=2)
        tk.Label(f, text=f"To:    {dest}", bg=BG, fg=CYAN,
                 font=('Courier', 8)).pack(anchor='w', pady=2)

        self._copy_status = self._status(f)
        action, nxt = self._btn_row("Copy files now", None, next_step=3)
        action.config(command=lambda: self._run_copy_agent(dest, action, nxt))

    def _run_copy_agent(self, dest, btn, nxt):
        btn.config(state=tk.DISABLED, text="Copying...")
        self._enable_cancel()
        self._copy_status.config(text="Copying... this may take a minute.", fg=CYAN)
        self.log("Copying grok_agent...", 'hdr')

        def worker():
            try:
                if self.cancel_event.is_set():
                    return
                if os.path.exists(dest):
                    self.log(f"Removing existing: {dest}")
                    shutil.rmtree(dest)
                shutil.copytree(GROK_PHASE2, dest, copy_function=self._copy_with_log)
                if self.cancel_event.is_set():
                    self.log("Copy cancelled.", 'warn')
                    self.after(0, lambda: self._copy_status.config(text="Cancelled.", fg=YELLOW))
                    return
                self.log("Copy complete.", 'ok')
                self.steps_done['copy'] = True
                self.after(0, lambda: (
                    self._copy_status.config(text="Files copied.", fg=GREEN),
                    nxt.config(state=tk.NORMAL, bg=BLUE)
                ))
            except Exception as e:
                self.log(f"ERROR: {e}", 'err')
                self.after(0, lambda: (
                    self._copy_status.config(text=f"Error: {e}", fg=RED),
                    btn.config(state=tk.NORMAL, text="Retry")
                ))
            finally:
                self.after(0, self._disable_cancel)

        threading.Thread(target=worker, daemon=True).start()

    def _copy_with_log(self, src, dst):
        if self.cancel_event.is_set():
            raise InterruptedError("Cancelled by user")
        self.log(f"  {os.path.basename(src)}")
        shutil.copy2(src, dst)

    # ── STEP 3 — COPY PIPER ───────────────────────────────────────────────

    def _step_copy_piper(self):
        self._title("Step 4 - Copy Piper TTS",
                    "Copy the Piper TTS engine to this PC.")
        f = tk.Frame(self._content, bg=BG)
        f.pack(fill=tk.X, padx=20)

        tk.Label(f, text=f"From:  {PIPER_SRC}", bg=BG, fg=CYAN,
                 font=('Courier', 8)).pack(anchor='w', pady=2)
        self._field(f, "Copy Piper to:", self.piper_dest, browse=True)

        self._piper_status = self._status(f)
        action, nxt = self._btn_row("Copy Piper now", None, next_step=4)
        action.config(command=lambda: self._run_copy_piper(action, nxt))

    def _run_copy_piper(self, btn, nxt):
        dest = self.piper_dest.get()
        if not dest:
            messagebox.showerror("Required", "Enter a destination for Piper TTS.")
            return
        btn.config(state=tk.DISABLED, text="Copying...")
        self._enable_cancel()
        self._piper_status.config(text="Copying Piper TTS...", fg=CYAN)
        self.log("Copying Piper TTS...", 'hdr')

        def worker():
            try:
                if os.path.exists(dest):
                    shutil.rmtree(dest)
                shutil.copytree(PIPER_SRC, dest, copy_function=self._copy_with_log)
                if self.cancel_event.is_set():
                    self.log("Cancelled.", 'warn')
                    self.after(0, lambda: self._piper_status.config(text="Cancelled.", fg=YELLOW))
                    return
                self.log("Piper copy complete.", 'ok')
                self.steps_done['piper'] = True
                self.after(0, lambda: (
                    self._piper_status.config(text="Piper TTS copied.", fg=GREEN),
                    nxt.config(state=tk.NORMAL, bg=BLUE)
                ))
            except Exception as e:
                self.log(f"ERROR: {e}", 'err')
                self.after(0, lambda: (
                    self._piper_status.config(text=f"Error: {e}", fg=RED),
                    btn.config(state=tk.NORMAL, text="Retry")
                ))
            finally:
                self.after(0, self._disable_cancel)

        threading.Thread(target=worker, daemon=True).start()

    # ── STEP 4 — ENV VARS ─────────────────────────────────────────────────

    def _step_env(self):
        self._title("Step 5 - API Key & Environment Variables",
                    "Set your Grok API key. No Administrator rights needed.")
        f = tk.Frame(self._content, bg=BG)
        f.pack(fill=tk.X, padx=20)

        self._field(f, "GROK_API_KEY:", self.grok_api_key, show='*')

        show_var = tk.BooleanVar(value=False)
        entries = []

        def _toggle_show():
            for e in entries:
                e.config(show='' if show_var.get() else '*')

        tk.Checkbutton(f, text="Show key", variable=show_var,
                       command=_toggle_show, bg=BG, fg=GRAY,
                       selectcolor=BG2, activebackground=BG,
                       font=('Helvetica', 8)).pack(anchor='w')

        self._field(f, "DB_PASSWORD (leave blank if PostgreSQL has no password):",
                    self.db_password, show='*')

        tk.Label(f,
                 text="These are saved as Windows user environment variables.\n"
                      "You will need to restart Windows once after install for them to activate.",
                 bg=BG, fg=GRAY, font=('Helvetica', 8),
                 wraplength=560, justify='left').pack(anchor='w', pady=6)

        self._env_status = self._status(f)
        action, nxt = self._btn_row("Set environment variables", None, next_step=5)
        action.config(command=lambda: self._run_set_env(action, nxt))

    def _run_set_env(self, btn, nxt):
        key = self.grok_api_key.get().strip()
        if not key:
            messagebox.showerror("Required", "Please enter your GROK_API_KEY.")
            return
        btn.config(state=tk.DISABLED, text="Setting...")
        self.log("Setting environment variables...", 'hdr')

        def worker():
            try:
                reg = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                     "Environment", 0, winreg.KEY_SET_VALUE)
                winreg.SetValueEx(reg, "GROK_API_KEY", 0, winreg.REG_SZ, key)
                db_pw = self.db_password.get().strip()
                if db_pw:
                    winreg.SetValueEx(reg, "DB_PASSWORD", 0, winreg.REG_SZ, db_pw)
                winreg.CloseKey(reg)

                subprocess.run(['setx', 'GROK_API_KEY', key], capture_output=True, text=True)
                if db_pw:
                    subprocess.run(['setx', 'DB_PASSWORD', db_pw], capture_output=True, text=True)

                self.log("GROK_API_KEY set.", 'ok')
                if db_pw:
                    self.log("DB_PASSWORD set.", 'ok')
                self.log("Restart Windows after install to activate.", 'warn')
                self.steps_done['env'] = True
                self.after(0, lambda: (
                    self._env_status.config(
                        text="Environment variables set. Restart Windows after install.",
                        fg=GREEN),
                    nxt.config(state=tk.NORMAL, bg=BLUE)
                ))
            except Exception as e:
                self.log(f"ERROR: {e}", 'err')
                self.after(0, lambda: (
                    self._env_status.config(text=f"Error: {e}", fg=RED),
                    btn.config(state=tk.NORMAL, text="Retry")
                ))

        threading.Thread(target=worker, daemon=True).start()

    # ── STEP 5 — DATABASE ─────────────────────────────────────────────────

    def _step_database(self):
        self._title("Step 6 - Restore PostgreSQL Database",
                    "Create the database and restore from backup.")
        f = tk.Frame(self._content, bg=BG)
        f.pack(fill=tk.X, padx=20)

        self._field(f, "Database name:", self.db_name)
        self._field(f, "PostgreSQL port:", self.db_port)
        self._field(f, "PostgreSQL bin folder (where psql.exe is):",
                    self.pg_bin, browse=True)
        self._field(f, "PostgreSQL password for 'postgres' user (leave blank if none):",
                    self.db_password, show='*')

        tk.Label(f, text=f"Backup file:  {DB_BACKUP}",
                 bg=BG, fg=CYAN, font=('Courier', 8)).pack(anchor='w', pady=4)
        tk.Label(f,
                 text="The password is passed directly to psql via PGPASSWORD env var.\n"
                      "If restore shows warnings but completes, that is normal.",
                 bg=BG, fg=GRAY, font=('Helvetica', 8),
                 wraplength=560, justify='left').pack(anchor='w', pady=4)

        self._db_status = self._status(f)
        action, nxt = self._btn_row("Restore database", None,
                                    action_color=GREEN, next_step=6)
        action.config(command=lambda: self._run_db_restore(action, nxt))

    def _run_db_restore(self, btn, nxt):
        psql = os.path.join(self.pg_bin.get(), "psql.exe")
        if not os.path.isfile(psql):
            messagebox.showerror("Not found",
                                 f"psql.exe not found at:\n{psql}\n\n"
                                 "Update the PostgreSQL bin folder path.")
            return
        if not os.path.isfile(DB_BACKUP):
            messagebox.showerror("Not found", f"Backup file not found:\n{DB_BACKUP}")
            return

        btn.config(state=tk.DISABLED, text="Restoring...")
        self._enable_cancel()
        self._db_status.config(text="Restoring database...", fg=CYAN)
        self.log("Starting database restore...", 'hdr')

        db   = self.db_name.get()
        port = self.db_port.get()

        def stream_cmd(cmd, label):
            self.log(f"Running: {label}")
            env = os.environ.copy()
            pg_pw = self.db_password.get().strip()
            if pg_pw:
                env['PGPASSWORD'] = pg_pw
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, env=env, bufsize=1)
            for line in proc.stdout:
                line = line.rstrip()
                if line:
                    self.log(f"  {line}")
                if self.cancel_event.is_set():
                    proc.terminate()
                    return -1
            proc.wait()
            return proc.returncode

        def worker():
            try:
                create_cmd = [psql, "-U", "postgres", "-p", port,
                              "-c", f"CREATE DATABASE {db};"]
                rc = stream_cmd(create_cmd, f"CREATE DATABASE {db}")
                if self.cancel_event.is_set():
                    self.log("Cancelled.", 'warn')
                    self.after(0, lambda: self._db_status.config(text="Cancelled.", fg=YELLOW))
                    return

                # Plain SQL dump — use psql not pg_restore
                psql_exe = os.path.join(self.pg_bin.get(), "psql.exe")
                restore_cmd = [psql_exe,
                               "-U", "postgres",
                               "-p", port,
                               "-d", db,
                               "-f", DB_BACKUP]
                rc = stream_cmd(restore_cmd, "Restore schema from SQL file")

                if self.cancel_event.is_set():
                    self.log("Cancelled.", 'warn')
                    self.after(0, lambda: self._db_status.config(text="Cancelled.", fg=YELLOW))
                    return

                if rc == 0:
                    self.log("Database restore complete.", 'ok')
                    self.steps_done['db'] = True
                    self.after(0, lambda: (
                        self._db_status.config(text="Database restored.", fg=GREEN),
                        nxt.config(state=tk.NORMAL, bg=BLUE)
                    ))
                else:
                    self.log(f"psql exited with code {rc} - check log above.", 'warn')
                    self.after(0, lambda: (
                        self._db_status.config(
                            text="Restore finished with warnings - check log. Click Next if OK.",
                            fg=YELLOW),
                        nxt.config(state=tk.NORMAL, bg=ORANGE)
                    ))
            except Exception as e:
                self.log(f"ERROR: {e}", 'err')
                self.after(0, lambda: (
                    self._db_status.config(text=f"Error: {e}", fg=RED),
                    btn.config(state=tk.NORMAL, text="Retry")
                ))
            finally:
                self.after(0, self._disable_cancel)

        threading.Thread(target=worker, daemon=True).start()

    # ── STEP 6 — PACKAGES ─────────────────────────────────────────────────

    def _step_packages(self):
        self._title("Step 7 - Install Python packages",
                    "Each package installs one at a time. Output streams live.")
        f = tk.Frame(self._content, bg=BG)
        f.pack(fill=tk.X, padx=20)

        bar_row = tk.Frame(f, bg=BG)
        bar_row.pack(fill=tk.X, pady=(0, 4))
        self._pkg_counter = tk.Label(bar_row, text=f"0 / {len(PACKAGES)}",
                                     bg=BG, fg=GRAY, font=('Helvetica', 8))
        self._pkg_counter.pack(side=tk.RIGHT)
        self._pkg_bar = ttk.Progressbar(f, maximum=len(PACKAGES), value=0)
        self._pkg_bar.pack(fill=tk.X, pady=(0, 6))

        self._pkg_cur = tk.Label(f, text="Ready - press Install packages to begin.",
                                 bg=BG, fg=CYAN, font=('Courier', 9), anchor='w')
        self._pkg_cur.pack(fill=tk.X, pady=(0, 4))

        self._pkg_failed = tk.Label(f, text="", bg=BG, fg=RED,
                                    font=('Helvetica', 8), wraplength=560, justify='left')
        self._pkg_failed.pack(anchor='w')

        action, nxt = self._btn_row("Install packages", None,
                                    action_color=BLUE, next_step=7)
        action.config(command=lambda: self._run_packages(action, nxt))

    def _run_packages(self, btn, nxt):
        btn.config(state=tk.DISABLED, text="Installing...")
        self._enable_cancel()
        self.log(f"Installing {len(PACKAGES)} packages...", 'hdr')
        failed = []

        def update_labels(pkg, i):
            self._pkg_cur.config(
                text=f"Installing: {pkg}  ({i+1} of {len(PACKAGES)})", fg=CYAN)
            self._pkg_counter.config(text=f"{i} / {len(PACKAGES)}")
            self._pkg_bar.config(value=i)

        def update_done(i):
            self._pkg_bar.config(value=i + 1)
            self._pkg_counter.config(text=f"{i+1} / {len(PACKAGES)}")

        def worker():
            for i, pkg in enumerate(PACKAGES):
                if self.cancel_event.is_set():
                    self.log("Cancelled by user.", 'warn')
                    break

                self.after(0, lambda p=pkg, n=i: update_labels(p, n))
                self.log(f">> pip install {pkg}", 'hdr')

                try:
                    proc = subprocess.Popen(
                        [sys.executable, "-m", "pip", "install", pkg, "--no-cache-dir"],
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                        text=True, bufsize=1)
                    for line in proc.stdout:
                        line = line.rstrip()
                        if line:
                            self.log(f"  {line}")
                        if self.cancel_event.is_set():
                            proc.terminate()
                            break
                    proc.wait()
                    rc = proc.returncode
                except Exception as e:
                    self.log(f"  ERROR launching pip: {e}", 'err')
                    rc = 1

                if rc == 0:
                    self.log(f"  OK: {pkg}", 'ok')
                else:
                    self.log(f"  FAILED: {pkg}", 'err')
                    failed.append(pkg)

                self.after(0, lambda n=i: update_done(n))

            # Special case: PyAudio — download matching pre-built wheel from PyPI
            # Wheels available for Python 3.8-3.13 on Windows 32/64-bit
            if not self.cancel_event.is_set():
                self.log(">> Installing PyAudio (pre-built wheel)...", 'hdr')
                self.after(0, lambda: self._pkg_cur.config(
                    text="Installing PyAudio (pre-built wheel)...", fg=CYAN))
                try:
                    import platform
                    ver = sys.version_info
                    cp = f"cp{ver.major}{ver.minor}"
                    bits = "win_amd64" if platform.machine().endswith("64") else "win32"

                    # Direct PyPI wheel URLs for PyAudio 0.2.14
                    wheel_map = {
                        ("cp313", "win_amd64"): "https://files.pythonhosted.org/packages/a5/8b/7f9a061c1cc2b230f9ac02a6003fcd14c85ce1828013aecbaf45aa988d20/PyAudio-0.2.14-cp313-cp313-win_amd64.whl",
                        ("cp313", "win32"):     "https://files.pythonhosted.org/packages/3a/77/66cd37111a87c1589b63524f3d3c848011d21ca97828422c7fde7665ff0d/PyAudio-0.2.14-cp313-cp313-win32.whl",
                        ("cp312", "win_amd64"): "https://files.pythonhosted.org/packages/b0/6a/d25812e5f79f06285767ec607b39149d02aa3b31d50c2269768f48768930/PyAudio-0.2.14-cp312-cp312-win_amd64.whl",
                        ("cp311", "win_amd64"): "https://files.pythonhosted.org/packages/82/d8/f043c854aad450a76e476b0cf9cda1956419e1dacf1062eb9df3c0055abe/PyAudio-0.2.14-cp311-cp311-win_amd64.whl",
                        ("cp310", "win_amd64"): "https://files.pythonhosted.org/packages/27/bc/719d140ee63cf4b0725016531d36743a797ffdbab85e8536922902c9349a/PyAudio-0.2.14-cp310-cp310-win_amd64.whl",
                        ("cp39",  "win_amd64"): "https://files.pythonhosted.org/packages/ac/9e/cb59be3b49a6c1ee6350f27ca1abae2be2c7e643eac63cf10c399c4d6f71/PyAudio-0.2.14-cp39-cp39-win_amd64.whl",
                    }

                    wheel_url = wheel_map.get((cp, bits))
                    if wheel_url:
                        self.log(f"  Using wheel for {cp}-{bits}")
                        cmd = [sys.executable, "-m", "pip", "install", wheel_url, "--no-cache-dir"]
                    else:
                        self.log(f"  No pre-built wheel for {cp}-{bits}, trying generic install")
                        cmd = [sys.executable, "-m", "pip", "install", "PyAudio==0.2.14", "--no-cache-dir"]

                    proc = subprocess.Popen(
                        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                        text=True, bufsize=1)
                    for line in proc.stdout:
                        line = line.rstrip()
                        if line:
                            self.log(f"  {line}")
                    proc.wait()
                    if proc.returncode == 0:
                        self.log("  OK: pyaudio", 'ok')
                    else:
                        self.log("  FAILED: pyaudio - voice playback may not work", 'warn')
                        failed.append("pyaudio")
                except Exception as e:
                    self.log(f"  ERROR installing pyaudio: {e}", 'err')
                    failed.append("pyaudio")

            def finish():
                if failed:
                    self._pkg_cur.config(
                        text=f"Done - {len(failed)} package(s) failed.", fg=YELLOW)
                    self._pkg_failed.config(
                        text="Failed: " + ", ".join(failed) +
                             "\nYou can retry failed ones manually after install.")
                    nxt.config(state=tk.NORMAL, bg=ORANGE)
                elif self.cancel_event.is_set():
                    self._pkg_cur.config(text="Cancelled.", fg=YELLOW)
                else:
                    self._pkg_cur.config(
                        text=f"All packages installed.", fg=GREEN)
                    self.steps_done['packages'] = True
                    nxt.config(state=tk.NORMAL, bg=BLUE)
                self._disable_cancel()

            self.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    # ── STEP 7 — CONFIG ───────────────────────────────────────────────────

    def _step_config(self):
        self._title("Step 8 - Update config files",
                    "Patch config/config.py with paths and settings for this PC.")
        f = tk.Frame(self._content, bg=BG)
        f.pack(fill=tk.X, padx=20)

        agent_path  = os.path.join(self.install_path.get(), "grok_agent", AGENT_REL)
        piper_exe   = os.path.join(self.piper_dest.get(), "piper_windows_amd64", "piper", "piper.exe")
        piper_model = os.path.join(self.piper_dest.get(), "en_GB-alan-medium.onnx")

        changes = [
            ("AGENT_SOURCE_PATH",  agent_path),
            ("PIPER_EXE_PATH",     piper_exe),
            ("PIPER_MODEL_PATH",   piper_model),
            ("MICROPHONE_INDEX",   self.mic_index.get()),
            ("DB port",            self.db_port.get()),
        ]
        for label, val in changes:
            row = tk.Frame(f, bg=BG2)
            row.pack(fill=tk.X, pady=1)
            tk.Label(row, text=label, bg=BG2, fg=GRAY,
                     font=('Helvetica', 8), width=20, anchor='w').pack(
                side=tk.LEFT, padx=6, pady=4)
            tk.Label(row, text=val, bg=BG2, fg=CYAN,
                     font=('Courier', 7)).pack(side=tk.LEFT, padx=4)

        self._cfg_status = self._status(f)
        action, nxt = self._btn_row("Update config files", None,
                                    action_color=ORANGE, next_step=8)
        action.config(command=lambda: self._run_config(
            agent_path, piper_exe, piper_model, action, nxt))

    def _run_config(self, agent_path, piper_exe, piper_model, btn, nxt):
        btn.config(state=tk.DISABLED, text="Updating...")
        self.log("Patching config/config.py...", 'hdr')

        base = os.path.join(self.install_path.get(), "grok_agent")

        def worker():
            import re

            def safe_replace(pattern, replacement, text):
                return re.sub(pattern, lambda m: replacement, text)

            patched = 0
            errors  = []

            # Find all config.py, main_gui.py, main.py in the tree
            target_files = []
            for root, dirs, files in os.walk(base):
                for fname in files:
                    if fname in ("config.py", "main_gui.py", "main.py"):
                        target_files.append(os.path.join(root, fname))

            for fpath in target_files:
                try:
                    with open(fpath, 'r', encoding='utf-8', errors='ignore') as fh:
                        content = fh.read()
                    original = content

                    # ── config.py variables (new config structure) ────────
                    content = safe_replace(
                        r'AGENT_SOURCE_PATH\s*=\s*r?"[^"\n]*"',
                        f'AGENT_SOURCE_PATH = r"{agent_path}"', content)
                    content = safe_replace(
                        r'PIPER_EXE_PATH\s*=\s*r?"[^"\n]*"',
                        f'PIPER_EXE_PATH = r"{piper_exe}"', content)
                    content = safe_replace(
                        r'PIPER_MODEL_PATH\s*=\s*r?"[^"\n]*"',
                        f'PIPER_MODEL_PATH = r"{piper_model}"', content)
                    content = safe_replace(
                        r'MICROPHONE_INDEX\s*=\s*\d+',
                        f'MICROPHONE_INDEX = {self.mic_index.get()}', content)

                    # ── DB port in config.py ──────────────────────────────
                    if 'config.py' in fpath:
                        content = safe_replace(
                            r'"port":\s*\d+',
                            f'"port": {self.db_port.get()}', content)

                    # ── Legacy hardcoded paths in main_gui.py / main.py ───
                    # (fallback — catches old-style files not yet using config.py)
                    content = safe_replace(
                        r'piper_exe\s*=\s*r?"[^"\n]*"',
                        f'piper_exe = r"{piper_exe}"', content)
                    content = safe_replace(
                        r'piper_model\s*=\s*r?"[^"\n]*"',
                        f'piper_model = r"{piper_model}"', content)
                    content = safe_replace(
                        r'microphone_index\s*=\s*\d+',
                        f'microphone_index = {self.mic_index.get()}', content)

                    if content != original:
                        with open(fpath, 'w', encoding='utf-8') as fh:
                            fh.write(content)
                        self.log(f"  Patched: {os.path.basename(fpath)}", 'ok')
                        patched += 1
                    else:
                        self.log(f"  No changes: {os.path.basename(fpath)}")
                except Exception as e:
                    self.log(f"  ERROR {os.path.basename(fpath)}: {e}", 'err')
                    errors.append(fpath)

            def finish():
                if errors:
                    self._cfg_status.config(
                        text=f"Patched {patched} file(s) - {len(errors)} error(s). Check log.",
                        fg=YELLOW)
                    nxt.config(state=tk.NORMAL, bg=ORANGE)
                else:
                    self._cfg_status.config(
                        text=f"{patched} file(s) updated.", fg=GREEN)
                    self.steps_done['config'] = True
                    nxt.config(state=tk.NORMAL, bg=BLUE)

            self.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    # ── STEP 8 — VERIFY ───────────────────────────────────────────────────

    def _create_shortcut(self, main_gui):
        """Create desktop shortcuts — two .bat launchers, always works on Windows."""
        try:
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            agent_dir = os.path.dirname(main_gui)
            api_key   = self.grok_api_key.get().strip() or "%GROK_API_KEY%"
            db_pw     = self.db_password.get().strip()

            results = []

            # GUI launcher
            gui_bat = os.path.join(desktop, "Neximus.bat")
            with open(gui_bat, 'w') as f:
                f.write('@echo off\n')
                f.write(f'SET GROK_API_KEY={api_key}\n')
                if db_pw:
                    f.write(f'SET DB_PASSWORD={db_pw}\n')
                f.write(f'cd /d "{agent_dir}"\n')
                f.write(f'python "{main_gui}"\n')
                f.write('pause\n')
            self.log(f"Created desktop launcher: {gui_bat}", 'ok')
            results.append(gui_bat)

            # Console launcher (main.py)
            main_py = os.path.join(agent_dir, "main.py")
            console_bat = os.path.join(desktop, "Neximus Console.bat")
            with open(console_bat, 'w') as f:
                f.write('@echo off\n')
                f.write(f'SET GROK_API_KEY={api_key}\n')
                if db_pw:
                    f.write(f'SET DB_PASSWORD={db_pw}\n')
                f.write(f'cd /d "{agent_dir}"\n')
                f.write(f'python "{main_py}"\n')
                f.write('pause\n')
            self.log(f"Created console launcher: {console_bat}", 'ok')
            results.append(console_bat)

            return True, ', '.join(results)
        except Exception as e:
            self.log(f"Shortcut error: {e}", 'err')
            return False, str(e)

    def _step_verify(self):
        self._title("Step 9 - Verify & finish", "")
        f = tk.Frame(self._content, bg=BG)
        f.pack(fill=tk.X, padx=20)

        checks = [
            ("Agent files copied",     self.steps_done.get('copy')),
            ("Piper TTS copied",       self.steps_done.get('piper')),
            ("Environment variables",  self.steps_done.get('env')),
            ("Database restored",      self.steps_done.get('db')),
            ("Python packages",        self.steps_done.get('packages')),
            ("Config files updated",   self.steps_done.get('config')),
        ]
        all_done = all(v for _, v in checks)
        for label, ok in checks:
            self._check_row(f, label, ok)

        tk.Label(f, text="", bg=BG).pack()

        if all_done:
            tk.Label(f,
                     text="Installation complete!\n\n"
                          "Restart Windows to activate environment variables, "
                          "then double-click the Neximus shortcut on your desktop.",
                     bg=BG, fg=GREEN, font=('Helvetica', 10, 'bold'),
                     wraplength=560, justify='left').pack(anchor='w', pady=8)
        else:
            tk.Label(f,
                     text="Some steps are not complete - go back and finish any marked X",
                     bg=BG, fg=YELLOW, font=('Helvetica', 9),
                     wraplength=560).pack(anchor='w', pady=8)

        main_gui = os.path.join(self.install_path.get(), "grok_agent",
                                AGENT_REL, "main_gui.py")

        self._shortcut_status = tk.Label(f, text="", bg=BG, fg=GRAY,
                                         font=('Helvetica', 9))
        self._shortcut_status.pack(anchor='w', pady=2)

        btn_row = tk.Frame(self._content, bg=BG)
        btn_row.pack(anchor='e', padx=20, pady=12)

        def make_shortcut():
            ok, result = self._create_shortcut(main_gui)
            if ok:
                self._shortcut_status.config(
                    text=f"Desktop launchers created: {result}", fg=GREEN)
            else:
                self._shortcut_status.config(
                    text=f"Shortcut failed: {result}", fg=RED)

        tk.Button(btn_row, text="Create desktop launchers",
                  command=make_shortcut,
                  bg=BLUE, fg=WHITE, font=('Helvetica', 10, 'bold'),
                  relief=tk.FLAT, padx=20, pady=8).pack(side=tk.LEFT, padx=(0, 8))

        if os.path.isfile(main_gui):
            # Create run_agent_gui.bat with env vars already set from Step 5
            bat_path = os.path.join(os.path.dirname(main_gui), "run_agent_gui.bat")
            try:
                api_key = self.grok_api_key.get().strip() or "YOUR_GROK_API_KEY_HERE"
                db_pw   = self.db_password.get().strip() or ""
                with open(bat_path, 'w') as bf:
                    bf.write("@echo off\n")
                    bf.write(f"SET GROK_API_KEY={api_key}\n")
                    if db_pw:
                        bf.write(f"SET DB_PASSWORD={db_pw}\n")
                    bf.write(f'cd /d "{os.path.dirname(main_gui)}"\n')
                    bf.write(f'python "{main_gui}"\n')
                    bf.write("pause\n")
                self.log(f"Created run_agent_gui.bat", 'ok')
            except Exception as e:
                self.log(f"Could not create bat file: {e}", 'warn')

            tk.Button(btn_row, text="Launch Neximus now",
                      command=lambda: subprocess.Popen(
                          [sys.executable, main_gui],
                          cwd=os.path.dirname(main_gui)),
                      bg=GREEN, fg=WHITE, font=('Helvetica', 10, 'bold'),
                      relief=tk.FLAT, padx=20, pady=8).pack(side=tk.LEFT, padx=(0, 8))

        tk.Button(btn_row, text="Close installer",
                  command=self.destroy,
                  bg=BG3, fg=WHITE, font=('Helvetica', 10),
                  relief=tk.FLAT, padx=20, pady=8).pack(side=tk.LEFT)


if __name__ == "__main__":
    app = NeximusInstaller()
    app.mainloop()