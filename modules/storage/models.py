"""
Storage Models
==============
Dataclasses for repository pattern data transfer objects.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from enum import Enum


class ProcessingStatus(str, Enum):
    """Processing job status values."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SourceType(str, Enum):
    """Book source file types."""
    PDF = "pdf"
    EPUB = "epub"


@dataclass
class BookCreate:
    """Data required to create a book record."""
    title: str
    source_path: str
    source_type: SourceType
    author: Optional[str] = None
    total_chapters: int = 0


@dataclass
class Book:
    """Book record with full data."""
    id: int
    title: str
    author: Optional[str]
    source_path: str
    source_type: SourceType
    total_chapters: int
    created_at: datetime
    updated_at: datetime


@dataclass
class BookSummary:
    """Lightweight book summary for library views."""
    id: int
    title: str
    author: Optional[str]
    total_chapters: int
    created_at: datetime
    completed_chapters: int = 0


@dataclass
class ChapterCreate:
    """Data required to create a chapter record."""
    book_id: int
    chapter_number: int
    title: str
    start_time_ms: Optional[int] = None
    duration_ms: Optional[int] = None
    mp3_path: Optional[str] = None


@dataclass
class Chapter:
    """Chapter record with full data."""
    id: int
    book_id: int
    chapter_number: int
    title: str
    start_time_ms: Optional[int]
    duration_ms: Optional[int]
    mp3_path: Optional[str]


@dataclass
class ProcessingJob:
    """Processing job record."""
    id: int
    book_id: int
    status: ProcessingStatus
    progress: float
    current_stage: Optional[str]
    error_message: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    book_title: Optional[str] = None
    book_author: Optional[str] = None


@dataclass
class BookFilters:
    """Filters for book queries."""
    search_query: Optional[str] = None
    source_type: Optional[SourceType] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    limit: int = 50
    offset: int = 0


@dataclass
class ConversionResult:
    """Result of a conversion operation."""
    success: bool
    book_id: Optional[int] = None
    output_path: Optional[str] = None
    total_duration_ms: int = 0
    error_message: Optional[str] = None
    chapters_completed: int = 0
    chapters_total: int = 0
