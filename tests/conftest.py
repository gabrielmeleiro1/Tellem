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
    if not path.exists():
        # Create a dummy PDF file if it doesn't exist
        with open(path, "wb") as f:
            f.write(b"%PDF-1.4\n%EOF")
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
