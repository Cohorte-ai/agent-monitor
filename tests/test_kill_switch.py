"""Tests for the KillSwitch."""

from __future__ import annotations

import time
from pathlib import Path

from theaios.agent_monitor.kill_switch import KillSwitch
from theaios.agent_monitor.types import (
    KillPolicyConfig,
    KillSwitchConfig,
    MetricSnapshot,
)


def _make_config(
    policies: list[KillPolicyConfig] | None = None,
    state_path: str = ".agent_monitor/kill_state.json",
) -> KillSwitchConfig:
    return KillSwitchConfig(
        enabled=True,
        policies=policies or [],
        state_path=state_path,
    )


def _make_snapshot(agent: str, **kwargs) -> MetricSnapshot:
    return MetricSnapshot(
        agent=agent,
        window_seconds=300,
        timestamp=time.time(),
        **kwargs,
    )


class TestKillSwitch:
    def test_kill_agent_and_is_killed(self) -> None:
        ks = KillSwitch(config=_make_config())
        ks.kill_agent("agent-alpha", reason="cost spike")
        assert ks.is_killed("agent-alpha") is True

    def test_kill_session(self) -> None:
        ks = KillSwitch(config=_make_config())
        ks.kill_session("sess-123")
        # is_killed checks agent + optional session_id
        assert ks.is_killed("any-agent", session_id="sess-123") is True
        assert ks.is_killed("any-agent", session_id="sess-456") is False

    def test_kill_global(self) -> None:
        ks = KillSwitch(config=_make_config())
        ks.kill_global(reason="emergency shutdown")
        assert ks.is_killed("any-agent") is True
        assert ks.is_killed("another-agent") is True

    def test_revive_agent(self) -> None:
        ks = KillSwitch(config=_make_config())
        ks.kill_agent("agent-alpha", reason="test")
        assert ks.is_killed("agent-alpha") is True
        ks.revive(agent="agent-alpha")
        assert ks.is_killed("agent-alpha") is False

    def test_revive_global(self) -> None:
        ks = KillSwitch(config=_make_config())
        ks.kill_global(reason="test")
        assert ks.is_killed("any-agent") is True
        ks.revive_global()
        assert ks.is_killed("any-agent") is False

    def test_save_and_load_persistence(self, tmp_dir: Path) -> None:
        path = str(tmp_dir / "kill_state.json")
        ks = KillSwitch(config=_make_config(state_path=path))
        ks.kill_agent("agent-alpha", reason="cost spike")
        ks.kill_session("sess-999")
        ks.save()
        assert Path(path).exists()

        ks2 = KillSwitch(config=_make_config(state_path=path))
        ks2.load()
        assert ks2.is_killed("agent-alpha") is True
        assert ks2.is_killed("any-agent", session_id="sess-999") is True

    def test_is_killed_returns_false_for_non_killed(self) -> None:
        ks = KillSwitch(config=_make_config())
        assert ks.is_killed("agent-alpha") is False

    def test_evaluate_policies_triggers_on_threshold(self) -> None:
        policies = [
            KillPolicyConfig(
                name="auto-kill-cost",
                metric="cost_per_minute",
                operator=">",
                threshold=1.0,
                action="kill_agent",
                severity="critical",
            )
        ]
        ks = KillSwitch(config=_make_config(policies=policies))
        snap = _make_snapshot("test-agent", cost_per_minute=2.0)
        triggered = ks.evaluate_policies("test-agent", snap)
        assert len(triggered) >= 1
        assert ks.is_killed("test-agent") is True

    def test_evaluate_policies_no_trigger_below_threshold(self) -> None:
        policies = [
            KillPolicyConfig(
                name="auto-kill-cost",
                metric="cost_per_minute",
                operator=">",
                threshold=1.0,
                action="kill_agent",
                severity="critical",
            )
        ]
        ks = KillSwitch(config=_make_config(policies=policies))
        snap = _make_snapshot("test-agent", cost_per_minute=0.5)
        triggered = ks.evaluate_policies("test-agent", snap)
        assert len(triggered) == 0
        assert ks.is_killed("test-agent") is False

    def test_kill_global_policy(self) -> None:
        policies = [
            KillPolicyConfig(
                name="emergency-shutdown",
                metric="event_count",
                operator=">",
                threshold=1000,
                action="kill_global",
                severity="critical",
            )
        ]
        ks = KillSwitch(config=_make_config(policies=policies))
        snap = _make_snapshot("test-agent", event_count=2000)
        triggered = ks.evaluate_policies("test-agent", snap)
        assert len(triggered) >= 1
        assert ks.is_killed("any-agent") is True

    def test_multiple_agents_independent(self) -> None:
        ks = KillSwitch(config=_make_config())
        ks.kill_agent("agent-a", reason="test-a")
        ks.kill_agent("agent-b", reason="test-b")
        assert ks.is_killed("agent-a") is True
        assert ks.is_killed("agent-b") is True
        ks.revive(agent="agent-a")
        assert ks.is_killed("agent-a") is False
        assert ks.is_killed("agent-b") is True

    def test_kill_reason_stored(self) -> None:
        ks = KillSwitch(config=_make_config())
        ks.kill_agent("agent-alpha", reason="cost exceeded $5/min")
        state = ks.get_state()
        assert "agent-alpha" in state.killed_agents
        assert state.reasons["agent:agent-alpha"] == "cost exceeded $5/min"
