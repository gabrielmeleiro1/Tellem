"""
TTS Engine Module
=================
Kokoro-82M TTS engine via mlx-audio framework.
Optimized for Apple Silicon with 4-bit quantization.
"""

import gc
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Literal
import numpy as np

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
    model_name: str = "lucasnewman/kokoro-mlx"
    quantization: Literal["4bit", "8bit", "full"] = "4bit"
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
        if self.config.quantization == "4bit":
            return f"{base}-4bit"
        elif self.config.quantization == "8bit":
            return f"{base}-8bit"
        return base
    
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
        speed: float = 1.0
    ) -> np.ndarray:
        """
        Synthesize speech from text.
        
        Args:
            text: Text to synthesize
            voice: Voice ID (e.g., 'am_adam', 'af_bella')
            speed: Speech speed multiplier (0.5-2.0)
            
        Returns:
            Audio as numpy array (float32, mono, 24kHz)
        """
        if not text.strip():
            return np.array([], dtype=np.float32)
        
        voice = voice or self.config.default_voice
        
        # Clamp speed to valid range
        speed = max(0.5, min(2.0, speed))
        
        try:
            # Generate audio using mlx-audio
            audio = generate_audio(
                text=text,
                model=self._model_path,
                voice=voice,
                speed=speed
            )
            
            # Convert MLX array to numpy if needed
            if hasattr(audio, 'tolist'):
                audio = np.array(audio, dtype=np.float32)
            
            return audio
            
        except Exception as e:
            print(f"TTS synthesis error: {e}")
            raise
    
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
                mx.metal.clear_cache()
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
