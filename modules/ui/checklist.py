"""
Library Checklist Component
===========================
File-system based library explorer for navigating /output directory.
Displays both text (markdown) and audio files with an interactive checklist interface.
"""

import streamlit as st
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime
import base64


@dataclass
class ChapterItem:
    """Represents a chapter with both text and audio components."""
    number: int
    title: str
    text_path: Optional[Path] = None
    audio_path: Optional[Path] = None
    is_playing: bool = False
    is_selected: bool = False


@dataclass
class BookItem:
    """Represents a book in the output directory."""
    name: str
    path: Path
    source_md: Optional[Path] = None
    m4b_file: Optional[Path] = None
    chapters_dir: Optional[Path] = None
    chapters: List[ChapterItem] = field(default_factory=list)
    created_at: Optional[datetime] = None
    is_expanded: bool = False
    is_selected: bool = False


def scan_output_directory(output_dir: Path = Path("output")) -> List[BookItem]:
    """
    Scan the output directory for all book folders.
    
    Returns:
        List of BookItem objects sorted by creation date (newest first)
    """
    books = []
    
    if not output_dir.exists():
        return books
    
    for book_path in output_dir.iterdir():
        if not book_path.is_dir():
            continue
            
        # Skip hidden directories
        if book_path.name.startswith(".") or book_path.name.startswith("__"):
            continue
        
        book = BookItem(
            name=book_path.name,
            path=book_path,
            created_at=datetime.fromtimestamp(book_path.stat().st_mtime)
        )
        
        # Look for source.md
        source_md = book_path / "source.md"
        if source_md.exists():
            book.source_md = source_md
        
        # Look for m4b file
        for f in book_path.glob("*.m4b"):
            book.m4b_file = f
            break
        
        # Look for chapters directory
        chapters_dir = book_path / "chapters"
        if chapters_dir.exists():
            book.chapters_dir = chapters_dir
            book.chapters = scan_chapters(chapters_dir)
        
        books.append(book)
    
    # Sort by creation date (newest first)
    books.sort(key=lambda b: b.created_at or datetime.min, reverse=True)
    
    return books


def scan_chapters(chapters_dir: Path) -> List[ChapterItem]:
    """
    Scan chapters directory for text and audio files.
    
    Returns:
        List of ChapterItem objects sorted by chapter number
    """
    chapters = []
    
    # Find all audio files (mp3)
    audio_files = list(chapters_dir.glob("*.mp3"))
    
    # Find all cleaned markdown files
    text_files = list(chapters_dir.glob("*_cleaned.md"))
    
    # Create a mapping based on chapter numbers
    chapter_map = {}
    
    # Process audio files
    for audio_file in audio_files:
        # Parse filename like "01_Chapter Title.mp3" or "01_Full Document.mp3"
        name = audio_file.stem
        
        # Try to extract chapter number
        number = 0
        title = name
        
        if "_" in name:
            parts = name.split("_", 1)
            try:
                number = int(parts[0])
                title = parts[1]
            except ValueError:
                title = name
        
        if number not in chapter_map:
            chapter_map[number] = ChapterItem(number=number, title=title)
        chapter_map[number].audio_path = audio_file
    
    # Process text files
    for text_file in text_files:
        # Parse filename like "chapter_01_cleaned.md"
        name = text_file.stem
        
        # Try to extract chapter number
        number = 0
        
        if "chapter_" in name:
            try:
                number_str = name.replace("chapter_", "").replace("_cleaned", "")
                number = int(number_str)
            except ValueError:
                pass
        
        # Find matching chapter or create new
        if number not in chapter_map:
            chapter_map[number] = ChapterItem(number=number, title=f"Chapter {number}")
        chapter_map[number].text_path = text_file
    
    chapters = list(chapter_map.values())
    chapters.sort(key=lambda c: c.number)
    
    return chapters


def format_file_size(path: Optional[Path]) -> str:
    """Format file size for display."""
    if not path or not path.exists():
        return "--"
    
    size_bytes = path.stat().st_size
    
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


def format_duration_from_size(audio_path: Optional[Path]) -> str:
    """Estimate duration from file size (rough approximation for MP3)."""
    if not audio_path or not audio_path.exists():
        return "--:--"
    
    # Rough estimate: ~1MB per minute at 128kbps
    size_mb = audio_path.stat().st_size / (1024 * 1024)
    minutes = int(size_mb)
    seconds = int((size_mb - minutes) * 60)
    
    return f"{minutes}:{seconds:02d}"


def get_status_icon(chapter: ChapterItem) -> str:
    """Get status icon for a chapter."""
    has_text = chapter.text_path is not None
    has_audio = chapter.audio_path is not None
    
    if has_text and has_audio:
        return "[OK]"  # Complete
    elif has_audio:
        return "[A]"  # Audio only
    elif has_text:
        return "[T]"  # Text only
    else:
        return "[ ]"  # Empty


def get_status_color(chapter: ChapterItem) -> str:
    """Get status color for a chapter."""
    has_text = chapter.text_path is not None
    has_audio = chapter.audio_path is not None
    
    if has_text and has_audio:
        return "#00FF00"  # Green - Complete
    elif has_audio:
        return "#FFB000"  # Amber - Audio only
    elif has_text:
        return "#00CCFF"  # Cyan - Text only
    else:
        return "#555555"  # Gray - Empty


# ============================================
# SESSION STATE MANAGEMENT
# ============================================

def init_checklist_state():
    """Initialize checklist state in session."""
    if "checklist_search" not in st.session_state:
        st.session_state.checklist_search = ""
    if "checklist_selected_book" not in st.session_state:
        st.session_state.checklist_selected_book = None
    if "checklist_expanded_books" not in st.session_state:
        st.session_state.checklist_expanded_books = set()
    if "checklist_sort" not in st.session_state:
        st.session_state.checklist_sort = "newest"
    if "checklist_view_mode" not in st.session_state:
        st.session_state.checklist_view_mode = "list"  # list or compact
    if "checklist_currently_playing" not in st.session_state:
        st.session_state.checklist_currently_playing = None
    if "checklist_selected_chapters" not in st.session_state:
        st.session_state.checklist_selected_chapters = set()


def toggle_book_expansion(book_name: str):
    """Toggle book expansion state."""
    if book_name in st.session_state.checklist_expanded_books:
        st.session_state.checklist_expanded_books.remove(book_name)
    else:
        st.session_state.checklist_expanded_books.add(book_name)


def select_book(book_name: str):
    """Select a book for detailed view."""
    st.session_state.checklist_selected_book = book_name


def clear_book_selection():
    """Clear book selection."""
    st.session_state.checklist_selected_book = None


def toggle_chapter_selection(book_name: str, chapter_number: int):
    """Toggle chapter selection."""
    key = f"{book_name}:{chapter_number}"
    if key in st.session_state.checklist_selected_chapters:
        st.session_state.checklist_selected_chapters.remove(key)
    else:
        st.session_state.checklist_selected_chapters.add(key)


def play_chapter(book_name: str, chapter: ChapterItem):
    """Set a chapter as currently playing."""
    st.session_state.checklist_currently_playing = {
        "book": book_name,
        "chapter": chapter.number,
        "path": str(chapter.audio_path) if chapter.audio_path else None
    }


# ============================================
# RENDER COMPONENTS
# ============================================

def render_chapter_row(book: BookItem, chapter: ChapterItem, is_expanded: bool = False):
    """Render a single chapter row with checkbox and actions."""
    key = f"{book.name}:{chapter.number}"
    is_selected = key in st.session_state.checklist_selected_chapters
    status_icon = get_status_icon(chapter)
    status_color = get_status_color(chapter)
    
    col1, col2, col3, col4, col5 = st.columns([0.5, 0.5, 4, 2, 2])
    
    with col1:
        # Selection checkbox
        if st.checkbox(
            "",
            value=is_selected,
            key=f"chk_{key}",
            label_visibility="collapsed"
        ):
            if not is_selected:
                st.session_state.checklist_selected_chapters.add(key)
        else:
            if is_selected:
                st.session_state.checklist_selected_chapters.discard(key)
    
    with col2:
        # Status icon
        st.markdown(
            f"<span style='color: {status_color}; font-weight: bold;'>{status_icon}</span>",
            unsafe_allow_html=True
        )
    
    with col3:
        # Chapter title
        title_display = f"**{chapter.number:02d}.** {chapter.title}"
        st.markdown(title_display)
    
    with col4:
        # File info
        if chapter.audio_path:
            size = format_file_size(chapter.audio_path)
            duration = format_duration_from_size(chapter.audio_path)
            st.markdown(f"<small>`{duration}` | `{size}`</small>", unsafe_allow_html=True)
        elif chapter.text_path:
            size = format_file_size(chapter.text_path)
            st.markdown(f"<small>`text` | `{size}`</small>", unsafe_allow_html=True)
        else:
            st.markdown("<small>`--`</small>", unsafe_allow_html=True)
    
    with col5:
        # Action buttons
        btn_cols = st.columns(2)
        
        with btn_cols[0]:
            # Play button (if audio exists)
            if chapter.audio_path:
                if st.button("[PLAY]", key=f"play_{key}", help="Play audio"):
                    play_chapter(book.name, chapter)
                    st.rerun()
        
        with btn_cols[1]:
            # Read button (if text exists)
            if chapter.text_path:
                if st.button("[READ]", key=f"read_{key}", help="Read text"):
                    st.session_state[f"show_text_{key}"] = True
                    st.rerun()
    
    # Show text content if requested
    if st.session_state.get(f"show_text_{key}", False) and chapter.text_path:
        with st.expander("[PREVIEW] Text Preview", expanded=True):
            try:
                with open(chapter.text_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                # Show first 2000 chars
                preview = content[:2000] + "..." if len(content) > 2000 else content
                st.markdown(f"```markdown\n{preview}\n```")
                
                col_a, col_b = st.columns([1, 5])
                with col_a:
                    if st.button("Close", key=f"close_text_{key}"):
                        st.session_state[f"show_text_{key}"] = False
                        st.rerun()
                with col_b:
                    # Download button
                    with open(chapter.text_path, 'rb') as f:
                        st.download_button(
                            "Download",
                            data=f.read(),
                            file_name=chapter.text_path.name,
                            mime="text/markdown",
                            key=f"dl_text_{key}"
                        )
            except Exception as e:
                st.error(f"Error reading file: {e}")


def render_book_card(book: BookItem):
    """Render a book as a compact card."""
    is_expanded = book.name in st.session_state.checklist_expanded_books
    is_selected = st.session_state.checklist_selected_book == book.name
    
    # Count chapters with audio/text
    audio_count = sum(1 for ch in book.chapters if ch.audio_path)
    text_count = sum(1 for ch in book.chapters if ch.text_path)
    
    # Card container
    card_style = "border: 1px solid #333; padding: 10px; margin-bottom: 10px; border-radius: 4px;"
    if is_selected:
        card_style += " border-color: #FFB000; background-color: rgba(255, 176, 0, 0.05);"
    
    with st.container():
        st.markdown(f"<div style='{card_style}'>", unsafe_allow_html=True)
        
        # Book header row
        header_col1, header_col2, header_col3 = st.columns([4, 2, 1])
        
        with header_col1:
            # Book title (clickable to expand)
            title_style = "color: #FFB000;" if is_selected else ""
            st.markdown(f"<h4 style='margin: 0; {title_style}'>{book.name}</h4>", unsafe_allow_html=True)
            
            # Meta info
            meta_parts = []
            if book.chapters:
                meta_parts.append(f"`{len(book.chapters)} chapters`")
            if audio_count:
                meta_parts.append(f"<span style='color: #00FF00;'>[A] {audio_count} audio</span>")
            if text_count:
                meta_parts.append(f"<span style='color: #00CCFF;'>[T] {text_count} text</span>")
            
            st.markdown(" | ".join(meta_parts), unsafe_allow_html=True)
        
        with header_col2:
            # File info
            if book.m4b_file:
                st.markdown(f"<small>m4b: `{format_file_size(book.m4b_file)}`</small>", unsafe_allow_html=True)
            if book.source_md:
                st.markdown(f"<small>source: [OK]</small>", unsafe_allow_html=True)
        
        with header_col3:
            # Expand/collapse button
            btn_icon = "[-]" if is_expanded else "[+]"
            if st.button(btn_icon, key=f"expand_{book.name}", help="Expand/Collapse"):
                toggle_book_expansion(book.name)
                st.rerun()
        
        # Expanded content - Chapter list
        if is_expanded and book.chapters:
            st.markdown("---")
            
            # Bulk actions
            bulk_col1, bulk_col2, bulk_col3 = st.columns([2, 2, 2])
            with bulk_col1:
                if st.button("[+] Select All", key=f"sel_all_{book.name}", use_container_width=True):
                    for ch in book.chapters:
                        st.session_state.checklist_selected_chapters.add(f"{book.name}:{ch.number}")
                    st.rerun()
            with bulk_col2:
                if st.button("[X] Clear Selection", key=f"clear_sel_{book.name}", use_container_width=True):
                    for ch in book.chapters:
                        st.session_state.checklist_selected_chapters.discard(f"{book.name}:{ch.number}")
                    st.rerun()
            with bulk_col3:
                # Download selected
                selected_in_book = [
                    ch for ch in book.chapters 
                    if f"{book.name}:{ch.number}" in st.session_state.checklist_selected_chapters
                ]
                if selected_in_book:
                    st.markdown(f"<small>`{len(selected_in_book)}` selected</small>", unsafe_allow_html=True)
            
            st.markdown("")
            
            # Chapter list
            for chapter in book.chapters:
                render_chapter_row(book, chapter, is_expanded)
        
        st.markdown("</div>", unsafe_allow_html=True)


def render_audio_player():
    """Render the currently playing audio player."""
    playing = st.session_state.checklist_currently_playing
    
    if not playing:
        return
    
    audio_path = playing.get("path")
    if not audio_path or not Path(audio_path).exists():
        st.warning("Audio file not found")
        return
    
    # Player container
    st.markdown("---")
    st.markdown("### [ now playing ]")
    
    play_col1, play_col2 = st.columns([4, 1])
    
    with play_col1:
        st.markdown(f"**{playing['book']}** - Chapter {playing['chapter']}")
        
        # Read and encode audio
        try:
            with open(audio_path, 'rb') as f:
                audio_bytes = f.read()
                audio_b64 = base64.b64encode(audio_bytes).decode()
                st.markdown(
                    f'<audio controls style="width: 100%;" src="data:audio/mp3;base64,{audio_b64}"></audio>',
                    unsafe_allow_html=True
                )
        except Exception as e:
            st.error(f"Error loading audio: {e}")
    
    with play_col2:
        if st.button("[X] Close Player", key="close_player"):
            st.session_state.checklist_currently_playing = None
            st.rerun()
    
    st.markdown("---")


def render_checklist_header(books: List[BookItem]):
    """Render the checklist header with search and filters."""
    st.markdown("### [ library explorer ]")
    
    # Stats
    total_books = len(books)
    total_chapters = sum(len(b.chapters) for b in books)
    total_audio = sum(
        sum(1 for ch in b.chapters if ch.audio_path) 
        for b in books
    )
    
    stats_col1, stats_col2, stats_col3, stats_col4 = st.columns(4)
    with stats_col1:
        st.markdown(f"books: `{total_books}`")
    with stats_col2:
        st.markdown(f"chapters: `{total_chapters}`")
    with stats_col3:
        st.markdown(f"<span style='color: #00FF00;'>[A] `{total_audio}` audio</span>", unsafe_allow_html=True)
    with stats_col4:
        selected = len(st.session_state.checklist_selected_chapters)
        if selected > 0:
            st.markdown(f"<span style='color: #FFB000;'>[OK] `{selected}` selected</span>", unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Search and filters
    filter_col1, filter_col2, filter_col3 = st.columns([3, 2, 2])
    
    with filter_col1:
        search = st.text_input(
            "search",
            value=st.session_state.checklist_search,
            placeholder="search books...",
            label_visibility="collapsed",
            key="checklist_search_input"
        )
        st.session_state.checklist_search = search
    
    with filter_col2:
        sort = st.selectbox(
            "sort",
            options=["newest", "oldest", "name", "chapters"],
            index=["newest", "oldest", "name", "chapters"].index(st.session_state.checklist_sort),
            label_visibility="collapsed",
            key="checklist_sort_select"
        )
        st.session_state.checklist_sort = sort
    
    with filter_col3:
        # View mode toggle (using selectbox for compatibility)
        view_options = ["list", "compact"]
        # Reset to default if invalid value in session state
        if st.session_state.checklist_view_mode not in view_options:
            st.session_state.checklist_view_mode = "list"
        view = st.selectbox(
            "view",
            options=view_options,
            index=view_options.index(st.session_state.checklist_view_mode),
            label_visibility="collapsed",
            key="checklist_view_mode_select"
        )
        st.session_state.checklist_view_mode = view


def filter_and_sort_books(books: List[BookItem]) -> List[BookItem]:
    """Apply search and sort to books."""
    search = st.session_state.checklist_search.lower()
    sort = st.session_state.checklist_sort
    
    # Filter
    if search:
        books = [
            b for b in books 
            if search in b.name.lower() or
            any(search in ch.title.lower() for ch in b.chapters)
        ]
    
    # Sort
    if sort == "newest":
        books.sort(key=lambda b: b.created_at or datetime.min, reverse=True)
    elif sort == "oldest":
        books.sort(key=lambda b: b.created_at or datetime.min)
    elif sort == "name":
        books.sort(key=lambda b: b.name.lower())
    elif sort == "chapters":
        books.sort(key=lambda b: len(b.chapters), reverse=True)
    
    return books


def render_bulk_actions(books: List[BookItem]):
    """Render bulk actions for selected chapters."""
    selected = st.session_state.checklist_selected_chapters
    
    if not selected:
        return
    
    st.markdown("---")
    st.markdown("### [ bulk actions ]")
    
    action_col1, action_col2, action_col3 = st.columns([2, 2, 4])
    
    with action_col1:
        st.markdown(f"**{len(selected)}** chapters selected")
    
    with action_col2:
        if st.button("[X] Clear All", use_container_width=True):
            st.session_state.checklist_selected_chapters.clear()
            st.rerun()
    
    with action_col3:
        # Find selected chapters for download
        selected_chapters = []
        for book in books:
            for ch in book.chapters:
                key = f"{book.name}:{ch.number}"
                if key in selected and ch.audio_path:
                    selected_chapters.append((book.name, ch))
        
        if selected_chapters:
            st.markdown(f"<small>Ready to download `{len(selected_chapters)}` audio files</small>", unsafe_allow_html=True)


# ============================================
# MAIN RENDER FUNCTION
# ============================================

def render_checklist_view(output_dir: Path = Path("output")):
    """
    Main checklist view component.
    
    Args:
        output_dir: Path to the output directory
    """
    from modules.ui.terminal import render_terminal_view
    
    init_checklist_state()
    
    # Scan directory
    books = scan_output_directory(output_dir)
    
    # Header
    render_checklist_header(books)
    
    # Audio player (if something is playing)
    render_audio_player()
    
    # Filter and sort
    filtered_books = filter_and_sort_books(books)
    
    # Bulk actions
    render_bulk_actions(books)
    
    st.markdown("---")
    
    # Book list
    if not filtered_books:
        if st.session_state.checklist_search:
            st.markdown("_no books match your search_")
        else:
            st.markdown("_no audiobooks in output directory_")
            st.markdown("")
            st.info("Convert some books to see them here!")
    else:
        # Display books
        for book in filtered_books:
            render_book_card(book)
    
    # Terminal section
    st.markdown("---")
    st.markdown("### [ terminal ]")
    render_terminal_view()
    
    # Footer
    st.markdown("---")
    st.markdown(
        "<div style='text-align: center; color: #555555; font-size: 10px;'>"
        "audiobook_creator v1.0 | optimized for apple silicon | 2026"
        "</div>",
        unsafe_allow_html=True,
    )
