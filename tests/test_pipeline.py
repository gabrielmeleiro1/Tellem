
import pytest
from unittest.mock import MagicMock, patch, ANY
from pathlib import Path
from modules.pipeline.orchestrator import ConversionPipeline, PipelineConfig, PipelineStage, ConversionResult
from modules.storage.database import Book, Chapter

class TestConversionPipeline:
    @pytest.fixture
    def mock_components(self):
        """Mock all external components used by pipeline."""
        with patch("modules.ingestion.pdf_parser.PDFParser") as mock_pdf, \
             patch("modules.ingestion.epub_parser.EPUBParser") as mock_epub, \
             patch("modules.tts.cleaner.TextCleaner") as mock_cleaner, \
             patch("modules.tts.chunker.TextChunker") as mock_chunker, \
             patch("modules.tts.engine.TTSEngine") as mock_tts, \
             patch("modules.audio.processor.AudioProcessor") as mock_proc, \
             patch("modules.audio.encoder.AudioEncoder") as mock_enc, \
             patch("modules.audio.packager.M4BPackager") as mock_pkg:
             
            # Setup returns
            mock_pdf.return_value.parse.return_value = Book(
                id=1, title="Test Book", author="Test Author", 
                source_path="test.pdf", source_type="pdf", total_chapters=1,
                created_at=None, updated_at=None
            )
            # Mock Document object
            mock_doc = MagicMock()
            mock_doc.title = "Test Book"
            mock_doc.author = "Test Author"
            mock_doc.chapters = [
                MagicMock(title="Chapter 1", content="Text 1", number=1)
            ]
            mock_pdf.return_value.parse.return_value = mock_doc
            
            mock_cleaner.return_value.__enter__.return_value.clean.side_effect = lambda x: x
            
            # TextChunker is instantiated, so we mock the instance method
            mock_chunker.return_value.chunk.return_value = ["chunk1"]
            mock_chunker.chunk_text.return_value = ["chunk1"] # Fallback
            
            mock_tts.return_value.synthesize.return_value = [0.1]
            
            mock_proc.return_value.load.return_value = MagicMock()
            mock_proc.return_value.normalize_volume.return_value = MagicMock()
            
            mock_enc.return_value.get_duration.return_value = 10.0 # 10 seconds
            
            yield {
                "pdf": mock_pdf,
                "cleaner": mock_cleaner,
                "chunker": mock_chunker,
                "tts": mock_tts
            }

    def test_pipeline_execution_success(self, mock_components, tmp_path):
        config = PipelineConfig(
            output_dir=tmp_path / "output",
            temp_dir=tmp_path / "temp"
        )
        pipeline = ConversionPipeline(config)
        
        with patch("pathlib.Path.exists", return_value=True), \
             patch("soundfile.write") as mock_sf_write:
            result = pipeline.convert(Path("test.pdf"))
        
        if not result.success:
            print(f"Pipeline failed with error: {result.error}")
            
        assert result.success
        assert result.title == "Test Book"
        assert len(result.chapters) == 1
        
    def test_cancellation(self, mock_components, tmp_path):
        config = PipelineConfig(
            output_dir=tmp_path / "output",
            temp_dir=tmp_path / "temp"
        )
        pipeline = ConversionPipeline(config)
        
        # We need to trigger cancellation DURING processing
        # Use chunker side effect to cancel
        def cancel_side_effect(*args, **kwargs):
            pipeline.cancel()
            return ["chunk1"]
            
        mock_components["chunker"].return_value.chunk.side_effect = cancel_side_effect
        mock_components["chunker"].chunk_text.side_effect = cancel_side_effect
        
        with patch("pathlib.Path.exists", return_value=True), \
             patch("soundfile.write"):
            result = pipeline.convert(Path("test.pdf"))
            
        assert not result.success
        assert "Cancelled" in str(result.error)

