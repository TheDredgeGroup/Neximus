# Neximus
AI agent with forever memory, self introspection and can control devices and equipment in real world

> **DISCLAIMER:** Use this code at your own risk. Dredge Group is not responsible for any damages, data loss, or issues arising from the use of this software. This is provided as-is with no warranty.
> For help visit dredgegroup.com and leave a message.

# Neximus AI Agent

An embodied AI agent with persistent memory, voice control, Allen-Bradley PLC integration, and multi-agent collaboration. Built by Dredge Group.

Intended for developers and technicians to build on and expand. The self-code-modification capability is not fully tested but the existing introspection system provides the foundation for it.

---

## What It Does

Neximus is a local AI agent that runs on your PC and remembers everything. It connects a large language model (LLM) to a persistent memory system, voice I/O, and industrial automation hardware.

- Remembers all past conversations across sessions using semantic vector search
- Responds to voice commands via voice interrupt detection
- Controls Allen-Bradley PLCs — reads/writes tags, monitors programs, detects unauthorized changes
- Integrates with iPhone via Siri Shortcuts
- Reads and understands its own source code (self-introspection)
- Collaborates with a second AI agent on a local network
- Runs a PID control loop at ~10ms cycle time while staying fully conversational

---

## Architecture

```
User Input (GUI / Voice / iPhone)
         |
    Message Router (core.py)
         |
  ┌──────┴──────────────────────┐
  |                             |
Parser Chain                Grok API
- Time-based recall         - Build context
- Introspection             - Semantic memory search
- Action executor           - PostgreSQL keyword search
- Reminder parser           - Get response
- PLC parser                |
  |                    Save to DB + ChromaDB
  └──────────────────────────┘
         |
    Return to user
    (GUI / TTS / iPhone)
```

Memory uses two stores in parallel:
- **PostgreSQL** — full text storage, keyword search
- **ChromaDB** — 384-dim vector embeddings for semantic search (all-MiniLM-L6-v2)

---

## Requirements

### Software
- Windows 10/11 64-bit
- Python 3.11 to 3.13 (**do not use Python 3.14+** — PyAudio and several other dependencies do not yet support it)
- PostgreSQL 14+ (port 5433 default)
- Grok API key (xAI) — get one at console.x.ai
- Porcupine access key (optional, for voice interrupt) — picovoice.ai

### Hardware (Minimum)
- CPU: Intel i5 / AMD Ryzen 5 or better
- RAM: 16GB minimum, 32GB recommended
- Storage: 20GB free (models + ChromaDB + logs)
- Microphone: any USB or built-in mic
- Internet connection for Grok API calls

### Hardware (Recommended)
- CUDA-capable NVIDIA GPU (RTX 2060 or better)
  - Whisper speech recognition runs significantly faster on GPU
  - Embedding generation is faster on GPU
  - Vision system (Moondream2) requires GPU for real-time use
- RAM: 32GB+
- SSD storage

---

## Quick Install

The easiest way is to use the installer:

1. Put these files in one folder on a USB drive or network share:
   - `INSTALL_NEXIMUS.bat`
   - `neximus_installer.py`
   - `grok_agent/` (the agent folder)
   - `piper tts/` (Piper TTS engine)
   - `grok_agent_03142026.sql` (database schema)

2. Double-click `INSTALL_NEXIMUS.bat`

3. Follow the 9-step installer:
   - Detects paths automatically
   - Copies files to your chosen location
   - Sets API key as Windows environment variable
   - Restores the PostgreSQL schema
   - Installs all Python packages
   - Patches config files for your PC
   - Creates desktop launchers

---

## Manual Install

### 1. Clone the repo

```
git clone https://github.com/dredgegroup/neximus.git
cd neximus
```

### 2. Create a virtual environment

```
python -m venv venv_agent
venv_agent\Scripts\activate
```

### 3. Install packages

```
pip install -r requirements.txt
```

### 4. Set up PostgreSQL

Create the database:
```
psql -U postgres -c "CREATE DATABASE grok_agent_db;"
psql -U postgres -d grok_agent_db -f grok_agent_03142026.sql
```

### 5. Configure

Edit `config/config.py` and fill in your paths:

```python
GROK_API_KEY = os.getenv("GROK_API_KEY", "")
PIPER_EXE_PATH = r"C:\path\to\piper\piper.exe"
PIPER_MODEL_PATH = r"C:\path\to\piper\en_GB-alan-medium.onnx"
MICROPHONE_INDEX = 0
AGENT_SOURCE_PATH = r"C:\path\to\grok_agent\agent"
USER_NAME = "YourName"
```

### 6. Create a launcher bat file

Create `run_agent_gui.bat` in the agent folder:

```batch
@echo off
SET GROK_API_KEY=your_key_here
SET DB_PASSWORD=your_db_password_here
cd /d "C:\path\to\grok_agent\agent"
python main_gui.py
pause
```

### 7. Launch

Double-click `run_agent_gui.bat`

---

## Naming Your Agent

Open **Settings → Identity** tab in the GUI. Enter your name and the agent name. Click Save. Restart the agent to apply.

The agent name and your name are stored in `config/config.py` under `AGENT_DISPLAY_NAME` and `USER_NAME`.

---

## Configuration

All settings are in `config/config.py`. Key settings:

| Setting | Description |
|---|---|
| `GROK_API_KEY` | Your xAI API key (set via env var) |
| `GROK_MODEL` | Model to use (grok-3-fast default, grok-4 for reasoning) |
| `DB_CONFIG` | PostgreSQL connection settings |
| `PIPER_EXE_PATH` | Path to piper.exe |
| `PIPER_MODEL_PATH` | Path to .onnx voice model |
| `MICROPHONE_INDEX` | Mic device index (0 = default) |
| `AGENT_SOURCE_PATH` | Path to agent/ folder for self-introspection |
| `USER_NAME` | Your name — used by the agent when addressing you |
| `PEER_URL` | IP:port of second agent for collaboration |

---

## Voice Commands

See `NEXIMUS_COMMANDS.txt` for the full command reference.

### Memory
- "What did we talk about yesterday?"
- "That's wrong, delete that" — removes last response from memory
- "Forget that" — same

### Introspection
- "List your modules"
- "Open core.py"
- "Explain your introspection module"
- "Search your code for pycomm3"

### PLC
- "Read tag Program:MainProgram.Motor_Run"
- "Write 1 to tag Motor_Enable"
- "PLC status"
- "Start the control loop"

### System
- "Open Google"
- "Search YouTube for PLC tutorials"
- "Open Notepad"
- "Remind me at 3pm to check the pump"

### iPhone (via Siri Shortcuts)
- "Hey Siri, tell [agent name] [anything]"
- All commands work the same way over HTTP

---

## Memory System

Neximus uses a hybrid memory approach:

1. **Semantic search** — ChromaDB finds past conversations by meaning
2. **Answer-flipped search** — Searches for answers, not just similar questions
3. **PostgreSQL keyword search** — Finds exact text matches as a fallback
4. **Forget command** — "That's wrong" / "Forget that" deletes bad responses from ChromaDB

Memory persists in `./memory_store/` (ChromaDB) and PostgreSQL.

---

## PLC Integration

Supports Allen-Bradley ControlLogix, CompactLogix, and Micro800 via pycomm3 and PyLogix.

- Read/write tags by voice
- Baseline program comparison — email alerts on unauthorized changes
- PID control loop with configurable setpoint and gain
- AI-to-AI physical control — second agent can send setpoints, primary agent writes to PLC

Tested on ControlLogix 1756-L71/B firmware 36.11.

---

## Multi-Agent Collaboration

The primary agent (PC1) and a second agent (PC2) communicate over HTTP on port 5000. Each agent runs independently and can send messages to the other. Used for:

- AI peer review of responses
- Distributed PLC control
- Parallel processing of complex tasks

Configure `PEER_URL` in `config/config.py` to your PC2 address.

---

## License

AGPL-3.0 for personal and research use.
Commercial license available — contact Dredge Group.

---

## About

Built by Anthony Alldredge — 30 years as an electrician, SCADA technician, and systems integrator.
Dredge Group — AI automation for industrial and home use.

> Figure it out, make it better, make it so nobody has to figure it out again.