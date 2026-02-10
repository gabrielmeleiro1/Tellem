"""
Application Event Contracts
===========================
Typed events for progress/log/state updates across CLI and TUI surfaces.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Union


class EventType(str, Enum):
    """High-level event categories."""

    PROGRESS = "progress"
    LOG = "log"
    STATE = "state"


class JobState(str, Enum):
    """Job lifecycle states."""

    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class ProgressEvent:
    """Progress update for conversion stage/chunk/chapter operations."""

    event_type: EventType
    timestamp: str
    stage: str
    progress: float
    message: str


@dataclass(frozen=True)
class LogEvent:
    """Log message emitted from the pipeline/controller."""

    event_type: EventType
    timestamp: str
    level: str
    message: str


@dataclass(frozen=True)
class StateEvent:
    """State transition event for conversion jobs."""

    event_type: EventType
    timestamp: str
    state: JobState
    job_id: str
    message: str = ""


AppEvent = Union[ProgressEvent, LogEvent, StateEvent]


def make_progress_event(stage: str, progress: float, message: str = "") -> ProgressEvent:
    """Create a normalized progress event."""
    pct = max(0.0, min(1.0, progress))
    return ProgressEvent(
        event_type=EventType.PROGRESS,
        timestamp=_now_iso(),
        stage=stage,
        progress=pct,
        message=message,
    )


def make_log_event(message: str, level: str = "info") -> LogEvent:
    """Create a normalized log event."""
    return LogEvent(
        event_type=EventType.LOG,
        timestamp=_now_iso(),
        level=level.lower(),
        message=message,
    )


def make_state_event(state: JobState, job_id: str, message: str = "") -> StateEvent:
    """Create a normalized state event."""
    return StateEvent(
        event_type=EventType.STATE,
        timestamp=_now_iso(),
        state=state,
        job_id=job_id,
        message=message,
    )
