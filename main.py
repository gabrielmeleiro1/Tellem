"""
Audiobook Creator - Main Application
=====================================
A Python-based audiobook creator optimized for Apple Silicon (M1/M2/M3).
Converts PDF and EPUB files into high-quality audiobooks.

UI: Streamlit with "Amber & Obsidian" retro terminal theme
"""

import streamlit as st
from pathlib import Path

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
        st.markdown("""
        <style>
            :root {
                --obsidian: #0A0A0A;
                --amber: #FFB000;
            }
            .stApp { background-color: #0A0A0A; color: #FFB000; }
        </style>
        """, unsafe_allow_html=True)

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

def add_log(message: str):
    """Add a message to the log window."""
    st.session_state.log_messages.append(message)
    # Keep only last 50 messages
    if len(st.session_state.log_messages) > 50:
        st.session_state.log_messages = st.session_state.log_messages[-50:]

# ============================================
# HEADER STRIP
# ============================================
header_col1, header_col2 = st.columns([3, 1])
with header_col1:
    st.markdown("# audiobook_creator_v1.0")
with header_col2:
    status_text = st.session_state.status.upper()
    st.markdown(f"**status:** {status_text}")

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
    
    # Voice selection
    st.markdown("### [ voice engine ]")
    voice = st.selectbox(
        "voice",
        options=["am_adam", "af_bella", "bf_emma", "bm_george"],
        label_visibility="collapsed"
    )
    
    # Speed slider
    st.markdown("### [ speed ]")
    speed = st.slider(
        "speed",
        min_value=0.5,
        max_value=2.0,
        value=1.0,
        step=0.1,
        label_visibility="collapsed"
    )
    st.markdown(f"`{speed}x`")
    
    st.markdown("---")
    
    # Stats
    st.markdown("### [ stats ]")
    st.markdown(f"voice: `{voice}`")
    st.markdown(f"speed: `{speed}x`")

# ============================================
# MAIN CONTENT AREA
# ============================================
main_col1, main_col2 = st.columns([2, 1])

with main_col1:
    # File Upload Section
    st.markdown("### [ source file ]")
    uploaded_file = st.file_uploader(
        "upload pdf or epub",
        type=["pdf", "epub"],
        label_visibility="collapsed",
        help="Drag and drop a PDF or EPUB file"
    )
    
    if uploaded_file:
        st.session_state.current_file = uploaded_file.name
        st.session_state.status = "ready"
        add_log(f"file loaded: {uploaded_file.name}")
        st.markdown(f"**loaded:** `{uploaded_file.name}`")
    
    st.markdown("---")
    
    # Text Preview Section
    st.markdown("### [ text preview ]")
    preview_container = st.container()
    with preview_container:
        if uploaded_file:
            st.markdown("```")
            st.markdown("the first lines of your book will appear here...")
            st.markdown("chapter detection and parsing in progress...")
            st.markdown("```")
        else:
            st.markdown("_no file loaded_")
    
    st.markdown("---")
    
    # Waveform Placeholder
    st.markdown("### [ waveform ]")
    waveform_placeholder = st.empty()
    with waveform_placeholder:
        # ASCII waveform visualization
        waveform = "▁▃▅▇█▇▅▃▁▃▅▇█▇▅▃▁▃▅▇█▇▅▃▁▃▅▇█▇▅▃▁▃▅▇█▇▅▃▁"
        st.markdown(f"`{waveform}`")
    
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

with main_col2:
    # Progress Section
    st.markdown("### [ progress ]")
    if st.session_state.current_file:
        st.progress(st.session_state.progress)
        st.markdown(f"chapter: `1/12`")
        st.markdown(f"progress: `{int(st.session_state.progress * 100)}%`")
    else:
        st.markdown("_awaiting file_")
    
    st.markdown("---")
    
    # Processing Info
    st.markdown("### [ processing ]")
    st.markdown(f"stage: `idle`")
    st.markdown(f"eta: `--:--`")

# ============================================
# LOG WINDOW (Bottom)
# ============================================
st.markdown("---")
st.markdown("### [ log ]")
log_container = st.container()
with log_container:
    if st.session_state.log_messages:
        for msg in st.session_state.log_messages[-10:]:
            st.markdown(f"`> {msg}`")
    else:
        st.markdown("`> system ready`")
        st.markdown("`> awaiting file upload...`")

# ============================================
# FOOTER
# ============================================
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #555555; font-size: 10px;'>"
    "audiobook_creator v1.0 | optimized for apple silicon | 2026"
    "</div>",
    unsafe_allow_html=True
)
