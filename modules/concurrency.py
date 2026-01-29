"""
Concurrency Module
===================
Threading utilities for background task execution.
Ensures Streamlit UI remains responsive during long-running operations.
"""

from __future__ import annotations

import queue
import threading
import time
from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional, TypeVar, Generic
from functools import wraps


class TaskStatus(Enum):
    """Status of a background task."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass
class TaskMessage:
    """Message sent through the task queue for UI updates."""
    task_id: str
    status: TaskStatus
    progress: float = 0.0  # 0.0 to 1.0
    message: str = ""
    data: Any = None
    error: Optional[Exception] = None
    timestamp: float = field(default_factory=time.time)


T = TypeVar('T')


class CancellationToken:
    """
    Token for cooperative task cancellation.
    
    Tasks should periodically check is_cancelled() and exit gracefully.
    """
    
    def __init__(self):
        self._cancelled = threading.Event()
    
    def cancel(self) -> None:
        """Request cancellation."""
        self._cancelled.set()
    
    def is_cancelled(self) -> bool:
        """Check if cancellation was requested."""
        return self._cancelled.is_set()
    
    def reset(self) -> None:
        """Reset the token for reuse."""
        self._cancelled.clear()
    
    def raise_if_cancelled(self) -> None:
        """Raise CancelledException if cancellation was requested."""
        if self.is_cancelled():
            raise CancelledException("Task was cancelled")


class CancelledException(Exception):
    """Raised when a task is cancelled."""
    pass


class TaskQueue(Generic[T]):
    """
    Thread-safe queue for task communication.
    
    Used to pass messages between background threads and the UI.
    """
    
    def __init__(self, maxsize: int = 0):
        self._queue: queue.Queue[T] = queue.Queue(maxsize=maxsize)
    
    def put(self, item: T, block: bool = True, timeout: Optional[float] = None) -> None:
        """Add an item to the queue."""
        self._queue.put(item, block=block, timeout=timeout)
    
    def get(self, block: bool = True, timeout: Optional[float] = None) -> Optional[T]:
        """
        Get an item from the queue.
        
        Returns None if non-blocking and queue is empty.
        """
        try:
            return self._queue.get(block=block, timeout=timeout)
        except queue.Empty:
            return None
    
    def get_nowait(self) -> Optional[T]:
        """Get an item without blocking. Returns None if empty."""
        return self.get(block=False)
    
    def get_all(self) -> list[T]:
        """Get all available items without blocking."""
        items = []
        while True:
            item = self.get_nowait()
            if item is None:
                break
            items.append(item)
        return items
    
    def empty(self) -> bool:
        """Check if queue is empty."""
        return self._queue.empty()
    
    def qsize(self) -> int:
        """Approximate queue size."""
        return self._queue.qsize()
    
    def clear(self) -> None:
        """Clear all items from the queue."""
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break


@dataclass
class TaskResult(Generic[T]):
    """Result of a completed task."""
    task_id: str
    status: TaskStatus
    result: Optional[T] = None
    error: Optional[Exception] = None
    elapsed_time: float = 0.0


class BackgroundTaskManager:
    """
    Manages background task execution with a ThreadPoolExecutor.
    
    Provides:
    - Non-blocking task submission
    - Progress updates via message queue
    - Cooperative cancellation
    - Task status tracking
    
    Example:
        manager = BackgroundTaskManager(max_workers=2)
        
        def long_task(cancel_token, progress_queue):
            for i in range(100):
                if cancel_token.is_cancelled():
                    return
                # Do work...
                progress_queue.put(TaskMessage(
                    task_id="my_task",
                    status=TaskStatus.RUNNING,
                    progress=i / 100,
                    message=f"Processing {i}%"
                ))
            return "Done!"
        
        task_id = manager.submit("my_task", long_task)
        
        # In UI loop:
        for msg in manager.get_messages():
            update_ui(msg)
        
        # To cancel:
        manager.cancel(task_id)
    """
    
    _instance: Optional['BackgroundTaskManager'] = None
    _lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        """Singleton pattern - ensures only one manager exists."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, max_workers: int = 4):
        # Only initialize once
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._message_queue: TaskQueue[TaskMessage] = TaskQueue()
        self._tasks: dict[str, Future] = {}
        self._cancel_tokens: dict[str, CancellationToken] = {}
        self._task_lock = threading.Lock()
        self._initialized = True
    
    @property
    def message_queue(self) -> TaskQueue[TaskMessage]:
        """Get the message queue for UI updates."""
        return self._message_queue
    
    def submit(
        self,
        task_id: str,
        func: Callable[[CancellationToken, TaskQueue[TaskMessage]], T],
        *args,
        **kwargs
    ) -> str:
        """
        Submit a task for background execution.
        
        The function must accept (cancel_token, progress_queue) as first two args.
        
        Args:
            task_id: Unique identifier for this task
            func: Function to execute
            *args: Additional positional arguments for func
            **kwargs: Additional keyword arguments for func
            
        Returns:
            The task_id
        """
        with self._task_lock:
            # Cancel any existing task with same ID
            if task_id in self._tasks:
                self.cancel(task_id, wait=False)
            
            cancel_token = CancellationToken()
            self._cancel_tokens[task_id] = cancel_token
            
            # Post pending message
            self._message_queue.put(TaskMessage(
                task_id=task_id,
                status=TaskStatus.PENDING,
                message="Task queued"
            ))
            
            # Wrap function to handle lifecycle
            def wrapped():
                start_time = time.time()
                try:
                    self._message_queue.put(TaskMessage(
                        task_id=task_id,
                        status=TaskStatus.RUNNING,
                        message="Task started"
                    ))
                    
                    result = func(cancel_token, self._message_queue, *args, **kwargs)
                    
                    elapsed = time.time() - start_time
                    if cancel_token.is_cancelled():
                        self._message_queue.put(TaskMessage(
                            task_id=task_id,
                            status=TaskStatus.CANCELLED,
                            message="Task cancelled",
                            data=TaskResult(task_id, TaskStatus.CANCELLED, elapsed_time=elapsed)
                        ))
                    else:
                        self._message_queue.put(TaskMessage(
                            task_id=task_id,
                            status=TaskStatus.COMPLETED,
                            progress=1.0,
                            message="Task completed",
                            data=TaskResult(task_id, TaskStatus.COMPLETED, result=result, elapsed_time=elapsed)
                        ))
                    return result
                    
                except CancelledException:
                    elapsed = time.time() - start_time
                    self._message_queue.put(TaskMessage(
                        task_id=task_id,
                        status=TaskStatus.CANCELLED,
                        message="Task cancelled",
                        data=TaskResult(task_id, TaskStatus.CANCELLED, elapsed_time=elapsed)
                    ))
                    
                except Exception as e:
                    elapsed = time.time() - start_time
                    self._message_queue.put(TaskMessage(
                        task_id=task_id,
                        status=TaskStatus.FAILED,
                        message=f"Task failed: {str(e)}",
                        error=e,
                        data=TaskResult(task_id, TaskStatus.FAILED, error=e, elapsed_time=elapsed)
                    ))
                    raise
                
                finally:
                    with self._task_lock:
                        self._tasks.pop(task_id, None)
                        self._cancel_tokens.pop(task_id, None)
            
            future = self._executor.submit(wrapped)
            self._tasks[task_id] = future
            
        return task_id
    
    def cancel(self, task_id: str, wait: bool = False) -> bool:
        """
        Request cancellation of a task.
        
        Args:
            task_id: Task to cancel
            wait: If True, block until task finishes
            
        Returns:
            True if cancellation was requested, False if task not found
        """
        with self._task_lock:
            token = self._cancel_tokens.get(task_id)
            future = self._tasks.get(task_id)
            
        if token is None:
            return False
        
        token.cancel()
        
        if wait and future is not None:
            try:
                future.result(timeout=30)  # Wait up to 30 seconds
            except Exception:
                pass
        
        return True
    
    def cancel_all(self, wait: bool = False) -> int:
        """
        Cancel all running tasks.
        
        Returns:
            Number of tasks cancelled
        """
        with self._task_lock:
            task_ids = list(self._tasks.keys())
        
        cancelled = 0
        for task_id in task_ids:
            if self.cancel(task_id, wait=wait):
                cancelled += 1
        
        return cancelled
    
    def get_messages(self) -> list[TaskMessage]:
        """Get all pending messages from background tasks."""
        return self._message_queue.get_all()
    
    def get_task_status(self, task_id: str) -> Optional[TaskStatus]:
        """Get the current status of a task."""
        with self._task_lock:
            if task_id not in self._tasks:
                return None
            
            future = self._tasks[task_id]
            token = self._cancel_tokens.get(task_id)
            
        if future.done():
            if token and token.is_cancelled():
                return TaskStatus.CANCELLED
            try:
                future.result(timeout=0)
                return TaskStatus.COMPLETED
            except Exception:
                return TaskStatus.FAILED
        elif future.running():
            return TaskStatus.RUNNING
        else:
            return TaskStatus.PENDING
    
    def is_running(self, task_id: str) -> bool:
        """Check if a task is currently running."""
        status = self.get_task_status(task_id)
        return status in (TaskStatus.PENDING, TaskStatus.RUNNING)
    
    def has_running_tasks(self) -> bool:
        """Check if any tasks are running."""
        with self._task_lock:
            return len(self._tasks) > 0
    
    def shutdown(self, wait: bool = True) -> None:
        """
        Shutdown the executor.
        
        Args:
            wait: If True, wait for running tasks to complete
        """
        self.cancel_all(wait=False)
        self._executor.shutdown(wait=wait)
        
        # Reset singleton for potential reinitialization
        with BackgroundTaskManager._lock:
            BackgroundTaskManager._instance = None
            self._initialized = False


def run_in_background(task_id: str):
    """
    Decorator to run a function in the background.
    
    The decorated function must accept (cancel_token, progress_queue) as first two args.
    
    Example:
        @run_in_background("my_task")
        def my_long_function(cancel_token, progress_queue, arg1, arg2):
            for i in range(100):
                cancel_token.raise_if_cancelled()
                # Do work...
            return result
        
        # Calling returns immediately:
        my_long_function(arg1="value1", arg2="value2")
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            manager = BackgroundTaskManager()
            return manager.submit(task_id, func, *args, **kwargs)
        return wrapper
    return decorator


# Convenience function to get the singleton manager
def get_task_manager() -> BackgroundTaskManager:
    """Get the singleton BackgroundTaskManager instance."""
    return BackgroundTaskManager()
