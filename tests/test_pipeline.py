
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
             patch("modules.tts.engine.concatenate_audio_files") as mock_concat, \
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
            
            # TextCleaner now uses persistent instance with load/clean/unload
            mock_cleaner_instance = MagicMock()
            mock_cleaner_instance.clean.side_effect = lambda x: x
            mock_cleaner.return_value = mock_cleaner_instance
            
            # TextChunker is instantiated, so we mock the instance method
            mock_chunker.return_value.chunk.return_value = ["chunk1"]
            mock_chunker.chunk_text.return_value = ["chunk1"] # Fallback
            
            # Mock batch synthesis - returns BatchResult-like objects
            from modules.tts.engine import BatchResult
            import numpy as np
            
            def mock_synthesize_batch(items, progress_callback=None):
                """Mock batch synthesis that returns audio arrays."""
                results = []
                for i, item in enumerate(items):
                    result = BatchResult(
                        audio=np.array([0.1, 0.2, 0.3], dtype=np.float32),
                        index=i,
                        error=None,
                        duration_ms=100
                    )
                    results.append(result)
                    if progress_callback:
                        progress_callback(i + 1, len(items))
                return results
            
            mock_tts_instance = MagicMock()
            mock_tts_instance.synthesize_batch.side_effect = mock_synthesize_batch
            mock_tts_instance.synthesize.return_value = np.array([0.1, 0.2, 0.3], dtype=np.float32)
            mock_tts.return_value = mock_tts_instance
            
            # Mock concatenate_audio_files to just create the output file
            def mock_concat_side_effect(file_paths, output_path, use_memmap=True):
                Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                Path(output_path).write_bytes(b"fake wav content")
                return Path(output_path)
            mock_concat.side_effect = mock_concat_side_effect
            
            mock_proc.return_value.load.return_value = MagicMock()
            mock_proc.return_value.normalize_volume.return_value = MagicMock()
            
            mock_enc.return_value.get_duration.return_value = 10.0 # 10 seconds
            
            # Make encoder.wav_to_mp3 actually create the file
            def wav_to_mp3_side_effect(wav_path, output_path, bitrate="128k"):
                Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                Path(output_path).write_bytes(b"fake mp3 content")
            mock_enc.return_value.wav_to_mp3.side_effect = wav_to_mp3_side_effect
            
            yield {
                "pdf": mock_pdf,
                "cleaner": mock_cleaner,
                "chunker": mock_chunker,
                "tts": mock_tts,
                "encoder": mock_enc,
            }

    def test_pipeline_execution_success(self, mock_components, tmp_path):
        config = PipelineConfig(
            output_dir=tmp_path / "output",
            temp_dir=tmp_path / "temp"
        )
        pipeline = ConversionPipeline(config)
        
        # Create a dummy test file
        test_file = tmp_path / "test.pdf"
        test_file.write_text("dummy pdf content")
        
        with patch("soundfile.write") as mock_sf_write:
            result = pipeline.convert(test_file)
        
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
        
        # Create a dummy test file
        test_file = tmp_path / "test.pdf"
        test_file.write_text("dummy pdf content")
        
        # We need to trigger cancellation DURING processing
        # Use chunker side effect to cancel
        def cancel_side_effect(*args, **kwargs):
            pipeline.cancel()
            return ["chunk1"]
            
        mock_components["chunker"].return_value.chunk.side_effect = cancel_side_effect
        mock_components["chunker"].chunk_text.side_effect = cancel_side_effect
        
        with patch("soundfile.write"):
            result = pipeline.convert(test_file)
            
        assert not result.success
        assert "Cancelled" in str(result.error)

    def test_persistence_files_created(self, mock_components, tmp_path):
        """Verify that source.md and chapter_XX_cleaned.md files are created."""
        config = PipelineConfig(
            output_dir=tmp_path / "output",
            temp_dir=tmp_path / "temp"
        )
        pipeline = ConversionPipeline(config)
        
        # Create a dummy test file
        test_file = tmp_path / "test.pdf"
        test_file.write_text("dummy pdf content")
        
        with patch("soundfile.write") as mock_sf_write:
            result = pipeline.convert(test_file)
        
        assert result.success
        
        # Check that source.md was created
        book_output_dir = tmp_path / "output" / "Test Book"
        source_md = book_output_dir / "source.md"
        assert source_md.exists(), f"source.md should be created at {source_md}"
        
        # Check that chapter_XX_cleaned.md was created
        chapters_dir = book_output_dir / "chapters"
        chapter_cleaned = chapters_dir / "chapter_01_cleaned.md"
        assert chapter_cleaned.exists(), f"chapter_01_cleaned.md should be created at {chapter_cleaned}"
        
        # Verify content of source.md
        source_content = source_md.read_text(encoding="utf-8")
        assert "# Test Book" in source_content
        
        # Verify content of chapter cleaned file
        chapter_content = chapter_cleaned.read_text(encoding="utf-8")
        assert "# Chapter 1" in chapter_content
        assert "chunk1" in chapter_content  # The cleaned chunk content

