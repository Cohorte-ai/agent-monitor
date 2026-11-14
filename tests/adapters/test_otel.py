"""OTelExporter: spans on the application's provider, never a hijacked global one."""

from __future__ import annotations

import time
import warnings

import pytest

pytest.importorskip("opentelemetry.sdk")

from opentelemetry import trace  # noqa: E402
from opentelemetry.sdk.trace import TracerProvider  # noqa: E402
from opentelemetry.sdk.trace.export import SimpleSpanProcessor  # noqa: E402
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter  # noqa: E402

from theaios.agent_monitor import AgentEvent, Monitor  # noqa: E402
from theaios.agent_monitor.adapters.otel import INSTRUMENTATION_SCOPE, OTelExporter  # noqa: E402
from theaios.agent_monitor.types import MonitorConfig  # noqa: E402


def _provider() -> tuple[TracerProvider, InMemorySpanExporter]:
    memory = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(memory))
    return provider, memory


def test_the_exporter_never_replaces_the_global_provider() -> None:
    before = trace.get_tracer_provider()
    provider, _ = _provider()
    OTelExporter(tracer_provider=provider)
    OTelExporter()
    assert trace.get_tracer_provider() is before


def test_recorded_events_become_spans_with_langfuse_attributes(basic_config: MonitorConfig) -> None:
    provider, memory = _provider()
    monitor = Monitor(basic_config)
    monitor.add_exporter(OTelExporter(tracer_provider=provider))
    now = time.time()
    monitor.record(
        AgentEvent(
            timestamp=now,
            agent="assistant",
            event_type="denial",
            data={
                "tool": "send_email",
                "component": "guardrails",
                "codes": ["untrusted_to_send"],
                "reason": "tainted",
            },
            session_id="t1",
            user="alice",
            latency_ms=12.0,
        )
    )
    monitor.record(
        AgentEvent(
            timestamp=now,
            agent="assistant",
            event_type="cost",
            data={"model": "gpt-4.1-mini"},
            cost_usd=0.0021,
        )
    )
    deny, cost = memory.get_finished_spans()
    assert deny.name == "denial:send_email"
    assert deny.instrumentation_scope.name == INSTRUMENTATION_SCOPE
    a = dict(deny.attributes or {})
    assert (
        a["langfuse.observation.type"] == "guardrail"
        and a["langfuse.observation.level"] == "WARNING"
    )
    assert a["user.id"] == "alice" and a["session.id"] == "t1"
    assert a["langfuse.observation.status_message"] == "tainted"
    assert a["langfuse.observation.metadata.codes"] == '["untrusted_to_send"]'
    assert abs((deny.end_time - deny.start_time) / 1e6 - 12.0) < 0.01  # its latency
    c = dict(cost.attributes or {})
    assert c["gen_ai.request.model"] == "gpt-4.1-mini" and c["agent.cost_usd"] == 0.0021
    assert "gen_ai.request.model" not in a  # only real model calls claim gen_ai


def test_a_failing_exporter_never_stops_recording(basic_config: MonitorConfig) -> None:
    class Broken:
        def export_event(self, event: AgentEvent) -> None:
            raise RuntimeError("collector down")

    monitor = Monitor(basic_config)
    monitor.add_exporter(Broken())
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        monitor.record(AgentEvent(timestamp=time.time(), agent="a", event_type="action"))
    assert len(monitor.get_events()) == 1
    assert any("collector down" in str(w.message) for w in caught)


def test_add_exporter_refuses_what_cannot_export(basic_config: MonitorConfig) -> None:
    with pytest.raises(TypeError):
        Monitor(basic_config).add_exporter(object())  # type: ignore[arg-type]
