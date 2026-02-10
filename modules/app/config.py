"""
Application Configuration
=========================
Configuration management for the audiobook creator application.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class AppConfig:
    """
    Application configuration.
    
    Attributes:
        data_dir: Directory for application data (database, etc.)
        output_dir: Directory for output audiobooks
        temp_dir: Directory for temporary files
        default_voice: Default voice ID
        default_speed: Default speech speed
        cleaner_model_name: Default text-cleaner model ID
        max_parallel_chapters: Max chapters to process in parallel
        enable_parallel: Enable parallel processing
        db_path: Path to SQLite database
    """
    
    # Directories
    data_dir: Path = field(default_factory=lambda: Path("data"))
    output_dir: Path = field(default_factory=lambda: Path("output"))
    temp_dir: Path = field(default_factory=lambda: Path("temp"))
    
    # TTS defaults
    default_voice: str = "am_adam"
    default_speed: float = 1.0
    tts_engine: str = "kokoro"
    tts_quantization: str = "bf16"
    cleaner_model_name: str = "mlx-community/Llama-3.2-3B-Instruct-4bit"
    
    # Pipeline settings
    enable_parallel: bool = True
    max_parallel_chapters: int = 2
    chunk_size: int = 500
    
    # Audio settings
    mp3_bitrate: str = "128k"
    normalize_volume: bool = True
    target_dbfs: float = -16.0
    
    # Database
    db_path: Optional[Path] = None
    
    def __post_init__(self):
        """Ensure directories exist and set defaults."""
        # Create directories
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Set default db_path if not provided
        if self.db_path is None:
            self.db_path = self.data_dir / "audiobooks.db"
    
    @classmethod
    def from_dict(cls, config_dict: dict) -> "AppConfig":
        """
        Create config from dictionary.
        
        Args:
            config_dict: Configuration dictionary
            
        Returns:
            AppConfig instance
        """
        # Convert path strings to Path objects
        path_fields = {"data_dir", "output_dir", "temp_dir", "db_path"}
        processed = {}
        
        for key, value in config_dict.items():
            if key in path_fields and value is not None:
                processed[key] = Path(value)
            else:
                processed[key] = value
        
        return cls(**processed)
    
    def to_dict(self) -> dict:
        """
        Convert config to dictionary.
        
        Returns:
            Configuration dictionary
        """
        return {
            "data_dir": str(self.data_dir),
            "output_dir": str(self.output_dir),
            "temp_dir": str(self.temp_dir),
            "default_voice": self.default_voice,
            "default_speed": self.default_speed,
            "tts_engine": self.tts_engine,
            "tts_quantization": self.tts_quantization,
            "cleaner_model_name": self.cleaner_model_name,
            "enable_parallel": self.enable_parallel,
            "max_parallel_chapters": self.max_parallel_chapters,
            "chunk_size": self.chunk_size,
            "mp3_bitrate": self.mp3_bitrate,
            "normalize_volume": self.normalize_volume,
            "target_dbfs": self.target_dbfs,
            "db_path": str(self.db_path) if self.db_path else None,
        }
