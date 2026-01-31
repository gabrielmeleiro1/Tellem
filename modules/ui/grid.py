"""
Brutalist Grid Layout System
============================
Strict tiling window manager style grid layouts.
"""

from typing import List, Callable, Optional
from dataclasses import dataclass
import streamlit as st


@dataclass
class GridCell:
    """A single cell in the brutalist grid."""
    content: Callable[..., None]  # Content renderer
    colspan: int = 1  # Grid column span
    rowspan: int = 1  # Grid row span
    border: bool = True  # Show cell border
    title: Optional[str] = None  # Optional panel title


@dataclass
class GridConfig:
    """Configuration for the grid layout."""
    columns: int = 2  # Number of columns
    gap: str = "1px"  # Gap between cells (should be minimal)
    border_style: str = "thin"  # Border style for cells: "thin" | "thick" | "accent"


def render_grid(
    cells: List[GridCell],
    config: Optional[GridConfig] = None,
    key: Optional[str] = None
) -> None:
    """
    Render a strict grid layout with borders.
    
    Example 2-column grid:
    ┌──────────────┬──────────────┐
    │   SOURCE     │  PROGRESS    │
    ├──────────────┼──────────────┤
    │   METRICS    │   OUTPUT     │
    └──────────────┴──────────────┘
    
    Args:
        cells: List of GridCell defining content
        config: Grid configuration
        key: Unique key for Streamlit
    """
    cfg = config or GridConfig()
    
    # Calculate grid layout
    rows = []
    current_row = []
    current_span = 0
    
    for cell in cells:
        if current_span + cell.colspan > cfg.columns:
            rows.append(current_row)
            current_row = [cell]
            current_span = cell.colspan
        else:
            current_row.append(cell)
            current_span += cell.colspan
    
    if current_row:
        rows.append(current_row)
    
    # Render each row
    for row_idx, row in enumerate(rows):
        # Calculate column widths
        cols = st.columns([cell.colspan for cell in row])
        
        for col_idx, (col, cell) in enumerate(zip(cols, row)):
            with col:
                _render_cell(cell, cfg.border_style, key=f"{key}_cell_{row_idx}_{col_idx}" if key else None)


def _render_cell(cell: GridCell, border_style: str, key: Optional[str] = None) -> None:
    """Render a single grid cell with border and optional title."""
    # Determine border width based on style
    border_width = "1px" if border_style == "thin" else "2px" if border_style == "thick" else "1px"
    border_color = "var(--border-color)"
    if border_style == "accent":
        border_color = "var(--border-accent)"
    
    # Create container with border
    container_style = f"""
        <style>
        .moss-grid-cell-{key or 'default'} {{
            background-color: var(--bg-surface);
            border: {border_width} solid {border_color};
            padding: var(--space-md);
            height: 100%;
        }}
        .moss-grid-cell-{key or 'default'} .moss-cell-title {{
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
        </style>
    """
    
    st.markdown(container_style, unsafe_allow_html=True)
    
    # Render cell content
    if cell.title:
        st.markdown(
            f'<div class="moss-grid-cell-{key or "default"}">'
            f'<div class="moss-cell-title">{cell.title}</div>',
            unsafe_allow_html=True,
        )
        cell.content()
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.markdown(
            f'<div class="moss-grid-cell-{key or "default"}">',
            unsafe_allow_html=True,
        )
        cell.content()
        st.markdown('</div>', unsafe_allow_html=True)


@dataclass
class PanelConfig:
    """Configuration for a brutalist panel/container."""
    title: str  # Panel title (will be UPPERCASED)
    border_style: str = "thin"  # "thin" | "thick" | "accent"
    padding: str = "md"  # "xs" | "sm" | "md" | "lg"
    background: str = "surface"  # "core" | "surface" | "elevated"


def render_panel(
    config: PanelConfig,
    content: Callable[..., None],
    key: Optional[str] = None
) -> None:
    """
    Render a brutalist panel with strict borders and zero radius.
    
    Args:
        config: Panel configuration
        content: Function that renders content inside the panel
        key: Unique key for Streamlit
    """
    # Determine border width
    border_width = "1px" if config.border_style == "thin" else "2px" if config.border_style == "thick" else "1px"
    border_color = "var(--border-accent)" if config.border_style == "accent" else "var(--border-color)"
    
    # Determine background color
    bg_color = f"var(--bg-{config.background})"
    
    # Determine padding
    padding = f"var(--space-{config.padding})"
    
    unique_key = key or f"panel_{config.title.lower().replace(' ', '_')}"
    
    panel_style = f"""
        <style>
        .moss-panel-{unique_key} {{
            background-color: {bg_color};
            border: {border_width} solid {border_color};
            padding: {padding};
        }}
        .moss-panel-{unique_key} .moss-panel-title {{
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
        </style>
    """
    
    st.markdown(panel_style, unsafe_allow_html=True)
    st.markdown(
        f'<div class="moss-panel-{unique_key}">'
        f'<div class="moss-panel-title">{config.title.upper()}</div>',
        unsafe_allow_html=True,
    )
    content()
    st.markdown('</div>', unsafe_allow_html=True)


def render_metric_row(metrics: List[dict], key: Optional[str] = None) -> None:
    """
    Render a row of metrics with consistent styling.
    
    Args:
        metrics: List of dicts with keys: label, value, unit, status
        key: Unique key for Streamlit
    """
    cols = st.columns(len(metrics))
    
    for idx, (col, metric) in enumerate(zip(cols, metrics)):
        with col:
            status_class = ""
            if metric.get('status') == 'active':
                status_class = "moss-metric-value-active"
            elif metric.get('status') == 'success':
                status_class = "moss-metric-value-success"
            elif metric.get('status') == 'error':
                status_class = "moss-metric-value-error"
            
            st.markdown(
                f'<div class="moss-metric">'
                f'<span class="moss-metric-label">{metric["label"]}</span>'
                f'<span class="moss-metric-value {status_class}">{metric["value"]}</span>'
                f'<span class="moss-metric-unit">{metric.get("unit", "")}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
