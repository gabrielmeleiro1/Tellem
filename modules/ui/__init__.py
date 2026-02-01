"""
UI Module
=========
Custom Streamlit components and styling utilities.

Includes Industrial Moss theme components for a brutalist, instrument-like UI.
"""

# Industrial Moss Component Library
from .components import (
    # Button components
    MossButton,
    ButtonVariant,
    ButtonSize,
    moss_button,
    # Panel components
    MossPanel,
    PanelHeader,
    PanelVariant,
    moss_panel,
    # Progress components
    MossProgress,
    ProgressVariant,
    moss_progress,
    # Badge components
    MossBadge,
    BadgeVariant,
    moss_badge,
    # Divider
    moss_divider,
)

# Legacy progress components
from .progress import (
    ProcessingStage,
    ChapterProgress,
    ConversionProgress,
    init_progress_state,
    get_progress,
    reset_progress,
    set_chapters,
    update_chapter_progress,
    set_current_stage,
    request_cancellation,
    is_cancelled,
    clear_cancellation,
    save_progress_to_session,
    restore_progress_from_session,
    clear_progress_backup,
    render_chapter_progress,
    render_stage_indicator,
    render_compact_progress,
)

# Industrial Moss Theme
from .theme import (
    IndustrialMossTheme,
    DEFAULT_THEME,
    load_fonts,
    load_css_from_file,
    apply_theme,
    get_theme,
)

# Industrial Moss Grid Layout
from .grid import (
    GridCell,
    GridConfig,
    PanelConfig,
    render_grid,
    render_panel,
    render_metric_row,
)

# Industrial Moss Terminal
from .terminal_moss import (
    LogLevel,
    LogEntry,
    add_log,
    add_debug,
    add_info,
    add_process,
    add_warning,
    add_error,
    clear_logs,
    get_logs,
    render_industrial_terminal,
    render_compact_terminal,
)

# Industrial Moss Progress
from .progress_moss import (
    PipelineStage,
    ChapterStatus,
    PipelineStatus,
    ASCIIProgressConfig,
    StatusIndicator,
    MetricDisplay,
    format_eta,
    format_duration,
    render_ascii_progress,
    render_ascii_progress_html,
    get_status_symbol,
    get_status_color,
    render_status,
    render_pipeline_status,
    render_metric,
    render_metrics_row,
)

# Industrial Moss Source Panel
from .source_panel import (
    SourceFile,
    render_source_panel,
    render_source_panel_simple,
)

# Industrial Moss Output Panel
from .output_panel import (
    AudioOutput,
    WaveformConfig,
    generate_ascii_waveform,
    render_waveform,
    render_output_panel,
    render_output_panel_simple,
)

__all__ = [
    # Component Library
    "MossButton",
    "ButtonVariant",
    "ButtonSize",
    "moss_button",
    "MossPanel",
    "PanelHeader",
    "PanelVariant",
    "moss_panel",
    "MossProgress",
    "ProgressVariant",
    "moss_progress",
    "MossBadge",
    "BadgeVariant",
    "moss_badge",
    "moss_divider",
    # Legacy progress
    "ProcessingStage",
    "ChapterProgress",
    "ConversionProgress",
    "init_progress_state",
    "get_progress",
    "reset_progress",
    "set_chapters",
    "update_chapter_progress",
    "set_current_stage",
    "request_cancellation",
    "is_cancelled",
    "clear_cancellation",
    "save_progress_to_session",
    "restore_progress_from_session",
    "clear_progress_backup",
    "render_chapter_progress",
    "render_stage_indicator",
    "render_compact_progress",
    # Industrial Moss Theme
    "IndustrialMossTheme",
    "DEFAULT_THEME",
    "load_fonts",
    "load_css_from_file",
    "apply_theme",
    "get_theme",
    # Industrial Moss Grid
    "GridCell",
    "GridConfig",
    "PanelConfig",
    "render_grid",
    "render_panel",
    "render_metric_row",
    # Industrial Moss Terminal
    "LogLevel",
    "LogEntry",
    "add_log",
    "add_debug",
    "add_info",
    "add_process",
    "add_warning",
    "add_error",
    "clear_logs",
    "get_logs",
    "render_industrial_terminal",
    "render_compact_terminal",
    # Industrial Moss Progress
    "PipelineStage",
    "ChapterStatus",
    "PipelineStatus",
    "ASCIIProgressConfig",
    "StatusIndicator",
    "MetricDisplay",
    "format_eta",
    "format_duration",
    "render_ascii_progress",
    "render_ascii_progress_html",
    "get_status_symbol",
    "get_status_color",
    "render_status",
    "render_pipeline_status",
    "render_metric",
    "render_metrics_row",
    # Industrial Moss Source Panel
    "SourceFile",
    "render_source_panel",
    "render_source_panel_simple",
    # Industrial Moss Output Panel
    "AudioOutput",
    "WaveformConfig",
    "generate_ascii_waveform",
    "render_waveform",
    "render_output_panel",
    "render_output_panel_simple",
]
