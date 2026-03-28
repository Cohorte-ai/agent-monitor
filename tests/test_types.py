"""Tests for data models and type definitions."""

from __future__ import annotations

import time

from theaios.agent_monitor.types import (
    VALID_ALERT_CHANNELS,
    VALID_EVENT_TYPES,
    VALID_KILL_ACTIONS,
    VALID_METRICS,
    VALID_SEVERITIES,
    AgentEvent,
    AlertChannelType,
    EventType,
    KillAction,
    KillState,
    MetricSnapshot,
    Severity,
)


class TestEventType:
    def test_action(self) -> None:
        assert EventType.ACTION.value == "action"

    def test_guardrail_trigger(self) -> None:
        assert EventType.GUARDRAIL_TRIGGER.value == "guardrail_trigger"

    def test_denial(self) -> None:
        assert EventType.DENIAL.value == "denial"

    def test_cost(self) -> None:
        assert EventType.COST.value == "cost"

    def test_error(self) -> None:
        assert EventType.ERROR.value == "error"

    def test_session_start(self) -> None:
        assert EventType.SESSION_START.value == "session_start"


class TestSeverity:
    def test_critical(self) -> None:
        assert Severity.CRITICAL.value == "critical"

    def test_high(self) -> None:
        assert Severity.HIGH.value == "high"

    def test_medium(self) -> None:
        assert Severity.MEDIUM.value == "medium"

    def test_low(self) -> None:
        assert Severity.LOW.value == "low"


class TestKillAction:
    def test_kill_agent(self) -> None:
        assert KillAction.KILL_AGENT.value == "kill_agent"

    def test_kill_session(self) -> None:
        assert KillAction.KILL_SESSION.value == "kill_session"

    def test_kill_global(self) -> None:
        assert KillAction.KILL_GLOBAL.value == "kill_global"


class TestAlertChannelType:
    def test_console(self) -> None:
        assert AlertChannelType.CONSOLE.value == "console"

    def test_file(self) -> None:
        assert AlertChannelType.FILE.value == "file"

    def test_webhook(self) -> None:
        assert AlertChannelType.WEBHOOK.value == "webhook"


class TestValidSets:
    def test_valid_event_types(self) -> None:
        assert "action" in VALID_EVENT_TYPES
        assert "guardrail_trigger" in VALID_EVENT_TYPES
        assert "denial" in VALID_EVENT_TYPES
        assert "cost" in VALID_EVENT_TYPES
        assert "error" in VALID_EVENT_TYPES
        assert "banana" not in VALID_EVENT_TYPES

    def test_valid_severities(self) -> None:
        assert "critical" in VALID_SEVERITIES
        assert "high" in VALID_SEVERITIES
        assert "medium" in VALID_SEVERITIES
        assert "low" in VALID_SEVERITIES
        assert "ultra" not in VALID_SEVERITIES

    def test_valid_metrics(self) -> None:
        assert "event_count" in VALID_METRICS
        assert "denial_rate" in VALID_METRICS
        assert "cost_per_minute" in VALID_METRICS
        assert "avg_latency_ms" in VALID_METRICS
        assert "throughput" not in VALID_METRICS

    def test_valid_kill_actions(self) -> None:
        assert "kill_agent" in VALID_KILL_ACTIONS
        assert "kill_session" in VALID_KILL_ACTIONS
        assert "kill_global" in VALID_KILL_ACTIONS
        assert "restart" not in VALID_KILL_ACTIONS

    def test_valid_alert_channels(self) -> None:
        assert "console" in VALID_ALERT_CHANNELS
        assert "file" in VALID_ALERT_CHANNELS
        assert "webhook" in VALID_ALERT_CHANNELS


class TestAgentEvent:
    def test_minimal_event(self) -> None:
        now = time.time()
        event = AgentEvent(timestamp=now, agent="test", event_type="action")
        assert event.event_type == "action"
        assert event.agent == "test"
        assert event.data == {}
        assert event.session_id is None
        assert event.cost_usd is None
        assert event.latency_ms is None

    def test_full_event(self) -> None:
        now = time.time()
        event = AgentEvent(
            timestamp=now,
            agent="finance-agent",
            event_type="guardrail_trigger",
            session_id="sess-abc",
            user="alice",
            cost_usd=0.002,
            latency_ms=150.0,
            data={"rule": "block-injection", "outcome": "deny"},
            tags=["security"],
        )
        assert event.event_type == "guardrail_trigger"
        assert event.agent == "finance-agent"
        assert event.session_id == "sess-abc"
        assert event.user == "alice"
        assert event.cost_usd == 0.002
        assert event.latency_ms == 150.0
        assert event.data["outcome"] == "deny"
        assert "security" in event.tags


class TestMetricSnapshot:
    def test_defaults(self) -> None:
        now = time.time()
        snap = MetricSnapshot(agent="test", window_seconds=3600, timestamp=now)
        assert snap.agent == "test"
        assert snap.event_count == 0
        assert snap.denial_rate == 0.0
        assert snap.cost_per_minute == 0.0
        assert snap.avg_latency_ms == 0.0

    def test_custom_values(self) -> None:
        now = time.time()
        snap = MetricSnapshot(
            agent="finance",
            window_seconds=60,
            timestamp=now,
            event_count=42,
            denial_rate=0.15,
            cost_per_minute=0.5,
            avg_latency_ms=200.0,
        )
        assert snap.event_count == 42
        assert snap.denial_rate == 0.15
        assert snap.cost_per_minute == 0.5


class TestKillState:
    def test_defaults(self) -> None:
        state = KillState()
        assert state.killed_agents == set()
        assert state.killed_sessions == set()
        assert state.global_kill is False
        assert state.reasons == {}

    def test_custom_values(self) -> None:
        state = KillState(
            killed_agents={"agent-a"},
            killed_sessions={"sess-1", "sess-2"},
            global_kill=True,
            reasons={"agent-a": "cost spike"},
        )
        assert "agent-a" in state.killed_agents
        assert "sess-1" in state.killed_sessions
        assert state.global_kill is True
        assert state.reasons["agent-a"] == "cost spike"
