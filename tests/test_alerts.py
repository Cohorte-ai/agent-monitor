"""Tests for the AlertDispatcher."""

from __future__ import annotations

import json
import time
from pathlib import Path

from theaios.agent_monitor.alerts import AlertDispatcher
from theaios.agent_monitor.types import (
    AlertChannelConfig,
    AlertConfig,
    AnomalyAlert,
)


def _make_alert(
    rule: str = "high-cost",
    agent: str = "test-agent",
    severity: str = "critical",
    message: str = "Cost spike detected",
    metric: str = "cost_per_minute",
    value: float = 5.0,
    z_score: float = 4.0,
    threshold: float = 3.0,
) -> AnomalyAlert:
    return AnomalyAlert(
        agent=agent,
        rule=rule,
        metric=metric,
        value=value,
        z_score=z_score,
        threshold=threshold,
        severity=severity,
        message=message,
        timestamp=time.time(),
    )


class TestAlertDispatcher:
    def test_console_channel(self, capsys: object) -> None:
        """Console channel writes to stderr."""
        config = AlertConfig(channels=[AlertChannelConfig(type="console")])
        dispatcher = AlertDispatcher(config=config)
        alert = _make_alert(message="Cost spike detected for high-cost")
        dispatcher.dispatch(alert)
        captured = capsys.readouterr()  # type: ignore[attr-defined]
        assert "Cost spike" in captured.err or "Cost spike" in captured.out

    def test_file_channel(self, tmp_dir: Path) -> None:
        """File channel writes JSONL."""
        alert_file = tmp_dir / "alerts.jsonl"
        config = AlertConfig(channels=[AlertChannelConfig(type="file", path=str(alert_file))])
        dispatcher = AlertDispatcher(config=config)
        alert = _make_alert()
        dispatcher.dispatch(alert)
        assert alert_file.exists()
        lines = alert_file.read_text().strip().splitlines()
        assert len(lines) == 1
        parsed = json.loads(lines[0])
        assert parsed["rule"] == "high-cost"

    def test_dispatch_kill_writes_alert(self, tmp_dir: Path) -> None:
        """Kill switch alerts are written."""
        alert_file = tmp_dir / "alerts.jsonl"
        config = AlertConfig(channels=[AlertChannelConfig(type="file", path=str(alert_file))])
        dispatcher = AlertDispatcher(config=config)
        dispatcher.dispatch_kill("test-agent", "cost exceeded threshold")
        lines = alert_file.read_text().strip().splitlines()
        parsed = json.loads(lines[0])
        assert parsed["type"] == "kill"

    def test_multiple_channels_all_receive(self, tmp_dir: Path, capsys: object) -> None:
        """All configured channels receive the alert."""
        alert_file = tmp_dir / "alerts.jsonl"
        config = AlertConfig(
            channels=[
                AlertChannelConfig(type="console"),
                AlertChannelConfig(type="file", path=str(alert_file)),
            ]
        )
        dispatcher = AlertDispatcher(config=config)
        alert = _make_alert(rule="test-rule", message="Test alert for test-rule")
        dispatcher.dispatch(alert)
        # Console channel
        captured = capsys.readouterr()  # type: ignore[attr-defined]
        assert "Test alert" in captured.err or "Test alert" in captured.out
        # File channel
        assert alert_file.exists()
        lines = alert_file.read_text().strip().splitlines()
        assert len(lines) == 1

    def test_multiple_dispatches_append(self, tmp_dir: Path) -> None:
        """Multiple dispatches append to the file."""
        alert_file = tmp_dir / "alerts.jsonl"
        config = AlertConfig(channels=[AlertChannelConfig(type="file", path=str(alert_file))])
        dispatcher = AlertDispatcher(config=config)
        for i in range(3):
            dispatcher.dispatch(_make_alert(rule=f"rule-{i}", message=f"Alert {i}"))
        lines = alert_file.read_text().strip().splitlines()
        assert len(lines) == 3

    def test_no_channels_no_error(self) -> None:
        """Empty channel list doesn't crash."""
        config = AlertConfig(channels=[])
        dispatcher = AlertDispatcher(config=config)
        dispatcher.dispatch(_make_alert())

    def test_alert_contains_timestamp(self, tmp_dir: Path) -> None:
        """Dispatched alerts include a timestamp."""
        alert_file = tmp_dir / "alerts.jsonl"
        config = AlertConfig(channels=[AlertChannelConfig(type="file", path=str(alert_file))])
        dispatcher = AlertDispatcher(config=config)
        dispatcher.dispatch(_make_alert())
        parsed = json.loads(alert_file.read_text().strip())
        assert "timestamp" in parsed
