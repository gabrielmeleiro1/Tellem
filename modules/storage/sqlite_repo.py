"""
SQLite Repository Implementation
================================
Concrete implementation of IBookRepository using SQLite.
Wraps the existing Database class to provide the repository interface.
"""

from datetime import datetime
from pathlib import Path
from typing import Optional
from contextlib import contextmanager
import sqlite3

from modules.storage.repository import IBookRepository
from modules.storage.models import (
    Book,
    BookCreate,
    BookSummary,
    BookFilters,
    Chapter,
    ChapterCreate,
    ProcessingJob,
    ProcessingStatus,
    SourceType,
)


class SQLiteRepository(IBookRepository):
    """
    SQLite implementation of the book repository interface.
    
    This wraps and extends the existing Database class to provide
    the standardized IBookRepository interface.
    """
    
    def __init__(self, db_path: Path | str = "data/audiobooks.db"):
        """
        Initialize SQLite repository.
        
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
                    status TEXT CHECK(status IN ('pending', 'processing', 'completed', 'failed', 'cancelled')) DEFAULT 'pending',
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
                CREATE INDEX IF NOT EXISTS idx_books_source_path ON books(source_path);
            """)
    
    def _row_to_book(self, row: sqlite3.Row) -> Book:
        """Convert database row to Book dataclass."""
        return Book(
            id=row["id"],
            title=row["title"],
            author=row["author"],
            source_path=row["source_path"],
            source_type=SourceType(row["source_type"]),
            total_chapters=row["total_chapters"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
    
    def _row_to_chapter(self, row: sqlite3.Row) -> Chapter:
        """Convert database row to Chapter dataclass."""
        return Chapter(
            id=row["id"],
            book_id=row["book_id"],
            chapter_number=row["chapter_number"],
            title=row["title"],
            start_time_ms=row["start_time_ms"],
            duration_ms=row["duration_ms"],
            mp3_path=row["mp3_path"],
        )
    
    def _row_to_job(self, row: sqlite3.Row) -> ProcessingJob:
        """Convert database row to ProcessingJob dataclass."""
        started_at = None
        if row["started_at"]:
            started_at = datetime.fromisoformat(row["started_at"])
        
        completed_at = None
        if row["completed_at"]:
            completed_at = datetime.fromisoformat(row["completed_at"])
        
        return ProcessingJob(
            id=row["id"],
            book_id=row["book_id"],
            status=ProcessingStatus(row["status"]),
            progress=row["progress"],
            current_stage=row["current_stage"],
            error_message=row["error_message"],
            started_at=started_at,
            completed_at=completed_at,
            book_title=row.get("title"),
            book_author=row.get("author"),
        )
    
    # ==================== Book Operations ====================
    
    def create_book(self, book: BookCreate) -> Book:
        """Create a new book record."""
        with self._connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO books (title, author, source_path, source_type, total_chapters)
                VALUES (?, ?, ?, ?, ?)
                """,
                (book.title, book.author, book.source_path, 
                 book.source_type.value, book.total_chapters)
            )
            book_id = cursor.lastrowid
            
            # Fetch the created book
            row = conn.execute(
                "SELECT * FROM books WHERE id = ?",
                (book_id,)
            ).fetchone()
            
            return self._row_to_book(row)
    
    def get_book(self, book_id: int) -> Optional[Book]:
        """Get a book by ID."""
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM books WHERE id = ?",
                (book_id,)
            ).fetchone()
            
            if row:
                return self._row_to_book(row)
            return None
    
    def get_book_by_source_path(self, source_path: str) -> Optional[Book]:
        """Get a book by its source file path."""
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM books WHERE source_path = ?",
                (source_path,)
            ).fetchone()
            
            if row:
                return self._row_to_book(row)
            return None
    
    def list_books(self, filters: Optional[BookFilters] = None) -> list[BookSummary]:
        """List books with optional filtering."""
        filters = filters or BookFilters()
        
        query = """
            SELECT b.*, COUNT(c.id) as completed_chapters
            FROM books b
            LEFT JOIN chapters c ON b.id = c.book_id
            WHERE 1=1
        """
        params = []
        
        if filters.search_query:
            query += " AND (b.title LIKE ? OR b.author LIKE ?)"
            search_pattern = f"%{filters.search_query}%"
            params.extend([search_pattern, search_pattern])
        
        if filters.source_type:
            query += " AND b.source_type = ?"
            params.append(filters.source_type.value)
        
        if filters.created_after:
            query += " AND b.created_at >= ?"
            params.append(filters.created_after.isoformat())
        
        if filters.created_before:
            query += " AND b.created_at <= ?"
            params.append(filters.created_before.isoformat())
        
        query += " GROUP BY b.id ORDER BY b.created_at DESC LIMIT ? OFFSET ?"
        params.extend([filters.limit, filters.offset])
        
        with self._connection() as conn:
            rows = conn.execute(query, params).fetchall()
            
            return [
                BookSummary(
                    id=row["id"],
                    title=row["title"],
                    author=row["author"],
                    total_chapters=row["total_chapters"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    completed_chapters=row["completed_chapters"],
                )
                for row in rows
            ]
    
    def update_book(self, book_id: int, **updates) -> Optional[Book]:
        """Update book fields."""
        allowed_fields = {"title", "author", "total_chapters"}
        filtered_updates = {k: v for k, v in updates.items() if k in allowed_fields}
        
        if not filtered_updates:
            return self.get_book(book_id)
        
        set_clause = ", ".join(f"{k} = ?" for k in filtered_updates.keys())
        set_clause += ", updated_at = CURRENT_TIMESTAMP"
        
        with self._connection() as conn:
            cursor = conn.execute(
                f"UPDATE books SET {set_clause} WHERE id = ?",
                (*filtered_updates.values(), book_id)
            )
            
            if cursor.rowcount == 0:
                return None
            
            return self.get_book(book_id)
    
    def delete_book(self, book_id: int) -> bool:
        """Delete a book and its chapters."""
        with self._connection() as conn:
            cursor = conn.execute(
                "DELETE FROM books WHERE id = ?",
                (book_id,)
            )
            return cursor.rowcount > 0
    
    # ==================== Chapter Operations ====================
    
    def create_chapter(self, chapter: ChapterCreate) -> Chapter:
        """Create a new chapter record."""
        with self._connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO chapters (book_id, chapter_number, title, start_time_ms, duration_ms, mp3_path)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (chapter.book_id, chapter.chapter_number, chapter.title,
                 chapter.start_time_ms, chapter.duration_ms, chapter.mp3_path)
            )
            chapter_id = cursor.lastrowid
            
            row = conn.execute(
                "SELECT * FROM chapters WHERE id = ?",
                (chapter_id,)
            ).fetchone()
            
            return self._row_to_chapter(row)
    
    def get_chapters(self, book_id: int) -> list[Chapter]:
        """Get all chapters for a book."""
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM chapters 
                WHERE book_id = ? 
                ORDER BY chapter_number
                """,
                (book_id,)
            ).fetchall()
            
            return [self._row_to_chapter(row) for row in rows]
    
    def update_chapter(
        self,
        chapter_id: int,
        duration_ms: Optional[int] = None,
        mp3_path: Optional[str] = None
    ) -> Optional[Chapter]:
        """Update chapter metadata."""
        updates = []
        params = []
        
        if duration_ms is not None:
            updates.append("duration_ms = ?")
            params.append(duration_ms)
        
        if mp3_path is not None:
            updates.append("mp3_path = ?")
            params.append(mp3_path)
        
        if not updates:
            with self._connection() as conn:
                row = conn.execute(
                    "SELECT * FROM chapters WHERE id = ?",
                    (chapter_id,)
                ).fetchone()
                return self._row_to_chapter(row) if row else None
        
        with self._connection() as conn:
            cursor = conn.execute(
                f"UPDATE chapters SET {', '.join(updates)} WHERE id = ?",
                (*params, chapter_id)
            )
            
            if cursor.rowcount == 0:
                return None
            
            row = conn.execute(
                "SELECT * FROM chapters WHERE id = ?",
                (chapter_id,)
            ).fetchone()
            return self._row_to_chapter(row) if row else None
    
    # ==================== Processing Job Operations ====================
    
    def create_job(self, book_id: int) -> ProcessingJob:
        """Create a new processing job."""
        with self._connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO processing_jobs (book_id, started_at)
                VALUES (?, ?)
                """,
                (book_id, datetime.now().isoformat())
            )
            job_id = cursor.lastrowid
            
            row = conn.execute(
                """
                SELECT j.*, b.title, b.author 
                FROM processing_jobs j
                JOIN books b ON j.book_id = b.id
                WHERE j.id = ?
                """,
                (job_id,)
            ).fetchone()
            
            return self._row_to_job(row)
    
    def get_job(self, job_id: int) -> Optional[ProcessingJob]:
        """Get a processing job by ID."""
        with self._connection() as conn:
            row = conn.execute(
                """
                SELECT j.*, b.title, b.author 
                FROM processing_jobs j
                LEFT JOIN books b ON j.book_id = b.id
                WHERE j.id = ?
                """,
                (job_id,)
            ).fetchone()
            
            if row:
                return self._row_to_job(row)
            return None
    
    def update_job_progress(
        self,
        job_id: int,
        progress: float,
        stage: Optional[str] = None
    ) -> bool:
        """Update job progress."""
        with self._connection() as conn:
            if stage:
                cursor = conn.execute(
                    """
                    UPDATE processing_jobs
                    SET progress = ?, current_stage = ?, status = 'processing'
                    WHERE id = ?
                    """,
                    (progress, stage, job_id)
                )
            else:
                cursor = conn.execute(
                    """
                    UPDATE processing_jobs
                    SET progress = ?, status = 'processing'
                    WHERE id = ?
                    """,
                    (progress, job_id)
                )
            return cursor.rowcount > 0
    
    def complete_job(self, job_id: int) -> bool:
        """Mark job as completed."""
        with self._connection() as conn:
            cursor = conn.execute(
                """
                UPDATE processing_jobs
                SET status = 'completed', progress = 1.0, completed_at = ?
                WHERE id = ?
                """,
                (datetime.now().isoformat(), job_id)
            )
            return cursor.rowcount > 0
    
    def fail_job(self, job_id: int, error: str) -> bool:
        """Mark job as failed."""
        with self._connection() as conn:
            cursor = conn.execute(
                """
                UPDATE processing_jobs
                SET status = 'failed', error_message = ?, completed_at = ?
                WHERE id = ?
                """,
                (error, datetime.now().isoformat(), job_id)
            )
            return cursor.rowcount > 0
    
    def get_processing_history(
        self,
        limit: int = 50,
        status: Optional[ProcessingStatus] = None
    ) -> list[ProcessingJob]:
        """Get recent processing history."""
        query = """
            SELECT j.*, b.title, b.author
            FROM processing_jobs j
            JOIN books b ON j.book_id = b.id
        """
        params = []
        
        if status:
            query += " WHERE j.status = ?"
            params.append(status.value)
        
        query += " ORDER BY j.started_at DESC LIMIT ?"
        params.append(limit)
        
        with self._connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_job(row) for row in rows]
    
    def get_active_jobs(self) -> list[ProcessingJob]:
        """Get currently active (processing) jobs."""
        return self.get_processing_history(
            limit=100,
            status=ProcessingStatus.PROCESSING
        )
    
    # ==================== Statistics ====================
    
    def get_library_stats(self) -> dict:
        """Get library statistics."""
        with self._connection() as conn:
            # Total books
            total_books = conn.execute(
                "SELECT COUNT(*) FROM books"
            ).fetchone()[0]
            
            # Total chapters
            total_chapters = conn.execute(
                "SELECT COUNT(*) FROM chapters"
            ).fetchone()[0]
            
            # Total duration
            total_duration = conn.execute(
                "SELECT COALESCE(SUM(duration_ms), 0) FROM chapters"
            ).fetchone()[0]
            
            # Books by type
            rows = conn.execute(
                """
                SELECT source_type, COUNT(*) as count 
                FROM books 
                GROUP BY source_type
                """
            ).fetchall()
            books_by_type = {row["source_type"]: row["count"] for row in rows}
            
            return {
                "total_books": total_books,
                "total_chapters": total_chapters,
                "total_duration_ms": total_duration,
                "books_by_type": books_by_type,
            }
