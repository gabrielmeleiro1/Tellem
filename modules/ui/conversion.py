"""
Conversion Runner
=================
Handles running the conversion pipeline with Streamlit UI integration.
"""

import tempfile
import shutil
from pathlib import Path
from typing import BinaryIO, Optional
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
