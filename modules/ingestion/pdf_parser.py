"""
PDF Parser Module
=================
Converts PDF files to structured Markdown using PyMuPDF4LLM.
Optimized for Apple Silicon.
"""

from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
import pymupdf4llm


@dataclass
class Chapter:
    """Represents a chapter extracted from a PDF."""
    number: int
    title: str
    content: str
    start_page: int
    end_page: int


@dataclass 
class Document:
    """Represents a parsed PDF document."""
    title: str
    author: Optional[str]
    chapters: list[Chapter] = field(default_factory=list)
    total_pages: int = 0
    raw_markdown: str = ""


class PDFParser:
    """
    Parses PDF files into structured Markdown format.
    
    Uses PyMuPDF4LLM for fast, accurate extraction optimized for LLMs.
    """
    
    def __init__(self, file_path: Path | str):
        """
        Initialize the parser with a PDF file.
        
        Args:
            file_path: Path to the PDF file
        """
        self.file_path = Path(file_path)
        if not self.file_path.exists():
            raise FileNotFoundError(f"PDF not found: {self.file_path}")
        if self.file_path.suffix.lower() != ".pdf":
            raise ValueError(f"Not a PDF file: {self.file_path}")
        
        self._doc = None
        self._toc = None
        self._markdown = None
    
    def parse(self) -> Document:
        """
        Parse the PDF into a Document object.
        
        Returns:
            Document with extracted content and chapters
        """
        # Extract markdown using pymupdf4llm
        self._markdown = pymupdf4llm.to_markdown(str(self.file_path))
        
        # Get page count
        import fitz
        with fitz.open(self.file_path) as doc:
            total_pages = len(doc)
            # Try to get metadata
            metadata = doc.metadata
            title = metadata.get("title", "") or self.file_path.stem
            author = metadata.get("author", "")
        
        # Extract chapters from TOC
        chapters = self._extract_chapters()
        
        return Document(
            title=title,
            author=author if author else None,
            chapters=chapters,
            total_pages=total_pages,
            raw_markdown=self._markdown
        )
    
    def extract_toc(self) -> list[tuple[int, str, int]]:
        """
        Extract the Table of Contents from the PDF.
        
        Returns:
            List of (level, title, page_number) tuples
        """
        import fitz
        with fitz.open(self.file_path) as doc:
            self._toc = doc.get_toc()
        return self._toc or []
    
    def _extract_chapters(self) -> list[Chapter]:
        """
        Extract chapters based on TOC or heading detection.
        
        Returns:
            List of Chapter objects
        """
        toc = self.extract_toc()
        chapters = []
        
        if not toc:
            # No TOC - treat entire document as one chapter
            chapters.append(Chapter(
                number=1,
                title="Full Document",
                content=self._markdown or "",
                start_page=1,
                end_page=self.get_page_count()
            ))
            return chapters
        
        # Process TOC entries (level 1 only for main chapters)
        level_1_entries = [(t, p) for lvl, t, p in toc if lvl == 1]
        
        for i, (title, start_page) in enumerate(level_1_entries):
            # Determine end page
            if i + 1 < len(level_1_entries):
                end_page = level_1_entries[i + 1][1] - 1
            else:
                end_page = self.get_page_count()
            
            chapters.append(Chapter(
                number=i + 1,
                title=title,
                content="",  # Content extracted later during processing
                start_page=start_page,
                end_page=end_page
            ))
        
        return chapters
    
    def get_page_count(self) -> int:
        """Get the total number of pages in the PDF."""
        import fitz
        with fitz.open(self.file_path) as doc:
            return len(doc)
    
    def get_markdown(self) -> str:
        """
        Get the full markdown content.
        
        Returns:
            Markdown string of entire document
        """
        if self._markdown is None:
            self._markdown = pymupdf4llm.to_markdown(str(self.file_path))
        return self._markdown
