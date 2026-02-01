"""
Audio Module
============
Audio processing, encoding, and M4B packaging.
"""

from .processor import AudioProcessor
from .encoder import AudioEncoder
from .packager import M4BPackager, AudiobookMetadata, ChapterMarker

# Buffer pool for memory-efficient audio processing
try:
    from .buffer_pool import (
        BufferPool,
        PooledBuffer,
        get_buffer_pool,
        pooled_array,
        BufferStats,
    )
    BUFFER_POOL_AVAILABLE = True
except ImportError:
    BUFFER_POOL_AVAILABLE = False

__all__ = [
    "AudioProcessor",
    "AudioEncoder",
    "M4BPackager",
    "AudiobookMetadata",
    "ChapterMarker",
]

if BUFFER_POOL_AVAILABLE:
    __all__.extend([
        "BufferPool",
        "PooledBuffer",
        "get_buffer_pool",
        "pooled_array",
        "BufferStats",
    ])
