#!/usr/bin/env python3
"""
Audiobook Creator TUI launcher.

Usage:
    python main.py
    python audiobook_tui.py --source /path/to/book.pdf
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="audiobook-tui", description="Audiobook Creator Textual TUI")
    parser.add_argument("--source", type=Path, help="Optional source PDF/EPUB to start conversion immediately")
    parser.add_argument("--voice", default="am_adam", help="Voice ID (default: am_adam)")
    parser.add_argument("--speed", type=float, default=1.0, help="Speech speed (default: 1.0)")
    parser.add_argument("--title", help="Optional title override")
    parser.add_argument("--author", help="Optional author override")
    parser.add_argument("--tts-engine", default="kokoro", help="TTS engine ID (default: kokoro)")
    parser.add_argument(
        "--tts-quantization",
        default="bf16",
        choices=["bf16", "8bit", "6bit", "4bit"],
        help="TTS quantization model (default: bf16)",
    )
    parser.add_argument(
        "--cleaner-model",
        default="mlx-community/Llama-3.2-3B-Instruct-4bit",
        help="Text cleaner model ID",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        from modules.tui.app import AudiobookTUI, LaunchOptions
    except ImportError:
        print("error: Textual is not installed. Run `pip install textual rich`.", file=sys.stderr)
        return 1

    options = LaunchOptions(
        source=args.source.resolve() if args.source else None,
        voice=args.voice,
        speed=args.speed,
        title=args.title,
        author=args.author,
        tts_engine=args.tts_engine,
        tts_quantization=args.tts_quantization,
        cleaner_model=args.cleaner_model,
    )
    app = AudiobookTUI(options=options)
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
