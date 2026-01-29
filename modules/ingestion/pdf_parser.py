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

from modules.errors import (
    validate_pdf,
    PDFParsingError,
    CorruptedFileError,
    EmptyChapterError,
    ChapterTooLongError,
)


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
    
    # Maximum words per chapter before warning
    MAX_CHAPTER_WORDS = 50000
    
    def __init__(self, file_path: Path | str, validate: bool = True):
        """
        Initialize the parser with a PDF file.
        
        Args:
            file_path: Path to the PDF file
            validate: Whether to validate the PDF structure
        """
        self.file_path = Path(file_path)
        if not self.file_path.exists():
            raise FileNotFoundError(f"PDF not found: {self.file_path}")
        if self.file_path.suffix.lower() != ".pdf":
            raise ValueError(f"Not a PDF file: {self.file_path}")
        
        # Validate PDF structure
        if validate:
            try:
                validate_pdf(self.file_path)
            except CorruptedFileError as e:
                raise PDFParsingError(
                    message=str(e.message),
                    details=e.details,
                    file_path=self.file_path
                )
        
        self._doc = None
        self._toc = None
        self._markdown = None
    
    def parse(self, skip_empty: bool = True, max_chapter_words: int = None) -> Document:
        """
        Parse the PDF into a Document object.
        
        Args:
            skip_empty: If True, silently skip empty chapters. If False, raise EmptyChapterError.
            max_chapter_words: Maximum words per chapter (raises ChapterTooLongError if exceeded).
                              Defaults to MAX_CHAPTER_WORDS class attribute.
        
        Returns:
            Document with extracted content and chapters
        
        Raises:
            PDFParsingError: If PDF cannot be parsed
            CorruptedFileError: If PDF structure is invalid
            EmptyChapterError: If chapter is empty and skip_empty=False
            ChapterTooLongError: If chapter exceeds max_chapter_words
        """
        import fitz
        
        max_words = max_chapter_words or self.MAX_CHAPTER_WORDS
        
        try:
            # Extract markdown with page chunks for mapping to chapters
            pages_data = pymupdf4llm.to_markdown(str(self.file_path), page_chunks=True)
        except Exception as e:
            raise PDFParsingError(
                message=f"Failed to extract markdown: {str(e)}",
                file_path=self.file_path
            )
        
        # Handle empty document
        if not pages_data:
            raise CorruptedFileError(
                message="PDF contains no extractable text",
                file_path=self.file_path
            )
        
        # Combine full markdown for the document record
        self._markdown = "\n\n".join(p["text"] for p in pages_data)
        
        # Get metadata
        try:
            with fitz.open(self.file_path) as doc:
                total_pages = len(doc)
                metadata = doc.metadata
                title = metadata.get("title", "") or self.file_path.stem
                author = metadata.get("author", "")
        except Exception as e:
            raise PDFParsingError(
                message=f"Failed to read PDF metadata: {str(e)}",
                file_path=self.file_path
            )
        
        # Extract chapters structure from TOC
        chapters = self._extract_chapters(total_pages)
        
        # Populate content for each chapter based on page ranges
        valid_chapters = []
        for chapter in chapters:
            # Handle potential bounds errors
            start_idx = max(0, chapter.start_page - 1)
            end_idx = min(len(pages_data), chapter.end_page)
            
            # Join text for pages in this chapter
            chapter_pages = pages_data[start_idx:end_idx]
            chapter.content = "\n\n".join(p["text"] for p in chapter_pages)
            
            # Check for empty chapter
            content_stripped = chapter.content.strip()
            if not content_stripped:
                if skip_empty:
                    continue  # Skip this chapter
                else:
                    raise EmptyChapterError(chapter.number, chapter.title)
            
            # Check for extremely long chapter
            word_count = len(content_stripped.split())
            if word_count > max_words:
                raise ChapterTooLongError(chapter.number, word_count, max_words)
            
            valid_chapters.append(chapter)
        
        # Renumber chapters after filtering
        for i, chapter in enumerate(valid_chapters):
            chapter.number = i + 1
        
        return Document(
            title=title,
            author=author if author else None,
            chapters=valid_chapters,
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
    
    def _extract_chapters(self, total_pages: int) -> list[Chapter]:
        """
        Extract chapters based on TOC or heading detection.
        
        Args:
            total_pages: Total page count to calculate end pages
            
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
                content="", # Populated in parse()
                start_page=1,
                end_page=total_pages
            ))
            return chapters
        
        # Process TOC entries (level 1 only for main chapters)
        level_1_entries = [(t, p) for lvl, t, p in toc if lvl == 1]
        
        # If no level 1 entries found, try level 2 or just use all
        if not level_1_entries and toc:
             level_1_entries = [(t, p) for lvl, t, p in toc]
        
        for i, (title, start_page) in enumerate(level_1_entries):
            # Determine end page
            if i + 1 < len(level_1_entries):
                end_page = level_1_entries[i + 1][1] - 1
            else:
                end_page = total_pages
            
            # Validate page numbers
            if start_page > end_page:
                start_page = end_page
            
            chapters.append(Chapter(
                number=i + 1,
                title=title,
                content="",  # Populated in parse()
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
