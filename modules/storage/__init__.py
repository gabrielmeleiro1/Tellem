"""
Storage Module
==============
Handles SQLite database operations and file management.

Repository Pattern:
    - IBookRepository: Abstract interface for storage
    - SQLiteRepository: Concrete SQLite implementation
    - Future: PostgreSQLRepository for production use
"""

# Legacy database class (kept for backward compatibility)
from .database import Database

# Repository Pattern
from .repository import IBookRepository
from .sqlite_repo import SQLiteRepository
from .models import (
    Book,
    BookCreate,
    BookSummary,
    BookFilters,
    Chapter,
    ChapterCreate,
    ProcessingJob,
    ProcessingStatus,
    SourceType,
    ConversionResult,
)

__all__ = [
    # Legacy
    "Database",
    # Repository Pattern
    "IBookRepository",
    "SQLiteRepository",
    # Models
    "Book",
    "BookCreate",
    "BookSummary",
    "BookFilters",
    "Chapter",
    "ChapterCreate",
    "ProcessingJob",
    "ProcessingStatus",
    "SourceType",
    "ConversionResult",
]
