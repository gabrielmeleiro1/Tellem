"""
Tests for Memory Management Features
====================================
Tests dynamic batch sizing, idle timeout unloading, and buffer pooling.
"""

import time
import threading
import numpy as np
import pytest
from pathlib import Path

# Test buffer pool
try:
    from modules.audio.buffer_pool import (
        BufferPool,
        PooledBuffer,
        get_buffer_pool,
        pooled_array,
        BufferStats,
    )
    BUFFER_POOL_AVAILABLE = True
except ImportError:
    BUFFER_POOL_AVAILABLE = False

# Test VRAM monitor
try:
    from modules.tts.vram_monitor import (
        VRAMMonitor,
        IdleTimeoutManager,
        AdaptiveMemoryManager,
        DynamicBatchConfig,
        IdleTimeoutConfig,
        VRAMPressureLevel,
        VRAMSnapshot,
        get_memory_manager,
    )
    VRAM_MONITOR_AVAILABLE = True
except ImportError:
    VRAM_MONITOR_AVAILABLE = False


pytestmark = [
    pytest.mark.memory,
]


@pytest.mark.skipif(not BUFFER_POOL_AVAILABLE, reason="Buffer pool not available")
class TestBufferPool:
    """Tests for buffer pool functionality."""
    
    def test_buffer_pool_singleton(self):
        """Test that buffer pool is a singleton."""
        pool1 = BufferPool(max_size_mb=64)
        pool2 = BufferPool(max_size_mb=64)  # Same config
        
        assert pool1 is pool2
    
    def test_acquire_and_release(self):
        """Test buffer acquisition and release."""
        pool = BufferPool(max_size_mb=64)
        pool.clear()  # Start fresh
        
        # Acquire a buffer
        buf = pool.acquire((1000,), np.float32)
        assert buf.array.shape == (1000,)
        assert buf.array.dtype == np.float32
        
        # Release it
        buf.release()
        
        # Stats should show one allocated and one released
        stats = pool.get_stats()
        assert stats.total_allocated >= 1
        assert stats.total_released >= 1
    
    def test_buffer_reuse(self):
        """Test that buffers are reused."""
        pool = BufferPool(max_size_mb=64)
        pool.clear()
        
        # Acquire and release multiple times
        for _ in range(5):
            buf = pool.acquire((1000,), np.float32)
            buf.release()
        
        # Should have reused buffers
        stats = pool.get_stats()
        assert stats.total_reused >= 1
        assert stats.reuse_ratio > 0
    
    def test_different_dtypes(self):
        """Test buffer pool with different dtypes."""
        pool = BufferPool(max_size_mb=64)
        pool.clear()
        
        # Acquire buffers with different dtypes
        buf_f32 = pool.acquire((1000,), np.float32)
        buf_f16 = pool.acquire((1000,), np.float16)
        buf_i16 = pool.acquire((1000,), np.int16)
        
        assert buf_f32.dtype == np.float32
        assert buf_f16.dtype == np.float16
        assert buf_i16.dtype == np.int16
        
        buf_f32.release()
        buf_f16.release()
        buf_i16.release()
    
    def test_different_shapes(self):
        """Test buffer pool with different shapes."""
        pool = BufferPool(max_size_mb=64)
        pool.clear()
        
        # 1D array
        buf1d = pool.acquire((1000,), np.float32)
        assert buf1d.shape == (1000,)
        buf1d.release()
        
        # 2D array
        buf2d = pool.acquire((100, 100), np.float32)
        assert buf2d.shape == (100, 100)
        buf2d.release()
        
        # Large array
        buf_large = pool.acquire((24000,), np.float32)
        assert buf_large.shape == (24000,)
        buf_large.release()
    
    def test_pool_size_limit(self):
        """Test that pool respects size limits."""
        # Very small pool
        pool = BufferPool(max_size_mb=1)
        pool.clear()
        
        # Allocate a small buffer that fits (1K floats = 4KB)
        buf = pool.acquire((1000,), np.float32)  # ~4KB
        buf.release()
        
        # Pool should keep this small buffer
        pool_size = pool.get_pool_size_bytes()
        assert pool_size > 0  # Should have kept the buffer
        
        # Allocate a large buffer that exceeds limit
        large_buf = pool.acquire((500000,), np.float32)  # ~2MB
        large_buf.release()
        
        # Pool may or may not keep this depending on current size
        # Just verify pool still works
        new_buf = pool.acquire((100,), np.float32)
        new_buf.release()
    
    def test_concurrent_access(self):
        """Test thread-safe concurrent access."""
        import queue
        pool = BufferPool(max_size_mb=128)
        pool.clear()
        
        results = queue.Queue()
        errors = queue.Queue()
        
        def worker():
            try:
                for _ in range(10):
                    buf = pool.acquire((1000,), np.float32)
                    time.sleep(0.001)
                    buf.release()
                results.put(True)
            except Exception as e:
                errors.put(str(e))
        
        # Run multiple threads
        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)
        
        # Check for errors
        error_list = []
        while not errors.empty():
            error_list.append(errors.get())
        if error_list:
            pytest.fail(f"Concurrent access errors: {error_list}")
        
        # Check results
        result_list = []
        while not results.empty():
            result_list.append(results.get())
        assert len(result_list) == 5


@pytest.mark.skipif(not VRAM_MONITOR_AVAILABLE, reason="VRAM monitor not available")
class TestVRAMMonitor:
    """Tests for VRAM monitor functionality."""
    
    def test_initial_batch_sizes(self):
        """Test initial batch sizes are set correctly."""
        monitor = VRAMMonitor(total_vram_gb=16.0)
        
        assert monitor.get_tts_batch_size() == monitor.config.base_tts_batch_size
        assert monitor.get_cleaner_batch_size() == monitor.config.base_cleaner_batch_size
    
    def test_pressure_level_calculation(self):
        """Test pressure level calculation from usage ratio."""
        monitor = VRAMMonitor(total_vram_gb=16.0)
        
        assert monitor._calculate_pressure_level(0.5) == VRAMPressureLevel.NORMAL
        assert monitor._calculate_pressure_level(0.75) == VRAMPressureLevel.ELEVATED
        assert monitor._calculate_pressure_level(0.90) == VRAMPressureLevel.HIGH
        assert monitor._calculate_pressure_level(0.98) == VRAMPressureLevel.CRITICAL
    
    def test_batch_size_adjustment(self):
        """Test batch size adjustment based on pressure."""
        config = DynamicBatchConfig(
            base_tts_batch_size=8,
            min_tts_batch_size=1,
        )
        monitor = VRAMMonitor(total_vram_gb=16.0, config=config)
        
        # Critical pressure - should reduce significantly
        monitor._adjust_batch_sizes(VRAMPressureLevel.CRITICAL)
        critical_size = monitor.get_tts_batch_size()
        assert critical_size < config.base_tts_batch_size
        
        # Normal pressure - should restore
        monitor._adjust_batch_sizes(VRAMPressureLevel.NORMAL)
        normal_size = monitor.get_tts_batch_size()
        assert normal_size >= critical_size
    
    def test_monitoring_start_stop(self):
        """Test starting and stopping the monitor."""
        monitor = VRAMMonitor(total_vram_gb=16.0)
        
        monitor.start_monitoring()
        assert monitor._monitoring is True
        
        monitor.stop_monitoring()
        assert monitor._monitoring is False


@pytest.mark.skipif(not VRAM_MONITOR_AVAILABLE, reason="VRAM monitor not available")
class TestIdleTimeoutManager:
    """Tests for idle timeout manager."""
    
    def test_activity_tracking(self):
        """Test activity tracking."""
        config = IdleTimeoutConfig(
            idle_timeout_seconds=5.0,
            check_interval_seconds=0.1,
        )
        manager = IdleTimeoutManager(config=config)
        
        # Initially not idle
        manager.record_activity()
        assert manager.get_idle_time() < 1.0
        
        # Wait a bit
        time.sleep(0.2)
        assert manager.get_idle_time() >= 0.2
        
        # Record activity again
        manager.record_activity()
        assert manager.get_idle_time() < 0.1
    
    def test_model_registration(self):
        """Test model registration and unregistration."""
        manager = IdleTimeoutManager()
        
        def mock_unload():
            pass
        
        manager.register_model("test_model", mock_unload)
        manager.unregister_model("test_model")
        # Should not raise
    
    def test_idle_timeout_check_logic(self):
        """Test idle timeout check logic directly."""
        config = IdleTimeoutConfig(
            idle_timeout_seconds=0.1,
            check_interval_seconds=0.05,
            warning_before_unload_seconds=0.05,
        )
        manager = IdleTimeoutManager(config=config)
        
        unloaded = []
        def mock_unload():
            unloaded.append(True)
        
        manager.register_model("test", mock_unload)
        manager.record_activity()
        
        # Manually trigger the check with expired idle time
        manager._last_activity = time.time() - 0.2  # 0.2 seconds ago
        manager._unload_all_models()
        
        assert len(unloaded) == 1, "Unload should have been called"


@pytest.mark.skipif(not VRAM_MONITOR_AVAILABLE, reason="VRAM monitor not available")
class TestAdaptiveMemoryManager:
    """Tests for adaptive memory manager."""
    
    def test_manager_initialization(self):
        """Test manager initialization."""
        manager = AdaptiveMemoryManager(
            total_vram_gb=16.0,
            idle_timeout_seconds=300.0,
        )
        
        assert manager.vram_monitor is not None
        assert manager.idle_manager is not None
    
    def test_start_stop(self):
        """Test starting and stopping the manager."""
        manager = AdaptiveMemoryManager(total_vram_gb=16.0)
        
        manager.start()
        assert manager.vram_monitor._monitoring is True
        
        manager.stop()
        assert manager.vram_monitor._monitoring is False
    
    def test_activity_recording(self):
        """Test activity recording."""
        manager = AdaptiveMemoryManager(total_vram_gb=16.0)
        
        manager.record_activity()
        # Should not raise
    
    def test_batch_size_access(self):
        """Test batch size access methods."""
        manager = AdaptiveMemoryManager(total_vram_gb=16.0)
        
        # Should return default values
        tts_batch = manager.get_tts_batch_size()
        cleaner_batch = manager.get_cleaner_batch_size()
        
        assert tts_batch > 0
        assert cleaner_batch > 0


@pytest.mark.skipif(not BUFFER_POOL_AVAILABLE or not VRAM_MONITOR_AVAILABLE,
                    reason="Required modules not available")
class TestIntegration:
    """Integration tests for memory management features."""
    
    def test_buffer_pool_with_audio_operations(self):
        """Test buffer pool with simulated audio operations."""
        pool = get_buffer_pool(max_size_mb=64)
        pool.clear()
        
        # Simulate audio processing
        for i in range(10):
            # Acquire buffer for audio chunk
            buf = pool.acquire((24000,), np.float32)  # 1 second at 24kHz
            
            # Simulate processing
            buf.array[:] = np.sin(np.linspace(0, 2 * np.pi * 440, 24000))
            
            # Release back to pool
            buf.release()
        
        # Check stats
        stats = pool.get_stats()
        assert stats.total_allocated > 0
        assert stats.reuse_ratio > 0
    
    def test_memory_manager_integration(self):
        """Test full memory manager integration."""
        manager = get_memory_manager(total_vram_gb=16.0)
        
        # Start monitoring
        manager.start()
        
        # Simulate activity
        for _ in range(5):
            manager.record_activity()
            batch_size = manager.get_tts_batch_size()
            assert batch_size > 0
            time.sleep(0.01)
        
        # Stop monitoring
        manager.stop()
