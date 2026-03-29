"""Kill switch — in-memory + persisted agent/session/global kill state."""

from __future__ import annotations

import json
import logging
import tempfile
import time
from pathlib import Path

from theaios.agent_monitor.types import (
    KillState,
    KillSwitchConfig,
    MetricSnapshot,
)

_logger = logging.getLogger(__name__)


class KillSwitch:
    """In-memory kill switch with JSON persistence.

    Maintains sets of killed agents and sessions for O(1) lookup.
    Supports manual kills, automatic policy-based kills, and
    global kill (emergency stop for all agents).
    """

    def __init__(self, config: KillSwitchConfig) -> None:
        self._config = config
        self._state = KillState()
        self._state_path = Path(config.state_path)

    def kill_agent(self, agent: str, reason: str = "") -> None:
        """Kill a specific agent."""
        self._state.killed_agents.add(agent)
        if reason:
            self._state.reasons[f"agent:{agent}"] = reason

    def kill_session(self, session_id: str, reason: str = "") -> None:
        """Kill a specific session."""
        self._state.killed_sessions.add(session_id)
        if reason:
            self._state.reasons[f"session:{session_id}"] = reason

    def kill_global(self, reason: str = "") -> None:
        """Activate global kill — stops all agents."""
        self._state.global_kill = True
        if reason:
            self._state.reasons["global"] = reason

    def is_killed(self, agent: str, session_id: str | None = None) -> bool:
        """Check if an agent or session is killed. O(1) set lookup.

        Parameters
        ----------
        agent : str
            The agent name to check.
        session_id : str, optional
            If provided, also checks if this specific session is killed.

        Returns
        -------
        bool
            True if any kill applies (global, agent, or session).
        """
        if self._state.global_kill:
            return True
        if agent in self._state.killed_agents:
            return True
        if session_id and session_id in self._state.killed_sessions:
            return True
        return False

    def revive(self, agent: str | None = None, session_id: str | None = None) -> None:
        """Revive a specific agent or session.

        Parameters
        ----------
        agent : str, optional
            Agent to revive. Removes from killed set.
        session_id : str, optional
            Session to revive. Removes from killed set.
        """
        if agent:
            self._state.killed_agents.discard(agent)
            self._state.reasons.pop(f"agent:{agent}", None)
        if session_id:
            self._state.killed_sessions.discard(session_id)
            self._state.reasons.pop(f"session:{session_id}", None)

    def revive_global(self) -> None:
        """Deactivate global kill switch."""
        self._state.global_kill = False
        self._state.reasons.pop("global", None)

    def get_state(self) -> KillState:
        """Return the current kill state."""
        return self._state

    def _evaluate_operator(self, value: float, operator: str, threshold: float) -> bool:
        """Evaluate a comparison operator."""
        if operator == ">":
            return value > threshold
        if operator == "<":
            return value < threshold
        if operator == ">=":
            return value >= threshold
        if operator == "<=":
            return value <= threshold
        if operator == "==":
            return value == threshold
        return False

    def _get_metric_value(self, metrics: MetricSnapshot, metric_name: str) -> float | None:
        """Extract a metric value from a snapshot by name."""
        if hasattr(metrics, metric_name):
            val = getattr(metrics, metric_name)
            if isinstance(val, (int, float)):
                return float(val)
        return None

    def evaluate_policies(self, agent: str, metrics: MetricSnapshot) -> list[str]:
        """Evaluate kill policies against current metrics.

        Returns a list of triggered policy names. Automatically kills
        the agent/session/global based on the policy action.

        Parameters
        ----------
        agent : str
            The agent to evaluate policies for.
        metrics : MetricSnapshot
            Current metric snapshot.

        Returns
        -------
        list[str]
            Names of policies that were triggered.
        """
        if not self._config.enabled:
            return []

        triggered: list[str] = []

        for policy in self._config.policies:
            value = self._get_metric_value(metrics, policy.metric)
            if value is None:
                continue

            if self._evaluate_operator(value, policy.operator, policy.threshold):
                triggered.append(policy.name)
                reason = policy.message or (
                    f"Kill policy '{policy.name}' triggered: "
                    f"{policy.metric}={value} {policy.operator} {policy.threshold}"
                )

                if policy.action == "kill_agent":
                    self.kill_agent(agent, reason)
                elif policy.action == "kill_session":
                    # Kill all sessions is approximated by killing the agent
                    self.kill_agent(agent, reason)
                elif policy.action == "kill_global":
                    self.kill_global(reason)

        return triggered

    def save(self) -> None:
        """Persist kill state to disk (atomic write)."""
        self._state_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "killed_agents": sorted(self._state.killed_agents),
            "killed_sessions": sorted(self._state.killed_sessions),
            "global_kill": self._state.global_kill,
            "reasons": self._state.reasons,
            "saved_at": time.time(),
        }

        # Atomic write: write to temp file then rename to prevent corruption
        with tempfile.NamedTemporaryFile(
            dir=self._state_path.parent, mode="w", encoding="utf-8", suffix=".tmp", delete=False
        ) as f:
            json.dump(data, f, indent=2, default=str)
            temp_path = Path(f.name)
        temp_path.replace(self._state_path)

    def load(self) -> None:
        """Load kill state from disk."""
        if not self._state_path.exists():
            return

        try:
            with open(self._state_path, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            _logger.warning("Failed to load kill state from %s — using defaults", self._state_path)
            return

        if not isinstance(data, dict):
            _logger.warning("Kill state file is not a dict — using defaults")
            return

        agents_raw = data.get("killed_agents", [])
        sessions_raw = data.get("killed_sessions", [])
        reasons_raw = data.get("reasons", {})

        self._state.killed_agents = set(agents_raw) if isinstance(agents_raw, list) else set()
        self._state.killed_sessions = set(sessions_raw) if isinstance(sessions_raw, list) else set()
        self._state.global_kill = bool(data.get("global_kill", False))
        self._state.reasons = dict(reasons_raw) if isinstance(reasons_raw, dict) else {}
