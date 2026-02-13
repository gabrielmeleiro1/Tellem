"""
Home selection screen for first-run centralized flow.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from modules.tui.theme import BLACK, CHARCOAL_GRAY, OFF_WHITE, ORANGE


class HomeScreen(ModalScreen[str]):
    """First-run choice screen: browse library or convert a new book."""

    BINDINGS = [
        ("1", "choose_library", "Library"),
        ("2", "choose_convert", "Convert"),
        ("escape", "choose_library", "Library"),
    ]

    CSS = f"""
    HomeScreen {{
        align: center middle;
        background: {BLACK};
    }}
    #home-root {{
        width: 78;
        height: 24;
        border: heavy {ORANGE};
        background: {CHARCOAL_GRAY};
        padding: 2 3;
    }}
    #home-title {{
        color: {OFF_WHITE};
        text-style: bold;
        margin-bottom: 1;
    }}
    #home-subtitle {{
        color: {ORANGE};
        margin-bottom: 2;
    }}
    Button {{
        width: 1fr;
        margin-bottom: 1;
        background: {BLACK};
        color: {OFF_WHITE};
        border: solid {ORANGE};
    }}
    Button:focus {{
        background: {ORANGE};
        color: {BLACK};
        text-style: bold;
    }}
    #home-help {{
        color: {OFF_WHITE};
        margin-top: 1;
    }}
    """

    def compose(self) -> ComposeResult:
        with Container(id="home-root"):
            with Vertical():
                yield Static("AUDIOBOOK CREATOR", id="home-title")
                yield Static("Select how you want to start", id="home-subtitle")
                yield Button("1. Browse Library", id="home-library", classes="-primary")
                yield Button("2. Convert New Book", id="home-convert", classes="-primary")
                yield Static("Use 1/2 or arrow+enter. Esc defaults to Library.", id="home-help")

    def on_mount(self) -> None:
        self.query_one("#home-library", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "home-library":
            self.dismiss("library")
            return
        if event.button.id == "home-convert":
            self.dismiss("convert")

    def action_choose_library(self) -> None:
        self.dismiss("library")

    def action_choose_convert(self) -> None:
        self.dismiss("convert")

