"""
Ingestion Module
================
Handles PDF and EPUB parsing, converting documents to structured Markdown.
"""

from .pdf_parser import PDFParser
from .epub_parser import EPUBParser
from .normalizer import MarkdownNormalizer

__all__ = ["PDFParser", "EPUBParser", "MarkdownNormalizer"]
