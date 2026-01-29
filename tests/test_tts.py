
import pytest
from unittest.mock import MagicMock, patch
from modules.tts.chunker import TextChunker, ChunkConfig
from modules.tts.cleaner import TextCleaner
from modules.tts.engine import TTSEngine

class TestTextChunker:
    def test_chunking(self):
        config = ChunkConfig(max_tokens=10)
        chunker = TextChunker(config)
        text = "This is sentence one. This is sentence two. This is sentence three."
        chunks = chunker.chunk(text)
        assert len(chunks) > 0
        assert all(isinstance(c, str) for c in chunks)
    
    def test_empty_text(self):
        chunker = TextChunker()
        assert chunker.chunk("") == []

class TestTextCleaner:
    def test_rule_based_cleaning(self):
        cleaner = TextCleaner()
        # Mock load to prevent model loading
        with patch.object(cleaner, 'load'):
            text = "Dr. Smith went to St. Louis."
            cleaned = cleaner.clean(text)
            assert "Doctor Smith" in cleaned
            assert "Saint Louis" in cleaned

    def test_no_cleaning_needed(self):
        cleaner = TextCleaner()
        with patch.object(cleaner, 'load'):
            text = "Simple text."
            assert cleaner.clean(text) == text

class TestTTSEngine:
    def test_init(self):
        engine = TTSEngine()
        assert engine.config.model_name is not None
    
    @patch("modules.tts.engine.generate_audio")
    @patch("soundfile.read")
    @patch("os.listdir")
    def test_synthesize(self, mock_listdir, mock_sf_read, mock_generate):
        # Mocking file system interactions for synthesis
        mock_listdir.return_value = ["output.wav"]
        mock_sf_read.return_value = ([0.1, 0.2, 0.3], 24000)
        
        engine = TTSEngine()
        # Mock internal model path to avoid validation error if checking exists
        engine._model_path = "/tmp/mock_model" 
        
        # We need to mock load_model to avoid actual download/load
        with patch.object(engine, 'load_model'):
            engine._model_path = "mock_path" # Ensure it's set after load_model mock
            audio = engine.synthesize("Hello world", voice="af_bella", speed=1.0)
            
            assert audio is not None
            mock_generate.assert_called_once()
