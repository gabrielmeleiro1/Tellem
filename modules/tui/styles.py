"""
Centralized Textual CSS for the terminal UI.
"""

from modules.tui.theme import (
    BLACK,
    CHARCOAL_GRAY,
    CORAL_PINK,
    DARK_GRAY,
    OFF_WHITE,
    ORANGE,
    TEAL_GREEN,
)


APP_CSS = """
Screen {
    background: %(BLACK)s;
    color: %(OFF_WHITE)s;
}
#root {
    height: 1fr;
    layout: vertical;
    background: %(DARK_GRAY)s;
}
#actions {
    height: auto;
    border: heavy %(ORANGE)s;
    margin: 1 1 0 1;
    padding: 1;
    background: %(CHARCOAL_GRAY)s;
}
#panes {
    height: 1fr;
    margin: 0 1 1 1;
}
#status-pane, #progress-pane, #library-pane, #log-pane {
    border: solid %(ORANGE)s;
    background: %(CHARCOAL_GRAY)s;
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
    color: %(OFF_WHITE)s;
    height: 8;
}
#progress-text, #stage-text {
    color: %(TEAL_GREEN)s;
}
.label {
    color: %(ORANGE)s;
    text-style: bold;
}
Button {
    background: %(BLACK)s;
    color: %(OFF_WHITE)s;
    border: solid %(ORANGE)s;
    margin-right: 1;
}
Button.-primary {
    color: %(BLACK)s;
    background: %(ORANGE)s;
}
Button#cancel {
    border: solid %(CORAL_PINK)s;
    color: %(CORAL_PINK)s;
}
""" % {
    "BLACK": BLACK,
    "DARK_GRAY": DARK_GRAY,
    "CHARCOAL_GRAY": CHARCOAL_GRAY,
    "ORANGE": ORANGE,
    "TEAL_GREEN": TEAL_GREEN,
    "CORAL_PINK": CORAL_PINK,
    "OFF_WHITE": OFF_WHITE,
}


CONVERT_MODAL_CSS = """
NewConversionModal {
    align: center middle;
    background: %(BLACK)s;
}
#modal-root {
    width: 96;
    height: 95%%;
    border: heavy %(ORANGE)s;
    background: %(CHARCOAL_GRAY)s;
    padding: 1 2;
    layout: vertical;
}
#modal-content {
    height: 1fr;
    overflow-y: auto;
}
#modal-title {
    color: %(ORANGE)s;
    text-style: bold;
    margin-bottom: 1;
}
#modal-help {
    color: %(OFF_WHITE)s;
    margin-bottom: 1;
}
#source-tree {
    height: 14;
    border: round %(ORANGE)s;
    margin-bottom: 1;
}
.field {
    margin-bottom: 1;
}
#modal-error {
    color: %(CORAL_PINK)s;
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
    color: %(OFF_WHITE)s;
    border: solid %(ORANGE)s;
    background: %(BLACK)s;
}
Button.-primary {
    color: %(BLACK)s;
    background: %(ORANGE)s;
}
""" % {
    "BLACK": BLACK,
    "CHARCOAL_GRAY": CHARCOAL_GRAY,
    "CORAL_PINK": CORAL_PINK,
    "OFF_WHITE": OFF_WHITE,
    "ORANGE": ORANGE,
}
