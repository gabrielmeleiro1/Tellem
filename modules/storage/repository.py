"""
Repository Pattern Interface
============================
Abstract base class for book storage operations.
Enables swapping storage backends (SQLite, PostgreSQL, etc.)
"""

from abc import ABC, abstractmethod
from typing import Optional

from modules.storage.models import (
    Book,
    BookCreate,
    BookSummary,
    BookFilters,
    Chapter,
    ChapterCreate,
    ProcessingJob,
    ProcessingStatus,
)


class IBookRepository(ABC):
    """
    Abstract repository interface for book storage.
    
    Implementations:
        - SQLiteRepository: Local SQLite storage (current)
        - PostgreSQLRepository: Production PostgreSQL (future)
        - MockRepository: For testing
    """
    
    # ==================== Book Operations ====================
    
    @abstractmethod
    def create_book(self, book: BookCreate) -> Book:
        """
        Create a new book record.
        
        Args:
            book: Book creation data
            
        Returns:
            Created book with assigned ID
        """
        pass
    
    @abstractmethod
    def get_book(self, book_id: int) -> Optional[Book]:
        """
        Get a book by ID.
        
        Args:
            book_id: Book identifier
            
        Returns:
            Book if found, None otherwise
        """
        pass
    
    @abstractmethod
    def get_book_by_source_path(self, source_path: str) -> Optional[Book]:
        """
        Get a book by its source file path.
        
        Args:
            source_path: Path to source file
            
        Returns:
            Book if found, None otherwise
        """
        pass
    
    @abstractmethod
    def list_books(self, filters: Optional[BookFilters] = None) -> list[BookSummary]:
        """
        List books with optional filtering.
        
        Args:
            filters: Query filters (search, date range, pagination)
            
        Returns:
            List of book summaries
        """
        pass
    
    @abstractmethod
    def update_book(self, book_id: int, **updates) -> Optional[Book]:
        """
        Update book fields.
        
        Args:
            book_id: Book to update
            **updates: Fields to update
            
        Returns:
            Updated book if found
        """
        pass
    
    @abstractmethod
    def delete_book(self, book_id: int) -> bool:
        """
        Delete a book and its chapters.
        
        Args:
            book_id: Book to delete
            
        Returns:
            True if deleted, False if not found
        """
        pass
    
    # ==================== Chapter Operations ====================
    
    @abstractmethod
    def create_chapter(self, chapter: ChapterCreate) -> Chapter:
        """
        Create a new chapter record.
        
        Args:
            chapter: Chapter creation data
            
        Returns:
            Created chapter with assigned ID
        """
        pass
    
    @abstractmethod
    def get_chapters(self, book_id: int) -> list[Chapter]:
        """
        Get all chapters for a book.
        
        Args:
            book_id: Book identifier
            
        Returns:
            List of chapters ordered by chapter_number
        """
        pass
    
    @abstractmethod
    def update_chapter(
        self,
        chapter_id: int,
        duration_ms: Optional[int] = None,
        mp3_path: Optional[str] = None
    ) -> Optional[Chapter]:
        """
        Update chapter metadata.
        
        Args:
            chapter_id: Chapter to update
            duration_ms: New duration in milliseconds
            mp3_path: New MP3 file path
            
        Returns:
            Updated chapter if found
        """
        pass
    
    # ==================== Processing Job Operations ====================
    
    @abstractmethod
    def create_job(self, book_id: int) -> ProcessingJob:
        """
        Create a new processing job.
        
        Args:
            book_id: Book to process
            
        Returns:
            Created job with assigned ID
        """
        pass
    
    @abstractmethod
    def get_job(self, job_id: int) -> Optional[ProcessingJob]:
        """
        Get a processing job by ID.
        
        Args:
            job_id: Job identifier
            
        Returns:
            Job if found, None otherwise
        """
        pass
    
    @abstractmethod
    def update_job_progress(
        self,
        job_id: int,
        progress: float,
        stage: Optional[str] = None
    ) -> bool:
        """
        Update job progress.
        
        Args:
            job_id: Job to update
            progress: Progress value 0.0-1.0
            stage: Current processing stage
            
        Returns:
            True if updated, False if not found
        """
        pass
    
    @abstractmethod
    def complete_job(self, job_id: int) -> bool:
        """
        Mark job as completed.
        
        Args:
            job_id: Job to complete
            
        Returns:
            True if updated, False if not found
        """
        pass
    
    @abstractmethod
    def fail_job(self, job_id: int, error: str) -> bool:
        """
        Mark job as failed.
        
        Args:
            job_id: Job to fail
            error: Error message
            
        Returns:
            True if updated, False if not found
        """
        pass
    
    @abstractmethod
    def get_processing_history(
        self,
        limit: int = 50,
        status: Optional[ProcessingStatus] = None
    ) -> list[ProcessingJob]:
        """
        Get recent processing history.
        
        Args:
            limit: Maximum number of records
            status: Filter by status
            
        Returns:
            List of processing jobs with book info
        """
        pass
    
    @abstractmethod
    def get_active_jobs(self) -> list[ProcessingJob]:
        """
        Get currently active (processing) jobs.
        
        Returns:
            List of active jobs
        """
        pass
    
    # ==================== Statistics ====================
    
    @abstractmethod
    def get_library_stats(self) -> dict:
        """
        Get library statistics.
        
        Returns:
            Dict with:
                - total_books: int
                - total_chapters: int
                - total_duration_ms: int
                - books_by_type: dict
        """
        pass
