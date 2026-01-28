#!/usr/bin/env python3
"""
Test Runner
===========
Unified test runner for all audiobook-creator tests.
Run with: python run_tests.py
"""

import sys
import subprocess
import time
from pathlib import Path

# Test modules to run (in order)
TEST_MODULES = [
    "tests/test_pdf_parser.py",
    "tests/test_epub_parser.py", 
    "tests/test_database.py",
    "tests/test_cleaner.py",
]

def run_test(test_path: str) -> tuple[bool, float]:
    """
    Run a single test module.
    
    Returns:
        Tuple of (passed, duration_seconds)
    """
    start = time.time()
    result = subprocess.run(
        [sys.executable, test_path],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent
    )
    duration = time.time() - start
    
    passed = result.returncode == 0
    
    if not passed:
        print(f"\n{'='*50}")
        print(f"FAILED: {test_path}")
        print(f"{'='*50}")
        print(result.stdout)
        print(result.stderr)
    
    return passed, duration


def main():
    """Run all tests and report results."""
    print("\n" + "="*60)
    print("   AUDIOBOOK CREATOR - TEST SUITE")
    print("="*60 + "\n")
    
    results = []
    total_start = time.time()
    
    for test_path in TEST_MODULES:
        if not Path(test_path).exists():
            print(f"⚠ SKIP: {test_path} (not found)")
            continue
            
        print(f"▸ Running {test_path}...", end=" ", flush=True)
        passed, duration = run_test(test_path)
        
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status} ({duration:.1f}s)")
        
        results.append((test_path, passed, duration))
    
    total_duration = time.time() - total_start
    
    # Summary
    print("\n" + "="*60)
    print("   RESULTS SUMMARY")
    print("="*60)
    
    passed_count = sum(1 for _, p, _ in results if p)
    failed_count = len(results) - passed_count
    
    for test_path, passed, duration in results:
        status = "✓" if passed else "✗"
        name = Path(test_path).stem
        print(f"  {status} {name}: {duration:.1f}s")
    
    print(f"\n  Total: {passed_count} passed, {failed_count} failed")
    print(f"  Duration: {total_duration:.1f}s")
    print("="*60 + "\n")
    
    # Exit code
    if failed_count > 0:
        print("❌ TESTS FAILED - Do not commit!")
        return 1
    else:
        print("✅ ALL TESTS PASSED - Safe to commit")
        return 0


if __name__ == "__main__":
    sys.exit(main())
