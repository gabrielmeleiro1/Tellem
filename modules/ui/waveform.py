"""
Waveform Visualizer
===================
Blocky oscilloscope-style waveform display for audio playback.
Includes real-time generation visualization and seeking capabilities.
"""

import streamlit as st
import numpy as np
from typing import Optional, Callable, Tuple
from dataclasses import dataclass
from enum import Enum


# Block characters for oscilloscope visualization (bottom to top)
BLOCKS = " ▁▂▃▄▅▆▇█"


class PlaybackState(Enum):
    """Audio playback state."""
    STOPPED = "stopped"
    PLAYING = "playing"
    PAUSED = "paused"
    BUFFERING = "buffering"


@dataclass
class WaveformConfig:
    """Configuration for waveform visualization."""
    num_bars: int = 40
    color: str = "#FFB000"
    cursor_color: str = "#FFFFFF"
    height_px: int = 60
    show_timescale: bool = True
    enable_seeking: bool = True
    animate_cursor: bool = True


def generate_waveform_data(num_bars: int = 40, seed: Optional[int] = None) -> list[float]:
    """
    Generate random waveform data for visualization.
    Returns values between 0.0 and 1.0.
    """
    if seed is not None:
        np.random.seed(seed)
    
    # Generate smooth waveform using sine waves with noise
    x = np.linspace(0, 4 * np.pi, num_bars)
    base = (np.sin(x) + 1) / 2  # Normalize to 0-1
    noise = np.random.random(num_bars) * 0.3
    data = np.clip(base + noise - 0.15, 0, 1)
    return data.tolist()


def generate_waveform_from_audio(audio_data: np.ndarray, num_bars: int = 40) -> list[float]:
    """
    Generate waveform data from actual audio samples.
    Returns values between 0.0 and 1.0.
    """
    if len(audio_data) == 0:
        return [0.0] * num_bars
    
    # Handle stereo by converting to mono
    if len(audio_data.shape) > 1:
        audio_data = np.mean(audio_data, axis=1)
    
    # Chunk audio into segments
    chunk_size = len(audio_data) // num_bars
    if chunk_size == 0:
        chunk_size = 1
    
    waveform = []
    for i in range(num_bars):
        start = i * chunk_size
        end = min(start + chunk_size, len(audio_data))
        chunk = audio_data[start:end]
        
        # Calculate RMS for this chunk
        if len(chunk) > 0:
            rms = np.sqrt(np.mean(chunk.astype(float) ** 2))
            # Normalize (assuming 16-bit audio)
            normalized = min(rms / 16384, 1.0)
            waveform.append(normalized)
        else:
            waveform.append(0.0)
    
    return waveform


def generate_waveform_during_synthesis(
    current_chunk: int,
    total_chunks: int,
    chunk_amplitudes: Optional[list[float]] = None,
    num_bars: int = 40
) -> Tuple[list[float], float]:
    """
    Generate waveform data showing synthesis progress.
    
    Args:
        current_chunk: Current chunk being synthesized (0-indexed)
        total_chunks: Total number of chunks
        chunk_amplitudes: Optional list of amplitudes for completed chunks
        num_bars: Number of bars in waveform
    
    Returns:
        Tuple of (waveform_data, progress_ratio)
    """
    progress = current_chunk / max(total_chunks, 1)
    
    if chunk_amplitudes is None:
        # Generate simulated amplitudes based on typical audio patterns
        np.random.seed(42)  # Consistent pattern
        chunk_amplitudes = []
        for i in range(total_chunks):
            # Simulate varying amplitudes
            base = 0.3 + 0.4 * np.sin(i * 0.5)
            noise = np.random.random() * 0.3
            chunk_amplitudes.append(min(max(base + noise, 0.0), 1.0))
    
    # Map chunks to waveform bars
    bars_per_chunk = num_bars / max(total_chunks, 1)
    waveform = []
    
    for i in range(num_bars):
        chunk_idx = int(i / bars_per_chunk)
        
        if chunk_idx < current_chunk:
            # Completed chunk - show actual amplitude
            amp_idx = min(chunk_idx, len(chunk_amplitudes) - 1)
            waveform.append(chunk_amplitudes[amp_idx])
        elif chunk_idx == current_chunk:
            # Currently synthesizing - show active indicator
            waveform.append(0.8)
        else:
            # Not yet synthesized - show placeholder
            waveform.append(0.1)
    
    return waveform, progress


def render_waveform_ascii(
    data: list[float],
    color: str = "#FFB000",
    animate: bool = False,
    playback_position: float = 0.0,
    cursor_color: str = "#FFFFFF",
) -> str:
    """
    Render waveform as ASCII block characters.
    
    Args:
        data: List of values between 0.0 and 1.0
        color: CSS color for the waveform
        animate: If True, show playback cursor
        playback_position: Position in the waveform (0.0-1.0)
        cursor_color: Color for the playback cursor
    
    Returns:
        HTML string for rendering
    """
    chars = []
    cursor_pos = int(playback_position * len(data)) if animate else -1
    
    for i, value in enumerate(data):
        # Map value to block character index
        block_idx = int(value * (len(BLOCKS) - 1))
        block = BLOCKS[block_idx]
        
        # Highlight playback cursor
        if i == cursor_pos:
            chars.append(f'<span style="color: {cursor_color}; text-shadow: 0 0 10px {cursor_color};">{block}</span>')
        elif animate and abs(i - cursor_pos) <= 1:
            # Glow effect near cursor
            chars.append(f'<span style="color: {color}; text-shadow: 0 0 5px {color}; opacity: 0.8;">{block}</span>')
        else:
            chars.append(block)
    
    waveform_str = "".join(chars)
    
    return f'''
    <div style="
        font-family: monospace;
        font-size: 24px;
        color: {color};
        text-shadow: 0 0 10px rgba(255, 176, 0, 0.5);
        letter-spacing: 2px;
        user-select: none;
    ">{waveform_str}</div>
    '''


def render_waveform_with_seeking(
    data: list[float],
    config: WaveformConfig,
    on_seek: Optional[Callable[[float], None]] = None,
    key: Optional[str] = None,
) -> Optional[float]:
    """
    Render waveform with seeking capabilities.
    
    Args:
        data: Waveform amplitude data
        config: Waveform configuration
        on_seek: Optional callback when user seeks (receives position 0.0-1.0)
        key: Unique Streamlit key
    
    Returns:
        Clicked position (0.0-1.0) if seeking enabled and clicked, None otherwise
    """
    unique_key = key or f"waveform_seek_{id(data)}"
    
    # Get current playback position from session state
    session_key = f"waveform_pos_{unique_key}"
    if session_key not in st.session_state:
        st.session_state[session_key] = 0.0
    
    playback_pos = st.session_state[session_key]
    
    # Render waveform
    html = render_waveform_ascii(
        data,
        color=config.color,
        animate=config.animate_cursor,
        playback_position=playback_pos,
        cursor_color=config.cursor_color,
    )
    
    # Add seeking overlay if enabled
    if config.enable_seeking:
        seek_css = f"""
            <style>
            .waveform-seek-container-{unique_key} {{
                position: relative;
                cursor: pointer;
                padding: 10px 0;
            }}
            .waveform-seek-container-{unique_key}:hover {{
                background-color: rgba(255, 176, 0, 0.05);
            }}
            .waveform-seek-bar-{unique_key} {{
                position: absolute;
                top: 0;
                bottom: 0;
                width: 2px;
                background-color: var(--accent-olive);
                opacity: 0;
                transition: opacity 0.2s;
                pointer-events: none;
            }}
            .waveform-seek-container-{unique_key}:hover .waveform-seek-bar-{unique_key} {{
                opacity: 0.5;
            }}
            .waveform-timescale-{unique_key} {{
                display: flex;
                justify-content: space-between;
                font-family: var(--font-mono);
                font-size: var(--text-xs);
                color: var(--text-faded);
                margin-top: var(--space-xs);
            }}
            </style>
        """
        
        # Render container with waveform
        st.markdown(seek_css, unsafe_allow_html=True)
        st.markdown(
            f'<div class="waveform-seek-container-{unique_key}">{html}</div>',
            unsafe_allow_html=True
        )
        
        # Create a slider for seeking (hidden but functional)
        # In a real implementation, this would use custom components
        new_pos = st.slider(
            "seek",
            min_value=0.0,
            max_value=1.0,
            value=playback_pos,
            step=0.01,
            key=f"seek_slider_{unique_key}",
            label_visibility="collapsed",
        )
        
        if new_pos != playback_pos:
            st.session_state[session_key] = new_pos
            if on_seek:
                on_seek(new_pos)
            return new_pos
    else:
        st.markdown(html, unsafe_allow_html=True)
    
    # Render timescale
    if config.show_timescale:
        st.markdown(
            f'<div class="waveform-timescale-{unique_key}">'
            f'<span>00:00</span>'
            f'<span>{int(playback_pos * 100)}%</span>'
            f'<span>--:--</span>'
            f'</div>',
            unsafe_allow_html=True
        )
    
    return None


def render_waveform_static(num_bars: int = 40, seed: int = 42, key: Optional[str] = None):
    """Render a static waveform preview."""
    data = generate_waveform_data(num_bars, seed=seed)
    html = render_waveform_ascii(data, animate=False)
    st.markdown(html, unsafe_allow_html=True)


def render_waveform_animated(
    data: list[float],
    playback_position: float = 0.0,
    key: Optional[str] = None,
):
    """
    Render animated waveform during playback.
    Call this in a loop to animate.
    """
    html = render_waveform_ascii(data, animate=True, playback_position=playback_position)
    st.markdown(html, unsafe_allow_html=True)


def render_waveform_component(
    is_playing: bool = False,
    playback_position: float = 0.0,
    audio_data: Optional[np.ndarray] = None,
    num_bars: int = 40,
    key: Optional[str] = None,
):
    """
    Main waveform component for the UI.
    
    Args:
        is_playing: Whether audio is currently playing
        playback_position: Current position in playback (0.0-1.0)
        audio_data: Optional raw audio data for actual waveform
        num_bars: Number of bars in the visualizer
        key: Unique key for Streamlit
    """
    # Generate or use provided waveform data
    if audio_data is not None:
        data = generate_waveform_from_audio(audio_data, num_bars)
    else:
        # Use session state seed for consistent display
        seed_key = f"waveform_seed_{key or 'default'}"
        if seed_key not in st.session_state:
            st.session_state[seed_key] = np.random.randint(0, 10000)
        data = generate_waveform_data(num_bars, seed=st.session_state[seed_key])
    
    if is_playing:
        render_waveform_animated(data, playback_position, key=key)
    else:
        html = render_waveform_ascii(data, animate=False)
        st.markdown(html, unsafe_allow_html=True)


def render_waveform_synthesis_progress(
    current_chunk: int,
    total_chunks: int,
    chunk_amplitudes: Optional[list[float]] = None,
    num_bars: int = 40,
    key: Optional[str] = None,
):
    """
    Render waveform showing synthesis progress in real-time.
    
    Args:
        current_chunk: Current chunk being synthesized (0-indexed)
        total_chunks: Total number of chunks
        chunk_amplitudes: Optional list of amplitudes for completed chunks
        num_bars: Number of bars in waveform
        key: Unique key for Streamlit
    
    Example:
        >>> for i in range(total_chunks):
        ...     synthesize_chunk(i)
        ...     render_waveform_synthesis_progress(i + 1, total_chunks)
    """
    unique_key = key or f"waveform_synth_{total_chunks}"
    
    # Generate waveform data showing progress
    data, progress = generate_waveform_during_synthesis(
        current_chunk, total_chunks, chunk_amplitudes, num_bars
    )
    
    # Render with custom styling for synthesis
    chars = []
    progress_pos = int(progress * len(data))
    
    for i, value in enumerate(data):
        block_idx = int(value * (len(BLOCKS) - 1))
        block = BLOCKS[block_idx]
        
        if i < progress_pos:
            # Completed - olive green
            chars.append(f'<span style="color: var(--accent-olive);">{block}</span>')
        elif i == progress_pos:
            # Current - bright with glow
            chars.append(f'<span style="color: #FFFFFF; text-shadow: 0 0 10px var(--accent-olive);">▆</span>')
        else:
            # Not started - dim
            chars.append(f'<span style="color: var(--border-color);">{block}</span>')
    
    waveform_str = "".join(chars)
    
    css = f"""
        <style>
        .waveform-synthesis-{unique_key} {{
            font-family: monospace;
            font-size: 20px;
            letter-spacing: 2px;
            user-select: none;
            padding: var(--space-sm);
            background-color: var(--bg-core);
            border: 1px solid var(--border-color);
        }}
        .waveform-synthesis-{unique_key} .progress-text {{
            font-family: var(--font-mono);
            font-size: var(--text-xs);
            color: var(--text-dim);
            text-align: right;
            margin-top: var(--space-xs);
        }}
        </style>
    """
    
    st.markdown(css, unsafe_allow_html=True)
    st.markdown(
        f'<div class="waveform-synthesis-{unique_key}">'
        f'<div>{waveform_str}</div>'
        f'<div class="progress-text">{current_chunk}/{total_chunks} chunks ({int(progress * 100)}%)</div>'
        f'</div>',
        unsafe_allow_html=True
    )


def render_mini_waveform(progress: float = 0.0, width: int = 20, key: Optional[str] = None):
    """
    Render a compact waveform for inline displays.
    Shows a simple progress bar style with blocky characters.
    """
    filled = int(progress * width)
    
    # Create a simple animated pattern
    pattern = "▁▃▅▇█▇▅▃"
    waveform = ""
    
    for i in range(width):
        if i < filled:
            char_idx = i % len(pattern)
            waveform += pattern[char_idx]
        else:
            waveform += "░"
    
    st.markdown(
        f'<span style="font-family: monospace; color: #FFB000;">[{waveform}]</span>',
        unsafe_allow_html=True
    )


def render_chapter_waveform_preview(
    chapter_duration: float,
    current_time: float = 0.0,
    synthesis_progress: Optional[float] = None,
    num_bars: int = 50,
    key: Optional[str] = None,
):
    """
    Render a chapter preview waveform with seeking and progress indication.
    
    Args:
        chapter_duration: Total chapter duration in seconds
        current_time: Current playback position in seconds
        synthesis_progress: Optional synthesis progress (0.0-1.0) if still generating
        num_bars: Number of bars in waveform
        key: Unique key for Streamlit
    
    Example:
        >>> render_chapter_waveform_preview(
        ...     chapter_duration=300.0,  # 5 minutes
        ...     current_time=45.0,       # 45 seconds in
        ...     synthesis_progress=None, # Already fully synthesized
        ... )
    """
    unique_key = key or f"chapter_waveform_{int(chapter_duration)}"
    
    # Generate representative waveform data
    np.random.seed(int(chapter_duration))  # Consistent for same chapter
    base_waveform = generate_waveform_data(num_bars)
    
    # Calculate positions
    playback_ratio = min(current_time / max(chapter_duration, 1), 1.0)
    playback_pos = int(playback_ratio * num_bars)
    
    # Build waveform visualization
    chars = []
    synth_pos = int(synthesis_progress * num_bars) if synthesis_progress else num_bars
    
    for i, value in enumerate(base_waveform):
        block_idx = int(value * (len(BLOCKS) - 1))
        block = BLOCKS[block_idx]
        
        if i >= synth_pos:
            # Not yet synthesized
            chars.append(f'<span style="color: var(--border-color);">░</span>')
        elif i == playback_pos:
            # Current playback position
            chars.append(f'<span style="color: #FFFFFF; text-shadow: 0 0 8px #FFB000;">█</span>')
        elif i < playback_pos:
            # Already played
            chars.append(f'<span style="color: var(--text-faded);">{block}</span>')
        else:
            # Upcoming
            chars.append(f'<span style="color: #FFB000;">{block}</span>')
    
    waveform_str = "".join(chars)
    
    # Format time display
    def format_time(seconds: float) -> str:
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins}:{secs:02d}"
    
    css = f"""
        <style>
        .chapter-waveform-{unique_key} {{
            background-color: var(--bg-surface);
            border: 1px solid var(--border-color);
            padding: var(--space-md);
            margin-bottom: var(--space-md);
        }}
        .chapter-waveform-{unique_key} .waveform-display {{
            font-family: monospace;
            font-size: 18px;
            letter-spacing: 1px;
            text-align: center;
            padding: var(--space-sm) 0;
        }}
        .chapter-waveform-{unique_key} .time-display {{
            display: flex;
            justify-content: space-between;
            font-family: var(--font-mono);
            font-size: var(--text-xs);
            color: var(--text-dim);
            margin-top: var(--space-xs);
        }}
        .chapter-waveform-{unique_key} .progress-info {{
            text-align: center;
            font-family: var(--font-mono);
            font-size: var(--text-xs);
            color: var(--accent-olive);
            margin-top: var(--space-xs);
        }}
        </style>
    """
    
    st.markdown(css, unsafe_allow_html=True)
    
    html_parts = [
        f'<div class="chapter-waveform-{unique_key}">',
        f'<div class="waveform-display">{waveform_str}</div>',
        f'<div class="time-display">',
        f'<span>{format_time(current_time)}</span>',
        f'<span>{format_time(chapter_duration)}</span>',
        f'</div>',
    ]
    
    if synthesis_progress is not None and synthesis_progress < 1.0:
        html_parts.append(
            f'<div class="progress-info">synthesizing... {int(synthesis_progress * 100)}%</div>'
        )
    
    html_parts.append('</div>')
    
    st.markdown("".join(html_parts), unsafe_allow_html=True)
