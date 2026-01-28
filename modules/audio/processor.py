"""
Audio Processor Module
======================
PyDub-based audio processing for chunk merging,
volume normalization, and silence insertion.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Sequence, TYPE_CHECKING
import numpy as np

if TYPE_CHECKING:
    from pydub import AudioSegment as AudioSegmentType

try:
    from pydub import AudioSegment
    from pydub.effects import normalize
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False


class AudioProcessor:
    """
    Audio processing utilities using PyDub.
    
    Handles WAV file concatenation, volume normalization,
    and silence insertion for audiobook production.
    """
    
    def __init__(self, sample_rate: int = 24000, channels: int = 1):
        """
        Initialize the audio processor.
        
        Args:
            sample_rate: Audio sample rate in Hz (default 24000 for Kokoro TTS)
            channels: Number of audio channels (default 1 for mono)
        """
        if not PYDUB_AVAILABLE:
            raise ImportError(
                "pydub not installed. Install with: pip install pydub"
            )
        
        self.sample_rate = sample_rate
        self.channels = channels
        self.sample_width = 2  # 16-bit audio
    
    def concatenate(self, segments: Sequence[AudioSegment | Path | str]) -> AudioSegment:
        """
        Concatenate multiple audio segments into one.
        
        Args:
            segments: List of AudioSegment objects or paths to audio files
            
        Returns:
            Combined AudioSegment
        """
        if not segments:
            # Return empty audio segment
            return AudioSegment.silent(duration=0, frame_rate=self.sample_rate)
        
        result = None
        
        for segment in segments:
            if isinstance(segment, (str, Path)):
                # Load from file
                audio = AudioSegment.from_file(str(segment))
            else:
                audio = segment
            
            if result is None:
                result = audio
            else:
                result = result + audio
        
        return result
    
    def normalize_volume(
        self, 
        audio: AudioSegment, 
        target_dBFS: float = -16.0
    ) -> AudioSegment:
        """
        Normalize audio volume to target dBFS level.
        
        Args:
            audio: Input AudioSegment
            target_dBFS: Target loudness in dBFS (default -16)
            
        Returns:
            Volume-normalized AudioSegment
        """
        if len(audio) == 0:
            return audio
        
        # Calculate current dBFS
        current_dBFS = audio.dBFS
        
        # Handle silent audio (dBFS is -inf)
        if current_dBFS == float('-inf'):
            return audio
        
        # Calculate gain needed
        gain = target_dBFS - current_dBFS
        
        # Apply gain
        return audio.apply_gain(gain)
    
    def add_silence(self, audio: AudioSegment, duration_ms: int) -> AudioSegment:
        """
        Add silence to the end of an audio segment.
        
        Args:
            audio: Input AudioSegment
            duration_ms: Duration of silence in milliseconds
            
        Returns:
            AudioSegment with silence appended
        """
        if duration_ms <= 0:
            return audio
        
        silence = AudioSegment.silent(
            duration=duration_ms,
            frame_rate=audio.frame_rate
        )
        
        return audio + silence
    
    def add_silence_between_chapters(
        self, 
        audio: AudioSegment, 
        pause_ms: int = 1500
    ) -> AudioSegment:
        """
        Add chapter-appropriate pause (longer silence for chapter breaks).
        
        Args:
            audio: Input AudioSegment
            pause_ms: Duration of pause in milliseconds (default 1500ms)
            
        Returns:
            AudioSegment with chapter pause appended
        """
        return self.add_silence(audio, pause_ms)
    
    def from_numpy(self, audio_array: np.ndarray, sample_rate: int = None) -> AudioSegment:
        """
        Convert numpy array to AudioSegment.
        
        Args:
            audio_array: Audio as numpy array (float32, -1 to 1)
            sample_rate: Sample rate (uses default if None)
            
        Returns:
            AudioSegment
        """
        sample_rate = sample_rate or self.sample_rate
        
        # Convert float32 to int16
        if audio_array.dtype == np.float32 or audio_array.dtype == np.float64:
            audio_int16 = (audio_array * 32767).astype(np.int16)
        else:
            audio_int16 = audio_array.astype(np.int16)
        
        # Create AudioSegment
        return AudioSegment(
            audio_int16.tobytes(),
            frame_rate=sample_rate,
            sample_width=2,  # 16-bit
            channels=self.channels
        )
    
    def to_numpy(self, audio: AudioSegment) -> np.ndarray:
        """
        Convert AudioSegment to numpy array.
        
        Args:
            audio: Input AudioSegment
            
        Returns:
            Audio as numpy array (float32, -1 to 1)
        """
        samples = np.array(audio.get_array_of_samples())
        
        # Convert to float32 normalized
        return samples.astype(np.float32) / 32768.0
    
    def load(self, file_path: Path | str) -> AudioSegment:
        """
        Load audio file.
        
        Args:
            file_path: Path to audio file
            
        Returns:
            AudioSegment
        """
        return AudioSegment.from_file(str(file_path))
    
    def save(
        self, 
        audio: AudioSegment, 
        output_path: Path | str, 
        format: str = "wav"
    ) -> Path:
        """
        Save audio to file.
        
        Args:
            audio: AudioSegment to save
            output_path: Output file path
            format: Audio format ('wav', 'mp3', etc.)
            
        Returns:
            Path to saved file
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        audio.export(str(output_path), format=format)
        
        return output_path
    
    def get_duration_ms(self, audio: AudioSegment) -> int:
        """
        Get audio duration in milliseconds.
        
        Args:
            audio: Input AudioSegment
            
        Returns:
            Duration in milliseconds
        """
        return len(audio)
    
    def get_duration_seconds(self, audio: AudioSegment) -> float:
        """
        Get audio duration in seconds.
        
        Args:
            audio: Input AudioSegment
            
        Returns:
            Duration in seconds
        """
        return len(audio) / 1000.0


def test_processor() -> bool:
    """
    Quick test of AudioProcessor functionality.
    
    Returns:
        True if test passes
    """
    try:
        processor = AudioProcessor()
        
        # Create test audio from numpy
        duration_sec = 1.0
        sample_rate = 24000
        t = np.linspace(0, duration_sec, int(sample_rate * duration_sec))
        test_audio = np.sin(2 * np.pi * 440 * t).astype(np.float32)  # 440Hz sine wave
        
        # Convert to AudioSegment
        audio1 = processor.from_numpy(test_audio)
        audio2 = processor.from_numpy(test_audio)
        
        # Test concatenation
        combined = processor.concatenate([audio1, audio2])
        assert len(combined) == len(audio1) + len(audio2), "Concatenation failed"
        
        # Test normalization
        normalized = processor.normalize_volume(combined, target_dBFS=-16)
        assert abs(normalized.dBFS - (-16)) < 1.0, "Normalization failed"
        
        # Test silence addition
        with_silence = processor.add_silence(audio1, 500)
        assert len(with_silence) == len(audio1) + 500, "Silence addition failed"
        
        print("AudioProcessor test passed!")
        return True
        
    except Exception as e:
        print(f"AudioProcessor test failed: {e}")
        return False


if __name__ == "__main__":
    test_processor()
