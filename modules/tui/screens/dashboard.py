"""
Dashboard screen shell for the central TUI layout.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, OptionList, ProgressBar, RichLog, Static


class DashboardShell(Container):
    """Main dashboard shell containing actions and status/progress/library/log panes."""

    def compose(self) -> ComposeResult:
        with Horizontal(id="actions"):
            yield Button("New (n)", id="new", classes="-primary")
            yield Button("Library (l)", id="library")
            yield Button("Start (s)", id="start")
            yield Button("Cancel (c)", id="cancel")
            yield Button("Refresh (r)", id="refresh")
            yield Button("Open Output (o)", id="open-output")
            yield Static("Guided conversion mode", classes="label")
        with Horizontal(id="panes"):
            with Vertical(id="status-pane"):
                yield Static("Selection", classes="label")
                yield Static("source: none", id="source-text")
                yield Static("tts engine: kokoro", id="tts-engine-text")
                yield Static("voice: am_adam", id="voice-text")
                yield Static("cleaner: default", id="cleaner-text")
                yield Static("quantization: bf16", id="quantization-text")
                yield Static("speed: 1.0", id="speed-text")
                yield Static("status", classes="label")
                yield Static("job: none", id="job-text")
                yield Static("state: idle", id="state-text")
                yield Static("stage: idle", id="stage-text")
            with Vertical(id="progress-pane"):
                yield Static("Progress", classes="label")
                yield ProgressBar(total=100, id="progress-bar")
                yield Static("0%", id="progress-text")
            with Vertical(id="library-pane"):
                yield Static("Library", classes="label")
                yield OptionList(id="library-list")
                yield Static("No converted books yet.", id="library-detail")
            with Vertical(id="log-pane"):
                yield Static("Logs", classes="label")
                yield RichLog(id="log-view", wrap=True, highlight=True)

