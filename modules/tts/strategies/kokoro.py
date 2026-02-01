"""
Kokoro TTS Strategy
===================
TTSStrategy implementation for Kokoro-82M via mlx-audio.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import numpy as np

from modules.tts.strategies.base import TTSStrategy, TTSVoice, TTSConfig
from modules.tts.engine import TTSEngine, TTSConfig as EngineConfig, BatchItem


# Voice definitions for Kokoro
KOKORO_VOICES = [
    TTSVoice(
        id="am_adam",
        name="Adam",
        language="en-US",
        gender="male",
        description="Deep, authoritative American male voice"
    ),
    TTSVoice(
        id="af_bella",
        name="Bella",
        language="en-US",
        gender="female",
        description="Warm, conversational American female voice"
    ),
    TTSVoice(
        id="am_michael",
        name="Michael",
        language="en-US",
        gender="male",
        description="Friendly, casual American male voice"
    ),
    TTSVoice(
        id="af_sarah",
        name="Sarah",
        language="en-US",
        gender="female",
        description="Professional, clear American female voice"
    ),
    TTSVoice(
        id="bf_emma",
        name="Emma",
        language="en-GB",
        gender="female",
        description="Refined, articulate British female voice"
    ),
    TTSVoice(
        id="bm_george",
        name="George",
        language="en-GB",
        gender="male",
        description="Classic, distinguished British male voice"
    ),
]


@dataclass
class KokoroConfig(TTSConfig):
    """Configuration specific to Kokoro TTS."""
    model_name: str = "mlx-community/Kokoro-82M"
    enable_streaming: bool = True
    stream_buffer_size: int = 8192


class KokoroTTSStrategy(TTSStrategy):
    """
    Kokoro-82M TTS strategy using mlx-audio framework.
    Optimized for Apple Silicon with quantization support.
    """
    
    def __init__(self, config: Optional[KokoroConfig] = None):
        """
        Initialize Kokoro TTS strategy.
        
        Args:
            config: Kokoro-specific configuration
        """
        super().__init__(config or KokoroConfig())
        self._engine: Optional[TTSEngine] = None
        self._config = config or KokoroConfig()
    
    # ==================== Properties ====================
    
    @property
    def name(self) -> str:
        return "kokoro"
    
    @property
    def display_name(self) -> str:
        return "Kokoro 82M"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def sample_rate(self) -> int:
        return self.config.sample_rate
    
    @property
    def supported_voices(self) -> list[TTSVoice]:
        return KOKORO_VOICES.copy()
    
    @property
    def supports_batching(self) -> bool:
        return True
    
    @property
    def supports_streaming(self) -> bool:
        return self._config.enable_streaming
    
    # ==================== Lifecycle ====================
    
    def load(self) -> None:
        """
        Load the Kokoro TTS model.
        
        Raises:
            ImportError: If mlx-audio not installed
        """
        if self._is_loaded and self._engine is not None:
            return
        
        # Convert strategy config to engine config
        engine_config = EngineConfig(
            model_name=self._config.model_name,
            quantization=self._config.quantization,
            sample_rate=self._config.sample_rate,
            default_voice="am_adam",
            max_chunk_tokens=self._config.max_chunk_tokens,
            batch_size=self._config.batch_size,
            use_batching=self._config.use_batching,
            enable_streaming=self._config.enable_streaming,
            stream_buffer_size=self._config.stream_buffer_size,
        )
        
        self._engine = TTSEngine(engine_config)
        self._engine.load_model()
        self._is_loaded = True
    
    def unload(self) -> None:
        """Unload the model to free memory."""
        if self._engine is not None:
            self._engine.unload_model()
            self._engine = None
        self._is_loaded = False
    
    # ==================== Synthesis ====================
    
    def synthesize(
        self,
        text: str,
        voice: str,
        speed: float = 1.0,
        output_path: Optional[Path] = None
    ) -> np.ndarray:
        """
        Synthesize speech using Kokoro.
        
        Args:
            text: Text to synthesize
            voice: Voice ID (must be in supported_voices)
            speed: Speech speed multiplier (0.5-2.0)
            output_path: Optional path to save audio
            
        Returns:
            Audio as numpy array (float32, mono, 24kHz)
            
        Raises:
            ValueError: If voice not supported
            RuntimeError: If synthesis fails
        """
        if not self._is_loaded or self._engine is None:
            raise RuntimeError("Model not loaded. Call load() first.")
        
        if not self.validate_voice(voice):
            raise ValueError(f"Voice '{voice}' not supported. "
                           f"Available: {[v.id for v in self.supported_voices]}")
        
        speed = self._clamp_speed(speed)
        
        return self._engine.synthesize(
            text=text,
            voice=voice,
            speed=speed,
            output_path=output_path
        )
    
    def synthesize_batch(
        self,
        texts: list[str],
        voice: str,
        speed: float = 1.0
    ) -> list[np.ndarray]:
        """
        Synthesize multiple texts using batch processing.
        
        Args:
            texts: List of texts to synthesize
            voice: Voice ID
            speed: Speech speed multiplier
            
        Returns:
            List of audio arrays
        """
        if not self._is_loaded or self._engine is None:
            raise RuntimeError("Model not loaded. Call load() first.")
        
        if not self.validate_voice(voice):
            raise ValueError(f"Voice '{voice}' not supported.")
        
        speed = self._clamp_speed(speed)
        
        # Create batch items
        batch_items = [
            BatchItem(text=text, voice=voice, speed=speed, index=i)
            for i, text in enumerate(texts)
        ]
        
        # Process batch
        results = self._engine.synthesize_batch(batch_items)
        
        # Sort by index and extract audio
        results.sort(key=lambda r: r.index)
        return [r.audio for r in results if r.audio is not None]
    
    # ==================== Utilities ====================
    
    def estimate_duration(self, text: str, speed: float = 1.0) -> float:
        """
        Estimate audio duration based on character count.
        
        Kokoro averages ~15 characters per second at 1.0 speed.
        
        Args:
            text: Text to estimate
            speed: Speech speed multiplier
            
        Returns:
            Estimated duration in seconds
        """
        if not text:
            return 0.0
        
        # Average speaking rate: ~15 chars/sec at normal speed
        chars_per_second = 15.0 * speed
        estimated = len(text) / chars_per_second
        
        return max(0.5, estimated)  # Minimum 0.5 seconds
    
    def get_stats(self) -> dict:
        """
        Get synthesis statistics from the underlying engine.
        
        Returns:
            Dict with statistics
        """
        if self._engine is None:
            return {
                "chunks_processed": 0,
                "average_chunk_time_ms": 0.0,
            }
        
        return {
            "chunks_processed": self._engine._total_chunks_processed,
            "average_chunk_time_ms": self._engine.average_chunk_time_ms,
        }