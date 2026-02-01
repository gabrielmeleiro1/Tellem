"""
TTS Module
==========
Text-to-Speech engine using Kokoro-82M via MLX.

Strategy Pattern:
    - TTSStrategy: Abstract base for TTS engines
    - KokoroTTSStrategy: Kokoro-82M implementation
    - OrpheusTTSStrategy: Future Orpheus support
    - TTSEngineFactory: Factory for creating engines
"""

# Legacy engine (kept for backward compatibility)
from .engine import TTSEngine, TTSConfig, list_voices, KOKORO_VOICES
from .chunker import TextChunker, ChunkConfig, chunk_text
from .memory import VRAMManager, clear_vram, get_memory_stats
from .cleaner import TextCleaner, CleanerConfig

# Strategy Pattern
from .strategies import (
    TTSStrategy,
    TTSVoice,
    TTSConfig as StrategyConfig,
    KokoroTTSStrategy,
    KokoroConfig,
    OrpheusTTSStrategy,
    OrpheusConfig,
)
from .factory import TTSEngineFactory, create_tts_engine

__all__ = [
    # Legacy
    "TTSEngine",
    "TTSConfig",
    "list_voices",
    "KOKORO_VOICES",
    "TextChunker",
    "ChunkConfig",
    "chunk_text",
    "VRAMManager",
    "clear_vram",
    "get_memory_stats",
    "TextCleaner",
    "CleanerConfig",
    # Strategy Pattern
    "TTSStrategy",
    "TTSVoice",
    "StrategyConfig",
    "KokoroTTSStrategy",
    "KokoroConfig",
    "OrpheusTTSStrategy",
    "OrpheusConfig",
    "TTSEngineFactory",
    "create_tts_engine",
]
