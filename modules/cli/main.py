"""
Audiobook Creator CLI
=====================
Terminal-first command surface for conversion and library operations.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Callable, Optional, TextIO

from modules.app.controller import AppController, ConversionCallbacks, JobStatus


def build_parser() -> argparse.ArgumentParser:
    """Create the root CLI parser."""
    parser = argparse.ArgumentParser(prog="audiobook", description="Audiobook Creator CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # convert
    convert_parser = subparsers.add_parser("convert", help="Convert a PDF/EPUB into audiobook output")
    convert_parser.add_argument("source", help="Path to PDF or EPUB file")
    convert_parser.add_argument("--voice", default="am_adam", help="Voice ID (default: am_adam)")
    convert_parser.add_argument("--speed", type=float, default=1.0, help="Speech speed (default: 1.0)")
    convert_parser.add_argument("--title", help="Override title")
    convert_parser.add_argument("--author", help="Override author")
    convert_parser.set_defaults(handler=handle_convert)

    # jobs
    jobs_parser = subparsers.add_parser("jobs", help="List active and recent processing jobs")
    jobs_parser.add_argument("--limit", type=int, default=20, help="History limit (default: 20)")
    jobs_parser.set_defaults(handler=handle_jobs)

    # cancel
    cancel_parser = subparsers.add_parser("cancel", help="Cancel the active conversion job")
    cancel_parser.add_argument("job_id", nargs="?", help="Optional active job ID to verify before cancel")
    cancel_parser.set_defaults(handler=handle_cancel)

    # library
    library_parser = subparsers.add_parser("library", help="Library operations")
    library_subparsers = library_parser.add_subparsers(dest="library_command", required=True)

    library_list_parser = library_subparsers.add_parser("list", help="List books in library")
    library_list_parser.add_argument("--search", help="Filter by title/author text")
    library_list_parser.add_argument("--limit", type=int, default=50, help="Max number of books")
    library_list_parser.add_argument("--offset", type=int, default=0, help="Pagination offset")
    library_list_parser.set_defaults(handler=handle_library_list)

    return parser


def _print(msg: str, out: TextIO) -> None:
    out.write(msg + "\n")
    out.flush()


def handle_convert(args: argparse.Namespace, controller: AppController, out: TextIO) -> int:
    """Run a conversion and stream progress to terminal."""
    source_path = Path(args.source).expanduser().resolve()
    if not source_path.exists():
        _print(f"error: source file not found: {source_path}", out)
        return 1

    state = {"stage": "starting", "progress": 0.0, "message": ""}

    def on_progress(stage: str, progress: float, message: str) -> None:
        state["stage"] = stage
        state["progress"] = max(0.0, min(1.0, progress))
        state["message"] = message or ""

    def on_log(message: str, _msg_type: str) -> None:
        _print(f"log: {message}", out)

    callbacks = ConversionCallbacks(on_progress=on_progress, on_log=on_log)

    try:
        job = controller.start_conversion(
            source_path=source_path,
            voice=args.voice,
            speed=args.speed,
            callbacks=callbacks,
            title=args.title,
            author=args.author,
        )
    except Exception as exc:
        _print(f"error: failed to start conversion: {exc}", out)
        return 1

    _print(f"started job: {job.id}", out)
    _print(f"source: {source_path}", out)
    _print("press Ctrl+C to cancel", out)

    spinner = "|/-\\"
    tick = 0

    try:
        while job.is_active():
            spin = spinner[tick % len(spinner)]
            pct = int(state["progress"] * 100)
            line = f"\r{spin} [{state['stage']}] {pct:3d}% {state['message'][:80]}"
            out.write(line)
            out.flush()
            tick += 1
            time.sleep(0.12)
        job.wait(timeout=1.0)
    except KeyboardInterrupt:
        out.write("\n")
        out.flush()
        cancelled = controller.cancel_conversion()
        _print("cancel requested" if cancelled else "no active conversion to cancel", out)
        return 130

    out.write("\n")
    out.flush()

    if job.status == JobStatus.COMPLETED and job.result and job.result.success:
        _print("conversion completed", out)
        if job.result.output_path:
            _print(f"output: {job.result.output_path}", out)
        return 0

    if job.status == JobStatus.CANCELLED:
        _print("conversion cancelled", out)
        return 130

    error_message = job.error
    if not error_message and job.result and job.result.error_message:
        error_message = job.result.error_message
    _print(f"conversion failed: {error_message or 'unknown error'}", out)
    return 1


def handle_jobs(args: argparse.Namespace, controller: AppController, out: TextIO) -> int:
    """Show active conversion and historical processing jobs."""
    active = controller.get_active_job()
    history = controller.get_processing_history(limit=args.limit)

    if active and active.is_active():
        _print(f"active: {active.id} ({active.status.value})", out)
    else:
        _print("active: none", out)

    _print(f"history (latest {args.limit}):", out)
    if not history:
        _print("  - no recorded jobs", out)
        return 0

    for job in history:
        stage = job.current_stage or "-"
        _print(
            f"  - id={job.id} status={job.status.value} progress={int(job.progress * 100)}% stage={stage}",
            out,
        )
    return 0


def handle_cancel(args: argparse.Namespace, controller: AppController, out: TextIO) -> int:
    """Cancel currently active conversion job."""
    active = controller.get_active_job()
    if active is None or not active.is_active():
        _print("no active conversion job", out)
        return 1

    if args.job_id and args.job_id != active.id:
        _print(f"active job is {active.id}, not {args.job_id}", out)
        return 1

    cancelled = controller.cancel_conversion()
    if cancelled:
        _print(f"cancelled job {active.id}", out)
        return 0

    _print("failed to cancel active conversion job", out)
    return 1


def handle_library_list(args: argparse.Namespace, controller: AppController, out: TextIO) -> int:
    """List library books and summary stats."""
    stats = controller.get_library_stats()
    books = controller.get_library_books(
        search=args.search,
        limit=args.limit,
        offset=args.offset,
    )

    _print(
        (
            "library stats: "
            f"books={stats.get('total_books', 0)} "
            f"chapters={stats.get('total_chapters', 0)} "
            f"duration_ms={stats.get('total_duration_ms', 0)}"
        ),
        out,
    )

    if not books:
        _print("no books found", out)
        return 0

    for book in books:
        author = book.author or "unknown"
        _print(
            f"- [{book.id}] {book.title} by {author} ({book.completed_chapters}/{book.total_chapters} chapters)",
            out,
        )
    return 0


def main(
    argv: Optional[list[str]] = None,
    controller_factory: Callable[[], AppController] = AppController,
    out: TextIO = sys.stdout,
) -> int:
    """
    CLI entrypoint.

    Args:
        argv: Optional argv override for testing.
        controller_factory: Dependency-injection hook for tests.
        out: Output stream.

    Returns:
        Process exit code.
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    controller = controller_factory()

    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help(file=out)
        return 2

    try:
        return int(handler(args, controller, out))
    finally:
        controller.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
