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
    
    def __init__(self, file_path: Path | str):
        """
        Initialize the parser with an EPUB file.
        
        Args:
            file_path: Path to the EPUB file
        """
        self.file_path = Path(file_path)
        if not self.file_path.exists():
            raise FileNotFoundError(f"EPUB not found: {self.file_path}")
        if self.file_path.suffix.lower() != ".epub":
            raise ValueError(f"Not an EPUB file: {self.file_path}")
        
        self._book: Optional[epub.EpubBook] = None
        self._chapters: list[Chapter] = []
    
    def _load_book(self) -> epub.EpubBook:
        """Load the EPUB book if not already loaded."""
        if self._book is None:
            self._book = epub.read_epub(str(self.file_path))
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
    
    def extract_chapters(self) -> list[Chapter]:
        """
        Extract all chapters from the EPUB.
        
        Returns:
            List of Chapter objects with cleaned text content
        """
        if self._chapters:
            return self._chapters
        
        book = self._load_book()
        chapters = []
        chapter_num = 0
        
        # Iterate through spine (reading order)
        for item in book.get_items():
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                html_content = item.get_content().decode("utf-8")
                text_content = self._html_to_text(html_content)
                
                # Skip empty or very short content
                if len(text_content.strip()) < 50:
                    continue
                
                chapter_num += 1
                title = self._extract_title(html_content) or f"Chapter {chapter_num}"
                
                chapters.append(Chapter(
                    number=chapter_num,
                    title=title,
                    content=text_content,
                    html_content=html_content
                ))
        
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
