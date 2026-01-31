"""
Source File Panel
=================
File upload and source information display.
"""

from dataclasses import dataclass
from typing import Optional, BinaryIO, Callable
from pathlib import Path
import streamlit as st


@dataclass
class SourceFile:
    """Uploaded source file information."""
    filename: str
    file_type: str  # "pdf" | "epub"
    size_bytes: int
    content: Optional[BinaryIO] = None
    preview_text: Optional[str] = None


def _format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def _get_file_extension(filename: str) -> str:
    """Get file extension in lowercase."""
    return Path(filename).suffix.lower().lstrip('.')


def _is_valid_file_type(filename: str) -> bool:
    """Check if file type is supported."""
    ext = _get_file_extension(filename)
    return ext in ['pdf', 'epub']


def render_source_panel(
    source: Optional[SourceFile] = None,
    on_upload: Optional[Callable[[SourceFile], None]] = None,
    on_remove: Optional[Callable[[], None]] = None,
    on_proceed: Optional[Callable[[], None]] = None,
    key: Optional[str] = None
) -> Optional[SourceFile]:
    """
    Render source file panel with brutalist styling.
    
    Layout (empty state):
    ┌─ SOURCE FILE ───────────────────────────┐
    │                                         │
    │  [ DROP FILE HERE ]                     │
    │                                         │
    │  ─ or ─                                 │
    │                                         │
    │  [ BROWSE FILES ]                       │
    │                                         │
    └─────────────────────────────────────────┘
    
    Layout (file loaded):
    ┌─ SOURCE FILE ───────────────────────────┐
    │                                         │
    │  name:    book.epub                     │
    │  type:    epub                          │
    │  size:    2.4 MB                        │
    │                                         │
    │  preview:                               │
    │  ┌─────────────────────────────────┐    │
    │  │ Lorem ipsum dolor sit amet...   │    │
    │  └─────────────────────────────────┘    │
    │                                         │
    │  [ REMOVE ]  [ PROCEED ]                │
    │                                         │
    └─────────────────────────────────────────┘
    
    Args:
        source: Currently loaded source file (if any)
        on_upload: Callback when file is uploaded
        on_remove: Callback when file is removed
        on_proceed: Callback when proceeding with file
        key: Unique key for Streamlit
        
    Returns:
        The uploaded source file, or None if no file
    """
    unique_key = key or "source_panel"
    
    # Panel CSS
    css = f"""
        <style>
        .moss-source-panel-{unique_key} {{
            background-color: var(--bg-surface);
            border: 1px solid var(--border-color);
            padding: var(--space-md);
        }}
        .moss-source-panel-{unique_key} .moss-panel-title {{
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
        .moss-source-panel-{unique_key} .moss-file-info {{
            font-family: var(--font-mono);
            font-size: var(--text-sm);
            margin-bottom: var(--space-xs);
        }}
        .moss-source-panel-{unique_key} .moss-file-info-label {{
            color: var(--text-dim);
            text-transform: lowercase;
            display: inline-block;
            min-width: 8ch;
        }}
        .moss-source-panel-{unique_key} .moss-file-info-label::after {{
            content: ":";
        }}
        .moss-source-panel-{unique_key} .moss-file-info-value {{
            color: var(--text-main);
        }}
        .moss-source-panel-{unique_key} .moss-preview-box {{
            background-color: var(--bg-core);
            border: 1px solid var(--border-color);
            padding: var(--space-sm);
            font-family: var(--font-mono);
            font-size: var(--text-xs);
            color: var(--text-dim);
            max-height: 150px;
            overflow-y: auto;
            margin-top: var(--space-sm);
            white-space: pre-wrap;
            word-break: break-word;
        }}
        .moss-source-panel-{unique_key} .moss-preview-label {{
            font-family: var(--font-mono);
            font-size: var(--text-sm);
            color: var(--text-dim);
            text-transform: lowercase;
            margin-top: var(--space-md);
        }}
        .moss-source-panel-{unique_key} .moss-preview-label::after {{
            content: ":";
        }}
        .moss-source-panel-{unique_key} .moss-button-row {{
            display: flex;
            gap: var(--space-md);
            margin-top: var(--space-md);
        }}
        </style>
    """
    
    st.markdown(css, unsafe_allow_html=True)
    st.markdown(
        f'<div class="moss-source-panel-{unique_key}">'
        f'<div class="moss-panel-title">source file</div>',
        unsafe_allow_html=True,
    )
    
    result_source = source
    
    if source is None:
        # Empty state - show file uploader
        uploaded_file = st.file_uploader(
            "",
            type=['pdf', 'epub'],
            key=f"{unique_key}_uploader",
            label_visibility="collapsed",
        )
        
        if uploaded_file is not None:
            file_type = _get_file_extension(uploaded_file.name)
            result_source = SourceFile(
                filename=uploaded_file.name,
                file_type=file_type,
                size_bytes=len(uploaded_file.getvalue()),
                content=uploaded_file,
            )
            if on_upload:
                on_upload(result_source)
            st.rerun()
    else:
        # File loaded - show info
        st.markdown(
            f'<div class="moss-file-info">'
            f'<span class="moss-file-info-label">name</span>'
            f'<span class="moss-file-info-value">{source.filename}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="moss-file-info">'
            f'<span class="moss-file-info-label">type</span>'
            f'<span class="moss-file-info-value">{source.file_type}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="moss-file-info">'
            f'<span class="moss-file-info-label">size</span>'
            f'<span class="moss-file-info-value">{_format_file_size(source.size_bytes)}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
        
        # Preview
        if source.preview_text:
            st.markdown(
                '<div class="moss-preview-label">preview</div>',
                unsafe_allow_html=True,
            )
            preview = source.preview_text[:500] + "..." if len(source.preview_text) > 500 else source.preview_text
            st.markdown(
                f'<div class="moss-preview-box">{preview}</div>',
                unsafe_allow_html=True,
            )
        
        # Action buttons
        col1, col2, _ = st.columns([1, 1, 2])
        
        with col1:
            if st.button("remove", key=f"{unique_key}_remove"):
                result_source = None
                if on_remove:
                    on_remove()
                st.rerun()
        
        with col2:
            if st.button("proceed", key=f"{unique_key}_proceed", type="primary"):
                if on_proceed:
                    on_proceed()
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    return result_source


def render_source_panel_simple(
    on_file_selected: Optional[Callable[[SourceFile], None]] = None,
    key: Optional[str] = None
) -> Optional[SourceFile]:
    """
    Simplified source panel with just file upload.
    
    Args:
        on_file_selected: Callback when file is selected
        key: Unique key for Streamlit
        
    Returns:
        The selected source file, or None
    """
    unique_key = key or "source_simple"
    
    uploaded_file = st.file_uploader(
        "SOURCE FILE",
        type=['pdf', 'epub'],
        key=f"{unique_key}_uploader",
    )
    
    if uploaded_file is not None:
        file_type = _get_file_extension(uploaded_file.name)
        source = SourceFile(
            filename=uploaded_file.name,
            file_type=file_type,
            size_bytes=len(uploaded_file.getvalue()),
            content=uploaded_file,
        )
        if on_file_selected:
            on_file_selected(source)
        return source
    
    return None
