"""
Application Settings
====================
Central configuration for the Audiobook Creator.
"""

from pathlib import Path
from dataclasses import dataclass, field
from typing import Literal


@dataclass
class Settings:
    """Application configuration settings."""
    
    # Paths
    base_dir: Path = field(default_factory=lambda: Path(__file__).parent.parent)
    output_dir: Path = field(default_factory=lambda: Path.home() / "Audiobooks")
    cache_dir: Path = field(default_factory=lambda: Path(__file__).parent.parent / "cache")
    
    # Audio Settings
    audio_format: Literal["mp3", "wav", "m4b"] = "mp3"
    audio_bitrate: str = "128k"
    sample_rate: int = 24000
    normalize_volume: bool = True
    target_dbfs: float = -16.0
    
    # TTS Settings
    tts_engine: Literal["kokoro", "orpheus"] = "kokoro"
    tts_quantization: Literal["4bit", "8bit", "full"] = "4bit"
    max_chunk_tokens: int = 500
    
    # Processing
    use_text_cleaner: bool = True
    max_workers: int = 4
    
    # UI
    theme: str = "amber_obsidian"
    
    def __post_init__(self):
        """Ensure directories exist."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)


# Global settings instance
settings = Settings()
