"""
Progress Tracking Components
============================
Per-chapter progress bars and processing stage visualization.
"""

import streamlit as st
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class ProcessingStage(Enum):
    """Processing stages for status display."""
    IDLE = "idle"
    LOADING_MODEL = "loading_model"
    PARSING = "parsing"
    CLEANING = "cleaning"
    SYNTHESIZING = "synthesizing"
    ENCODING = "encoding"
    PACKAGING = "packaging"
    COMPLETE = "complete"
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass
class ChapterProgress:
    """Progress state for a single chapter."""
    name: str
    index: int
    total_chunks: int = 0
    completed_chunks: int = 0
    stage: ProcessingStage = ProcessingStage.IDLE
    error: Optional[str] = None
    
    @property
    def progress(self) -> float:
        """Returns progress as 0.0-1.0."""
        if self.total_chunks == 0:
            return 0.0
        return self.completed_chunks / self.total_chunks
    
    @property
    def is_complete(self) -> bool:
        """Returns True if chapter processing is complete."""
        return self.stage == ProcessingStage.COMPLETE
    
    @property
    def has_error(self) -> bool:
        """Returns True if chapter had an error."""
        return self.stage == ProcessingStage.ERROR


@dataclass
class ConversionProgress:
    """Overall conversion progress state."""
    chapters: list[ChapterProgress] = field(default_factory=list)
    current_chapter_idx: int = 0
    stage: ProcessingStage = ProcessingStage.IDLE
    start_time: Optional[float] = None
    eta_seconds: Optional[float] = None
    is_cancelled: bool = False
    
    @property
    def total_chapters(self) -> int:
        """Returns total number of chapters."""
        return len(self.chapters)
    
    @property
    def completed_chapters(self) -> int:
        """Returns number of completed chapters."""
        return sum(1 for ch in self.chapters if ch.is_complete)
    
    @property
    def overall_progress(self) -> float:
        """Returns overall progress as 0.0-1.0."""
        if not self.chapters:
            return 0.0
        # Weight each chapter equally
        total = sum(ch.progress for ch in self.chapters)
        return total / len(self.chapters)
    
    @property
    def current_chapter(self) -> Optional[ChapterProgress]:
        """Returns the currently processing chapter."""
        if 0 <= self.current_chapter_idx < len(self.chapters):
            return self.chapters[self.current_chapter_idx]
        return None
    
    def format_eta(self) -> str:
        """Format ETA as mm:ss or --:--."""
        if self.eta_seconds is None or self.eta_seconds < 0:
            return "--:--"
        minutes = int(self.eta_seconds // 60)
        seconds = int(self.eta_seconds % 60)
        return f"{minutes:02d}:{seconds:02d}"


def init_progress_state():
    """Initialize progress tracking in session state."""
    if "conversion_progress" not in st.session_state:
        st.session_state.conversion_progress = ConversionProgress()


def get_progress() -> ConversionProgress:
    """Get current progress from session state."""
    init_progress_state()
    return st.session_state.conversion_progress


def reset_progress():
    """Reset all progress state."""
    st.session_state.conversion_progress = ConversionProgress()


def set_chapters(chapter_names: list[str]):
    """Initialize progress with chapter list."""
    progress = get_progress()
    progress.chapters = [
        ChapterProgress(name=name, index=i)
        for i, name in enumerate(chapter_names)
    ]
    progress.current_chapter_idx = 0
    progress.stage = ProcessingStage.IDLE


def update_chapter_progress(
    chapter_idx: int,
    completed_chunks: int,
    total_chunks: int,
    stage: ProcessingStage
):
    """Update progress for a specific chapter."""
    progress = get_progress()
    if 0 <= chapter_idx < len(progress.chapters):
        ch = progress.chapters[chapter_idx]
        ch.completed_chunks = completed_chunks
        ch.total_chunks = total_chunks
        ch.stage = stage


def set_current_stage(stage: ProcessingStage):
    """Set the overall processing stage."""
    progress = get_progress()
    progress.stage = stage


def request_cancellation():
    """Request cancellation of the current conversion."""
    progress = get_progress()
    progress.is_cancelled = True
    progress.stage = ProcessingStage.CANCELLED


def is_cancelled() -> bool:
    """Check if cancellation has been requested."""
    progress = get_progress()
    return progress.is_cancelled


def clear_cancellation():
    """Clear the cancellation flag (for retrying)."""
    progress = get_progress()
    progress.is_cancelled = False
    if progress.stage == ProcessingStage.CANCELLED:
        progress.stage = ProcessingStage.IDLE


def save_progress_to_session():
    """
    Save progress state to session for persistence across page refreshes.
    Uses a serializable dict format stored in st.session_state.
    """
    progress = get_progress()
    
    # Serialize chapters
    chapters_data = []
    for ch in progress.chapters:
        chapters_data.append({
            "name": ch.name,
            "index": ch.index,
            "total_chunks": ch.total_chunks,
            "completed_chunks": ch.completed_chunks,
            "stage": ch.stage.value,
            "error": ch.error,
        })
    
    st.session_state["_progress_backup"] = {
        "chapters": chapters_data,
        "current_chapter_idx": progress.current_chapter_idx,
        "stage": progress.stage.value,
        "start_time": progress.start_time,
        "eta_seconds": progress.eta_seconds,
        "is_cancelled": progress.is_cancelled,
    }


def restore_progress_from_session() -> bool:
    """
    Restore progress state from session backup.
    Returns True if restoration was successful, False if no backup exists.
    """
    if "_progress_backup" not in st.session_state:
        return False
    
    backup = st.session_state["_progress_backup"]
    progress = get_progress()
    
    # Restore chapters
    progress.chapters = []
    for ch_data in backup.get("chapters", []):
        ch = ChapterProgress(
            name=ch_data["name"],
            index=ch_data["index"],
            total_chunks=ch_data["total_chunks"],
            completed_chunks=ch_data["completed_chunks"],
            stage=ProcessingStage(ch_data["stage"]),
            error=ch_data.get("error"),
        )
        progress.chapters.append(ch)
    
    progress.current_chapter_idx = backup.get("current_chapter_idx", 0)
    progress.stage = ProcessingStage(backup.get("stage", "idle"))
    progress.start_time = backup.get("start_time")
    progress.eta_seconds = backup.get("eta_seconds")
    progress.is_cancelled = backup.get("is_cancelled", False)
    
    return True


def clear_progress_backup():
    """Clear the saved progress backup."""
    if "_progress_backup" in st.session_state:
        del st.session_state["_progress_backup"]


def render_chapter_progress():
    """Render per-chapter progress bars in the UI."""
    progress = get_progress()
    
    if not progress.chapters:
        st.markdown("_no chapters loaded_")
        return
    
    # Overall progress bar
    st.markdown(f"**overall:** `{progress.completed_chapters}/{progress.total_chapters}` chapters")
    st.progress(progress.overall_progress)
    
    st.markdown("")
    
    # Per-chapter progress
    for ch in progress.chapters:
        # Status indicator
        if ch.has_error:
            indicator = '<span style="color: #FF4500;">✖</span>'
        elif ch.is_complete:
            indicator = '<span style="color: #00FF00;">✓</span>'
        elif ch.index == progress.current_chapter_idx:
            indicator = '<span style="color: #FFB000;">▶</span>'
        else:
            indicator = '<span style="color: #555555;">○</span>'
        
        # Chapter name (truncate if too long)
        name = ch.name[:30] + "..." if len(ch.name) > 30 else ch.name
        
        # Progress bar visualization (ASCII style to match retro theme)
        bar_width = 20
        filled = int(ch.progress * bar_width)
        bar = "█" * filled + "░" * (bar_width - filled)
        percent = int(ch.progress * 100)
        
        st.markdown(
            f"{indicator} `{ch.index + 1:02d}` {name}<br>"
            f'<span style="font-family: monospace; color: #FFB000;">[{bar}]</span> `{percent}%`',
            unsafe_allow_html=True
        )


def render_stage_indicator():
    """Render current processing stage with visual indicator."""
    progress = get_progress()
    
    stage_labels = {
        ProcessingStage.IDLE: ("○", "#555555", "idle"),
        ProcessingStage.LOADING_MODEL: ("◐", "#FFB000", "loading model"),
        ProcessingStage.PARSING: ("◐", "#FFB000", "parsing"),
        ProcessingStage.CLEANING: ("◐", "#FFB000", "cleaning text"),
        ProcessingStage.SYNTHESIZING: ("◐", "#FFB000", "synthesizing"),
        ProcessingStage.ENCODING: ("◐", "#FFB000", "encoding"),
        ProcessingStage.PACKAGING: ("◐", "#FFB000", "packaging"),
        ProcessingStage.COMPLETE: ("●", "#00FF00", "complete"),
        ProcessingStage.ERROR: ("✖", "#FF4500", "error"),
        ProcessingStage.CANCELLED: ("○", "#555555", "cancelled"),
    }
    
    icon, color, label = stage_labels.get(
        progress.stage, 
        ("○", "#555555", "unknown")
    )
    
    st.markdown(
        f'<span style="color: {color};">{icon}</span> `{label}`',
        unsafe_allow_html=True
    )
    
    # ETA display
    st.markdown(f"eta: `{progress.format_eta()}`")


def render_compact_progress():
    """Render a compact single-line progress indicator."""
    progress = get_progress()
    
    if not progress.chapters:
        return
    
    current = progress.current_chapter
    if current:
        st.markdown(
            f"**chapter {progress.current_chapter_idx + 1}/{progress.total_chapters}:** "
            f"`{current.name[:25]}...`"
        )
    
    # Single progress bar
    st.progress(progress.overall_progress)
    st.markdown(f"`{int(progress.overall_progress * 100)}%` | eta: `{progress.format_eta()}`")
