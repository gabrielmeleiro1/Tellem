"""
M4B Packager Module
===================
Creates M4B audiobooks with chapter markers using FFmpeg.
Optimized for Apple Books and other audiobook players.
"""

from __future__ import annotations

import subprocess
import shutil
from pathlib import Path
from typing import Optional
from dataclasses import dataclass
import json
import tempfile


def _check_ffmpeg() -> bool:
    """Check if FFmpeg is available in PATH."""
    return shutil.which("ffmpeg") is not None


@dataclass
class ChapterMarker:
    """Chapter marker for M4B TOC."""
    title: str
    start_ms: int
    end_ms: int
    
    @property
    def start_seconds(self) -> float:
        return self.start_ms / 1000.0
    
    @property
    def end_seconds(self) -> float:
        return self.end_ms / 1000.0


@dataclass
class AudiobookMetadata:
    """Metadata for audiobook files."""
    title: str
    author: str
    narrator: Optional[str] = None
    year: Optional[str] = None
    genre: str = "Audiobook"
    comment: Optional[str] = None
    cover_path: Optional[Path | str] = None


class M4BPackager:
    """
    M4B audiobook packager using FFmpeg.
    
    Creates M4B files with chapter markers, metadata, and cover art.
    Compatible with Apple Books and other audiobook players.
    """
    
    def __init__(self):
        """Initialize the M4B packager."""
        if not _check_ffmpeg():
            raise RuntimeError(
                "FFmpeg not found. Install with: brew install ffmpeg"
            )
    
    def create_m4b(
        self,
        mp3_files: list[Path | str],
        chapter_names: list[str],
        metadata: AudiobookMetadata,
        output_path: Path | str
    ) -> Path:
        """
        Create M4B audiobook from MP3 files.
        
        Args:
            mp3_files: List of paths to MP3 chapter files (in order)
            chapter_names: List of chapter names (same length as mp3_files)
            metadata: Audiobook metadata
            output_path: Path for output M4B file
            
        Returns:
            Path to generated M4B file
        """
        if len(mp3_files) != len(chapter_names):
            raise ValueError("mp3_files and chapter_names must have same length")
        
        mp3_files = [Path(f) for f in mp3_files]
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Verify all input files exist
        for mp3_file in mp3_files:
            if not mp3_file.exists():
                raise FileNotFoundError(f"MP3 file not found: {mp3_file}")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Step 1: Concatenate MP3 files into single AAC stream
            concat_file = temp_path / "concat.txt"
            concat_m4a = temp_path / "concat.m4a"
            
            # Create FFmpeg concat file
            with open(concat_file, "w") as f:
                for mp3_file in mp3_files:
                    f.write(f"file '{mp3_file.absolute()}'\n")
            
            # Concatenate and convert to AAC
            concat_cmd = [
                "ffmpeg", "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_file),
                "-c:a", "aac",
                "-b:a", "128k",
                "-movflags", "+faststart",
                str(concat_m4a)
            ]
            
            result = subprocess.run(
                concat_cmd,
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                raise RuntimeError(f"Concatenation failed: {result.stderr}")
            
            # Step 2: Generate chapter markers
            chapters = self._generate_chapter_markers(mp3_files, chapter_names)
            chapter_file = temp_path / "chapters.txt"
            self._write_ffmetadata(chapter_file, chapters, metadata)
            
            # Step 3: Add metadata and chapters to M4B
            final_cmd = [
                "ffmpeg", "-y",
                "-i", str(concat_m4a),
                "-i", str(chapter_file),
                "-map_metadata", "1",
                "-c:a", "copy",
            ]
            
            # Add cover art if provided
            if metadata.cover_path and Path(metadata.cover_path).exists():
                final_cmd.extend([
                    "-i", str(metadata.cover_path),
                    "-map", "0:a",
                    "-map", "2:v",
                    "-c:v", "mjpeg",
                    "-disposition:v", "attached_pic",
                ])
            
            final_cmd.append(str(output_path))
            
            result = subprocess.run(
                final_cmd,
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                raise RuntimeError(f"M4B creation failed: {result.stderr}")
        
        return output_path
    
    def _generate_chapter_markers(
        self,
        mp3_files: list[Path],
        chapter_names: list[str]
    ) -> list[ChapterMarker]:
        """Generate chapter markers from MP3 file durations."""
        from .encoder import AudioEncoder
        
        encoder = AudioEncoder()
        chapters = []
        current_ms = 0
        
        for mp3_file, chapter_name in zip(mp3_files, chapter_names):
            duration_sec = encoder.get_duration(mp3_file)
            duration_ms = int(duration_sec * 1000)
            
            chapters.append(ChapterMarker(
                title=chapter_name,
                start_ms=current_ms,
                end_ms=current_ms + duration_ms
            ))
            
            current_ms += duration_ms
        
        return chapters
    
    def _write_ffmetadata(
        self,
        output_path: Path,
        chapters: list[ChapterMarker],
        metadata: AudiobookMetadata
    ) -> None:
        """Write FFmpeg metadata file with chapters."""
        lines = [";FFMETADATA1"]
        
        # Add metadata
        lines.append(f"title={metadata.title}")
        lines.append(f"artist={metadata.author}")
        lines.append(f"album={metadata.title}")
        lines.append(f"genre={metadata.genre}")
        
        if metadata.narrator:
            lines.append(f"composer={metadata.narrator}")
        if metadata.year:
            lines.append(f"date={metadata.year}")
        if metadata.comment:
            lines.append(f"comment={metadata.comment}")
        
        # Add chapters
        for chapter in chapters:
            lines.append("")
            lines.append("[CHAPTER]")
            lines.append("TIMEBASE=1/1000")
            lines.append(f"START={chapter.start_ms}")
            lines.append(f"END={chapter.end_ms}")
            lines.append(f"title={chapter.title}")
        
        with open(output_path, "w") as f:
            f.write("\n".join(lines))
    
    def get_chapters(self, m4b_path: Path | str) -> list[ChapterMarker]:
        """
        Extract chapter markers from existing M4B file.
        
        Args:
            m4b_path: Path to M4B file
            
        Returns:
            List of ChapterMarker objects
        """
        m4b_path = Path(m4b_path)
        
        if not m4b_path.exists():
            raise FileNotFoundError(f"M4B file not found: {m4b_path}")
        
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_chapters",
            str(m4b_path)
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"FFprobe failed: {result.stderr}")
        
        data = json.loads(result.stdout)
        chapters = []
        
        for ch in data.get("chapters", []):
            chapters.append(ChapterMarker(
                title=ch.get("tags", {}).get("title", "Chapter"),
                start_ms=int(float(ch["start_time"]) * 1000),
                end_ms=int(float(ch["end_time"]) * 1000)
            ))
        
        return chapters


def test_packager() -> bool:
    """
    Quick test of M4B packager functionality.
    
    Returns:
        True if test passes
    """
    import numpy as np
    import wave
    
    try:
        packager = M4BPackager()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create test MP3 files
            from .encoder import AudioEncoder
            encoder = AudioEncoder()
            
            mp3_files = []
            chapter_names = ["Chapter 1", "Chapter 2", "Chapter 3"]
            
            for i, name in enumerate(chapter_names):
                # Generate test WAV
                wav_file = temp_path / f"chapter_{i+1}.wav"
                mp3_file = temp_path / f"chapter_{i+1}.mp3"
                
                sample_rate = 24000
                duration = 0.5  # Short for testing
                t = np.linspace(0, duration, int(sample_rate * duration))
                freq = 440 * (i + 1)  # Different frequency per chapter
                audio = (np.sin(2 * np.pi * freq * t) * 32767).astype(np.int16)
                
                with wave.open(str(wav_file), 'w') as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(sample_rate)
                    wf.writeframes(audio.tobytes())
                
                encoder.wav_to_mp3(wav_file, mp3_file)
                mp3_files.append(mp3_file)
            
            # Create M4B
            metadata = AudiobookMetadata(
                title="Test Audiobook",
                author="Test Author",
                narrator="Test Narrator"
            )
            
            output_m4b = temp_path / "test_audiobook.m4b"
            result = packager.create_m4b(
                mp3_files,
                chapter_names,
                metadata,
                output_m4b
            )
            
            assert result.exists(), "M4B file not created"
            
            # Verify chapters
            chapters = packager.get_chapters(result)
            assert len(chapters) == 3, f"Expected 3 chapters, got {len(chapters)}"
            
            for i, ch in enumerate(chapters):
                print(f"  {ch.title}: {ch.start_seconds:.2f}s - {ch.end_seconds:.2f}s")
            
            print("M4BPackager test passed!")
            return True
        
    except Exception as e:
        print(f"M4BPackager test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    test_packager()
