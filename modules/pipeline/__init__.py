"""
Pipeline Module
================
Conversion pipeline orchestration for audiobook creation.

Supports both sequential and parallel processing modes:
- Sequential: Process chapters one by one
- Parallel: Process multiple chapters concurrently with VRAM-aware scheduling
"""

from .orchestrator import (
    ConversionPipeline,
    PipelineStage,
    PipelineConfig,
    ConversionResult,
    ChapterResult,
)

# Parallel processing components (optional)
try:
    from .parallel import (
        ParallelConfig,
        VRAMBudget,
        ChapterWorkerPool,
        AsyncFileManager,
        PipelinedStage,
        PipelineTask,
        StageStatus,
        get_optimal_worker_count,
        create_parallel_config,
    )
    _PARALLEL_AVAILABLE = True
except ImportError:
    _PARALLEL_AVAILABLE = False

__all__ = [
    # Core pipeline
    "ConversionPipeline",
    "PipelineStage",
    "PipelineConfig",
    "ConversionResult",
    "ChapterResult",
]

# Extend __all__ with parallel components if available
if _PARALLEL_AVAILABLE:
    __all__.extend([
        "ParallelConfig",
        "VRAMBudget",
        "ChapterWorkerPool",
        "AsyncFileManager",
        "PipelinedStage",
        "PipelineTask",
        "StageStatus",
        "get_optimal_worker_count",
        "create_parallel_config",
    ])
