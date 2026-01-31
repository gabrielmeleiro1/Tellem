"""
Industrial Moss Theme Provider
==============================
Centralized theme configuration and CSS generation for the brutalist UI.
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional
from pathlib import Path
import streamlit as st


@dataclass(frozen=True)
class IndustrialMossTheme:
    """Complete theme definition for Industrial Moss aesthetic."""
    
    # Color definitions
    colors: Dict[str, str]
    typography: Dict[str, str]
    spacing: Dict[str, str]
    borders: Dict[str, str]
    
    def __init__(
        self,
        colors: Optional[Dict[str, str]] = None,
        typography: Optional[Dict[str, str]] = None,
        spacing: Optional[Dict[str, str]] = None,
        borders: Optional[Dict[str, str]] = None,
    ):
        # Use object.__setattr__ since dataclass is frozen
        object.__setattr__(
            self,
            'colors',
            colors or {
                # Core Background Colors
                'bg-core': '#1a1b1a',
                'bg-surface': '#282828',
                'bg-elevated': '#32302f',
                
                # Border Colors
                'border-color': '#3c3836',
                'border-focus': '#504945',
                'border-accent': '#665c54',
                
                # Text Colors
                'text-main': '#d5c4a1',
                'text-dim': '#a89984',
                'text-faded': '#7c6f64',
                
                # Accent Colors
                'accent-olive': '#859900',
                'accent-rust': '#af3a03',
                'accent-gold': '#b57614',
                
                # Status Colors
                'status-active': '#98971a',
                'status-success': '#79740e',
                'status-error': '#9d0006',
                'status-info': '#458588',
            }
        )
        object.__setattr__(
            self,
            'typography',
            typography or {
                'font-mono': "'JetBrains Mono', 'IBM Plex Mono', 'Iosevka', 'Courier New', monospace",
                'text-xs': '10px',
                'text-sm': '12px',
                'text-base': '14px',
                'text-lg': '16px',
                'text-xl': '18px',
                'text-2xl': '22px',
                'font-normal': '400',
                'font-medium': '500',
                'font-bold': '700',
            }
        )
        object.__setattr__(
            self,
            'spacing',
            spacing or {
                'space-xs': '2px',
                'space-sm': '4px',
                'space-md': '8px',
                'space-lg': '12px',
                'space-xl': '16px',
                'grid-gap': '1px',
            }
        )
        object.__setattr__(
            self,
            'borders',
            borders or {
                'radius': '0px',
                'border-thin': '1px',
                'border-thick': '2px',
            }
        )
    
    def generate_css(self) -> str:
        """Generate complete CSS with all custom properties."""
        css_parts = [":root {"]
        
        # Colors
        for key, value in self.colors.items():
            css_parts.append(f"    --{key}: {value};")
        
        # Typography
        for key, value in self.typography.items():
            css_parts.append(f"    --{key}: {value};")
        
        # Spacing
        for key, value in self.spacing.items():
            css_parts.append(f"    --{key}: {value};")
        
        # Borders
        for key, value in self.borders.items():
            css_parts.append(f"    --{key}: {value};")
        
        css_parts.append("}")
        return "\n".join(css_parts)
    
    def get_streamlit_css(self) -> str:
        """Generate Streamlit-compatible CSS overrides."""
        return f"""
        <style>
        {self.generate_css()}
        
        .stApp {{
            background-color: var(--bg-core) !important;
            color: var(--text-main) !important;
            font-family: var(--font-mono) !important;
        }}
        </style>
        """
    
    def get_color(self, name: str) -> str:
        """Get a color by name."""
        return self.colors.get(name, '#000000')
    
    def get_font_size(self, size: str) -> str:
        """Get a font size by name."""
        return self.typography.get(f'text-{size}', '14px')


# Default theme instance
DEFAULT_THEME = IndustrialMossTheme()


def load_fonts() -> None:
    """Load JetBrains Mono from Google Fonts."""
    st.markdown(
        """
        <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
        """,
        unsafe_allow_html=True,
    )


def load_css_from_file(css_path: Optional[Path] = None) -> None:
    """Load CSS from the industrial_moss.css file."""
    if css_path is None:
        css_path = Path(__file__).parent.parent.parent / "assets" / "css" / "industrial_moss.css"
    
    if css_path.exists():
        with open(css_path, 'r') as f:
            css_content = f.read()
        st.markdown(f"<style>{css_content}</style>", unsafe_allow_html=True)
    else:
        # Fallback to generated CSS
        st.markdown(DEFAULT_THEME.get_streamlit_css(), unsafe_allow_html=True)


def apply_theme(css_path: Optional[Path] = None) -> None:
    """Apply the complete Industrial Moss theme to Streamlit."""
    load_fonts()
    load_css_from_file(css_path)


def get_theme() -> IndustrialMossTheme:
    """Get the default theme instance."""
    return DEFAULT_THEME
