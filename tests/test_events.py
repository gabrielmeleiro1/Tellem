"""
Test App Events Module
======================
Unit tests for typed app event contracts.
"""

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from modules.app.events import (
    EventType,
    JobState,
    make_log_event,
    make_progress_event,
    make_state_event,
)


def test_events() -> bool:
    print("\n" + "=" * 50)
    print("APP EVENTS TEST SUITE")
    print("=" * 50 + "\n")

    # Progress event clamp and fields
    progress = make_progress_event(stage="synthesizing", progress=1.7, message="chunk done")
    assert progress.event_type == EventType.PROGRESS
    assert progress.progress == 1.0
    assert progress.stage == "synthesizing"
    assert progress.message == "chunk done"
    print("✓ progress event normalization")

    # Log event level normalization
    log = make_log_event("model loaded", "INFO")
    assert log.event_type == EventType.LOG
    assert log.level == "info"
    assert log.message == "model loaded"
    print("✓ log event normalization")

    # State event creation
    state = make_state_event(JobState.RUNNING, "conv_123", "started")
    assert state.event_type == EventType.STATE
    assert state.state == JobState.RUNNING
    assert state.job_id == "conv_123"
    assert state.message == "started"
    print("✓ state event creation")

    print("\n" + "=" * 50)
    print("ALL APP EVENT TESTS PASSED ✓")
    print("=" * 50 + "\n")
    return True


if __name__ == "__main__":
    success = test_events()
    sys.exit(0 if success else 1)
