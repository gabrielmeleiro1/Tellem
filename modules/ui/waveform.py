"""
Waveform Visualizer
===================
Blocky oscilloscope-style waveform display for audio playback.
"""

import streamlit as st
import numpy as np
from typing import Optional


# Block characters for oscilloscope visualization (bottom to top)
BLOCKS = " ▁▂▃▄▅▆▇█"


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


def generate_audio_waveform(audio_data: np.ndarray, num_bars: int = 40) -> list[float]:
    """
    Generate waveform data from actual audio samples.
    Returns values between 0.0 and 1.0.
    """
    if len(audio_data) == 0:
        return [0.0] * num_bars
    
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


def render_waveform_ascii(
    data: list[float],
    color: str = "#FFB000",
    animate: bool = False,
    playback_position: float = 0.0
) -> str:
    """
    Render waveform as ASCII block characters.
    
    Args:
        data: List of values between 0.0 and 1.0
        color: CSS color for the waveform
        animate: If True, show playback cursor
        playback_position: Position in the waveform (0.0-1.0)
    
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
            chars.append(f'<span style="color: #FFFFFF; text-shadow: 0 0 10px #FFFFFF;">{block}</span>')
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


def render_waveform_static(num_bars: int = 40, seed: int = 42):
    """Render a static waveform preview."""
    data = generate_waveform_data(num_bars, seed=seed)
    html = render_waveform_ascii(data, animate=False)
    st.markdown(html, unsafe_allow_html=True)


def render_waveform_animated(
    data: list[float],
    playback_position: float = 0.0
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
    num_bars: int = 40
):
    """
    Main waveform component for the UI.
    
    Args:
        is_playing: Whether audio is currently playing
        playback_position: Current position in playback (0.0-1.0)
        audio_data: Optional raw audio data for actual waveform
        num_bars: Number of bars in the visualizer
    """
    # Generate or use provided waveform data
    if audio_data is not None:
        data = generate_audio_waveform(audio_data, num_bars)
    else:
        # Use session state seed for consistent display
        if "waveform_seed" not in st.session_state:
            st.session_state.waveform_seed = np.random.randint(0, 10000)
        data = generate_waveform_data(num_bars, seed=st.session_state.waveform_seed)
    
    if is_playing:
        render_waveform_animated(data, playback_position)
    else:
        html = render_waveform_ascii(data, animate=False)
        st.markdown(html, unsafe_allow_html=True)


def render_mini_waveform(progress: float = 0.0, width: int = 20):
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
