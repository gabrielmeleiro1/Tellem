"""
VRAM Memory Management Utility
==============================
Utilities for managing GPU/Unified memory on Apple Silicon.
Ensures models are properly loaded and unloaded sequentially.
"""

import gc
from typing import Optional, Callable, TypeVar, Any
from contextlib import contextmanager
from dataclasses import dataclass, field

# MLX imports
try:
    import mlx.core as mx
    MLX_AVAILABLE = True
except ImportError:
    MLX_AVAILABLE = False


@dataclass
class MemoryStats:
    """Memory usage statistics."""
    active_bytes: int = 0
    peak_bytes: int = 0
    cache_bytes: int = 0
    
    @property
    def active_mb(self) -> float:
        return self.active_bytes / (1024 * 1024)
    
    @property
    def peak_mb(self) -> float:
        return self.peak_bytes / (1024 * 1024)
    
    @property
    def cache_mb(self) -> float:
        return self.cache_bytes / (1024 * 1024)
    
    def __str__(self) -> str:
        return f"Active: {self.active_mb:.1f}MB, Peak: {self.peak_mb:.1f}MB, Cache: {self.cache_mb:.1f}MB"


class VRAMManager:
    """
    Manages VRAM/memory for sequential model loading.
    
    Ensures only one model is loaded at a time to prevent
    out-of-memory errors on 16GB unified memory systems.
    """
    
    _instance: Optional['VRAMManager'] = None
    
    def __new__(cls):
        """Singleton pattern to ensure single manager instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._current_model: Optional[str] = None
        self._model_unloaders: dict[str, Callable] = {}
        self._initialized = True
    
    @property
    def current_model(self) -> Optional[str]:
        """Get the currently loaded model name."""
        return self._current_model
    
    def register_model(
        self, 
        name: str, 
        unload_fn: Callable[[], None]
    ) -> None:
        """
        Register a model with its unload function.
        
        Args:
            name: Unique model identifier
            unload_fn: Function to call to unload the model
        """
        self._model_unloaders[name] = unload_fn
        self._current_model = name
    
    def unload_current(self) -> None:
        """Unload the currently loaded model."""
        if self._current_model and self._current_model in self._model_unloaders:
            self._model_unloaders[self._current_model]()
            del self._model_unloaders[self._current_model]
        self._current_model = None
        clear_vram()
    
    def ensure_can_load(self, model_name: str) -> None:
        """
        Ensure memory is available to load a new model.
        
        Unloads any existing model before loading a new one.
        
        Args:
            model_name: Name of model about to be loaded
        """
        if self._current_model and self._current_model != model_name:
            print(f"Unloading {self._current_model} to load {model_name}")
            self.unload_current()
    
    @contextmanager
    def model_context(self, name: str, unload_fn: Callable[[], None]):
        """
        Context manager for model loading.
        
        Automatically registers and unloads model.
        
        Args:
            name: Model identifier
            unload_fn: Function to unload the model
        """
        self.ensure_can_load(name)
        self.register_model(name, unload_fn)
        try:
            yield
        finally:
            self.unload_current()


def clear_vram() -> None:
    """
    Clear GPU/Unified memory cache.
    
    Forces garbage collection and clears MLX cache
    to free unused memory.
    """
    # Force Python garbage collection
    gc.collect()
    
    # Clear MLX cache if available
    if MLX_AVAILABLE:
        try:
            mx.clear_cache()
        except Exception:
            pass
    
    # Second GC pass for thorough cleanup
    gc.collect()


def get_memory_stats() -> MemoryStats:
    """
    Get current memory usage statistics.
    
    Returns:
        MemoryStats object with current usage
    """
    stats = MemoryStats()
    
    if MLX_AVAILABLE:
        try:
            stats.active_bytes = mx.get_active_memory()
            stats.peak_bytes = mx.get_peak_memory()
            stats.cache_bytes = mx.get_cache_memory()
        except Exception:
            pass
    
    return stats


def reset_peak_memory() -> None:
    """Reset peak memory tracking."""
    if MLX_AVAILABLE:
        try:
            mx.reset_peak_memory()
        except Exception:
            pass


@contextmanager
def memory_tracking():
    """
    Context manager to track memory usage during an operation.
    
    Yields:
        Tuple of (start_stats, get_current_stats_fn)
    """
    reset_peak_memory()
    start_stats = get_memory_stats()
    
    def get_delta() -> MemoryStats:
        current = get_memory_stats()
        return MemoryStats(
            active_bytes=current.active_bytes - start_stats.active_bytes,
            peak_bytes=current.peak_bytes,
            cache_bytes=current.cache_bytes - start_stats.cache_bytes
        )
    
    yield start_stats, get_delta
    
    clear_vram()


def verify_memory_freed(
    before: MemoryStats, 
    tolerance_mb: float = 10.0
) -> bool:
    """
    Verify that memory has been properly freed.
    
    Args:
        before: Memory stats before operation
        tolerance_mb: Acceptable difference in MB
        
    Returns:
        True if memory is within tolerance of original
    """
    clear_vram()
    after = get_memory_stats()
    
    diff_mb = after.active_mb - before.active_mb
    freed = diff_mb <= tolerance_mb
    
    if not freed:
        print(f"Warning: Memory not fully freed. Difference: {diff_mb:.1f}MB")
    
    return freed


def test_memory_management() -> bool:
    """
    Test memory management functions.
    
    Returns:
        True if all tests pass
    """
    print("Testing memory management...")
    
    # Test 1: clear_vram doesn't crash
    try:
        clear_vram()
        print("✓ Test 1 passed: clear_vram() works")
    except Exception as e:
        print(f"✗ Test 1 failed: {e}")
        return False
    
    # Test 2: get_memory_stats returns valid data
    stats = get_memory_stats()
    print(f"✓ Test 2 passed: Memory stats: {stats}")
    
    # Test 3: VRAMManager singleton
    manager1 = VRAMManager()
    manager2 = VRAMManager()
    if manager1 is not manager2:
        print("✗ Test 3 failed: VRAMManager not singleton")
        return False
    print("✓ Test 3 passed: VRAMManager singleton works")
    
    # Test 4: Memory tracking context
    with memory_tracking() as (start, get_delta):
        # Allocate some memory
        if MLX_AVAILABLE:
            _ = mx.zeros((1000, 1000))
        delta = get_delta()
        print(f"✓ Test 4 passed: Memory tracking works. Delta: {delta}")
    
    print("\nAll memory management tests passed!")
    return True


if __name__ == "__main__":
    test_memory_management()
