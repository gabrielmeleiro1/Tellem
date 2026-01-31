"""
Audio Output Panel
==================
Audio playback and output file information.
"""

from dataclasses import dataclass
from typing import Optional, List, Callable
from pathlib import Path
import streamlit as st
import base64


@dataclass
class AudioOutput:
    """Generated audio output information."""
    filename: str
    path: Path
    duration_seconds: Optional[int] = None
    file_size_bytes: Optional[int] = None
    chapters: Optional[List[str]] = None


@dataclass
class WaveformConfig:
    """Configuration for ASCII waveform display."""
    width: int = 60
    height: int = 8
    block_chars: str = " ▁▂▃▄▅▆▇█"


def _format_file_size(size_bytes: Optional[int]) -> str:
    """Format file size in human-readable format."""
    if size_bytes is None:
        return "--"
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def _format_duration(seconds: Optional[int]) -> str:
    """Format duration as HH:MM:SS."""
    if seconds is None:
        return "--:--:--"
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def generate_ascii_waveform(
    data: Optional[List[float]] = None,
    config: Optional[WaveformConfig] = None
) -> str:
    """
    Generate an ASCII waveform visualization.
    
    Args:
        data: Optional list of amplitude values (0.0 to 1.0)
        config: Waveform configuration
        
    Returns:
        ASCII waveform string
    """
    cfg = config or WaveformConfig()
    
    # Generate sample data if none provided
    if data is None:
        # Generate a simple sine wave pattern
        import math
        data = [
            0.5 + 0.4 * math.sin(2 * math.pi * i / 20) * math.exp(-i / 100)
            for i in range(cfg.width)
        ]
    
    # Normalize data to [0, 1]
    if data:
        max_val = max(data) if max(data) > 0 else 1
        min_val = min(data)
        data = [(val - min_val) / (max_val - min_val) if max_val != min_val else 0.5 for val in data]
    
    # Build waveform
    chars = list(cfg.block_chars)
    num_chars = len(chars)
    
    waveform = ""
    for value in data[:cfg.width]:
        # Map value to character index
        idx = int(value * (num_chars - 1))
        idx = max(0, min(idx, num_chars - 1))
        waveform += chars[idx]
    
    return waveform


def render_waveform(
    data: Optional[List[float]] = None,
    config: Optional[WaveformConfig] = None,
    key: Optional[str] = None
) -> None:
    """
    Render an ASCII waveform visualization.
    
    Args:
        data: Optional list of amplitude values (0.0 to 1.0)
        config: Waveform configuration
        key: Unique key for Streamlit
    """
    waveform = generate_ascii_waveform(data, config)
    
    unique_key = key or "waveform"
    cfg = config or WaveformConfig()
    
    css = f"""
        <style>
        .moss-waveform-{unique_key} {{
            font-family: var(--font-mono);
            font-size: var(--text-sm);
            color: var(--accent-olive);
            letter-spacing: 0;
            white-space: pre;
            line-height: 1;
            overflow-x: auto;
        }}
        </style>
    """
    
    st.markdown(css, unsafe_allow_html=True)
    st.markdown(
        f'<div class="moss-waveform-{unique_key}">{waveform}</div>',
        unsafe_allow_html=True,
    )


def render_output_panel(
    output: Optional[AudioOutput] = None,
    show_waveform: bool = True,
    on_play: Optional[Callable[[], None]] = None,
    on_download: Optional[Callable[[], None]] = None,
    on_delete: Optional[Callable[[], None]] = None,
    key: Optional[str] = None
) -> None:
    """
    Render output panel with waveform visualization.
    
    Layout:
    ┌─ OUTPUT ────────────────────────────────┐
    │                                         │
    │  file:     audiobook.m4b                │
    │  duration: 04:23:15                     │
    │  size:     142 MB                       │
    │                                         │
    │  waveform:                              │
    │  ▂▄▆████▇▆▄▃▂▁▂▄▆▇████▇▆▄▂▁▁▂▄▆▇▆▄▂   │
    │                                         │
    │  [ PLAY ]  [ DOWNLOAD ]  [ DELETE ]     │
    │                                         │
    └─────────────────────────────────────────┘
    
    Args:
        output: Audio output information
        show_waveform: Whether to show waveform
        on_play: Callback when play button is clicked
        on_download: Callback when download button is clicked
        on_delete: Callback when delete button is clicked
        key: Unique key for Streamlit
    """
    unique_key = key or "output_panel"
    
    css = f"""
        <style>
        .moss-output-panel-{unique_key} {{
            background-color: var(--bg-surface);
            border: 1px solid var(--border-color);
            padding: var(--space-md);
        }}
        .moss-output-panel-{unique_key} .moss-panel-title {{
            font-family: var(--font-mono);
            font-size: var(--text-sm);
            font-weight: var(--font-bold);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-main);
            border-bottom: 1px solid var(--border-color);
            padding-bottom: var(--space-sm);
            margin-bottom: var(--space-md);
        }}
        .moss-output-panel-{unique_key} .moss-file-info {{
            font-family: var(--font-mono);
            font-size: var(--text-sm);
            margin-bottom: var(--space-xs);
        }}
        .moss-output-panel-{unique_key} .moss-file-info-label {{
            color: var(--text-dim);
            text-transform: lowercase;
            display: inline-block;
            min-width: 10ch;
        }}
        .moss-output-panel-{unique_key} .moss-file-info-label::after {{
            content: ":";
        }}
        .moss-output-panel-{unique_key} .moss-file-info-value {{
            color: var(--text-main);
        }}
        .moss-output-panel-{unique_key} .moss-waveform-label {{
            font-family: var(--font-mono);
            font-size: var(--text-sm);
            color: var(--text-dim);
            text-transform: lowercase;
            margin-top: var(--space-md);
        }}
        .moss-output-panel-{unique_key} .moss-waveform-label::after {{
            content: ":";
        }}
        .moss-output-panel-{unique_key} .moss-button-row {{
            display: flex;
            gap: var(--space-md);
            margin-top: var(--space-md);
        }}
        .moss-output-panel-{unique_key} .moss-empty-state {{
            font-family: var(--font-mono);
            font-size: var(--text-sm);
            color: var(--text-faded);
            text-align: center;
            padding: var(--space-lg);
        }}
        </style>
    """
    
    st.markdown(css, unsafe_allow_html=True)
    st.markdown(
        f'<div class="moss-output-panel-{unique_key}">'
        f'<div class="moss-panel-title">output</div>',
        unsafe_allow_html=True,
    )
    
    if output is None:
        st.markdown(
            '<div class="moss-empty-state">no output file</div>',
            unsafe_allow_html=True,
        )
    else:
        # File info
        st.markdown(
            f'<div class="moss-file-info">'
            f'<span class="moss-file-info-label">file</span>'
            f'<span class="moss-file-info-value">{output.filename}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="moss-file-info">'
            f'<span class="moss-file-info-label">duration</span>'
            f'<span class="moss-file-info-value">{_format_duration(output.duration_seconds)}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="moss-file-info">'
            f'<span class="moss-file-info-label">size</span>'
            f'<span class="moss-file-info-value">{_format_file_size(output.file_size_bytes)}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
        
        # Waveform
        if show_waveform:
            st.markdown(
                '<div class="moss-waveform-label">waveform</div>',
                unsafe_allow_html=True,
            )
            render_waveform(key=f"{unique_key}_waveform")
        
        # Audio player if file exists
        if output.path and output.path.exists():
            try:
                st.audio(str(output.path))
            except Exception:
                pass  # Audio playback not available
        
        # Action buttons
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if on_play and st.button("play", key=f"{unique_key}_play"):
                on_play()
        
        with col2:
            if on_download and output and output.path and output.path.exists():
                with open(output.path, 'rb') as f:
                    data = f.read()
                st.download_button(
                    label="download",
                    data=data,
                    file_name=output.filename,
                    mime="audio/mp4",
                    key=f"{unique_key}_download",
                )
        
        with col3:
            if on_delete and st.button("delete", key=f"{unique_key}_delete"):
                on_delete()
    
    st.markdown('</div>', unsafe_allow_html=True)


def render_output_panel_simple(
    output: Optional[AudioOutput] = None,
    key: Optional[str] = None
) -> None:
    """
    Simplified output panel with just file info and audio player.
    
    Args:
        output: Audio output information
        key: Unique key for Streamlit
    """
    unique_key = key or "output_simple"
    
    if output is None:
        st.markdown("*no output file*")
        return
    
    # File info
    st.markdown(f"**file:** {output.filename}")
    st.markdown(f"**duration:** {_format_duration(output.duration_seconds)}")
    st.markdown(f"**size:** {_format_file_size(output.file_size_bytes)}")
    
    # Audio player
    if output.path and output.path.exists():
        try:
            st.audio(str(output.path))
        except Exception:
            st.markdown("*audio playback not available*")
    
    # Download button
    if output.path and output.path.exists():
        with open(output.path, 'rb') as f:
            data = f.read()
        st.download_button(
            label="download",
            data=data,
            file_name=output.filename,
            mime="audio/mp4",
            key=f"{unique_key}_download",
        )
