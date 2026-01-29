
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from modules.ingestion.pdf_parser import PDFParser, Document, Chapter

class TestPDFParser:
    @pytest.fixture
    def mock_parser_deps(self):
        with patch("modules.ingestion.pdf_parser.pymupdf4llm") as mock_llm, \
             patch("fitz.open") as mock_open:
            
            # Setup pymupdf4llm to return page chunks
            mock_llm.to_markdown.return_value = [
                {"text": "Page 1 Content"},
                {"text": "Page 2 Content"},
                {"text": "Page 3 Content"}
            ]
            
            # Setup fitz doc
            mock_doc = MagicMock()
            mock_doc.__len__.return_value = 3
            mock_doc.metadata = {"title": "Test Book", "author": "Tester"}
            # Return TOC: 2 chapters. Ch1 starts pg1, Ch2 starts pg3
            # TOC format: [level, title, page_num]
            mock_doc.get_toc.return_value = [
                [1, "Chapter 1", 1],
                [1, "Chapter 2", 3]
            ]
            
            mock_open.return_value.__enter__.return_value = mock_doc
            
            yield mock_llm, mock_open

    def test_init(self, sample_pdf):
        parser = PDFParser(sample_pdf)
        assert parser.file_path == sample_pdf
    
    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            PDFParser("nonexistent.pdf")

    def test_parse_success(self, sample_pdf, mock_parser_deps):
        parser = PDFParser(sample_pdf)
        doc = parser.parse()
        
        assert isinstance(doc, Document)
        assert doc.title == "Test Book"
        assert len(doc.chapters) == 2
        
        # Verify content mapping
        # Ch1 is pg1-2 (inclusive logic in extract_chapters: start 1, next starts 3 -> end 2)
        # However, 0-indexed slicing:
        # Ch1: start_page=1 (idx 0), end_page=2. Slice [0:2] -> Page 1, Page 2
        assert "Page 1 Content" in doc.chapters[0].content
        assert "Page 2 Content" in doc.chapters[0].content
        assert "Page 3 Content" not in doc.chapters[0].content
        
        # Ch2: start_page=3 (idx 2), end_page=3. Slice [2:3] -> Page 3
        assert "Page 3 Content" in doc.chapters[1].content
        assert "Page 1 Content" not in doc.chapters[1].content
