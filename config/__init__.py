"""
Configuration Module
====================
Application settings and voice configurations.
"""

from .settings import Settings
from .voices import VOICES, DEFAULT_VOICE

__all__ = ["Settings", "VOICES", "DEFAULT_VOICE"]
