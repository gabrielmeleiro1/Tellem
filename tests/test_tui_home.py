"""
Test TUI Home Screen + Palette
==============================
Script-style tests for centralized home flow and brutalist palette.
"""

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _test_palette_values() -> None:
    from modules.tui import theme

    assert theme.BLACK == "#000000"
    assert theme.DARK_GRAY == "#111318"
    assert theme.CHARCOAL_GRAY == "#1A1D22"
    assert theme.ORANGE == "#FF5A14"
    assert theme.TEAL_GREEN == "#46C59E"
    assert theme.CORAL_PINK == "#F26D6D"
    assert theme.OFF_WHITE == "#F2F2F2"
    print("✓ strict palette values")


def _test_home_screen_bindings_and_actions() -> None:
    from modules.tui.screens.home import HomeScreen

    binding_map = {binding[0]: binding[1] for binding in HomeScreen.BINDINGS}
    assert binding_map["1"] == "choose_library"
    assert binding_map["2"] == "choose_convert"

    screen = HomeScreen()
    state = {"result": None}

    def fake_dismiss(value) -> None:
        state["result"] = value

    screen.dismiss = fake_dismiss  # type: ignore[method-assign]

    screen.action_choose_library()
    assert state["result"] == "library"

    screen.action_choose_convert()
    assert state["result"] == "convert"
    print("✓ home screen actions")


def _test_app_css_uses_brutalist_palette() -> None:
    from modules.tui.app import AudiobookTUI
    from modules.tui.theme import (
        BLACK,
        DARK_GRAY,
        CHARCOAL_GRAY,
        ORANGE,
        TEAL_GREEN,
        CORAL_PINK,
        OFF_WHITE,
    )

    css = AudiobookTUI.CSS
    for color in [BLACK, DARK_GRAY, CHARCOAL_GRAY, ORANGE, TEAL_GREEN, CORAL_PINK, OFF_WHITE]:
        assert color in css
    print("✓ app css includes strict palette")


def test_tui_home() -> bool:
    print("\n" + "=" * 50)
    print("TUI HOME TEST SUITE")
    print("=" * 50 + "\n")

    _test_palette_values()
    _test_home_screen_bindings_and_actions()
    _test_app_css_uses_brutalist_palette()

    print("\n" + "=" * 50)
    print("ALL TUI HOME TESTS PASSED ✓")
    print("=" * 50 + "\n")
    return True


if __name__ == "__main__":
    success = test_tui_home()
    sys.exit(0 if success else 1)
