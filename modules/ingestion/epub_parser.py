"""
EPUB Parser Module
==================
Extracts content from EPUB files using EbookLib + BeautifulSoup4.
Placeholder - full implementation in task 1.5.
"""

from pathlib import Path
from dataclasses import dataclass
from typing import Optional


@dataclass
class Chapter:
    """Represents a chapter from an EPUB."""
    number: int
    title: str
    content: str


@dataclass
class Document:
    """Represents a parsed EPUB document."""
    title: str
    author: Optional[str]
    chapters: list[Chapter]


class EPUBParser:
    """Placeholder for EPUB parser - implemented in task 1.5."""
    
    def __init__(self, file_path: Path | str):
        self.file_path = Path(file_path)
    
    def parse(self) -> Document:
        raise NotImplementedError("EPUB parsing - see task 1.5")
    
    def extract_chapters(self) -> list[Chapter]:
        raise NotImplementedError("EPUB parsing - see task 1.5")
    
    def get_metadata(self) -> dict[str, str]:
        raise NotImplementedError("EPUB parsing - see task 1.5")
