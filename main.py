"""
Audiobook Creator - Main Application
=====================================
A Python-based audiobook creator optimized for Apple Silicon (M1/M2/M3).
Converts PDF and EPUB files into high-quality audiobooks.

UI: Streamlit with "Amber & Obsidian" retro terminal theme
"""

import streamlit as st
from pathlib import Path

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
from modules.ui.monitor import render_system_stats

# ============================================
# PAGE CONFIGURATION
# ============================================
st.set_page_config(
    page_title="audiobook_creator_v1.0",
    page_icon="📖",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================
# LOAD CUSTOM CSS
# ============================================
def load_css():
    """Load the retro Amber & Obsidian theme."""
    css_path = Path(__file__).parent / "assets" / "css" / "retro.css"
    if css_path.exists():
        with open(css_path) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    else:
        # Fallback inline styles if CSS file not found
        st.markdown(
            """
        <style>
            :root {
                --void: #0A0A0B;
                --ink: #111113;
                --rust: #9A3412;
                --forest: #166534;
            }
            .stApp { background-color: #0A0A0B; color: #E4E4E7; }
        </style>
        """,
            unsafe_allow_html=True,
        )


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


def add_log(message: str):
    """Add a message to the log window."""
    st.session_state.log_messages.append(message)
    # Keep only last 50 messages
    if len(st.session_state.log_messages) > 50:
        st.session_state.log_messages = st.session_state.log_messages[-50:]


# ============================================
# HEADER STRIP
# ============================================
header_col1, header_col2, header_col3 = st.columns([1, 2, 1])
with header_col1:
    st.markdown("")
with header_col2:
    st.markdown(
        "<h1 style='text-align: center;'>audiobook_creator_v1.0</h1>",
        unsafe_allow_html=True,
    )
with header_col3:
    status_text = st.session_state.status.upper()
    st.markdown(
        f"<p style='text-align: right; margin-top: 12px;'><strong>status:</strong> {status_text}</p>",
        unsafe_allow_html=True,
    )

st.markdown("---")

# ============================================
# SIDEBAR
# ============================================
with st.sidebar:
    st.markdown("### [ navigation ]")
    st.markdown("")

    # Upload button
    if st.button("+ upload", key="nav_upload", use_container_width=True):
        st.session_state.view = "upload"

    # Play button
    if st.button("> play", key="nav_play", use_container_width=True):
        st.session_state.view = "play"

    # Library button
    if st.button("# library", key="nav_library", use_container_width=True):
        st.session_state.view = "library"

    st.markdown("---")

    # Voice selection with descriptions
    st.markdown("### [ voice engine ]")

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
    st.markdown("### [ speed ]")
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
    st.markdown("### [ current settings ]")
    st.markdown(f"voice: `{voice}`")
    st.markdown(f"speed: `{speed}x`")

    st.markdown("---")

    # System Monitor - CPU/RAM stats
    st.markdown("### [ system monitor ]")
    render_system_stats()


# ============================================
# MAIN CONTENT AREA
# ============================================
# MAIN CONTENT AREA
# ============================================
main_col1, main_col2 = st.columns([2, 1])

with main_col2:
    # Progress Section
    st.markdown("### [ progress ]")
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
    st.markdown("### [ processing ]")
    status_placeholder = st.empty()
    with status_placeholder.container():
        render_stage_indicator()

    st.markdown("---")

    # Parsing Progress - Shows text extraction progress
    st.markdown("### [ parsing progress ]")
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
    st.markdown("### [ models ]")

    # TTS Model
    if st.session_state.tts_model_loaded:
        tts_indicator = "<span style='color: #00FF00;'>●</span>"
        tts_status = "loaded"
    else:
        tts_indicator = "<span style='color: #555555;'>○</span>"
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
        cleaner_indicator = "<span style='color: #00FF00;'>●</span>"
        cleaner_status = "loaded"
    else:
        cleaner_indicator = "<span style='color: #555555;'>○</span>"
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
            f"<small><span style='color: #FFB000;'>▶</span> active: `{st.session_state.active_model}`</small>",
            unsafe_allow_html=True,
        )

with main_col1:
    # File Upload Section
    st.markdown("### [ source file ]")
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
                "⏹ STOP CONVERSION", use_container_width=True, type="secondary"
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
                "▶ START CONVERSION", use_container_width=True, type="primary"
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

                # Run the conversion pipeline
                with st.spinner("Converting... this may take a while"):
                    # Define callbacks
                    def on_verbose(msg, type):
                        add_terminal_log(msg, type)

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

                    # Save file and run conversion
                    from modules.ui.conversion import save_uploaded_file

                    source_path = save_uploaded_file(uploaded_file, uploaded_file.name)

                    pipeline = ConversionPipeline(
                        config=config,
                        progress_callback=on_progress,
                        verbose_callback=on_verbose,
                    )

                    result = pipeline.convert(source_path)
                    st.session_state.conversion_result = result

                # Reset active model
                st.session_state.active_model = None

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
    st.markdown("### [ waveform ]")
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
st.markdown("---")
tabs = st.tabs(["[ terminal ]", "[ logs ]"])

with tabs[0]:
    # Live Matrix Terminal
    terminal_placeholder = st.empty()
    with terminal_placeholder.container():
        render_terminal_view()

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
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #555555; font-size: 10px;'>"
    "audiobook_creator v1.0 | optimized for apple silicon | 2026"
    "</div>",
    unsafe_allow_html=True,
)
