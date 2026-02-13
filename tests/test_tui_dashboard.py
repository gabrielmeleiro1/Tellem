"""
Test TUI Dashboard Screen
=========================
Script-style tests for centralized dashboard screen module.
"""

import asyncio
import sys
from pathlib import Path

from textual.app import App, ComposeResult

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _test_dashboard_export() -> None:
    from modules.tui.screens import DashboardShell

    assert DashboardShell is not None
    print("✓ dashboard screen export")


async def _test_dashboard_widget_tree_async() -> None:
    from modules.tui.screens.dashboard import DashboardShell

    class Harness(App[None]):
        def compose(self) -> ComposeResult:
            yield DashboardShell(id="root")

    app = Harness()
    async with app.run_test() as pilot:
        app.query_one("#actions")
        app.query_one("#panes")
        app.query_one("#status-pane")
        app.query_one("#progress-pane")
        app.query_one("#library-pane")
        app.query_one("#log-pane")
        app.query_one("#new")
        app.query_one("#library")
        app.query_one("#start")
        app.query_one("#cancel")
        app.query_one("#refresh")
        app.query_one("#open-output")
        await pilot.pause()


def _test_dashboard_widget_tree() -> None:
    asyncio.run(_test_dashboard_widget_tree_async())
    print("✓ dashboard widget tree")


def test_tui_dashboard() -> bool:
    print("\n" + "=" * 50)
    print("TUI DASHBOARD TEST SUITE")
    print("=" * 50 + "\n")

    _test_dashboard_export()
    _test_dashboard_widget_tree()

    print("\n" + "=" * 50)
    print("ALL TUI DASHBOARD TESTS PASSED ✓")
    print("=" * 50 + "\n")
    return True


if __name__ == "__main__":
    success = test_tui_dashboard()
    sys.exit(0 if success else 1)
