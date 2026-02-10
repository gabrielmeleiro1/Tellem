"""
Application Controller
======================
Central controller for audiobook creator business logic.

Moves business logic out of the UI layer (main.py) to enable:
- Testability without Streamlit
- Clear separation of concerns
- Easier UI framework changes
"""

import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Callable, BinaryIO
from enum import Enum

from modules.app.config import AppConfig
from modules.storage.repository import IBookRepository
from modules.storage.sqlite_repo import SQLiteRepository
from modules.storage.models import (
    BookCreate,
    ChapterCreate,
    BookSummary,
    BookFilters,
    ProcessingJob,
    ProcessingStatus,
    SourceType,
    ConversionResult,
)
from modules.pipeline.orchestrator import ConversionPipeline, PipelineConfig
from modules.tts.factory import TTSEngineFactory
from modules.tts.strategies.base import TTSStrategy
from modules.app.events import (
    AppEvent,
    JobState,
    make_log_event,
    make_progress_event,
    make_state_event,
)


class JobStatus(Enum):
    """Conversion job status."""
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ConversionJob:
    """
    Handle for an active conversion job.
    
    Provides status checking and cancellation.
    """
    id: str
    book_id: Optional[int]
    status: JobStatus
    pipeline: Optional[ConversionPipeline] = None
    result: Optional[ConversionResult] = None
    error: Optional[str] = None
    _thread: Optional[threading.Thread] = field(default=None, repr=False)
    
    def cancel(self) -> bool:
        """
        Request cancellation of the job.
        
        Returns:
            True if cancellation was requested
        """
        if self.pipeline and self.status == JobStatus.RUNNING:
            self.pipeline.cancel()
            self.status = JobStatus.CANCELLED
            return True
        return False
    
    def is_active(self) -> bool:
        """Check if job is currently running."""
        return self.status == JobStatus.RUNNING
    
    def wait(self, timeout: Optional[float] = None) -> bool:
        """
        Wait for job to complete.
        
        Args:
            timeout: Maximum time to wait (None = forever)
            
        Returns:
            True if job completed, False if timeout
        """
        if self._thread is None:
            return True
        
        self._thread.join(timeout=timeout)
        return not self._thread.is_alive()


@dataclass
class ConversionCallbacks:
    """Callbacks for conversion progress updates."""
    on_progress: Optional[Callable[[str, float, str], None]] = None
    on_stage_change: Optional[Callable[[str], None]] = None
    on_chapter_complete: Optional[Callable[[int, int], None]] = None
    on_log: Optional[Callable[[str, str], None]] = None
    on_complete: Optional[Callable[[ConversionResult], None]] = None
    on_error: Optional[Callable[[str], None]] = None
    on_event: Optional[Callable[[AppEvent], None]] = None


class AppController:
    """
    Central controller for audiobook creator application.
    
    Responsibilities:
        - Library management (books, chapters)
        - Conversion orchestration
        - Voice preview generation
        - Processing history tracking
    
    Example:
        controller = AppController()
        
        # Start conversion
        job = controller.start_conversion(
            source_path=Path("book.pdf"),
            voice="am_adam",
            speed=1.0,
            callbacks=ConversionCallbacks(on_progress=update_ui)
        )
        
        # Check library
        books = controller.get_library_books()
        
        # Generate preview
        preview_path = controller.generate_voice_preview("am_adam", 1.0)
    """
    
    def __init__(
        self,
        config: Optional[AppConfig] = None,
        repository: Optional[IBookRepository] = None
    ):
        """
        Initialize the application controller.
        
        Args:
            config: Application configuration
            repository: Book repository (creates SQLiteRepository if None)
        """
        self.config = config or AppConfig()
        self.repository = repository or SQLiteRepository(self.config.db_path)
        
        # Active job tracking
        self._active_job: Optional[ConversionJob] = None
        self._job_lock = threading.Lock()
        
        # Cached TTS engine for previews
        self._preview_engine: Optional[TTSStrategy] = None
    
    # ==================== Library Management ====================
    
    def get_library_books(
        self,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> list[BookSummary]:
        """
        Get books from the library.
        
        Args:
            search: Optional search query
            limit: Maximum number of results
            offset: Pagination offset
            
        Returns:
            List of book summaries
        """
        filters = BookFilters(
            search_query=search,
            limit=limit,
            offset=offset
        )
        return self.repository.list_books(filters)
    
    def get_book(self, book_id: int) -> Optional[dict]:
        """
        Get full book details including chapters.
        
        Args:
            book_id: Book identifier
            
        Returns:
            Book details dict or None if not found
        """
        book = self.repository.get_book(book_id)
        if book is None:
            return None
        
        chapters = self.repository.get_chapters(book_id)
        
        return {
            "id": book.id,
            "title": book.title,
            "author": book.author,
            "source_path": book.source_path,
            "source_type": book.source_type.value,
            "total_chapters": book.total_chapters,
            "created_at": book.created_at,
            "chapters": [
                {
                    "id": ch.id,
                    "number": ch.chapter_number,
                    "title": ch.title,
                    "duration_ms": ch.duration_ms,
                    "mp3_path": ch.mp3_path,
                }
                for ch in chapters
            ]
        }
    
    def delete_book(self, book_id: int) -> bool:
        """
        Delete a book and its associated files.
        
        Args:
            book_id: Book to delete
            
        Returns:
            True if deleted, False if not found
        """
        return self.repository.delete_book(book_id)
    
    def get_library_stats(self) -> dict:
        """
        Get library statistics.
        
        Returns:
            Dict with statistics
        """
        return self.repository.get_library_stats()
    
    # ==================== Conversion ====================
    
    def start_conversion(
        self,
        source_path: Path,
        voice: str,
        speed: float,
        callbacks: Optional[ConversionCallbacks] = None,
        title: Optional[str] = None,
        author: Optional[str] = None
    ) -> ConversionJob:
        """
        Start a new conversion job.
        
        Args:
            source_path: Path to PDF or EPUB file
            voice: Voice ID for TTS
            speed: Speech speed multiplier
            callbacks: Optional progress callbacks
            title: Override book title
            author: Override author name
            
        Returns:
            ConversionJob handle
            
        Raises:
            RuntimeError: If a conversion is already running
            ValueError: If source file doesn't exist
        """
        if not source_path.exists():
            raise ValueError(f"Source file not found: {source_path}")
        
        with self._job_lock:
            if self._active_job is not None and self._active_job.is_active():
                raise RuntimeError("A conversion is already in progress")
            
            # Create job
            job_id = f"conv_{int(time.time())}"
            job = ConversionJob(
                id=job_id,
                book_id=None,
                status=JobStatus.IDLE
            )
            self._active_job = job
        
        # Run conversion in background thread
        thread = threading.Thread(
            target=self._run_conversion,
            args=(job, source_path, voice, speed, callbacks, title, author),
            daemon=True
        )
        job._thread = thread
        job.status = JobStatus.RUNNING
        thread.start()
        if callbacks and callbacks.on_event:
            callbacks.on_event(make_state_event(JobState.RUNNING, job.id, "conversion started"))
        
        return job
    
    def _run_conversion(
        self,
        job: ConversionJob,
        source_path: Path,
        voice: str,
        speed: float,
        callbacks: Optional[ConversionCallbacks],
        title: Optional[str],
        author: Optional[str]
    ):
        """
        Internal method to run conversion in background thread.
        """
        try:
            # Create pipeline config
            pipeline_config = PipelineConfig(
                voice=voice,
                speed=speed,
                output_dir=self.config.output_dir,
                temp_dir=self.config.temp_dir,
                mp3_bitrate=self.config.mp3_bitrate,
                normalize_volume=self.config.normalize_volume,
                target_dbfs=self.config.target_dbfs,
                chunk_size=self.config.chunk_size,
                enable_parallel=self.config.enable_parallel,
                max_parallel_chapters=self.config.max_parallel_chapters,
            )
            
            # Define progress callback
            def on_progress(
                stage, chapter_idx, total_chapters,
                chunk_idx, total_chunks, message, eta
            ):
                progress = 0.0
                if total_chapters > 0:
                    chapter_progress = chapter_idx / total_chapters
                    if total_chunks > 0:
                        chunk_p = chunk_idx / total_chunks
                        chapter_progress += (chunk_p / total_chapters)
                    progress = min(1.0, chapter_progress)
                
                if callbacks and callbacks.on_progress:
                    callbacks.on_progress(stage.value, progress, message or "")
                if callbacks and callbacks.on_event:
                    callbacks.on_event(make_progress_event(stage.value, progress, message or ""))
                
                if callbacks and callbacks.on_stage_change:
                    callbacks.on_stage_change(stage.value)
            
            # Define verbose callback
            def on_verbose(message: str, msg_type: str):
                if callbacks and callbacks.on_log:
                    callbacks.on_log(message, msg_type)
                if callbacks and callbacks.on_event:
                    callbacks.on_event(make_log_event(message=message, level=msg_type))
            
            # Create and run pipeline
            pipeline = ConversionPipeline(
                config=pipeline_config,
                progress_callback=on_progress,
                verbose_callback=on_verbose
            )
            job.pipeline = pipeline
            
            result = pipeline.convert(
                source_path=source_path,
                title=title,
                author=author
            )
            
            # Store result
            job.result = ConversionResult(
                success=result.success,
                output_path=str(result.output_path) if result.output_path else None,
                total_duration_ms=result.total_duration_ms,
                error_message=result.error,
                chapters_completed=len([c for c in result.chapters if not c.error]),
                chapters_total=len(result.chapters)
            )
            
            if result.success:
                job.status = JobStatus.COMPLETED
                
                # Save to library
                try:
                    source_type = SourceType(source_path.suffix.lower().lstrip("."))
                except ValueError:
                    source_type = SourceType.EPUB
                
                book = self.repository.create_book(BookCreate(
                    title=result.title,
                    author=result.author,
                    source_path=str(source_path),
                    source_type=source_type,
                    total_chapters=len(result.chapters)
                ))
                job.book_id = book.id
                
                # Save chapters
                for ch in result.chapters:
                    self.repository.create_chapter(ChapterCreate(
                        book_id=book.id,
                        chapter_number=ch.chapter_number,
                        title=ch.chapter_title,
                        duration_ms=ch.duration_ms,
                        mp3_path=str(ch.mp3_path) if ch.mp3_path else None
                    ))
                
                if callbacks and callbacks.on_complete:
                    callbacks.on_complete(job.result)
                if callbacks and callbacks.on_event:
                    callbacks.on_event(make_state_event(JobState.COMPLETED, job.id, "conversion completed"))
            else:
                job.status = JobStatus.FAILED
                job.error = result.error or "Unknown error"
                
                if callbacks and callbacks.on_error:
                    callbacks.on_error(job.error)
                if callbacks and callbacks.on_event:
                    callbacks.on_event(make_state_event(JobState.FAILED, job.id, job.error))
                    
        except Exception as e:
            job.status = JobStatus.FAILED
            job.error = str(e)
            
            if callbacks and callbacks.on_error:
                callbacks.on_error(str(e))
            if callbacks and callbacks.on_event:
                callbacks.on_event(make_state_event(JobState.FAILED, job.id, str(e)))
        
        finally:
            job.pipeline = None
    
    def get_active_job(self) -> Optional[ConversionJob]:
        """
        Get the currently active conversion job.
        
        Returns:
            Active job or None
        """
        with self._job_lock:
            return self._active_job
    
    def cancel_conversion(self) -> bool:
        """
        Cancel the active conversion.
        
        Returns:
            True if cancelled, False if no active job
        """
        with self._job_lock:
            if self._active_job and self._active_job.is_active():
                return self._active_job.cancel()
            return False
    
    # ==================== Voice Preview ====================
    
    def generate_voice_preview(
        self,
        voice: str,
        speed: float = 1.0,
        text: Optional[str] = None
    ) -> Path:
        """
        Generate a voice preview audio file.
        
        Args:
            voice: Voice ID
            speed: Speech speed
            text: Optional custom preview text
            
        Returns:
            Path to generated audio file
            
        Raises:
            ValueError: If voice not supported
            RuntimeError: If generation fails
        """
        if text is None:
            text = (
                "A few light taps upon the pane made him turn to the window. "
                "It had begun to snow again. He watched sleepily the flakes, "
                "silver and dark, falling obliquely against the lamplight."
            )
        
        # Create or reuse preview engine
        if self._preview_engine is None:
            self._preview_engine = TTSEngineFactory.create(
                self.config.tts_engine,
                quantization=self.config.tts_quantization
            )
            self._preview_engine.load()
        
        # Validate voice
        if not self._preview_engine.validate_voice(voice):
            raise ValueError(
                f"Voice '{voice}' not supported. "
                f"Available: {[v.id for v in self._preview_engine.supported_voices]}"
            )
        
        # Generate preview
        import tempfile
        import soundfile as sf
        
        audio = self._preview_engine.synthesize(text, voice, speed)
        
        # Save to temp file
        temp_file = tempfile.NamedTemporaryFile(
            suffix=".wav",
            delete=False,
            dir=self.config.temp_dir
        )
        sf.write(temp_file.name, audio, self._preview_engine.sample_rate)
        
        return Path(temp_file.name)
    
    def get_available_voices(self) -> list[dict]:
        """
        Get list of available voices.
        
        Returns:
            List of voice info dicts
        """
        engine = TTSEngineFactory.create(self.config.tts_engine)
        
        return [
            {
                "id": v.id,
                "name": v.name,
                "language": v.language,
                "gender": v.gender,
                "description": v.description,
            }
            for v in engine.supported_voices
        ]
    
    # ==================== Processing History ====================
    
    def get_processing_history(
        self,
        limit: int = 50,
        status: Optional[ProcessingStatus] = None
    ) -> list[ProcessingJob]:
        """
        Get processing history.
        
        Args:
            limit: Maximum number of records
            status: Filter by status
            
        Returns:
            List of processing jobs
        """
        return self.repository.get_processing_history(limit, status)
    
    # ==================== Cleanup ====================
    
    def cleanup(self):
        """
        Clean up resources.
        
        Call this when shutting down the application.
        """
        # Cancel any active job
        self.cancel_conversion()
        
        # Unload preview engine
        if self._preview_engine is not None:
            self._preview_engine.unload()
            self._preview_engine = None
