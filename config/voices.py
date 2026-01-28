"""
Voice Configuration
===================
Voice presets for the TTS engine.
"""

from dataclasses import dataclass
from typing import Literal


@dataclass
class Voice:
    """Voice preset configuration."""
    id: str
    name: str
    gender: Literal["male", "female"]
    accent: Literal["american", "british"]
    style: str
    

# Available voices for Kokoro-82M
VOICES = {
    "af_bella": Voice(
        id="af_bella",
        name="Bella",
        gender="female",
        accent="american",
        style="warm, conversational"
    ),
    "af_sarah": Voice(
        id="af_sarah",
        name="Sarah",
        gender="female",
        accent="american",
        style="professional, clear"
    ),
    "am_adam": Voice(
        id="am_adam",
        name="Adam",
        gender="male",
        accent="american",
        style="deep, authoritative"
    ),
    "am_michael": Voice(
        id="am_michael",
        name="Michael",
        gender="male",
        accent="american",
        style="friendly, casual"
    ),
    "bf_emma": Voice(
        id="bf_emma",
        name="Emma",
        gender="female",
        accent="british",
        style="refined, articulate"
    ),
    "bm_george": Voice(
        id="bm_george",
        name="George",
        gender="male",
        accent="british",
        style="classic, distinguished"
    ),
}

# Default voice
DEFAULT_VOICE = "am_adam"


def get_voice(voice_id: str) -> Voice:
    """Get a voice by ID."""
    return VOICES.get(voice_id, VOICES[DEFAULT_VOICE])


def list_voices() -> list[str]:
    """List all available voice IDs."""
    return list(VOICES.keys())


def get_voice_choices() -> list[tuple[str, str]]:
    """
    Get voice choices for UI dropdowns.
    
    Returns:
        List of (display_name, voice_id) tuples
    """
    choices = []
    for voice in VOICES.values():
        display = f"{voice.name} ({voice.accent.title()} {voice.gender.title()}) - {voice.style}"
        choices.append((display, voice.id))
    return sorted(choices)


# Speed configuration
DEFAULT_SPEED = 1.0
MIN_SPEED = 0.5
MAX_SPEED = 2.0

SPEED_PRESETS = {
    "slow": 0.75,
    "normal": 1.0,
    "fast": 1.25,
    "very_fast": 1.5,
}

