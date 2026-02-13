"""
Conversion modal screen and related request models.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import unquote, urlparse

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, DirectoryTree, Input, Select, Static

from modules.tui.styles import CONVERT_MODAL_CSS


SUPPORTED_SOURCE_SUFFIXES = {".pdf", ".epub"}
TTS_QUANTIZATION_CHOICES = ["bf16", "8bit", "6bit", "4bit"]
UNAVAILABLE_SELECT_VALUE = "__unavailable__"


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

    CSS = CONVERT_MODAL_CSS

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
        if not engine_options:
            engine_options = [("No TTS engines available", UNAVAILABLE_SELECT_VALUE)]
            default_engine = UNAVAILABLE_SELECT_VALUE
        else:
            default_engine = self.initial.tts_engine
            if not any(value == default_engine for _, value in engine_options):
                default_engine = engine_options[0][1]

        voice_options = self._voice_options(default_engine)
        if not voice_options:
            voice_options = [("No voices available", UNAVAILABLE_SELECT_VALUE)]
        default_voice = self.initial.voice
        if not any(value == default_voice for _, value in voice_options):
            default_voice = voice_options[0][1]

        cleaner_options = [(model, model) for model in self.cleaner_models]
        if not cleaner_options:
            cleaner_options = [("No cleaner models available", UNAVAILABLE_SELECT_VALUE)]
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
            options = [("No voices available", UNAVAILABLE_SELECT_VALUE)]
        voice_select.set_options(options)

        option_values = {value for _, value in options}
        selected_voice = preferred_voice if preferred_voice in option_values else options[0][1]
        voice_select.value = selected_voice

    def _update_engine_help(self, engine_name: str) -> None:
        help_widget = self.query_one("#modal-help", Static)
        if not self.conversion_supported_engines:
            help_widget.update(
                "No conversion-ready TTS engines detected. Install/enable Kokoro and retry."
            )
            return
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
        value = raw.strip()
        if len(value) >= 2 and value.startswith("(") and value.endswith(")"):
            value = value[1:-1]
        value = value.strip().strip("'").strip('"')
        value = value.replace("\\ ", " ")

        if value.startswith("file://"):
            parsed = urlparse(value)
            value = unquote(parsed.path)

        return value

    @staticmethod
    def _default_tree_root() -> Path:
        # Start in the user's home folder; root-level navigation is too noisy for most runs.
        return Path.home()

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

        if not self.conversion_supported_engines:
            self._set_error("No conversion-ready TTS engines available.")
            return

        tts_engine = str(self.query_one("#tts-engine-select", Select).value)
        if tts_engine not in self.conversion_supported_engines:
            self._set_error(
                f"TTS engine '{tts_engine}' is not available for conversion yet. Use kokoro."
            )
            return

        voice = str(self.query_one("#voice-select", Select).value)
        if voice == UNAVAILABLE_SELECT_VALUE:
            self._set_error("No voice available for the selected engine.")
            return

        cleaner_model = str(self.query_one("#cleaner-model-select", Select).value)
        if cleaner_model == UNAVAILABLE_SELECT_VALUE:
            self._set_error("No cleaner model available.")
            return

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
