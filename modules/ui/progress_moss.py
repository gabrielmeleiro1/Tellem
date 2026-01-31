"""
Industrial Moss Progress Dashboard
==================================
Text-based progress indicators for conversion pipeline.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Callable
from enum import Enum
import streamlit as st


class PipelineStage(Enum):
    """Processing stages with Industrial Moss status."""
    IDLE = "idle"
    PARSING = "parsing"
    CLEANING = "cleaning"
    SYNTHESIZING = "synthesizing"
    ENCODING = "encoding"
    PACKAGING = "packaging"
    COMPLETE = "complete"
    ERROR = "error"


@dataclass
class ChapterStatus:
    """Status for a single chapter in the pipeline."""
    number: int
    name: str
    stage: PipelineStage
    progress: float = 0.0  # 0.0 to 1.0
    error_message: Optional[str] = None


@dataclass
class PipelineStatus:
    """Overall pipeline status display."""
    total_chapters: int
    completed_chapters: int
    current_stage: PipelineStage
    current_chapter: Optional[int] = None
    chapters: List[ChapterStatus] = field(default_factory=list)
    eta_seconds: Optional[int] = None


def format_eta(seconds: Optional[int]) -> str:
    """Format ETA as mm:ss or --:--."""
    if seconds is None or seconds < 0:
        return "--:--"
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes:02d}:{secs:02d}"


def format_duration(seconds: Optional[int]) -> str:
    """Format duration as HH:MM:SS."""
    if seconds is None or seconds < 0:
        return "--:--:--"
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


@dataclass
class ASCIIProgressConfig:
    """Configuration for ASCII-based progress bars."""
    width: int = 40  # Number of characters
    fill_char: str = "█"  # Filled portion
    empty_char: str = "░"  # Empty portion
    bracket_open: str = "["  # Left bracket
    bracket_close: str = "]"  # Right bracket


def render_ascii_progress(
    progress: float,  # 0.0 to 1.0
    config: Optional[ASCIIProgressConfig] = None,
    show_percentage: bool = True,
    key: Optional[str] = None
) -> str:
    """
    Render a text-based progress bar using block characters.
    Example: [████████████████░░░░░░░░░░░░░░░░░░░░] 42%
    
    Args:
        progress: Progress value from 0.0 to 1.0
        config: Progress bar configuration
        show_percentage: Whether to append percentage
        key: Unique key for Streamlit
        
    Returns:
        The rendered progress bar string
    """
    cfg = config or ASCIIProgressConfig()
    
    # Clamp progress to [0, 1]
    progress = max(0.0, min(1.0, progress))
    
    # Calculate filled width
    filled = int(progress * cfg.width)
    empty = cfg.width - filled
    
    # Build bar
    bar = (
        cfg.bracket_open +
        cfg.fill_char * filled +
        cfg.empty_char * empty +
        cfg.bracket_close
    )
    
    if show_percentage:
        bar += f" {int(progress * 100)}%"
    
    return bar


def render_ascii_progress_html(
    progress: float,
    config: Optional[ASCIIProgressConfig] = None,
    show_percentage: bool = True,
    key: Optional[str] = None
) -> None:
    """
    Render an ASCII progress bar as HTML with styling.
    
    Args:
        progress: Progress value from 0.0 to 1.0
        config: Progress bar configuration
        show_percentage: Whether to append percentage
        key: Unique key for Streamlit
    """
    bar = render_ascii_progress(progress, config, show_percentage, key)
    
    unique_key = key or "ascii_progress"
    
    css = f"""
        <style>
        .moss-ascii-progress-{unique_key} {{
            font-family: var(--font-mono);
            font-size: var(--text-sm);
            color: var(--text-dim);
            letter-spacing: 0;
            white-space: pre;
        }}
        </style>
    """
    
    st.markdown(css, unsafe_allow_html=True)
    st.markdown(
        f'<div class="moss-ascii-progress-{unique_key}">{bar}</div>',
        unsafe_allow_html=True,
    )


@dataclass
class StatusIndicator:
    """A text-based status indicator."""
    state: str  # "idle" | "active" | "complete" | "error"
    label: str  # Description (lowercase)
    use_brackets: bool = True  # Wrap in [ ]


def get_status_symbol(state: str) -> str:
    """
    Get the status symbol for a given state.
    
    Symbols:
    - idle: ○
    - active: ◐
    - complete: ●
    - error: ✕
    """
    symbols = {
        "idle": "○",
        "active": "◐",
        "complete": "●",
        "error": "✕",
    }
    return symbols.get(state, "○")


def get_status_color(state: str) -> str:
    """Get the CSS color variable for a status state."""
    colors = {
        "idle": "var(--text-faded)",
        "active": "var(--accent-olive)",
        "complete": "var(--accent-olive)",
        "error": "var(--accent-rust)",
    }
    return colors.get(state, "var(--text-faded)")


def render_status(
    indicator: StatusIndicator,
    key: Optional[str] = None
) -> None:
    """
    Render a status indicator with appropriate symbol and color.
    
    Args:
        indicator: Status indicator configuration
        key: Unique key for Streamlit
    """
    symbol = get_status_symbol(indicator.state)
    color = get_status_color(indicator.state)
    
    if indicator.use_brackets:
        display = f"[ {symbol} ] {indicator.label}"
    else:
        display = f"{symbol} {indicator.label}"
    
    unique_key = key or f"status_{indicator.state}"
    
    css = f"""
        <style>
        .moss-status-{unique_key} {{
            font-family: var(--font-mono);
            font-size: var(--text-sm);
            color: {color};
        }}
        </style>
    """
    
    st.markdown(css, unsafe_allow_html=True)
    st.markdown(
        f'<div class="moss-status-{unique_key}">{display}</div>',
        unsafe_allow_html=True,
    )


def render_pipeline_status(
    status: PipelineStatus,
    compact: bool = False,
    key: Optional[str] = None
) -> None:
    """
    Render pipeline progress with ASCII bars and status symbols.
    
    Example output:
    ┌─ PIPELINE STATUS ───────────────────────┐
    │                                         │
    │  stage:     synthesizing                │
    │  progress:  [████████░░░░░░░░░░░░] 42%  │
    │  chapters:  5/12 complete               │
    │  eta:       00:04:23                    │
    │                                         │
    │  CHAPTERS:                              │
    │  [●] 01 - introduction      complete    │
    │  [●] 02 - chapter one       complete    │
    │  [◐] 03 - chapter two       processing  │
    │  [○] 04 - chapter three     pending     │
    │  [○] 05 - chapter four      pending     │
    │                                         │
    └─────────────────────────────────────────┘
    
    Args:
        status: Pipeline status
        compact: Whether to show compact view
        key: Unique key for Streamlit
    """
    unique_key = key or "pipeline_status"
    
    # Calculate overall progress
    if status.total_chapters > 0:
        overall_progress = status.completed_chapters / status.total_chapters
    else:
        overall_progress = 0.0
    
    # Stage display name mapping
    stage_names = {
        PipelineStage.IDLE: "idle",
        PipelineStage.PARSING: "parsing",
        PipelineStage.CLEANING: "cleaning",
        PipelineStage.SYNTHESIZING: "synthesizing",
        PipelineStage.ENCODING: "encoding",
        PipelineStage.PACKAGING: "packaging",
        PipelineStage.COMPLETE: "complete",
        PipelineStage.ERROR: "error",
    }
    
    css = f"""
        <style>
        .moss-pipeline-{unique_key} {{
            font-family: var(--font-mono);
            font-size: var(--text-sm);
            color: var(--text-main);
        }}
        .moss-pipeline-{unique_key} .moss-pipeline-row {{
            display: flex;
            gap: var(--space-md);
            margin-bottom: var(--space-xs);
            align-items: baseline;
        }}
        .moss-pipeline-{unique_key} .moss-pipeline-label {{
            color: var(--text-dim);
            text-transform: lowercase;
            min-width: 10ch;
        }}
        .moss-pipeline-{unique_key} .moss-pipeline-label::after {{
            content: ":";
        }}
        .moss-pipeline-{unique_key} .moss-pipeline-value {{
            color: var(--text-main);
        }}
        .moss-pipeline-{unique_key} .moss-pipeline-section {{
            margin-top: var(--space-md);
            text-transform: uppercase;
            color: var(--text-dim);
            letter-spacing: 0.05em;
        }}
        .moss-pipeline-{unique_key} .moss-chapter-row {{
            display: flex;
            gap: var(--space-md);
            margin-bottom: var(--space-xs);
            font-size: var(--text-xs);
        }}
        .moss-pipeline-{unique_key} .moss-chapter-status {{
            width: 3ch;
            text-align: center;
        }}
        .moss-pipeline-{unique_key} .moss-chapter-number {{
            color: var(--text-faded);
            min-width: 4ch;
        }}
        .moss-pipeline-{unique_key} .moss-chapter-name {{
            color: var(--text-main);
            flex: 1;
        }}
        .moss-pipeline-{unique_key} .moss-chapter-stage {{
            color: var(--text-dim);
            text-transform: lowercase;
        }}
        .moss-pipeline-{unique_key} .moss-status-symbol-idle {{
            color: var(--text-faded);
        }}
        .moss-pipeline-{unique_key} .moss-status-symbol-active {{
            color: var(--accent-olive);
        }}
        .moss-pipeline-{unique_key} .moss-status-symbol-complete {{
            color: var(--accent-olive);
        }}
        .moss-pipeline-{unique_key} .moss-status-symbol-error {{
            color: var(--accent-rust);
        }}
        </style>
    """
    
    st.markdown(css, unsafe_allow_html=True)
    
    html_parts = [f'<div class="moss-pipeline-{unique_key}">']
    
    # Stage row
    stage_name = stage_names.get(status.current_stage, status.current_stage.value)
    html_parts.append(
        f'<div class="moss-pipeline-row">'
        f'<span class="moss-pipeline-label">stage</span>'
        f'<span class="moss-pipeline-value">{stage_name}</span>'
        f'</div>'
    )
    
    # Progress row with ASCII bar
    progress_bar = render_ascii_progress(overall_progress, width=30)
    html_parts.append(
        f'<div class="moss-pipeline-row">'
        f'<span class="moss-pipeline-label">progress</span>'
        f'<span class="moss-pipeline-value moss-ascii-progress">{progress_bar}</span>'
        f'</div>'
    )
    
    # Chapters row
    html_parts.append(
        f'<div class="moss-pipeline-row">'
        f'<span class="moss-pipeline-label">chapters</span>'
        f'<span class="moss-pipeline-value">{status.completed_chapters}/{status.total_chapters} complete</span>'
        f'</div>'
    )
    
    # ETA row
    eta_str = format_eta(status.eta_seconds)
    html_parts.append(
        f'<div class="moss-pipeline-row">'
        f'<span class="moss-pipeline-label">eta</span>'
        f'<span class="moss-pipeline-value">{eta_str}</span>'
        f'</div>'
    )
    
    # Chapter list (if not compact)
    if not compact and status.chapters:
        html_parts.append('<div class="moss-pipeline-section">chapters</div>')
        
        for ch in status.chapters:
            stage_class = ch.stage.value if ch.stage.value in ["idle", "active", "complete", "error"] else "idle"
            symbol = get_status_symbol(stage_class)
            
            html_parts.append(
                f'<div class="moss-chapter-row">'
                f'<span class="moss-chapter-status moss-status-symbol-{stage_class}">[{symbol}]</span>'
                f'<span class="moss-chapter-number">{ch.number:02d}</span>'
                f'<span class="moss-chapter-name">{ch.name}</span>'
                f'<span class="moss-chapter-stage">{ch.stage.value}</span>'
                f'</div>'
            )
    
    html_parts.append('</div>')
    
    st.markdown("".join(html_parts), unsafe_allow_html=True)


@dataclass
class MetricDisplay:
    """A metric value display for the Industrial Moss theme."""
    label: str  # lowercase label (e.g., "cpu usage:")
    value: str | float  # The value to display
    unit: Optional[str] = None  # Unit suffix (e.g., "%", "MB", "s")
    status: str = "neutral"  # "neutral" | "active" | "success" | "error"


def render_metric(
    metric: MetricDisplay,
    key: Optional[str] = None
) -> None:
    """
    Render a metric with monospace font and status coloring.
    Format: [label] [value][unit]
    
    Args:
        metric: Metric display configuration
        key: Unique key for Streamlit
    """
    unique_key = key or f"metric_{metric.label.replace(' ', '_')}"
    
    status_class = ""
    if metric.status == "active":
        status_class = "moss-metric-value-active"
    elif metric.status == "success":
        status_class = "moss-metric-value-success"
    elif metric.status == "error":
        status_class = "moss-metric-value-error"
    
    css = f"""
        <style>
        .moss-metric-{unique_key} {{
            font-family: var(--font-mono);
            font-size: var(--text-sm);
            display: flex;
            gap: var(--space-sm);
            align-items: baseline;
        }}
        .moss-metric-{unique_key} .moss-metric-label {{
            color: var(--text-dim);
            text-transform: lowercase;
        }}
        .moss-metric-{unique_key} .moss-metric-label::after {{
            content: ":";
        }}
        .moss-metric-{unique_key} .moss-metric-value {{
            color: var(--text-main);
        }}
        .moss-metric-{unique_key} .moss-metric-value-active {{
            color: var(--status-active);
        }}
        .moss-metric-{unique_key} .moss-metric-value-success {{
            color: var(--status-success);
        }}
        .moss-metric-{unique_key} .moss-metric-value-error {{
            color: var(--status-error);
        }}
        .moss-metric-{unique_key} .moss-metric-unit {{
            color: var(--text-faded);
        }}
        </style>
    """
    
    st.markdown(css, unsafe_allow_html=True)
    st.markdown(
        f'<div class="moss-metric-{unique_key}">'
        f'<span class="moss-metric-label">{metric.label}</span>'
        f'<span class="moss-metric-value {status_class}">{metric.value}</span>'
        f'<span class="moss-metric-unit">{metric.unit or ""}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )


def render_metrics_row(metrics: List[MetricDisplay], key: Optional[str] = None) -> None:
    """
    Render a row of metrics.
    
    Args:
        metrics: List of metrics to display
        key: Unique key for Streamlit
    """
    cols = st.columns(len(metrics))
    for idx, (col, metric) in enumerate(zip(cols, metrics)):
        with col:
            render_metric(metric, key=f"{key}_{idx}" if key else None)
