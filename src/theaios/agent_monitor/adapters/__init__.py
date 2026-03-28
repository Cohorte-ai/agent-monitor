"""Adapters for integrating the agent monitor with other systems."""

from __future__ import annotations

__all__ = [
    "GuardrailsMonitor",
]


def __getattr__(name: str) -> object:
    if name == "GuardrailsMonitor":
        from theaios.agent_monitor.adapters.guardrails import GuardrailsMonitor

        return GuardrailsMonitor
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
