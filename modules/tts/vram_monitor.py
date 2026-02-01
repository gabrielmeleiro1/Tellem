"""
VRAM Monitor Module
===================
Real-time VRAM monitoring with dynamic batch sizing and idle timeout unloading.

Features:
- Monitor VRAM usage in real-time
- Dynamically reduce batch size when approaching limits
- Automatically unload models when idle for >5 minutes
- Thread-safe monitoring and adjustment
"""

from __future__ import annotations

import gc
import threading
import time
from dataclasses import dataclass, field
from typing import Optional, Callable, Dict, Any, TYPE_CHECKING
from enum import Enum, auto
from collections import deque
import warnings

# MLX imports
try:
    import mlx.core as mx
    MLX_AVAILABLE = True
except ImportError:
    MLX_AVAILABLE = False

if TYPE_CHECKING:
    from modules.tts.engine import TTSEngine
    from modules.tts.cleaner import TextCleaner


class VRAMPressureLevel(Enum):
    """VRAM pressure levels for adaptive batch sizing."""
    NORMAL = auto()      # < 70% usage
    ELEVATED = auto()    # 70-85% usage - slight reduction
    HIGH = auto()        # 85-95% usage - significant reduction
    CRITICAL = auto()    # > 95% usage - emergency measures


@dataclass
class VRAMSnapshot:
    """Snapshot of VRAM usage at a point in time."""
    timestamp: float
    active_bytes: int
    peak_bytes: int
    cache_bytes: int
    
    @property
    def active_mb(self) -> float:
        return self.active_bytes / (1024 * 1024)
    
    @property
    def peak_mb(self) -> float:
        return self.peak_bytes / (1024 * 1024)
    
    @property
    def cache_mb(self) -> float:
        return self.cache_bytes / (1024 * 1024)


@dataclass
class DynamicBatchConfig:
    """Configuration for dynamic batch sizing."""
    # Base batch sizes
    base_tts_batch_size: int = 4
    base_cleaner_batch_size: int = 8
    
    # VRAM thresholds (as percentage of available)
    elevated_threshold: float = 0.70
    high_threshold: float = 0.85
    critical_threshold: float = 0.95
    
    # Batch size multipliers at each level
    elevated_multiplier: float = 0.75
    high_multiplier: float = 0.50
    critical_multiplier: float = 0.25
    
    # Minimum batch sizes
    min_tts_batch_size: int = 1
    min_cleaner_batch_size: int = 2
    
    # Monitoring interval
    check_interval_seconds: float = 2.0
    
    # History for trend analysis
    history_size: int = 10


@dataclass
class IdleTimeoutConfig:
    """Configuration for idle timeout management."""
    idle_timeout_seconds: float = 300.0  # 5 minutes
    check_interval_seconds: float = 30.0
    warning_before_unload_seconds: float = 60.0  # Warn 1 min before


class VRAMMonitor:
    """
    Real-time VRAM monitor with dynamic batch sizing.
    
    Continuously monitors VRAM usage and adjusts batch sizes
    dynamically based on available memory.
    
    Example:
        monitor = VRAMMonitor(total_vram_gb=16.0)
        monitor.start_monitoring()
        
        # Get current batch size (auto-adjusted based on VRAM)
        batch_size = monitor.get_tts_batch_size()
        
        monitor.stop_monitoring()
    """
    
    _instance: Optional[VRAMMonitor] = None
    _instance_lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        """Singleton pattern for global monitor."""
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(
        self,
        total_vram_gb: float = 32.0,
        reserved_vram_gb: float = 2.0,
        config: Optional[DynamicBatchConfig] = None,
    ):
        # Only initialize once
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        self.total_vram_bytes = int(total_vram_gb * 1024 * 1024 * 1024)
        self.reserved_vram_bytes = int(reserved_vram_gb * 1024 * 1024 * 1024)
        self.available_vram_bytes = self.total_vram_bytes - self.reserved_vram_bytes
        self.config = config or DynamicBatchConfig()
        
        # Current batch sizes (dynamically adjusted)
        self._current_tts_batch_size = self.config.base_tts_batch_size
        self._current_cleaner_batch_size = self.config.base_cleaner_batch_size
        
        # Monitoring state
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        
        # VRAM history for trend analysis
        self._history: deque[VRAMSnapshot] = deque(maxlen=self.config.history_size)
        self._history_lock = threading.Lock()
        
        # Current pressure level
        self._pressure_level = VRAMPressureLevel.NORMAL
        self._pressure_lock = threading.Lock()
        
        # Callbacks for pressure level changes
        self._pressure_callbacks: list[Callable[[VRAMPressureLevel, VRAMPressureLevel], None]] = []
        
        self._initialized = True
    
    def start_monitoring(self) -> None:
        """Start the VRAM monitoring thread."""
        if self._monitoring:
            return
        
        self._stop_event.clear()
        self._monitoring = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
    
    def stop_monitoring(self) -> None:
        """Stop the VRAM monitoring thread."""
        if not self._monitoring:
            return
        
        self._stop_event.set()
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5.0)
    
    def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while not self._stop_event.is_set():
            try:
                self._check_vram()
            except Exception as e:
                warnings.warn(f"VRAM monitoring error: {e}")
            
            self._stop_event.wait(self.config.check_interval_seconds)
    
    def _check_vram(self) -> None:
        """Check VRAM usage and adjust batch sizes."""
        if not MLX_AVAILABLE:
            return
        
        try:
            # Get current VRAM stats
            active = mx.get_active_memory()
            peak = mx.get_peak_memory()
            cache = mx.get_cache_memory()
            
            snapshot = VRAMSnapshot(
                timestamp=time.time(),
                active_bytes=active,
                peak_bytes=peak,
                cache_bytes=cache,
            )
            
            with self._history_lock:
                self._history.append(snapshot)
            
            # Calculate usage ratio
            usage_ratio = active / self.available_vram_bytes if self.available_vram_bytes > 0 else 0
            
            # Determine pressure level
            new_level = self._calculate_pressure_level(usage_ratio)
            
            with self._pressure_lock:
                old_level = self._pressure_level
                if new_level != old_level:
                    self._pressure_level = new_level
                    self._adjust_batch_sizes(new_level)
                    self._notify_pressure_change(old_level, new_level)
                    
        except Exception:
            pass  # Silently ignore MLX errors
    
    def _calculate_pressure_level(self, usage_ratio: float) -> VRAMPressureLevel:
        """Calculate VRAM pressure level from usage ratio."""
        if usage_ratio >= self.config.critical_threshold:
            return VRAMPressureLevel.CRITICAL
        elif usage_ratio >= self.config.high_threshold:
            return VRAMPressureLevel.HIGH
        elif usage_ratio >= self.config.elevated_threshold:
            return VRAMPressureLevel.ELEVATED
        return VRAMPressureLevel.NORMAL
    
    def _adjust_batch_sizes(self, level: VRAMPressureLevel) -> None:
        """Adjust batch sizes based on pressure level."""
        if level == VRAMPressureLevel.NORMAL:
            multiplier = 1.0
        elif level == VRAMPressureLevel.ELEVATED:
            multiplier = self.config.elevated_multiplier
        elif level == VRAMPressureLevel.HIGH:
            multiplier = self.config.high_multiplier
        else:  # CRITICAL
            multiplier = self.config.critical_multiplier
        
        # Calculate new batch sizes
        new_tts_size = max(
            self.config.min_tts_batch_size,
            int(self.config.base_tts_batch_size * multiplier)
        )
        new_cleaner_size = max(
            self.config.min_cleaner_batch_size,
            int(self.config.base_cleaner_batch_size * multiplier)
        )
        
        self._current_tts_batch_size = new_tts_size
        self._current_cleaner_batch_size = new_cleaner_size
        
        # Force garbage collection on high/critical
        if level in (VRAMPressureLevel.HIGH, VRAMPressureLevel.CRITICAL):
            gc.collect()
            if MLX_AVAILABLE:
                try:
                    mx.clear_cache()
                except Exception:
                    pass
    
    def _notify_pressure_change(
        self,
        old_level: VRAMPressureLevel,
        new_level: VRAMPressureLevel,
    ) -> None:
        """Notify callbacks of pressure level change."""
        for callback in self._pressure_callbacks:
            try:
                callback(old_level, new_level)
            except Exception:
                pass
    
    def on_pressure_change(
        self,
        callback: Callable[[VRAMPressureLevel, VRAMPressureLevel], None]
    ) -> None:
        """Register a callback for pressure level changes."""
        self._pressure_callbacks.append(callback)
    
    def get_tts_batch_size(self) -> int:
        """Get current TTS batch size (dynamically adjusted)."""
        with self._pressure_lock:
            return self._current_tts_batch_size
    
    def get_cleaner_batch_size(self) -> int:
        """Get current cleaner batch size (dynamically adjusted)."""
        with self._pressure_lock:
            return self._current_cleaner_batch_size
    
    def get_pressure_level(self) -> VRAMPressureLevel:
        """Get current VRAM pressure level."""
        with self._pressure_lock:
            return self._pressure_level
    
    def get_current_usage(self) -> Optional[VRAMSnapshot]:
        """Get most recent VRAM snapshot."""
        with self._history_lock:
            return self._history[-1] if self._history else None
    
    def get_usage_trend(self) -> float:
        """
        Get VRAM usage trend (bytes/second).
        
        Returns:
            Positive means usage increasing, negative means decreasing
        """
        with self._history_lock:
            if len(self._history) < 2:
                return 0.0
            
            recent = list(self._history)[-5:]  # Last 5 samples
            if len(recent) < 2:
                return 0.0
            
            first = recent[0]
            last = recent[-1]
            time_delta = last.timestamp - first.timestamp
            
            if time_delta <= 0:
                return 0.0
            
            return (last.active_bytes - first.active_bytes) / time_delta


class IdleTimeoutManager:
    """
    Manages automatic model unloading after idle timeout.
    
    Tracks activity and automatically unloads models when idle
    for a specified duration to free VRAM.
    
    Example:
        idle_manager = IdleTimeoutManager(timeout_seconds=300)
        idle_manager.register_model("tts", tts_engine.unload_model)
        idle_manager.register_model("cleaner", cleaner.unload_model)
        idle_manager.start()
        
        # Activity is tracked automatically
        idle_manager.record_activity()
        
        # After 5 minutes of no activity, models are auto-unloaded
    """
    
    _instance: Optional[IdleTimeoutManager] = None
    _instance_lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        """Singleton pattern for global manager."""
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, timeout_seconds: float = 300.0, config: Optional[IdleTimeoutConfig] = None):
        # Only initialize once
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        self.config = config or IdleTimeoutConfig()
        self._timeout_seconds = timeout_seconds
        
        # Registered models and their unload functions
        self._models: Dict[str, Callable[[], None]] = {}
        self._models_lock = threading.Lock()
        
        # Activity tracking
        self._last_activity = time.time()
        self._activity_lock = threading.Lock()
        self._warning_issued = False
        
        # Monitoring state
        self._running = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        
        # Callbacks
        self._on_unload_callbacks: list[Callable[[], None]] = []
        self._on_warning_callbacks: list[Callable[[float], None]] = []
        
        self._initialized = True
    
    def register_model(self, name: str, unload_fn: Callable[[], None]) -> None:
        """
        Register a model for idle timeout management.
        
        Args:
            name: Model identifier
            unload_fn: Function to call to unload the model
        """
        with self._models_lock:
            self._models[name] = unload_fn
    
    def unregister_model(self, name: str) -> None:
        """Unregister a model from idle management."""
        with self._models_lock:
            self._models.pop(name, None)
    
    def record_activity(self) -> None:
        """Record activity to reset idle timer."""
        with self._activity_lock:
            self._last_activity = time.time()
            self._warning_issued = False
    
    def start(self) -> None:
        """Start the idle timeout monitoring thread."""
        if self._running:
            return
        
        self._stop_event.clear()
        self._running = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
    
    def stop(self) -> None:
        """Stop the idle timeout monitoring thread."""
        if not self._running:
            return
        
        self._stop_event.set()
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5.0)
    
    def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while not self._stop_event.is_set():
            try:
                self._check_idle_timeout()
            except Exception as e:
                warnings.warn(f"Idle timeout error: {e}")
            
            self._stop_event.wait(self.config.check_interval_seconds)
    
    def _check_idle_timeout(self) -> None:
        """Check if idle timeout has been reached."""
        with self._activity_lock:
            idle_time = time.time() - self._last_activity
        
        # Issue warning before unload
        warning_time = self._timeout_seconds - self.config.warning_before_unload_seconds
        if idle_time >= warning_time and not self._warning_issued:
            self._warning_issued = True
            time_remaining = self._timeout_seconds - idle_time
            for callback in self._on_warning_callbacks:
                try:
                    callback(time_remaining)
                except Exception:
                    pass
        
        # Unload if timeout reached
        if idle_time >= self._timeout_seconds:
            self._unload_all_models()
            # Reset activity to prevent repeated unloading
            with self._activity_lock:
                self._last_activity = time.time()
    
    def _unload_all_models(self) -> None:
        """Unload all registered models."""
        with self._models_lock:
            models = list(self._models.items())
        
        unloaded = []
        for name, unload_fn in models:
            try:
                unload_fn()
                unloaded.append(name)
            except Exception as e:
                warnings.warn(f"Failed to unload model {name}: {e}")
        
        if unloaded:
            print(f"Idle timeout: Unloaded models: {', '.join(unloaded)}")
            for callback in self._on_unload_callbacks:
                try:
                    callback()
                except Exception:
                    pass
    
    def get_idle_time(self) -> float:
        """Get current idle time in seconds."""
        with self._activity_lock:
            return time.time() - self._last_activity
    
    def on_unload(self, callback: Callable[[], None]) -> None:
        """Register callback for when models are unloaded."""
        self._on_unload_callbacks.append(callback)
    
    def on_warning(self, callback: Callable[[float], None]) -> None:
        """Register callback for idle warning (receives seconds remaining)."""
        self._on_warning_callbacks.append(callback)


class AdaptiveMemoryManager:
    """
    Combined memory manager integrating VRAM monitoring and idle timeout.
    
    Provides a unified interface for adaptive memory management.
    
    Example:
        manager = AdaptiveMemoryManager(total_vram_gb=16.0)
        manager.start()
        
        # Register models
        manager.register_for_idle_timeout("tts", tts_engine.unload_model)
        
        # Get dynamically adjusted batch sizes
        batch_size = manager.get_tts_batch_size()
        
        manager.stop()
    """
    
    def __init__(
        self,
        total_vram_gb: float = 32.0,
        idle_timeout_seconds: float = 300.0,
        dynamic_config: Optional[DynamicBatchConfig] = None,
        idle_config: Optional[IdleTimeoutConfig] = None,
    ):
        self.vram_monitor = VRAMMonitor(
            total_vram_gb=total_vram_gb,
            config=dynamic_config,
        )
        self.idle_manager = IdleTimeoutManager(
            timeout_seconds=idle_timeout_seconds,
            config=idle_config,
        )
        self._started = False
    
    def start(self) -> None:
        """Start all monitoring."""
        if self._started:
            return
        
        self.vram_monitor.start_monitoring()
        self.idle_manager.start()
        self._started = True
    
    def stop(self) -> None:
        """Stop all monitoring."""
        if not self._started:
            return
        
        self.vram_monitor.stop_monitoring()
        self.idle_manager.stop()
        self._started = False
    
    def register_for_idle_timeout(self, name: str, unload_fn: Callable[[], None]) -> None:
        """Register a model for idle timeout management."""
        self.idle_manager.register_model(name, unload_fn)
    
    def record_activity(self) -> None:
        """Record activity to reset idle timer."""
        self.idle_manager.record_activity()
    
    def get_tts_batch_size(self) -> int:
        """Get current TTS batch size (dynamically adjusted)."""
        return self.vram_monitor.get_tts_batch_size()
    
    def get_cleaner_batch_size(self) -> int:
        """Get current cleaner batch size (dynamically adjusted)."""
        return self.vram_monitor.get_cleaner_batch_size()
    
    def get_vram_pressure(self) -> VRAMPressureLevel:
        """Get current VRAM pressure level."""
        return self.vram_monitor.get_pressure_level()
    
    def get_idle_time(self) -> float:
        """Get current idle time in seconds."""
        return self.idle_manager.get_idle_time()


# Convenience function
def get_memory_manager(
    total_vram_gb: float = 32.0,
    idle_timeout_seconds: float = 300.0,
) -> AdaptiveMemoryManager:
    """Get the global adaptive memory manager instance."""
    return AdaptiveMemoryManager(
        total_vram_gb=total_vram_gb,
        idle_timeout_seconds=idle_timeout_seconds,
    )


# Test functions
def test_vram_monitor():
    """Test VRAM monitor functionality."""
    print("Testing VRAMMonitor...")
    
    monitor = VRAMMonitor(total_vram_gb=16.0)
    
    # Test 1: Initial state
    assert monitor.get_tts_batch_size() == monitor.config.base_tts_batch_size
    print("✓ Test 1 passed: Initial batch size correct")
    
    # Test 2: Pressure level calculation
    assert monitor._calculate_pressure_level(0.5) == VRAMPressureLevel.NORMAL
    assert monitor._calculate_pressure_level(0.75) == VRAMPressureLevel.ELEVATED
    assert monitor._calculate_pressure_level(0.90) == VRAMPressureLevel.HIGH
    assert monitor._calculate_pressure_level(0.98) == VRAMPressureLevel.CRITICAL
    print("✓ Test 2 passed: Pressure level calculation correct")
    
    # Test 3: Batch size adjustment
    monitor._adjust_batch_sizes(VRAMPressureLevel.CRITICAL)
    assert monitor.get_tts_batch_size() == monitor.config.min_tts_batch_size
    print("✓ Test 3 passed: Critical pressure reduces batch size")
    
    print("VRAMMonitor tests passed!")


def test_idle_timeout_manager():
    """Test idle timeout manager functionality."""
    print("\nTesting IdleTimeoutManager...")
    
    config = IdleTimeoutConfig(
        idle_timeout_seconds=2.0,
        check_interval_seconds=0.1,
        warning_before_unload_seconds=1.0,
    )
    
    manager = IdleTimeoutManager(config=config)
    
    # Test 1: Register and activity tracking
    unloaded = []
    def mock_unload():
        unloaded.append(True)
    
    manager.register_model("test", mock_unload)
    manager.record_activity()
    assert manager.get_idle_time() < 1.0
    print("✓ Test 1 passed: Activity tracking works")
    
    # Test 2: Unload callback
    manager.start()
    time.sleep(2.5)  # Wait for timeout
    manager.stop()
    
    assert len(unloaded) >= 1
    print("✓ Test 2 passed: Idle timeout triggers unload")
    
    print("IdleTimeoutManager tests passed!")


if __name__ == "__main__":
    test_vram_monitor()
    test_idle_timeout_manager()
    print("\nAll VRAM monitor tests passed!")
