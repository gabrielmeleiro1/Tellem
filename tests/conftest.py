import pytest
from pathlib import Path
import sys
import shutil

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

@pytest.fixture
def test_data_dir():
    """Return path to test fixtures directory."""
    return Path(__file__).parent / "fixtures"

@pytest.fixture
def sample_pdf(test_data_dir):
    """Return path to sample PDF."""
    path = test_data_dir / "sample.pdf"
    # Create a minimal valid PDF structure (larger than 100 bytes to pass validation)
    pdf_content = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [] /Count 0 >>
endobj
xref
0 3
0000000000 65535 f 
0000000009 00000 n 
0000000052 00000 n 
trailer
<< /Size 3 /Root 1 0 R >>
startxref
110
%%EOF
"""
    path.write_bytes(pdf_content)
    return path

@pytest.fixture
def sample_epub(test_data_dir):
    """Return path to sample EPUB."""
    path = test_data_dir / "sample.epub"
    if not path.exists():
        # Create a dummy EPUB file if it doesn't exist
        with open(path, "wb") as f:
            f.write(b"PK\x03\x04")  # Zip header
    return path

@pytest.fixture
def mock_tts_engine(mocker):
    """Mock TTS Engine to avoid loading models."""
    mock = mocker.patch("modules.tts.engine.TTSEngine") 
    return mock
