"""
Voice Interface Module with Interrupt Detection
Version 2.2 - Fixed voice interrupt using shared flag instead of virtual keypress
Speech-to-text using Whisper, TTS using Piper/gTTS, and interrupt detection
"""

__version__ = "2.2"

import speech_recognition as sr
import logging
import os
import subprocess
import tempfile
import threading
import time
import struct
import wave
import pyaudio

try:
    import pvporcupine
    PORCUPINE_AVAILABLE = True
except ImportError:
    PORCUPINE_AVAILABLE = False
    print("Warning: Porcupine not installed. Voice interrupt will not be available.")

try:
    import keyboard
    KEYBOARD_AVAILABLE = True
except ImportError:
    KEYBOARD_AVAILABLE = False
    print("Warning: keyboard module not installed. ESC key interrupt will not be available.")

logger = logging.getLogger(__name__)


class VoiceInterface:
    """
    Voice interface with speech recognition, TTS, and voice interrupt detection.
    Version 2.2 - Uses shared interrupt flag for both ESC and voice commands
    """
    
    def __init__(self, whisper_model: str = "base", microphone_index: int = None,
                 piper_path: str = None, piper_model: str = None, speech_rate: float = 1.0,
                 porcupine_access_key: str = None):
        """
        Initialize voice interface
        
        Args:
            whisper_model: Whisper model size (tiny, base, small, medium, large)
            microphone_index: Index of microphone to use (None = default)
            piper_path: Path to Piper TTS executable
            piper_model: Path to Piper model file
            speech_rate: Speech rate multiplier (1.0 = normal)
            porcupine_access_key: Picovoice access key for voice interrupt (get from console.picovoice.ai)
        """
        self.recognizer = sr.Recognizer()
        self.microphone_index = microphone_index
        self.whisper_model = whisper_model
        self.porcupine_access_key = porcupine_access_key
        
        # TTS settings
        self.piper_path = piper_path
        self.piper_model = piper_model
        self.speech_rate = speech_rate
        self.tts_mode = 'piper' if piper_path and piper_model else 'gtts'
        
        # Voice output control
        self.voice_output_enabled = True
        self.is_speaking = False  # True while TTS is actively playing
        
        # Interrupt detection - shared flag for both ESC and voice commands
        self.interrupt_flag = False
        self.interrupt_listener_running = False
        self.porcupine = None
        self.pa = None
        self.audio_stream = None
        
        logger.info(f"Voice Interface v{__version__} initialized")
        logger.info(f"Whisper model: {whisper_model}")
        logger.info(f"TTS mode: {self.tts_mode}")
        logger.info(f"Porcupine available: {PORCUPINE_AVAILABLE}")
        logger.info(f"Keyboard interrupt available: {KEYBOARD_AVAILABLE}")
    
    def start_interrupt_listener(self):
        """Start background thread to listen for wake word that triggers virtual ESC"""
        if not PORCUPINE_AVAILABLE or not KEYBOARD_AVAILABLE:
            logger.warning("Cannot start voice interrupt - Porcupine or keyboard module not available")
            return
        
        if not self.porcupine_access_key:
            logger.warning("Cannot start voice interrupt - Porcupine access key not provided")
            return
        
        if self.interrupt_listener_running:
            return
        
        self.interrupt_listener_running = True
        thread = threading.Thread(target=self._interrupt_listener_loop, daemon=True)
        thread.start()
        logger.info("Voice interrupt listener started - say wake word to interrupt TTS")
    
    def stop_interrupt_listener(self):
        """Stop the interrupt listener"""
        self.interrupt_listener_running = False
        
        if self.audio_stream:
            try:
                self.audio_stream.stop_stream()
                self.audio_stream.close()
            except:
                pass
            self.audio_stream = None
        
        if self.porcupine:
            try:
                self.porcupine.delete()
            except:
                pass
            self.porcupine = None
        
        if self.pa:
            try:
                self.pa.terminate()
            except:
                pass
            self.pa = None
    
    def _interrupt_listener_loop(self):
        """Background loop that listens for wake word and triggers virtual ESC keypress"""
        try:
            # Initialize Porcupine - use "terminator" as it's unlikely to be said in normal conversation
            self.porcupine = pvporcupine.create(
                access_key=self.porcupine_access_key,
                keywords=['terminator']
            )
            
            self.pa = pyaudio.PyAudio()
            
            self.audio_stream = self.pa.open(
                rate=self.porcupine.sample_rate,
                channels=1,
                format=pyaudio.paInt16,
                input=True,
                frames_per_buffer=self.porcupine.frame_length,
                input_device_index=self.microphone_index
            )
            
            logger.info("Voice interrupt active - say 'terminator' to interrupt TTS")
            
            while self.interrupt_listener_running:
                pcm = self.audio_stream.read(self.porcupine.frame_length, exception_on_overflow=False)
                pcm = struct.unpack_from("h" * self.porcupine.frame_length, pcm)
                
                keyword_index = self.porcupine.process(pcm)
                
                if keyword_index >= 0:
                    # Wake word detected - set interrupt flag!
                    logger.info("Wake word detected - setting interrupt flag")
                    self.interrupt_flag = True
                    
                    # Brief pause to avoid multiple detections
                    time.sleep(0.5)
        
        except Exception as e:
            logger.error(f"Error in interrupt listener: {e}")
        
        finally:
            self.stop_interrupt_listener()
    
    def listen(self, timeout: int = 10, phrase_time_limit: int = 30) -> str:
        """
        Listen for speech and convert to text using Whisper
        
        Args:
            timeout: Seconds to wait for speech to start
            phrase_time_limit: Maximum seconds for the phrase
            
        Returns:
            Transcribed text or empty string
        """
        try:
            with sr.Microphone(device_index=self.microphone_index) as source:
                logger.info("Listening...")
                
                # Adjust for ambient noise
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                
                # Listen for audio
                audio = self.recognizer.listen(
                    source,
                    timeout=timeout,
                    phrase_time_limit=phrase_time_limit
                )
                
                logger.info("Processing speech...")
                
                # Use Whisper for transcription
                text = self.recognizer.recognize_whisper(
                    audio,
                    model=self.whisper_model,
                    language="english"
                )
                
                logger.info(f"Recognized: {text}")
                return text
                
        except sr.WaitTimeoutError:
            logger.debug("Listening timeout - no speech detected")
            return ""
        except sr.UnknownValueError:
            logger.warning("Could not understand audio")
            return ""
        except Exception as e:
            logger.error(f"Error in speech recognition: {e}")
            return ""
    
    def speak(self, text: str):
        """
        Convert text to speech
        
        Args:
            text: Text to speak
        """
        if not self.voice_output_enabled:
            return
        
        if not text or not text.strip():
            return
        
        # Reset interrupt flag
        self.interrupt_flag = False
        
        self.is_speaking = True
        try:
            if self.tts_mode == 'piper':
                self._speak_piper(text)
            else:
                self._speak_gtts(text)
        except Exception as e:
            logger.error(f"Error in TTS: {e}")
        finally:
            self.is_speaking = False
    
    def _speak_piper(self, text: str):
        """Speak using Piper TTS (offline)"""
        if not self.piper_path or not self.piper_model:
            logger.error("Piper TTS not configured")
            return
        
        try:
            import re
            
            # Clean text for Piper (remove non-ASCII)
            clean_text = re.sub(r'[^\x00-\x7F]+', '', text)
            
            # Create temporary WAV file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_wav:
                wav_path = temp_wav.name
            
            # Generate speech with Piper
            cmd = [
                self.piper_path,
                '--model', self.piper_model,
                '--output_file', wav_path,
                '--length_scale', str(1.0 / self.speech_rate)
            ]
            
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8'
            )
            
            stdout, stderr = process.communicate(input=clean_text)
            
            if process.returncode != 0:
                logger.error(f"Piper TTS error: {stderr}")
                return
            
            # Play using PyAudio with ESC detection
            self._play_wav(wav_path)
            
            # Clean up
            try:
                os.unlink(wav_path)
            except:
                pass
            
        except Exception as e:
            logger.error(f"Error in Piper TTS: {e}")
    
    def _speak_gtts(self, text: str):
        """Speak using Google TTS (online)"""
        try:
            from gtts import gTTS
            from pydub import AudioSegment
            
            # Create temporary MP3 file
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_mp3:
                mp3_path = temp_mp3.name
            
            # Generate speech
            tts = gTTS(text=text, lang='en', slow=False)
            tts.save(mp3_path)
            
            # Convert to WAV
            audio = AudioSegment.from_mp3(mp3_path)
            
            # Adjust speed if needed
            if self.speech_rate != 1.0:
                audio = audio.speedup(playback_speed=self.speech_rate)
            
            # Save as WAV
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_wav:
                wav_path = temp_wav.name
            audio.export(wav_path, format='wav')
            
            # Play using PyAudio with ESC detection
            self._play_wav(wav_path)
            
            # Clean up
            try:
                os.unlink(mp3_path)
                os.unlink(wav_path)
            except:
                pass
            
        except Exception as e:
            logger.error(f"Error in gTTS: {e}")
    
    def _play_wav(self, wav_file: str):
        """
        Play a WAV file using PyAudio with ESC key interrupt support
        This is the OLD method that worked - plays in chunks and checks ESC in loop
        
        Args:
            wav_file: Path to WAV file
        """
        try:
            # Open WAV file
            wf = wave.open(wav_file, 'rb')
            
            # Initialize PyAudio
            p = pyaudio.PyAudio()
            
            # Open stream
            stream = p.open(
                format=p.get_format_from_width(wf.getsampwidth()),
                channels=wf.getnchannels(),
                rate=wf.getframerate(),
                output=True
            )
            
            # Read and play audio in chunks
            chunk_size = 1024
            data = wf.readframes(chunk_size)
            
            print("🔊 Speaking... (Press Esc to interrupt)")
            
            interrupted = False
            while data:
                # Check for BOTH ESC key AND interrupt flag
                if (KEYBOARD_AVAILABLE and keyboard.is_pressed('esc')) or self.interrupt_flag:
                    print("\n⏹️ Speech interrupted!")
                    interrupted = True
                    self.interrupt_flag = False  # Reset flag
                    break
                
                stream.write(data)
                data = wf.readframes(chunk_size)
            
            # Clean up
            stream.stop_stream()
            stream.close()
            p.terminate()
            wf.close()
            
            if interrupted and KEYBOARD_AVAILABLE:
                # Wait for Esc key to be released
                while keyboard.is_pressed('esc'):
                    time.sleep(0.01)
            
        except Exception as e:
            logger.error(f"Error playing audio: {e}")
    
    def enable_voice_output(self):
        """Enable voice output"""
        self.voice_output_enabled = True
        logger.info("Voice output enabled")
    
    def disable_voice_output(self):
        """Disable voice output"""
        self.voice_output_enabled = False
        logger.info("Voice output disabled")
    
    def toggle_tts_mode(self):
        """Toggle between Piper and gTTS"""
        if self.tts_mode == 'piper':
            self.tts_mode = 'gtts'
        else:
            if self.piper_path and self.piper_model:
                self.tts_mode = 'piper'
            else:
                logger.warning("Cannot switch to Piper - not configured")
                return
        
        logger.info(f"TTS mode switched to: {self.tts_mode}")
    
    def get_tts_mode(self) -> str:
        """Get current TTS mode"""
        return self.tts_mode
    
    def set_tts_mode(self, mode: str):
        """Set TTS mode"""
        if mode.lower() in ['piper', 'gtts']:
            self.tts_mode = mode.lower()
            logger.info(f"TTS mode set to: {self.tts_mode}")
    
    def test_microphone(self) -> bool:
        """
        Test if microphone is working
        
        Returns:
            True if microphone test successful
        """
        try:
            with sr.Microphone(device_index=self.microphone_index) as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
                logger.info("Microphone test successful")
                return True
        except Exception as e:
            logger.error(f"Microphone test failed: {e}")
            return False


def initialize_voice_interface(whisper_model: str = "base", microphone_index: int = None,
                               piper_path: str = None, piper_model: str = None,
                               speech_rate: float = 1.0, porcupine_access_key: str = None) -> VoiceInterface:
    """
    Initialize and return a VoiceInterface instance
    
    Args:
        whisper_model: Whisper model size
        microphone_index: Microphone device index
        piper_path: Path to Piper executable
        piper_model: Path to Piper model
        speech_rate: Speech rate multiplier
        porcupine_access_key: Picovoice access key (get free at console.picovoice.ai)
    
    Returns:
        VoiceInterface instance (v2.2)
    """
    voice = VoiceInterface(
        whisper_model=whisper_model,
        microphone_index=microphone_index,
        piper_path=piper_path,
        piper_model=piper_model,
        speech_rate=speech_rate,
        porcupine_access_key=porcupine_access_key
    )
    
    # Start interrupt listener if available
    voice.start_interrupt_listener()
    
    return voice