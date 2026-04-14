"""
GUI Launcher for Grok Agent - Phase 3 + Vision
Initializes all components including PLC, Scheduler, Reminders, and Vision
"""

import logging
import sys
import os

# Add parent directory to path to ensure imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.config import (DB_CONFIG, GROK_API_KEY, GROK_MODEL, AGENT_NAME, LOG_LEVEL,
                              PIPER_EXE_PATH, PIPER_MODEL_PATH, SPEECH_RATE,
                              MICROPHONE_INDEX, PORCUPINE_ACCESS_KEY, AGENT_SOURCE_PATH,
                              AGENT_DISPLAY_NAME)
from database.db import initialize_database
from agent.grok_client import initialize_grok_client
from agent.embeddings import initialize_embedding_generator
from agent.memory_search import initialize_memory_search
from agent.core import initialize_agent
from agent.voice_interface import initialize_voice_interface
from agent.gui import AgentGUI
from agent.vision_integration import VisionIntegration  # VISION: Updated import


def setup_logging():
    """Configure logging"""
    # Create logs directory if it doesn't exist
    os.makedirs('logs', exist_ok=True)
    
    # Console handler with UTF-8 encoding to handle emojis without crashing
    import sys
    console_handler = logging.StreamHandler(stream=open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1))
    
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('logs/agent.log', encoding='utf-8'),
            console_handler
        ]
    )


def main():
    """Main function to run the GUI agent"""
    print("=" * 60)
    print("GROK EMBODIED AI AGENT - PHASE 3")
    print("Brain + Memory + Voice + PLC Control + Reminders + Vision")
    print("=" * 60)
    print()
    
    # Setup logging
    setup_logging()
    logger = logging.getLogger(__name__)
    
    try:
        # ==========================================
        # CORE INITIALIZATION
        # ==========================================
        
        print("ðŸ”Œ Initializing database connection...")
        db = initialize_database(DB_CONFIG)
        print("âœ“ Database connected")
        
        print("ðŸ“‹ Initializing chore database...")
        from database.db_chores import initialize_chore_database
        chore_db = initialize_chore_database(db.get_connection())
        print("âœ“ Chore database ready")
        
        print("ðŸ§  Initializing Grok client...")
        grok = initialize_grok_client(api_key=GROK_API_KEY, model=GROK_MODEL)
        print("âœ“ Grok client connected")
        
        print("ðŸŽ¯ Initializing embedding generator...")
        print("   (First run may download model ~90MB)")
        embedder = initialize_embedding_generator()
        print("âœ“ Embedding generator ready")
        
        print("ðŸ’¾ Initializing memory search...")
        memory = initialize_memory_search(persist_directory="./memory_store")
        print("âœ“ Memory search ready")
        
        # ==========================================
        # VOICE INITIALIZATION
        # ==========================================
        
        print("ðŸŽ¤ Initializing voice interface...")
        print("   (Loading Whisper model - may take a minute)")
        print("   TTS: Piper (offline) + gTTS (online)")
        
        # Piper TTS configuration — paths set by installer in config/config.py
        voice = initialize_voice_interface(
            whisper_model="base",
            microphone_index=MICROPHONE_INDEX,
            piper_path=PIPER_EXE_PATH,
            piper_model=PIPER_MODEL_PATH,
            speech_rate=SPEECH_RATE,
            porcupine_access_key=PORCUPINE_ACCESS_KEY
        )
        print("âœ“ Voice interface ready")
        
        # ==========================================
        # PLC INITIALIZATION
        # ==========================================
        
        print("ðŸ”¡ Initializing PLC communicator...")
        from agent.plc_comm import initialize_plc_communicator
        plc_comm = initialize_plc_communicator()
        if plc_comm.is_available():
            print("âœ“ PLC communicator ready (pycomm3 loaded)")
        else:
            print("âš  PLC communicator ready (pycomm3 NOT installed - simulation mode)")
        
        # ==========================================
        # AGENT INITIALIZATION
        # ==========================================
        
        print("ðŸ¤– Initializing agent with semantic memory...")
        agent = initialize_agent(grok, db, embedder, memory, chore_db, plc_comm, AGENT_NAME, AGENT_SOURCE_PATH)
        print(f"âœ“ {AGENT_NAME} is ready!")
        
        # Immediately create introspection parser for both agent and GUI
        print("🔍 Attaching introspection parser to agent...")
        from agent.introspection_parser import IntrospectionParser
        introspection_parser = IntrospectionParser(agent)
        agent.introspection_parser = introspection_parser
        print()
        
        # VISION: Add vision capabilities to agent
        print("ðŸ‘ï¸  Initializing vision system...")
        agent.vision = VisionIntegration()
        print(f"âœ“ Vision ready: {len(agent.vision.monitors)} monitor(s) detected")
        print()
        
        # Test connection
        print("ðŸ” Testing Grok API connection...")
        if grok.test_connection():
            print("âœ“ Grok API connection successful")
        else:
            print("âœ— Grok API connection failed")
            return
        
        # Show memory stats
        stats = agent.get_memory_stats()
        print(f"ðŸ“Š Memory: {stats['total_messages']} messages indexed")
        
        # ==========================================
        # SCHEDULER INITIALIZATION
        # ==========================================
        
        print("â° Initializing scheduler service...")
        from agent.scheduler_service import initialize_scheduler, start_scheduler
        scheduler = initialize_scheduler(chore_db, plc_comm, voice)
        start_scheduler()
        print("âœ“ Scheduler service started")
        
        # ==========================================
        # REMINDER PARSER INITIALIZATION
        # ==========================================
        
        print("ðŸ“ Initializing reminder parser...")
        from agent.reminder_parser import initialize_reminder_parser
        reminder_parser = initialize_reminder_parser(chore_db, scheduler)
        print("âœ“ Reminder parser ready")
        
        print("ðŸ”§ Initializing PLC parser...")
        from agent.plc_parser import initialize_plc_parser
        plc_parser = initialize_plc_parser(chore_db, plc_comm)
        print("âœ“ PLC parser ready")
        
        # Introspection parser already attached to agent above
        # (No need to reinitialize here)

        # ==========================================
        # WEB SERVER FOR IPHONE INTEGRATION
        # ==========================================
        
        print("ðŸ“± Starting iPhone web server...")
        from agent.web_server import start_web_server_thread
        import socket
        
        # Get PC's IP address
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        
        start_web_server_thread(
            agent=agent,
            plc_parser=plc_parser,
            reminder_parser=reminder_parser,
            voice=voice,
            plc_comm=plc_comm,
            scheduler=scheduler,
            chore_db_inst=chore_db
        )
        print(f"âœ“ Web server running on http://{local_ip}:5000")
        print(f"  iPhone Shortcut URL: http://{local_ip}:5000/transcript")
        
        # ==========================================
        # VOICE TEST
        # ==========================================
        
        print("ðŸ”Š Testing voice output...")
        voice.speak("Voice interface ready")
        voice.speak(f"My name is {AGENT_DISPLAY_NAME}")
        voice.speak("What would you like me to help you with")
        
        print()
        print("=" * 60)
        print("LAUNCHING GUI - PHASE 3 + VISION")
        print("Console will show logs and errors")
        print("=" * 60)
        print()
        
        # Start conversation
        agent.start_conversation()
        
        # ==========================================
        # LAUNCH GUI
        # ==========================================
        
        gui = AgentGUI(
            agent=agent,
            voice_interface=voice,
            chore_db=chore_db,
            plc_comm=plc_comm,
            scheduler=scheduler,
            reminder_parser=reminder_parser,
            plc_parser=plc_parser,
            introspection_parser=introspection_parser
        )
        
        # Give web server the GUI reference so iPhone transcripts appear in chat
        import agent.web_server as ws_module
        ws_module.gui = gui
        
        gui.run()
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        print(f"\nâœ— Fatal error: {e}")
        print("\nPlease check:")
        print("  1. PostgreSQL is running")
        print("  2. Database 'grok_agent_db' exists and schema is loaded")
        print("  3. GROK_API_KEY environment variable is set")
        print("  4. DB_PASSWORD environment variable is set (if needed)")
        print("  5. All packages installed:")
        print("     - pip install sentence-transformers chromadb")
        print("     - pip install SpeechRecognition whisper")
        print("     - pip install gtts pydub pyaudio")
        print("     - pip install tkinterdnd2")
        print("     - pip install pycomm3 (optional, for PLC)")
        print("     - pip install geopy astral pytz (optional, for location/sunrise)")
        print("     - pip install mss Pillow torch transformers accelerate (for vision)")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())