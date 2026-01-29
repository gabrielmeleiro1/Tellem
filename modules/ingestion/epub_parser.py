"""
EPUB Parser Module
==================
Extracts content from EPUB files using EbookLib + BeautifulSoup4.
Optimized for clean text extraction suitable for TTS.
"""

from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup

from modules.errors import (
    validate_epub,
    EPUBParsingError,
    CorruptedFileError,
    EmptyChapterError,
    ChapterTooLongError,
)


@dataclass
class Chapter:
    """Represents a chapter from an EPUB."""
    number: int
    title: str
    content: str
    html_content: str = ""


@dataclass
class Document:
    """Represents a parsed EPUB document."""
    title: str
    author: Optional[str]
    chapters: list[Chapter] = field(default_factory=list)
    language: Optional[str] = None
    publisher: Optional[str] = None


class EPUBParser:
    """
    Parses EPUB files into structured content.
    
    Uses EbookLib for EPUB extraction and BeautifulSoup4 for HTML parsing.
    """
    
    # Maximum words per chapter before warning
    MAX_CHAPTER_WORDS = 50000
    
    def __init__(self, file_path: Path | str, validate: bool = True):
        """
        Initialize the parser with an EPUB file.
        
        Args:
            file_path: Path to the EPUB file
            validate: Whether to validate the EPUB structure
        """
        self.file_path = Path(file_path)
        if not self.file_path.exists():
            raise FileNotFoundError(f"EPUB not found: {self.file_path}")
        if self.file_path.suffix.lower() != ".epub":
            raise ValueError(f"Not an EPUB file: {self.file_path}")
        
        # Validate EPUB structure
        if validate:
            try:
                validate_epub(self.file_path)
            except (CorruptedFileError, EPUBParsingError) as e:
                raise EPUBParsingError(
                    message=str(e.message),
                    details=e.details if hasattr(e, 'details') else None,
                    file_path=self.file_path
                )
        
        self._book: Optional[epub.EpubBook] = None
        self._chapters: list[Chapter] = []
    
    def _load_book(self) -> epub.EpubBook:
        """Load the EPUB book if not already loaded."""
        if self._book is None:
            try:
                self._book = epub.read_epub(str(self.file_path))
            except Exception as e:
                raise EPUBParsingError(
                    message=f"Failed to read EPUB: {str(e)}",
                    file_path=self.file_path
                )
        return self._book
    
    def parse(self) -> Document:
        """
        Parse the EPUB into a Document object.
        
        Returns:
            Document with extracted content and chapters
        """
        book = self._load_book()
        metadata = self.get_metadata()
        chapters = self.extract_chapters()
        
        return Document(
            title=metadata.get("title", self.file_path.stem),
            author=metadata.get("author"),
            chapters=chapters,
            language=metadata.get("language"),
            publisher=metadata.get("publisher")
        )
    
    def extract_chapters(self, skip_empty: bool = True, max_chapter_words: int = None) -> list[Chapter]:
        """
        Extract all chapters from the EPUB.
        
        Args:
            skip_empty: If True, silently skip empty chapters. If False, raise EmptyChapterError.
            max_chapter_words: Maximum words per chapter (raises ChapterTooLongError if exceeded).
        
        Returns:
            List of Chapter objects with cleaned text content
            
        Raises:
            EmptyChapterError: If chapter is empty and skip_empty=False
            ChapterTooLongError: If chapter exceeds max_chapter_words
        """
        if self._chapters:
            return self._chapters
        
        max_words = max_chapter_words or self.MAX_CHAPTER_WORDS
        
        book = self._load_book()
        chapters = []
        chapter_num = 0
        
        # Iterate through spine (reading order)
        for item in book.get_items():
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                try:
                    html_content = item.get_content().decode("utf-8")
                except UnicodeDecodeError:
                    # Try with latin-1 fallback
                    html_content = item.get_content().decode("latin-1")
                
                text_content = self._html_to_text(html_content)
                content_stripped = text_content.strip()
                
                # Skip empty or very short content
                if len(content_stripped) < 50:
                    if not skip_empty and len(content_stripped) == 0:
                        raise EmptyChapterError(chapter_num + 1)
                    continue
                
                chapter_num += 1
                title = self._extract_title(html_content) or f"Chapter {chapter_num}"
                
                # Check for extremely long chapter
                word_count = len(content_stripped.split())
                if word_count > max_words:
                    raise ChapterTooLongError(chapter_num, word_count, max_words)
                
                chapters.append(Chapter(
                    number=chapter_num,
                    title=title,
                    content=text_content,
                    html_content=html_content
                ))
        
        # Check if we got any chapters
        if not chapters:
            raise EPUBParsingError(
                message="No readable chapters found in EPUB",
                file_path=self.file_path
            )
        
        self._chapters = chapters
        return chapters
    
    def get_metadata(self) -> dict[str, str]:
        """
        Extract metadata from the EPUB.
        
        Returns:
            Dictionary with title, author, language, publisher
        """
        book = self._load_book()
        metadata = {}
        
        # Title
        title = book.get_metadata("DC", "title")
        if title:
            metadata["title"] = title[0][0]
        
        # Author
        creator = book.get_metadata("DC", "creator")
        if creator:
            metadata["author"] = creator[0][0]
        
        # Language
        language = book.get_metadata("DC", "language")
        if language:
            metadata["language"] = language[0][0]
        
        # Publisher
        publisher = book.get_metadata("DC", "publisher")
        if publisher:
            metadata["publisher"] = publisher[0][0]
        
        return metadata
    
    def _html_to_text(self, html_content: str) -> str:
        """
        Convert HTML content to clean text.
        
        Args:
            html_content: Raw HTML string
            
        Returns:
            Cleaned text content
        """
        soup = BeautifulSoup(html_content, "lxml")
        
        # Remove script and style elements
        for element in soup(["script", "style", "nav", "header", "footer"]):
            element.decompose()
        
        # Get text with proper spacing
        text = soup.get_text(separator="\n", strip=True)
        
        # Clean up excessive whitespace
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        return "\n\n".join(lines)
    
    def _extract_title(self, html_content: str) -> Optional[str]:
        """
        Extract chapter title from HTML.
        
        Args:
            html_content: Raw HTML string
            
        Returns:
            Title string or None
        """
        soup = BeautifulSoup(html_content, "lxml")
        
        # Try h1, h2, h3 in order
        for tag in ["h1", "h2", "h3"]:
            heading = soup.find(tag)
            if heading:
                return heading.get_text(strip=True)
        
        # Try title tag
        title = soup.find("title")
        if title:
            return title.get_text(strip=True)
        
        return None
    
    def get_cover(self) -> Optional[bytes]:
        """
        Extract cover image from EPUB if available.
        
        Returns:
            Cover image bytes or None
        """
        book = self._load_book()
        
        for item in book.get_items():
            if item.get_type() == ebooklib.ITEM_COVER:
                return item.get_content()
        
        # Try to find by name
        for item in book.get_items_of_type(ebooklib.ITEM_IMAGE):
            if "cover" in item.get_name().lower():
                return item.get_content()
        
        return None
