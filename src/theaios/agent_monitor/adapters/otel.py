"""OpenTelemetry export: every recorded event becomes a span on your tracer provider.

Requires ``opentelemetry-api`` (``pip install "theaios-agent-monitor[otel]"``). The exporter
never configures OpenTelemetry for you: it uses the tracer provider you pass, or the global
one your application (or Langfuse) set up. Spans carry Langfuse's observation attributes, so
a Langfuse client on the same provider shows them as guardrail, tool and agent observations
once it admits this library's instrumentation scope::

    from langfuse import Langfuse
    from langfuse._client.span_filter import is_default_export_span
    from theaios.agent_monitor.adapters.otel import INSTRUMENTATION_SCOPE

    Langfuse(should_export_span=lambda s: is_default_export_span(s)
             or s.instrumentation_scope.name == INSTRUMENTATION_SCOPE)
"""

from __future__ import annotations

import json
from typing import Any

INSTRUMENTATION_SCOPE = "theaios-agent-monitor"

# event_type -> (Langfuse observation type, level)
_KIND = {
    "denial": ("guardrail", "WARNING"),
    "guardrail_trigger": ("guardrail", "WARNING"),
    "approval_request": ("guardrail", "DEFAULT"),
    "approval_response": ("guardrail", "DEFAULT"),
    "action": ("tool", "DEFAULT"),
    "error": ("tool", "ERROR"),
    "cost": ("generation", "DEFAULT"),
}


class OTelExporter:
    """Exports agent events as OpenTelemetry spans. Attach with ``monitor.add_exporter(...)``.

    Parameters
    ----------
    tracer_provider : TracerProvider, optional
        Where spans go. Default: the global provider. The exporter never sets the global
        provider (0.1 did, which replaced the application's).
    service_name : str, optional
        Kept for compatibility with 0.1; the service name belongs to your provider's resource.
    """

    def __init__(self, tracer_provider: Any = None, service_name: str | None = None) -> None:  # noqa: ANN401
        try:
            from opentelemetry import trace
        except ImportError as e:
            raise ImportError(
                "OpenTelemetry is required for OTelExporter. "
                'Install with: pip install "theaios-agent-monitor[otel]"'
            ) from e
        from theaios.agent_monitor import __version__

        provider = tracer_provider if tracer_provider is not None else trace.get_tracer_provider()
        self._tracer = provider.get_tracer(INSTRUMENTATION_SCOPE, __version__)
        self._service_name = service_name

    def export_event(self, event: Any) -> None:  # noqa: ANN401
        """Export one :class:`~theaios.agent_monitor.types.AgentEvent` as a span."""
        event_type = str(getattr(event, "event_type", "") or "unknown")
        kind, level = _KIND.get(event_type, ("span", "DEFAULT"))
        data = getattr(event, "data", None) or {}
        tool = data.get("tool") if isinstance(data, dict) else None
        name = f"{event_type}:{tool}" if tool else f"agent.{event_type}"
        attributes: dict[str, Any] = {
            "agent.name": str(getattr(event, "agent", "") or ""),
            "agent.event_type": event_type,
            "langfuse.observation.type": kind,
            "langfuse.observation.level": level,
        }
        session = getattr(event, "session_id", None)
        user = getattr(event, "user", None)
        if session:
            attributes["session.id"] = str(session)
            attributes["agent.session_id"] = str(session)
        if user:
            attributes["user.id"] = str(user)
            attributes["agent.user"] = str(user)
        if isinstance(data, dict):
            reason = data.get("reason")
            if reason:
                attributes["langfuse.observation.status_message"] = str(reason)[:1000]
            for key, value in data.items():
                attributes[f"langfuse.observation.metadata.{key}"] = _attr(value)
        cost = getattr(event, "cost_usd", None)
        if cost is not None:
            attributes["agent.cost_usd"] = float(cost)
            attributes["langfuse.observation.cost_details"] = json.dumps({"total": float(cost)})
        latency = getattr(event, "latency_ms", None)
        if latency is not None:
            attributes["agent.latency_ms"] = float(latency)
        tags = getattr(event, "tags", None)
        if tags:
            attributes["agent.tags"] = [str(t) for t in tags]
        if event_type == "cost" and isinstance(data, dict) and data.get("model"):
            attributes["gen_ai.request.model"] = str(data["model"])  # a real model call
            attributes["langfuse.observation.model.name"] = str(data["model"])
        # The event's timestamp is when it ended; its latency, if any, is how long it took.
        timestamp = getattr(event, "timestamp", None)
        end = int(float(timestamp) * 1e9) if timestamp else None
        start = end - int(float(latency) * 1e6) if end is not None and latency else end
        span = self._tracer.start_span(name, attributes=attributes, start_time=start)
        span.end(end_time=end)


def _attr(value: object) -> str | int | float | bool:
    """An OpenTelemetry attribute value: scalars as is, the rest as JSON text."""
    if isinstance(value, (str, bool, int, float)):
        return value
    return json.dumps(value, default=str, sort_keys=True)[:2000]
