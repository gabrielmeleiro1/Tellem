"""
SQLite Database Module
======================
Handles metadata storage for audiobooks, chapters, and processing jobs.
"""

import sqlite3
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass
from typing import Optional
from contextlib import contextmanager


@dataclass
class Book:
    """Represents a book record."""
    id: int
    title: str
    author: Optional[str]
    source_path: str
    source_type: str
    total_chapters: int
    created_at: datetime
    updated_at: datetime


@dataclass
class Chapter:
    """Represents a chapter record."""
    id: int
    book_id: int
    chapter_number: int
    title: str
    start_time_ms: Optional[int]
    duration_ms: Optional[int]
    mp3_path: Optional[str]


@dataclass
class ProcessingJob:
    """Represents a processing job record."""
    id: int
    book_id: int
    status: str
    progress: float
    current_stage: Optional[str]
    error_message: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]


class Database:
    """
    SQLite database for audiobook metadata storage.
    
    Tables:
        - books: Book metadata
        - chapters: Chapter info and audio paths
        - processing_jobs: Job status tracking
    """
    
    def __init__(self, db_path: Path | str = "data/audiobooks.db"):
        """
        Initialize database connection.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()
    
    @contextmanager
    def _connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def _init_schema(self):
        """Initialize database schema."""
        with self._connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS books (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    author TEXT,
                    source_path TEXT NOT NULL,
                    source_type TEXT CHECK(source_type IN ('pdf', 'epub')),
                    total_chapters INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS chapters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    book_id INTEGER NOT NULL,
                    chapter_number INTEGER NOT NULL,
                    title TEXT,
                    start_time_ms INTEGER,
                    duration_ms INTEGER,
                    mp3_path TEXT,
                    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
                );
                
                CREATE TABLE IF NOT EXISTS processing_jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    book_id INTEGER NOT NULL,
                    status TEXT CHECK(status IN ('pending', 'processing', 'completed', 'failed')) DEFAULT 'pending',
                    progress REAL DEFAULT 0,
                    current_stage TEXT,
                    error_message TEXT,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
                );
                
                CREATE INDEX IF NOT EXISTS idx_chapters_book_id ON chapters(book_id);
                CREATE INDEX IF NOT EXISTS idx_jobs_book_id ON processing_jobs(book_id);
                CREATE INDEX IF NOT EXISTS idx_jobs_status ON processing_jobs(status);
            """)
    
    def create_book(
        self,
        title: str,
        source_path: str,
        source_type: str,
        author: Optional[str] = None,
        total_chapters: int = 0
    ) -> int:
        """
        Create a new book record.
        
        Returns:
            Book ID
        """
        with self._connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO books (title, author, source_path, source_type, total_chapters)
                VALUES (?, ?, ?, ?, ?)
                """,
                (title, author, source_path, source_type, total_chapters)
            )
            return cursor.lastrowid
    
    def get_book(self, book_id: int) -> Optional[Book]:
        """Get a book by ID."""
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM books WHERE id = ?",
                (book_id,)
            ).fetchone()
            
            if row:
                return Book(**dict(row))
            return None
    
    def create_chapter(
        self,
        book_id: int,
        chapter_number: int,
        title: str,
        start_time_ms: Optional[int] = None,
        duration_ms: Optional[int] = None,
        mp3_path: Optional[str] = None
    ) -> int:
        """Create a new chapter record."""
        with self._connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO chapters (book_id, chapter_number, title, start_time_ms, duration_ms, mp3_path)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (book_id, chapter_number, title, start_time_ms, duration_ms, mp3_path)
            )
            return cursor.lastrowid
    
    def get_chapters(self, book_id: int) -> list[Chapter]:
        """Get all chapters for a book."""
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT * FROM chapters WHERE book_id = ? ORDER BY chapter_number",
                (book_id,)
            ).fetchall()
            return [Chapter(**dict(row)) for row in rows]
    
    def create_job(self, book_id: int) -> int:
        """Create a new processing job."""
        with self._connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO processing_jobs (book_id, started_at)
                VALUES (?, ?)
                """,
                (book_id, datetime.now())
            )
            return cursor.lastrowid
    
    def update_progress(
        self,
        job_id: int,
        progress: float,
        stage: Optional[str] = None
    ):
        """Update job progress."""
        with self._connection() as conn:
            conn.execute(
                """
                UPDATE processing_jobs
                SET progress = ?, current_stage = ?, status = 'processing'
                WHERE id = ?
                """,
                (progress, stage, job_id)
            )
    
    def complete_job(self, job_id: int):
        """Mark job as completed."""
        with self._connection() as conn:
            conn.execute(
                """
                UPDATE processing_jobs
                SET status = 'completed', progress = 1.0, completed_at = ?
                WHERE id = ?
                """,
                (datetime.now(), job_id)
            )
    
    def fail_job(self, job_id: int, error: str):
        """Mark job as failed."""
        with self._connection() as conn:
            conn.execute(
                """
                UPDATE processing_jobs
                SET status = 'failed', error_message = ?, completed_at = ?
                WHERE id = ?
                """,
                (error, datetime.now(), job_id)
            )
    
    def get_processing_history(self, limit: int = 50) -> list[dict]:
        """Get recent processing history."""
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT j.*, b.title, b.author
                FROM processing_jobs j
                JOIN books b ON j.book_id = b.id
                ORDER BY j.started_at DESC
                LIMIT ?
                """,
                (limit,)
            ).fetchall()
            return [dict(row) for row in rows]
