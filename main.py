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

# View state for navigation
if "view" not in st.session_state:
    st.session_state.view = "upload"  # upload, library, checklist


def add_log(message: str):
    """Add a message to the log window."""
    st.session_state.log_messages.append(message)
    # Keep only last 50 messages
    if len(st.session_state.log_messages) > 50:
        st.session_state.log_messages = st.session_state.log_messages[-50:]


# ============================================
# THREADING FOR BACKGROUND CONVERSION
# ============================================
def run_conversion_in_thread(pipeline, source_path):
    """
    Run the conversion pipeline in a background thread.
    Stores result or error in session state.
    """
    try:
        result = pipeline.convert(source_path)
        st.session_state.conversion_result = result
        st.session_state.thread_running = False
    except Exception as e:
        st.session_state.thread_error = str(e)
        st.session_state.thread_running = False


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
    st.markdown("### NAVIGATION")
    st.markdown("")

    # Upload button
    if st.button("UPLOAD", key="nav_upload", use_container_width=True):
        st.session_state.view = "upload"

    # Play button
    if st.button("PLAY", key="nav_play", use_container_width=True):
        st.session_state.view = "play"

    # Library button
    if st.button("LIBRARY", key="nav_library", use_container_width=True):
        st.session_state.view = "library"
    
    # Checklist/Explorer button
    if st.button("EXPLORER", key="nav_checklist", use_container_width=True):
        st.session_state.view = "checklist"

    st.markdown("---")

    # Voice selection with descriptions
    st.markdown("### VOICE ENGINE")

    # Voice options with descriptions
    voice_options = {
        "am_adam": "Adam (American Male) - deep, authoritative",
        "af_bella": "Bella (American Female) - warm, conversational",
        "am_michael": "Michael (American Male) - friendly, casual",
        "af_sarah": "Sarah (American Female) - professional, clear",
        "bf_emma": "Emma (British Female) - refined, articulate",
        "bm_george": "George (British Male) - classic, distinguished",
    }

    voice = st.selectbox(
        "voice",
        options=list(voice_options.keys()),
        format_func=lambda x: voice_options[x],
        index=list(voice_options.keys()).index(st.session_state.selected_voice),
        label_visibility="collapsed",
        key="voice_select",
    )
    st.session_state.selected_voice = voice

    # Preview button - plays actual TTS sample
    if st.button("preview", key="voice_preview", use_container_width=True):
        add_log(f"generating preview: {voice}")
        preview_text = (
            "A few light taps upon the pane made him turn to the window. "
            "It had begun to snow again. He watched sleepily the flakes, "
            "silver and dark, falling obliquely against the lamplight."
        )
        try:
            from modules.tts.engine import TTSEngine
            import tempfile
            import base64

            with st.spinner("Generating preview..."):
                engine = TTSEngine()
                engine.load_model()
                audio = engine.synthesize(
                    preview_text, voice=voice, speed=st.session_state.selected_speed
                )

                # Save to temp file and create audio player
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                    import soundfile as sf

                    sf.write(f.name, audio, 24000)

                    # Read and encode for HTML audio
                    with open(f.name, "rb") as audio_file:
                        audio_bytes = audio_file.read()
                        audio_b64 = base64.b64encode(audio_bytes).decode()
                        st.markdown(
                            f'<audio autoplay controls src="data:audio/wav;base64,{audio_b64}"></audio>',
                            unsafe_allow_html=True,
                        )

                engine.unload_model()
                add_log(f"preview complete: {voice}")
        except Exception as e:
            add_log(f"preview error: {str(e)}")
            st.error(f"Preview failed: {e}")

    # Speed slider
    st.markdown("### SPEED")
    speed = st.slider(
        "speed",
        min_value=0.5,
        max_value=2.0,
        value=st.session_state.selected_speed,
        step=0.1,
        label_visibility="collapsed",
        key="speed_slider",
    )
    st.session_state.selected_speed = speed
    st.markdown(f"`{speed}x`")

    st.markdown("---")

    # Stats
    st.markdown("### CURRENT SETTINGS")
    st.markdown(f"voice: `{voice}`")
    st.markdown(f"speed: `{speed}x`")

    st.markdown("---")

    # System Monitor - CPU/RAM stats
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

            # Conversion control buttons
            st.markdown("")

            # Show STOP button if processing
            if st.session_state.status == "processing":
                if st.button(
                    "[X] STOP CONVERSION", use_container_width=True, type="secondary"
                ):
                    from modules.ui.progress import request_cancellation

                    request_cancellation()
                    st.session_state.conversion_cancelled = True
                    st.session_state.status = "idle"
                    st.session_state.active_model = None
                    add_log("conversion cancellation requested...")
                    add_terminal_log("Conversion cancelled by user", "warning")
                    st.rerun()
            else:
                # START CONVERSION BUTTON
                if st.button(
                    "[>] START CONVERSION", use_container_width=True, type="primary"
                ):
                    st.session_state.status = "processing"
                    st.session_state.processing_stage = "ingesting"
                    st.session_state.conversion_cancelled = False
                    add_log("starting conversion...")
                    add_log(
                        f"voice: {st.session_state.selected_voice}, speed: {st.session_state.selected_speed}x"
                    )
                    add_terminal_log(
                        f"Starting conversion with voice: {st.session_state.selected_voice}",
                        "process",
                    )

                    # Define callbacks (outside thread for session state access)
                    def on_verbose(msg, msg_type):
                        add_terminal_log(msg, msg_type)

                        # Update active model based on log messages
                        if "text cleaner" in msg.lower() or "cleaner" in msg.lower():
                            st.session_state.active_model = "cleaner"
                            st.session_state.cleaner_model_loaded = True
                        elif "tts" in msg.lower() and "model" in msg.lower():
                            st.session_state.active_model = "tts"
                            st.session_state.tts_model_loaded = True
                        elif "unloaded" in msg.lower():
                            # Model was unloaded
                            if "cleaner" in msg.lower():
                                st.session_state.cleaner_model_loaded = False
                            elif "tts" in msg.lower():
                                st.session_state.tts_model_loaded = False

                    # Create pipeline with callbacks
                    from modules.pipeline.orchestrator import (
                        ConversionPipeline,
                        PipelineConfig,
                    )
                    from modules.ui.progress import (
                        set_chapters,
                        update_chapter_progress,
                        set_current_stage,
                        ProcessingStage,
                        request_cancellation,
                        is_cancelled,
                    )

                    # Configure pipeline
                    config = PipelineConfig(
                        voice=st.session_state.selected_voice,
                        speed=st.session_state.selected_speed,
                        output_dir=Path("output"),
                        temp_dir=Path("temp"),
                    )

                    # Progress callback
                    def on_progress(
                        stage,
                        chapter_idx,
                        total_chapters,
                        chunk_idx,
                        total_chunks,
                        message,
                        eta,
                    ):
                        # Map pipeline stage to UI stage
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
                        ui_stage = stage_map.get(stage.value, ProcessingStage.IDLE)
                        set_current_stage(ui_stage)

                        # Update session state for parsing progress
                        if stage.value in ("ingesting", "chunking"):
                            st.session_state.processing_stage = "parsing"
                        else:
                            st.session_state.processing_stage = stage.value

                        # Update chapter progress
                        if total_chapters > 0:
                            # During parsing, mark chapters as parsed
                            if (
                                stage.value == "ingesting"
                                and chapter_idx < total_chapters
                            ):
                                progress = get_progress()
                                if chapter_idx < len(progress.chapters):
                                    progress.chapters[chapter_idx].is_parsed = True

                            update_chapter_progress(
                                chapter_idx=chapter_idx,
                                completed_chunks=chunk_idx,
                                total_chunks=total_chunks,
                                stage=ui_stage,
                            )

                        if message:
                            add_log(message)

                    # Save file before starting thread
                    from modules.ui.conversion import save_uploaded_file

                    source_path = save_uploaded_file(uploaded_file, uploaded_file.name)

                    pipeline = ConversionPipeline(
                        config=config,
                        progress_callback=on_progress,
                        verbose_callback=on_verbose,
                    )

                    # Start conversion in background thread
                    st.session_state.thread_running = True
                    st.session_state.thread_error = None
                    st.session_state.conversion_result = None

                    conversion_thread = threading.Thread(
                        target=run_conversion_in_thread,
                        args=(pipeline, source_path),
                        daemon=True,
                    )
                    conversion_thread.start()
                    st.session_state.conversion_thread = conversion_thread

                    add_log("conversion started in background thread")
                    add_terminal_log("Conversion running in background...", "process")

                    # Poll until thread completes
                    progress_placeholder = st.empty()
                    while st.session_state.thread_running:
                        progress_placeholder.info(
                            "⏳ Converting... (check terminal for real-time updates)"
                        )
                        time.sleep(0.5)
                        st.rerun()

                    # Thread finished - process result
                    progress_placeholder.empty()

                    # Reset active model
                    st.session_state.active_model = None

                    # Check for errors
                    if st.session_state.thread_error:
                        st.session_state.status = "error"
                        add_log(f"conversion failed: {st.session_state.thread_error}")
                        add_terminal_log(f"Conversion failed: {st.session_state.thread_error}", "error")
                        st.rerun()

                    # Get result
                    result = st.session_state.conversion_result

                    if result is None:
                        st.session_state.status = "error"
                        add_log("conversion failed: no result returned")
                        add_terminal_log("Conversion failed: no result returned", "error")
                        st.rerun()

                    if result.success:
                        st.session_state.status = "complete"
                        add_log(f"conversion complete: {result.output_path}")
                        add_terminal_log("Conversion complete!", "success")

                        # Save to Library Database
                        try:
                            db = Database()
                            book_id = db.create_book(
                                title=result.title,
                                author=result.author,
                                source_path=uploaded_file.name,
                                source_type=Path(uploaded_file.name)
                                .suffix.lstrip(".")
                                .lower(),
                                total_chapters=len(result.chapters),
                            )

                            for ch in result.chapters:
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

                    elif result.error == "Cancelled":
                        st.session_state.status = "cancelled"
                        add_log("conversion cancelled")
                    else:
                        st.session_state.status = "error"
                        add_log(f"conversion failed: {result.error}")
                        add_terminal_log(f"Conversion failed: {result.error}", "error")

                    # Clean up thread state
                    st.session_state.conversion_thread = None
                    st.session_state.thread_running = False

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
