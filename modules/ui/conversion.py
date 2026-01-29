"""
Conversion Runner
=================
Handles running the conversion pipeline with Streamlit UI integration.
Supports both synchronous and background (non-blocking) conversion.
"""

import tempfile
import shutil
from pathlib import Path
from typing import BinaryIO, Optional, Callable
import streamlit as st

from modules.pipeline.orchestrator import (
    ConversionPipeline,
    PipelineStage,
    PipelineConfig,
    ConversionResult,
)
from modules.ui.progress import (
    ProcessingStage,
    set_chapters,
    update_chapter_progress,
    set_current_stage,
    get_progress,
    save_progress_to_session,
    render_chapter_progress,
    render_stage_indicator,
)
from modules.concurrency import (
    BackgroundTaskManager,
    CancellationToken,
    TaskQueue,
    TaskMessage,
    TaskStatus,
)


# Background conversion task ID
CONVERSION_TASK_ID = "audiobook_conversion"


def add_log(message: str):
    """Add a message to the log window."""
    if "log_messages" not in st.session_state:
        st.session_state.log_messages = []
    st.session_state.log_messages.append(message)
    if len(st.session_state.log_messages) > 50:
        st.session_state.log_messages = st.session_state.log_messages[-50:]


def map_pipeline_stage(stage: PipelineStage) -> ProcessingStage:
    """Map pipeline stage to UI processing stage."""
    mapping = {
        PipelineStage.IDLE: ProcessingStage.IDLE,
        PipelineStage.INGESTING: ProcessingStage.PARSING,
        PipelineStage.CHUNKING: ProcessingStage.PARSING,
        PipelineStage.CLEANING: ProcessingStage.CLEANING,
        PipelineStage.SYNTHESIZING: ProcessingStage.SYNTHESIZING,
        PipelineStage.ENCODING: ProcessingStage.ENCODING,
        PipelineStage.PACKAGING: ProcessingStage.PACKAGING,
        PipelineStage.COMPLETE: ProcessingStage.COMPLETE,
        PipelineStage.ERROR: ProcessingStage.ERROR,
        PipelineStage.CANCELLED: ProcessingStage.CANCELLED,
    }
    return mapping.get(stage, ProcessingStage.IDLE)


def progress_callback(
    stage: PipelineStage,
    chapter_idx: int,
    total_chapters: int,
    chunk_idx: int,
    total_chunks: int,
    message: str,
):
    """
    Handle progress updates from pipeline.
    Updates UI state and logs.
    """
    # Update UI processing stage
    ui_stage = map_pipeline_stage(stage)
    set_current_stage(ui_stage)
    
    # Update chapter progress
    if total_chapters > 0:
        update_chapter_progress(
            chapter_idx=chapter_idx,
            completed_chunks=chunk_idx,
            total_chunks=total_chunks,
            stage=ui_stage,
        )
    
    # Update ETA
    progress = get_progress()
    if total_chapters > 0 and total_chunks > 0:
        # Simple progress calculation
        chapter_progress = chapter_idx / total_chapters if total_chapters > 0 else 0
        chunk_progress = chunk_idx / total_chunks if total_chunks > 0 else 0
        overall = chapter_progress + (chunk_progress / total_chapters)
        st.session_state.progress = overall
    
    # Log message
    if message:
        add_log(message)
    
    # Save to session for persistence
    save_progress_to_session()


def save_uploaded_file(uploaded_file: BinaryIO, filename: str) -> Path:
    """
    Save uploaded file to temp directory.
    
    Returns:
        Path to saved file
    """
    temp_dir = Path(tempfile.gettempdir()) / "audiobook_uploads"
    temp_dir.mkdir(exist_ok=True)
    
    file_path = temp_dir / filename
    with open(file_path, "wb") as f:
        f.write(uploaded_file.read())
    
    return file_path


def run_conversion(
    uploaded_file: BinaryIO,
    filename: str,
    voice: str,
    speed: float,
    progress_container=None,
    status_container=None,
    verbose_callback=None,
) -> ConversionResult:
    """
    Run the full conversion pipeline.
    
    Args:
        uploaded_file: Uploaded file object
        filename: Original filename
        voice: Selected voice ID
        speed: Playback speed
        progress_container: Streamlit container/placeholder for progress updates
        status_container: Streamlit container/placeholder for status updates
        verbose_callback: Callback for detailed logging
        
    Returns:
        ConversionResult with output path and status
    """
    # Save uploaded file
    source_path = save_uploaded_file(uploaded_file, filename)
    
    # Configure pipeline
    config = PipelineConfig(
        voice=voice,
        speed=speed,
        output_dir=Path("output"),
        temp_dir=Path("temp"),
    )
    
    # Define callback with access to containers
    def _on_progress(
        stage: PipelineStage,
        chapter_idx: int,
        total_chapters: int,
        chunk_idx: int,
        total_chunks: int,
        message: str,
        eta_seconds: Optional[float] = None,
    ):
        # Update UI processing stage
        ui_stage = map_pipeline_stage(stage)
        set_current_stage(ui_stage)
        
        # Update chapter progress
        if total_chapters > 0:
            update_chapter_progress(
                chapter_idx=chapter_idx,
                completed_chunks=chunk_idx,
                total_chunks=total_chunks,
                stage=ui_stage,
            )
        
        # Update ETA and overall progress
        progress = get_progress()
        progress.eta_seconds = eta_seconds
        
        if total_chapters > 0:
            # Simple progress calculation
            chapter_progress = chapter_idx / total_chapters
            if total_chunks > 0:
                 chunk_p = chunk_idx / total_chunks
                 chapter_progress += (chunk_p / total_chapters)
            
            st.session_state.progress = min(1.0, chapter_progress)
        
        # Log message
        if message:
            add_log(message)
        
        # LIVE UI UPDATES
        if progress_container:
            with progress_container.container():
                render_chapter_progress()
        
        if status_container:
            with status_container.container():
                render_stage_indicator()
        
        # Save to session for persistence
        save_progress_to_session()

    # Create pipeline with progress callback
    pipeline = ConversionPipeline(
        config=config,
        progress_callback=_on_progress,
        verbose_callback=verbose_callback,
    )
    
    # Run conversion
    add_log(f"starting conversion: {filename}")
    result = pipeline.convert(source_path)
    
    # Cleanup temp file
    try:
        source_path.unlink()
    except Exception:
        pass
    
    return result


def init_conversion_state():
    """Initialize conversion-related session state."""
    if "conversion_result" not in st.session_state:
        st.session_state.conversion_result = None
    if "parsed_document" not in st.session_state:
        st.session_state.parsed_document = None
    if "uploaded_file_bytes" not in st.session_state:
        st.session_state.uploaded_file_bytes = None


def handle_start_conversion(uploaded_file, voice: str, speed: float):
    """
    Handle the START CONVERSION button click.
    Parses the file and initiates conversion.
    """
    init_conversion_state()
    
    # Save file bytes for processing
    st.session_state.uploaded_file_bytes = uploaded_file.read()
    uploaded_file.seek(0)  # Reset for potential re-read
    
    # Update status
    st.session_state.status = "processing"
    st.session_state.processing_stage = "ingesting"
    
    add_log(f"parsing: {uploaded_file.name}")


def get_text_preview(uploaded_file) -> str:
    """
    Get a text preview from the uploaded file.
    
    Returns:
        First ~500 characters of text
    """
    try:
        import tempfile
        import os
        
        # Save to temp file
        temp_path = Path(tempfile.gettempdir()) / uploaded_file.name
        with open(temp_path, "wb") as f:
            f.write(uploaded_file.read())
        uploaded_file.seek(0)  # Reset
        
        suffix = temp_path.suffix.lower()
        
        if suffix == ".epub":
            from modules.ingestion.epub_parser import EPUBParser
            parser = EPUBParser(temp_path)
            doc = parser.parse()
            if doc.chapters:
                preview = doc.chapters[0].content[:500]
            else:
                preview = "No chapters found"
        elif suffix == ".pdf":
            from modules.ingestion.pdf_parser import PDFParser
            parser = PDFParser(temp_path)
            doc = parser.parse()
            if doc.raw_markdown:
                preview = doc.raw_markdown[:500]
            else:
                preview = "No content found"
        else:
            preview = "Unsupported file type"
        
        # Cleanup
        try:
            temp_path.unlink()
        except:
            pass
        
        return preview + "..." if len(preview) >= 500 else preview
        
    except Exception as e:
        return f"Preview error: {str(e)}"


# ===========================================
# Background Conversion Functions
# ===========================================

def _run_background_conversion(
    cancel_token: CancellationToken,
    message_queue: TaskQueue[TaskMessage],
    source_path: Path,
    config: PipelineConfig,
    verbose_callback: Optional[Callable[[str, str], None]] = None,
) -> ConversionResult:
    """
    Background task function for running conversion.
    
    This runs in a separate thread and communicates via the message queue.
    """
    # Create pipeline with callbacks that post to the queue
    def on_progress(
        stage: PipelineStage,
        chapter_idx: int,
        total_chapters: int,
        chunk_idx: int,
        total_chunks: int,
        message: str,
        eta_seconds: Optional[float] = None,
    ):
        # Check for cancellation
        if cancel_token.is_cancelled():
            return
        
        # Calculate overall progress
        progress = 0.0
        if total_chapters > 0:
            chapter_progress = chapter_idx / total_chapters
            if total_chunks > 0:
                chunk_p = chunk_idx / total_chunks
                chapter_progress += (chunk_p / total_chapters)
            progress = min(1.0, chapter_progress)
        
        # Post progress update
        message_queue.put(TaskMessage(
            task_id=CONVERSION_TASK_ID,
            status=TaskStatus.RUNNING,
            progress=progress,
            message=message or "",
            data={
                "stage": stage.value,
                "chapter_idx": chapter_idx,
                "total_chapters": total_chapters,
                "chunk_idx": chunk_idx,
                "total_chunks": total_chunks,
                "eta_seconds": eta_seconds,
            }
        ))
    
    def on_verbose(msg: str, log_type: str = "info"):
        # Post verbose log
        message_queue.put(TaskMessage(
            task_id=CONVERSION_TASK_ID,
            status=TaskStatus.RUNNING,
            message=msg,
            data={"log_type": log_type, "is_verbose": True}
        ))
        
        # Also call external callback if provided
        if verbose_callback:
            verbose_callback(msg, log_type)
    
    # Create and run pipeline
    pipeline = ConversionPipeline(
        config=config,
        progress_callback=on_progress,
        verbose_callback=on_verbose,
    )
    
    # Check cancellation before starting
    if cancel_token.is_cancelled():
        return ConversionResult(
            success=False,
            title="Cancelled",
            error="Cancelled before start"
        )
    
    # Pass cancellation check to pipeline
    original_check = pipeline._check_cancelled
    def patched_check():
        if cancel_token.is_cancelled():
            pipeline.cancel()
        original_check()
    pipeline._check_cancelled = patched_check
    
    result = pipeline.convert(source_path)
    
    return result


def start_background_conversion(
    uploaded_file: BinaryIO,
    filename: str,
    voice: str,
    speed: float,
    verbose_callback: Optional[Callable[[str, str], None]] = None,
) -> str:
    """
    Start a background conversion. Returns immediately.
    
    Args:
        uploaded_file: Uploaded file object
        filename: Original filename  
        voice: Selected voice ID
        speed: Playback speed
        verbose_callback: Optional callback for detailed logging
        
    Returns:
        Task ID for tracking the conversion
    """
    # Save uploaded file first (must be done in main thread)
    source_path = save_uploaded_file(uploaded_file, filename)
    
    # Store source path in session for later cleanup
    st.session_state.background_source_path = source_path
    
    # Configure pipeline
    config = PipelineConfig(
        voice=voice,
        speed=speed,
        output_dir=Path("output"),
        temp_dir=Path("temp"),
    )
    
    # Get task manager and submit
    manager = BackgroundTaskManager()
    
    task_id = manager.submit(
        CONVERSION_TASK_ID,
        _run_background_conversion,
        source_path,
        config,
        verbose_callback,
    )
    
    # Mark as running in session state
    st.session_state.background_conversion_running = True
    st.session_state.status = "processing"
    st.session_state.processing_stage = "ingesting"
    
    add_log(f"background conversion started: {filename}")
    
    return task_id


def process_background_messages() -> Optional[ConversionResult]:
    """
    Process any pending messages from background conversion.
    
    Call this in your Streamlit UI loop to update the display.
    Should be called frequently (e.g., during st.rerun() cycle).
    
    Returns:
        ConversionResult if conversion completed, None otherwise
    """
    manager = BackgroundTaskManager()
    messages = manager.get_messages()
    
    result = None
    
    for msg in messages:
        if msg.task_id != CONVERSION_TASK_ID:
            continue
        
        # Handle based on status
        if msg.status == TaskStatus.RUNNING:
            data = msg.data or {}
            
            # Check if this is a verbose log
            if data.get("is_verbose"):
                # Add to terminal log
                from modules.ui.terminal import add_terminal_log
                add_terminal_log(msg.message, data.get("log_type", "info"))
                
                # Update active model based on log messages
                if "cleaner" in msg.message.lower():
                    st.session_state.active_model = "cleaner"
                    st.session_state.cleaner_model_loaded = True
                elif "tts" in msg.message.lower() and "model" in msg.message.lower():
                    st.session_state.active_model = "tts"
                    st.session_state.tts_model_loaded = True
                elif "unloaded" in msg.message.lower():
                    if "cleaner" in msg.message.lower():
                        st.session_state.cleaner_model_loaded = False
                    elif "tts" in msg.message.lower():
                        st.session_state.tts_model_loaded = False
            else:
                # Progress update
                stage_str = data.get("stage", "idle")
                ui_stage = map_pipeline_stage(PipelineStage(stage_str))
                set_current_stage(ui_stage)
                
                # Update processing stage
                if stage_str in ("ingesting", "chunking"):
                    st.session_state.processing_stage = "parsing"
                else:
                    st.session_state.processing_stage = stage_str
                
                # Update chapter progress
                total_chapters = data.get("total_chapters", 0)
                if total_chapters > 0:
                    update_chapter_progress(
                        chapter_idx=data.get("chapter_idx", 0),
                        completed_chunks=data.get("chunk_idx", 0),
                        total_chunks=data.get("total_chunks", 0),
                        stage=ui_stage,
                    )
                
                # Update progress
                st.session_state.progress = msg.progress
                
                if msg.message:
                    add_log(msg.message)
                
                save_progress_to_session()
        
        elif msg.status == TaskStatus.COMPLETED:
            st.session_state.background_conversion_running = False
            st.session_state.active_model = None
            
            # Extract result from task result
            if msg.data and hasattr(msg.data, 'result'):
                result = msg.data.result
                st.session_state.conversion_result = result
                
                if result.success:
                    st.session_state.status = "complete"
                    add_log(f"conversion complete: {result.output_path}")
                else:
                    st.session_state.status = "error"
                    add_log(f"conversion failed: {result.error}")
            
            # Cleanup temp file
            if hasattr(st.session_state, 'background_source_path'):
                try:
                    st.session_state.background_source_path.unlink()
                except:
                    pass
        
        elif msg.status == TaskStatus.CANCELLED:
            st.session_state.background_conversion_running = False
            st.session_state.status = "cancelled"
            st.session_state.active_model = None
            add_log("conversion cancelled")
        
        elif msg.status == TaskStatus.FAILED:
            st.session_state.background_conversion_running = False
            st.session_state.status = "error"
            st.session_state.active_model = None
            add_log(f"conversion failed: {msg.message}")
            
            if msg.error:
                from modules.ui.terminal import add_terminal_log
                add_terminal_log(f"Error: {str(msg.error)}", "error")
    
    return result


def cancel_background_conversion() -> bool:
    """
    Cancel the running background conversion.
    
    Returns:
        True if cancellation was requested, False if no conversion running
    """
    manager = BackgroundTaskManager()
    cancelled = manager.cancel(CONVERSION_TASK_ID)
    
    if cancelled:
        st.session_state.background_conversion_running = False
        st.session_state.conversion_cancelled = True
        add_log("conversion cancellation requested...")
    
    return cancelled


def is_background_conversion_running() -> bool:
    """Check if a background conversion is currently running."""
    return st.session_state.get("background_conversion_running", False)


def init_background_conversion_state():
    """Initialize background conversion session state."""
    if "background_conversion_running" not in st.session_state:
        st.session_state.background_conversion_running = False
    if "background_source_path" not in st.session_state:
        st.session_state.background_source_path = None

