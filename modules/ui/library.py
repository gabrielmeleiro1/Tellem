"""
Library View Component
======================
Display and manage past audiobook conversions.
"""

import streamlit as st
from datetime import datetime
from typing import Optional
from pathlib import Path

from modules.storage.database import Database, Book


def format_duration(duration_ms: Optional[int]) -> str:
    """Format milliseconds as HH:MM:SS."""
    if duration_ms is None:
        return "--:--:--"
    
    total_seconds = duration_ms // 1000
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def format_date(dt: Optional[datetime]) -> str:
    """Format datetime for display."""
    if dt is None:
        return "--"
    return dt.strftime("%Y-%m-%d %H:%M")


def init_library_state():
    """Initialize library state in session."""
    if "library_search" not in st.session_state:
        st.session_state.library_search = ""
    if "library_selected_book" not in st.session_state:
        st.session_state.library_selected_book = None
    if "library_sort" not in st.session_state:
        st.session_state.library_sort = "newest"


def get_all_books(db: Database, search: str = "", sort: str = "newest") -> list[Book]:
    """
    Get all books from database with optional filtering.
    
    Args:
        db: Database instance
        search: Search query (filters by title/author)
        sort: Sort order - 'newest', 'oldest', 'title', 'author'
    
    Returns:
        List of Book objects
    """
    # Query all books
    with db._connection() as conn:
        cursor = conn.execute("""
            SELECT id, title, author, source_path, source_type, 
                   total_chapters, created_at, updated_at
            FROM books
            ORDER BY created_at DESC
        """)
        rows = cursor.fetchall()
    
    books = []
    for row in rows:
        book = Book(
            id=row[0],
            title=row[1],
            author=row[2],
            source_path=row[3],
            source_type=row[4],
            total_chapters=row[5],
            created_at=datetime.fromisoformat(row[6]) if row[6] else datetime.now(),
            updated_at=datetime.fromisoformat(row[7]) if row[7] else datetime.now(),
        )
        books.append(book)
    
    # Apply search filter
    if search:
        search_lower = search.lower()
        books = [
            b for b in books
            if search_lower in b.title.lower() or 
               (b.author and search_lower in b.author.lower())
        ]
    
    # Apply sorting
    if sort == "oldest":
        books.sort(key=lambda b: b.created_at)
    elif sort == "title":
        books.sort(key=lambda b: b.title.lower())
    elif sort == "author":
        books.sort(key=lambda b: (b.author or "").lower())
    # Default: newest (already sorted by query)
    
    return books


def get_book_duration(db: Database, book_id: int) -> int:
    """Get total duration of a book in milliseconds."""
    chapters = db.get_chapters(book_id)
    total = sum(ch.duration_ms or 0 for ch in chapters)
    return total


def delete_book(db: Database, book_id: int) -> bool:
    """
    Delete a book and its associated files.
    
    Returns:
        True if successful
    """
    book = db.get_book(book_id)
    if not book:
        return False
    
    # Delete chapters first (cascade would handle this but let's be explicit)
    chapters = db.get_chapters(book_id)
    for ch in chapters:
        if ch.mp3_path:
            mp3_file = Path(ch.mp3_path)
            if mp3_file.exists():
                mp3_file.unlink()
    
    # Delete from database
    with db._connection() as conn:
        conn.execute("DELETE FROM chapters WHERE book_id = ?", (book_id,))
        conn.execute("DELETE FROM processing_jobs WHERE book_id = ?", (book_id,))
        conn.execute("DELETE FROM books WHERE id = ?", (book_id,))
        conn.commit()
    
    return True


def render_book_card(book: Book, duration_str: str):
    """Render a single book card in the library."""
    with st.container():
        col1, col2, col3 = st.columns([3, 2, 1])
        
        with col1:
            st.markdown(f"**{book.title}**")
            author = book.author or "_unknown author_"
            st.markdown(f"`{author}`")
        
        with col2:
            st.markdown(f"chapters: `{book.total_chapters}`")
            st.markdown(f"duration: `{duration_str}`")
        
        with col3:
            st.markdown(f"`{format_date(book.created_at)}`")
        
        st.markdown("---")


def render_library_list(db: Database):
    """Render the library book list."""
    init_library_state()
    
    # Search and filter controls
    col1, col2 = st.columns([3, 1])
    with col1:
        search = st.text_input(
            "search",
            value=st.session_state.library_search,
            placeholder="search by title or author...",
            label_visibility="collapsed",
            key="library_search_input"
        )
        st.session_state.library_search = search
    
    with col2:
        sort = st.selectbox(
            "sort",
            options=["newest", "oldest", "title", "author"],
            index=["newest", "oldest", "title", "author"].index(st.session_state.library_sort),
            label_visibility="collapsed",
            key="library_sort_select"
        )
        st.session_state.library_sort = sort
    
    st.markdown("")
    
    # Get and display books
    books = get_all_books(db, search, sort)
    
    if not books:
        if search:
            st.markdown("_no books match your search_")
        else:
            st.markdown("_no audiobooks in library_")
        return
    
    st.markdown(f"**{len(books)}** audiobooks")
    st.markdown("")
    
    # List books
    for book in books:
        duration = get_book_duration(db, book.id)
        duration_str = format_duration(duration)
        
        with st.container():
            # Book row
            row_col1, row_col2, row_col3, row_col4 = st.columns([3, 2, 2, 1])
            
            with row_col1:
                st.markdown(f"**{book.title}**")
                author = book.author or "_unknown_"
                st.markdown(f"by `{author}`")
            
            with row_col2:
                st.markdown(f"`{book.total_chapters}` chapters")
                st.markdown(f"`{duration_str}`")
            
            with row_col3:
                st.markdown(f"`{format_date(book.created_at)}`")
            
            with row_col4:
                # Action buttons
                if st.button("▶", key=f"play_{book.id}", help="Play"):
                    st.session_state.library_selected_book = book.id
                    st.session_state.view = "play"
                    st.rerun()
        
        st.markdown("---")


def render_library_detail(db: Database, book_id: int):
    """Render detailed view of a single book."""
    book = db.get_book(book_id)
    if not book:
        st.markdown("_book not found_")
        return
    
    # Back button
    if st.button("← back to library"):
        st.session_state.library_selected_book = None
        st.rerun()
    
    st.markdown("")
    st.markdown(f"## {book.title}")
    if book.author:
        st.markdown(f"by **{book.author}**")
    
    st.markdown("---")
    
    # Book info
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"source: `{book.source_type}`")
        st.markdown(f"chapters: `{book.total_chapters}`")
    with col2:
        duration = get_book_duration(db, book.id)
        st.markdown(f"duration: `{format_duration(duration)}`")
        st.markdown(f"created: `{format_date(book.created_at)}`")
    
    st.markdown("---")
    
    # Chapter list
    st.markdown("### chapters")
    chapters = db.get_chapters(book.id)
    
    for ch in chapters:
        ch_duration = format_duration(ch.duration_ms)
        has_audio = "●" if ch.mp3_path else "○"
        st.markdown(
            f'<span style="color: #00FF00;">{has_audio}</span> '
            f"`{ch.chapter_number:02d}` {ch.title} — `{ch_duration}`",
            unsafe_allow_html=True
        )
    
    st.markdown("---")
    
    # Actions
    btn_col1, btn_col2, btn_col3 = st.columns(3)
    with btn_col1:
        if st.button("▶ play", use_container_width=True):
            st.session_state.library_selected_book = book_id
            st.session_state.view = "play"
            st.rerun()
    with btn_col2:
        if st.button("↓ export", use_container_width=True):
            st.session_state.export_book_id = book_id
            st.rerun()
    with btn_col3:
        if st.button("✖ delete", use_container_width=True):
            if delete_book(db, book_id):
                st.session_state.library_selected_book = None
                st.rerun()


def render_library_view(db: Optional[Database] = None):
    """
    Main library view component.
    
    Args:
        db: Database instance (creates one if not provided)
    """
    if db is None:
        db = Database()
    
    init_library_state()
    
    st.markdown("### [ library ]")
    
    # Show detail or list view
    if st.session_state.library_selected_book:
        render_library_detail(db, st.session_state.library_selected_book)
    else:
        render_library_list(db)
