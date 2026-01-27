"""
TTS Module
==========
Text-to-Speech engine using Kokoro-82M via MLX.
"""

from .engine import TTSEngine, TTSConfig, list_voices, KOKORO_VOICES

__all__ = ["TTSEngine", "TTSConfig", "list_voices", "KOKORO_VOICES"]
