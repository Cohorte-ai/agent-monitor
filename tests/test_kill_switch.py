"""Tests for the KillSwitch."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

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


# --- Round 1 findings: persistence and after-kill events ---------------------------------------


def test_a_kill_survives_a_restart_and_reaches_a_running_monitor(tmp_path: Path) -> None:
    from theaios.agent_monitor import Monitor
    from theaios.agent_monitor.types import MonitorConfig, StorageConfig

    path = str(tmp_path / "kill.json")

    def monitor() -> Monitor:
        return Monitor(
            MonitorConfig(
                version="1.0",
                storage=StorageConfig(path=str(tmp_path / "e.jsonl")),
                kill_switch=KillSwitchConfig(state_path=path),
            )
        )

    running = monitor()
    assert not running.is_killed("a")
    KillSwitch(KillSwitchConfig(state_path=path)).kill_agent("a", "from the CLI")
    assert running.is_killed("a")  # another process's kill applies at once
    assert monitor().is_killed("a")  # and after a restart
    running.revive("a")
    assert not monitor().is_killed("a")


def test_events_after_a_kill_are_stored_tagged_but_feed_no_metrics(tmp_path: Path) -> None:
    import time as _time

    from theaios.agent_monitor import AgentEvent, Monitor
    from theaios.agent_monitor.types import MonitorConfig, StorageConfig

    m = Monitor(
        MonitorConfig(
            version="1.0",
            storage=StorageConfig(path=str(tmp_path / "e.jsonl")),
            kill_switch=KillSwitchConfig(state_path=str(tmp_path / "k.json")),
        )
    )
    m.kill_agent("a", "runaway")
    m.record(AgentEvent(timestamp=_time.time(), agent="a", event_type="cost", cost_usd=1.5))
    (event,) = m.get_events()
    assert event["tags"] == ["after_kill"] and event["cost_usd"] == 1.5
    assert m.get_metrics("a").event_count == 0


def test_relative_paths_in_a_config_file_are_relative_to_it(tmp_path: Path) -> None:
    import os

    from theaios.agent_monitor import Monitor, load_config

    conf = tmp_path / "svc"
    conf.mkdir()
    (conf / "monitor.yaml").write_text(
        'version: "1.0"\nkill_switch:\n  state_path: state/kill.json\n'
        "storage:\n  path: state/events.jsonl\n"
    )
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    service = Monitor(load_config(str(conf / "monitor.yaml")))
    cwd = os.getcwd()
    os.chdir(elsewhere)
    try:  # an operator running the CLI from another directory
        KillSwitch(load_config(str(conf / "monitor.yaml")).kill_switch).kill_agent("a")
    finally:
        os.chdir(cwd)
    assert service.is_killed("a")
    assert (conf / "state" / "kill.json").exists() and not (elsewhere / "state").exists()


def test_concurrent_writers_never_lose_a_kill(tmp_path: Path) -> None:
    import threading

    path = str(tmp_path / "kill.json")
    stop = threading.Event()

    def busy() -> None:  # another worker reviving something else, all the time
        other = KillSwitch(KillSwitchConfig(state_path=path))
        while not stop.is_set():
            other.revive(agent="noise")

    workers = [threading.Thread(target=busy) for _ in range(3)]
    for w in workers:
        w.start()
    try:
        for i in range(30):
            KillSwitch(KillSwitchConfig(state_path=path)).kill_agent(f"a{i}")
    finally:
        stop.set()
        for w in workers:
            w.join()
    fresh = KillSwitch(KillSwitchConfig(state_path=path))
    assert all(fresh.is_killed(f"a{i}") for i in range(30))


def test_the_cli_never_overwrites_a_kill_made_meanwhile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from click.testing import CliRunner

    from theaios.agent_monitor.cli import main

    conf = tmp_path / "monitor.yaml"
    conf.write_text('version: "1.0"\nkill_switch:\n  state_path: kill.json\n')
    original = KillSwitch.kill_agent

    def kill_then_someone_else_kills(self: KillSwitch, agent: str, reason: str = "") -> None:
        original(self, agent, reason)
        if agent == "A":  # another process kills B right after the CLI's locked write
            original(KillSwitch(KillSwitchConfig(state_path=str(tmp_path / "kill.json"))), "B")

    monkeypatch.setattr(KillSwitch, "kill_agent", kill_then_someone_else_kills)
    result = CliRunner().invoke(main, ["-c", str(conf), "kill", "A"])
    assert result.exit_code == 0, result.output
    fresh = KillSwitch(KillSwitchConfig(state_path=str(tmp_path / "kill.json")))
    assert fresh.is_killed("A") and fresh.is_killed("B")
