#!/usr/bin/env python3
"""
Project-level CLI launcher.

Usage:
    python audiobook_cli.py <command> [options]
"""

from modules.cli.main import main


if __name__ == "__main__":
    raise SystemExit(main())
