"""
Textual TUI App
===============
Guided terminal workflow for conversion status, progress, logs, and library browsing.
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections import deque
from pathlib import Path
from typing import Optional

from textual.app import App, ComposeResult
from textual.reactive import reactive
from textual.widgets import (
    Button,
    Footer,
    Header,
    OptionList,
    ProgressBar,
    RichLog,
    Static,
)

from modules.app import AppController, ConversionCallbacks
from modules.app.events import AppEvent, EventType
from modules.tui.screens.convert_modal import (
    ConversionRequest,
    LaunchOptions,
    NewConversionModal,
    SUPPORTED_SOURCE_SUFFIXES,
    TTS_QUANTIZATION_CHOICES,
)
from modules.tui.screens.dashboard import DashboardShell
from modules.tui.screens.home import HomeScreen
from modules.tui.styles import APP_CSS


class AudiobookTUI(App):
    """Brutalist terminal dashboard for guided audiobook conversion."""

    CSS = APP_CSS

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("n", "new_conversion", "New"),
        ("l", "open_library", "Library"),
        ("o", "open_selected_output", "Open"),
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

        self._source: Optional[Path] = self.options.source
        self._voice: str = self.options.voice
        self._speed: float = self.options.speed
        self._title: Optional[str] = self.options.title
        self._author: Optional[str] = self.options.author
        self._tts_engine: str = self.options.tts_engine
        self._tts_quantization: str = self.options.tts_quantization
        self._cleaner_model: str = self.options.cleaner_model

        self._tts_engines: dict[str, dict] = {}
        self._voices_by_engine: dict[str, list[dict]] = {}
        self._conversion_supported_engines: set[str] = set()
        self._cleaner_models: list[str] = []

        self._book_ids_by_index: list[int] = []
        self._selected_book_id: Optional[int] = None
        self._selected_output_path: Optional[Path] = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield DashboardShell(id="root")
        yield Footer()

    def on_mount(self) -> None:
        self._load_model_options()
        self._refresh_selection_panel()
        self._log("ready")

        if self._source:
            self.action_open_library()
            self._log(f"auto-starting source from launch option: {self._source}")
            self.action_start_conversion()
            return

        self.push_screen(HomeScreen(), self._on_home_choice)

    def _on_home_choice(self, choice: Optional[str]) -> None:
        selected = choice or "library"
        if selected == "convert":
            self._log("home: convert new book")
            self.action_new_conversion()
            return

        self._log("home: browse library")
        self.action_open_library()

    def _load_model_options(self) -> None:
        tts_engines = self.controller.get_available_tts_engines()
        self._tts_engines = {engine["id"]: engine for engine in tts_engines}
        self._voices_by_engine = {engine["id"]: engine.get("voices", []) for engine in tts_engines}
        self._conversion_supported_engines = {
            engine["id"]
            for engine in tts_engines
            if engine.get("available_for_conversion", False)
        }

        if self._tts_engine not in self._tts_engines:
            self._tts_engine = next(iter(self._conversion_supported_engines), "kokoro")

        if self._tts_engine not in self._conversion_supported_engines and self._conversion_supported_engines:
            self._tts_engine = next(iter(self._conversion_supported_engines))

        available_voice_ids = {
            voice["id"]
            for voice in self._voices_by_engine.get(self._tts_engine, [])
        }
        if self._voice not in available_voice_ids:
            self._voice = next(iter(available_voice_ids), "am_adam")

        self._cleaner_models = self.controller.get_available_cleaner_models()
        if self._cleaner_model not in self._cleaner_models and self._cleaner_models:
            self._cleaner_model = self._cleaner_models[0]

        if self._tts_quantization not in TTS_QUANTIZATION_CHOICES:
            self._tts_quantization = "bf16"

    def _refresh_selection_panel(self) -> None:
        source_value = str(self._source) if self._source else "none"
        self.query_one("#source-text", Static).update(f"source: {source_value}")
        self.query_one("#tts-engine-text", Static).update(f"tts engine: {self._tts_engine}")
        self.query_one("#voice-text", Static).update(f"voice: {self._voice}")
        self.query_one("#cleaner-text", Static).update(f"cleaner: {self._cleaner_model}")
        self.query_one("#quantization-text", Static).update(f"quantization: {self._tts_quantization}")
        self.query_one("#speed-text", Static).update(f"speed: {self._speed:.2f}")

    def _log(self, message: str) -> None:
        self._messages.append(message)
        log = self.query_one("#log-view", RichLog)
        log.write(message)

    @staticmethod
    def _safe_title(value: str) -> str:
        return "".join(char if char.isalnum() or char in " -_" else "_" for char in value)

    def _derive_output_path(self, book: dict) -> Optional[Path]:
        safe_title = self._safe_title(book["title"])
        output_dir = self.controller.config.output_dir / safe_title
        m4b_path = output_dir / f"{safe_title}.m4b"
        if m4b_path.exists():
            return m4b_path

        for chapter in book.get("chapters", []):
            mp3 = chapter.get("mp3_path")
            if mp3:
                mp3_path = Path(mp3)
                if mp3_path.exists():
                    return mp3_path

        return None

    def _show_library_detail(self, index: int) -> None:
        if index < 0 or index >= len(self._book_ids_by_index):
            self._selected_book_id = None
            self._selected_output_path = None
            self.query_one("#library-detail", Static).update("No converted books yet.")
            return

        book_id = self._book_ids_by_index[index]
        details = self.controller.get_book(book_id)
        if details is None:
            self._selected_book_id = None
            self._selected_output_path = None
            self.query_one("#library-detail", Static).update("Selected book no longer exists.")
            return

        self._selected_book_id = book_id
        self._selected_output_path = self._derive_output_path(details)

        output_text = str(self._selected_output_path) if self._selected_output_path else "not found"
        author = details.get("author") or "unknown"
        detail = (
            f"title: {details['title']}\n"
            f"author: {author}\n"
            f"chapters: {len(details.get('chapters', []))}\n"
            f"source: {details['source_path']}\n"
            f"output: {output_text}"
        )
        self.query_one("#library-detail", Static).update(detail)

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
            if event.state.value in {"completed", "failed", "cancelled"}:
                self.action_open_library()

    def _make_callbacks(self) -> ConversionCallbacks:
        def on_event(event: AppEvent) -> None:
            # Background thread callback -> marshal onto UI thread.
            self.call_from_thread(self._emit_event, event)

        return ConversionCallbacks(on_event=on_event)

    def action_new_conversion(self) -> None:
        modal = NewConversionModal(
            initial=LaunchOptions(
                source=self._source,
                voice=self._voice,
                speed=self._speed,
                title=self._title,
                author=self._author,
                tts_engine=self._tts_engine,
                tts_quantization=self._tts_quantization,
                cleaner_model=self._cleaner_model,
            ),
            tts_engines=list(self._tts_engines.values()),
            cleaner_models=self._cleaner_models,
            voices_by_engine=self._voices_by_engine,
        )
        self.push_screen(modal, self._on_new_conversion_result)

    def _on_new_conversion_result(self, result: Optional[ConversionRequest]) -> None:
        if result is None:
            self._log("new conversion canceled")
            return

        self._source = result.source
        self._voice = result.voice
        self._speed = result.speed
        self._title = result.title
        self._author = result.author
        self._tts_engine = result.tts_engine
        self._tts_quantization = result.tts_quantization
        self._cleaner_model = result.cleaner_model
        self._refresh_selection_panel()
        self.action_start_conversion()

    def action_open_library(self) -> None:
        books = self.controller.get_library_books(limit=50)
        library_list = self.query_one("#library-list", OptionList)
        library_list.clear_options()
        self._book_ids_by_index = []

        if not books:
            self._show_library_detail(-1)
            self._log("library refreshed: no books")
            return

        options: list[str] = []
        for book in books:
            author = book.author or "unknown"
            options.append(
                f"[{book.id}] {book.title} by {author} ({book.completed_chapters}/{book.total_chapters})"
            )
            self._book_ids_by_index.append(book.id)

        library_list.add_options(options)
        library_list.highlighted = 0
        self._show_library_detail(0)
        self._log(f"library refreshed: {len(books)} book(s)")

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
        if self._source is None:
            self._log("no source selected; press 'n' to create a new conversion")
            return

        source = self._source
        if not source.exists():
            self._log(f"source not found: {source}")
            return

        if source.suffix.lower() not in SUPPORTED_SOURCE_SUFFIXES:
            suffixes = ", ".join(sorted(SUPPORTED_SOURCE_SUFFIXES))
            self._log(f"unsupported source type {source.suffix}; expected {suffixes}")
            return

        if self._tts_engine not in self._conversion_supported_engines:
            self._log(f"tts engine '{self._tts_engine}' not supported for conversion")
            return

        try:
            job = self.controller.start_conversion(
                source_path=source,
                voice=self._voice,
                speed=self._speed,
                title=self._title,
                author=self._author,
                tts_engine=self._tts_engine,
                tts_quantization=self._tts_quantization,
                cleaner_model=self._cleaner_model,
                callbacks=self._make_callbacks(),
            )
            self.query_one("#job-text", Static).update(f"job: {job.id}")
            self.query_one("#state-text", Static).update("state: running")
            self.query_one("#stage-text", Static).update("stage: starting")
            self._log(
                "started conversion: "
                f"job={job.id} engine={self._tts_engine} voice={self._voice} "
                f"cleaner={self._cleaner_model} quant={self._tts_quantization}"
            )
        except Exception as exc:
            self._log(f"failed to start conversion: {exc}")

    def action_cancel_conversion(self) -> None:
        cancelled = self.controller.cancel_conversion()
        if cancelled:
            self._log("cancel requested")
            self.query_one("#state-text", Static).update("state: cancelled")
        else:
            self._log("no active conversion to cancel")

    def action_open_selected_output(self) -> None:
        if self._selected_output_path is None:
            self._log("no output selected in library")
            return

        target = self._selected_output_path
        if not target.exists():
            self._log(f"output path not found: {target}")
            return

        try:
            if sys.platform == "darwin":
                subprocess.Popen(["open", str(target)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif os.name == "nt":
                os.startfile(str(target))  # type: ignore[attr-defined]
            else:
                subprocess.Popen(["xdg-open", str(target)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self._log(f"opened output: {target}")
        except Exception as exc:
            self._log(f"failed to open output: {exc}")

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_list.id != "library-list":
            return
        self._show_library_detail(event.index)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "new":
            self.action_new_conversion()
        elif event.button.id == "library":
            self.action_open_library()
        elif event.button.id == "start":
            self.action_start_conversion()
        elif event.button.id == "cancel":
            self.action_cancel_conversion()
        elif event.button.id == "refresh":
            self.action_refresh_status()
            self.action_open_library()
        elif event.button.id == "open-output":
            self.action_open_selected_output()

    def on_unmount(self) -> None:
        self.controller.cleanup()
