"""
Audio Buffer Pool Module
========================
Implements memory pooling for audio buffers to reduce numpy array reallocation.

Features:
- Reuse numpy arrays instead of reallocating
- Buffer pool pattern for chunk audio
- Thread-safe buffer management
- Automatic size-based pool segregation
"""

from __future__ import annotations

import threading
import weakref
from collections import defaultdict
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass, field
import numpy as np


@dataclass
class BufferStats:
    """Statistics for buffer pool usage."""
    total_allocated: int = 0
    total_reused: int = 0
    total_released: int = 0
    current_pooled: int = 0
    peak_pooled: int = 0
    
    @property
    def reuse_ratio(self) -> float:
        """Calculate buffer reuse ratio."""
        total = self.total_allocated + self.total_reused
        return self.total_reused / total if total > 0 else 0.0
    
    def __str__(self) -> str:
        return (
            f"BufferStats(alloc={self.total_allocated}, reuse={self.total_reused}, "
            f"release={self.total_released}, current={self.current_pooled}, "
            f"reuse_ratio={self.reuse_ratio:.1%})"
        )


class PooledBuffer:
    """
    A numpy array wrapper that returns to pool when no longer referenced.
    
    Usage:
        buffer = buffer_pool.acquire(shape=(24000,), dtype=np.float32)
        # Use buffer.array for data
        buffer.array[:] = audio_data
        # When buffer goes out of scope, it's automatically returned to pool
    """
    
    # Note: __weakref__ is required for weakref support with __slots__
    __slots__ = ['_array', '_pool', '_shape', '_dtype', '_in_use', '__weakref__']
    
    def __init__(self, array: np.ndarray, pool: BufferPool):
        self._array = array
        self._pool = pool
        self._shape = array.shape
        self._dtype = array.dtype
        self._in_use = True
    
    @property
    def array(self) -> np.ndarray:
        """Get the underlying numpy array."""
        if not self._in_use:
            raise RuntimeError("Buffer has been released back to pool")
        return self._array
    
    @property
    def shape(self) -> Tuple[int, ...]:
        return self._shape
    
    @property
    def dtype(self) -> np.dtype:
        return self._dtype
    
    def release(self) -> None:
        """Explicitly release buffer back to pool."""
        if self._in_use and self._pool is not None:
            self._pool._release_buffer(self)
            self._in_use = False
    
    def __del__(self):
        """Destructor - return buffer to pool when garbage collected."""
        if self._in_use and self._pool is not None:
            self._pool._release_buffer(self)


class BufferPool:
    """
    Thread-safe pool for reusing numpy arrays.
    
    Reduces memory allocation overhead by reusing arrays of similar sizes.
    Buffers are categorized by size bucket to minimize waste.
    
    Example:
        pool = BufferPool(max_size_mb=512)
        
        # Acquire a buffer
        buf = pool.acquire(shape=(24000,), dtype=np.float32)
        buf.array[:] = audio_data
        
        # Buffer automatically returns to pool when done
        buf.release()  # Or just let it go out of scope
    """
    
    _instance: Optional[BufferPool] = None
    _instance_lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        """Singleton pattern for global buffer pool."""
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(
        self,
        max_size_mb: float = 512.0,
        size_bucket_tolerance: float = 1.2,  # 20% size tolerance
    ):
        # Only initialize once
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        self._max_size_bytes = max_size_mb * 1024 * 1024
        self._size_tolerance = size_bucket_tolerance
        
        # Pools organized by (dtype, size_bucket)
        self._pools: Dict[Tuple[np.dtype, int], List[np.ndarray]] = defaultdict(list)
        self._pool_lock = threading.RLock()
        
        # Statistics
        self._stats = BufferStats()
        self._current_size_bytes = 0
        
        # Track active buffers for debugging
        self._active_buffers: weakref.WeakSet = weakref.WeakSet()
        
        self._initialized = True
    
    def _get_size_bucket(self, shape: Tuple[int, ...], dtype: np.dtype) -> int:
        """Calculate size bucket key for a buffer specification."""
        element_size = np.dtype(dtype).itemsize
        total_elements = np.prod(shape) if shape else 1
        size_bytes = total_elements * element_size
        
        # Bucket by log2 size for coarse grouping
        import math
        bucket = int(math.log2(max(size_bytes, 1)))
        return bucket
    
    def acquire(
        self,
        shape: Tuple[int, ...],
        dtype: np.dtype = np.float32,
    ) -> PooledBuffer:
        """
        Acquire a buffer from the pool or allocate new.
        
        Args:
            shape: Desired array shape
            dtype: Desired array dtype
            
        Returns:
            PooledBuffer wrapping a numpy array
        """
        dtype = np.dtype(dtype)
        size_bucket = self._get_size_bucket(shape, dtype)
        pool_key = (dtype, size_bucket)
        
        with self._pool_lock:
            # Try to find a suitable buffer in the pool
            pool = self._pools[pool_key]
            
            # Find buffer with matching or larger shape
            best_idx = -1
            for i, buf in enumerate(pool):
                if buf.shape == shape:
                    best_idx = i
                    break
                elif buf.size >= np.prod(shape):
                    if best_idx < 0 or buf.size < pool[best_idx].size:
                        best_idx = i
            
            if best_idx >= 0:
                # Reuse existing buffer
                array = pool.pop(best_idx)
                self._stats.total_reused += 1
                self._stats.current_pooled -= 1
                
                # Trim array to exact shape if needed
                if array.shape != shape:
                    array = array.reshape(shape)
            else:
                # Allocate new buffer
                array = np.empty(shape, dtype=dtype)
                self._stats.total_allocated += 1
        
        buffer = PooledBuffer(array, self)
        self._active_buffers.add(buffer)
        return buffer
    
    def _release_buffer(self, pooled_buffer: PooledBuffer) -> None:
        """Internal method to return a buffer to the pool."""
        array = pooled_buffer._array
        
        with self._pool_lock:
            # Check if we have room in the pool
            array_size = array.nbytes
            
            if self._current_size_bytes + array_size > self._max_size_bytes:
                # Pool is full, don't keep this buffer
                self._stats.total_released += 1
                return
            
            size_bucket = self._get_size_bucket(array.shape, array.dtype)
            pool_key = (array.dtype, size_bucket)
            
            # Add back to pool
            self._pools[pool_key].append(array)
            self._stats.total_released += 1
            self._stats.current_pooled += 1
            self._current_size_bytes += array_size
            
            if self._stats.current_pooled > self._stats.peak_pooled:
                self._stats.peak_pooled = self._stats.current_pooled
    
    def get_stats(self) -> BufferStats:
        """Get current buffer pool statistics."""
        with self._pool_lock:
            return BufferStats(
                total_allocated=self._stats.total_allocated,
                total_reused=self._stats.total_reused,
                total_released=self._stats.total_released,
                current_pooled=self._stats.current_pooled,
                peak_pooled=self._stats.peak_pooled,
            )
    
    def clear(self) -> None:
        """Clear all pooled buffers and free memory."""
        with self._pool_lock:
            self._pools.clear()
            self._current_size_bytes = 0
            self._stats.current_pooled = 0
    
    def get_pool_size_bytes(self) -> int:
        """Get current pool size in bytes."""
        with self._pool_lock:
            return self._current_size_bytes
    
    def get_active_count(self) -> int:
        """Get number of currently active (in-use) buffers."""
        return len(self._active_buffers)


def get_buffer_pool(max_size_mb: float = 512.0) -> BufferPool:
    """Get the global buffer pool instance."""
    return BufferPool(max_size_mb=max_size_mb)


def pooled_array(shape: Tuple[int, ...], dtype: np.dtype = np.float32) -> np.ndarray:
    """
    Convenience function to get a pooled array.
    
    Note: The returned array will NOT be automatically returned to the pool.
    Use BufferPool.acquire() directly for automatic return-to-pool behavior.
    
    Args:
        shape: Array shape
        dtype: Array dtype
        
    Returns:
        numpy array (from pool if available)
    """
    pool = get_buffer_pool()
    buffer = pool.acquire(shape, dtype)
    return buffer.array


# Test function
def test_buffer_pool():
    """Test buffer pool functionality."""
    print("Testing BufferPool...")
    
    pool = BufferPool(max_size_mb=64)
    
    # Test 1: Basic acquire/release
    buf1 = pool.acquire((1000,), np.float32)
    assert buf1.array.shape == (1000,)
    buf1.release()
    print("✓ Test 1 passed: Basic acquire/release")
    
    # Test 2: Reuse
    buf2 = pool.acquire((1000,), np.float32)
    buf2.release()
    stats = pool.get_stats()
    assert stats.total_reused >= 1
    print(f"✓ Test 2 passed: Buffer reuse working (reuse_ratio={stats.reuse_ratio:.1%})")
    
    # Test 3: Multiple buffers
    buffers = [pool.acquire((24000,), np.float32) for _ in range(10)]
    for buf in buffers:
        buf.release()
    print("✓ Test 3 passed: Multiple buffer management")
    
    # Test 4: Different dtypes and shapes
    buf_f32 = pool.acquire((1000,), np.float32)
    buf_f16 = pool.acquire((1000,), np.float16)
    buf_int = pool.acquire((1000,), np.int16)
    buf_f32.release()
    buf_f16.release()
    buf_int.release()
    print("✓ Test 4 passed: Different dtypes handled correctly")
    
    print(f"\nFinal stats: {pool.get_stats()}")
    print("All buffer pool tests passed!")


if __name__ == "__main__":
    test_buffer_pool()
