"""End-to-end integration tests."""

from __future__ import annotations

import json
import textwrap
import time
from pathlib import Path

import pytest

from theaios.agent_monitor.config import load_config
from theaios.agent_monitor.engine import Monitor
from theaios.agent_monitor.types import AgentEvent


class TestEndToEnd:
    @pytest.fixture()
    def enterprise_config(self, tmp_path: Path) -> str:
        alert_path = str(tmp_path / "alerts.jsonl")
        events_path = str(tmp_path / "events.jsonl")
        content = textwrap.dedent(
            """\
            version: "1.0"

            storage:
              path: "{events_path}"

            metrics:
              default_window_seconds: 300
              max_window_seconds: 3600

            baselines:
              enabled: true
              min_samples: 5
              metrics:
                - denial_rate
                - error_count
                - cost_per_minute
                - avg_latency_ms

            anomaly_detection:
              enabled: true
              rules:
                - name: high-denial-rate
                  metric: denial_rate
                  z_threshold: 2.5
                  severity: high
                  cooldown_seconds: 0

            kill_switch:
              enabled: true
              policies:
                - name: auto-kill-high-cost
                  metric: cost_per_minute
                  operator: ">"
                  threshold: 10.0
                  action: kill_agent
                  severity: critical

            alerts:
              channels:
                - type: file
                  path: "{alert_path}"
        """.format(alert_path=alert_path, events_path=events_path)
        )
        p = tmp_path / "monitor.yaml"
        p.write_text(content)
        return str(p)

    def test_full_pipeline_record_and_metrics(self, enterprise_config: str) -> None:
        """Load config, create Monitor, record events, verify metrics."""
        config = load_config(enterprise_config)
        monitor = Monitor(config)

        now = time.time()
        # Record a sequence of events
        for i in range(10):
            monitor.record(
                AgentEvent(
                    timestamp=now - 10 + i,
                    event_type="action",
                    agent="test-agent",
                    latency_ms=100.0 + i * 10,
                    cost_usd=0.01,
                )
            )

        snap = monitor.get_metrics("test-agent")
        assert snap.event_count == 10
        assert snap.avg_latency_ms > 0
        assert snap.cost_per_minute > 0

    def test_full_pipeline_denial_tracking(self, enterprise_config: str) -> None:
        """Denials are tracked in metrics."""
        config = load_config(enterprise_config)
        monitor = Monitor(config)

        now = time.time()
        # Record events: 3 actions, 2 denials
        event_types = ["action", "denial", "action", "denial", "action"]
        for i, et in enumerate(event_types):
            monitor.record(
                AgentEvent(
                    timestamp=now - 5 + i,
                    event_type=et,
                    agent="test-agent",
                )
            )

        snap = monitor.get_metrics("test-agent")
        # denial_rate = denials / (actions + denials) = 2 / 5 = 0.4
        assert abs(snap.denial_rate - 0.4) < 0.05

    def test_full_pipeline_kill_switch_auto_trigger(self, enterprise_config: str) -> None:
        """Kill switch auto-triggers when cost threshold is exceeded."""
        config = load_config(enterprise_config)
        monitor = Monitor(config)

        now = time.time()
        # Record expensive events to trigger the kill switch (cost > 10/min)
        for i in range(100):
            monitor.record(
                AgentEvent(
                    timestamp=now - 100 + i,
                    event_type="action",
                    agent="expensive-agent",
                    latency_ms=50.0,
                    cost_usd=1.0,
                )
            )

        # The agent should now be killed
        assert monitor.is_killed("expensive-agent") is True

    def test_full_pipeline_manual_kill_and_revive(self, enterprise_config: str) -> None:
        """Manual kill/revive works through the Monitor API."""
        config = load_config(enterprise_config)
        monitor = Monitor(config)

        now = time.time()
        monitor.record(
            AgentEvent(
                timestamp=now,
                event_type="action",
                agent="test-agent",
                latency_ms=100.0,
                cost_usd=0.01,
            )
        )
        assert monitor.is_killed("test-agent") is False

        monitor.kill_agent("test-agent", reason="manual override")
        assert monitor.is_killed("test-agent") is True

        # Killed agents reject events
        result = monitor.record(
            AgentEvent(
                timestamp=now + 1,
                event_type="action",
                agent="test-agent",
                latency_ms=100.0,
            )
        )
        assert result is False or result is None

        monitor.revive(agent="test-agent")
        assert monitor.is_killed("test-agent") is False

    def test_full_pipeline_compliance_export(self, enterprise_config: str) -> None:
        """Compliance export produces valid reports."""
        config = load_config(enterprise_config)
        monitor = Monitor(config)

        now = time.time()
        for i in range(5):
            monitor.record(
                AgentEvent(
                    timestamp=now - 10 + i * 2,
                    event_type="action",
                    agent="test-agent",
                    latency_ms=100.0,
                    cost_usd=0.01,
                )
            )
            monitor.record(
                AgentEvent(
                    timestamp=now - 10 + i * 2 + 1,
                    event_type="guardrail_trigger",
                    agent="test-agent",
                    data={"outcome": "allow", "rule": "test-rule"},
                )
            )

        report_str = monitor.compliance_exporter.export(format="json")
        report = json.loads(report_str)
        assert report["format"] == "json"
        assert report["total_events"] == 10
