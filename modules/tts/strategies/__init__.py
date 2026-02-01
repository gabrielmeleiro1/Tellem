"""
TTS Strategies Module
=====================
Pluggable TTS engine implementations.

Available Strategies:
    - KokoroTTSStrategy: Kokoro-82M via mlx-audio (current default)
    - OrpheusTTSStrategy: Orpheus TTS (future)

Usage:
    from modules.tts.strategies import KokoroTTSStrategy, TTSVoice
    from modules.tts.factory import TTSEngineFactory
    
    # Direct usage
    engine = KokoroTTSStrategy()
    engine.load()
    audio = engine.synthesize("Hello world", voice="am_adam")
    
    # Via factory
    engine = TTSEngineFactory.create("kokoro")
"""

from modules.tts.strategies.base import TTSStrategy, TTSVoice, TTSConfig
from modules.tts.strategies.kokoro import KokoroTTSStrategy, KokoroConfig
from modules.tts.strategies.orpheus import OrpheusTTSStrategy, OrpheusConfig

__all__ = [
    # Base classes
    "TTSStrategy",
    "TTSVoice",
    "TTSConfig",
    # Implementations
    "KokoroTTSStrategy",
    "KokoroConfig",
    "OrpheusTTSStrategy",
    "OrpheusConfig",
]
