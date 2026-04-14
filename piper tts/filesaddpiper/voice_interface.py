"""
Voice Interface Module
Handles speech-to-text and text-to-speech for the agent
"""

import speech_recognition as sr
import pyttsx3
import logging
from typing import Optional
import whisper

logger = logging.getLogger(__name__)


class VoiceInterface:
    """Voice interface for the agent using Whisper and pyttsx3"""
    
    def __init__(self, whisper_model: str = "base", voice_id: int = 0, speech_rate: int = 150, microphone_index: int = None):
        """
        Initialize voice interface
        
        Args:
            whisper_model: Whisper model size (tiny, base, small, medium, large)
            voice_id: Voice ID (0=David, 1=Zira on most systems)
            speech_rate: Words per minute (default 150)
            microphone_index: Microphone device index (None for default)
        """
        # Initialize speech recognition
        self.recognizer = sr.Recognizer()
        
        # Initialize microphone with better error handling
        try:
            if microphone_index is not None:
                logger.info(f"Attempting to use microphone index: {microphone_index}")
                self.microphone = sr.Microphone(device_index=microphone_index)
                # Test the microphone
                with self.microphone as source:
                    logger.info(f"Successfully initialized microphone {microphone_index}")
            else:
                logger.info("Using default microphone")
                self.microphone = sr.Microphone()
        except Exception as e:
            logger.error(f"Failed to initialize microphone {microphone_index}: {e}")
            logger.info("Falling back to default microphone")
            self.microphone = sr.Microphone()
        
        # Load Whisper model
        logger.info(f"Loading Whisper model: {whisper_model}")
        self.whisper_model = whisper.load_model(whisper_model)
        logger.info("Whisper model loaded")
        
        # Store TTS settings (engine will be created fresh for each speak call)
        self.voice_id = voice_id
        self.speech_rate = speech_rate
        
        # Voice mode enabled flag
        self.voice_output_enabled = True
        
        logger.info("Voice interface initialized")
    
    def listen(self, timeout: int = 10, phrase_time_limit: int = 15) -> Optional[str]:
        """
        Listen for speech input and convert to text
        
        Args:
            timeout: Seconds to wait for speech to start
            phrase_time_limit: Maximum seconds for phrase
        
        Returns:
            Transcribed text or None if failed
        """
        try:
            print("🎤 Listening... (speak now)")
            
            with self.microphone as source:
                # Adjust for ambient noise
                self.recognizer.adjust_for_ambient_noise(source, duration=4)
                
                # Listen for audio
                audio = self.recognizer.listen(
                    source, 
                    timeout=timeout,
                    phrase_time_limit=phrase_time_limit
                )
            
            print("🔄 Processing speech...")
            
            # Save audio to temporary WAV file
            with open("temp_audio.wav", "wb") as f:
                f.write(audio.get_wav_data())
            
            # Transcribe with Whisper
            result = self.whisper_model.transcribe("temp_audio.wav")
            text = result["text"].strip()
            
            logger.info(f"Transcribed: {text}")
            return text
                
        except sr.WaitTimeoutError:
            print("⏱️ No speech detected")
            return None
        except Exception as e:
            logger.error(f"Error during speech recognition: {e}")
            print(f"❌ Speech recognition error: {e}")
            return None
    
    def speak(self, text: str):
        """
        Convert text to speech
        
        Args:
            text: Text to speak
        """
        if not self.voice_output_enabled:
            return
        
        try:
            import time
            # Small delay to ensure microphone is fully released
            time.sleep(0.3)
            
            logger.info(f"Speaking: {text[:50]}...")
            
            # Create fresh engine for this speech
            engine = pyttsx3.init()
            
            # Set voice
            voices = engine.getProperty('voices')
            if voices and len(voices) > self.voice_id:
                engine.setProperty('voice', voices[self.voice_id].id)
            
            # Set speech rate
            engine.setProperty('rate', self.speech_rate)
            
            # Speak
            engine.say(text)
            engine.runAndWait()
            
            # Clean up
            engine.stop()
            del engine
            
        except Exception as e:
            logger.error(f"Error during text-to-speech: {e}")
            print(f"❌ Speech error: {e}")
    
    def enable_voice_output(self):
        """Enable voice output"""
        self.voice_output_enabled = True
        logger.info("Voice output enabled")
    
    def disable_voice_output(self):
        """Disable voice output (text only)"""
        self.voice_output_enabled = False
        logger.info("Voice output disabled")
    
    def set_voice(self, voice_id: int):
        """
        Change the voice
        
        Args:
            voice_id: Voice index
        """
        # Just update the stored voice_id
        self.voice_id = voice_id
        logger.info(f"Voice changed to index: {voice_id}")
        return True
    
    def set_speech_rate(self, rate: int):
        """
        Set speech rate
        
        Args:
            rate: Words per minute (100-300 typical)
        """
        self.speech_rate = rate
        logger.info(f"Speech rate set to: {rate}")
    
    def list_voices(self):
        """List available voices"""
        engine = pyttsx3.init()
        voices = engine.getProperty('voices')
        print("\nAvailable voices:")
        for i, voice in enumerate(voices):
            print(f"  {i}: {voice.name}")
        engine.stop()
        del engine
        return voices
    
    def test_speech(self, text: str = "Hello! Voice interface is working."):
        """
        Test the speech output
        
        Args:
            text: Test message
        """
        print(f"Testing speech output...")
        self.speak(text)


def initialize_voice_interface(
    whisper_model: str = "base",
    voice_id: int = 0,
    speech_rate: int = 150,
    microphone_index: int = None
) -> VoiceInterface:
    """
    Initialize and return voice interface
    
    Args:
        whisper_model: Whisper model size
        voice_id: Voice to use
        speech_rate: Speaking rate
        microphone_index: Microphone device index
    
    Returns:
        VoiceInterface instance
    """
    try:
        voice = VoiceInterface(
            whisper_model=whisper_model,
            voice_id=voice_id,
            speech_rate=speech_rate,
            microphone_index=microphone_index
        )
        logger.info("Voice interface initialized successfully")
        return voice
    except Exception as e:
        logger.error(f"Failed to initialize voice interface: {e}")
        raise