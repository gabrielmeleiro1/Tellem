"""
Pipeline Parallelization Module
===============================
Implements chapter-level parallel processing and pipeline stage pipelining.

Features:
- ProcessPoolExecutor for true parallel processing (bypasses GIL)
- VRAM budget management for controlled resource usage
- Async I/O for non-blocking file operations
- Pipeline stage pipelining for overlapping compute and I/O
"""

from __future__ import annotations

import asyncio
import logging
import multiprocessing as mp
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, Future
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Optional, TypeVar, Generic
from collections import deque
import threading

import numpy as np

# Configure logging
logger = logging.getLogger(__name__)


class StageStatus(Enum):
    """Status of a pipeline stage."""
    PENDING = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()


@dataclass
class VRAMBudget:
    """VRAM budget configuration for parallel processing."""
    total_vram_gb: float = 32.0  # Total VRAM available
    reserved_vram_gb: float = 2.0  # Reserved for system/OS
    tts_model_size_gb: float = 0.5  # Kokoro-82M ~500MB
    cleaner_model_size_gb: float = 1.5  # Llama-3.2-3B ~1.5GB
    safety_margin_gb: float = 1.0  # Safety buffer
    
    @property
    def available_vram_gb(self) -> float:
        """Calculate available VRAM for processing."""
        return self.total_vram_gb - self.reserved_vram_gb - self.safety_margin_gb
    
    @property
    def max_concurrent_chapters(self) -> int:
        """Calculate max chapters that can run in parallel based on VRAM."""
        # Each chapter needs TTS + Cleaner (if both loaded)
        per_chapter_cost = self.tts_model_size_gb + self.cleaner_model_size_gb
        max_chapters = int(self.available_vram_gb / per_chapter_cost)
        return max(1, min(max_chapters, 4))  # Cap at 4 chapters


@dataclass
class ParallelConfig:
    """Configuration for parallel pipeline processing."""
    max_workers: int = 2  # Max concurrent chapters (2-4 recommended)
    use_processes: bool = True  # Use ProcessPoolExecutor (True) vs ThreadPoolExecutor (False)
    enable_async_io: bool = True  # Use aiofiles for I/O
    enable_pipelining: bool = True  # Overlap pipeline stages
    vram_budget: VRAMBudget = field(default_factory=VRAMBudget)
    chunk_queue_size: int = 4  # Max chunks in pipeline buffer
    
    def __post_init__(self):
        """Validate and adjust configuration based on VRAM budget."""
        max_vram_workers = self.vram_budget.max_concurrent_chapters
        if self.max_workers > max_vram_workers:
            logger.warning(
                f"Reducing max_workers from {self.max_workers} to {max_vram_workers} "
                f"due to VRAM constraints"
            )
            self.max_workers = max_vram_workers


@dataclass
class PipelineTask:
    """Represents a task in the pipeline."""
    chapter_idx: int
    chapter: Any  # Chapter object
    stage: str
    data: Any = None
    status: StageStatus = StageStatus.PENDING
    error: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    
    @property
    def duration(self) -> float:
        """Get task duration in seconds."""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return 0.0


T = TypeVar('T')


class AsyncFileManager:
    """Manager for async file operations using aiofiles."""
    
    def __init__(self):
        self._lock = asyncio.Lock()
        self._pending_writes: deque[asyncio.Task] = deque()
    
    async def write_audio(
        self,
        path: Path,
        audio: np.ndarray,
        sample_rate: int = 24000,
    ) -> None:
        """Write audio data asynchronously."""
        try:
            import aiofiles
            import soundfile as sf
        except ImportError:
            # Fallback to sync write
            import soundfile as sf
            sf.write(str(path), audio, sample_rate, subtype='PCM_16')
            return
        
        # Write to temp file first, then rename (atomic)
        temp_path = path.with_suffix(path.suffix + '.tmp')
        
        # Use thread pool for CPU-intensive audio encoding
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,  # Default executor
            lambda: sf.write(str(temp_path), audio, sample_rate, subtype='PCM_16')
        )
        
        # Atomic rename
        async with self._lock:
            temp_path.replace(path)
    
    async def read_text(self, path: Path) -> str:
        """Read text file asynchronously."""
        try:
            import aiofiles
            async with aiofiles.open(path, 'r', encoding='utf-8') as f:
                return await f.read()
        except ImportError:
            # Fallback to sync read
            return path.read_text(encoding='utf-8')
    
    async def write_text(self, path: Path, content: str) -> None:
        """Write text file asynchronously."""
        try:
            import aiofiles
            temp_path = path.with_suffix(path.suffix + '.tmp')
            async with aiofiles.open(temp_path, 'w', encoding='utf-8') as f:
                await f.write(content)
            temp_path.replace(path)
        except ImportError:
            # Fallback to sync write
            path.write_text(content, encoding='utf-8')
    
    async def wait_for_pending(self) -> None:
        """Wait for all pending I/O operations to complete."""
        if self._pending_writes:
            await asyncio.gather(*self._pending_writes, return_exceptions=True)
            self._pending_writes.clear()


class PipelinedStage:
    """
    Implements pipeline stage pipelining for overlapping compute and I/O.
    
    Allows starting encoding of Chapter N-1 while synthesizing Chapter N.
    """
    
    def __init__(self, config: ParallelConfig):
        self.config = config
        self._synthesis_queue: asyncio.Queue[PipelineTask] = asyncio.Queue(
            maxsize=config.chunk_queue_size
        )
        self._encoding_queue: asyncio.Queue[PipelineTask] = asyncio.Queue(
            maxsize=config.chunk_queue_size
        )
        self._completed: list[PipelineTask] = []
        self._lock = asyncio.Lock()
        self._cancelled = False
    
    async def submit_for_synthesis(self, task: PipelineTask) -> None:
        """Submit a task for synthesis stage."""
        await self._synthesis_queue.put(task)
    
    async def submit_for_encoding(self, task: PipelineTask) -> None:
        """Submit a task for encoding stage (synthesis complete)."""
        await self._encoding_queue.put(task)
    
    async def run_synthesis_pipeline(
        self,
        synthesize_func: Callable[[PipelineTask], Any],
    ) -> None:
        """Run synthesis stage with pipelining."""
        while not self._cancelled:
            try:
                task = await asyncio.wait_for(
                    self._synthesis_queue.get(),
                    timeout=1.0
                )
                if task is None:  # Poison pill
                    break
                
                task.status = StageStatus.RUNNING
                task.start_time = time.time()
                
                try:
                    result = synthesize_func(task)
                    task.data = result
                    task.status = StageStatus.COMPLETED
                    
                    # Pass to encoding queue
                    await self._encoding_queue.put(task)
                    
                except Exception as e:
                    task.status = StageStatus.FAILED
                    task.error = str(e)
                    logger.error(f"Synthesis failed for chapter {task.chapter_idx}: {e}")
                
                finally:
                    task.end_time = time.time()
                    
            except asyncio.TimeoutError:
                continue
    
    async def run_encoding_pipeline(
        self,
        encode_func: Callable[[PipelineTask], Any],
    ) -> None:
        """Run encoding stage with pipelining."""
        while not self._cancelled:
            try:
                task = await asyncio.wait_for(
                    self._encoding_queue.get(),
                    timeout=1.0
                )
                if task is None:  # Poison pill
                    break
                
                task.status = StageStatus.RUNNING
                
                try:
                    result = encode_func(task)
                    async with self._lock:
                        self._completed.append(task)
                except Exception as e:
                    logger.error(f"Encoding failed for chapter {task.chapter_idx}: {e}")
                    
            except asyncio.TimeoutError:
                continue
    
    def cancel(self) -> None:
        """Cancel pipelining."""
        self._cancelled = True


class ChapterWorkerPool:
    """
    Manages a pool of workers for parallel chapter processing.
    
    Uses ProcessPoolExecutor for true parallelism (bypasses Python GIL).
    """
    
    def __init__(self, config: ParallelConfig):
        self.config = config
        self._executor: Optional[ProcessPoolExecutor | ThreadPoolExecutor] = None
        self._futures: dict[int, Future] = {}
        self._results: dict[int, Any] = {}
        self._errors: dict[int, str] = {}
        self._lock = threading.Lock()
    
    def __enter__(self) -> ChapterWorkerPool:
        """Context manager entry."""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.shutdown()
    
    def start(self) -> None:
        """Start the worker pool."""
        mp_context = mp.get_context('spawn')  # Spawn for clean process isolation
        
        if self.config.use_processes:
            self._executor = ProcessPoolExecutor(
                max_workers=self.config.max_workers,
                mp_context=mp_context,
                initializer=_init_worker,
                initargs=(self.config.vram_budget.available_vram_gb,)
            )
            logger.info(
                f"Started ProcessPoolExecutor with {self.config.max_workers} workers"
            )
        else:
            self._executor = ThreadPoolExecutor(
                max_workers=self.config.max_workers
            )
            logger.info(
                f"Started ThreadPoolExecutor with {self.config.max_workers} workers"
            )
    
    def submit(
        self,
        chapter_idx: int,
        func: Callable[..., T],
        *args,
        **kwargs
    ) -> Future:
        """Submit a chapter for processing."""
        if self._executor is None:
            raise RuntimeError("Worker pool not started")
        
        future = self._executor.submit(func, *args, **kwargs)
        
        with self._lock:
            self._futures[chapter_idx] = future
        
        # Add callback for result collection
        future.add_done_callback(
            lambda f, idx=chapter_idx: self._on_complete(idx, f)
        )
        
        return future
    
    def _on_complete(self, chapter_idx: int, future: Future) -> None:
        """Handle chapter completion."""
        try:
            result = future.result()
            with self._lock:
                self._results[chapter_idx] = result
        except Exception as e:
            with self._lock:
                self._errors[chapter_idx] = str(e)
            logger.error(f"Chapter {chapter_idx} failed: {e}")
    
    def wait_for_all(self) -> dict[int, Any]:
        """Wait for all submitted chapters to complete."""
        with self._lock:
            futures_list = list(self._futures.values())
        
        if futures_list:
            from concurrent.futures import wait
            wait(futures_list)
        
        with self._lock:
            return dict(self._results)
    
    def shutdown(self, wait: bool = True) -> None:
        """Shutdown the worker pool."""
        if self._executor:
            self._executor.shutdown(wait=wait)
            self._executor = None
        
        with self._lock:
            self._futures.clear()
    
    def get_results(self) -> dict[int, Any]:
        """Get completed results (may be incomplete)."""
        with self._lock:
            return dict(self._results)
    
    def get_errors(self) -> dict[int, str]:
        """Get errors by chapter index."""
        with self._lock:
            return dict(self._errors)
    
    def get_active_count(self) -> int:
        """Get number of active (not yet completed) futures."""
        with self._lock:
            active = 0
            for future in self._futures.values():
                if not future.done():
                    active += 1
            return active


def _init_worker(available_vram_gb: float) -> None:
    """
    Initialize worker process.
    
    Called once per worker process in ProcessPoolExecutor.
    """
    # Set process-specific resource limits
    import signal
    signal.signal(signal.SIGINT, signal.SIG_IGN)  # Ignore Ctrl+C in workers
    
    # Configure MLX for this worker's VRAM share
    try:
        import mlx.core as mx
        # Each worker gets a fraction of available VRAM
        worker_vram = available_vram_gb / mp.cpu_count()
        # MLX doesn't have explicit VRAM limiting, but we can set environment
        import os
        os.environ['MLX_METAL_MEMORY'] = str(int(worker_vram * 0.9 * 1024 * 1024 * 1024))
    except ImportError:
        pass
    
    logger.debug(f"Worker initialized with VRAM limit: {available_vram_gb:.1f}GB")


class ParallelPipelineOrchestrator:
    """
    Orchestrates parallel pipeline execution.
    
    Combines chapter-level parallelism with stage pipelining for
    maximum throughput.
    """
    
    def __init__(self, config: Optional[ParallelConfig] = None):
        self.config = config or ParallelConfig()
        self._file_manager = AsyncFileManager()
        self._worker_pool: Optional[ChapterWorkerPool] = None
        self._cancelled = False
    
    async def process_chapters_parallel(
        self,
        chapters: list[Any],
        process_func: Callable[[Any, int, AsyncFileManager], Any],
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> list[Any]:
        """
        Process chapters in parallel with VRAM-aware scheduling.
        
        Args:
            chapters: List of chapter objects
            process_func: Function(chapter, chapter_idx, file_manager) -> result
            progress_callback: Optional callback(current, total, message)
            
        Returns:
            List of results in chapter order
        """
        total = len(chapters)
        results: list[Optional[Any]] = [None] * total
        completed = 0
        
        with ChapterWorkerPool(self.config) as pool:
            # Submit chapters up to max_workers at a time
            for i, chapter in enumerate(chapters):
                if self._cancelled:
                    break
                
                # Wait if we have too many in-flight chapters
                while pool.get_active_count() >= self.config.max_workers:
                    await asyncio.sleep(0.05)
                    if self._cancelled:
                        break
                
                # Submit chapter processing
                pool.submit(
                    i,
                    _process_chapter_wrapper,
                    chapter,
                    i,
                    process_func,
                    self.config.enable_async_io,
                )
                
                if progress_callback:
                    progress_callback(i + 1, total, f"Queued chapter {i + 1}/{total}")
            
            # Wait for completion with progress updates
            while completed < total and not self._cancelled:
                await asyncio.sleep(0.1)
                
                current_results = pool.get_results()
                new_completed = len(current_results)
                
                if new_completed > completed:
                    completed = new_completed
                    if progress_callback:
                        progress_callback(completed, total, f"Completed {completed}/{total} chapters")
            
            # Get final results
            final_results = pool.wait_for_all()
            errors = pool.get_errors()
            
            if errors:
                for idx, error in errors.items():
                    logger.error(f"Chapter {idx} error: {error}")
        
        # Convert to ordered list
        for idx in range(total):
            if idx in final_results:
                results[idx] = final_results[idx]
        
        return [r for r in results if r is not None]
    
    def cancel(self) -> None:
        """Cancel parallel processing."""
        self._cancelled = True


def _process_chapter_wrapper(
    chapter: Any,
    chapter_idx: int,
    process_func: Callable,
    use_async_io: bool,
) -> Any:
    """
    Wrapper for chapter processing in worker process.
    
    Handles process isolation and result serialization.
    """
    # Create a new event loop for async operations in this process
    if use_async_io:
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            file_manager = AsyncFileManager()
        except Exception:
            file_manager = None
    else:
        file_manager = None
    
    try:
        return process_func(chapter, chapter_idx, file_manager)
    except Exception as e:
        logger.error(f"Chapter {chapter_idx} processing failed: {e}")
        raise
    finally:
        if use_async_io and 'loop' in locals():
            loop.close()


# Convenience functions for pipeline configuration

def get_optimal_worker_count(
    total_vram_gb: float = 32.0,
    max_desired: int = 4,
) -> int:
    """
    Calculate optimal worker count based on available VRAM.
    
    Args:
        total_vram_gb: Total VRAM available in GB
        max_desired: Maximum desired workers (default 4)
        
    Returns:
        Optimal number of workers (1-4)
    """
    budget = VRAMBudget(total_vram_gb=total_vram_gb)
    return min(budget.max_concurrent_chapters, max_desired)


def create_parallel_config(
    max_workers: Optional[int] = None,
    total_vram_gb: float = 32.0,
    enable_pipelining: bool = True,
) -> ParallelConfig:
    """
    Create a parallel configuration with smart defaults.
    
    Args:
        max_workers: Max concurrent workers (auto-calculated if None)
        total_vram_gb: Total VRAM available
        enable_pipelining: Whether to enable stage pipelining
        
    Returns:
        Configured ParallelConfig
    """
    if max_workers is None:
        max_workers = get_optimal_worker_count(total_vram_gb)
    
    return ParallelConfig(
        max_workers=max_workers,
        use_processes=True,
        enable_async_io=True,
        enable_pipelining=enable_pipelining,
        vram_budget=VRAMBudget(total_vram_gb=total_vram_gb),
    )
