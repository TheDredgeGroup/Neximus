"""
Flask Web Server for iPhone Transcript Integration
Receives voice transcripts from iPhone Siri Shortcut and processes through Grok Agent
Can run standalone or as a background thread in main_gui.py
"""

from flask import Flask, request, jsonify
import requests as http_requests
import json
from datetime import datetime
import sys
import os
import logging
import threading

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)

app = Flask(__name__)

# Global agent components (will be set by initialization)
agent = None
plc_parser = None
reminder_parser = None
voice = None
chore_db = None
plc_comm = None
scheduler = None
gui = None
collaborate_enabled = False  # AI collaboration toggle

def set_components(agent_inst, plc_parser_inst, reminder_parser_inst, 
                   voice_inst, plc_comm_inst, scheduler_inst, gui_inst=None, chore_db_inst=None):
    """Set global component references"""
    global agent, plc_parser, reminder_parser, voice, plc_comm, scheduler, gui, chore_db
    agent = agent_inst
    plc_parser = plc_parser_inst
    reminder_parser = reminder_parser_inst
    voice = voice_inst
    plc_comm = plc_comm_inst
    scheduler = scheduler_inst
    gui = gui_inst
    if chore_db_inst is not None:
        chore_db = chore_db_inst

def initialize_components():
    """Initialize all Grok Agent components"""
    global agent, plc_parser, reminder_parser, voice, chore_db, plc_comm, scheduler
    
    print("🔌 Initializing database connection...")
    db = initialize_database(DB_CONFIG)
    
    print("📋 Initializing chore database...")
    chore_db = initialize_chore_database(db.get_connection())
    
    print("🧠 Initializing Grok client...")
    grok = initialize_grok_client(api_key=GROK_API_KEY, model=GROK_MODEL)
    
    print("🎯 Initializing embedding generator...")
    embedder = initialize_embedding_generator()
    
    print("💾 Initializing memory search...")
    memory = initialize_memory_search(persist_directory="./memory_store")
    
    print("🎤 Initializing voice interface...")
    # Piper TTS configuration
    piper_exe = r"C:\Users\aalldredge-da\Desktop\piper tts\piper_windows_amd64\piper\piper.exe"
    piper_model = r"C:\Users\aalldredge-da\Desktop\piper tts\en_GB-alan-medium.onnx"
    
    voice = initialize_voice_interface(
        whisper_model="base",
        microphone_index=1,
        piper_path=piper_exe,
        piper_model=piper_model,
        speech_rate=1.3
    )
    
    print("📡 Initializing PLC communicator...")
    plc_comm = initialize_plc_communicator()
    
    print("🤖 Initializing agent with semantic memory...")
    agent = initialize_agent(grok, db, embedder, memory, AGENT_NAME)
    agent.start_conversation()
    
    print("⏰ Initializing scheduler service...")
    scheduler = initialize_scheduler(chore_db, plc_comm, voice)
    start_scheduler()
    
    print("📝 Initializing reminder parser...")
    reminder_parser = initialize_reminder_parser(chore_db, scheduler)
    
    print("🔧 Initializing PLC parser...")
    plc_parser = initialize_plc_parser(chore_db, plc_comm)
    
    # Test connection
    if grok.test_connection():
        print("✅ Grok API connection successful")
    else:
        print("❌ Grok API connection failed")
        return False
    
    # Show memory stats
    stats = agent.get_memory_stats()
    print(f"📊 Memory: {stats['total_messages']} messages indexed")
    
    print("\n" + "="*60)
    print("✅ ALL SYSTEMS READY")
    print("="*60)
    return True

@app.route('/transcript', methods=['POST'])
def transcript():
    """
    Receive transcript from iPhone and process through agent
    
    Expected JSON: {"text": "your message here"}
    Returns: {"status": "success", "response": "agent response", "timestamp": "HH:MM:SS"}
    """
    try:
        data = request.get_json()
        text = data.get('text', '').strip()
        
        if not text:
            return jsonify({
                "status": "error",
                "error": "No text provided"
            }), 400
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"\n{'='*60}")
        print(f"📱 [{timestamp}] iPhone: {text}")
        print(f"{'='*60}")
        
        # Process message through parsers and agent
        response = None
        
        # Check for reminder request
        if reminder_parser and reminder_parser.is_reminder_request(text):
            logger.info("Processing as reminder request")
            was_reminder, response = reminder_parser.process_message(text, agent)
            if was_reminder and response:
                print(f"⏰ Reminder set")
        
        # Check for PLC command
        if not response and plc_parser and plc_parser.is_plc_request(text):
            logger.info("Processing as PLC request")
            was_plc, response = plc_parser.process_message(text, agent)
            if was_plc and response:
                print(f"📡 PLC command executed")
        
        # Check for introspection command
        if not response and agent.introspection_parser:
            logger.info("Checking for introspection command")
            was_introspection, response = agent.introspection_parser.parse_and_execute(text)
            if was_introspection and response:
                print(f"🔍 Introspection command executed")
        
        # Check for action command (browser/search) - runs even when AI is off
        if not response and hasattr(agent, 'action_executor'):
            action_result = agent.action_executor.process_command(text)
            if action_result.get('executed'):
                action_type = action_result.get('action', 'action')
                target = action_result.get('target', '')
                if action_type == 'search':
                    response = f"Searching for: {target}"
                else:
                    response = f"Opening: {target}"
                logger.info(f"Action executed: {action_type} {target}")
        
        # Normal chat if not handled above
        if not response:
            logger.info("Processing as normal chat")
            response = agent.chat(text)
        
        print(f"🤖 Agent: {response}")
        print(f"{'='*60}\n")
        
        # Push messages to GUI chat window
        if gui:
            gui.add_message("📱 iPhone", text, "#00aaff")
            gui.add_message("Agent", response, "#ffffff")
            
            # Code mode: check for code blocks and write to Notepad
            if gui.code_mode_enabled and not gui.code_writing_active:
                code_blocks = gui._extract_code_blocks(response)
                if code_blocks:
                    gui.code_write_stop_event.clear()
                    threading.Thread(
                        target=gui._notepad_writer_thread,
                        args=(code_blocks,),
                        daemon=True
                    ).start()
        
        # Optionally speak response on PC
        if voice and voice.voice_output_enabled:
            try:
                voice.speak(response)
            except Exception as e:
                logger.error(f"Voice output error: {e}")
        
        # Save to file for logging
        try:
            with open("latest_transcript.txt", "a", encoding="utf-8") as f:
                f.write(f"[{timestamp}] User: {text}\n")
                f.write(f"[{timestamp}] Agent: {response}\n\n")
        except Exception as e:
            logger.error(f"File logging error: {e}")

        # Forward response to peer if collaboration is enabled
        if collaborate_enabled:
            def send_to_peer():
                import time
                if voice:
                    while voice.is_speaking:
                        time.sleep(0.1)
                    # Add small buffer, but cap wait at 30s in case speech was interrupted
                    waited = 0
                    while voice.is_speaking and waited < 30:
                        time.sleep(0.5)
                        waited += 0.5
                time.sleep(0.3)
                try:
                    from config.config import PEER_URL, AGENT_DISPLAY_NAME
                    http_requests.post(
                        f"{PEER_URL}/agent_message",
                        json={"text": response, "sender": AGENT_DISPLAY_NAME},
                        timeout=120
                    )
                    logger.info(f"Sent response to peer at {PEER_URL}")
                except Exception as e:
                    logger.error(f"Failed to send to peer: {e}")
            threading.Thread(target=send_to_peer, daemon=True).start()

        return jsonify({"status": "success", "response": response}), 200
        
    except Exception as e:
        logger.error(f"Error processing transcript: {e}", exc_info=True)
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

@app.route('/agent_message', methods=['POST'])
def agent_message():
    """
    Receive message from peer agent (PC2) and process through local agent
    Expected JSON: {"text": "message", "sender": "Lumina"}
    """
    global collaborate_enabled
    try:
        data = request.get_json()
        text = data.get('text', '').strip()
        sender = data.get('sender', 'Peer Agent')

        if not text:
            return jsonify({"status": "error", "error": "No text provided"}), 400

        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"\n{'='*60}")
        print(f"🤝 [{timestamp}] {sender}: {text}")
        print(f"{'='*60}")

        # Process through agent — peer messages go straight to chat only
        # Skip reminder/PLC/introspection parsers to prevent feedback loops
        # Also skip time-based recall by prefixing with sender context
        response = None

        # Loop detection — if peer sends a short pure time-recall response, redirect conversation
        loop_indicators = [
            "i couldn't find any conversations",
            "i found 0 conversation",
            "no conversations found",
        ]
        is_loop_response = (
            any(indicator in text.lower() for indicator in loop_indicators)
            and len(text) < 120
        )

        if is_loop_response:
            logger.warning(f"Loop detected — redirecting conversation from {sender}")
            response = agent.chat(f"{sender} is ready to continue our conversation. Please share a thought or ask something interesting to keep our collaboration going.", use_memory_search=False)
        else:
            # Check if message matches the collaborate format template
            # If it does, execute the PLC write directly - no Grok round trip
            collab_write_done = False
            tag_name_str = ''
            write_value = 0.0
            try:
                import re as _re
                fmt = None
                if chore_db:
                    fmt = chore_db.get_setting('cl_collaborate_format')
                if fmt:
                    # Format from dropdown is: [PLC:AI PLC|Tag:Agent_Loop_1_Output|Value:{value}]
                    # PLC name and tag name are fixed - only {value} is a token
                    # Also retrieve saved PLC id and tag name directly from settings
                    saved_plc_id  = chore_db.get_setting('cl_collab_plc_id')
                    saved_tag_name = chore_db.get_setting('cl_collab_tag_name')
                    # Build regex - escape the format then replace {value} token
                    escaped = _re.escape(fmt)
                    escaped = escaped.replace(_re.escape('{value}'), '(?P<value>[0-9.]+)')
                    match = _re.search(escaped, text)
                    if match:
                        write_value = float(match.group('value').strip())
                        # Use saved PLC id and tag name - no ambiguity
                        plcs = chore_db.get_all_plcs(enabled_only=True)
                        plc_cfg = next((p for p in plcs if p['id'] == saved_plc_id), None)
                        if not plc_cfg:
                            plc_cfg = plcs[0] if plcs else None
                        tag_name_str = saved_tag_name
                        if plc_cfg and tag_name_str and plc_comm:
                            result = plc_comm.write_tag(
                                plc_cfg['ip_address'],
                                tag_name_str,
                                write_value,
                                plc_cfg['slot'],
                                plc_cfg['plc_type']
                            )
                            if result.success:
                                logger.info(f"Collaborate PLC write: {tag_name_str} = {write_value}")
                                collab_write_done = True
                                if gui:
                                    gui.add_message("System", f"Collab PLC write: {tag_name_str} = {write_value}", "#00ff88")
                            else:
                                logger.warning(f"Collaborate PLC write failed: {result.error}")
            except Exception as e:
                logger.warning(f"Collaborate format parse error: {e}")

            # Normal peer chat - use Grok if available, fallback ack if not
            grok_available = getattr(agent, 'ai_enabled', True)
            if grok_available:
                try:
                    response = agent.chat(f"{sender} says: {text}", use_memory_search=True)
                    # If response indicates offline, treat as unavailable
                    if response and "currently offline" in response.lower():
                        grok_available = False
                except Exception:
                    grok_available = False

            if not grok_available:
                if collab_write_done and tag_name_str:
                    response = f"Write confirmed: {tag_name_str} = {write_value}. Next value?"
                else:
                    response = "Received. Grok offline - local commands still active."
                logger.info("Grok unavailable - using fallback response")

        print(f"🤖 Agent: {response}")
        print(f"{'='*60}\n")

        # Push to GUI
        if gui:
            from config.config import PEER_DISPLAY_NAME, AGENT_DISPLAY_NAME
            gui.add_message(f"🤝 {sender}", text, "#ff9900")
            gui.add_message(AGENT_DISPLAY_NAME, response, "#ffffff")

        # Speak response
        if voice and voice.voice_output_enabled:
            try:
                voice.speak(response)
            except Exception as e:
                logger.error(f"Voice output error: {e}")

        # If collaboration is enabled, send response back to peer
        if collaborate_enabled:
            def send_to_peer_when_done():
                import time
                # Wait for voice to finish speaking before sending
                # Cap at 30s in case speech was interrupted and is_speaking stays True
                if voice:
                    waited = 0
                    while voice.is_speaking and waited < 30:
                        time.sleep(0.5)
                        waited += 0.5
                    time.sleep(0.3)
                try:
                    from config.config import PEER_URL, AGENT_DISPLAY_NAME
                    http_requests.post(
                        f"{PEER_URL}/agent_message",
                        json={"text": response, "sender": AGENT_DISPLAY_NAME},
                        timeout=120
                    )
                    logger.info(f"Sent response to peer at {PEER_URL}")
                except Exception as e:
                    logger.error(f"Failed to send to peer: {e}")
            threading.Thread(target=send_to_peer_when_done, daemon=True).start()

        return jsonify({"status": "success", "response": response}), 200

    except Exception as e:
        logger.error(f"Error processing agent message: {e}", exc_info=True)
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route('/collaborate', methods=['POST'])
def set_collaborate():
    """Enable or disable AI collaboration mode"""
    global collaborate_enabled
    try:
        data = request.get_json()
        collaborate_enabled = data.get('enabled', False)
        logger.info(f"Collaboration mode: {'ON' if collaborate_enabled else 'OFF'}")
        if gui:
            status = "ON" if collaborate_enabled else "OFF"
            gui.add_message("System", f"AI Collaboration: {status}", "#00ff00")
        return jsonify({"status": "success", "collaborate": collaborate_enabled}), 200
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "running",
        "agent": "ready" if agent else "not initialized",
        "plc": "available" if plc_comm and plc_comm.is_available() else "unavailable",
        "scheduler": "running" if scheduler and scheduler.running else "stopped"
    }), 200

@app.route('/status', methods=['GET'])
def status():
    """Get detailed system status"""
    try:
        memory_stats = agent.get_memory_stats() if agent else {}
        scheduler_status = scheduler.get_status() if scheduler else {}
        
        return jsonify({
            "agent_ready": agent is not None,
            "memory_stats": memory_stats,
            "plc_available": plc_comm.is_available() if plc_comm else False,
            "scheduler": scheduler_status,
            "voice_enabled": voice.voice_output_enabled if voice else False
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def start_web_server_thread(agent, plc_parser, reminder_parser, voice, plc_comm, scheduler, gui=None, chore_db_inst=None):
    """
    Start Flask web server in a background thread
    Called from main_gui.py to run alongside the GUI
    """
    # Set component references
    set_components(agent, plc_parser, reminder_parser, voice, plc_comm, scheduler, gui, chore_db_inst)
    
    # Start Flask in daemon thread so it exits when main program exits
    def run_server():
        # Suppress Flask startup messages
        import logging as flask_logging
        log = flask_logging.getLogger('werkzeug')
        log.setLevel(flask_logging.ERROR)
        
        app.run(host='0.0.0.0', port=5000, debug=False, threaded=True, use_reloader=False)
    
    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
    return thread

if __name__ == '__main__':
    """
    Standalone mode - run web server independently without GUI
    """
    # Import agent components only for standalone mode
    from config.config import DB_CONFIG, GROK_API_KEY, GROK_MODEL, AGENT_NAME, LOG_LEVEL
    from database.db import initialize_database
    from database.db_chores import initialize_chore_database
    from agent.grok_client import initialize_grok_client
    from agent.embeddings import initialize_embedding_generator
    from agent.memory_search import initialize_memory_search
    from agent.core import initialize_agent
    from agent.voice_interface import initialize_voice_interface
    from agent.plc_comm import initialize_plc_communicator
    from agent.plc_parser import initialize_plc_parser
    from agent.reminder_parser import initialize_reminder_parser
    from agent.scheduler_service import initialize_scheduler, start_scheduler
    
    # Setup logging
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('logs/web_server.log'),
            logging.StreamHandler()
        ]
    )
    
    def initialize_standalone():
        """Initialize all components for standalone mode"""
        global agent, plc_parser, reminder_parser, voice, chore_db, plc_comm, scheduler
        
        print("🔌 Initializing database connection...")
        db = initialize_database(DB_CONFIG)
        
        print("📋 Initializing chore database...")
        chore_db = initialize_chore_database(db.get_connection())
        
        print("🧠 Initializing Grok client...")
        grok = initialize_grok_client(api_key=GROK_API_KEY, model=GROK_MODEL)
        
        print("🎯 Initializing embedding generator...")
        embedder = initialize_embedding_generator()
        
        print("💾 Initializing memory search...")
        memory = initialize_memory_search(persist_directory="./memory_store")
        
        print("🎤 Initializing voice interface...")
        piper_exe = r"C:\Users\aalldredge-da\Desktop\piper tts\piper_windows_amd64\piper\piper.exe"
        piper_model = r"C:\Users\aalldredge-da\Desktop\piper tts\en_GB-alan-medium.onnx"
        
        voice = initialize_voice_interface(
            whisper_model="base",
            microphone_index=1,
            piper_path=piper_exe,
            piper_model=piper_model,
            speech_rate=1.3
        )
        
        print("📡 Initializing PLC communicator...")
        plc_comm = initialize_plc_communicator()
        
        print("🤖 Initializing agent with semantic memory...")
        agent = initialize_agent(grok, db, embedder, memory, AGENT_NAME)
        agent.start_conversation()
        
        print("⏰ Initializing scheduler service...")
        scheduler = initialize_scheduler(chore_db, plc_comm, voice)
        start_scheduler()
        
        print("📝 Initializing reminder parser...")
        reminder_parser = initialize_reminder_parser(chore_db, scheduler)
        
        print("🔧 Initializing PLC parser...")
        plc_parser = initialize_plc_parser(chore_db, plc_comm)
        
        # Set components
        set_components(agent, plc_parser, reminder_parser, voice, plc_comm, scheduler)
        
        # Test connection
        if grok.test_connection():
            print("✅ Grok API connection successful")
        else:
            print("❌ Grok API connection failed")
            return False
        
        stats = agent.get_memory_stats()
        print(f"📊 Memory: {stats['total_messages']} messages indexed")
        
        print("\n" + "="*60)
        print("✅ ALL SYSTEMS READY")
        print("="*60)
        return True
    
    print("="*60)
    print("GROK AGENT - iPhone Transcript Server (STANDALONE)")
    print("Receives voice transcripts from iPhone Siri Shortcut")
    print("="*60)
    print()
    
    # Create logs directory
    os.makedirs('logs', exist_ok=True)
    
    # Initialize all components
    if initialize_standalone():
        import socket
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        
        print(f"\n📱 Server starting on http://{local_ip}:5000")
        print(f"📱 iPhone Shortcut URL: http://{local_ip}:5000/transcript")
        print()
        print("Available endpoints:")
        print("  POST /transcript  - Send voice transcript")
        print("  GET  /health      - Check server health")
        print("  GET  /status      - Get detailed status")
        print()
        print("Press Ctrl+C to stop")
        print("="*60)
        
        # Run Flask server (blocking)
        app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
    else:
        print("\n❌ Failed to initialize components. Check configuration.")
        sys.exit(1)