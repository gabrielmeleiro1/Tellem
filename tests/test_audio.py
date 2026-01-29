
import pytest
import numpy as np
from unittest.mock import MagicMock, patch, mock_open
from pathlib import Path

from modules.audio.processor import AudioProcessor
from modules.audio.encoder import AudioEncoder
from modules.audio.packager import M4BPackager, AudiobookMetadata, ChapterMarker

class TestAudioProcessor:
    @patch("modules.audio.processor.AudioSegment")
    def test_concatenate(self, mock_audiosegment):
        processor = AudioProcessor()
        # Create mock audio segments
        seg1 = MagicMock()
        seg2 = MagicMock()
        # Setup addition result
        seg1.__add__.return_value = seg1 
        
        result = processor.concatenate([seg1, seg2])
        seg1.__add__.assert_called()

    @patch("modules.audio.processor.AudioSegment")
    def test_normalize_volume(self, mock_audiosegment):
        processor = AudioProcessor()
        audio = MagicMock()
        audio.__len__.return_value = 1000 # 1 second
        audio.dBFS = -20.0
        audio.apply_gain.return_value = audio
        
        # Target -16, current -20, gain should be +4
        normalized = processor.normalize_volume(audio, target_dBFS=-16.0)
        audio.apply_gain.assert_called_with(4.0)

class TestAudioEncoder:
    @patch("shutil.which")
    def test_ffmpeg_check(self, mock_which):
        mock_which.return_value = "/usr/bin/ffmpeg"
        encoder = AudioEncoder()
        assert encoder.sample_rate == 24000
    
    @patch("subprocess.run")
    @patch("shutil.which")
    def test_wav_to_mp3(self, mock_which, mock_run):
        mock_which.return_value = "/usr/bin/ffmpeg"
        mock_run.return_value = MagicMock(returncode=0)
        
        encoder = AudioEncoder()
        
        # We need to mock input path exists
        with patch("pathlib.Path.exists", return_value=True):
            encoder.wav_to_mp3("input.wav", "output.mp3")
            
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "ffmpeg" in args
        assert "-b:a" in args
        assert "128k" in args

class TestM4BPackager:
    def test_chapter_marker_creation(self):
        marker = ChapterMarker("Chapter 1", 0, 10000)
        assert marker.start_seconds == 0.0
        assert marker.end_seconds == 10.0
        
    @patch("subprocess.run")
    @patch("shutil.which")
    def test_create_m4b(self, mock_which, mock_run):
        mock_which.return_value = "/usr/bin/ffmpeg"
        mock_run.return_value = MagicMock(returncode=0)
        
        packager = M4BPackager()
        metadata = AudiobookMetadata(title="Test", author="Author")
        
        # Mocking file operations
        with patch("builtins.open", mock_open()), \
             patch("pathlib.Path.mkdir"), \
             patch("pathlib.Path.exists", return_value=True), \
             patch.object(packager, '_generate_chapter_markers', return_value=[]), \
             patch.object(packager, '_write_ffmetadata'):
             
             packager.create_m4b(["ch1.mp3"], ["Chapter 1"], metadata, "out.m4b")
             
        assert mock_run.call_count >= 2 # concat + final package commands
