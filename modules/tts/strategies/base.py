"""
TTS Strategy Base Interface
============================
Abstract base class for Text-to-Speech engine strategies.
Enables pluggable TTS engines (Kokoro, Orpheus, future).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Literal
import numpy as np


@dataclass
class TTSVoice:
    """Represents a TTS voice option."""
    id: str
    name: str
    language: str
    gender: Literal["male", "female", "neutral"]
    description: str
    is_multilingual: bool = False


@dataclass
class TTSConfig:
    """Base configuration for TTS engines."""
    sample_rate: int = 24000
    default_speed: float = 1.0
    max_chunk_tokens: int = 500
    quantization: Literal["4bit", "6bit", "8bit", "bf16"] = "bf16"
    batch_size: int = 4
    use_batching: bool = True


class TTSStrategy(ABC):
    """
    Abstract base class for TTS engine strategies.
    
    Implementations:
        - KokoroTTSStrategy: Kokoro-82M via mlx-audio
        - OrpheusTTSStrategy: Orpheus TTS (future)
        - OpenAITTSStrategy: OpenAI TTS API (future)
    """
    
    def __init__(self, config: Optional[TTSConfig] = None):
        """
        Initialize the TTS strategy.
        
        Args:
            config: TTS configuration (uses defaults if None)
        """
        self.config = config or TTSConfig()
        self._is_loaded = False
    
    # ==================== Properties ====================
    
    @property
    @abstractmethod
    def name(self) -> str:
        """
        Strategy name identifier.
        
        Returns:
            Short name like 'kokoro', 'orpheus', etc.
        """
        pass
    
    @property
    @abstractmethod
    def display_name(self) -> str:
        """
        Human-readable display name.
        
        Returns:
            Name like 'Kokoro 82M', 'Orpheus TTS', etc.
        """
        pass
    
    @property
    @abstractmethod
    def version(self) -> str:
        """
        Engine version string.
        
        Returns:
            Version like '1.0.0'
        """
        pass
    
    @property
    def is_loaded(self) -> bool:
        """Check if the model is currently loaded."""
        return self._is_loaded
    
    @property
    @abstractmethod
    def sample_rate(self) -> int:
        """
        Audio sample rate in Hz.
        
        Returns:
            Sample rate like 24000, 22050, etc.
        """
        pass
    
    @property
    @abstractmethod
    def supported_voices(self) -> list[TTSVoice]:
        """
        List of supported voice options.
        
        Returns:
            List of TTSVoice dataclasses
        """
        pass
    
    @property
    @abstractmethod
    def supports_batching(self) -> bool:
        """
        Whether this engine supports batch inference.
        
        Returns:
            True if batching is supported
        """
        pass
    
    @property
    @abstractmethod
    def supports_streaming(self) -> bool:
        """
        Whether this engine supports streaming generation.
        
        Returns:
            True if streaming is supported
        """
        pass
    
    # ==================== Lifecycle ====================
    
    @abstractmethod
    def load(self) -> None:
        """
        Load the TTS model into memory.
        
        Raises:
            ImportError: If required dependencies not installed
            RuntimeError: If model fails to load
        """
        pass
    
    @abstractmethod
    def unload(self) -> None:
        """
        Unload the model to free memory.
        Safe to call even if not loaded.
        """
        pass
    
    # ==================== Synthesis ====================
    
    @abstractmethod
    def synthesize(
        self,
        text: str,
        voice: str,
        speed: float = 1.0,
        output_path: Optional[Path] = None
    ) -> np.ndarray:
        """
        Synthesize speech from text.
        
        Args:
            text: Text to synthesize
            voice: Voice ID (must be in supported_voices)
            speed: Speech speed multiplier (0.5-2.0)
            output_path: Optional path to save audio directly
            
        Returns:
            Audio as numpy array (float32, mono)
            
        Raises:
            ValueError: If voice not supported
            RuntimeError: If synthesis fails
        """
        pass
    
    def synthesize_batch(
        self,
        texts: list[str],
        voice: str,
        speed: float = 1.0
    ) -> list[np.ndarray]:
        """
        Synthesize multiple texts in batch (if supported).
        
        Default implementation processes sequentially.
        Override for true batch processing.
        
        Args:
            texts: List of texts to synthesize
            voice: Voice ID
            speed: Speech speed multiplier
            
        Returns:
            List of audio arrays
        """
        return [self.synthesize(text, voice, speed) for text in texts]
    
    # ==================== Utilities ====================
    
    @abstractmethod
    def estimate_duration(self, text: str, speed: float = 1.0) -> float:
        """
        Estimate audio duration in seconds.
        
        Args:
            text: Text to estimate
            speed: Speech speed multiplier
            
        Returns:
            Estimated duration in seconds
        """
        pass
    
    def validate_voice(self, voice: str) -> bool:
        """
        Check if a voice ID is supported.
        
        Args:
            voice: Voice ID to validate
            
        Returns:
            True if voice is supported
        """
        return any(v.id == voice for v in self.supported_voices)
    
    def get_voice(self, voice_id: str) -> Optional[TTSVoice]:
        """
        Get voice details by ID.
        
        Args:
            voice_id: Voice identifier
            
        Returns:
            TTSVoice if found, None otherwise
        """
        for voice in self.supported_voices:
            if voice.id == voice_id:
                return voice
        return None
    
    def _clamp_speed(self, speed: float) -> float:
        """
        Clamp speed to valid range.
        
        Args:
            speed: Requested speed
            
        Returns:
            Speed clamped to 0.5-2.0 range
        """
        return max(0.5, min(2.0, speed))
