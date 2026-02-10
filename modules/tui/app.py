"""
Textual TUI App
===============
Guided terminal workflow for conversion status, progress, logs, and library browsing.
"""

from __future__ import annotations

import os
import subprocess
import sys
from urllib.parse import unquote, urlparse
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    DirectoryTree,
    Footer,
    Header,
    Input,
    OptionList,
    ProgressBar,
    RichLog,
    Select,
    Static,
)

from modules.app import AppController, ConversionCallbacks
from modules.app.events import AppEvent, EventType

SUPPORTED_SOURCE_SUFFIXES = {".pdf", ".epub"}
TTS_QUANTIZATION_CHOICES = ["bf16", "8bit", "6bit", "4bit"]


@dataclass
class LaunchOptions:
    source: Optional[Path] = None
    voice: str = "am_adam"
    speed: float = 1.0
    title: Optional[str] = None
    author: Optional[str] = None
    tts_engine: str = "kokoro"
    tts_quantization: str = "bf16"
    cleaner_model: str = "mlx-community/Llama-3.2-3B-Instruct-4bit"


@dataclass
class ConversionRequest:
    source: Path
    voice: str
    speed: float
    title: Optional[str]
    author: Optional[str]
    tts_engine: str
    tts_quantization: str
    cleaner_model: str


class NewConversionModal(ModalScreen[Optional[ConversionRequest]]):
    """Modal to select source file and model options before starting conversion."""

    BINDINGS = [
        ("enter", "submit", "Start"),
        ("escape", "cancel_modal", "Cancel"),
    ]

    CSS = """
    NewConversionModal {
        align: center middle;
    }
    #modal-root {
        width: 96;
        height: 95%;
        border: solid #e9d7b8;
        background: #171717;
        padding: 1 2;
        layout: vertical;
    }
    #modal-content {
        height: 1fr;
        overflow-y: auto;
    }
    #modal-title {
        color: #f7b267;
        text-style: bold;
        margin-bottom: 1;
    }
    #modal-help {
        color: #d8d2c7;
        margin-bottom: 1;
    }
    #source-tree {
        height: 14;
        border: round #e9d7b8;
        margin-bottom: 1;
    }
    .field {
        margin-bottom: 1;
    }
    #modal-error {
        color: #ff8a80;
        margin-top: 1;
        height: 2;
    }
    #modal-actions {
        dock: bottom;
        margin-top: 1;
        height: auto;
    }
    Button {
        margin-right: 1;
    }
    """

    def __init__(
        self,
        *,
        initial: LaunchOptions,
        tts_engines: list[dict],
        cleaner_models: list[str],
        voices_by_engine: dict[str, list[dict]],
    ) -> None:
        super().__init__()
        self.initial = initial
        self.tts_engines = tts_engines
        self.cleaner_models = cleaner_models
        self.voices_by_engine = voices_by_engine
        self.conversion_supported_engines = {
            engine["id"]
            for engine in tts_engines
            if engine.get("available_for_conversion", False)
        }

    def _engine_options(self) -> list[tuple[str, str]]:
        options: list[tuple[str, str]] = []
        for engine in self.tts_engines:
            suffix = "" if engine.get("available_for_conversion") else " (coming soon)"
            options.append((f"{engine['display_name']} [{engine['id']}]" + suffix, engine["id"]))
        return options

    def _voice_options(self, engine_name: str) -> list[tuple[str, str]]:
        voices = self.voices_by_engine.get(engine_name, [])
        options = []
        for voice in voices:
            label = f"{voice['id']} - {voice['name']} ({voice['language']})"
            options.append((label, voice["id"]))
        return options

    def compose(self) -> ComposeResult:
        engine_options = self._engine_options()
        default_engine = self.initial.tts_engine
        if not any(value == default_engine for _, value in engine_options):
            default_engine = engine_options[0][1] if engine_options else "kokoro"

        voice_options = self._voice_options(default_engine)
        default_voice = self.initial.voice
        if not any(value == default_voice for _, value in voice_options):
            default_voice = voice_options[0][1] if voice_options else "am_adam"

        cleaner_options = [(model, model) for model in self.cleaner_models]
        quantization_options = [(value, value) for value in TTS_QUANTIZATION_CHOICES]

        default_cleaner = self.initial.cleaner_model
        if not any(value == default_cleaner for _, value in cleaner_options):
            default_cleaner = cleaner_options[0][1]

        default_quantization = self.initial.tts_quantization
        if not any(value == default_quantization for _, value in quantization_options):
            default_quantization = quantization_options[0][1]

        with Container(id="modal-root"):
            with VerticalScroll(id="modal-content"):
                yield Static("Create New Audiobook", id="modal-title")
                yield Static(
                    "Select a source file and conversion settings. Choose a file from the tree or paste a path.",
                    id="modal-help",
                )
                yield Input(
                    value=str(self.initial.source) if self.initial.source else "",
                    placeholder="/path/to/book.pdf or /path/to/book.epub",
                    id="source-input",
                    classes="field",
                )
                yield DirectoryTree(str(self._default_tree_root()), id="source-tree")
                yield Select(
                    engine_options,
                    value=default_engine,
                    allow_blank=False,
                    prompt="TTS Engine",
                    id="tts-engine-select",
                    classes="field",
                )
                yield Select(
                    voice_options,
                    value=default_voice,
                    allow_blank=False,
                    prompt="Voice",
                    id="voice-select",
                    classes="field",
                )
                yield Select(
                    cleaner_options,
                    value=default_cleaner,
                    allow_blank=False,
                    prompt="Text Cleaner Model",
                    id="cleaner-model-select",
                    classes="field",
                )
                yield Select(
                    quantization_options,
                    value=default_quantization,
                    allow_blank=False,
                    prompt="TTS Quantization",
                    id="tts-quantization-select",
                    classes="field",
                )
                yield Input(
                    value=f"{self.initial.speed:.2f}",
                    placeholder="Speech speed (0.5 - 2.0)",
                    type="number",
                    id="speed-input",
                    classes="field",
                )
                yield Input(
                    value=self.initial.title or "",
                    placeholder="Optional title override",
                    id="title-input",
                    classes="field",
                )
                yield Input(
                    value=self.initial.author or "",
                    placeholder="Optional author override",
                    id="author-input",
                    classes="field",
                )
                yield Static("Enter=start, Esc=cancel", classes="field")
                yield Static("", id="modal-error")
            with Horizontal(id="modal-actions"):
                yield Button("Start Conversion", id="confirm", classes="-primary")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        engine_select = self.query_one("#tts-engine-select", Select)
        self._sync_voice_options(str(engine_select.value), preferred_voice=self.initial.voice)
        self._update_engine_help(str(engine_select.value))

    def _sync_voice_options(self, engine_name: str, preferred_voice: Optional[str] = None) -> None:
        voice_select = self.query_one("#voice-select", Select)
        options = self._voice_options(engine_name)
        if not options:
            options = [("No voices available", "")]
        voice_select.set_options(options)

        option_values = {value for _, value in options}
        selected_voice = preferred_voice if preferred_voice in option_values else options[0][1]
        voice_select.value = selected_voice

    def _update_engine_help(self, engine_name: str) -> None:
        help_widget = self.query_one("#modal-help", Static)
        if engine_name in self.conversion_supported_engines:
            help_widget.update(
                "Select a source file and conversion settings. Choose a file from the tree or paste a path."
            )
            return
        help_widget.update(
            "Selected TTS engine is not conversion-ready yet. Switch to a supported engine (currently kokoro)."
        )

    def _set_error(self, message: str) -> None:
        self.query_one("#modal-error", Static).update(message)

    def _parse_speed(self) -> Optional[float]:
        raw = self.query_one("#speed-input", Input).value.strip()
        try:
            speed = float(raw)
        except ValueError:
            self._set_error("Speed must be a number between 0.5 and 2.0.")
            return None

        if speed < 0.5 or speed > 2.0:
            self._set_error("Speed must be between 0.5 and 2.0.")
            return None
        return speed

    @staticmethod
    def _normalize_source_input(raw: str) -> str:
        # Accept pasted paths from shell/Finder:
        # - quoted path
        # - path wrapped in parentheses
        # - file:// URI
        # - escaped spaces from shell copy
        value = raw.strip().rstrip(")")
        if value.startswith("("):
            value = value[1:]
        value = value.strip().strip("'").strip('"')
        value = value.replace("\\ ", " ")

        if value.startswith("file://"):
            parsed = urlparse(value)
            value = unquote(parsed.path)

        return value

    def _validate_source(self) -> Optional[Path]:
        raw = self.query_one("#source-input", Input).value
        if not raw:
            self._set_error("Please select a source file.")
            return None

        normalized = self._normalize_source_input(raw)
        source = Path(normalized).expanduser().resolve()
        if not source.exists():
            self._set_error(f"Source path not found: {source}")
            return None

        if source.is_dir():
            self._set_error(f"Selected path is a folder, not a file: {source}")
            return None

        if not source.is_file():
            self._set_error(f"Selected path is not a file: {source}")
            return None

        if source.suffix.lower() not in SUPPORTED_SOURCE_SUFFIXES:
            suffixes = ", ".join(sorted(SUPPORTED_SOURCE_SUFFIXES))
            self._set_error(f"Unsupported source type: {source.suffix}. Use one of: {suffixes}")
            return None

        return source

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        source = event.path
        if source.suffix.lower() not in SUPPORTED_SOURCE_SUFFIXES:
            self._set_error("Select a PDF or EPUB source file.")
            return

        self.query_one("#source-input", Input).value = str(source)
        self._set_error("")

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "tts-engine-select":
            engine_name = str(event.value)
            self._sync_voice_options(engine_name, preferred_voice=self.initial.voice)
            self._update_engine_help(engine_name)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
            return

        if event.button.id != "confirm":
            return

        self._submit_form()

    def _submit_form(self) -> None:
        source = self._validate_source()
        if source is None:
            return

        speed = self._parse_speed()
        if speed is None:
            return

        tts_engine = str(self.query_one("#tts-engine-select", Select).value)
        if tts_engine not in self.conversion_supported_engines:
            self._set_error(
                f"TTS engine '{tts_engine}' is not available for conversion yet. Use kokoro."
            )
            return

        voice = str(self.query_one("#voice-select", Select).value)
        cleaner_model = str(self.query_one("#cleaner-model-select", Select).value)
        tts_quantization = str(self.query_one("#tts-quantization-select", Select).value)
        title = self.query_one("#title-input", Input).value.strip() or None
        author = self.query_one("#author-input", Input).value.strip() or None

        self.dismiss(
            ConversionRequest(
                source=source,
                voice=voice,
                speed=speed,
                title=title,
                author=author,
                tts_engine=tts_engine,
                tts_quantization=tts_quantization,
                cleaner_model=cleaner_model,
            )
        )

    def action_submit(self) -> None:
        self._submit_form()

    def action_cancel_modal(self) -> None:
        self.dismiss(None)


class AudiobookTUI(App):
    """Brutalist terminal dashboard for guided audiobook conversion."""

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
    #status-pane, #progress-pane, #library-pane, #log-pane {
        border: solid #e9d7b8;
        background: #1d1d1d;
        padding: 1;
        margin-right: 1;
    }
    #status-pane {
        width: 28;
    }
    #progress-pane {
        width: 24;
    }
    #library-pane {
        width: 42;
    }
    #log-pane {
        margin-right: 0;
        width: 1fr;
    }
    #library-list {
        height: 1fr;
        margin-top: 1;
    }
    #library-detail {
        margin-top: 1;
        color: #d8d2c7;
        height: 8;
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
        with Container(id="root"):
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
        yield Footer()

    def on_mount(self) -> None:
        self._load_model_options()
        self._refresh_selection_panel()
        self.action_open_library()
        self._log("ready")

        if self._source:
            self._log(f"auto-starting source from launch option: {self._source}")
            self.action_start_conversion()
        else:
            self._log("choose 'New' to start conversion or browse existing library output")

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
    @staticmethod
    def _default_tree_root() -> Path:
        # Use the system root ("/" on Unix-like systems, drive root on Windows)
        # rather than the current project directory.
        return Path(Path.home().anchor)
