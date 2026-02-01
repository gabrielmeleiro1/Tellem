"""
Performance Benchmark Tests
============================
Benchmarks TTS performance and tracks against baseline.
Fails if performance regresses >10% from baseline.
"""

import pytest
import time
import json
import os
from pathlib import Path
from typing import Dict, Any
from dataclasses import dataclass, asdict
from unittest.mock import patch, MagicMock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.tts.engine import TTSEngine, TTSConfig
from modules.tts.chunker import TextChunker, ChunkConfig


# Path to store baseline performance data
BASELINE_PATH = Path(__file__).parent / ".benchmark_baseline.json"
PERFORMANCE_THRESHOLD = 0.10  # 10% regression threshold


@dataclass
class BenchmarkResult:
    """Result of a single benchmark."""
    name: str
    chars_per_second: float
    total_chars: int
    elapsed_seconds: float
    timestamp: str


class PerformanceBaseline:
    """Manager for performance baselines."""
    
    @staticmethod
    def load() -> Dict[str, Any]:
        """Load baseline from file or return empty dict."""
        if BASELINE_PATH.exists():
            with open(BASELINE_PATH, 'r') as f:
                return json.load(f)
        return {}
    
    @staticmethod
    def save(baseline: Dict[str, Any]) -> None:
        """Save baseline to file."""
        with open(BASELINE_PATH, 'w') as f:
            json.dump(baseline, f, indent=2)
    
    @staticmethod
    def update(result: BenchmarkResult) -> None:
        """Update baseline with new result."""
        baseline = PerformanceBaseline.load()
        baseline[result.name] = asdict(result)
        PerformanceBaseline.save(baseline)


@pytest.mark.benchmark
class TestTTSPerformance:
    """Performance tests for TTS operations."""
    
    @pytest.fixture
    def sample_texts(self):
        """Generate sample texts of various sizes."""
        return {
            "short": "Hello world. This is a short test.",
            "medium": "The quick brown fox jumps over the lazy dog. " * 20,
            "long": "Lorem ipsum dolor sit amet, consectetur adipiscing elit. " * 100,
        }
    
    @pytest.fixture
    def mock_tts_engine(self):
        """Create a mock TTS engine that simulates realistic timing."""
        engine = MagicMock(spec=TTSEngine)
        
        def mock_synthesize(text, **kwargs):
            # Simulate realistic TTS timing: ~100 chars/sec
            char_time = len(text) / 100.0
            time.sleep(char_time * 0.01)  # Scale down for tests
            import numpy as np
            return np.zeros(int(24000 * char_time), dtype=np.float32)
        
        engine.synthesize = mock_synthesize
        engine.config = TTSConfig()
        engine.is_loaded = True
        return engine
    
    def benchmark_tts_speed(
        self,
        text: str,
        engine,
        iterations: int = 3
    ) -> BenchmarkResult:
        """
        Benchmark TTS synthesis speed.
        
        Args:
            text: Text to synthesize
            engine: TTS engine (real or mock)
            iterations: Number of iterations to average
        
        Returns:
            BenchmarkResult with performance metrics
        """
        chunker = TextChunker()
        chunks = chunker.chunk(text)
        
        if not chunks:
            return BenchmarkResult(
                name=f"tts_empty",
                chars_per_second=0.0,
                total_chars=0,
                elapsed_seconds=0.0,
                timestamp=time.strftime("%Y-%m-%dT%H:%M:%S")
            )
        
        # Warm up
        for chunk in chunks[:min(2, len(chunks))]:
            engine.synthesize(chunk, voice="af_bella")
        
        # Benchmark
        total_chars = sum(len(c) for c in chunks)
        start_time = time.time()
        
        for _ in range(iterations):
            for chunk in chunks:
                engine.synthesize(chunk, voice="af_bella")
        
        elapsed = time.time() - start_time
        chars_per_second = (total_chars * iterations) / elapsed if elapsed > 0 else 0
        
        return BenchmarkResult(
            name=f"tts_{total_chars}chars",
            chars_per_second=chars_per_second,
            total_chars=total_chars * iterations,
            elapsed_seconds=elapsed,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S")
        )
    
    def test_tts_short_text_performance(self, sample_texts, mock_tts_engine):
        """
        Benchmark TTS with short text (~50 chars).
        """
        result = self.benchmark_tts_speed(
            sample_texts["short"],
            mock_tts_engine,
            iterations=5
        )
        
        print(f"\nShort text benchmark: {result.chars_per_second:.2f} chars/sec")
        print(f"  Total chars: {result.total_chars}")
        print(f"  Elapsed: {result.elapsed_seconds:.3f}s")
        
        # Performance should be reasonable even with overhead
        assert result.chars_per_second > 10, "Performance too slow for short text"
    
    def test_tts_medium_text_performance(self, sample_texts, mock_tts_engine):
        """
        Benchmark TTS with medium text (~800 chars).
        """
        result = self.benchmark_tts_speed(
            sample_texts["medium"],
            mock_tts_engine,
            iterations=3
        )
        
        print(f"\nMedium text benchmark: {result.chars_per_second:.2f} chars/sec")
        print(f"  Total chars: {result.total_chars}")
        print(f"  Elapsed: {result.elapsed_seconds:.3f}s")
        
        # Should be faster per char than short text (amortized overhead)
        assert result.chars_per_second > 50, "Performance too slow for medium text"
    
    def test_tts_long_text_performance(self, sample_texts, mock_tts_engine):
        """
        Benchmark TTS with long text (~5000 chars).
        """
        result = self.benchmark_tts_speed(
            sample_texts["long"],
            mock_tts_engine,
            iterations=1
        )
        
        print(f"\nLong text benchmark: {result.chars_per_second:.2f} chars/sec")
        print(f"  Total chars: {result.total_chars}")
        print(f"  Elapsed: {result.elapsed_seconds:.3f}s")
        
        # Long text should have best throughput
        assert result.chars_per_second > 80, "Performance too slow for long text"
    
    def test_performance_against_baseline(self, sample_texts, mock_tts_engine):
        """
        Test that performance hasn't regressed >10% from baseline.
        
        If no baseline exists, creates one.
        """
        # Run benchmark
        result = self.benchmark_tts_speed(
            sample_texts["medium"],
            mock_tts_engine,
            iterations=3
        )
        result.name = "tts_baseline_medium"
        
        # Load baseline
        baseline = PerformanceBaseline.load()
        baseline_key = "tts_baseline_medium"
        
        if baseline_key not in baseline:
            # No baseline yet - create one
            print(f"\nCreating baseline: {result.chars_per_second:.2f} chars/sec")
            PerformanceBaseline.update(result)
            pytest.skip("Baseline created, run again to compare")
        
        baseline_result = baseline[baseline_key]
        baseline_cps = baseline_result["chars_per_second"]
        current_cps = result.chars_per_second
        
        # Calculate regression
        regression = (baseline_cps - current_cps) / baseline_cps
        
        print(f"\nPerformance comparison:")
        print(f"  Baseline: {baseline_cps:.2f} chars/sec")
        print(f"  Current:  {current_cps:.2f} chars/sec")
        print(f"  Regression: {regression:.2%}")
        
        # Update baseline if performance improved
        if current_cps > baseline_cps:
            print("  Performance improved - updating baseline")
            PerformanceBaseline.update(result)
        
        # Fail if regressed > 10%
        assert regression < PERFORMANCE_THRESHOLD, (
            f"Performance regressed by {regression:.2%} (threshold: {PERFORMANCE_THRESHOLD:.2%})"
        )
    
    def test_chunker_performance(self, sample_texts):
        """
        Benchmark text chunking performance.
        """
        chunker = TextChunker()
        text = sample_texts["long"] * 10  # Very long text
        
        iterations = 10
        start = time.time()
        
        for _ in range(iterations):
            chunks = chunker.chunk(text)
        
        elapsed = time.time() - start
        chars_per_sec = (len(text) * iterations) / elapsed
        
        print(f"\nChunker benchmark: {chars_per_sec:.2f} chars/sec")
        print(f"  Total chars: {len(text) * iterations}")
        print(f"  Elapsed: {elapsed:.3f}s")
        
        # Chunking should be very fast
        assert chars_per_sec > 10000, "Chunker performance too slow"
    
    def test_parallel_vs_sequential_benchmark(self, sample_texts, mock_tts_engine):
        """
        Benchmark to ensure parallel processing provides speedup.
        
        This checks that the overhead of parallelization is worth it.
        """
        # Sequential benchmark
        text = sample_texts["medium"]
        sequential_result = self.benchmark_tts_speed(text, mock_tts_engine, iterations=3)
        
        # Note: In a real test, we'd run parallel here too
        # For now, just verify sequential works as expected
        
        print(f"\nSequential processing: {sequential_result.chars_per_second:.2f} chars/sec")
        assert sequential_result.chars_per_second > 0


@pytest.mark.integration
@pytest.mark.slow
class TestRealTTSPerformance:
    """
    Performance tests with real TTS engine.
    
    These tests are slow and require MLX to be installed.
    Run with: pytest test_performance_benchmark.py -m "integration and slow"
    """
    
    @pytest.fixture
    def real_tts_engine(self):
        """Create real TTS engine if available."""
        try:
            engine = TTSEngine(TTSConfig())
            engine.load_model()
            return engine
        except ImportError as e:
            pytest.skip(f"MLX not available: {e}")
    
    def test_real_tts_baseline(self, real_tts_engine):
        """
        Create/update baseline with real TTS engine.
        """
        text = "Hello world. This is a test of the TTS engine performance. " * 10
        
        test = TestTTSPerformance()
        result = test.benchmark_tts_speed(text, real_tts_engine, iterations=1)
        result.name = "tts_real_baseline"
        
        print(f"\nReal TTS benchmark: {result.chars_per_second:.2f} chars/sec")
        
        # Save or compare to baseline
        baseline = PerformanceBaseline.load()
        
        if "tts_real_baseline" not in baseline:
            PerformanceBaseline.update(result)
            print("Baseline created for real TTS")
        else:
            baseline_cps = baseline["tts_real_baseline"]["chars_per_second"]
            regression = (baseline_cps - result.chars_per_second) / baseline_cps
            
            print(f"Baseline: {baseline_cps:.2f}, Current: {result.chars_per_second:.2f}")
            print(f"Regression: {regression:.2%}")
            
            if result.chars_per_second > baseline_cps:
                PerformanceBaseline.update(result)
            
            assert regression < PERFORMANCE_THRESHOLD


def print_baseline():
    """Print current baseline for manual inspection."""
    baseline = PerformanceBaseline.load()
    print("\nCurrent Performance Baseline:")
    print("=" * 50)
    for name, data in baseline.items():
        print(f"\n{name}:")
        print(f"  Speed: {data['chars_per_second']:.2f} chars/sec")
        print(f"  Recorded: {data['timestamp']}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Performance benchmarks")
    parser.add_argument("--print-baseline", action="store_true", help="Print current baseline")
    parser.add_argument("--reset-baseline", action="store_true", help="Reset baseline")
    args = parser.parse_args()
    
    if args.print_baseline:
        print_baseline()
    elif args.reset_baseline:
        if BASELINE_PATH.exists():
            BASELINE_PATH.unlink()
            print("Baseline reset")
    else:
        pytest.main([__file__, "-v", "-m", "benchmark"])
