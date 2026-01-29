"""
Conversion Pipeline Orchestrator
=================================
Coordinates all modules for audiobook conversion:
Ingest → Chunker → TTS → Audio Processor → M4B Packager
"""

from __future__ import annotations

import time
import shutil
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Callable, Union
from enum import Enum
import numpy as np


class PipelineStage(Enum):
    """Pipeline processing stages."""
    IDLE = "idle"
    INGESTING = "ingesting"
    CHUNKING = "chunking"
    CLEANING = "cleaning"
    SYNTHESIZING = "synthesizing"
    ENCODING = "encoding"
    PACKAGING = "packaging"
    COMPLETE = "complete"
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass
class PipelineConfig:
    """Configuration for conversion pipeline."""
    voice: str = "am_adam"
    speed: float = 1.0
    output_dir: Path = field(default_factory=lambda: Path("output"))
    temp_dir: Path = field(default_factory=lambda: Path("temp"))
    mp3_bitrate: str = "128k"
    normalize_volume: bool = True
    target_dbfs: float = -16.0
    chunk_size: int = 500  # Max tokens per TTS chunk
    

@dataclass
class ChapterResult:
    """Result for a single chapter conversion."""
    chapter_number: int
    chapter_title: str
    wav_path: Optional[Path] = None
    mp3_path: Optional[Path] = None
    duration_ms: int = 0
    error: Optional[str] = None


@dataclass
class ConversionResult:
    """Result of full conversion pipeline."""
    success: bool
    title: str
    author: Optional[str]
    output_path: Optional[Path] = None
    chapters: list[ChapterResult] = field(default_factory=list)
    total_duration_ms: int = 0
    error: Optional[str] = None
    

# Type alias for progress callback
ProgressCallback = Callable[[PipelineStage, int, int, int, int, str, Optional[float]], None]
# Args: stage, chapter_idx, total_chapters, chunk_idx, total_chunks, message, eta_seconds


class ConversionPipeline:
    """
    Orchestrates the full audiobook conversion pipeline.
    
    Stages:
        1. INGESTING - Parse PDF/EPUB, extract chapters
        2. CHUNKING - Split text into TTS-sized chunks
        3. SYNTHESIZING - Generate audio per chunk
        4. ENCODING - Normalize and encode to MP3
        5. PACKAGING - Create M4B with chapters
    """
    
    def __init__(
        self,
        config: Optional[PipelineConfig] = None,
        progress_callback: Optional[ProgressCallback] = None,
    ):
        """
        Initialize the pipeline.
        
        Args:
            config: Pipeline configuration
            progress_callback: Called on progress updates
        """
        self.config = config or PipelineConfig()
        self.progress_callback = progress_callback
        
        self._stage = PipelineStage.IDLE
        self._cancelled = False
        self._start_time: Optional[float] = None
        self._chars_processed = 0
        self._total_chars = 0
        
        # Ensure directories exist
        self.config.output_dir.mkdir(parents=True, exist_ok=True)
        self.config.temp_dir.mkdir(parents=True, exist_ok=True)
    
    @property
    def stage(self) -> PipelineStage:
        """Current pipeline stage."""
        return self._stage
    
    @property
    def is_running(self) -> bool:
        """Check if pipeline is currently running."""
        return self._stage not in (
            PipelineStage.IDLE,
            PipelineStage.COMPLETE,
            PipelineStage.ERROR,
            PipelineStage.CANCELLED,
        )
    
    def cancel(self):
        """Request pipeline cancellation."""
        self._cancelled = True
    
    def _check_cancelled(self) -> bool:
        """Check if cancellation was requested."""
        if self._cancelled:
            self._stage = PipelineStage.CANCELLED
            return True
        return False
    
    def _notify_progress(
        self,
        chapter_idx: int = 0,
        total_chapters: int = 0,
        chunk_idx: int = 0,
        total_chunks: int = 0,
        message: str = "",
    ):
        """Send progress update via callback."""
        if self.progress_callback:
            self.progress_callback(
                self._stage,
                chapter_idx,
                total_chapters,
                chunk_idx,
                total_chunks,
                message,
                self.estimate_eta(),
            )
    
    def estimate_eta(self) -> Optional[float]:
        """
        Estimate remaining time in seconds.
        
        Returns:
            Estimated seconds remaining, or None if not enough data
        """
        if not self._start_time or self._chars_processed == 0:
            return None
        
        elapsed = time.time() - self._start_time
        chars_per_second = self._chars_processed / elapsed
        
        if chars_per_second <= 0:
            return None
        
        remaining_chars = self._total_chars - self._chars_processed
        return remaining_chars / chars_per_second
    
    def convert(
        self,
        source_path: Union[Path, str],
        title: Optional[str] = None,
        author: Optional[str] = None,
    ) -> ConversionResult:
        """
        Run the full conversion pipeline.
        
        Args:
            source_path: Path to PDF or EPUB file
            title: Override book title
            author: Override author name
            
        Returns:
            ConversionResult with output paths and status
        """
        source_path = Path(source_path)
        self._cancelled = False
        self._start_time = time.time()
        self._chars_processed = 0
        
        try:
            # Stage 1: Ingest
            self._stage = PipelineStage.INGESTING
            self._notify_progress(message=f"Parsing {source_path.name}...")
            
            document = self._ingest(source_path)
            if self._check_cancelled():
                return ConversionResult(success=False, title="", error="Cancelled")
            
            # Use provided or parsed title/author
            book_title = title or document.title
            book_author = author or getattr(document, 'author', None)
            
            # Calculate total characters for ETA
            self._total_chars = sum(len(ch.content) for ch in document.chapters)
            
            # Create output directory for this book
            safe_title = "".join(c if c.isalnum() or c in " -_" else "_" for c in book_title)
            book_output_dir = self.config.output_dir / safe_title
            book_output_dir.mkdir(parents=True, exist_ok=True)
            chapters_dir = book_output_dir / "chapters"
            chapters_dir.mkdir(exist_ok=True)
            
            # Stage 2-4: Process each chapter
            chapter_results: list[ChapterResult] = []
            total_chapters = len(document.chapters)
            
            for idx, chapter in enumerate(document.chapters):
                if self._check_cancelled():
                    return ConversionResult(
                        success=False,
                        title=book_title,
                        author=book_author,
                        error="Cancelled",
                    )
                
                result = self._process_chapter(
                    chapter=chapter,
                    chapter_idx=idx,
                    total_chapters=total_chapters,
                    output_dir=chapters_dir,
                )
                chapter_results.append(result)
                
                if result.error:
                    # Continue with other chapters, don't fail entire pipeline
                    pass
            
            if self._check_cancelled():
                return ConversionResult(
                    success=False,
                    title=book_title,
                    author=book_author,
                    error="Cancelled",
                )
            
            # Stage 5: Package into M4B
            self._stage = PipelineStage.PACKAGING
            self._notify_progress(
                chapter_idx=total_chapters,
                total_chapters=total_chapters,
                message="Creating M4B audiobook...",
            )
            
            m4b_path = self._package(
                chapter_results=chapter_results,
                title=book_title,
                author=book_author,
                output_dir=book_output_dir,
            )
            
            # Calculate total duration
            total_duration = sum(r.duration_ms for r in chapter_results)
            
            # Complete
            self._stage = PipelineStage.COMPLETE
            self._notify_progress(
                chapter_idx=total_chapters,
                total_chapters=total_chapters,
                message="Conversion complete!",
            )
            
            return ConversionResult(
                success=True,
                title=book_title,
                author=book_author,
                output_path=m4b_path,
                chapters=chapter_results,
                total_duration_ms=total_duration,
            )
            
        except Exception as e:
            self._stage = PipelineStage.ERROR
            return ConversionResult(
                success=False,
                title=title or "",
                author=author,
                error=str(e),
            )
        finally:
            self._cleanup_temp()
    
    def _ingest(self, source_path: Path):
        """
        Parse source file and extract document structure.
        
        Returns:
            Parsed Document object
        """
        suffix = source_path.suffix.lower()
        
        if suffix == ".epub":
            from modules.ingestion.epub_parser import EPUBParser
            parser = EPUBParser(source_path)
            return parser.parse()
        elif suffix == ".pdf":
            from modules.ingestion.pdf_parser import PDFParser
            parser = PDFParser(source_path)
            return parser.parse()
        else:
            raise ValueError(f"Unsupported file type: {suffix}")
    
    def _process_chapter(
        self,
        chapter,
        chapter_idx: int,
        total_chapters: int,
        output_dir: Path,
    ) -> ChapterResult:
        """
        Process a single chapter: chunk → synthesize → encode.
        
        Returns:
            ChapterResult with paths and status
        """
        from modules.tts.chunker import TextChunker
        from modules.tts.engine import TTSEngine
        from modules.audio.processor import AudioProcessor
        from modules.audio.encoder import AudioEncoder
        import soundfile as sf
        
        result = ChapterResult(
            chapter_number=chapter.number,
            chapter_title=chapter.title,
        )
        
        try:
            # Stage 2: Chunk text
            self._stage = PipelineStage.CHUNKING
            self._notify_progress(
                chapter_idx=chapter_idx,
                total_chapters=total_chapters,
                message=f"Chunking: {chapter.title}",
            )
            
            chunker = TextChunker(max_tokens=self.config.chunk_size)
            chunks = chunker.chunk_text(chapter.content)
            total_chunks = len(chunks)
            
            if total_chunks == 0:
                result.error = "No text content"
                return result
            
            # Stage 2.5: Clean text
            self._stage = PipelineStage.CLEANING
            from modules.tts.cleaner import TextCleaner
            
            cleaned_chunks = []
            
            # Clean chunks with progress updates
            # Use context manager to ensure model unloads if used
            with TextCleaner() as cleaner:
                for chunk_idx, chunk in enumerate(chunks):
                    if self._check_cancelled():
                        result.error = "Cancelled"
                        return result
                    
                    self._notify_progress(
                        chapter_idx=chapter_idx,
                        total_chapters=total_chapters,
                        chunk_idx=chunk_idx,
                        total_chunks=total_chunks,
                        message=f"Cleaning chunk {chunk_idx + 1}/{total_chunks}",
                    )
                    
                    cleaned_chunk = cleaner.clean(chunk)
                    cleaned_chunks.append(cleaned_chunk)
            
            chunks = cleaned_chunks
            
            # Stage 3: Synthesize each chunk
            self._stage = PipelineStage.SYNTHESIZING
            engine = TTSEngine()
            engine.load_model()
            
            chunk_audio_segments = []
            
            for chunk_idx, chunk in enumerate(chunks):
                if self._check_cancelled():
                    engine.unload_model()
                    result.error = "Cancelled"
                    return result
                
                self._notify_progress(
                    chapter_idx=chapter_idx,
                    total_chapters=total_chapters,
                    chunk_idx=chunk_idx,
                    total_chunks=total_chunks,
                    message=f"Synthesizing chunk {chunk_idx + 1}/{total_chunks}",
                )
                
                audio = engine.synthesize(
                    text=chunk,
                    voice=self.config.voice,
                    speed=self.config.speed,
                )
                chunk_audio_segments.append(audio)
                
                self._chars_processed += len(chunk)
            
            engine.unload_model()
            
            # Concatenate all chunks
            full_audio = np.concatenate(chunk_audio_segments)
            
            # Save chapter WAV to temp
            chapter_wav = self.config.temp_dir / f"chapter_{chapter.number:02d}.wav"
            sf.write(str(chapter_wav), full_audio, 24000, subtype='PCM_16')
            result.wav_path = chapter_wav
            
            # Stage 4: Encode to MP3
            self._stage = PipelineStage.ENCODING
            self._notify_progress(
                chapter_idx=chapter_idx,
                total_chapters=total_chapters,
                message=f"Encoding: {chapter.title}",
            )
            
            # Normalize volume
            if self.config.normalize_volume:
                processor = AudioProcessor()
                normalized = processor.normalize_volume(
                    processor.load_audio(chapter_wav),
                    target_dBFS=self.config.target_dbfs,
                )
                processor.save_audio(normalized, chapter_wav)
            
            # Encode to MP3
            safe_title = "".join(
                c if c.isalnum() or c in " -_" else "_" 
                for c in chapter.title
            )[:50]
            chapter_mp3 = output_dir / f"{chapter.number:02d}_{safe_title}.mp3"
            
            encoder = AudioEncoder()
            encoder.wav_to_mp3(chapter_wav, chapter_mp3, bitrate=self.config.mp3_bitrate)
            
            result.mp3_path = chapter_mp3
            result.duration_ms = int(encoder.get_duration(chapter_mp3) * 1000)
            
            return result
            
        except Exception as e:
            result.error = str(e)
            return result
    
    def _package(
        self,
        chapter_results: list[ChapterResult],
        title: str,
        author: Optional[str],
        output_dir: Path,
    ) -> Path:
        """
        Package MP3s into M4B with chapter markers.
        
        Returns:
            Path to M4B file
        """
        from modules.audio.packager import M4BPackager, AudiobookMetadata
        
        # Collect valid MP3s
        mp3_files = []
        chapter_names = []
        
        for result in chapter_results:
            if result.mp3_path and result.mp3_path.exists():
                mp3_files.append(result.mp3_path)
                chapter_names.append(result.chapter_title)
        
        if not mp3_files:
            raise RuntimeError("No valid chapter MP3s to package")
        
        # Create metadata
        metadata = AudiobookMetadata(
            title=title,
            author=author or "Unknown",
            narrator=self.config.voice,
            comment=f"Generated by Audiobook Creator",
        )
        
        # Output path
        safe_title = "".join(c if c.isalnum() or c in " -_" else "_" for c in title)
        m4b_path = output_dir / f"{safe_title}.m4b"
        
        # Package
        packager = M4BPackager()
        packager.create_m4b(
            mp3_files=mp3_files,
            chapter_names=chapter_names,
            metadata=metadata,
            output_path=m4b_path,
        )
        
        return m4b_path
    
    def _cleanup_temp(self):
        """Clean up temporary files."""
        try:
            if self.config.temp_dir.exists():
                for f in self.config.temp_dir.iterdir():
                    if f.is_file():
                        f.unlink()
        except Exception:
            pass  # Best effort cleanup
