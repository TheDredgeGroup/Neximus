"""
Neximus AI Agent - Configuration
Edit this file for your local setup.
Copy this file to config/config.py and fill in your values.
"""

import os

# =============================================================================
# GROK API
# =============================================================================
GROK_API_KEY = os.getenv("GROK_API_KEY", "")
GROK_API_BASE_URL = "https://api.x.ai/v1"
GROK_MODEL = "grok-3-fast"  # Fast default — switch to grok-4 via GUI for reasoning

# =============================================================================
# POSTGRESQL DATABASE
# =============================================================================
DB_CONFIG = {
    "host": "localhost",
    "port": 5433,                    # Change if your PostgreSQL uses a different port
    "database": "grok_agent_db",
    "user": "postgres",
    "password": os.getenv("DB_PASSWORD", "")
}

# =============================================================================
# AGENT IDENTITY
# =============================================================================
AGENT_NAME = "GrokAgent"
AGENT_DISPLAY_NAME = "Agent"         # Name shown in GUI and spoken by TTS
PEER_DISPLAY_NAME = "Peer"           # Name of second agent on PC2
PEER_URL = "http://192.168.1.2:5000" # Change to your PC2 IP address

# Your name — used by the agent when addressing you
USER_NAME = "User"

# =============================================================================
# VOICE — PIPER TTS (offline)
# Installer sets these automatically. Change if you move Piper.
# Download Piper from: https://github.com/rhasspy/piper/releases
# =============================================================================
PIPER_EXE_PATH = r"C:\Neximus\piper tts\piper_windows_amd64\piper\piper.exe"
PIPER_MODEL_PATH = r"C:\Neximus\piper tts\en_GB-alan-medium.onnx"
SPEECH_RATE = 1.3                    # TTS speed multiplier (1.0 = normal)

# =============================================================================
# VOICE — WHISPER (speech recognition)
# =============================================================================
MICROPHONE_INDEX = 0                 # Run python -m sounddevice to list devices

# =============================================================================
# WAKE WORD INTERRUPT — PORCUPINE (optional)
# Get a free key at: https://console.picovoice.ai/
# Leave blank to disable voice interrupt detection
# =============================================================================
PORCUPINE_ACCESS_KEY = os.getenv("PORCUPINE_ACCESS_KEY", "")

# =============================================================================
# AGENT SOURCE PATH (for self-introspection)
# Installer sets this automatically.
# =============================================================================
AGENT_SOURCE_PATH = r"C:\Neximus\grok_agent\agent"

# =============================================================================
# MEMORY
# =============================================================================
MAX_MEMORY_RESULTS = 5
CONVERSATION_CONTEXT_LENGTH = 10

# =============================================================================
# LOCATION (for sunrise/sunset calculations)
# Find your coordinates at latlong.net
# =============================================================================
LOCATION_LAT = 0.0
LOCATION_LON = 0.0
LOCATION_TIMEZONE = "America/New_York"

# =============================================================================
# LOGGING
# =============================================================================
LOG_LEVEL = "INFO"
LOG_FILE = "logs/agent.log"