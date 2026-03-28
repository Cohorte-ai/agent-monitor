"""Tests for the AnomalyDetector."""

from __future__ import annotations

import time

from theaios.agent_monitor.anomaly import AnomalyDetector
from theaios.agent_monitor.baselines import BaselineTracker
from theaios.agent_monitor.types import (
    AnomalyDetectionConfig,
    AnomalyRuleConfig,
    MetricSnapshot,
)


def _normal_values(center: float = 10.0, n: int = 20) -> list[float]:
    """Generate values with small variance for baseline building."""
    return [center + (i % 3 - 1) for i in range(n)]


def _build_tracker(
    agent: str,
    metric: str,
    values: list[float],
    min_samples: int = 3,
) -> BaselineTracker:
    """Helper to build a baseline tracker with known values."""
    tracker = BaselineTracker(min_samples=min_samples)
    for val in values:
        tracker.update(agent, metric, val)
    return tracker


def _make_snapshot(agent: str, **kwargs) -> MetricSnapshot:
    """Helper to build a MetricSnapshot with required fields."""
    return MetricSnapshot(
        agent=agent,
        window_seconds=300,
        timestamp=time.time(),
        **kwargs,
    )


class TestAnomalyDetector:
    def test_triggers_alert_above_threshold(self) -> None:
        tracker = _build_tracker("test-agent", "event_count", _normal_values())
        config = AnomalyDetectionConfig(
            enabled=True,
            rules=[
                AnomalyRuleConfig(
                    name="high-count",
                    metric="event_count",
                    z_threshold=2.0,
                    severity="high",
                    cooldown_seconds=0,
                )
            ],
        )
        detector = AnomalyDetector(config=config, baselines=tracker)
        snap = _make_snapshot("test-agent", event_count=100)
        alerts = detector.check("test-agent", snap)
        assert len(alerts) >= 1
        assert alerts[0].rule == "high-count"

    def test_no_alert_below_threshold(self) -> None:
        tracker = _build_tracker("test-agent", "event_count", _normal_values())
        config = AnomalyDetectionConfig(
            enabled=True,
            rules=[
                AnomalyRuleConfig(
                    name="high-count",
                    metric="event_count",
                    z_threshold=3.0,
                    severity="high",
                    cooldown_seconds=0,
                )
            ],
        )
        detector = AnomalyDetector(config=config, baselines=tracker)
        snap = _make_snapshot("test-agent", event_count=11)
        alerts = detector.check("test-agent", snap)
        assert len(alerts) == 0

    def test_no_alert_when_baseline_not_established(self) -> None:
        tracker = BaselineTracker(min_samples=50)
        # Only 3 samples, min_samples=50 => not enough data
        for val in [10.0, 20.0, 30.0]:
            tracker.update("test-agent", "event_count", val)
        config = AnomalyDetectionConfig(
            enabled=True,
            rules=[
                AnomalyRuleConfig(
                    name="high-count",
                    metric="event_count",
                    z_threshold=2.0,
                    severity="high",
                    cooldown_seconds=0,
                )
            ],
        )
        detector = AnomalyDetector(config=config, baselines=tracker)
        snap = _make_snapshot("test-agent", event_count=1000)
        alerts = detector.check("test-agent", snap)
        assert len(alerts) == 0

    def test_cooldown_prevents_duplicate_alerts(self) -> None:
        tracker = _build_tracker("test-agent", "event_count", _normal_values())
        config = AnomalyDetectionConfig(
            enabled=True,
            rules=[
                AnomalyRuleConfig(
                    name="high-count",
                    metric="event_count",
                    z_threshold=2.0,
                    severity="high",
                    cooldown_seconds=600,
                )
            ],
        )
        detector = AnomalyDetector(config=config, baselines=tracker)
        snap = _make_snapshot("test-agent", event_count=100)
        # First evaluation should trigger
        alerts1 = detector.check("test-agent", snap)
        assert len(alerts1) >= 1
        # Second evaluation within cooldown should not trigger
        alerts2 = detector.check("test-agent", snap)
        assert len(alerts2) == 0

    def test_severity_in_alert(self) -> None:
        tracker = _build_tracker("test-agent", "event_count", _normal_values())
        config = AnomalyDetectionConfig(
            enabled=True,
            rules=[
                AnomalyRuleConfig(
                    name="critical-count",
                    metric="event_count",
                    z_threshold=2.0,
                    severity="critical",
                    cooldown_seconds=0,
                )
            ],
        )
        detector = AnomalyDetector(config=config, baselines=tracker)
        snap = _make_snapshot("test-agent", event_count=100)
        alerts = detector.check("test-agent", snap)
        assert alerts[0].severity == "critical"

    def test_multiple_rules_independent(self) -> None:
        tracker = _build_tracker("test-agent", "event_count", _normal_values())
        for val in _normal_values(0.01):
            tracker.update("test-agent", "cost_per_minute", val)
        config = AnomalyDetectionConfig(
            enabled=True,
            rules=[
                AnomalyRuleConfig(
                    name="high-count",
                    metric="event_count",
                    z_threshold=2.0,
                    severity="high",
                    cooldown_seconds=0,
                ),
                AnomalyRuleConfig(
                    name="cost-spike",
                    metric="cost_per_minute",
                    z_threshold=2.0,
                    severity="critical",
                    cooldown_seconds=0,
                ),
            ],
        )
        detector = AnomalyDetector(config=config, baselines=tracker)
        snap = _make_snapshot(
            "test-agent",
            event_count=100,
            cost_per_minute=10.0,
        )
        alerts = detector.check("test-agent", snap)
        assert len(alerts) == 2

    def test_no_rules_no_alerts(self) -> None:
        tracker = BaselineTracker(min_samples=3)
        config = AnomalyDetectionConfig(enabled=True, rules=[])
        detector = AnomalyDetector(config=config, baselines=tracker)
        snap = _make_snapshot("test-agent", event_count=1000)
        alerts = detector.check("test-agent", snap)
        assert len(alerts) == 0

    def test_disabled_config_no_alerts(self) -> None:
        tracker = _build_tracker("test-agent", "event_count", _normal_values())
        config = AnomalyDetectionConfig(
            enabled=False,
            rules=[
                AnomalyRuleConfig(
                    name="high-count",
                    metric="event_count",
                    z_threshold=2.0,
                    severity="high",
                    cooldown_seconds=0,
                )
            ],
        )
        detector = AnomalyDetector(config=config, baselines=tracker)
        snap = _make_snapshot("test-agent", event_count=100)
        alerts = detector.check("test-agent", snap)
        assert len(alerts) == 0
