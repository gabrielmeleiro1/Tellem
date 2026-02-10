"""
Test TUI Launcher Module
========================
Script-style tests for the terminal TUI launcher.
"""

import io
import sys
import tempfile
import types
from pathlib import Path
from unittest.mock import patch

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import audiobook_tui


def test_tui() -> bool:
    print("\n" + "=" * 50)
    print("TUI TEST SUITE")
    print("=" * 50 + "\n")

    # Test parser defaults
    parser = audiobook_tui.build_parser()
    args = parser.parse_args([])
    assert args.source is None
    assert args.voice == "am_adam"
    assert args.speed == 1.0
    assert args.tts_engine == "kokoro"
    assert args.tts_quantization == "bf16"
    print("✓ parser default args")

    # Test parser custom args
    args = parser.parse_args(
        [
            "--voice",
            "af_bella",
            "--speed",
            "1.2",
            "--title",
            "Test",
            "--tts-engine",
            "kokoro",
            "--tts-quantization",
            "4bit",
            "--cleaner-model",
            "mlx-community/Llama-3.2-1B-Instruct-4bit",
        ]
    )
    assert args.voice == "af_bella"
    assert args.speed == 1.2
    assert args.title == "Test"
    assert args.tts_engine == "kokoro"
    assert args.tts_quantization == "4bit"
    assert args.cleaner_model == "mlx-community/Llama-3.2-1B-Instruct-4bit"
    print("✓ parser custom args")

    # Test missing textual dependency path
    stderr = io.StringIO()
    original_import = __import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):  # noqa: A002
        if name == "modules.tui.app":
            raise ImportError("missing textual")
        return original_import(name, globals, locals, fromlist, level)

    with patch("builtins.__import__", side_effect=fake_import):
        with patch("sys.stderr", stderr):
            code = audiobook_tui.main([])
    assert code == 1
    assert "Textual is not installed" in stderr.getvalue()
    print("✓ import error handling")

    # Test successful run path with fake app module
    fake_module = types.ModuleType("modules.tui.app")
    state = {"ran": False, "options": None}

    class LaunchOptions:
        def __init__(
            self,
            source=None,
            voice="am_adam",
            speed=1.0,
            title=None,
            author=None,
            tts_engine="kokoro",
            tts_quantization="bf16",
            cleaner_model="mlx-community/Llama-3.2-3B-Instruct-4bit",
        ):
            self.source = source
            self.voice = voice
            self.speed = speed
            self.title = title
            self.author = author
            self.tts_engine = tts_engine
            self.tts_quantization = tts_quantization
            self.cleaner_model = cleaner_model

    class AudiobookTUI:
        def __init__(self, options):
            state["options"] = options

        def run(self):
            state["ran"] = True

    fake_module.LaunchOptions = LaunchOptions
    fake_module.AudiobookTUI = AudiobookTUI

    with tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp) / "sample.pdf"
        source.write_text("dummy")

        with patch.dict(sys.modules, {"modules.tui.app": fake_module}):
            code = audiobook_tui.main(
                [
                    "--source",
                    str(source),
                    "--voice",
                    "bm_george",
                    "--speed",
                    "1.4",
                    "--tts-engine",
                    "kokoro",
                    "--tts-quantization",
                    "8bit",
                    "--cleaner-model",
                    "mlx-community/Llama-3.2-1B-Instruct-4bit",
                ]
            )

    assert code == 0
    assert state["ran"] is True
    assert state["options"] is not None
    assert state["options"].source == source.resolve()
    assert state["options"].voice == "bm_george"
    assert state["options"].speed == 1.4
    assert state["options"].tts_engine == "kokoro"
    assert state["options"].tts_quantization == "8bit"
    assert state["options"].cleaner_model == "mlx-community/Llama-3.2-1B-Instruct-4bit"
    print("✓ successful launcher path")

    print("\n" + "=" * 50)
    print("ALL TUI TESTS PASSED ✓")
    print("=" * 50 + "\n")
    return True


if __name__ == "__main__":
    success = test_tui()
    sys.exit(0 if success else 1)
