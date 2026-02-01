"""
Audio Encoder Module
====================
FFmpeg-based audio encoding for WAV to MP3 conversion.
Optimized for audiobook production with hardware acceleration.
"""

from __future__ import annotations

import subprocess
import shutil
from pathlib import Path
from typing import Optional
import json

from ..errors import FFmpegNotFoundError


def _check_ffmpeg() -> bool:
    """Check if FFmpeg is available in PATH."""
    return shutil.which("ffmpeg") is not None


def _check_ffprobe() -> bool:
    """Check if FFprobe is available in PATH."""
    return shutil.which("ffprobe") is not None


class AudioEncoder:
    """
    FFmpeg-based audio encoder for audiobook production.
    
    Converts WAV files to MP3 with configurable bitrate.
    Optimized for Apple Silicon with hardware acceleration.
    """
    
    def __init__(self, bitrate: str = "128k", sample_rate: int = 24000):
        """
        Initialize the audio encoder.
        
        Args:
            bitrate: Target MP3 bitrate (default '128k')
            sample_rate: Audio sample rate in Hz (default 24000)
        """
        if not _check_ffmpeg():
            raise FFmpegNotFoundError()
        
        self.bitrate = bitrate
        self.sample_rate = sample_rate
    
    def wav_to_mp3(
        self,
        input_path: Path | str,
        output_path: Path | str,
        bitrate: Optional[str] = None
    ) -> Path:
        """
        Convert WAV file to MP3.
        
        Args:
            input_path: Path to input WAV file
            output_path: Path for output MP3 file
            bitrate: Override default bitrate (e.g., '128k', '192k')
            
        Returns:
            Path to generated MP3 file
        """
        input_path = Path(input_path)
        output_path = Path(output_path)
        bitrate = bitrate or self.bitrate
        
        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")
        
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Build FFmpeg command
        cmd = [
            "ffmpeg",
            "-y",  # Overwrite output
            "-i", str(input_path),
            "-c:a", "libmp3lame",
            "-b:a", bitrate,
            "-ar", str(self.sample_rate),
            "-ac", "1",  # Mono
            "-q:a", "2",  # High quality
            str(output_path)
        ]
        
        # Run FFmpeg
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg encoding failed: {result.stderr}")
        
        return output_path
    
    def get_duration(self, file_path: Path | str) -> float:
        """
        Get audio file duration in seconds.
        
        Uses ffprobe for accurate duration measurement.
        
        Args:
            file_path: Path to audio file
            
        Returns:
            Duration in seconds
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        if not _check_ffprobe():
            raise FFmpegNotFoundError()
        
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            str(file_path)
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"FFprobe failed: {result.stderr}")
        
        data = json.loads(result.stdout)
        return float(data["format"]["duration"])
    
    def get_duration_formatted(self, file_path: Path | str) -> str:
        """
        Get audio duration as formatted string (HH:MM:SS).
        
        Args:
            file_path: Path to audio file
            
        Returns:
            Duration as formatted string
        """
        duration_sec = self.get_duration(file_path)
        hours = int(duration_sec // 3600)
        minutes = int((duration_sec % 3600) // 60)
        seconds = int(duration_sec % 60)
        
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"
    
    def batch_encode(
        self,
        input_files: list[Path | str],
        output_dir: Path | str,
        bitrate: Optional[str] = None
    ) -> list[Path]:
        """
        Encode multiple WAV files to MP3.
        
        Args:
            input_files: List of input WAV file paths
            output_dir: Output directory for MP3 files
            bitrate: Override default bitrate
            
        Returns:
            List of paths to generated MP3 files
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        output_files = []
        for input_file in input_files:
            input_path = Path(input_file)
            output_path = output_dir / input_path.with_suffix(".mp3").name
            
            self.wav_to_mp3(input_path, output_path, bitrate)
            output_files.append(output_path)
        
        return output_files
    
    def check_hardware_acceleration(self) -> dict[str, bool]:
        """
        Check available hardware acceleration options.
        
        Returns:
            Dict of acceleration options and availability
        """
        result = subprocess.run(
            ["ffmpeg", "-hwaccels"],
            capture_output=True,
            text=True
        )
        
        output = result.stdout + result.stderr
        
        return {
            "videotoolbox": "videotoolbox" in output.lower(),
            "cuda": "cuda" in output.lower(),
            "vaapi": "vaapi" in output.lower(),
        }


def test_encoder() -> bool:
    """
    Quick test of AudioEncoder functionality.
    
    Returns:
        True if test passes
    """
    import tempfile
    import numpy as np
    
    try:
        encoder = AudioEncoder()
        
        # Check FFmpeg is available
        accel = encoder.check_hardware_acceleration()
        print(f"Hardware acceleration: {accel}")
        
        # Create a test WAV file
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create simple test WAV using numpy and wave
            import wave
            
            test_wav = temp_path / "test.wav"
            test_mp3 = temp_path / "test.mp3"
            
            # Generate 1 second of 440Hz sine wave
            sample_rate = 24000
            duration = 1.0
            t = np.linspace(0, duration, int(sample_rate * duration))
            audio = (np.sin(2 * np.pi * 440 * t) * 32767).astype(np.int16)
            
            with wave.open(str(test_wav), 'w') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(audio.tobytes())
            
            # Test encoding
            result = encoder.wav_to_mp3(test_wav, test_mp3)
            assert result.exists(), "MP3 file not created"
            
            # Test duration
            duration = encoder.get_duration(test_mp3)
            assert 0.9 < duration < 1.1, f"Unexpected duration: {duration}"
            
            print(f"Encoded test.mp3: {encoder.get_duration_formatted(test_mp3)}")
            print("AudioEncoder test passed!")
            return True
        
    except Exception as e:
        print(f"AudioEncoder test failed: {e}")
        return False


if __name__ == "__main__":
    test_encoder()
