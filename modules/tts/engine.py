"""
TTS Engine Module
=================
Kokoro-82M TTS engine via mlx-audio framework.
Optimized for Apple Silicon with 4-bit quantization.
"""

import gc
import time
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Literal
import numpy as np

from modules.errors import TTSModelError, SynthesisError, VRAMOverflowError

# MLX imports - lazy loaded to avoid import errors if not installed
try:
    import mlx.core as mx
    from mlx_audio.tts.generate import generate_audio
    MLX_AVAILABLE = True
except ImportError:
    MLX_AVAILABLE = False


@dataclass
class TTSConfig:
    """Configuration for TTS engine."""
    model_name: str = "mlx-community/Kokoro-82M"
    quantization: Literal["4bit", "6bit", "8bit", "bf16"] = "bf16"
    sample_rate: int = 24000
    default_voice: str = "am_adam"
    max_chunk_tokens: int = 500


class TTSEngine:
    """
    Kokoro-82M TTS engine wrapper.
    
    Uses mlx-audio for GPU-accelerated inference on Apple Silicon.
    Supports 4-bit and 8-bit quantization for memory efficiency.
    """
    
    def __init__(self, config: Optional[TTSConfig] = None):
        """
        Initialize the TTS engine.
        
        Args:
            config: TTS configuration (uses defaults if None)
        """
        if not MLX_AVAILABLE:
            raise ImportError(
                "mlx-audio not installed. Install with: pip install mlx-audio"
            )
        
        self.config = config or TTSConfig()
        self._model_loaded = False
        self._model = None
        
        # Determine model path based on quantization
        self._model_path = self._get_model_path()
    
    def _get_model_path(self) -> str:
        """Get the model path based on quantization setting."""
        base = self.config.model_name
        if self.config.quantization == "bf16":
            return f"{base}-bf16"
        elif self.config.quantization == "6bit":
            return f"{base}-6bit"
        elif self.config.quantization == "8bit":
            return f"{base}-8bit"
        elif self.config.quantization == "4bit":
            return f"{base}-4bit"
        return f"{base}-bf16"
    
    @property
    def is_loaded(self) -> bool:
        """Check if model is currently loaded."""
        return self._model_loaded
    
    @property
    def sample_rate(self) -> int:
        """Get the audio sample rate."""
        return self.config.sample_rate
    
    def load_model(self, quantization: Optional[str] = None) -> None:
        """
        Load the TTS model into memory.
        
        Args:
            quantization: Override quantization setting ('4bit', '8bit', 'full')
        """
        if self._model_loaded:
            return
        
        if quantization:
            self.config.quantization = quantization
            self._model_path = self._get_model_path()
        
        # Model is lazily loaded by mlx-audio on first generate call
        # We just mark it as ready here
        self._model_loaded = True
        print(f"TTS Engine ready: {self._model_path}")
    
    def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        speed: float = 1.0,
        max_retries: int = 3,
    ) -> np.ndarray:
        """
        Synthesize speech from text.
        
        Args:
            text: Text to synthesize
            voice: Voice ID (e.g., 'am_adam', 'af_bella')
            speed: Speech speed multiplier (0.5-2.0)
            max_retries: Number of retries for model download failures
            
        Returns:
            Audio as numpy array (float32, mono, 24kHz)
            
        Raises:
            TTSModelError: If model fails to load/download
            SynthesisError: If speech synthesis fails
            VRAMOverflowError: If not enough VRAM
        """
        import tempfile
        import soundfile as sf
        import os
        
        if not text.strip():
            return np.array([], dtype=np.float32)
        
        voice = voice or self.config.default_voice
        
        # Clamp speed to valid range
        speed = max(0.5, min(2.0, speed))
        
        last_error = None
        for attempt in range(max_retries):
            try:
                # Generate audio using mlx-audio to temp directory
                with tempfile.TemporaryDirectory() as temp_dir:
                    generate_audio(
                        text=text,
                        model=self._model_path,
                        voice=voice,
                        speed=speed,
                        output_path=temp_dir,
                        file_prefix="tts_output",
                        audio_format="wav",
                        verbose=False
                    )
                    
                    # Find the generated file
                    wav_files = [f for f in os.listdir(temp_dir) if f.endswith('.wav')]
                    if not wav_files:
                        raise SynthesisError("No audio file generated")
                    
                    # Read the audio file
                    audio_path = os.path.join(temp_dir, wav_files[0])
                    audio, sample_rate = sf.read(audio_path, dtype='float32')
                    
                    return audio
                
            except MemoryError as e:
                raise VRAMOverflowError(model_name=self._model_path)
            
            except (OSError, IOError) as e:
                error_str = str(e).lower()
                # Check for network/download related errors
                if any(k in error_str for k in ['download', 'connection', 'network', 'timeout', 'http', 'repository']):
                    last_error = e
                    if attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 2  # Exponential backoff
                        print(f"Model download failed, retrying in {wait_time}s... (attempt {attempt + 1}/{max_retries})")
                        time.sleep(wait_time)
                        continue
                    raise TTSModelError(
                        message=f"Failed to download model after {max_retries} attempts: {str(e)}",
                        model_name=self._model_path
                    )
                raise SynthesisError(message=str(e))
            
            except Exception as e:
                error_str = str(e).lower()
                # Check for model loading errors
                if any(k in error_str for k in ['model', 'load', 'weight', 'checkpoint']):
                    if 'download' in error_str or 'network' in error_str:
                        last_error = e
                        if attempt < max_retries - 1:
                            wait_time = (attempt + 1) * 2
                            print(f"Model load failed, retrying in {wait_time}s... (attempt {attempt + 1}/{max_retries})")
                            time.sleep(wait_time)
                            continue
                    raise TTSModelError(
                        message=f"Model loading failed: {str(e)}",
                        model_name=self._model_path
                    )
                # Check for memory errors
                if 'memory' in error_str or 'vram' in error_str or 'oom' in error_str:
                    raise VRAMOverflowError(model_name=self._model_path)
                # Generic synthesis error
                raise SynthesisError(message=str(e))
        
        # Should not reach here, but just in case
        if last_error:
            raise TTSModelError(
                message=f"Failed after {max_retries} attempts: {str(last_error)}",
                model_name=self._model_path
            )
    
    def synthesize_to_file(
        self,
        text: str,
        output_path: Path | str,
        voice: Optional[str] = None,
        speed: float = 1.0
    ) -> Path:
        """
        Synthesize speech and save to WAV file.
        
        Args:
            text: Text to synthesize
            output_path: Path for output WAV file
            voice: Voice ID
            speed: Speech speed multiplier
            
        Returns:
            Path to generated WAV file
        """
        import soundfile as sf
        
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        audio = self.synthesize(text, voice, speed)
        
        sf.write(
            str(output_path),
            audio,
            self.config.sample_rate,
            subtype='PCM_16'
        )
        
        return output_path
    
    def unload_model(self) -> None:
        """
        Unload the model and free memory.
        
        Important for VRAM management on 16GB unified memory.
        """
        if not self._model_loaded:
            return
        
        self._model = None
        self._model_loaded = False
        
        # Force garbage collection
        gc.collect()
        
        # Clear MLX cache if available
        if MLX_AVAILABLE:
            try:
                mx.clear_cache()
            except Exception:
                pass
        
        print("TTS Engine unloaded, memory freed")
    
    def __enter__(self):
        """Context manager entry."""
        self.load_model()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensures cleanup."""
        self.unload_model()
        return False


# Available voices for Kokoro-82M
KOKORO_VOICES = {
    "af_bella": "American Female - Bella (warm, conversational)",
    "af_sarah": "American Female - Sarah (professional, clear)",
    "am_adam": "American Male - Adam (deep, authoritative)",
    "am_michael": "American Male - Michael (friendly, casual)",
    "bf_emma": "British Female - Emma (refined, articulate)",
    "bm_george": "British Male - George (classic, distinguished)",
}


def list_voices() -> dict[str, str]:
    """List all available voices with descriptions."""
    return KOKORO_VOICES.copy()


def test_synthesis() -> bool:
    """
    Quick test of TTS synthesis.
    
    Returns:
        True if test passes
    """
    try:
        engine = TTSEngine()
        engine.load_model()
        
        audio = engine.synthesize("Hello, this is a test.", voice="am_adam")
        
        if len(audio) == 0:
            print("Test failed: Empty audio output")
            return False
        
        print(f"Test passed: Generated {len(audio)} samples")
        engine.unload_model()
        return True
        
    except Exception as e:
        print(f"Test failed: {e}")
        return False


if __name__ == "__main__":
    test_synthesis()
