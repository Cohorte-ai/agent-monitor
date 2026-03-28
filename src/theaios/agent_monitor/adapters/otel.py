"""OpenTelemetry adapter — exports agent events as OTel spans and metrics.

This is a stub that provides a helpful ImportError when OTel is not installed.
Install with: pip install theaios-agent-monitor[otel]
"""

from __future__ import annotations

from typing import Any


class OTelExporter:
    """Exports agent events to OpenTelemetry.

    Requires ``opentelemetry-api`` and ``opentelemetry-sdk``. Install via::

        pip install theaios-agent-monitor[otel]
    """

    def __init__(self, service_name: str = "theaios-agent-monitor") -> None:
        try:
            from opentelemetry import trace  # noqa: F401
            from opentelemetry.sdk.trace import TracerProvider  # noqa: F401
        except ImportError as e:
            raise ImportError(
                "OpenTelemetry is required for OTelExporter. "
                "Install with: pip install theaios-agent-monitor[otel]"
            ) from e

        self._service_name = service_name
        self._setup_tracer()

    def _setup_tracer(self) -> None:
        """Initialize the OTel tracer provider."""
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider

        resource = Resource.create({"service.name": self._service_name})
        provider = TracerProvider(resource=resource)
        trace.set_tracer_provider(provider)
        self._tracer = trace.get_tracer(self._service_name)

    def export_event(self, event: Any) -> None:  # noqa: ANN401
        """Export an AgentEvent as an OTel span.

        Parameters
        ----------
        event : theaios.agent_monitor.types.AgentEvent
            The event to export.
        """
        with self._tracer.start_as_current_span(
            name=f"agent.{getattr(event, 'event_type', 'unknown')}",
        ) as span:
            span.set_attribute("agent.name", getattr(event, "agent", ""))
            span.set_attribute("agent.event_type", getattr(event, "event_type", ""))
            span.set_attribute("agent.session_id", getattr(event, "session_id", "") or "")
            span.set_attribute("agent.user", getattr(event, "user", "") or "")

            cost = getattr(event, "cost_usd", None)
            if cost is not None:
                span.set_attribute("agent.cost_usd", float(cost))

            latency = getattr(event, "latency_ms", None)
            if latency is not None:
                span.set_attribute("agent.latency_ms", float(latency))

            tags = getattr(event, "tags", [])
            if tags:
                span.set_attribute("agent.tags", tags)
