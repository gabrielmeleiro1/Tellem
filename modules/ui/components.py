"""
Industrial Moss UI Component Library
=====================================
Reusable components for the Industrial Moss design system.

Components:
- MossButton: Brutalist button styles
- MossPanel: Container panels with consistent styling
- MossProgress: Progress indicators (linear and circular)
- MossBadge: Status badges and labels
- MossDivider: Section dividers
"""

from dataclasses import dataclass, field
from typing import Optional, Callable, Literal, List
from enum import Enum
import streamlit as st


class ButtonVariant(Enum):
    """Button style variants."""
    DEFAULT = "default"      # Standard button
    PRIMARY = "primary"      # Accent-colored button
    GHOST = "ghost"          # Transparent background
    DANGER = "danger"        # Error/warning color


class ButtonSize(Enum):
    """Button size variants."""
    SMALL = "sm"
    MEDIUM = "md"
    LARGE = "lg"


@dataclass
class MossButton:
    """
    Industrial Moss button component.
    
    A brutalist button with monospace typography and sharp edges.
    No rounded corners - pure industrial aesthetic.
    
    Args:
        label: Button text (keep lowercase for consistency)
        variant: Button style variant
        size: Button size
        icon: Optional icon character (e.g., "▶", "■", "✓")
        disabled: Whether button is disabled
        key: Unique Streamlit key
    
    Example:
        >>> btn = MossButton("start conversion", variant=ButtonVariant.PRIMARY, icon="▶")
        >>> btn.render()
        >>> if btn.clicked:
        ...     start_conversion()
    """
    label: str
    variant: ButtonVariant = ButtonVariant.DEFAULT
    size: ButtonSize = ButtonSize.MEDIUM
    icon: Optional[str] = None
    disabled: bool = False
    key: Optional[str] = None
    
    # Styling configuration
    _variants_css: dict = field(default_factory=lambda: {
        ButtonVariant.DEFAULT: {
            "bg": "var(--bg-elevated)",
            "color": "var(--text-main)",
            "border": "var(--border-color)",
            "hover_bg": "var(--bg-surface)",
        },
        ButtonVariant.PRIMARY: {
            "bg": "var(--accent-olive)",
            "color": "var(--bg-core)",
            "border": "var(--accent-olive)",
            "hover_bg": "var(--status-success)",
        },
        ButtonVariant.GHOST: {
            "bg": "transparent",
            "color": "var(--text-dim)",
            "border": "var(--border-color)",
            "hover_bg": "var(--bg-surface)",
        },
        ButtonVariant.DANGER: {
            "bg": "var(--accent-rust)",
            "color": "var(--text-main)",
            "border": "var(--accent-rust)",
            "hover_bg": "#8b2e02",
        },
    })
    
    _sizes_css: dict = field(default_factory=lambda: {
        ButtonSize.SMALL: {"padding": "4px 8px", "font_size": "var(--text-xs)"},
        ButtonSize.MEDIUM: {"padding": "8px 16px", "font_size": "var(--text-sm)"},
        ButtonSize.LARGE: {"padding": "12px 24px", "font_size": "var(--text-base)"},
    })
    
    def __post_init__(self):
        self._clicked = False
    
    @property
    def clicked(self) -> bool:
        """Whether the button was clicked in this render cycle."""
        return self._clicked
    
    def render(self) -> bool:
        """
        Render the button and return True if clicked.
        
        Returns:
            True if button was clicked, False otherwise
        """
        variant_styles = self._variants_css.get(self.variant, self._variants_css[ButtonVariant.DEFAULT])
        size_styles = self._sizes_css.get(self.size, self._sizes_css[ButtonSize.MEDIUM])
        
        unique_key = self.key or f"moss_btn_{hash(self.label + str(self.variant))}"
        
        # Generate CSS
        css = f"""
            <style>
            .moss-button-{unique_key} {{
                display: inline-flex;
                align-items: center;
                gap: var(--space-sm);
                padding: {size_styles['padding']};
                font-family: var(--font-mono);
                font-size: {size_styles['font_size']};
                font-weight: var(--font-medium);
                text-transform: lowercase;
                letter-spacing: 0.05em;
                background-color: {variant_styles['bg']};
                color: {variant_styles['color']};
                border: 1px solid {variant_styles['border']};
                border-radius: var(--radius);
                cursor: {'not-allowed' if self.disabled else 'pointer'};
                opacity: {0.5 if self.disabled else 1.0};
                transition: all 0.15s ease;
                user-select: none;
            }}
            .moss-button-{unique_key}:hover:not(:disabled) {{
                background-color: {variant_styles['hover_bg']};
                border-color: var(--border-focus);
            }}
            .moss-button-{unique_key}:active:not(:disabled) {{
                transform: translateY(1px);
            }}
            .moss-button-{unique_key} .icon {{
                font-size: 0.9em;
            }}
            </style>
        """
        
        st.markdown(css, unsafe_allow_html=True)
        
        # Build button HTML for display
        icon_html = f'<span class="icon">{self.icon}</span>' if self.icon else ""
        label_html = f'<span>{self.label.lower()}</span>'
        
        # Use Streamlit's native button for functionality
        button_html = f"""
        <div class="moss-button-{unique_key}">
            {icon_html}
            {label_html}
        </div>
        """
        
        # Render with Streamlit button
        self._clicked = st.button(
            f"{self.icon + ' ' if self.icon else ''}{self.label}",
            key=unique_key,
            disabled=self.disabled,
            use_container_width=False,
        )
        
        return self._clicked


def moss_button(
    label: str,
    variant: Literal["default", "primary", "ghost", "danger"] = "default",
    size: Literal["sm", "md", "lg"] = "md",
    icon: Optional[str] = None,
    disabled: bool = False,
    key: Optional[str] = None,
) -> bool:
    """
    Functional API for MossButton.
    
    Args:
        label: Button text
        variant: Button style variant
        size: Button size
        icon: Optional icon character
        disabled: Whether disabled
        key: Unique key
    
    Returns:
        True if clicked
    
    Example:
        >>> if moss_button("start", variant="primary", icon="▶"):
        ...     start_process()
    """
    variant_map = {
        "default": ButtonVariant.DEFAULT,
        "primary": ButtonVariant.PRIMARY,
        "ghost": ButtonVariant.GHOST,
        "danger": ButtonVariant.DANGER,
    }
    size_map = {
        "sm": ButtonSize.SMALL,
        "md": ButtonSize.MEDIUM,
        "lg": ButtonSize.LARGE,
    }
    
    btn = MossButton(
        label=label,
        variant=variant_map.get(variant, ButtonVariant.DEFAULT),
        size=size_map.get(size, ButtonSize.MEDIUM),
        icon=icon,
        disabled=disabled,
        key=key,
    )
    return btn.render()


# =============================================================================
# MossPanel Component
# =============================================================================

class PanelVariant(Enum):
    """Panel style variants."""
    DEFAULT = "default"      # Standard panel
    ELEVATED = "elevated"    # Higher elevation
    BORDERED = "bordered"    # Emphasized border
    GHOST = "ghost"          # Minimal/no background


@dataclass
class PanelHeader:
    """Panel header configuration."""
    title: str
    icon: Optional[str] = None
    action: Optional[str] = None  # Action button label


@dataclass
class MossPanel:
    """
    Industrial Moss panel container component.
    
    A brutalist container with sharp corners and consistent padding.
    
    Args:
        header: Optional panel header
        variant: Panel style variant
        padding: Internal padding size (xs, sm, md, lg)
        full_width: Whether panel expands to full width
        key: Unique Streamlit key
    
    Example:
        >>> panel = MossPanel(
        ...     header=PanelHeader("conversion status", icon="◉"),
        ...     variant=PanelVariant.ELEVATED
        ... )
        >>> with panel:
        ...     st.write("Content goes here")
    """
    header: Optional[PanelHeader] = None
    variant: PanelVariant = PanelVariant.DEFAULT
    padding: Literal["xs", "sm", "md", "lg"] = "md"
    full_width: bool = True
    key: Optional[str] = None
    
    _variants_css: dict = field(default_factory=lambda: {
        PanelVariant.DEFAULT: {
            "bg": "var(--bg-surface)",
            "border": "var(--border-color)",
            "shadow": "none",
        },
        PanelVariant.ELEVATED: {
            "bg": "var(--bg-elevated)",
            "border": "var(--border-color)",
            "shadow": "0 4px 0 rgba(0,0,0,0.3)",
        },
        PanelVariant.BORDERED: {
            "bg": "var(--bg-surface)",
            "border": "var(--border-accent)",
            "shadow": "none",
        },
        PanelVariant.GHOST: {
            "bg": "transparent",
            "border": "var(--border-color)",
            "shadow": "none",
        },
    })
    
    _padding_css: dict = field(default_factory=lambda: {
        "xs": "var(--space-xs)",
        "sm": "var(--space-sm)",
        "md": "var(--space-md)",
        "lg": "var(--space-lg)",
    })
    
    def __enter__(self):
        """Enter context manager."""
        self._start_container()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager."""
        self._end_container()
    
    def _start_container(self):
        """Start the panel container."""
        variant_styles = self._variants_css.get(self.variant, self._variants_css[PanelVariant.DEFAULT])
        padding = self._padding_css.get(self.padding, "var(--space-md)")
        unique_key = self.key or f"moss_panel_{id(self)}"
        
        css = f"""
            <style>
            .moss-panel-{unique_key} {{
                background-color: {variant_styles['bg']};
                border: 1px solid {variant_styles['border']};
                border-radius: var(--radius);
                box-shadow: {variant_styles['shadow']};
                margin-bottom: var(--space-md);
            }}
            .moss-panel-{unique_key} .moss-panel-header {{
                display: flex;
                align-items: center;
                justify-content: space-between;
                padding: {padding};
                border-bottom: 1px solid {variant_styles['border']};
                background-color: rgba(0,0,0,0.1);
            }}
            .moss-panel-{unique_key} .moss-panel-title {{
                font-family: var(--font-mono);
                font-size: var(--text-sm);
                font-weight: var(--font-bold);
                text-transform: uppercase;
                letter-spacing: 0.1em;
                color: var(--text-dim);
                display: flex;
                align-items: center;
                gap: var(--space-sm);
            }}
            .moss-panel-{unique_key} .moss-panel-icon {{
                color: var(--accent-olive);
            }}
            .moss-panel-{unique_key} .moss-panel-content {{
                padding: {padding};
            }}
            </style>
        """
        
        st.markdown(css, unsafe_allow_html=True)
        
        # Start panel HTML
        st.markdown(f'<div class="moss-panel-{unique_key}">', unsafe_allow_html=True)
        
        # Render header if provided
        if self.header:
            icon_html = f'<span class="moss-panel-icon">{self.header.icon}</span>' if self.header.icon else ""
            action_html = f'<span style="font-size: var(--text-xs); color: var(--text-faded);">{self.header.action}</span>' if self.header.action else ""
            st.markdown(
                f'<div class="moss-panel-header">'
                f'<div class="moss-panel-title">{icon_html}{self.header.title.lower()}</div>'
                f'{action_html}'
                f'</div>',
                unsafe_allow_html=True
            )
        
        # Start content area
        st.markdown(f'<div class="moss-panel-content">', unsafe_allow_html=True)
    
    def _end_container(self):
        """End the panel container."""
        st.markdown('</div></div>', unsafe_allow_html=True)


def moss_panel(
    title: Optional[str] = None,
    icon: Optional[str] = None,
    variant: Literal["default", "elevated", "bordered", "ghost"] = "default",
    padding: Literal["xs", "sm", "md", "lg"] = "md",
    key: Optional[str] = None,
):
    """
    Functional API for MossPanel as context manager.
    
    Args:
        title: Panel title
        icon: Optional icon character
        variant: Panel style variant
        padding: Internal padding
        key: Unique key
    
    Example:
        >>> with moss_panel("status", icon="◉", variant="elevated"):
        ...     st.write("Panel content")
    """
    variant_map = {
        "default": PanelVariant.DEFAULT,
        "elevated": PanelVariant.ELEVATED,
        "bordered": PanelVariant.BORDERED,
        "ghost": PanelVariant.GHOST,
    }
    
    header = PanelHeader(title=title, icon=icon) if title else None
    
    return MossPanel(
        header=header,
        variant=variant_map.get(variant, PanelVariant.DEFAULT),
        padding=padding,
        key=key,
    )


# =============================================================================
# MossProgress Component
# =============================================================================

class ProgressVariant(Enum):
    """Progress indicator variants."""
    LINEAR = "linear"        # Horizontal bar
    CIRCULAR = "circular"    # Circular/spinner style
    BLOCKS = "blocks"        # ASCII block style


@dataclass
class MossProgress:
    """
    Industrial Moss progress indicator component.
    
    Various progress visualization styles fitting the brutalist aesthetic.
    
    Args:
        value: Current progress (0.0 to 1.0)
        variant: Progress indicator style
        label: Optional label text
        show_value: Whether to show percentage value
        width: Width in characters (for block style) or pixels
        key: Unique Streamlit key
    
    Example:
        >>> progress = MossProgress(value=0.42, variant=ProgressVariant.BLOCKS)
        >>> progress.render()
        
        >>> # Or use with context manager for automatic updates
        >>> with MossProgress(total=100, variant=ProgressVariant.LINEAR) as p:
        ...     for i in range(100):
        ...         p.update(i + 1)
    """
    value: float = 0.0
    variant: ProgressVariant = ProgressVariant.BLOCKS
    label: Optional[str] = None
    show_value: bool = True
    width: int = 40
    key: Optional[str] = None
    
    def __post_init__(self):
        self._total: Optional[int] = None
        self._current: int = 0
    
    def render(self) -> None:
        """Render the progress indicator."""
        if self.variant == ProgressVariant.LINEAR:
            self._render_linear()
        elif self.variant == ProgressVariant.CIRCULAR:
            self._render_circular()
        else:
            self._render_blocks()
    
    def _render_blocks(self) -> None:
        """Render ASCII block-style progress bar."""
        unique_key = self.key or f"moss_progress_{id(self)}"
        
        # Clamp value to [0, 1]
        value = max(0.0, min(1.0, self.value))
        filled = int(value * self.width)
        empty = self.width - filled
        
        blocks = "█" * filled + "░" * empty
        percentage = f"{int(value * 100)}%" if self.show_value else ""
        
        css = f"""
            <style>
            .moss-progress-blocks-{unique_key} {{
                font-family: var(--font-mono);
                font-size: var(--text-sm);
                color: var(--accent-olive);
                letter-spacing: 0;
                white-space: pre;
            }}
            .moss-progress-blocks-{unique_key} .label {{
                color: var(--text-dim);
                text-transform: lowercase;
                margin-bottom: var(--space-xs);
            }}
            .moss-progress-blocks-{unique_key} .value {{
                color: var(--text-faded);
                margin-left: var(--space-sm);
            }}
            </style>
        """
        
        label_html = f'<div class="label">{self.label.lower()}</div>' if self.label else ""
        
        st.markdown(css, unsafe_allow_html=True)
        st.markdown(
            f'<div class="moss-progress-blocks-{unique_key}">'
            f'{label_html}'
            f'<span>[{blocks}]</span>'
            f'<span class="value">{percentage}</span>'
            f'</div>',
            unsafe_allow_html=True
        )
    
    def _render_linear(self) -> None:
        """Render linear progress bar with CSS."""
        unique_key = self.key or f"moss_progress_{id(self)}"
        value = max(0.0, min(1.0, self.value))
        percentage = int(value * 100)
        
        css = f"""
            <style>
            .moss-progress-linear-{unique_key} {{
                margin-bottom: var(--space-sm);
            }}
            .moss-progress-linear-{unique_key} .label {{
                font-family: var(--font-mono);
                font-size: var(--text-xs);
                color: var(--text-dim);
                text-transform: lowercase;
                margin-bottom: var(--space-xs);
            }}
            .moss-progress-linear-{unique_key} .bar-container {{
                width: 100%;
                height: 8px;
                background-color: var(--bg-core);
                border: 1px solid var(--border-color);
            }}
            .moss-progress-linear-{unique_key} .bar-fill {{
                width: {percentage}%;
                height: 100%;
                background-color: var(--accent-olive);
                transition: width 0.3s ease;
            }}
            .moss-progress-linear-{unique_key} .value {{
                font-family: var(--font-mono);
                font-size: var(--text-xs);
                color: var(--text-faded);
                text-align: right;
                margin-top: var(--space-xs);
            }}
            </style>
        """
        
        label_html = f'<div class="label">{self.label.lower()}</div>' if self.label else ""
        value_html = f'<div class="value">{percentage}%</div>' if self.show_value else ""
        
        st.markdown(css, unsafe_allow_html=True)
        st.markdown(
            f'<div class="moss-progress-linear-{unique_key}">'
            f'{label_html}'
            f'<div class="bar-container"><div class="bar-fill"></div></div>'
            f'{value_html}'
            f'</div>',
            unsafe_allow_html=True
        )
    
    def _render_circular(self) -> None:
        """Render circular progress indicator."""
        unique_key = self.key or f"moss_progress_{id(self)}"
        value = max(0.0, min(1.0, self.value))
        percentage = int(value * 100)
        
        # Calculate circle properties
        radius = 20
        circumference = 2 * 3.14159 * radius
        stroke_dashoffset = circumference * (1 - value)
        
        css = f"""
            <style>
            .moss-progress-circular-{unique_key} {{
                display: flex;
                align-items: center;
                gap: var(--space-md);
            }}
            .moss-progress-circular-{unique_key} .circle-container {{
                position: relative;
                width: 50px;
                height: 50px;
            }}
            .moss-progress-circular-{unique_key} svg {{
                transform: rotate(-90deg);
            }}
            .moss-progress-circular-{unique_key} .circle-bg {{
                fill: none;
                stroke: var(--bg-core);
                stroke-width: 4;
            }}
            .moss-progress-circular-{unique_key} .circle-progress {{
                fill: none;
                stroke: var(--accent-olive);
                stroke-width: 4;
                stroke-dasharray: {circumference};
                stroke-dashoffset: {stroke_dashoffset};
                transition: stroke-dashoffset 0.3s ease;
            }}
            .moss-progress-circular-{unique_key} .info {{
                display: flex;
                flex-direction: column;
            }}
            .moss-progress-circular-{unique_key} .label {{
                font-family: var(--font-mono);
                font-size: var(--text-xs);
                color: var(--text-dim);
                text-transform: lowercase;
            }}
            .moss-progress-circular-{unique_key} .value {{
                font-family: var(--font-mono);
                font-size: var(--text-lg);
                font-weight: var(--font-bold);
                color: var(--text-main);
            }}
            </style>
        """
        
        label_html = f'<div class="label">{self.label.lower()}</div>' if self.label else ""
        value_html = f'<div class="value">{percentage}%</div>' if self.show_value else ""
        
        st.markdown(css, unsafe_allow_html=True)
        st.markdown(
            f'<div class="moss-progress-circular-{unique_key}">'
            f'<div class="circle-container">'
            f'<svg width="50" height="50">'
            f'<circle class="circle-bg" cx="25" cy="25" r="{radius}"/>'
            f'<circle class="circle-progress" cx="25" cy="25" r="{radius}"/>'
            f'</svg>'
            f'</div>'
            f'<div class="info">{label_html}{value_html}</div>'
            f'</div>',
            unsafe_allow_html=True
        )


def moss_progress(
    value: float,
    variant: Literal["linear", "circular", "blocks"] = "blocks",
    label: Optional[str] = None,
    show_value: bool = True,
    width: int = 40,
    key: Optional[str] = None,
) -> None:
    """
    Functional API for MossProgress.
    
    Args:
        value: Current progress (0.0 to 1.0)
        variant: Progress style
        label: Optional label
        show_value: Show percentage
        width: Width (chars for blocks, ignored for others)
        key: Unique key
    
    Example:
        >>> moss_progress(0.42, variant="blocks", label="processing")
        [████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░] 42%
    """
    variant_map = {
        "linear": ProgressVariant.LINEAR,
        "circular": ProgressVariant.CIRCULAR,
        "blocks": ProgressVariant.BLOCKS,
    }
    
    progress = MossProgress(
        value=value,
        variant=variant_map.get(variant, ProgressVariant.BLOCKS),
        label=label,
        show_value=show_value,
        width=width,
        key=key,
    )
    progress.render()


# =============================================================================
# MossBadge Component
# =============================================================================

class BadgeVariant(Enum):
    """Badge style variants."""
    DEFAULT = "default"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    INFO = "info"


@dataclass
class MossBadge:
    """
    Industrial Moss badge/label component.
    
    Small status indicator badges for inline use.
    
    Args:
        text: Badge text (keep short, uppercase)
        variant: Badge color variant
        icon: Optional icon character
        key: Unique Streamlit key
    
    Example:
        >>> MossBadge("active", variant=BadgeVariant.SUCCESS, icon="●").render()
    """
    text: str
    variant: BadgeVariant = BadgeVariant.DEFAULT
    icon: Optional[str] = None
    key: Optional[str] = None
    
    _variants_css: dict = field(default_factory=lambda: {
        BadgeVariant.DEFAULT: {"bg": "var(--bg-elevated)", "color": "var(--text-dim)", "border": "var(--border-color)"},
        BadgeVariant.SUCCESS: {"bg": "rgba(121, 116, 14, 0.2)", "color": "var(--status-success)", "border": "var(--status-success)"},
        BadgeVariant.WARNING: {"bg": "rgba(181, 118, 20, 0.2)", "color": "var(--accent-gold)", "border": "var(--accent-gold)"},
        BadgeVariant.ERROR: {"bg": "rgba(157, 0, 6, 0.2)", "color": "var(--status-error)", "border": "var(--status-error)"},
        BadgeVariant.INFO: {"bg": "rgba(69, 133, 136, 0.2)", "color": "var(--status-info)", "border": "var(--status-info)"},
    })
    
    def render(self) -> None:
        """Render the badge."""
        styles = self._variants_css.get(self.variant, self._variants_css[BadgeVariant.DEFAULT])
        unique_key = self.key or f"moss_badge_{hash(self.text + str(self.variant))}"
        
        css = f"""
            <style>
            .moss-badge-{unique_key} {{
                display: inline-flex;
                align-items: center;
                gap: 4px;
                padding: 2px 8px;
                font-family: var(--font-mono);
                font-size: var(--text-xs);
                font-weight: var(--font-bold);
                text-transform: uppercase;
                letter-spacing: 0.05em;
                background-color: {styles['bg']};
                color: {styles['color']};
                border: 1px solid {styles['border']};
                border-radius: var(--radius);
            }}
            </style>
        """
        
        icon_html = f"{self.icon} " if self.icon else ""
        
        st.markdown(css, unsafe_allow_html=True)
        st.markdown(
            f'<span class="moss-badge-{unique_key}">{icon_html}{self.text.upper()}</span>',
            unsafe_allow_html=True
        )


def moss_badge(
    text: str,
    variant: Literal["default", "success", "warning", "error", "info"] = "default",
    icon: Optional[str] = None,
    key: Optional[str] = None,
) -> None:
    """
    Functional API for MossBadge.
    
    Args:
        text: Badge text
        variant: Badge color variant
        icon: Optional icon character
        key: Unique key
    
    Example:
        >>> moss_badge("ready", variant="success", icon="✓")
    """
    variant_map = {
        "default": BadgeVariant.DEFAULT,
        "success": BadgeVariant.SUCCESS,
        "warning": BadgeVariant.WARNING,
        "error": BadgeVariant.ERROR,
        "info": BadgeVariant.INFO,
    }
    
    badge = MossBadge(
        text=text,
        variant=variant_map.get(variant, BadgeVariant.DEFAULT),
        icon=icon,
        key=key,
    )
    badge.render()


# =============================================================================
# MossDivider Component
# =============================================================================

def moss_divider(
    label: Optional[str] = None,
    style: Literal["solid", "dashed", "dots"] = "solid",
    key: Optional[str] = None,
) -> None:
    """
    Industrial Moss divider component.
    
    Section divider with optional label.
    
    Args:
        label: Optional section label (uppercase)
        style: Line style
        key: Unique key
    
    Example:
        >>> moss_divider("settings", style="dashed")
    """
    unique_key = key or f"moss_divider_{hash(str(label) + style)}"
    
    style_map = {
        "solid": "border-top: 1px solid var(--border-color);",
        "dashed": "border-top: 1px dashed var(--border-color);",
        "dots": "border-top: 1px dotted var(--border-color);",
    }
    
    border_style = style_map.get(style, style_map["solid"])
    
    css = f"""
        <style>
        .moss-divider-{unique_key} {{
            display: flex;
            align-items: center;
            margin: var(--space-lg) 0;
        }}
        .moss-divider-{unique_key} .line {{
            flex: 1;
            {border_style}
        }}
        .moss-divider-{unique_key} .label {{
            font-family: var(--font-mono);
            font-size: var(--text-xs);
            font-weight: var(--font-bold);
            text-transform: uppercase;
            letter-spacing: 0.1em;
            color: var(--text-faded);
            padding: 0 var(--space-md);
        }}
        </style>
    """
    
    label_html = f'<span class="label">{label.upper()}</span>' if label else ""
    
    st.markdown(css, unsafe_allow_html=True)
    st.markdown(
        f'<div class="moss-divider-{unique_key}">'
        f'<div class="line"></div>'
        f'{label_html}'
        f'<div class="line"></div>'
        f'</div>',
        unsafe_allow_html=True
    )
