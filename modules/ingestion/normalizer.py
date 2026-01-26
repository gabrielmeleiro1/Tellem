"""
Markdown Normalizer
===================
Normalizes parsed content into consistent format for TTS processing.
Handles whitespace, special characters, and chapter splitting.
"""

import re
from dataclasses import dataclass


@dataclass
class NormalizedChapter:
    """A chapter with normalized text content."""
    number: int
    title: str
    content: str
    word_count: int


class MarkdownNormalizer:
    """
    Normalizes text content for optimal TTS processing.
    
    Operations:
        - Remove markdown formatting
        - Normalize whitespace
        - Handle special characters
        - Split into chapters
    """
    
    def __init__(self):
        """Initialize the normalizer with default settings."""
        # Characters to remove or replace
        self._replacements = {
            "—": ", ",      # em dash
            "–": ", ",      # en dash
            "…": "...",     # ellipsis
            """: '"',       # smart quotes
            """: '"',
            "'": "'",
            "'": "'",
            "•": ", ",      # bullets
            "→": " to ",
            "←": " from ",
            "©": "copyright ",
            "®": " registered ",
            "™": " trademark ",
            "°": " degrees ",
            "±": " plus or minus ",
            "×": " times ",
            "÷": " divided by ",
        }
        
        # Patterns to remove
        self._remove_patterns = [
            r'\[.*?\]\(.*?\)',          # markdown links
            r'!\[.*?\]\(.*?\)',         # markdown images
            r'^#{1,6}\s+',              # markdown headers (keep text)
            r'\*\*([^*]+)\*\*',         # bold (keep text)
            r'\*([^*]+)\*',             # italic (keep text)
            r'`([^`]+)`',               # inline code (keep text)
            r'```[\s\S]*?```',          # code blocks
            r'^[-*+]\s+',               # list markers
            r'^\d+\.\s+',               # numbered list markers
            r'^>\s+',                   # blockquotes
            r'\|.*\|',                  # table rows
        ]
    
    def normalize(self, text: str) -> str:
        """
        Normalize text for TTS processing.
        
        Args:
            text: Raw text content
            
        Returns:
            Cleaned, normalized text
        """
        if not text:
            return ""
        
        result = text
        
        # Apply character replacements
        for old, new in self._replacements.items():
            result = result.replace(old, new)
        
        # Remove markdown formatting but keep content
        for pattern in self._remove_patterns:
            if '(' in pattern and ')' in pattern:
                # Pattern has capture group - use substitution
                result = re.sub(pattern, r'\1', result, flags=re.MULTILINE)
            else:
                result = re.sub(pattern, '', result, flags=re.MULTILINE)
        
        # Normalize whitespace
        result = self._normalize_whitespace(result)
        
        # Clean up punctuation
        result = self._clean_punctuation(result)
        
        return result.strip()
    
    def _normalize_whitespace(self, text: str) -> str:
        """Normalize whitespace in text."""
        # Replace multiple spaces with single space
        text = re.sub(r' +', ' ', text)
        # Replace multiple newlines with double newline (paragraph break)
        text = re.sub(r'\n{3,}', '\n\n', text)
        # Remove trailing whitespace from lines
        text = '\n'.join(line.rstrip() for line in text.split('\n'))
        return text
    
    def _clean_punctuation(self, text: str) -> str:
        """Clean up punctuation for TTS."""
        # Add space after punctuation if missing
        text = re.sub(r'([.!?])([A-Z])', r'\1 \2', text)
        # Remove duplicate punctuation
        text = re.sub(r'([.!?]){2,}', r'\1', text)
        # Add pause after colons in dialogue
        text = re.sub(r':(["\'])', r': \1', text)
        return text
    
    def split_chapters(self, text: str, markers: list[str] = None) -> list[str]:
        """
        Split text into chapters based on markers.
        
        Args:
            text: Full document text
            markers: Optional list of chapter markers (regex patterns)
            
        Returns:
            List of chapter content strings
        """
        if markers is None:
            markers = [
                r'^Chapter\s+\d+',
                r'^CHAPTER\s+\d+',
                r'^Part\s+\d+',
                r'^PART\s+\d+',
                r'^Section\s+\d+',
                r'^\d+\.\s+[A-Z]',  # "1. Title"
            ]
        
        # Combine markers into one pattern
        pattern = '|'.join(f'({m})' for m in markers)
        
        # Split on markers
        parts = re.split(f'({pattern})', text, flags=re.MULTILINE | re.IGNORECASE)
        
        # Recombine marker with content
        chapters = []
        current = ""
        
        for part in parts:
            if part is None:
                continue
            if any(re.match(m, part, re.IGNORECASE) for m in markers):
                if current.strip():
                    chapters.append(current.strip())
                current = part
            else:
                current += part
        
        if current.strip():
            chapters.append(current.strip())
        
        # If no chapters found, return whole text as one chapter
        if not chapters:
            chapters = [text.strip()]
        
        return chapters
    
    def process_document(self, text: str) -> list[NormalizedChapter]:
        """
        Process a full document into normalized chapters.
        
        Args:
            text: Raw document text
            
        Returns:
            List of NormalizedChapter objects
        """
        # Split into chapters
        chapter_texts = self.split_chapters(text)
        
        chapters = []
        for i, content in enumerate(chapter_texts, 1):
            # Extract title from first line
            lines = content.split('\n', 1)
            title = lines[0].strip() if lines else f"Chapter {i}"
            body = lines[1] if len(lines) > 1 else content
            
            # Normalize the content
            normalized = self.normalize(body)
            
            chapters.append(NormalizedChapter(
                number=i,
                title=title,
                content=normalized,
                word_count=len(normalized.split())
            ))
        
        return chapters
