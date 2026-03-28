"""Tests for the MetricsEngine."""

from __future__ import annotations

import time

from theaios.agent_monitor.metrics import MetricsEngine
from theaios.agent_monitor.types import AgentEvent, MetricSnapshot


class TestMetricsEngine:
    def test_ingest_event(self) -> None:
        engine = MetricsEngine(default_window_seconds=300)
        now = time.time()
        event = AgentEvent(
            timestamp=now,
            event_type="action",
            agent="test",
            latency_ms=200.0,
            cost_usd=0.01,
        )
        engine.ingest(event)
        snap = engine.get_metrics("test")
        assert snap.event_count >= 1

    def test_compute_snapshot(self) -> None:
        engine = MetricsEngine(default_window_seconds=300)
        now = time.time()
        for i in range(5):
            engine.ingest(
                AgentEvent(
                    timestamp=now - i,
                    event_type="action",
                    agent="test",
                    latency_ms=100.0 + i * 10,
                    cost_usd=0.01,
                )
            )
        snap = engine.get_metrics("test")
        assert isinstance(snap, MetricSnapshot)
        assert snap.agent == "test"

    def test_event_count_correct(self) -> None:
        engine = MetricsEngine(default_window_seconds=300)
        now = time.time()
        for i in range(7):
            engine.ingest(
                AgentEvent(
                    timestamp=now - i,
                    event_type="action",
                    agent="test",
                    latency_ms=100.0,
                    cost_usd=0.01,
                )
            )
        snap = engine.get_metrics("test")
        assert snap.event_count == 7

    def test_denial_rate_computed(self) -> None:
        engine = MetricsEngine(default_window_seconds=300)
        now = time.time()
        # 2 denials out of 4 decisions (2 action + 2 denial)
        engine.ingest(AgentEvent(timestamp=now - 4, event_type="denial", agent="test"))
        engine.ingest(AgentEvent(timestamp=now - 3, event_type="action", agent="test"))
        engine.ingest(AgentEvent(timestamp=now - 2, event_type="denial", agent="test"))
        engine.ingest(AgentEvent(timestamp=now - 1, event_type="action", agent="test"))
        snap = engine.get_metrics("test")
        assert abs(snap.denial_rate - 0.5) < 0.01

    def test_cost_per_minute(self) -> None:
        engine = MetricsEngine(default_window_seconds=60, max_window_seconds=60)
        now = time.time()
        # 3 events, $0.01 each, within a 60-second window
        for i in range(3):
            engine.ingest(
                AgentEvent(
                    timestamp=now - i * 10,
                    event_type="action",
                    agent="test",
                    cost_usd=0.01,
                )
            )
        snap = engine.get_metrics("test")
        assert snap.cost_per_minute > 0

    def test_avg_latency_ms(self) -> None:
        engine = MetricsEngine(default_window_seconds=300)
        now = time.time()
        latencies = [100.0, 200.0, 300.0]
        for i, lat in enumerate(latencies):
            engine.ingest(
                AgentEvent(
                    timestamp=now - i,
                    event_type="action",
                    agent="test",
                    latency_ms=lat,
                )
            )
        snap = engine.get_metrics("test")
        assert abs(snap.avg_latency_ms - 200.0) < 0.01

    def test_multiple_agents_independent(self) -> None:
        engine = MetricsEngine(default_window_seconds=300)
        now = time.time()
        for i in range(3):
            engine.ingest(
                AgentEvent(
                    timestamp=now - i,
                    event_type="action",
                    agent="alpha",
                    latency_ms=100.0,
                    cost_usd=0.01,
                )
            )
        for i in range(5):
            engine.ingest(
                AgentEvent(
                    timestamp=now - i,
                    event_type="action",
                    agent="beta",
                    latency_ms=200.0,
                    cost_usd=0.02,
                )
            )
        snap_alpha = engine.get_metrics("alpha")
        snap_beta = engine.get_metrics("beta")
        assert snap_alpha.event_count == 3
        assert snap_beta.event_count == 5
        assert snap_alpha.avg_latency_ms != snap_beta.avg_latency_ms

    def test_rolling_window_expiry(self) -> None:
        engine = MetricsEngine(default_window_seconds=60, max_window_seconds=60)
        now = time.time()
        # Old event outside the window
        engine.ingest(
            AgentEvent(
                timestamp=now - 120,
                event_type="action",
                agent="test",
                latency_ms=100.0,
                cost_usd=0.01,
            )
        )
        # Recent event inside the window
        engine.ingest(
            AgentEvent(
                timestamp=now - 10,
                event_type="action",
                agent="test",
                latency_ms=200.0,
                cost_usd=0.02,
            )
        )
        snap = engine.get_metrics("test")
        assert snap.event_count == 1

    def test_empty_metrics_for_unknown_agent(self) -> None:
        engine = MetricsEngine(default_window_seconds=300)
        snap = engine.get_metrics("nonexistent")
        assert snap.event_count == 0
        assert snap.denial_rate == 0.0
        assert snap.cost_per_minute == 0.0
        assert snap.avg_latency_ms == 0.0

    def test_zero_latency_events(self) -> None:
        engine = MetricsEngine(default_window_seconds=300)
        now = time.time()
        engine.ingest(
            AgentEvent(
                timestamp=now,
                event_type="error",
                agent="test",
            )
        )
        snap = engine.get_metrics("test")
        assert snap.avg_latency_ms == 0.0

    def test_no_cost_events(self) -> None:
        engine = MetricsEngine(default_window_seconds=300)
        now = time.time()
        engine.ingest(
            AgentEvent(
                timestamp=now,
                event_type="action",
                agent="test",
                data={"tool": "search"},
            )
        )
        snap = engine.get_metrics("test")
        assert snap.cost_per_minute == 0.0
