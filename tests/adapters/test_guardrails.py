"""Tests for the GuardrailsMonitor adapter."""

from __future__ import annotations

from unittest.mock import MagicMock

from theaios.agent_monitor.adapters.guardrails import GuardrailsMonitor
from theaios.agent_monitor.engine import Monitor
from theaios.agent_monitor.types import (
    AlertChannelConfig,
    AlertConfig,
    MonitorConfig,
    StorageConfig,
)


def _make_monitor(tmp_path) -> Monitor:
    config = MonitorConfig(
        version="1.0",
        alerts=AlertConfig(
            channels=[AlertChannelConfig(type="console")],
        ),
        storage=StorageConfig(path=str(tmp_path / "events.jsonl")),
    )
    return Monitor(config)


def _make_guard_event(agent: str = "test-agent", scope: str = "action") -> MagicMock:
    """Create a mock guardrails event."""
    event = MagicMock()
    event.agent = agent
    event.session_id = None
    event.scope = scope
    return event


def _make_decision(outcome: str = "allow", rule=None, severity=None) -> MagicMock:
    """Create a mock guardrails decision."""
    decision = MagicMock()
    decision.outcome = outcome
    decision.rule = rule
    decision.severity = severity
    decision.reason = None
    decision.dry_run = False
    decision.matched_rules = []
    return decision


class TestGuardrailsMonitor:
    def test_wraps_engine(self, tmp_path) -> None:
        monitor = _make_monitor(tmp_path)
        mock_engine = MagicMock()
        gm = GuardrailsMonitor(engine=mock_engine, monitor=monitor)
        # The adapter stores engine and monitor internally
        assert gm._engine is mock_engine
        assert gm._monitor is monitor

    def test_auto_records_decisions(self, tmp_path) -> None:
        monitor = _make_monitor(tmp_path)
        mock_engine = MagicMock()
        decision = _make_decision(outcome="allow")
        mock_engine.evaluate.return_value = decision

        gm = GuardrailsMonitor(engine=mock_engine, monitor=monitor)
        guard_event = _make_guard_event()
        result = gm.evaluate(guard_event)

        assert result is decision
        events = monitor.get_events()
        assert len(events) == 1
        # "allow" maps to "action" event type
        assert events[0]["event_type"] == "action"

    def test_records_denials(self, tmp_path) -> None:
        monitor = _make_monitor(tmp_path)
        mock_engine = MagicMock()
        decision = _make_decision(outcome="deny", rule="block-injection", severity="critical")
        mock_engine.evaluate.return_value = decision

        gm = GuardrailsMonitor(engine=mock_engine, monitor=monitor)
        guard_event = _make_guard_event()
        gm.evaluate(guard_event)

        events = monitor.get_events()
        assert len(events) == 1
        assert events[0]["event_type"] == "denial"
        assert events[0]["data"]["outcome"] == "deny"
        assert events[0]["data"]["rule"] == "block-injection"

    def test_records_approval_requests(self, tmp_path) -> None:
        monitor = _make_monitor(tmp_path)
        mock_engine = MagicMock()
        decision = _make_decision(outcome="require_approval")
        mock_engine.evaluate.return_value = decision

        gm = GuardrailsMonitor(engine=mock_engine, monitor=monitor)
        guard_event = _make_guard_event()
        gm.evaluate(guard_event)

        events = monitor.get_events()
        assert events[0]["event_type"] == "approval_request"
