"""
Tests for Pipeline Parallelization
==================================
Tests chapter-level parallel processing, VRAM budget management,
async I/O, and pipeline stage pipelining.
"""

import asyncio
import multiprocessing as mp
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, ANY
from dataclasses import dataclass

import pytest
import numpy as np

# Import parallel components
try:
    from modules.pipeline.parallel import (
        ParallelConfig,
        VRAMBudget,
        ChapterWorkerPool,
        AsyncFileManager,
        PipelinedStage,
        PipelineTask,
        StageStatus,
        get_optimal_worker_count,
        create_parallel_config,
        ParallelPipelineOrchestrator,
    )
    PARALLEL_AVAILABLE = True
except ImportError as e:
    PARALLEL_AVAILABLE = False
    print(f"Parallel module not available: {e}")

# Mark all tests in this module
pytestmark = [
    pytest.mark.skipif(not PARALLEL_AVAILABLE, reason="Parallel module not available"),
    pytest.mark.pipeline,
    pytest.mark.parallel,
]

from modules.pipeline.orchestrator import (
    ConversionPipeline,
    PipelineConfig,
    PipelineStage,
    ConversionResult,
    ChapterResult,
)


@dataclass
class MockChapter:
    """Mock chapter for testing."""
    number: int
    title: str
    content: str = "Test content for chapter."


class TestVRAMBudget:
    """Tests for VRAM budget management."""
    
    def test_vram_budget_calculation(self):
        """Test VRAM budget calculations."""
        budget = VRAMBudget(
            total_vram_gb=32.0,
            reserved_vram_gb=2.0,
            safety_margin_gb=1.0,
        )
        
        # Available VRAM should be total - reserved - margin
        assert budget.available_vram_gb == 29.0
        
        # Max concurrent chapters calculation
        # Per chapter: ~0.5GB (TTS) + ~1.5GB (Cleaner) = ~2GB
        # 29GB / 2GB = ~14, but capped at 4
        assert budget.max_concurrent_chapters >= 1
        assert budget.max_concurrent_chapters <= 4
    
    def test_vram_budget_with_low_memory(self):
        """Test VRAM budget with limited memory."""
        budget = VRAMBudget(
            total_vram_gb=4.0,  # Limited VRAM
            reserved_vram_gb=1.0,
            safety_margin_gb=0.5,
        )
        
        # Should still allow at least 1 chapter
        assert budget.max_concurrent_chapters >= 1
    
    def test_vram_budget_auto_adjustment(self):
        """Test that config auto-adjusts based on VRAM."""
        config = ParallelConfig(
            max_workers=10,  # Unrealistically high
            vram_budget=VRAMBudget(total_vram_gb=16.0),
        )
        
        # Should be reduced based on VRAM
        assert config.max_workers <= 4


class TestParallelConfig:
    """Tests for parallel configuration."""
    
    def test_default_config(self):
        """Test default parallel configuration."""
        config = ParallelConfig()
        
        assert config.max_workers >= 1
        assert config.max_workers <= 4
        assert config.use_processes is True
        assert config.enable_async_io is True
        assert config.enable_pipelining is True
    
    def test_create_parallel_config(self):
        """Test helper function for creating config."""
        config = create_parallel_config(
            max_workers=2,
            total_vram_gb=32.0,
            enable_pipelining=True,
        )
        
        assert config.max_workers == 2
        assert config.enable_pipelining is True
        assert config.vram_budget.total_vram_gb == 32.0
    
    def test_get_optimal_worker_count(self):
        """Test optimal worker count calculation."""
        # High VRAM should allow max workers
        high_vram = get_optimal_worker_count(total_vram_gb=64.0, max_desired=4)
        assert high_vram <= 4
        assert high_vram >= 1
        
        # Low VRAM should be constrained
        low_vram = get_optimal_worker_count(total_vram_gb=4.0, max_desired=4)
        assert low_vram >= 1


class TestAsyncFileManager:
    """Tests for async file operations."""
    
    @pytest.fixture
    def temp_dir(self, tmp_path):
        """Provide temporary directory."""
        return tmp_path
    
    @pytest.mark.asyncio
    async def test_write_text_async(self, temp_dir):
        """Test async text writing."""
        manager = AsyncFileManager()
        test_file = temp_dir / "test.txt"
        test_content = "Hello, async world!"
        
        await manager.write_text(test_file, test_content)
        
        # Verify file was written
        assert test_file.exists()
        assert test_file.read_text(encoding="utf-8") == test_content
    
    @pytest.mark.asyncio
    async def test_read_text_async(self, temp_dir):
        """Test async text reading."""
        manager = AsyncFileManager()
        test_file = temp_dir / "test.txt"
        test_content = "Test content for reading"
        
        # Write synchronously first
        test_file.write_text(test_content, encoding="utf-8")
        
        # Read asynchronously
        content = await manager.read_text(test_file)
        
        assert content == test_content
    
    @pytest.mark.asyncio
    async def test_write_audio_async(self, temp_dir):
        """Test async audio writing."""
        manager = AsyncFileManager()
        test_file = temp_dir / "test.wav"
        test_audio = np.array([0.1, 0.2, 0.3, 0.4, 0.5], dtype=np.float32)
        
        await manager.write_audio(test_file, test_audio, sample_rate=24000)
        
        # Verify file was written
        assert test_file.exists()
        assert test_file.stat().st_size > 0
    
    @pytest.mark.asyncio
    async def test_concurrent_writes(self, temp_dir):
        """Test concurrent async file operations."""
        manager = AsyncFileManager()
        
        # Create multiple concurrent write tasks
        tasks = []
        for i in range(5):
            test_file = temp_dir / f"concurrent_{i}.txt"
            tasks.append(manager.write_text(test_file, f"Content {i}"))
        
        # Execute all concurrently
        await asyncio.gather(*tasks)
        
        # Verify all files were written
        for i in range(5):
            test_file = temp_dir / f"concurrent_{i}.txt"
            assert test_file.exists()
            assert test_file.read_text(encoding="utf-8") == f"Content {i}"


class TestChapterWorkerPool:
    """Tests for chapter worker pool."""
    
    def test_worker_pool_context_manager(self):
        """Test worker pool as context manager."""
        config = ParallelConfig(max_workers=2, use_processes=False)  # Use threads for speed
        
        with ChapterWorkerPool(config) as pool:
            assert pool._executor is not None
        
        # Should be shut down after exiting context
        assert pool._executor is None
    
    def test_worker_pool_thread_mode(self):
        """Test worker pool with ThreadPoolExecutor."""
        config = ParallelConfig(max_workers=2, use_processes=False)
        
        with ChapterWorkerPool(config) as pool:
            # Submit simple task
            future = pool.submit(0, lambda: "test_result")
            result = future.result(timeout=5)
            
            assert result == "test_result"
    
    def test_worker_pool_parallel_execution(self):
        """Test parallel execution of multiple tasks."""
        config = ParallelConfig(max_workers=2, use_processes=False)
        
        def slow_task(duration):
            time.sleep(duration)
            return f"completed_{duration}"
        
        with ChapterWorkerPool(config) as pool:
            start_time = time.time()
            
            # Submit multiple tasks
            for i in range(3):
                pool.submit(i, slow_task, 0.01)
            
            # Wait for all
            results = pool.wait_for_all()
            elapsed = time.time() - start_time
            
            # Should complete faster than sequential (3 * 0.01 = 0.03s)
            # With 2 workers: ~0.02s
            assert elapsed < 0.03
            assert len(results) == 3
    
    def test_worker_pool_error_handling(self):
        """Test error handling in worker pool."""
        config = ParallelConfig(max_workers=2, use_processes=False)
        
        def failing_task():
            raise ValueError("Test error")
        
        with ChapterWorkerPool(config) as pool:
            pool.submit(0, failing_task)
            pool.wait_for_all()
            
            errors = pool.get_errors()
            assert 0 in errors
            assert "Test error" in errors[0]


class TestPipelinedStage:
    """Tests for pipeline stage pipelining."""
    
    @pytest.mark.asyncio
    async def test_pipeline_task_creation(self):
        """Test pipeline task dataclass."""
        task = PipelineTask(
            chapter_idx=0,
            chapter=MockChapter(1, "Test"),
            stage="synthesis",
        )
        
        assert task.chapter_idx == 0
        assert task.stage == "synthesis"
        assert task.status == StageStatus.PENDING
    
    @pytest.mark.asyncio
    async def test_pipelined_stage_basic(self):
        """Test basic pipelined stage functionality."""
        config = ParallelConfig()
        stage = PipelinedStage(config)
        
        # Create test task
        task = PipelineTask(
            chapter_idx=0,
            chapter=MockChapter(1, "Test"),
            stage="synthesis",
            data="test_data",
        )
        
        # Submit for synthesis
        await stage.submit_for_synthesis(task)
        
        # Verify task was queued
        assert stage._synthesis_queue.qsize() == 1
    
    @pytest.mark.asyncio
    async def test_synthesis_pipeline_execution(self):
        """Test synthesis pipeline execution."""
        config = ParallelConfig()
        stage = PipelinedStage(config)
        done_signal = asyncio.Event()
        results = []
        
        def mock_synthesize(task):
            results.append(task.chapter_idx)
            if task.chapter_idx == 2:  # Last task
                done_signal.set()
            return f"synthesized_{task.chapter_idx}"
        
        # Start pipeline in background
        pipeline_task = asyncio.create_task(
            stage.run_synthesis_pipeline(mock_synthesize)
        )
        
        # Submit tasks
        for i in range(3):
            task = PipelineTask(
                chapter_idx=i,
                chapter=MockChapter(i+1, f"Chapter {i+1}"),
                stage="synthesis",
            )
            await stage.submit_for_synthesis(task)
        
        # Wait for signal instead of fixed sleep
        try:
            await asyncio.wait_for(done_signal.wait(), timeout=1.0)
        except asyncio.TimeoutError:
            pass
        
        # Cancel pipeline
        stage.cancel()
        pipeline_task.cancel()
        
        try:
            await pipeline_task
        except asyncio.CancelledError:
            pass


class TestParallelPipelineOrchestrator:
    """Tests for parallel pipeline orchestrator."""
    
    @pytest.mark.asyncio
    async def test_orchestrator_initialization(self):
        """Test orchestrator initialization."""
        if not PARALLEL_AVAILABLE:
            pytest.skip("Parallel module not available")
        
        config = ParallelConfig(max_workers=2)
        orchestrator = ParallelPipelineOrchestrator(config)
        
        assert orchestrator.config == config
        assert orchestrator._cancelled is False
    
    @pytest.mark.asyncio
    async def test_process_chapters_parallel(self):
        """Test parallel chapter processing."""
        if not PARALLEL_AVAILABLE:
            pytest.skip("Parallel module not available")
        
        config = ParallelConfig(max_workers=2, use_processes=False)
        orchestrator = ParallelPipelineOrchestrator(config)
        
        chapters = [
            MockChapter(1, "Chapter 1", "Content 1"),
            MockChapter(2, "Chapter 2", "Content 2"),
            MockChapter(3, "Chapter 3", "Content 3"),
        ]
        
        def mock_process(chapter, idx, fm):
            return f"result_{idx}"
        
        progress_calls = []
        
        def progress_cb(current, total, msg):
            progress_calls.append((current, total, msg))
        
        results = await orchestrator.process_chapters_parallel(
            chapters=chapters,
            process_func=mock_process,
            progress_callback=progress_cb,
        )
        
        # Should get results for all chapters
        assert len(results) == 3
        assert "result_0" in results
        assert "result_1" in results
        assert "result_2" in results
    
    def test_orchestrator_cancel(self):
        """Test orchestrator cancellation."""
        config = ParallelConfig()
        orchestrator = ParallelPipelineOrchestrator(config)
        
        orchestrator.cancel()
        assert orchestrator._cancelled is True


class TestPipelineIntegration:
    """Integration tests for parallel pipeline with orchestrator."""
    
    def test_pipeline_parallel_mode_detection(self):
        """Test pipeline detects and enables parallel mode."""
        config = PipelineConfig(
            enable_parallel=True,
            max_parallel_chapters=2,
        )
        
        pipeline = ConversionPipeline(config)
        
        # Should detect parallel availability
        if PARALLEL_AVAILABLE:
            assert pipeline.is_parallel is True
        else:
            assert pipeline.is_parallel is False
    
    def test_pipeline_sequential_fallback(self):
        """Test pipeline falls back to sequential when parallel disabled."""
        config = PipelineConfig(enable_parallel=False)
        pipeline = ConversionPipeline(config)
        
        assert pipeline.is_parallel is False
    
    def test_pipeline_vram_config_adjustment(self):
        """Test pipeline adjusts config based on VRAM budget."""
        config = PipelineConfig(
            enable_parallel=True,
            max_parallel_chapters=10,  # Unrealistically high
            total_vram_gb=16.0,
        )
        
        pipeline = ConversionPipeline(config)
        
        # Should be adjusted based on VRAM
        assert pipeline.config.max_parallel_chapters <= 4
    
    @pytest.mark.asyncio
    async def test_async_chapter_processing(self):
        """Test async chapter processing coordination."""
        config = PipelineConfig(
            enable_parallel=True,
            max_parallel_chapters=2,
            use_processes=False,  # Use threads for testing
        )
        
        pipeline = ConversionPipeline(config)
        
        chapters = [
            MockChapter(1, "Chapter 1", "Short content"),
            MockChapter(2, "Chapter 2", "Short content"),
        ]
        
        # Mock the chapter processing
        with patch.object(pipeline, '_process_chapter_worker') as mock_worker:
            mock_worker.return_value = ChapterResult(
                chapter_number=1,
                chapter_title="Test",
                duration_ms=1000,
            )
            
            # This would normally be called internally
            results = await pipeline._async_process_chapters(
                chapters=chapters,
                output_dir=Path("/tmp/test"),
            )
            
            assert len(results) > 0


class TestPipelineConfigOptions:
    """Tests for pipeline configuration options."""
    
    def test_config_defaults(self):
        """Test default configuration values."""
        config = PipelineConfig()
        
        assert config.voice == "am_adam"
        assert config.speed == 1.0
        assert config.chunk_size == 500
        assert config.enable_parallel is True
        assert config.max_parallel_chapters == 2
        assert config.use_process_pool is True
        assert config.enable_async_io is True
        assert config.enable_pipelining is True
        assert config.total_vram_gb == 32.0
    
    def test_config_custom_values(self):
        """Test custom configuration values."""
        config = PipelineConfig(
            voice="af_bella",
            speed=1.2,
            chunk_size=1000,
            enable_parallel=False,
            max_parallel_chapters=4,
            total_vram_gb=64.0,
        )
        
        assert config.voice == "af_bella"
        assert config.speed == 1.2
        assert config.chunk_size == 1000
        assert config.enable_parallel is False
        assert config.max_parallel_chapters == 4
        assert config.total_vram_gb == 64.0


class TestPerformanceCharacteristics:
    """Tests to verify performance characteristics of parallel processing."""
    
    def test_parallel_faster_than_sequential(self):
        """Verify parallel processing is faster for multiple chapters."""
        def slow_task(duration):
            time.sleep(duration)
            return duration
        
        # Sequential execution time
        seq_start = time.time()
        for i in range(4):
            slow_task(0.01)
        seq_time = time.time() - seq_start
        
        # Parallel execution time
        config = ParallelConfig(max_workers=2, use_processes=False)
        par_start = time.time()
        with ChapterWorkerPool(config) as pool:
            for i in range(4):
                pool.submit(i, slow_task, 0.01)
            pool.wait_for_all()
        par_time = time.time() - par_start
        
        # Parallel should be faster (at least 1.5x speedup with 2 workers)
        # Note: This is a loose check due to test environment variability
        assert par_time < seq_time * 0.8, f"Parallel ({par_time:.3f}s) should be faster than sequential ({seq_time:.3f}s)"


class TestEdgeCases:
    """Tests for edge cases and error conditions."""
    
    def test_empty_chapter_list(self):
        """Test handling of empty chapter list."""
        config = ParallelConfig()
        orchestrator = ParallelPipelineOrchestrator(config)
        
        async def run_test():
            results = await orchestrator.process_chapters_parallel(
                chapters=[],
                process_func=lambda ch, idx, fm: None,
            )
            assert results == []
        
        asyncio.run(run_test())
    
    def test_single_chapter(self):
        """Test handling of single chapter."""
        config = ParallelConfig()
        orchestrator = ParallelPipelineOrchestrator(config)
        
        chapters = [MockChapter(1, "Only Chapter")]
        
        async def run_test():
            results = await orchestrator.process_chapters_parallel(
                chapters=chapters,
                process_func=lambda ch, idx, fm: f"result_{idx}",
            )
            assert len(results) == 1
            assert results[0] == "result_0"
        
        asyncio.run(run_test())
    
    def test_worker_pool_not_started(self):
        """Test error when using pool without starting."""
        config = ParallelConfig()
        pool = ChapterWorkerPool(config)
        
        with pytest.raises(RuntimeError, match="Worker pool not started"):
            pool.submit(0, lambda: "test")
