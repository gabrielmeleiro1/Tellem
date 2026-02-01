"""
Application Module
==================
Core application controller and business logic.

This module centralizes business logic that was previously
scattered in the UI layer (main.py).

Key Components:
    - AppController: Central business logic coordinator
    - AppConfig: Application configuration
    - ConversionJob: Active conversion job handle
"""

from .config import AppConfig
from .controller import AppController, ConversionJob, ConversionCallbacks

__all__ = [
    "AppConfig",
    "AppController",
    "ConversionJob",
    "ConversionCallbacks",
]
