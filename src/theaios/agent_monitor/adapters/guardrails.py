"""Adapter for theaios-guardrails — auto-records guardrail evaluations as events."""

from __future__ import annotations

import time
from typing import Any


class GuardrailsMonitor:
    """Wraps a guardrails Engine, auto-records every evaluate() as an AgentEvent.

    Uses object typing with lazy imports so the adapter works even when
    theaios-guardrails is not installed (it just won't be usable).

    Usage::

        from theaios.agent_monitor import Monitor, load_config
        from theaios.agent_monitor.adapters.guardrails import GuardrailsMonitor
        from theaios.guardrails import Engine, load_policy

        monitor = Monitor(load_config())
        engine = Engine(load_policy())
        wrapped = GuardrailsMonitor(engine, monitor)

        # Use wrapped.evaluate() instead of engine.evaluate()
        decision = wrapped.evaluate(event)
    """

    def __init__(self, engine: Any, monitor: Any) -> None:  # noqa: ANN401
        """Initialize the guardrails adapter.

        Parameters
        ----------
        engine : theaios.guardrails.Engine
            The guardrails engine to wrap.
        monitor : theaios.agent_monitor.engine.Monitor
            The agent monitor to record events to.
        """
        self._engine = engine
        self._monitor = monitor

    def evaluate(self, event: Any) -> Any:  # noqa: ANN401
        """Evaluate a guardrail event and record it as an AgentEvent.

        Parameters
        ----------
        event : theaios.guardrails.types.GuardEvent
            The guardrails event to evaluate.

        Returns
        -------
        theaios.guardrails.types.Decision
            The guardrails decision.
        """
        from theaios.agent_monitor.types import AgentEvent

        start = time.time()
        decision = self._engine.evaluate(event)
        elapsed_ms = (time.time() - start) * 1000

        # Map guardrails outcome to agent event type
        outcome = getattr(decision, "outcome", "allow")
        if outcome == "deny":
            event_type = "denial"
        elif outcome == "require_approval":
            event_type = "approval_request"
        elif outcome in ("allow", "log", "redact"):
            event_type = "action"
        else:
            event_type = "guardrail_trigger"

        agent_name = getattr(event, "agent", "unknown")
        session_id = getattr(event, "session_id", None)

        data: dict[str, object] = {
            "scope": getattr(event, "scope", ""),
            "outcome": outcome,
            "rule": getattr(decision, "rule", None),
            "reason": getattr(decision, "reason", None),
            "severity": getattr(decision, "severity", None),
            "dry_run": getattr(decision, "dry_run", False),
            "matched_rules": getattr(decision, "matched_rules", []),
        }

        agent_event = AgentEvent(
            timestamp=time.time(),
            agent=agent_name,
            event_type=event_type,
            data=data,
            session_id=session_id,
            latency_ms=round(elapsed_ms, 3),
        )

        self._monitor.record(agent_event)
        return decision
