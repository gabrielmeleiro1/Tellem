"""
Application Module
==================
Core application controller and business logic.

This module centralizes business logic that was previously
scattered across presentation layers.

Key Components:
    - AppController: Central business logic coordinator
    - AppConfig: Application configuration
    - ConversionJob: Active conversion job handle
"""

from .config import AppConfig
from .controller import AppController, ConversionJob, ConversionCallbacks
from .events import (
    AppEvent,
    EventType,
    JobState,
    LogEvent,
    ProgressEvent,
    StateEvent,
)

__all__ = [
    "AppConfig",
    "AppController",
    "ConversionJob",
    "ConversionCallbacks",
    "AppEvent",
    "EventType",
    "JobState",
    "ProgressEvent",
    "LogEvent",
    "StateEvent",
]
