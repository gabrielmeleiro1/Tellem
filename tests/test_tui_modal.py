"""
Test TUI Modal
==============
Script-style tests for NewConversionModal behavior.
"""

import asyncio
import sys
from pathlib import Path

from textual.app import App, ComposeResult
from textual.widgets import Static

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from modules.tui.app import LaunchOptions, NewConversionModal


def _make_modal() -> NewConversionModal:
    tts_engines = [
        {
            "id": "kokoro",
            "display_name": "Kokoro 82M",
            "available_for_conversion": True,
            "voices": [
                {"id": "am_adam", "name": "Adam", "language": "en-US"},
                {"id": "af_bella", "name": "Bella", "language": "en-US"},
            ],
        }
    ]
    voices_by_engine = {
        "kokoro": [
            {"id": "am_adam", "name": "Adam", "language": "en-US"},
            {"id": "af_bella", "name": "Bella", "language": "en-US"},
        ]
    }
    cleaner_models = ["mlx-community/Llama-3.2-3B-Instruct-4bit"]
    return NewConversionModal(
        initial=LaunchOptions(),
        tts_engines=tts_engines,
        cleaner_models=cleaner_models,
        voices_by_engine=voices_by_engine,
    )


def _test_default_tree_root() -> None:
    root = NewConversionModal._default_tree_root()
    assert root.exists()
    assert root.is_absolute()
    print("✓ modal default tree root")


def _test_normalize_source_input() -> None:
    normalize = NewConversionModal._normalize_source_input

    assert normalize("'~/book.pdf'") == "~/book.pdf"
    assert normalize('"/tmp/my\\ file.pdf"') == "/tmp/my file.pdf"
    assert normalize("(/tmp/my book.epub)") == "/tmp/my book.epub"
    assert normalize("file:///tmp/My%20Book.pdf") == "/tmp/My Book.pdf"
    print("✓ source path normalization")


def _test_bindings_and_actions() -> None:
    modal = _make_modal()

    binding_map = {binding[0]: binding[1] for binding in modal.BINDINGS}
    assert binding_map["enter"] == "submit"
    assert binding_map["escape"] == "cancel_modal"

    state = {"submitted": False, "dismissed": object()}

    def fake_submit() -> None:
        state["submitted"] = True

    def fake_dismiss(value) -> None:
        state["dismissed"] = value

    modal._submit_form = fake_submit  # type: ignore[method-assign]
    modal.dismiss = fake_dismiss  # type: ignore[method-assign]

    modal.action_submit()
    modal.action_cancel_modal()

    assert state["submitted"] is True
    assert state["dismissed"] is None
    print("✓ modal key actions")


async def _test_modal_mount_no_crash_async() -> None:
    class Harness(App[None]):
        def compose(self) -> ComposeResult:
            yield Static("harness")

        def on_mount(self) -> None:
            self.push_screen(_make_modal())

    app = Harness()
    async with app.run_test() as pilot:
        await pilot.pause()


def _test_modal_mount_no_crash() -> None:
    asyncio.run(_test_modal_mount_no_crash_async())
    print("✓ modal mounts and composes")


def test_tui_modal() -> bool:
    print("\n" + "=" * 50)
    print("TUI MODAL TEST SUITE")
    print("=" * 50 + "\n")

    _test_default_tree_root()
    _test_normalize_source_input()
    _test_bindings_and_actions()
    _test_modal_mount_no_crash()

    print("\n" + "=" * 50)
    print("ALL TUI MODAL TESTS PASSED ✓")
    print("=" * 50 + "\n")
    return True


if __name__ == "__main__":
    success = test_tui_modal()
    sys.exit(0 if success else 1)
