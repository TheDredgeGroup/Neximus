"""
Voice Interface with Edge TTS (Ryan British Male Voice)
Includes audio processing for speed/pitch/volume control
"""

import asyncio
import edge_tts
import pyaudio
import wave
import logging
import os
import tempfile
from audio_processor import AudioProcessor, get_processor

logger = logging.getLogger(__name__)


class EdgeTTSVoice:
    """
    Edge TTS Voice Interface with Ryan (British Male)
    Supports audio processing for custom sound adjustment
    """
    
    def __init__(self, 
                 voice: str = "en-GB-RyanNeural",
                 rate: str = "-0%",  # Speed: -50% to +50%
                 volume: str = "+0%",  # Volume: -50% to +50%
                 pitch: str = "+0Hz",  # Pitch: -50Hz to +50Hz
                 audio_preset: str = "normal"):
        """
        Initialize Edge TTS voice
        
        Args:
            voice: Voice ID (default: en-GB-RyanNeural - British Male)
            rate: Speech rate (-50% to +50%)
            volume: Volume level (-50% to +50%)
            pitch: Pitch adjustment (-50Hz to +50Hz)
            audio_preset: Audio processing preset (normal, slow, fast, deep, clear)
        """
        self.voice = voice
        self.rate = rate
        self.volume = volume
        self.pitch = pitch
        self.audio_preset = audio_preset
        
        # Audio processor
        self.audio_processor = get_processor(audio_preset)
        
        # PyAudio for playback
        self.pyaudio = pyaudio.PyAudio()
        
        logger.info(f"Edge TTS initialized: {voice} (preset: {audio_preset})")
    
    async def _generate_speech(self, text: str, output_file: str):
        """
        Generate speech with Edge TTS
        
        Args:
            text: Text to speak
            output_file: Output MP3 file path
        """
        # Create communicate object with voice parameters
        communicate = edge_tts.Communicate(
            text,
            voice=self.voice,
            rate=self.rate,
            volume=self.volume,
            pitch=self.pitch
        )
        
        # Save to file
        await communicate.save(output_file)
    
    def speak(self, text: str):
        """
        Speak text using Edge TTS with audio processing
        
        Args:
            text: Text to speak
        """
        try:
            # Create temporary files
            temp_raw = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            temp_processed = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            temp_raw.close()
            temp_processed.close()
            
            # Generate speech
            logger.info(f"Generating speech: {text[:50]}...")
            asyncio.run(self._generate_speech(text, temp_raw.name))
            
            # Process audio
            logger.info(f"Processing audio with preset: {self.audio_preset}")
            self.audio_processor.process(temp_raw.name, temp_processed.name)
            
            # Play audio
            self._play_mp3(temp_processed.name)
            
            # Cleanup
            os.unlink(temp_raw.name)
            os.unlink(temp_processed.name)
            
        except Exception as e:
            logger.error(f"Speech generation failed: {e}")
    
    def _play_mp3(self, mp3_file: str):
        """
        Play MP3 file using PyAudio
        
        Args:
            mp3_file: Path to MP3 file
        """
        try:
            # Convert MP3 to WAV for playback
            from pydub import AudioSegment
            
            audio = AudioSegment.from_mp3(mp3_file)
            
            # Export as WAV to temp file
            temp_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            temp_wav.close()
            audio.export(temp_wav.name, format="wav")
            
            # Play WAV
            wf = wave.open(temp_wav.name, 'rb')
            
            stream = self.pyaudio.open(
                format=self.pyaudio.get_format_from_width(wf.getsampwidth()),
                channels=wf.getnchannels(),
                rate=wf.getframerate(),
                output=True
            )
            
            # Read and play
            chunk_size = 1024
            data = wf.readframes(chunk_size)
            
            while data:
                stream.write(data)
                data = wf.readframes(chunk_size)
            
            # Cleanup
            stream.stop_stream()
            stream.close()
            wf.close()
            os.unlink(temp_wav.name)
            
        except Exception as e:
            logger.error(f"Audio playback failed: {e}")
    
    def set_audio_preset(self, preset: str):
        """
        Change audio processing preset
        
        Args:
            preset: Preset name (normal, slow, fast, deep, clear)
        """
        self.audio_preset = preset
        self.audio_processor = get_processor(preset)
        logger.info(f"Audio preset changed to: {preset}")
    
    def cleanup(self):
        """Cleanup resources"""
        self.pyaudio.terminate()


# Test
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("Testing Edge TTS with Ryan (British Male)")
    print("="*60)
    
    # Test different presets
    presets = ["normal", "slow", "clear", "deep"]
    
    for preset in presets:
        print(f"\nTesting preset: {preset}")
        voice = EdgeTTSVoice(audio_preset=preset)
        voice.speak(f"Hello, I'm your AI agent speaking with the {preset} preset.")
        voice.cleanup()
        print(f"✓ {preset} preset complete")
    
    print("\n" + "="*60)
    print("Test complete!")