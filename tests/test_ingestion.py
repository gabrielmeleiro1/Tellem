
import pytest
from pathlib import Path
from modules.ingestion.pdf_parser import PDFParser
from modules.ingestion.epub_parser import EPUBParser

class TestPDFParser:
    def test_init(self, sample_pdf):
        parser = PDFParser(sample_pdf)
        assert parser.file_path == sample_pdf
    
    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            PDFParser("nonexistent.pdf")

class TestEPUBParser:
    def test_init(self, sample_epub):
        parser = EPUBParser(sample_epub)
        assert parser.file_path == sample_epub

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            EPUBParser("nonexistent.epub")
