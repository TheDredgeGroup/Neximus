"""
Grok Agent - Main Entry Point
Phase 1: Core Neural System with Memory
"""

import sys
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.config import DB_CONFIG, GROK_API_KEY, GROK_MODEL, AGENT_NAME, LOG_LEVEL
from database.db import initialize_database
from agent.grok_client import initialize_grok_client
from agent.embeddings import initialize_embedding_generator
from agent.memory_search import initialize_memory_search
from agent.core import initialize_agent
from agent.voice_interface import initialize_voice_interface


def setup_logging():
    """Configure logging"""
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('logs/agent.log'),
            logging.StreamHandler(sys.stdout)
        ]
    )


def main():
    """Main function to run the agent"""
    print("=" * 60)
    print("GROK EMBODIED AI AGENT - PHASE 2.1")
    print("Brain + Memory + Semantic Search + Voice")
    print("=" * 60)
    print()
    
    # Setup logging
    setup_logging()
    logger = logging.getLogger(__name__)
    
    try:
        # Initialize components
        print("🔌 Initializing database connection...")
        db = initialize_database(DB_CONFIG)
        print("✓ Database connected")
        
        print("🧠 Initializing Grok client...")
        grok = initialize_grok_client(api_key=GROK_API_KEY, model=GROK_MODEL)
        print("✓ Grok client connected")
        
        print("🎯 Initializing embedding generator...")
        print("   (First run may download model ~90MB)")
        embedder = initialize_embedding_generator()
        print("✓ Embedding generator ready")
        
        print("💾 Initializing memory search...")
        memory = initialize_memory_search(persist_directory="./memory_store")
        print("✓ Memory search ready")
        
        print("🎤 Initializing voice interface...")
        print("   (Loading Whisper model - may take a minute)")
        print("   TTS: Piper (British Male - Alan)")
        
        # Piper TTS configuration
        piper_exe = r"C:\Users\aalldredge-da\Desktop\piper tts\piper_windows_amd64\piper\piper.exe"
        piper_model = r"C:\Users\aalldredge-da\Desktop\piper tts\en_GB-alan-medium.onnx"
        
        voice = initialize_voice_interface(
            whisper_model="base",
            microphone_index=1,  # Focusrite
            piper_path=piper_exe,
            piper_model=piper_model,
            speech_rate=1.0  # Normal speed
        )
        print("✓ Voice interface ready")
        
        print("🤖 Initializing agent with semantic memory...")
        agent = initialize_agent(grok, db, embedder, memory, AGENT_NAME)
        print(f"✓ {AGENT_NAME} is ready!")
        print()
        
        # Test connection
        print("🔍 Testing Grok API connection...")
        if grok.test_connection():
            print("✓ Grok API connection successful")
        else:
            print("✗ Grok API connection failed")
            return
        
        # Show memory stats
        stats = agent.get_memory_stats()
        print(f"📊 Memory: {stats['total_messages']} messages indexed")
        
        # Test voice
        print("🔊 Testing voice output...")
        voice.speak("Voice interface ready")
        
        print()
        print("=" * 60)
        print("AGENT READY - Phase 2.1 Active!")
        print("Voice + Text Interface")
        print()
        print("Commands:")
        print("  'voice' - Start voice mode (speak your messages)")
        print("  'text' - Switch to text mode (type messages)")
        print("  'talk' - Single voice input")
        print("  'mute' - Disable voice output")
        print("  'unmute' - Enable voice output")
        print("  'exit' - quit")
        print("  'new' - new conversation")
        print("  'history' - recent conversations")
        print("  'memory' - memory statistics")
        print("=" * 60)
        print()
        
        # Start interactive session
        agent.start_conversation()
        voice_mode = False  # START IN TEXT MODE
        
        print("💡 TIP: Type 'voice' to activate voice mode")
        print()
        
        while True:
            try:
                # Get user input
                if voice_mode:
                    print("\n🎤 Voice mode active")
                    print("   Press Ctrl+C to return to text mode, or speak your message...")
                    
                    try:
                        user_input = voice.listen(timeout=10, phrase_time_limit=30)
                        
                        if user_input is None:
                            print("⏱️ No speech detected. Press Ctrl+C for text mode, or speak again...")
                            continue
                        
                        print(f"You (voice): {user_input}")
                        
                    except KeyboardInterrupt:
                        voice_mode = False
                        voice.speak("Switching to text mode")
                        print("\n✓ Switched to text mode")
                        continue
                else:
                    user_input = input("You: ").strip()
                
                if not user_input:
                    continue
                
                # Check for commands
                cmd = user_input.lower()
                
                if cmd == 'exit':
                    voice.speak("Shutting down agent. Goodbye!")
                    print("\nShutting down agent...")
                    agent.shutdown()
                    print("Goodbye!")
                    break
                
                if cmd == 'voice':
                    voice_mode = True
                    voice.speak("Voice mode activated. I'm listening.")
                    print("✓ Voice mode activated")
                    continue
                
                if cmd == 'text':
                    voice_mode = False
                    voice.speak("Switching to text mode.")
                    print("✓ Text mode activated")
                    continue
                
                if cmd == 'talk':
                    print("🎤 Listening for single input...")
                    single_input = voice.listen(timeout=10, phrase_time_limit=30)
                    if single_input:
                        print(f"You (voice): {single_input}")
                        user_input = single_input
                    else:
                        print("No speech detected")
                        continue
                
                if cmd == 'mute':
                    voice.disable_voice_output()
                    print("✓ Voice output muted")
                    continue
                
                if cmd == 'unmute':
                    voice.enable_voice_output()
                    voice.speak("Voice output enabled")
                    print("✓ Voice output unmuted")
                    continue
                
                if cmd == 'new':
                    agent.start_conversation()
                    voice.speak("Started new conversation")
                    print("✓ Started new conversation")
                    continue
                
                if cmd == 'history':
                    conversations = agent.list_recent_conversations(5)
                    print("\nRecent conversations:")
                    for conv in conversations:
                        print(f"  - {conv['title']} ({conv['message_count']} messages) - {conv['updated_at']}")
                    print()
                    continue
                
                if cmd == 'summary':
                    summary = agent.get_conversation_summary()
                    print("\nCurrent conversation:")
                    print(f"  Title: {summary.get('title')}")
                    print(f"  Messages: {summary.get('message_count')}")
                    print(f"  Started: {summary.get('created_at')}")
                    print()
                    continue
                
                if cmd == 'memory':
                    stats = agent.get_memory_stats()
                    msg = f"Memory statistics. Total messages indexed: {stats['total_messages']}"
                    print(f"\n📊 {msg}")
                    print(f"  Storage location: {stats['persist_directory']}")
                    voice.speak(msg)
                    print()
                    continue
                
                # Send message to agent
                print(f"\n{AGENT_NAME}: ", end="", flush=True)
                response = agent.chat(user_input)
                print(response)
                
                # Speak response if voice output enabled
                voice.speak(response)
                print()
                
            except KeyboardInterrupt:
                print("\n\nInterrupted by user. Shutting down...")
                agent.shutdown()
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                print(f"\nError: {e}")
                print("Continuing...")
    
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        print(f"\n✗ Fatal error: {e}")
        print("\nPlease check:")
        print("  1. PostgreSQL is running")
        print("  2. Database 'grok_agent_db' exists and schema is loaded")
        print("  3. GROK_API_KEY environment variable is set")
        print("  4. DB_PASSWORD environment variable is set (if needed)")
        print("  5. sentence-transformers and chromadb are installed")
        print("  6. Voice packages (pyttsx3, SpeechRecognition, whisper) installed")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
