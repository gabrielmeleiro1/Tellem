"""
Test main launcher module.
"""

import subprocess
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import audiobook_tui
import main as launcher


def test_main_launcher() -> bool:
    print("\n" + "=" * 50)
    print("MAIN LAUNCHER TEST SUITE")
    print("=" * 50 + "\n")

    assert launcher.main is audiobook_tui.main
    print("✓ main.py delegates to audiobook_tui.main")

    result = subprocess.run(
        [sys.executable, "main.py", "--help"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "Audiobook Creator Textual TUI" in result.stdout
    print("✓ main.py --help works")

    print("\n" + "=" * 50)
    print("ALL MAIN LAUNCHER TESTS PASSED ✓")
    print("=" * 50 + "\n")
    return True


if __name__ == "__main__":
    success = test_main_launcher()
    sys.exit(0 if success else 1)
