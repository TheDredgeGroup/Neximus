"""
Voice Interface Module
Handles speech-to-text and text-to-speech for the agent
"""

import speech_recognition as sr
import subprocess
import logging
from typing import Optional
import whisper
import os
import tempfile
import wave
import pyaudio

logger = logging.getLogger(__name__)


class VoiceInterface:
    """Voice interface for the agent using Whisper and pyttsx3"""
    
    def __init__(self, whisper_model: str = "base", microphone_index: int = None, 
                 piper_path: str = None, piper_model: str = None, speech_rate: float = 1.0):
        """
        Initialize voice interface
        
        Args:
            whisper_model: Whisper model size (tiny, base, small, medium, large)
            microphone_index: Microphone device index (None for default)
            piper_path: Path to piper.exe
            piper_model: Path to Piper voice model (.onnx file)
            speech_rate: Speech rate multiplier (1.0 = normal, 0.8 = slower, 1.2 = faster)
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
        
        # Piper TTS settings
        self.piper_path = piper_path
        self.piper_model = piper_model
        self.speech_rate = speech_rate
        
        # Voice mode enabled flag
        self.voice_output_enabled = True
        
        logger.info(f"Voice interface initialized with Piper TTS")
        logger.info(f"Piper: {piper_path}")
        logger.info(f"Model: {piper_model}")
    
    def listen(self, timeout: int = 5, phrase_time_limit: int = 10) -> Optional[str]:
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
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                
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
        Convert text to speech using Piper TTS
        
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
            
            # Create temporary file for audio
            temp_wav = tempfile.mktemp(suffix='.wav')
            
            # Run Piper to generate speech
            cmd = [
                self.piper_path,
                '--model', self.piper_model,
                '--output_file', temp_wav,
                '--length_scale', str(1.0 / self.speech_rate)  # Piper uses length_scale (inverse of speed)
            ]
            
            # Send text to Piper via stdin
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            stdout, stderr = process.communicate(input=text)
            
            if process.returncode != 0:
                logger.error(f"Piper TTS error: {stderr}")
                return
            
            # Play the generated audio
            self._play_wav(temp_wav)
            
            # Clean up temp file
            try:
                os.remove(temp_wav)
            except:
                pass
                
        except Exception as e:
            logger.error(f"Error during text-to-speech: {e}")
            print(f"❌ Speech error: {e}")
    
    def _play_wav(self, wav_file: str):
        """
        Play a WAV file using PyAudio
        
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
            
            while data:
                stream.write(data)
                data = wf.readframes(chunk_size)
            
            # Clean up
            stream.stop_stream()
            stream.close()
            p.terminate()
            wf.close()
            
        except Exception as e:
            logger.error(f"Error playing audio: {e}")
    
    def enable_voice_output(self):
        """Enable voice output"""
        self.voice_output_enabled = True
        logger.info("Voice output enabled")
    
    def disable_voice_output(self):
        """Disable voice output (text only)"""
        self.voice_output_enabled = False
        logger.info("Voice output disabled")
    
    def set_speech_rate(self, rate: float):
        """
        Set speech rate
        
        Args:
            rate: Speech rate multiplier (1.0 = normal, 0.8 = slower, 1.2 = faster)
        """
        self.speech_rate = rate
        logger.info(f"Speech rate set to: {rate}")
    
    def set_piper_model(self, model_path: str):
        """
        Change Piper voice model
        
        Args:
            model_path: Path to .onnx model file
        """
        self.piper_model = model_path
        logger.info(f"Piper model changed to: {model_path}")
    
    def test_speech(self, text: str = "Hello! Voice interface is working with British accent."):
        """
        Test the speech output
        
        Args:
            text: Test message
        """
        print(f"Testing Piper TTS output...")
        self.speak(text)


def initialize_voice_interface(
    whisper_model: str = "base",
    microphone_index: int = None,
    piper_path: str = None,
    piper_model: str = None,
    speech_rate: float = 1.0
) -> VoiceInterface:
    """
    Initialize and return voice interface
    
    Args:
        whisper_model: Whisper model size
        microphone_index: Microphone device index
        piper_path: Path to piper.exe
        piper_model: Path to Piper voice model
        speech_rate: Speech rate multiplier
    
    Returns:
        VoiceInterface instance
    """
    try:
        voice = VoiceInterface(
            whisper_model=whisper_model,
            microphone_index=microphone_index,
            piper_path=piper_path,
            piper_model=piper_model,
            speech_rate=speech_rate
        )
        logger.info("Voice interface initialized successfully")
        return voice
    except Exception as e:
        logger.error(f"Failed to initialize voice interface: {e}")
        raise
