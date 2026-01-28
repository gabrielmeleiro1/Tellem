"""
UI Module
=========
Custom Streamlit components and styling utilities.
"""

from .progress import (
    ProcessingStage,
    ChapterProgress,
    ConversionProgress,
    init_progress_state,
    get_progress,
    reset_progress,
    set_chapters,
    update_chapter_progress,
    set_current_stage,
    render_chapter_progress,
    render_stage_indicator,
    render_compact_progress,
)

__all__ = [
    "ProcessingStage",
    "ChapterProgress",
    "ConversionProgress",
    "init_progress_state",
    "get_progress",
    "reset_progress",
    "set_chapters",
    "update_chapter_progress",
    "set_current_stage",
    "render_chapter_progress",
    "render_stage_indicator",
    "render_compact_progress",
]
