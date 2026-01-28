"""
Audio Module
============
Audio processing, encoding, and M4B packaging.
"""

from .processor import AudioProcessor
from .encoder import AudioEncoder
from .packager import M4BPackager, AudiobookMetadata, ChapterMarker

__all__ = [
    "AudioProcessor",
    "AudioEncoder", 
    "M4BPackager",
    "AudiobookMetadata",
    "ChapterMarker",
]
