"""
Textual TUI App
===============
First terminal UI screen for conversion status, progress, and logs.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Button, Footer, Header, ProgressBar, RichLog, Static

from modules.app import AppController, ConversionCallbacks
from modules.app.events import AppEvent, EventType


@dataclass
class LaunchOptions:
    source: Optional[Path] = None
    voice: str = "am_adam"
    speed: float = 1.0
    title: Optional[str] = None
    author: Optional[str] = None


class AudiobookTUI(App):
    """Brutalist terminal dashboard for audiobook conversion."""

    CSS = """
    Screen {
        background: #131313;
        color: #f5f1e8;
    }
    #root {
        height: 1fr;
        layout: vertical;
    }
    #actions {
        height: auto;
        border: solid #e9d7b8;
        margin: 1 1 0 1;
        padding: 1;
        background: #1d1d1d;
    }
    #panes {
        height: 1fr;
        margin: 0 1 1 1;
    }
    #status-pane, #progress-pane, #log-pane {
        border: solid #e9d7b8;
        background: #1d1d1d;
        padding: 1;
        margin-right: 1;
    }
    #log-pane {
        margin-right: 0;
    }
    .label {
        color: #f7b267;
        text-style: bold;
    }
    Button {
        background: #2b2b2b;
        color: #f5f1e8;
        border: solid #e9d7b8;
        margin-right: 1;
    }
    Button.-primary {
        background: #7f2a1d;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("s", "start_conversion", "Start"),
        ("c", "cancel_conversion", "Cancel"),
        ("r", "refresh_status", "Refresh"),
    ]

    progress_value = reactive(0.0)
    current_stage = reactive("idle")
    current_status = reactive("idle")

    def __init__(self, options: Optional[LaunchOptions] = None):
        super().__init__()
        self.options = options or LaunchOptions()
        self.controller = AppController()
        self._messages: deque[str] = deque(maxlen=500)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id="root"):
            with Horizontal(id="actions"):
                yield Button("Start (s)", id="start", classes="-primary")
                yield Button("Cancel (c)", id="cancel")
                yield Button("Refresh (r)", id="refresh")
                yield Static("Terminal-first dashboard", classes="label")
            with Horizontal(id="panes"):
                with Vertical(id="status-pane"):
                    yield Static("Status", classes="label")
                    yield Static("job: none", id="job-text")
                    yield Static("state: idle", id="state-text")
                    yield Static("stage: idle", id="stage-text")
                with Vertical(id="progress-pane"):
                    yield Static("Progress", classes="label")
                    yield ProgressBar(total=100, id="progress-bar")
                    yield Static("0%", id="progress-text")
                with Vertical(id="log-pane"):
                    yield Static("Logs", classes="label")
                    yield RichLog(id="log-view", wrap=True, highlight=True)
        yield Footer()

    def on_mount(self) -> None:
        self._log("ready")
        if self.options.source:
            self.action_start_conversion()

    def _log(self, message: str) -> None:
        self._messages.append(message)
        log = self.query_one("#log-view", RichLog)
        log.write(message)

    def _emit_event(self, event: AppEvent) -> None:
        if event.event_type == EventType.PROGRESS:
            self.progress_value = event.progress
            self.current_stage = event.stage
            self.query_one("#stage-text", Static).update(f"stage: {self.current_stage}")
            pct = int(event.progress * 100)
            progress_bar = self.query_one("#progress-bar", ProgressBar)
            progress_bar.update(progress=pct)
            self.query_one("#progress-text", Static).update(f"{pct}%")
            if event.message:
                self._log(f"[progress] {event.message}")
        elif event.event_type == EventType.LOG:
            self._log(f"[{event.level}] {event.message}")
        elif event.event_type == EventType.STATE:
            self.current_status = event.state.value
            self.query_one("#state-text", Static).update(f"state: {self.current_status}")
            self.query_one("#job-text", Static).update(f"job: {event.job_id}")
            if event.message:
                self._log(f"[state] {event.message}")

    def _make_callbacks(self) -> ConversionCallbacks:
        def on_event(event: AppEvent) -> None:
            # Background thread callback -> marshal onto UI thread.
            self.call_from_thread(self._emit_event, event)

        return ConversionCallbacks(on_event=on_event)

    def action_refresh_status(self) -> None:
        job = self.controller.get_active_job()
        if job and job.is_active():
            self.query_one("#job-text", Static).update(f"job: {job.id}")
            self.query_one("#state-text", Static).update(f"state: {job.status.value}")
            self._log("status refreshed: active job")
            return
        self.query_one("#job-text", Static).update("job: none")
        self.query_one("#state-text", Static).update("state: idle")
        self._log("status refreshed: no active job")

    def action_start_conversion(self) -> None:
        source = self.options.source
        if not source:
            self._log("no source configured; relaunch with --source <file>")
            return
        if not source.exists():
            self._log(f"source not found: {source}")
            return
        try:
            job = self.controller.start_conversion(
                source_path=source,
                voice=self.options.voice,
                speed=self.options.speed,
                title=self.options.title,
                author=self.options.author,
                callbacks=self._make_callbacks(),
            )
            self.query_one("#job-text", Static).update(f"job: {job.id}")
            self.query_one("#state-text", Static).update("state: running")
            self.query_one("#stage-text", Static).update("stage: starting")
            self._log(f"started conversion: {job.id}")
        except Exception as exc:
            self._log(f"failed to start conversion: {exc}")

    def action_cancel_conversion(self) -> None:
        cancelled = self.controller.cancel_conversion()
        if cancelled:
            self._log("cancel requested")
            self.query_one("#state-text", Static).update("state: cancelled")
        else:
            self._log("no active conversion to cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "start":
            self.action_start_conversion()
        elif event.button.id == "cancel":
            self.action_cancel_conversion()
        elif event.button.id == "refresh":
            self.action_refresh_status()

    def on_unmount(self) -> None:
        self.controller.cleanup()
