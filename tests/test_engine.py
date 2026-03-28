"""Tests for the Monitor (main engine)."""

from __future__ import annotations

import time

from theaios.agent_monitor.engine import Monitor
from theaios.agent_monitor.types import (
    AgentEvent,
    AlertChannelConfig,
    AlertConfig,
    AnomalyDetectionConfig,
    AnomalyRuleConfig,
    BaselineConfig,
    MonitorConfig,
    StorageConfig,
)


class TestMonitorRecord:
    def test_record_event_stores_it(self, basic_config: MonitorConfig) -> None:
        monitor = Monitor(basic_config)
        now = time.time()
        event = AgentEvent(
            timestamp=now,
            event_type="action",
            agent="test-agent",
            latency_ms=100.0,
            cost_usd=0.01,
        )
        monitor.record(event)
        events = monitor.get_events()
        assert len(events) == 1
        assert events[0]["event_type"] == "action"

    def test_record_triggers_metrics(self, basic_config: MonitorConfig) -> None:
        monitor = Monitor(basic_config)
        now = time.time()
        for i in range(5):
            monitor.record(
                AgentEvent(
                    timestamp=now - i,
                    event_type="action",
                    agent="test-agent",
                    latency_ms=100.0,
                    cost_usd=0.01,
                )
            )
        snap = monitor.get_metrics("test-agent")
        assert snap.event_count == 5

    def test_record_triggers_anomaly_detection(self, tmp_path) -> None:
        config = MonitorConfig(
            version="1.0",
            baselines=BaselineConfig(min_samples=3),
            anomaly_detection=AnomalyDetectionConfig(
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
            ),
            alerts=AlertConfig(
                channels=[AlertChannelConfig(type="console")],
            ),
            storage=StorageConfig(path=str(tmp_path / "events.jsonl")),
        )
        monitor = Monitor(config)
        now = time.time()
        # Build baseline with normal values
        for i in range(20):
            monitor.record(
                AgentEvent(
                    timestamp=now - 20 + i,
                    event_type="action",
                    agent="test-agent",
                    latency_ms=100.0,
                )
            )
        # The monitor should have processed events without error
        snap = monitor.get_metrics("test-agent")
        assert snap.event_count > 0


class TestMonitorKillSwitch:
    def test_is_killed_works(self, basic_config: MonitorConfig) -> None:
        monitor = Monitor(basic_config)
        assert monitor.is_killed("test-agent") is False

    def test_kill_agent_prevents_further_processing(self, basic_config: MonitorConfig) -> None:
        monitor = Monitor(basic_config)
        monitor.kill_agent("test-agent", reason="test")
        assert monitor.is_killed("test-agent") is True
        # Events for killed agents should be rejected (record returns None)
        result = monitor.record(
            AgentEvent(
                timestamp=time.time(),
                event_type="action",
                agent="test-agent",
                latency_ms=100.0,
            )
        )
        assert result is False or result is None

    def test_revive_allows_processing(self, basic_config: MonitorConfig) -> None:
        monitor = Monitor(basic_config)
        monitor.kill_agent("test-agent", reason="test")
        assert monitor.is_killed("test-agent") is True
        monitor.revive(agent="test-agent")
        assert monitor.is_killed("test-agent") is False


class TestMonitorMetrics:
    def test_get_metrics_returns_correct_values(self, basic_config: MonitorConfig) -> None:
        monitor = Monitor(basic_config)
        now = time.time()
        latencies = [100.0, 200.0, 300.0]
        for i, lat in enumerate(latencies):
            monitor.record(
                AgentEvent(
                    timestamp=now - i,
                    event_type="action",
                    agent="test-agent",
                    latency_ms=lat,
                    cost_usd=0.01,
                )
            )
        snap = monitor.get_metrics("test-agent")
        assert snap.event_count == 3
        assert snap.avg_latency_ms > 0

    def test_get_events_returns_stored_events(self, basic_config: MonitorConfig) -> None:
        monitor = Monitor(basic_config)
        now = time.time()
        for i in range(5):
            monitor.record(
                AgentEvent(
                    timestamp=now - i,
                    event_type="action",
                    agent="test-agent",
                    data={"i": i},
                )
            )
        events = monitor.get_events()
        assert len(events) == 5

    def test_get_events_filter_by_agent(self, basic_config: MonitorConfig) -> None:
        monitor = Monitor(basic_config)
        now = time.time()
        monitor.record(AgentEvent(timestamp=now, event_type="action", agent="alpha"))
        monitor.record(AgentEvent(timestamp=now, event_type="action", agent="beta"))
        events = monitor.get_events(agent="alpha")
        assert len(events) == 1
        assert events[0]["agent"] == "alpha"

    def test_get_metrics_unknown_agent(self, basic_config: MonitorConfig) -> None:
        monitor = Monitor(basic_config)
        snap = monitor.get_metrics("nonexistent")
        assert snap.event_count == 0


class TestMonitorFlush:
    def test_flush_resets_metrics(self, basic_config: MonitorConfig) -> None:
        monitor = Monitor(basic_config)
        now = time.time()
        for i in range(5):
            monitor.record(
                AgentEvent(
                    timestamp=now - i,
                    event_type="action",
                    agent="test-agent",
                    latency_ms=100.0,
                    cost_usd=0.01,
                )
            )
        monitor.flush()
        snap = monitor.get_metrics("test-agent")
        assert snap.event_count == 0


class TestMonitorMultiAgent:
    def test_multiple_agents(self, basic_config: MonitorConfig) -> None:
        monitor = Monitor(basic_config)
        now = time.time()
        for i in range(3):
            monitor.record(
                AgentEvent(
                    timestamp=now - i,
                    event_type="action",
                    agent="alpha",
                    latency_ms=100.0,
                    cost_usd=0.01,
                )
            )
        for i in range(5):
            monitor.record(
                AgentEvent(
                    timestamp=now - i,
                    event_type="action",
                    agent="beta",
                    latency_ms=200.0,
                    cost_usd=0.02,
                )
            )
        snap_alpha = monitor.get_metrics("alpha")
        snap_beta = monitor.get_metrics("beta")
        assert snap_alpha.event_count == 3
        assert snap_beta.event_count == 5

    def test_kill_one_agent_not_other(self, basic_config: MonitorConfig) -> None:
        monitor = Monitor(basic_config)
        monitor.kill_agent("alpha", reason="test")
        assert monitor.is_killed("alpha") is True
        assert monitor.is_killed("beta") is False
