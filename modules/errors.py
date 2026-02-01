"""
Error Handling Module
=====================
Custom exceptions and error handling utilities for the Audiobook Creator.
Provides consistent error codes and messages for edge cases.
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional
from pathlib import Path


class ErrorCode(Enum):
    """Error codes for the audiobook creator."""
    # Ingestion errors (E001-E099)
    E001 = "PDF parsing failed"
    E002 = "EPUB structure invalid"
    E003 = "File corrupted"
    E004 = "Empty chapter detected"
    E005 = "Chapter too long"
    E006 = "Unsupported file format"
    
    # TTS errors (E100-E199)
    E100 = "TTS model load failed"
    E101 = "Speech synthesis failed"
    E102 = "Text cleaning failed"
    
    # Audio errors (E200-E299)
    E200 = "Audio concatenation failed"
    E201 = "Audio encoding failed"
    E202 = "M4B packaging failed"
    E203 = "FFmpeg not found"
    
    # System errors (E300-E399)
    E300 = "VRAM overflow"
    E301 = "Disk full"
    E302 = "Model download failed"
    E303 = "Filename contains invalid characters"
    
    # Pipeline errors (E400-E499)
    E400 = "Pipeline cancelled"
    E401 = "Pipeline timeout"


@dataclass
class AudiobookError(Exception):
    """Base exception for the Audiobook Creator with error codes."""
    code: ErrorCode
    message: str
    details: Optional[str] = None
    file_path: Optional[Path] = None
    
    def __str__(self) -> str:
        base = f"[{self.code.name}] {self.code.value}: {self.message}"
        if self.details:
            base += f" ({self.details})"
        if self.file_path:
            base += f" - File: {self.file_path}"
        return base


class PDFParsingError(AudiobookError):
    """Error during PDF parsing."""
    def __init__(self, message: str, details: str = None, file_path: Path = None):
        super().__init__(
            code=ErrorCode.E001,
            message=message,
            details=details,
            file_path=file_path
        )


class EPUBParsingError(AudiobookError):
    """Error during EPUB parsing."""
    def __init__(self, message: str, details: str = None, file_path: Path = None):
        super().__init__(
            code=ErrorCode.E002,
            message=message,
            details=details,
            file_path=file_path
        )


class CorruptedFileError(AudiobookError):
    """Error when file is corrupted."""
    def __init__(self, message: str, file_path: Path = None):
        super().__init__(
            code=ErrorCode.E003,
            message=message,
            file_path=file_path
        )


class EmptyChapterError(AudiobookError):
    """Error when chapter has no content."""
    def __init__(self, chapter_number: int, chapter_title: str = None):
        super().__init__(
            code=ErrorCode.E004,
            message=f"Chapter {chapter_number} is empty",
            details=chapter_title
        )


class ChapterTooLongError(AudiobookError):
    """Error when chapter exceeds maximum word count."""
    def __init__(self, chapter_number: int, word_count: int, max_words: int = 50000):
        super().__init__(
            code=ErrorCode.E005,
            message=f"Chapter {chapter_number} has {word_count:,} words",
            details=f"Maximum allowed: {max_words:,} words"
        )


class TTSModelError(AudiobookError):
    """Error loading TTS model."""
    def __init__(self, message: str, model_name: str = None):
        super().__init__(
            code=ErrorCode.E100,
            message=message,
            details=model_name
        )


class SynthesisError(AudiobookError):
    """Error during speech synthesis."""
    def __init__(self, message: str, chunk_index: int = None):
        super().__init__(
            code=ErrorCode.E101,
            message=message,
            details=f"Chunk {chunk_index}" if chunk_index else None
        )


class FFmpegNotFoundError(AudiobookError):
    """Error when FFmpeg is not installed."""
    
    INSTALL_INSTRUCTIONS = """FFmpeg is required but not found in PATH.

Installation instructions:
  macOS:    brew install ffmpeg
  Ubuntu:   sudo apt update && sudo apt install ffmpeg
  Windows:  winget install Gyan.FFmpeg
            or download from: https://ffmpeg.org/download.html

After installation, ensure 'ffmpeg' is available in your system PATH."""
    
    def __init__(self):
        super().__init__(
            code=ErrorCode.E203,
            message="FFmpeg is required but not found",
            details=self.INSTALL_INSTRUCTIONS
        )


class M4BPackagingError(AudiobookError):
    """Error during M4B packaging."""
    def __init__(self, message: str, details: str = None):
        super().__init__(
            code=ErrorCode.E202,
            message=message,
            details=details
        )


class DiskFullError(AudiobookError):
    """Error when disk is full."""
    def __init__(self, required_bytes: int = None):
        details = None
        if required_bytes:
            gb = required_bytes / (1024 ** 3)
            details = f"Required: {gb:.2f} GB"
        super().__init__(
            code=ErrorCode.E301,
            message="Insufficient disk space",
            details=details
        )


class VRAMOverflowError(AudiobookError):
    """Error when VRAM is exhausted."""
    def __init__(self, model_name: str = None):
        super().__init__(
            code=ErrorCode.E300,
            message="VRAM overflow - model too large for available memory",
            details=model_name
        )


class InvalidFilenameError(AudiobookError):
    """Error when filename contains invalid characters."""
    def __init__(self, filename: str, invalid_chars: str = None):
        super().__init__(
            code=ErrorCode.E303,
            message=f"Filename contains invalid characters: {filename}",
            details=f"Invalid characters: {invalid_chars}" if invalid_chars else None
        )


# ===========================================
# Utility Functions
# ===========================================

def validate_pdf(file_path: Path) -> bool:
    """
    Validate that a file is a valid PDF.
    
    Args:
        file_path: Path to the PDF file
        
    Returns:
        True if valid, raises exception otherwise
    """
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    # Check file size (minimum valid PDF is ~25 bytes)
    if file_path.stat().st_size < 25:
        raise CorruptedFileError("File too small to be a valid PDF", file_path)
    
    # Check PDF header
    with open(file_path, 'rb') as f:
        header = f.read(8)
        if not header.startswith(b'%PDF-'):
            raise CorruptedFileError("Invalid PDF header - file may be corrupted", file_path)
        
        # Check for proper structure (look for %%EOF marker)
        f.seek(-1024, 2)  # Seek to last 1KB
        try:
            tail = f.read()
            if b'%%EOF' not in tail:
                raise CorruptedFileError("Missing PDF EOF marker - file may be truncated", file_path)
        except:
            # File too small for this check, but header is valid
            pass
    
    return True


def validate_epub(file_path: Path) -> bool:
    """
    Validate that a file is a valid EPUB.
    
    Args:
        file_path: Path to the EPUB file
        
    Returns:
        True if valid, raises exception otherwise
    """
    import zipfile
    
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    # Check if it's a valid ZIP file (EPUBs are ZIP archives)
    if not zipfile.is_zipfile(file_path):
        raise CorruptedFileError("Not a valid ZIP archive - EPUB may be corrupted", file_path)
    
    # Check for required EPUB structure
    try:
        with zipfile.ZipFile(file_path, 'r') as zf:
            names = zf.namelist()
            
            # Must have mimetype file
            if 'mimetype' not in names:
                raise EPUBParsingError("Missing mimetype file", file_path=file_path)
            
            # Check mimetype content
            mimetype = zf.read('mimetype').decode('utf-8').strip()
            if mimetype != 'application/epub+zip':
                raise EPUBParsingError(
                    f"Invalid mimetype: {mimetype}",
                    details="Expected: application/epub+zip",
                    file_path=file_path
                )
            
            # Must have META-INF/container.xml
            if 'META-INF/container.xml' not in names:
                raise EPUBParsingError(
                    "Missing container.xml",
                    details="Required EPUB structure file not found",
                    file_path=file_path
                )
    except zipfile.BadZipFile:
        raise CorruptedFileError("Corrupted ZIP structure in EPUB", file_path)
    
    return True


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename by removing/replacing invalid characters.
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename safe for all operating systems
    """
    import re
    
    # Characters not allowed in filenames on various OSes
    invalid_chars = r'[<>:"/\\|?*\x00-\x1f]'
    
    # Replace invalid characters with underscores
    sanitized = re.sub(invalid_chars, '_', filename)
    
    # Remove leading/trailing spaces and dots
    sanitized = sanitized.strip(' .')
    
    # Collapse multiple underscores
    sanitized = re.sub(r'_+', '_', sanitized)
    
    # Ensure filename is not empty
    if not sanitized:
        sanitized = "untitled"
    
    # Limit length (255 bytes for most filesystems, keep some margin)
    if len(sanitized.encode('utf-8')) > 200:
        # Truncate while preserving extension
        name, ext = Path(sanitized).stem, Path(sanitized).suffix
        max_name_len = 200 - len(ext.encode('utf-8'))
        name = name.encode('utf-8')[:max_name_len].decode('utf-8', errors='ignore')
        sanitized = name + ext
    
    return sanitized


def check_disk_space(path: Path, required_bytes: int) -> bool:
    """
    Check if there's enough disk space.
    
    Args:
        path: Path to check (uses its mount point)
        required_bytes: Required space in bytes
        
    Returns:
        True if enough space, raises DiskFullError otherwise
    """
    import shutil
    
    # Get disk usage for the path's mount point
    usage = shutil.disk_usage(path.parent if path.is_file() else path)
    
    if usage.free < required_bytes:
        raise DiskFullError(required_bytes)
    
    return True


def estimate_audio_size(word_count: int, bitrate_kbps: int = 128) -> int:
    """
    Estimate the size of generated audio in bytes.
    
    Args:
        word_count: Number of words
        bitrate_kbps: Audio bitrate in kbps
        
    Returns:
        Estimated size in bytes
    """
    # Average speaking rate: ~150 words per minute
    duration_minutes = word_count / 150
    duration_seconds = duration_minutes * 60
    
    # Size = bitrate * duration / 8 (convert bits to bytes)
    size_bytes = (bitrate_kbps * 1000 * duration_seconds) / 8
    
    # Add 20% overhead for container format
    return int(size_bytes * 1.2)
