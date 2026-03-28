"""Tests for the BaselineTracker (Welford's online algorithm)."""

from __future__ import annotations

import math
from pathlib import Path

from theaios.agent_monitor.baselines import BaselineTracker


class TestBaselineTracker:
    def test_update_and_get_baseline(self) -> None:
        tracker = BaselineTracker(min_samples=3)
        for val in [10.0, 20.0, 30.0]:
            tracker.update("test-agent", "event_count", val)
        baseline = tracker.get_baseline("test-agent", "event_count")
        assert baseline is not None
        assert baseline.sample_count == 3

    def test_mean_correct_after_n_samples(self) -> None:
        tracker = BaselineTracker(min_samples=1)
        values = [10.0, 20.0, 30.0, 40.0, 50.0]
        for val in values:
            tracker.update("test-agent", "event_count", val)
        baseline = tracker.get_baseline("test-agent", "event_count")
        assert baseline is not None
        expected_mean = sum(values) / len(values)
        assert abs(baseline.mean - expected_mean) < 0.01

    def test_stddev_correct_after_n_samples(self) -> None:
        tracker = BaselineTracker(min_samples=1)
        values = [10.0, 20.0, 30.0, 40.0, 50.0]
        for val in values:
            tracker.update("test-agent", "event_count", val)
        baseline = tracker.get_baseline("test-agent", "event_count")
        assert baseline is not None
        expected_mean = sum(values) / len(values)
        variance = sum((v - expected_mean) ** 2 for v in values) / len(values)
        expected_stddev = math.sqrt(variance)
        assert abs(baseline.stddev - expected_stddev) < 0.01

    def test_z_score_returns_none_below_min_samples(self) -> None:
        tracker = BaselineTracker(min_samples=10)
        for val in [10.0, 20.0, 30.0]:
            tracker.update("test-agent", "event_count", val)
        z = tracker.z_score("test-agent", "event_count", 50.0)
        assert z is None

    def test_z_score_returns_correct_value(self) -> None:
        tracker = BaselineTracker(min_samples=3)
        values = [10.0, 20.0, 30.0, 40.0, 50.0]
        for val in values:
            tracker.update("test-agent", "event_count", val)
        baseline = tracker.get_baseline("test-agent", "event_count")
        assert baseline is not None
        mean = baseline.mean
        stddev = baseline.stddev
        test_value = 80.0
        expected_z = (test_value - mean) / stddev
        z = tracker.z_score("test-agent", "event_count", test_value)
        assert z is not None
        assert abs(z - expected_z) < 0.01

    def test_z_score_zero_stddev(self) -> None:
        tracker = BaselineTracker(min_samples=3)
        for _ in range(5):
            tracker.update("test-agent", "event_count", 10.0)
        # All identical values => stddev=0 => z_score should handle gracefully
        z = tracker.z_score("test-agent", "event_count", 10.0)
        # Either 0.0 or None is acceptable when stddev is zero
        assert z is None or z == 0.0

    def test_save_and_load_persistence(self, tmp_dir: Path) -> None:
        path = tmp_dir / "baselines.json"
        tracker = BaselineTracker(storage_path=str(path), min_samples=3)
        for val in [10.0, 20.0, 30.0, 40.0, 50.0]:
            tracker.update("test-agent", "event_count", val)
        tracker.save()
        assert path.exists()

        tracker2 = BaselineTracker(storage_path=str(path), min_samples=3)
        tracker2.load()
        baseline = tracker2.get_baseline("test-agent", "event_count")
        assert baseline is not None
        assert baseline.sample_count == 5

    def test_multiple_metrics_per_agent(self) -> None:
        tracker = BaselineTracker(min_samples=3)
        for val in [10.0, 20.0, 30.0]:
            tracker.update("test-agent", "event_count", val)
        for val in [100.0, 200.0, 300.0]:
            tracker.update("test-agent", "avg_latency_ms", val)
        ec = tracker.get_baseline("test-agent", "event_count")
        lat = tracker.get_baseline("test-agent", "avg_latency_ms")
        assert ec is not None
        assert lat is not None
        assert ec.mean != lat.mean

    def test_unknown_agent_returns_none(self) -> None:
        tracker = BaselineTracker(min_samples=3)
        baseline = tracker.get_baseline("ghost", "event_count")
        assert baseline is None

    def test_z_score_unknown_agent_returns_none(self) -> None:
        tracker = BaselineTracker(min_samples=3)
        z = tracker.z_score("ghost", "event_count", 50.0)
        assert z is None
