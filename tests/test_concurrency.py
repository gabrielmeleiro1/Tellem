"""
Concurrency Module Tests
========================
Tests for background task execution, cancellation, and message queue.
"""

import pytest
import time
import threading
from pathlib import Path

from modules.concurrency import (
    BackgroundTaskManager,
    CancellationToken,
    TaskQueue,
    TaskMessage,
    TaskStatus,
    TaskResult,
    CancelledException,
    run_in_background,
    get_task_manager,
)


class TestCancellationToken:
    """Tests for CancellationToken."""
    
    def test_initial_state_not_cancelled(self):
        """Token should not be cancelled initially."""
        token = CancellationToken()
        assert not token.is_cancelled()
    
    def test_cancel_sets_flag(self):
        """cancel() should set the cancelled flag."""
        token = CancellationToken()
        token.cancel()
        assert token.is_cancelled()
    
    def test_reset_clears_flag(self):
        """reset() should clear the cancelled flag."""
        token = CancellationToken()
        token.cancel()
        token.reset()
        assert not token.is_cancelled()
    
    def test_raise_if_cancelled(self):
        """raise_if_cancelled() should raise when cancelled."""
        token = CancellationToken()
        token.cancel()
        with pytest.raises(CancelledException):
            token.raise_if_cancelled()
    
    def test_raise_if_cancelled_not_cancelled(self):
        """raise_if_cancelled() should not raise when not cancelled."""
        token = CancellationToken()
        token.raise_if_cancelled()  # Should not raise


class TestTaskQueue:
    """Tests for TaskQueue."""
    
    def test_put_and_get(self):
        """Basic put and get operations."""
        queue = TaskQueue[str]()
        queue.put("test")
        result = queue.get(timeout=1.0)
        assert result == "test"
    
    def test_get_nowait_empty(self):
        """get_nowait() returns None on empty queue."""
        queue = TaskQueue[str]()
        assert queue.get_nowait() is None
    
    def test_get_all(self):
        """get_all() returns all items."""
        queue = TaskQueue[str]()
        queue.put("a")
        queue.put("b")
        queue.put("c")
        
        items = queue.get_all()
        assert items == ["a", "b", "c"]
        assert queue.empty()
    
    def test_clear(self):
        """clear() removes all items."""
        queue = TaskQueue[str]()
        queue.put("a")
        queue.put("b")
        
        queue.clear()
        assert queue.empty()


class TestTaskMessage:
    """Tests for TaskMessage dataclass."""
    
    def test_creation(self):
        """TaskMessage should be creatable with required fields."""
        msg = TaskMessage(
            task_id="test",
            status=TaskStatus.RUNNING,
            progress=0.5,
            message="Processing"
        )
        assert msg.task_id == "test"
        assert msg.status == TaskStatus.RUNNING
        assert msg.progress == 0.5
        assert msg.message == "Processing"
    
    def test_timestamp_auto_generated(self):
        """Timestamp should be auto-generated."""
        msg = TaskMessage(task_id="test", status=TaskStatus.PENDING)
        assert msg.timestamp > 0


class TestBackgroundTaskManager:
    """Tests for BackgroundTaskManager."""
    
    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset the singleton before each test."""
        # Force reset the singleton
        BackgroundTaskManager._instance = None
        yield
        # Cleanup after test
        try:
            manager = BackgroundTaskManager()
            manager.shutdown(wait=True)
        except:
            pass
        BackgroundTaskManager._instance = None
    
    def test_singleton_pattern(self):
        """Manager should be a singleton."""
        manager1 = BackgroundTaskManager()
        manager2 = BackgroundTaskManager()
        assert manager1 is manager2
    
    def test_submit_and_complete(self):
        """Task should be submitted and complete."""
        manager = BackgroundTaskManager()
        
        def simple_task(cancel_token, progress_queue):
            return "done"
        
        manager.submit("test_task", simple_task)
        
        # Wait for completion
        time.sleep(0.5)
        
        # Check for completion message
        messages = manager.get_messages()
        statuses = [m.status for m in messages if m.task_id == "test_task"]
        assert TaskStatus.COMPLETED in statuses
    
    def test_progress_updates(self):
        """Task should send progress updates."""
        manager = BackgroundTaskManager()
        
        def progress_task(cancel_token, progress_queue):
            for i in range(3):
                progress_queue.put(TaskMessage(
                    task_id="progress_test",
                    status=TaskStatus.RUNNING,
                    progress=i / 3,
                    message=f"Step {i}"
                ))
                time.sleep(0.05)
            return "done"
        
        manager.submit("progress_test", progress_task)
        
        # Wait for completion
        time.sleep(0.5)
        
        # Should have multiple messages
        messages = manager.get_messages()
        assert len(messages) >= 3  # At least 3 progress + pending/running/complete
    
    def test_cancellation(self):
        """Task should be cancellable."""
        manager = BackgroundTaskManager()
        
        cancelled = threading.Event()
        
        def long_task(cancel_token, progress_queue):
            for i in range(100):
                if cancel_token.is_cancelled():
                    cancelled.set()
                    return "cancelled"
                time.sleep(0.01)
            return "done"
        
        manager.submit("cancel_test", long_task)
        time.sleep(0.05)  # Let it start
        
        manager.cancel("cancel_test", wait=True)
        
        assert cancelled.is_set()
    
    def test_has_running_tasks(self):
        """has_running_tasks() should reflect task state."""
        manager = BackgroundTaskManager()
        
        started = threading.Event()
        
        def slow_task(cancel_token, progress_queue):
            started.set()
            time.sleep(0.5)
            return "done"
        
        assert not manager.has_running_tasks()
        
        manager.submit("slow_task", slow_task)
        started.wait()  # Wait for task to start
        
        assert manager.has_running_tasks()
        
        # Wait for completion
        time.sleep(0.6)
        manager.get_messages()  # Process completion
        
        assert not manager.has_running_tasks()
    
    def test_cancel_nonexistent(self):
        """Cancelling nonexistent task should return False."""
        manager = BackgroundTaskManager()
        assert not manager.cancel("nonexistent")
    
    def test_exception_handling(self):
        """Exceptions should be caught and reported."""
        manager = BackgroundTaskManager()
        
        def failing_task(cancel_token, progress_queue):
            raise ValueError("Test error")
        
        manager.submit("fail_test", failing_task)
        
        # Wait for failure
        time.sleep(0.2)
        
        messages = manager.get_messages()
        fail_messages = [m for m in messages if m.task_id == "fail_test" and m.status == TaskStatus.FAILED]
        assert len(fail_messages) >= 1
        assert fail_messages[0].error is not None


class TestLargeFileSimulation:
    """Simulate large file processing to ensure concurrency works."""
    
    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset the singleton before each test."""
        BackgroundTaskManager._instance = None
        yield
        try:
            manager = BackgroundTaskManager()
            manager.shutdown(wait=True)
        except:
            pass
        BackgroundTaskManager._instance = None
    
    def test_large_data_processing(self):
        """
        Simulate processing a large file (50k+ words).
        Ensures the concurrency module can handle sustained load.
        """
        manager = BackgroundTaskManager()
        
        # Simulate 50k words in 100 chunks of ~500 words each
        TOTAL_CHUNKS = 100
        progress_values = []
        
        def process_large_file(cancel_token, progress_queue):
            for chunk_idx in range(TOTAL_CHUNKS):
                if cancel_token.is_cancelled():
                    return "cancelled"
                
                # Simulate processing time
                time.sleep(0.001)  # 1ms per chunk
                
                progress = chunk_idx / TOTAL_CHUNKS
                progress_queue.put(TaskMessage(
                    task_id="large_file",
                    status=TaskStatus.RUNNING,
                    progress=progress,
                    message=f"Processing chunk {chunk_idx + 1}/{TOTAL_CHUNKS}"
                ))
            
            return f"Processed {TOTAL_CHUNKS} chunks"
        
        manager.submit("large_file", process_large_file)
        
        # Poll for messages while running
        start_time = time.time()
        while time.time() - start_time < 5.0:  # 5 second timeout
            messages = manager.get_messages()
            for msg in messages:
                if msg.task_id == "large_file":
                    if msg.status == TaskStatus.RUNNING:
                        progress_values.append(msg.progress)
                    elif msg.status == TaskStatus.COMPLETED:
                        # Verify we got progress updates
                        assert len(progress_values) > 50, "Should have many progress updates"
                        return
            time.sleep(0.01)
        
        pytest.fail("Large file processing timed out")
    
    def test_cancellation_mid_processing(self):
        """
        Test cancellation works correctly during large file processing.
        """
        manager = BackgroundTaskManager()
        
        chunks_processed = 0
        
        def process_with_tracking(cancel_token, progress_queue):
            nonlocal chunks_processed
            for i in range(1000):
                if cancel_token.is_cancelled():
                    return "cancelled"
                chunks_processed += 1
                time.sleep(0.001)
            return "done"
        
        manager.submit("cancel_mid", process_with_tracking)
        
        # Wait for some processing
        time.sleep(0.05)
        
        # Cancel
        manager.cancel("cancel_mid", wait=True)
        
        # Should have processed some but not all
        assert chunks_processed > 0
        assert chunks_processed < 1000


class TestGetTaskManager:
    """Tests for the get_task_manager convenience function."""
    
    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset the singleton before each test."""
        BackgroundTaskManager._instance = None
        yield
        try:
            manager = get_task_manager()
            manager.shutdown(wait=True)
        except:
            pass
        BackgroundTaskManager._instance = None
    
    def test_returns_singleton(self):
        """get_task_manager should return the singleton instance."""
        manager1 = get_task_manager()
        manager2 = get_task_manager()
        assert manager1 is manager2
