"""
Conversion Pipeline Orchestrator
=================================
Coordinates all modules for audiobook conversion:
Ingest → Chunker → TTS → Audio Processor → M4B Packager

Supports both sequential and parallel processing modes:
- Sequential: Better for single-chapter books, debugging
- Parallel: Process multiple chapters concurrently with VRAM management
"""

from __future__ import annotations

import asyncio
import logging
import time
import shutil
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Callable, Union, Any
from enum import Enum
import numpy as np

# Import parallel processing modules
try:
    from .parallel import (
        ParallelConfig,
        VRAMBudget,
        ChapterWorkerPool,
        AsyncFileManager,
        PipelinedStage,
        PipelineTask,
        StageStatus,
        create_parallel_config,
        get_optimal_worker_count,
    )
    PARALLEL_AVAILABLE = True
except ImportError:
    PARALLEL_AVAILABLE = False

logger = logging.getLogger(__name__)


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
    tts_engine: str = "kokoro"
    tts_model_name: str = "mlx-community/Kokoro-82M"
    tts_quantization: str = "bf16"
    cleaner_model_name: str = "mlx-community/Llama-3.2-3B-Instruct-4bit"
    voice: str = "am_adam"
    speed: float = 1.0
    output_dir: Path = field(default_factory=lambda: Path("output"))
    temp_dir: Path = field(default_factory=lambda: Path("temp"))
    mp3_bitrate: str = "128k"
    normalize_volume: bool = True
    target_dbfs: float = -16.0
    chunk_size: int = 500  # Max tokens per TTS chunk
    
    # Parallel processing settings
    enable_parallel: bool = True  # Enable chapter-level parallel processing
    max_parallel_chapters: int = 2  # Number of chapters to process concurrently (2-4)
    use_process_pool: bool = True  # Use ProcessPoolExecutor (True) vs ThreadPoolExecutor
    enable_async_io: bool = True  # Use aiofiles for non-blocking I/O
    enable_pipelining: bool = True  # Overlap synthesis and encoding stages
    total_vram_gb: float = 32.0  # Total VRAM for budget calculations


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
    processing_time_seconds: float = 0.0


# Type aliases for callbacks
ProgressCallback = Callable[[PipelineStage, int, int, int, int, str, Optional[float]], None]
# Args: stage, chapter_idx, total_chapters, chunk_idx, total_chunks, message, eta_seconds

VerboseCallback = Callable[[str, str], None]
# Args: message, log_type (info, process, warning, error, success)

ChapterProgressCallback = Callable[[int, int, str], None]
# Args: current_chapter, total_chapters, message


class ConversionPipeline:
    """
    Orchestrates the full audiobook conversion pipeline.
    
    Supports both sequential and parallel processing:
    - Sequential: Process chapters one by one (good for single-chapter books)
    - Parallel: Process multiple chapters concurrently with VRAM management
    
    Stages:
        1. INGESTING - Parse PDF/EPUB, extract chapters
        2. CHUNKING - Split text into TTS-sized chunks
        3. CLEANING - LLM-based text normalization
        4. SYNTHESIZING - Generate audio per chunk
        5. ENCODING - Normalize and encode to MP3
        6. PACKAGING - Create M4B with chapters
    """
    
    def __init__(
        self,
        config: Optional[PipelineConfig] = None,
        progress_callback: Optional[ProgressCallback] = None,
        verbose_callback: Optional[VerboseCallback] = None,
    ):
        """
        Initialize the pipeline.
        
        Args:
            config: Pipeline configuration
            progress_callback: Called on progress updates
            verbose_callback: Called on detailed log updates
        """
        self.config = config or PipelineConfig()
        self.progress_callback = progress_callback
        self.verbose_callback = verbose_callback
        
        self._stage = PipelineStage.IDLE
        self._cancelled = False
        self._start_time: Optional[float] = None
        self._chars_processed = 0
        self._total_chars = 0
        
        # Initialize parallel processing if available
        self._parallel_config: Optional[ParallelConfig] = None
        self._file_manager: Optional[AsyncFileManager] = None
        
        if PARALLEL_AVAILABLE and self.config.enable_parallel:
            self._parallel_config = create_parallel_config(
                max_workers=self.config.max_parallel_chapters,
                total_vram_gb=self.config.total_vram_gb,
                enable_pipelining=self.config.enable_pipelining,
            )
            # Adjust max_parallel_chapters based on VRAM budget
            self.config.max_parallel_chapters = self._parallel_config.max_workers
            if self.config.enable_async_io:
                self._file_manager = AsyncFileManager()
        
        # Ensure directories exist
        self.config.output_dir.mkdir(parents=True, exist_ok=True)
        self.config.temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Cached model instances (for sequential mode)
        self._tts_engine: Any = None
        self._text_cleaner: Any = None
    
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
    
    @property
    def is_parallel(self) -> bool:
        """Check if parallel processing is enabled and available."""
        return PARALLEL_AVAILABLE and self.config.enable_parallel
    
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
        
        Automatically selects parallel or sequential processing based on:
        - Configuration settings
        - Number of chapters
        - Available VRAM
        
        Args:
            source_path: Path to PDF or EPUB file
            title: Override book title
            author: Override author name
            
        Returns:
            ConversionResult with output paths and status
        """
        pipeline_start = time.time()
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
            
            # Persistence: Save full source markdown
            self._save_intermediate_source(document, book_output_dir)
            
            # Determine processing mode
            total_chapters = len(document.chapters)
            
            # Warm up models before processing chapters (sequential mode only)
            if not self.is_parallel and total_chapters > 0:
                self._warmup_models()
            use_parallel = (
                self.is_parallel 
                and total_chapters > 1 
                and self.config.max_parallel_chapters > 1
            )
            
            if use_parallel:
                self._log_verbose(
                    f"[PARALLEL] Using {self.config.max_parallel_chapters} concurrent workers "
                    f"for {total_chapters} chapters",
                    "process"
                )
                chapter_results = self._process_chapters_parallel(
                    document.chapters,
                    chapters_dir,
                )
            else:
                self._log_verbose(
                    f"[SEQUENTIAL] Processing {total_chapters} chapters sequentially",
                    "process"
                )
                chapter_results = self._process_chapters_sequential(
                    document.chapters,
                    chapters_dir,
                )
            
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
            
            processing_time = time.time() - pipeline_start
            
            return ConversionResult(
                success=True,
                title=book_title,
                author=book_author,
                output_path=m4b_path,
                chapters=chapter_results,
                total_duration_ms=total_duration,
                processing_time_seconds=processing_time,
            )
            
        except Exception as e:
            self._stage = PipelineStage.ERROR
            logger.exception("Pipeline conversion failed")
            return ConversionResult(
                success=False,
                title=title or "",
                author=author,
                error=str(e),
            )
        finally:
            # Unload cached models to free memory
            self._cleanup_models()
            self._cleanup_temp()
    
    def _process_chapters_sequential(
        self,
        chapters: list,
        output_dir: Path,
    ) -> list[ChapterResult]:
        """Process chapters sequentially (original behavior)."""
        chapter_results: list[ChapterResult] = []
        total_chapters = len(chapters)
        
        for idx, chapter in enumerate(chapters):
            if self._check_cancelled():
                break
            
            result = self._process_chapter(
                chapter=chapter,
                chapter_idx=idx,
                total_chapters=total_chapters,
                output_dir=output_dir,
            )
            chapter_results.append(result)
        
        return chapter_results
    
    def _process_chapters_parallel(
        self,
        chapters: list,
        output_dir: Path,
    ) -> list[ChapterResult]:
        """
        Process chapters in parallel using ProcessPoolExecutor.
        
        Each chapter is processed independently in a separate process,
        with proper VRAM budget management.
        """
        if not PARALLEL_AVAILABLE or not self._parallel_config:
            # Fallback to sequential
            return self._process_chapters_sequential(chapters, output_dir)
        
        total_chapters = len(chapters)
        chapter_results: list[Optional[ChapterResult]] = [None] * total_chapters
        
        # Use asyncio for parallel coordination
        try:
            results = asyncio.run(
                self._async_process_chapters(chapters, output_dir)
            )
            return [r for r in results if r is not None]
        except Exception as e:
            logger.error(f"Parallel processing failed: {e}, falling back to sequential")
            return self._process_chapters_sequential(chapters, output_dir)
    
    async def _async_process_chapters(
        self,
        chapters: list,
        output_dir: Path,
    ) -> list[ChapterResult]:
        """Async coordination for parallel chapter processing."""
        total_chapters = len(chapters)
        results: list[Optional[ChapterResult]] = [None] * total_chapters
        
        def chapter_progress(current: int, total: int, message: str):
            self._log_verbose(f"[PARALLEL] {message}", "info")
            self._notify_progress(
                chapter_idx=current,
                total_chapters=total,
                message=message,
            )
        
        # Create parallel orchestrator
        from .parallel import ParallelPipelineOrchestrator
        orchestrator = ParallelPipelineOrchestrator(self._parallel_config)
        
        # Process chapters in parallel
        parallel_results = await orchestrator.process_chapters_parallel(
            chapters=list(chapters),
            process_func=lambda ch, idx, fm: self._process_chapter_worker(
                ch, idx, output_dir, self.config
            ),
            progress_callback=chapter_progress,
        )
        
        # Convert to ChapterResult objects
        for i, result in enumerate(parallel_results):
            if isinstance(result, ChapterResult):
                results[i] = result
            elif isinstance(result, dict):
                results[i] = ChapterResult(**result)
        
        return [r for r in results if r is not None]
    
    @staticmethod
    def _process_chapter_worker(
        chapter: Any,
        chapter_idx: int,
        output_dir: Path,
        config: PipelineConfig,
    ) -> ChapterResult:
        """
        Worker function for processing a single chapter in a separate process.
        
        This runs in isolation in a ProcessPoolExecutor worker.
        """
        # Create a new pipeline instance for this worker
        worker_config = PipelineConfig(
            tts_engine=config.tts_engine,
            tts_model_name=config.tts_model_name,
            tts_quantization=config.tts_quantization,
            cleaner_model_name=config.cleaner_model_name,
            voice=config.voice,
            speed=config.speed,
            output_dir=config.output_dir,
            temp_dir=config.temp_dir,
            mp3_bitrate=config.mp3_bitrate,
            normalize_volume=config.normalize_volume,
            target_dbfs=config.target_dbfs,
            chunk_size=config.chunk_size,
            enable_parallel=False,  # Disable parallel in worker to avoid recursion
        )
        
        pipeline = ConversionPipeline(worker_config)
        
        try:
            result = pipeline._process_chapter(
                chapter=chapter,
                chapter_idx=chapter_idx,
                total_chapters=chapter_idx + 1,  # Worker doesn't know total
                output_dir=output_dir,
            )
            return result
        except Exception as e:
            logger.error(f"Worker failed for chapter {chapter_idx}: {e}")
            return ChapterResult(
                chapter_number=chapter.number,
                chapter_title=chapter.title,
                error=str(e),
            )
    
    def _process_chapter(
        self,
        chapter,
        chapter_idx: int,
        total_chapters: int,
        output_dir: Path,
    ) -> ChapterResult:
        """
        Process a single chapter: chunk → clean → synthesize → encode.
        """
        from modules.tts.chunker import TextChunker, ChunkConfig
        from modules.tts.engine import TTSEngine, TTSConfig, BatchItem, concatenate_audio_files
        from modules.audio.processor import AudioProcessor
        from modules.audio.encoder import AudioEncoder
        import soundfile as sf
        
        result = ChapterResult(
            chapter_number=chapter.number,
            chapter_title=chapter.title,
        )
        self._log_verbose(f"[CHAPTER {chapter.number}] Processing: {chapter.title}", "process")
        
        # Log first chapter start
        if chapter_idx == 0:
            self._log_verbose(f"[STATUS] Starting first chapter: {chapter.title}", "process")
        
        # Use persistent TTS engine across chapters for caching (sequential mode)
        engine_config = TTSConfig(
            model_name=self.config.tts_model_name,
            quantization=self.config.tts_quantization,
            default_voice=self.config.voice,
        )
        if not self.is_parallel:
            if self._tts_engine is None:
                self._tts_engine = TTSEngine(config=engine_config)
                self._tts_engine.load_model()
        else:
            # In parallel mode, each worker creates its own engine
            tts_engine = TTSEngine(config=engine_config)
            tts_engine.load_model()
            self._tts_engine = tts_engine
        
        try:
            # Stage 2: Chunk text
            self._stage = PipelineStage.CHUNKING
            self._notify_progress(
                chapter_idx=chapter_idx,
                total_chapters=total_chapters,
                message=f"Chunking: {chapter.title}",
            )
            
            chunk_config = ChunkConfig(max_tokens=self.config.chunk_size)
            chunker = TextChunker(config=chunk_config)
            chunks = chunker.chunk(chapter.content)
            total_chunks = len(chunks)
            self._log_verbose(f"[CHUNKER] Split into {total_chunks} chunks", "info")
            
            if total_chunks == 0:
                result.error = "No text content"
                self._log_verbose(f"[CHAPTER {chapter.number}] Empty chapter!", "error")
                return result
            
            # Stage 2.5: Clean text with model caching
            self._stage = PipelineStage.CLEANING
            from modules.tts.cleaner import TextCleaner, CleanerConfig
            
            cleaned_chunks = []
            
            # Use persistent cleaner if available (sequential mode), otherwise create new
            if not self.is_parallel:
                if self._text_cleaner is None:
                    self._log_verbose(
                        f"[CLEANER] Loading Text Cleaner model: {self.config.cleaner_model_name}",
                        "process"
                    )
                    self._text_cleaner = TextCleaner(
                        config=CleanerConfig(
                            model_name=self.config.cleaner_model_name,
                            cache_model=True,
                        )
                    )
                    self._text_cleaner.load()
                    self._log_verbose("[CLEANER] Model loaded - Cleaning text chunks...", "success")
                else:
                    self._log_verbose("[CLEANER] Using cached Text Cleaner model", "success")
                text_cleaner = self._text_cleaner
            else:
                # In parallel mode, each worker creates its own cleaner
                self._log_verbose(
                    f"[CLEANER] Loading Text Cleaner model: {self.config.cleaner_model_name}",
                    "process"
                )
                text_cleaner = TextCleaner(
                    config=CleanerConfig(
                        model_name=self.config.cleaner_model_name,
                        cache_model=True,
                    )
                )
                text_cleaner.load()
                self._log_verbose("[CLEANER] Model loaded - Cleaning text chunks...", "success")
            
            self._log_verbose("[STATUS] LLM (Text Cleaner) running...", "process")
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
                
                # Show preview in terminal
                preview = chunk[:50].replace("\n", " ") + "..."
                self._log_verbose(f"[CLEANER] Chunk {chunk_idx+1}/{total_chunks}: {preview}", "info")
                
                cleaned_chunk = text_cleaner.clean(chunk)
                cleaned_chunks.append(cleaned_chunk)
            
            chunks = cleaned_chunks
            
            # Save intermediate cleaned chapter
            try:
                clean_md = output_dir / f"chapter_{chapter.number:02d}_cleaned.md"
                clean_md.write_text(
                    f"# {chapter.title}\n\n" + "\n\n".join(chunks),
                    encoding="utf-8"
                )
                self._log_verbose(f"[CLEANER] Saved cleaned text: {clean_md.name}", "success")
            except Exception as e:
                self._log_verbose(f"[CLEANER] Failed to save cleaned md: {e}", "warning")
            
            # Stage 3: Synthesize chunks using batch processing
            self._stage = PipelineStage.SYNTHESIZING
            # Check if using cached model (loaded during warm-up) or fresh load (parallel mode)
            is_cached = self._tts_engine is not None and self._tts_engine.is_loaded
            if is_cached:
                self._log_verbose(
                    f"[TTS] Using cached TTS Model: {self.config.tts_model_name}-{self.config.tts_quantization}",
                    "success",
                )
            else:
                self._log_verbose(
                    f"[TTS] Loading TTS Model: {self.config.tts_model_name}-{self.config.tts_quantization}",
                    "process",
                )
            self._log_verbose("[STATUS] TTS (Text-to-Speech) running...", "process")
            
            if is_cached:
                self._log_verbose("[TTS] Starting batch synthesis with cached model", "success")
            else:
                self._log_verbose("[TTS] Model loaded - Starting batch synthesis", "success")
            
            # Create batch items for parallel processing
            batch_items = [
                BatchItem(
                    text=chunk,
                    voice=self.config.voice,
                    speed=self.config.speed,
                    index=i
                )
                for i, chunk in enumerate(chunks)
            ]
            
            chunk_files = []
            
            def on_batch_progress(completed: int, total: int):
                """Update progress during batch synthesis."""
                chunk_idx = completed - 1
                if chunk_idx >= 0 and chunk_idx < len(chunks):
                    self._notify_progress(
                        chapter_idx=chapter_idx,
                        total_chapters=total_chapters,
                        chunk_idx=chunk_idx,
                        total_chunks=total_chunks,
                        message=f"Synthesizing chunk {chunk_idx + 1}/{total_chunks}",
                    )
                    
                    # Terminal output
                    text_preview = chunks[chunk_idx][:40].replace("\n", " ")
                    self._log_verbose(
                        f"[TTS] Speaking chunk {chunk_idx+1}/{total_chunks}: {text_preview}...",
                        "info"
                    )
                    
                    # Log progress percentage
                    pct = int((chunk_idx + 1) / total_chunks * 100)
                    if pct % 25 == 0:
                        self._log_verbose(
                            f"[TTS] Progress: {pct}% ({chunk_idx+1}/{total_chunks} chunks)",
                            "info"
                        )
                    
                    self._chars_processed += len(chunks[chunk_idx])
            
            # Process in batches for better throughput
            batch_results = self._tts_engine.synthesize_batch(
                items=batch_items,
                progress_callback=on_batch_progress,
            )
            
            # Check for errors and save audio files
            for i, batch_result in enumerate(batch_results):
                if batch_result.error:
                    self._log_verbose(f"[TTS] Error on chunk {i+1}: {batch_result.error}", "error")
                    continue
                
                # Save individual chunk file
                chunk_wav = self.config.temp_dir / f"chapter_{chapter.number:02d}_chunk_{i:04d}.wav"
                sf.write(str(chunk_wav), batch_result.audio, 24000, subtype='PCM_16')
                chunk_files.append(chunk_wav)
            
            if not chunk_files:
                result.error = "No audio generated"
                return result
            
            self._log_verbose(f"[TTS] Generation complete - {len(chunk_files)} audio segments", "success")
            
            # Concatenate all chunks using memory-mapped files for large audio
            chapter_wav = self.config.temp_dir / f"chapter_{chapter.number:02d}.wav"
            
            # Use memmap for large files (>10 chunks) to reduce memory
            use_memmap = len(chunk_files) > 10
            if use_memmap:
                self._log_verbose("[TTS] Using memory-mapped concatenation for large audio", "info")
            
            concatenate_audio_files(chunk_files, chapter_wav, use_memmap=use_memmap)
            result.wav_path = chapter_wav
            
            # Clean up chunk files after concatenation
            for chunk_file in chunk_files:
                try:
                    chunk_file.unlink()
                except Exception:
                    pass
            
            # Stage 4: Encode to MP3
            self._stage = PipelineStage.ENCODING
            self._notify_progress(
                chapter_idx=chapter_idx,
                total_chapters=total_chapters,
                message=f"Encoding: {chapter.title}",
            )
            self._log_verbose("[ENCODER] Encoding to MP3...", "process")
            
            # Normalize volume
            if self.config.normalize_volume:
                self._log_verbose("[ENCODER] Normalizing audio volume...", "info")
                processor = AudioProcessor()
                normalized = processor.normalize_volume(
                    processor.load(chapter_wav),
                    target_dBFS=self.config.target_dbfs,
                )
                processor.save(normalized, chapter_wav)
            
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
            
            self._log_verbose(
                f"[ENCODER] Complete: {chapter_mp3.name} ({result.duration_ms/1000:.1f}s)",
                "success"
            )
            self._log_verbose(f"[CHAPTER {chapter.number}] TTS Complete - Audio ready", "success")
            
            # Log first chapter completion
            if chapter_idx == 0:
                self._log_verbose(f"[STATUS] First chapter finished: {chapter.title}", "success")
            
            return result
            
        except Exception as e:
            result.error = str(e)
            logger.exception(f"Chapter {chapter.number} processing failed")
            return result
    
    def _ingest(self, source_path: Path):
        """Parse source file and extract document structure."""
        suffix = source_path.suffix.lower()
        self._log_verbose(f"[PARSER] Ingesting file: {source_path.name}", "process")
        self._log_verbose(f"[PARSER] File type: {suffix}", "info")
        
        # Get file size for progress calculation
        file_size = source_path.stat().st_size
        self._log_verbose(f"[PARSER] File size: {file_size / 1024:.1f} KB", "info")
        
        parser = None
        if suffix == ".epub":
            from modules.ingestion.epub_parser import EPUBParser
            parser = EPUBParser(source_path)
        elif suffix == ".pdf":
            from modules.ingestion.pdf_parser import PDFParser
            parser = PDFParser(source_path)
        else:
            raise ValueError(f"Unsupported file type: {suffix}")
        
        self._log_verbose("[PARSER] Parsing content...", "process")
        document = parser.parse()
        
        num_chapters = len(document.chapters)
        self._log_verbose(f"[PARSER] Extracted: {num_chapters} chapters found", "success")
        
        # Report each chapter parsed with progress
        for i, ch in enumerate(document.chapters):
            progress_pct = int((i + 1) / num_chapters * 100) if num_chapters > 0 else 0
            self._log_verbose(
                f"[PARSER] [{progress_pct:3d}%] Chapter {i+1}/{num_chapters}: {ch.title[:40]}... ({len(ch.content)} chars)",
                "info"
            )
            # Update progress for UI
            self._notify_progress(
                chapter_idx=i,
                total_chapters=num_chapters,
                message=f"Parsing chapter {i+1}/{num_chapters}: {ch.title[:30]}..."
            )
        
        self._log_verbose(f"[PARSER] Parsing complete - {num_chapters} chapters ready", "success")
        self._log_verbose(f"[STATUS] Parsing done - {num_chapters} chapters extracted", "process")
        return document
    
    def _save_intermediate_source(self, document, output_dir: Path):
        """Save full source text for debugging."""
        try:
            source_md = output_dir / "source.md"
            source_md.write_text(
                f"# {document.title}\n\n{document.raw_markdown}",
                encoding="utf-8"
            )
            self._log_verbose(f"Saved source markdown: {source_md.name}", "info")
        except Exception as e:
            self._log_verbose(f"Failed to save source.md: {e}", "warning")
    
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
    
    def _warmup_models(self) -> None:
        """
        Pre-load TTS and cleaner models before processing chapters.
        
        This ensures models are loaded once and reused across all chapters
        in sequential processing mode, avoiding per-chapter loading overhead.
        """
        self._log_verbose("[WARMUP] Pre-loading models for sequential processing...", "process")
        
        # Warm up TTS engine
        if self._tts_engine is None:
            from modules.tts.engine import TTSEngine, TTSConfig
            self._log_verbose(
                f"[WARMUP] Loading TTS Model: {self.config.tts_model_name}-{self.config.tts_quantization}",
                "process",
            )
            self._tts_engine = TTSEngine(
                config=TTSConfig(
                    model_name=self.config.tts_model_name,
                    quantization=self.config.tts_quantization,
                    default_voice=self.config.voice,
                )
            )
            self._tts_engine.load_model()
            self._log_verbose("[WARMUP] TTS Model loaded and cached", "success")
        
        # Warm up text cleaner
        if self._text_cleaner is None:
            from modules.tts.cleaner import TextCleaner, CleanerConfig
            self._log_verbose(
                f"[WARMUP] Loading Text Cleaner model: {self.config.cleaner_model_name}",
                "process",
            )
            self._text_cleaner = TextCleaner(
                config=CleanerConfig(
                    model_name=self.config.cleaner_model_name,
                    cache_model=True,
                )
            )
            self._text_cleaner.load()
            self._log_verbose("[WARMUP] Text Cleaner model loaded and cached", "success")
        
        self._log_verbose("[WARMUP] Model warm-up complete - ready for chapter processing", "success")
    
    def _cleanup_models(self):
        """Unload cached models to free memory."""
        try:
            if self._tts_engine is not None:
                self._tts_engine.unload_model(keep_in_cache=True)
        except Exception:
            pass
        
        try:
            if self._text_cleaner is not None:
                self._text_cleaner.unload(keep_in_cache=True)
        except Exception:
            pass
        
        self._tts_engine = None
        self._text_cleaner = None
    
    def _cleanup_temp(self):
        """Clean up temporary files."""
        try:
            if self.config.temp_dir.exists():
                for f in self.config.temp_dir.iterdir():
                    if f.is_file():
                        try:
                            f.unlink()
                        except Exception:
                            pass
        except Exception:
            pass  # Best effort cleanup
    
    def _log_verbose(self, message: str, log_type: str = "info"):
        """Emit verbose log if callback present."""
        if self.verbose_callback:
            self.verbose_callback(message, log_type)
