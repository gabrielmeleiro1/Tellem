"""
Industrial Moss Terminal
========================
Restyled terminal view matching the Industrial Moss aesthetic.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Generator
from enum import Enum
import streamlit as st


class LogLevel(Enum):
    """Log levels with Industrial Moss colors."""
    DEBUG = "debug"      # --text-faded
    INFO = "info"        # --text-dim
    PROCESS = "process"  # --accent-olive
    WARNING = "warning"  # --accent-gold
    ERROR = "error"      # --accent-rust


@dataclass
class LogEntry:
    """Single log entry."""
    timestamp: datetime
    level: LogLevel
    message: str
    source: Optional[str] = None  # Module/component source


# Configuration for log buffer
MAX_LOG_BUFFER_SIZE = 100  # Maximum entries to keep in buffer

# Global buffer for terminal logs (per-session via session_state)
def _init_terminal_state():
    """Initialize terminal state in session state."""
    if "moss_terminal_logs" not in st.session_state:
        st.session_state.moss_terminal_logs = []


def add_log(
    message: str,
    level: LogLevel = LogLevel.INFO,
    source: Optional[str] = None
) -> None:
    """
    Add a log entry to the terminal.
    
    Args:
        message: Log message content
        level: Log level for styling
        source: Optional component source
    """
    _init_terminal_state()
    
    entry = LogEntry(
        timestamp=datetime.now(),
        level=level,
        message=message,
        source=source,
    )
    st.session_state.moss_terminal_logs.append(entry)
    
    # Keep buffer limited to MAX_LOG_BUFFER_SIZE entries (optimized from 500)
    if len(st.session_state.moss_terminal_logs) > MAX_LOG_BUFFER_SIZE:
        st.session_state.moss_terminal_logs = st.session_state.moss_terminal_logs[-MAX_LOG_BUFFER_SIZE:]


def add_debug(message: str, source: Optional[str] = None) -> None:
    """Add a debug log entry."""
    add_log(message, LogLevel.DEBUG, source)


def add_info(message: str, source: Optional[str] = None) -> None:
    """Add an info log entry."""
    add_log(message, LogLevel.INFO, source)


def add_process(message: str, source: Optional[str] = None) -> None:
    """Add a process log entry."""
    add_log(message, LogLevel.PROCESS, source)


def add_warning(message: str, source: Optional[str] = None) -> None:
    """Add a warning log entry."""
    add_log(message, LogLevel.WARNING, source)


def add_error(message: str, source: Optional[str] = None) -> None:
    """Add an error log entry."""
    add_log(message, LogLevel.ERROR, source)


def clear_logs() -> None:
    """Clear all terminal logs."""
    _init_terminal_state()
    st.session_state.moss_terminal_logs = []


def get_logs() -> List[LogEntry]:
    """Get all log entries."""
    _init_terminal_state()
    return st.session_state.moss_terminal_logs


def get_logs_generator(
    min_level: Optional[LogLevel] = None,
    source_filter: Optional[str] = None
) -> Generator[LogEntry, None, None]:
    """
    Generator for streaming log entries with optional filtering.
    
    Args:
        min_level: Minimum log level to include (e.g., LogLevel.WARNING)
        source_filter: Only include logs from this source
    
    Yields:
        LogEntry objects matching the filter criteria
    
    Example:
        # Stream only warnings and errors
        for entry in get_logs_generator(min_level=LogLevel.WARNING):
            process_log(entry)
        
        # Stream logs from specific source
        for entry in get_logs_generator(source_filter="TTS"):
            process_log(entry)
    """
    _init_terminal_state()
    
    level_priority = {
        LogLevel.DEBUG: 0,
        LogLevel.INFO: 1,
        LogLevel.PROCESS: 2,
        LogLevel.WARNING: 3,
        LogLevel.ERROR: 4,
    }
    
    min_priority = level_priority.get(min_level, 0) if min_level else 0
    
    for entry in st.session_state.moss_terminal_logs:
        # Filter by level
        if min_level and level_priority.get(entry.level, 0) < min_priority:
            continue
        
        # Filter by source
        if source_filter and entry.source != source_filter:
            continue
        
        yield entry


def stream_logs_batch(
    batch_size: int = 10,
    min_level: Optional[LogLevel] = None
) -> Generator[List[LogEntry], None, None]:
    """
    Generator that yields logs in batches for efficient processing.
    
    Args:
        batch_size: Number of logs per batch
        min_level: Minimum log level to include
    
    Yields:
        Batches of LogEntry objects
    
    Example:
        # Process logs in batches of 50
        for batch in stream_logs_batch(batch_size=50, min_level=LogLevel.INFO):
            save_to_database(batch)
    """
    batch: List[LogEntry] = []
    
    for entry in get_logs_generator(min_level=min_level):
        batch.append(entry)
        
        if len(batch) >= batch_size:
            yield batch
            batch = []
    
    # Yield any remaining entries
    if batch:
        yield batch


def add_log_filtered(
    message: str,
    level: LogLevel = LogLevel.INFO,
    source: Optional[str] = None,
    min_buffer_level: LogLevel = LogLevel.DEBUG
) -> bool:
    """
    Add a log entry with level filtering before buffer storage.
    
    Args:
        message: Log message content
        level: Log level for styling
        source: Optional component source
        min_buffer_level: Minimum level to store in buffer (lower levels are dropped)
    
    Returns:
        True if log was added, False if filtered out
    
    Example:
        # Only store INFO and above in buffer (exclude DEBUG)
        added = add_log_filtered("Debug info", LogLevel.DEBUG, min_buffer_level=LogLevel.INFO)
        # added will be False, log is not stored
    """
    level_priority = {
        LogLevel.DEBUG: 0,
        LogLevel.INFO: 1,
        LogLevel.PROCESS: 2,
        LogLevel.WARNING: 3,
        LogLevel.ERROR: 4,
    }
    
    entry_priority = level_priority.get(level, 1)
    min_priority = level_priority.get(min_buffer_level, 0)
    
    # Filter out logs below the minimum buffer level
    if entry_priority < min_priority:
        return False
    
    add_log(message, level, source)
    return True


def render_industrial_terminal(
    logs: Optional[List[LogEntry]] = None,
    max_height: int = 400,
    show_timestamps: bool = True,
    show_level: bool = True,
    max_entries: int = 100,
    key: Optional[str] = None
) -> None:
    """
    Render terminal with Industrial Moss styling.
    
    Format:
    [14:32:08.042] [PROCESS] converting chapter 3...
    [14:32:10.156] [INFO]    tts engine initialized
    [14:32:15.789] [ERROR]   chunk 42 failed
    
    Args:
        logs: List of log entries (uses session state if None)
        max_height: Maximum height in pixels
        show_timestamps: Whether to show timestamps
        show_level: Whether to show log level
        max_entries: Maximum number of entries to display
        key: Unique key for Streamlit
    """
    _init_terminal_state()
    
    entries = logs if logs is not None else st.session_state.moss_terminal_logs
    
    # Limit entries
    display_entries = entries[-max_entries:] if len(entries) > max_entries else entries
    
    unique_key = key or "moss_terminal"
    
    # Terminal CSS
    terminal_css = f"""
        <style>
        .moss-terminal-{unique_key} {{
            background-color: var(--bg-core);
            border: 1px solid var(--border-color);
            font-family: var(--font-mono);
            font-size: var(--text-xs);
            color: var(--text-main);
            padding: var(--space-sm);
            height: {max_height}px;
            overflow-y: auto;
            line-height: 1.5;
        }}
        .moss-terminal-entry {{
            margin-bottom: var(--space-xs);
            white-space: pre-wrap;
            word-break: break-word;
        }}
        .moss-terminal-timestamp {{
            color: var(--text-faded);
        }}
        .moss-terminal-level {{
            display: inline-block;
            width: 9ch;
            text-align: center;
        }}
        .moss-terminal-debug {{
            color: var(--text-faded);
        }}
        .moss-terminal-info {{
            color: var(--text-dim);
        }}
        .moss-terminal-process {{
            color: var(--accent-olive);
        }}
        .moss-terminal-warning {{
            color: var(--accent-gold);
        }}
        .moss-terminal-error {{
            color: var(--accent-rust);
        }}
        .moss-terminal-cursor {{
            display: inline-block;
            width: 6px;
            height: 12px;
            background-color: var(--text-main);
            animation: blink 1s step-end infinite;
            vertical-align: middle;
            margin-left: 4px;
        }}
        @keyframes blink {{
            50% {{ opacity: 0; }}
        }}
        </style>
    """
    
    st.markdown(terminal_css, unsafe_allow_html=True)
    
    # Build terminal HTML
    html_parts = [f'<div class="moss-terminal-{unique_key}">']
    
    for entry in display_entries:
        timestamp_str = entry.timestamp.strftime("%H:%M:%S.%f")[:-3] if show_timestamps else ""
        level_str = entry.level.value.upper() if show_level else ""
        
        # Format the line
        line_parts = []
        if show_timestamps:
            line_parts.append(f'<span class="moss-terminal-timestamp">[{timestamp_str}]</span>')
        if show_level:
            level_padding = level_str.ljust(8)
            line_parts.append(f'<span class="moss-terminal-level moss-terminal-{entry.level.value}">[{level_padding}]</span>')
        
        line_parts.append(f'<span class="moss-terminal-{entry.level.value}">{entry.message}</span>')
        
        html_parts.append(f'<div class="moss-terminal-entry">{" ".join(line_parts)}</div>')
    
    # Add blinking cursor
    html_parts.append('<div class="moss-terminal-entry"><span class="moss-terminal-cursor"></span></div>')
    html_parts.append('</div>')
    
    st.markdown("".join(html_parts), unsafe_allow_html=True)


def render_compact_terminal(
    max_height: int = 200,
    max_entries: int = 20,
    key: Optional[str] = None
) -> None:
    """
    Render a compact terminal view (last N entries only).
    
    Args:
        max_height: Maximum height in pixels
        max_entries: Maximum number of entries to display
        key: Unique key for Streamlit
    """
    render_industrial_terminal(
        max_height=max_height,
        max_entries=max_entries,
        key=key or "compact_terminal",
    )
