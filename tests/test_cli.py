"""
Test CLI Module
===============
Script-style tests for the terminal CLI command surface.
"""

import io
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from modules.app.controller import JobStatus
from modules.cli.main import main as cli_main


class FakeJob:
    def __init__(self, job_id: str, status: JobStatus, success: bool = True):
        self.id = job_id
        self.status = status
        self.error = None if success else "test failure"
        self.result = SimpleNamespace(success=success, output_path="output/test.m4b", error_message=self.error)
        self._active = False

    def is_active(self) -> bool:
        return self._active

    def wait(self, timeout=None) -> bool:  # noqa: ARG002
        return True


class FakeController:
    def __init__(self, mode: str = "ok"):
        self.mode = mode
        self.cleaned = False
        self.active_job = FakeJob("conv_123", JobStatus.RUNNING, success=True)
        self.active_job._active = True

    def start_conversion(self, source_path, voice, speed, callbacks=None, title=None, author=None):  # noqa: ARG002
        if self.mode == "start_error":
            raise RuntimeError("boom")
        if callbacks and callbacks.on_progress:
            callbacks.on_progress("synthesizing", 1.0, "done")
        job = FakeJob("conv_999", JobStatus.COMPLETED, success=(self.mode != "convert_fail"))
        if self.mode == "convert_fail":
            job.status = JobStatus.FAILED
        return job

    def get_active_job(self):
        if self.mode == "no_active":
            return None
        return self.active_job

    def cancel_conversion(self):
        if self.mode == "cancel_fail":
            return False
        self.active_job._active = False
        self.active_job.status = JobStatus.CANCELLED
        return True

    def get_processing_history(self, limit=20):  # noqa: ARG002
        return [
            SimpleNamespace(id=7, status=SimpleNamespace(value="completed"), progress=1.0, current_stage="packaging"),
            SimpleNamespace(id=8, status=SimpleNamespace(value="failed"), progress=0.4, current_stage="synthesizing"),
        ]

    def get_library_stats(self):
        return {"total_books": 3, "total_chapters": 12, "total_duration_ms": 600000}

    def get_library_books(self, search=None, limit=50, offset=0):  # noqa: ARG002
        return [
            SimpleNamespace(id=1, title="Book A", author="Author A", completed_chapters=5, total_chapters=5),
            SimpleNamespace(id=2, title="Book B", author=None, completed_chapters=2, total_chapters=4),
        ]

    def cleanup(self):
        self.cleaned = True


def run_case(argv, mode="ok"):
    output = io.StringIO()
    controller = FakeController(mode=mode)
    code = cli_main(argv=argv, controller_factory=lambda: controller, out=output)
    return code, output.getvalue(), controller


def test_cli():
    """Run all CLI tests."""
    print("\n" + "=" * 50)
    print("CLI TEST SUITE")
    print("=" * 50 + "\n")

    # convert success
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "book.pdf"
        src.write_text("dummy")
        code, out, _ = run_case(["convert", str(src)])
    assert code == 0
    assert "conversion completed" in out
    print("✓ convert success")

    # convert missing file
    code, out, _ = run_case(["convert", "/tmp/does-not-exist.pdf"])
    assert code == 1
    assert "source file not found" in out
    print("✓ convert missing file")

    # convert start error
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "book.epub"
        src.write_text("dummy")
        code, out, _ = run_case(["convert", str(src)], mode="start_error")
    assert code == 1
    assert "failed to start conversion" in out
    print("✓ convert start error handling")

    # jobs
    code, out, _ = run_case(["jobs"])
    assert code == 0
    assert "history (latest 20)" in out
    assert "id=7" in out
    print("✓ jobs listing")

    # cancel no active
    code, out, _ = run_case(["cancel"], mode="no_active")
    assert code == 1
    assert "no active conversion job" in out
    print("✓ cancel with no active job")

    # cancel active
    code, out, _ = run_case(["cancel", "conv_123"])
    assert code == 0
    assert "cancelled job conv_123" in out
    print("✓ cancel active job")

    # library list
    code, out, _ = run_case(["library", "list"])
    assert code == 0
    assert "library stats:" in out
    assert "Book A" in out
    print("✓ library list")

    print("\n" + "=" * 50)
    print("ALL CLI TESTS PASSED ✓")
    print("=" * 50 + "\n")
    return True


if __name__ == "__main__":
    success = test_cli()
    sys.exit(0 if success else 1)
