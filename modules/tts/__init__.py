"""
TTS Module
==========
Text-to-Speech engine using Kokoro-82M via MLX.
"""

from .engine import TTSEngine, TTSConfig, list_voices, KOKORO_VOICES
from .chunker import TextChunker, ChunkConfig, chunk_text
from .memory import VRAMManager, clear_vram, get_memory_stats
from .cleaner import TextCleaner, CleanerConfig

__all__ = [
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
]
