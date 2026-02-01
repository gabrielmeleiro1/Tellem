"""
Audiobook Creator - Main Application
====================================
A Python-based audiobook creator optimized for Apple Silicon (M1/M2/M3).
Converts PDF and EPUB files into high-quality audiobooks.

UI: Streamlit with "Industrial Moss" brutalist theme
"""

import streamlit as st
import threading
import time
from pathlib import Path
from queue import Queue
from dataclasses import dataclass
from typing import Optional, Any

# Industrial Moss Theme
from modules.ui.theme import apply_theme

from modules.ui.progress import (
    init_progress_state,
    get_progress,
    set_chapters,
    set_current_stage,
    render_chapter_progress,
    render_stage_indicator,
    ProcessingStage,
)
from modules.ui.waveform import render_waveform_component
from modules.ui.conversion import (
    run_conversion,
    get_text_preview,
    init_conversion_state,
    add_log as conversion_add_log,
)
from modules.storage.database import Database, Book, Chapter

from modules.ui.terminal import render_terminal_view, add_terminal_log
from modules.ui.terminal_moss import (
    render_industrial_terminal,
    add_info as moss_add_info,
    add_process as moss_add_process,
    add_error as moss_add_error,
)
from modules.ui.monitor import render_system_stats
from modules.ui.checklist import render_checklist_view

# ============================================
# PAGE CONFIGURATION
# ============================================
st.set_page_config(
    page_title="audiobook_creator_v1.0",
    page_icon=":material/book:",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================
# LOAD CUSTOM CSS
# ============================================
def load_css():
    """Load the Industrial Moss brutalist theme."""
    # Use Industrial Moss theme
    css_path = Path(__file__).parent / "assets" / "css" / "industrial_moss.css"
    if css_path.exists():
        with open(css_path) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    else:
        # Fallback to theme module
        apply_theme()


load_css()

# ============================================
# SESSION STATE INITIALIZATION
# ============================================
if "status" not in st.session_state:
    st.session_state.status = "idle"
if "current_file" not in st.session_state:
    st.session_state.current_file = None
if "log_messages" not in st.session_state:
    st.session_state.log_messages = []
if "progress" not in st.session_state:
    st.session_state.progress = 0.0
if "selected_voice" not in st.session_state:
    st.session_state.selected_voice = "am_adam"
if "selected_speed" not in st.session_state:
    st.session_state.selected_speed = 1.0

# Model tracking
if "tts_model_loaded" not in st.session_state:
    st.session_state.tts_model_loaded = False
if "tts_model_name" not in st.session_state:
    st.session_state.tts_model_name = "mlx-community/Kokoro-82M-bf16"
if "cleaner_model_loaded" not in st.session_state:
    st.session_state.cleaner_model_loaded = False
if "cleaner_model_name" not in st.session_state:
    st.session_state.cleaner_model_name = "mlx-community/Llama-3.2-3B-Instruct-4bit"
if "active_model" not in st.session_state:
    st.session_state.active_model = None  # "tts" or "cleaner"

if "processing_stage" not in st.session_state:
    st.session_state.processing_stage = "idle"
if "conversion_cancelled" not in st.session_state:
    st.session_state.conversion_cancelled = False

# Threading state for background conversion
if "conversion_thread" not in st.session_state:
    st.session_state.conversion_thread = None
if "thread_error" not in st.session_state:
    st.session_state.thread_error = None
if "thread_running" not in st.session_state:
    st.session_state.thread_running = False

# Pipeline instance for cancellation access
if "active_pipeline" not in st.session_state:
    st.session_state.active_pipeline = None

# View state for navigation
if "view" not in st.session_state:
    st.session_state.view = "upload"  # upload, library, checklist

# Message queue for thread-safe communication
if "message_queue" not in st.session_state:
    st.session_state.message_queue = Queue()


# ============================================
# THREAD-SAFE MESSAGE TYPES
# ============================================
@dataclass
class LogMessage:
    """Message for log updates from background thread."""
    message: str
    msg_type: str = "info"

@dataclass
class ProgressMessage:
    """Message for progress updates from background thread."""
    stage: Any  # PipelineStage
    chapter_idx: int
    total_chapters: int
    chunk_idx: int
    total_chunks: int
    message: str
    eta: Optional[float] = None

@dataclass
class ModelStatusMessage:
    """Message for model status updates."""
    model_type: str  # "tts" or "cleaner"
    is_loaded: bool

@dataclass
class ConversionCompleteMessage:
    """Message sent when conversion completes."""
    result: Any  # ConversionResult
    error: Optional[str] = None


# ============================================
# BACKGROUND CONVERSION MONITOR
# ==========================================
def check_conversion_status():
    """
    Check and update conversion status from background thread.
    Processes message queue and updates UI state.
    Call this at the start of each script run.
    """
    # Process any pending messages from the background thread
    process_message_queue()
    
    # Check if thread has finished
    if st.session_state.conversion_thread and not st.session_state.conversion_thread.is_alive():
        # Thread is dead but we may still have messages to process
        process_message_queue()
        
        # If thread_running is still True but thread is dead, we missed the completion message
        if st.session_state.thread_running:
            st.session_state.thread_running = False
            st.session_state.active_pipeline = None
            st.session_state.active_model = None
            st.session_state.conversion_thread = None


def add_log(message: str):
    """Add a message to the log window."""
    # Ensure log_messages exists (thread-safe check)
    if "log_messages" not in st.session_state:
        st.session_state.log_messages = []
    
    st.session_state.log_messages.append(message)
    # Keep only last 50 messages
    if len(st.session_state.log_messages) > 50:
        st.session_state.log_messages = st.session_state.log_messages[-50:]


# ============================================
# THREADING FOR BACKGROUND CONVERSION
# ============================================
def run_conversion_in_thread(pipeline, source_path, message_queue: Queue):
    """
    Run the conversion pipeline in a background thread.
    Uses message_queue for thread-safe communication.
    """
    try:
        result = pipeline.convert(source_path)
        message_queue.put(ConversionCompleteMessage(result=result, error=None))
    except Exception as e:
        message_queue.put(ConversionCompleteMessage(result=None, error=str(e)))


def process_message_queue():
    """
    Process all pending messages from the background thread.
    Call this in the main thread to update UI state.
    """
    from modules.ui.terminal import add_terminal_log
    from modules.ui.progress import (
        update_chapter_progress,
        set_current_stage,
        ProcessingStage,
        get_progress,
    )
    
    queue = st.session_state.message_queue
    
    while not queue.empty():
        msg = queue.get()
        
        if isinstance(msg, LogMessage):
            add_log(msg.message)
            if msg.msg_type != "info":
                add_terminal_log(msg.message, msg.msg_type)
        
        elif isinstance(msg, ProgressMessage):
            stage_map = {
                "ingesting": ProcessingStage.PARSING,
                "chunking": ProcessingStage.PARSING,
                "cleaning": ProcessingStage.CLEANING,
                "synthesizing": ProcessingStage.SYNTHESIZING,
                "encoding": ProcessingStage.ENCODING,
                "packaging": ProcessingStage.PACKAGING,
                "complete": ProcessingStage.COMPLETE,
                "error": ProcessingStage.ERROR,
                "cancelled": ProcessingStage.CANCELLED,
            }
            ui_stage = stage_map.get(msg.stage.value, ProcessingStage.IDLE)
            set_current_stage(ui_stage)
            
            if msg.stage.value in ("ingesting", "chunking"):
                st.session_state.processing_stage = "parsing"
            else:
                st.session_state.processing_stage = msg.stage.value
            
            if msg.total_chapters > 0:
                if msg.stage.value == "ingesting" and msg.chapter_idx < msg.total_chapters:
                    progress = get_progress()
                    if msg.chapter_idx < len(progress.chapters):
                        progress.chapters[msg.chapter_idx].is_parsed = True
                
                update_chapter_progress(
                    chapter_idx=msg.chapter_idx,
                    completed_chunks=msg.chunk_idx,
                    total_chunks=msg.total_chunks,
                    stage=ui_stage,
                )
            
            if msg.message:
                add_log(msg.message)
        
        elif isinstance(msg, ModelStatusMessage):
            if msg.model_type == "cleaner":
                st.session_state.active_model = "cleaner" if msg.is_loaded else None
                st.session_state.cleaner_model_loaded = msg.is_loaded
            elif msg.model_type == "tts":
                st.session_state.active_model = "tts" if msg.is_loaded else None
                st.session_state.tts_model_loaded = msg.is_loaded
        
        elif isinstance(msg, ConversionCompleteMessage):
            st.session_state.thread_running = False
            st.session_state.active_pipeline = None
            st.session_state.active_model = None
            
            if msg.error:
                st.session_state.thread_error = msg.error
                st.session_state.status = "error"
                add_log(f"conversion failed: {msg.error}")
                add_terminal_log(f"Conversion failed: {msg.error}", "error")
            elif msg.result:
                st.session_state.conversion_result = msg.result
                if msg.result.success:
                    st.session_state.status = "complete"
                    add_log(f"conversion complete: {msg.result.output_path}")
                    add_terminal_log("Conversion complete!", "success")
                    
                    # Save to Library Database
                    try:
                        from modules.storage.database import Database
                        db = Database()
                        book_id = db.create_book(
                            title=msg.result.title,
                            author=msg.result.author,
                            source_path=st.session_state.current_file,
                            source_type=Path(st.session_state.current_file).suffix.lstrip(".").lower(),
                            total_chapters=len(msg.result.chapters),
                        )
                        for ch in msg.result.chapters:
                            db.create_chapter(
                                book_id=book_id,
                                chapter_number=ch.chapter_number,
                                title=ch.chapter_title,
                                duration_ms=ch.duration_ms,
                                mp3_path=str(ch.mp3_path) if ch.mp3_path else None,
                            )
                        add_log("added to library")
                    except Exception as e:
                        add_log(f"database error: {e}")
                elif msg.result.error == "Cancelled":
                    st.session_state.status = "cancelled"
                    add_log("conversion cancelled")
                else:
                    st.session_state.status = "error"
                    error_msg = msg.result.error or "unknown error"
                    add_log(f"conversion failed: {error_msg}")
                    add_terminal_log(f"Conversion failed: {error_msg}", "error")
            
            st.session_state.conversion_thread = None


def start_conversion(uploaded_file, voice: str, speed: float):
    """
    Start a background conversion.
    """
    from modules.pipeline.orchestrator import (
        ConversionPipeline,
        PipelineConfig,
    )
    from modules.ui.terminal import add_terminal_log
    from modules.ui.conversion import save_uploaded_file
    
    st.session_state.status = "processing"
    st.session_state.processing_stage = "ingesting"
    st.session_state.conversion_cancelled = False
    st.session_state.thread_error = None
    st.session_state.conversion_result = None
    st.session_state.message_queue = Queue()  # Reset queue
    
    add_log("starting conversion...")
    add_log(f"voice: {voice}, speed: {speed}x")
    add_terminal_log(f"Starting conversion with voice: {voice}", "process")
    
    # Get reference to message queue for thread callbacks
    msg_queue = st.session_state.message_queue
    
    # Define verbose callback - puts messages in queue instead of direct session access
    def on_verbose(msg, msg_type):
        msg_queue.put(LogMessage(message=msg, msg_type=msg_type))
        
        # Detect model loading/unloading from messages
        if "text cleaner" in msg.lower() or "loading cleaner" in msg.lower():
            msg_queue.put(ModelStatusMessage(model_type="cleaner", is_loaded=True))
        elif "tts" in msg.lower() and "model" in msg.lower() and "loading" in msg.lower():
            msg_queue.put(ModelStatusMessage(model_type="tts", is_loaded=True))
        elif "unloaded" in msg.lower():
            if "cleaner" in msg.lower():
                msg_queue.put(ModelStatusMessage(model_type="cleaner", is_loaded=False))
            elif "tts" in msg.lower():
                msg_queue.put(ModelStatusMessage(model_type="tts", is_loaded=False))
    
    # Progress callback - puts messages in queue
    def on_progress(stage, chapter_idx, total_chapters, chunk_idx, total_chunks, message, eta):
        msg_queue.put(ProgressMessage(
            stage=stage,
            chapter_idx=chapter_idx,
            total_chapters=total_chapters,
            chunk_idx=chunk_idx,
            total_chunks=total_chunks,
            message=message,
            eta=eta,
        ))
    
    # Save file and create pipeline
    source_path = save_uploaded_file(uploaded_file, uploaded_file.name)
    
    config = PipelineConfig(
        voice=voice,
        speed=speed,
        output_dir=Path("output"),
        temp_dir=Path("temp"),
    )
    
    pipeline = ConversionPipeline(
        config=config,
        progress_callback=on_progress,
        verbose_callback=on_verbose,
    )
    
    # Store pipeline for cancellation
    st.session_state.active_pipeline = pipeline
    
    # Start thread
    st.session_state.thread_running = True
    conversion_thread = threading.Thread(
        target=run_conversion_in_thread,
        args=(pipeline, source_path, msg_queue),
        daemon=True,
    )
    conversion_thread.start()
    st.session_state.conversion_thread = conversion_thread
    st.session_state.thread_running = True
    
    add_log("conversion started in background thread")
    add_terminal_log("Conversion running in background...", "process")


def stop_conversion():
    """
    Stop the running conversion.
    """
    from modules.ui.terminal import add_terminal_log
    from modules.ui.progress import request_cancellation, clear_cancellation
    
    if st.session_state.active_pipeline:
        st.session_state.active_pipeline.cancel()
    
    request_cancellation()
    st.session_state.conversion_cancelled = True
    st.session_state.status = "idle"
    st.session_state.active_model = None
    add_log("conversion cancellation requested...")
    add_terminal_log("Conversion cancelled by user", "warning")
    
    # Don't clean up thread state immediately - let it finish naturally
    # The thread will check cancellation and exit cleanly


# ============================================
# HEADER STRIP
# ============================================
header_col1, header_col2, header_col3 = st.columns([1, 2, 1])
with header_col1:
    st.markdown("")
with header_col2:
    st.markdown(
        "<h1 style='text-align: center; border-bottom: none;'>AUDIOBOOK_CREATOR_V1.0</h1>",
        unsafe_allow_html=True,
    )
with header_col3:
    status_text = st.session_state.status.upper()
    st.markdown(
        f"<p style='text-align: right; margin-top: 12px; font-family: var(--font-mono);'>"
        f"<span style='color: var(--text-dim); text-transform: lowercase;'>status:</span> "
        f"<span style='color: var(--text-main);'>{status_text}</span></p>",
        unsafe_allow_html=True,
    )

st.markdown("---")

# ============================================
# SIDEBAR
# ============================================
with st.sidebar:
    # ==========================================
    # SECTION 1: NAVIGATION
    # ==========================================
    st.markdown("### NAVIGATION")
    st.markdown("")

    nav_col1, nav_col2 = st.columns(2)
    with nav_col1:
        if st.button("UPLOAD", key="nav_upload", use_container_width=True):
            st.session_state.view = "upload"
            st.rerun()
        if st.button("LIBRARY", key="nav_library", use_container_width=True):
            st.session_state.view = "library"
            st.rerun()
    with nav_col2:
        if st.button("PLAY", key="nav_play", use_container_width=True):
            st.session_state.view = "play"
            st.rerun()
        if st.button("EXPLORER", key="nav_checklist", use_container_width=True):
            st.session_state.view = "checklist"
            st.rerun()

    st.markdown("---")
    
    # ==========================================
    # SECTION 2: VOICE SETTINGS (PRE-CONVERSION)
    # ==========================================
    st.markdown("### VOICE SETTINGS")
    st.markdown("<small>configure before starting conversion</small>", 
                unsafe_allow_html=True)
    st.markdown("")

    # Voice options with descriptions
    voice_options = {
        "am_adam": "Adam (American Male)",
        "af_bella": "Bella (American Female)",
        "am_michael": "Michael (American Male)",
        "af_sarah": "Sarah (American Female)",
        "bf_emma": "Emma (British Female)",
        "bm_george": "George (British Male)",
    }
    
    voice_descriptions = {
        "am_adam": "deep, authoritative",
        "af_bella": "warm, conversational",
        "am_michael": "friendly, casual",
        "af_sarah": "professional, clear",
        "bf_emma": "refined, articulate",
        "bm_george": "classic, distinguished",
    }

    # Voice selection
    st.markdown("<small>**SELECT VOICE:**</small>", unsafe_allow_html=True)
    voice = st.selectbox(
        "voice",
        options=list(voice_options.keys()),
        format_func=lambda x: f"{voice_options[x]} - {voice_descriptions[x]}",
        index=list(voice_options.keys()).index(st.session_state.selected_voice),
        label_visibility="collapsed",
        key="voice_select",
        disabled=st.session_state.status == "processing",
    )
    st.session_state.selected_voice = voice
    st.markdown(f"<small style='color: var(--text-dim);'>{voice_descriptions[voice]}</small>", 
                unsafe_allow_html=True)

    st.markdown("")
    
    # Speed selection
    st.markdown("<small>**SPEECH SPEED:**</small>", unsafe_allow_html=True)
    speed = st.slider(
        "speed",
        min_value=0.5,
        max_value=2.0,
        value=st.session_state.selected_speed,
        step=0.1,
        label_visibility="collapsed",
        key="speed_slider",
        disabled=st.session_state.status == "processing",
    )
    st.session_state.selected_speed = speed
    st.markdown(f"<small>`{speed}x` speed</small>", unsafe_allow_html=True)

    st.markdown("---")

    # ==========================================
    # SECTION 3: SYSTEM MONITOR
    # ==========================================
    st.markdown("### SYSTEM MONITOR")
    render_system_stats()


# ============================================
# MAIN CONTENT AREA - VIEW ROUTING
# ============================================

# CHECKLIST/EXPLORER VIEW
if st.session_state.view == "checklist":
    render_checklist_view()

# LIBRARY VIEW (placeholder for future implementation)
elif st.session_state.view == "library":
    st.markdown("### LIBRARY")
    st.markdown("_Library view coming soon. Use Explorer for now._")
    st.info("The new EXPLORER view is now available! Click EXPLORER in the sidebar.")

# UPLOAD/CONVERT VIEW (default)
if st.session_state.view in ("upload", "play"):
    main_col1, main_col2 = st.columns([2, 1])

    with main_col2:
        # Progress Section
        st.markdown("### PROGRESS")
        init_progress_state()
        progress_placeholder = st.empty()
        if st.session_state.current_file:
            with progress_placeholder.container():
                render_chapter_progress()
        else:
            with progress_placeholder.container():
                st.markdown("_awaiting file_")

        st.markdown("---")

        # Processing Info
        st.markdown("### PROCESSING")
        status_placeholder = st.empty()
        with status_placeholder.container():
            render_stage_indicator()

        st.markdown("---")

        # Parsing Progress - Shows text extraction progress
        st.markdown("### PARSING PROGRESS")
        parsing_placeholder = st.empty()
        with parsing_placeholder.container():
            if (
                st.session_state.processing_stage == "ingesting"
                or st.session_state.processing_stage == "parsing"
            ):
                progress = get_progress()
                if progress.chapters:
                    parsed_count = sum(1 for ch in progress.chapters if ch.is_parsed)
                    total_count = len(progress.chapters)
                    parse_pct = parsed_count / total_count if total_count > 0 else 0
                    st.markdown(
                        f"**extracting text:** `{parsed_count}/{total_count}` chapters"
                    )
                    st.progress(parse_pct)
                else:
                    st.markdown("_parsing document..._")
                    st.progress(0.1)
            else:
                st.markdown("_waiting to parse_")

        st.markdown("---")

        # Model Status - Shows both TTS and Cleaner models
        st.markdown("### MODELS")

        # TTS Model
        if st.session_state.tts_model_loaded:
            tts_indicator = "<span style='color: #00FF00;'>[ON]</span>"
            tts_status = "loaded"
        else:
            tts_indicator = "<span style='color: #555555;'>[OFF]</span>"
            tts_status = "standby"

        # Highlight if active
        tts_active = st.session_state.active_model == "tts"
        tts_highlight = "<b>" if tts_active else ""
        tts_highlight_end = "</b>" if tts_active else ""

        st.markdown(
            f"{tts_indicator} {tts_highlight}TTS:{tts_highlight_end} `{st.session_state.tts_model_name.split('/')[-1]}`<br>"
            f"<small>status: `{tts_status}`</small>",
            unsafe_allow_html=True,
        )

        st.markdown("")

        # Cleaner Model
        if st.session_state.cleaner_model_loaded:
            cleaner_indicator = "<span style='color: #00FF00;'>[ON]</span>"
            cleaner_status = "loaded"
        else:
            cleaner_indicator = "<span style='color: #555555;'>[OFF]</span>"
            cleaner_status = "standby"

        # Highlight if active
        cleaner_active = st.session_state.active_model == "cleaner"
        cleaner_highlight = "<b>" if cleaner_active else ""
        cleaner_highlight_end = "</b>" if cleaner_active else ""

        st.markdown(
            f"{cleaner_indicator} {cleaner_highlight}Cleaner:{cleaner_highlight_end} `{st.session_state.cleaner_model_name.split('/')[-1]}`<br>"
            f"<small>status: `{cleaner_status}`</small>",
            unsafe_allow_html=True,
        )

        # Show active model indicator
        if st.session_state.active_model:
            st.markdown("")
            st.markdown(
                f"<small><span style='color: #FFB000;'>&gt;</span> active: `{st.session_state.active_model}`</small>",
                unsafe_allow_html=True,
            )

    with main_col1:
        # File Upload Section
        st.markdown("### SOURCE FILE")
        uploaded_file = st.file_uploader(
            "upload pdf or epub",
            type=["pdf", "epub"],
            label_visibility="collapsed",
            help="Drag and drop a PDF or EPUB file",
        )

        if uploaded_file:
            st.session_state.current_file = uploaded_file.name
            st.session_state.status = "ready"
            add_log(f"file loaded: {uploaded_file.name}")
            st.markdown(f"**loaded:** `{uploaded_file.name}`")

            # Initialize conversion state
            init_conversion_state()

            # Voice confirmation display
            st.markdown("")
            st.markdown(
                f"**voice:** `{st.session_state.selected_voice}` | **speed:** `{st.session_state.selected_speed}x`"
            )

            # Conversion Settings - Voice selection BEFORE conversion
            st.markdown("")
            st.markdown("---")
            st.markdown("### CONVERSION SETTINGS")
            
            # Show current settings
            settings_col1, settings_col2 = st.columns(2)
            with settings_col1:
                st.markdown(f"**voice:** `{st.session_state.selected_voice}`")
            with settings_col2:
                st.markdown(f"**speed:** `{st.session_state.selected_speed}x`")
            
            # Voice preview (before conversion)
            if st.button("🔊 preview voice", use_container_width=True, key="preview_before"):
                add_log(f"generating preview: {st.session_state.selected_voice}")
                preview_text = (
                    "A few light taps upon the pane made him turn to the window. "
                    "It had begun to snow again."
                )
                try:
                    from modules.tts.engine import TTSEngine
                    import tempfile
                    import base64
                    import soundfile as sf

                    with st.spinner("generating preview..."):
                        engine = TTSEngine()
                        engine.load_model()
                        audio = engine.synthesize(
                            preview_text, voice=st.session_state.selected_voice, 
                            speed=st.session_state.selected_speed
                        )

                        # Save to temp file and create audio player
                        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                            sf.write(f.name, audio, 24000)

                            # Read and encode for HTML audio
                            with open(f.name, "rb") as audio_file:
                                audio_bytes = audio_file.read()
                                audio_b64 = base64.b64encode(audio_bytes).decode()
                                st.markdown(
                                    f'<audio autoplay controls src="data:audio/wav;base64,{audio_b64}" '
                                    f'style="width:100%;height:30px;"></audio>',
                                    unsafe_allow_html=True,
                                )

                        engine.unload_model()
                        add_log(f"preview complete")
                except Exception as e:
                    add_log(f"preview error: {str(e)}")
                    st.error(f"Preview failed: {e}")
            
            st.markdown("")
            
            # Conversion control buttons
            # Check conversion status at start of each run
            check_conversion_status()
            
            # Show STOP button if processing
            if st.session_state.status == "processing":
                if st.button(
                    "⏹ STOP CONVERSION", use_container_width=True, type="secondary"
                ):
                    stop_conversion()
                    st.rerun()
                
                # Show processing indicator
                st.info("⏳ Conversion in progress... (check terminal for details)")
                
                # Auto-refresh to check status
                time.sleep(0.5)
                st.rerun()
            else:
                # START CONVERSION BUTTON
                start_disabled = st.session_state.status in ("processing",)
                if st.button(
                    "▶ START CONVERSION", 
                    use_container_width=True, 
                    type="primary",
                    disabled=start_disabled,
                ):
                    start_conversion(
                        uploaded_file, 
                        st.session_state.selected_voice, 
                        st.session_state.selected_speed
                    )
                    st.rerun()

            # Show download button if conversion complete
            if (
                st.session_state.get("conversion_result")
                and st.session_state.conversion_result.success
            ):
                result = st.session_state.conversion_result
                if result.output_path and result.output_path.exists():
                    with open(result.output_path, "rb") as f:
                        st.download_button(
                            label="↓ DOWNLOAD AUDIOBOOK",
                            data=f.read(),
                            file_name=result.output_path.name,
                            mime="audio/mp4",
                            use_container_width=True,
                        )

                    st.markdown("")
                    with st.expander("download chapters"):
                        for ch in result.chapters:
                            if ch.mp3_path and ch.mp3_path.exists():
                                with open(ch.mp3_path, "rb") as f:
                                    st.download_button(
                                        label=f"{ch.chapter_number:02d}. {ch.chapter_title}",
                                        data=f.read(),
                                        file_name=ch.mp3_path.name,
                                        mime="audio/mpeg",
                                        key=f"dl_ch_{ch.chapter_number}",
                                        use_container_width=True,
                                    )

        st.markdown("---")

        # Waveform Visualizer
        st.markdown("### WAVEFORM")
        is_playing = st.session_state.status == "playing"
        render_waveform_component(
            is_playing=is_playing, playback_position=st.session_state.progress
        )

        st.markdown("---")

        # Control Buttons
        btn_col1, btn_col2, btn_col3, btn_col4 = st.columns(4)
        with btn_col1:
            if st.button("play", use_container_width=True):
                st.session_state.status = "playing"
                add_log("playback started")
        with btn_col2:
            if st.button("pause", use_container_width=True):
                st.session_state.status = "paused"
                add_log("playback paused")
        with btn_col3:
            if st.button("stop", use_container_width=True):
                st.session_state.status = "idle"
                add_log("playback stopped")
        with btn_col4:
            if st.button("export", use_container_width=True):
                st.session_state.status = "exporting"
                add_log("export started...")

# ============================================
# LOG WINDOW (Bottom) - Collapsible
# ============================================
# Only show terminal/logs for upload/play views
if st.session_state.view in ("upload", "play"):
    st.markdown("---")
    tabs = st.tabs(["TERMINAL", "LOGS"])

    with tabs[0]:
        # Industrial Moss Terminal
        terminal_placeholder = st.empty()
        with terminal_placeholder.container():
            # Use new Industrial Moss terminal
            render_industrial_terminal(max_height=400)

    with tabs[1]:
        # Classic Log
        if st.session_state.log_messages:
            for msg in st.session_state.log_messages[-20:]:
                st.markdown(f"`> {msg}`")
        else:
            st.markdown("`> system ready`")


# ============================================
# FOOTER
# ============================================
if st.session_state.view in ("upload", "play", "library"):
    st.markdown("---")
    st.markdown(
        "<div style='text-align: center; color: var(--text-faded); font-size: 10px; font-family: var(--font-mono);'>"
        "AUDIOBOOK_CREATOR_V1.0 | OPTIMIZED_FOR_APPLE_SILICON | 2026"
        "</div>",
        unsafe_allow_html=True,
    )
