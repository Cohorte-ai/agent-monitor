# Integration Guide

theaios-agent-monitor works with any agentic platform. This page shows how to integrate at every level.

---

## Level 1: Direct API (Simplest)

Record events directly from your agent code.

```python
from theaios.agent_monitor import Monitor, load_config, AgentEvent

monitor = Monitor(load_config("monitor.yaml"))

# After every LLM call
def call_llm(prompt: str, agent: str) -> str:
    start = time.time()
    response = llm.generate(prompt)
    elapsed = (time.time() - start) * 1000

    monitor.record(AgentEvent(
        event_type="llm_call",
        agent=agent,
        data={
            "model": "gpt-4",
            "latency_ms": elapsed,
            "cost": response.usage.total_cost,
        },
    ))

    if monitor.is_killed(agent):
        raise RuntimeError(f"Agent {agent} has been killed")

    return response.text
```

---

## Level 2: Guardrails Adapter

If you use [theaios-guardrails](https://github.com/Cohorte-ai/guardrails), the `GuardrailsMonitor` adapter automatically records every guardrail decision.

```bash
pip install theaios-agent-monitor[guardrails]
```

```python
from theaios.agent_monitor import Monitor, load_config
from theaios.agent_monitor.adapters.guardrails import GuardrailsMonitor
from theaios.guardrails import Engine, load_policy, GuardEvent

# Set up monitor
monitor = Monitor(load_config("monitor.yaml"))
gm = GuardrailsMonitor(monitor=monitor)

# Set up guardrails
engine = Engine(load_policy("guardrails.yaml"))

# Evaluate and record in one step
event = GuardEvent(scope="input", agent="sales-agent", data={"content": user_message})
decision = engine.evaluate(event)
gm.record_decision(agent="sales-agent", decision=decision)

# Metrics now include denial_rate from guardrail decisions
snap = monitor.get_metrics("sales-agent")
print(f"Denial rate: {snap.denial_rate:.1%}")
```

The adapter extracts `outcome`, `rule`, and `severity` from the guardrail decision and records a `guardrail_decision` event.

---

## Level 3: OpenTelemetry Export

Export events and metrics to any OpenTelemetry-compatible backend (Jaeger, Zipkin, Datadog, Honeycomb, etc.).

```bash
pip install theaios-agent-monitor[otel]
```

```python
from theaios.agent_monitor.adapters.otel import OTelExporter

exporter = OTelExporter(
    service_name="my-agent-service",
    endpoint="http://localhost:4318",
)

# Attach to monitor
monitor = Monitor(load_config("monitor.yaml"))
monitor.add_exporter(exporter)

# Events are now exported as OTel spans
# Metrics are exported as OTel metrics
```

!!! note
    The OTel adapter is an optional dependency. Install with `pip install theaios-agent-monitor[otel]`.

---

## Level 4: Custom Adapters

Build your own adapter for any platform. The pattern is:

1. Create a wrapper that holds a reference to the `Monitor`
2. After each relevant operation, call `monitor.record()` with the appropriate event

```python
from theaios.agent_monitor import Monitor, AgentEvent


class MyPlatformMonitor:
    def __init__(self, monitor: Monitor) -> None:
        self.monitor = monitor

    def on_llm_response(self, agent: str, response: dict) -> None:
        self.monitor.record(AgentEvent(
            event_type="llm_call",
            agent=agent,
            data={
                "model": response["model"],
                "latency_ms": response["latency_ms"],
                "cost": response["cost"],
            },
        ))

    def on_tool_call(self, agent: str, tool: str, result: dict) -> None:
        self.monitor.record(AgentEvent(
            event_type="tool_call",
            agent=agent,
            data={
                "tool": tool,
                "latency_ms": result["latency_ms"],
                "success": result["success"],
            },
        ))

    def on_error(self, agent: str, error: Exception) -> None:
        self.monitor.record(AgentEvent(
            event_type="error",
            agent=agent,
            data={
                "error_type": type(error).__name__,
                "message": str(error),
            },
        ))
```

---

## Level 5: HTTP Middleware

For REST API-based agents:

```python
# FastAPI example
from fastapi import Request, HTTPException
from theaios.agent_monitor import Monitor, load_config, AgentEvent

monitor = Monitor(load_config("monitor.yaml"))

@app.middleware("http")
async def monitor_middleware(request: Request, call_next):
    agent = request.headers.get("X-Agent-ID", "default")

    # Check kill switch before processing
    if monitor.is_killed(agent):
        raise HTTPException(503, detail=f"Agent {agent} is currently suspended")

    start = time.time()
    response = await call_next(request)
    elapsed = (time.time() - start) * 1000

    # Record the request as an event
    monitor.record(AgentEvent(
        event_type="llm_call",
        agent=agent,
        data={"latency_ms": elapsed},
    ))

    return response
```

---

## Framework Examples

### LangChain

```python
from langchain.callbacks.base import BaseCallbackHandler
from theaios.agent_monitor import Monitor, AgentEvent

class MonitorCallback(BaseCallbackHandler):
    def __init__(self, monitor: Monitor, agent: str):
        self.monitor = monitor
        self.agent = agent

    def on_llm_end(self, response, **kwargs):
        self.monitor.record(AgentEvent(
            event_type="llm_call",
            agent=self.agent,
            data={"model": response.llm_output.get("model_name", "unknown")},
        ))

    def on_tool_start(self, serialized, input_str, **kwargs):
        self.monitor.record(AgentEvent(
            event_type="tool_call",
            agent=self.agent,
            data={"tool": serialized.get("name", "unknown")},
        ))
```

### CrewAI / AutoGen

```python
# After each agent step
monitor.record(AgentEvent(
    event_type="llm_call",
    agent=agent.name,
    data={
        "model": agent.model,
        "latency_ms": step_time_ms,
        "cost": step_cost,
    },
))
```

---

## Performance Considerations

The monitor is designed for inline (synchronous) use. At <0.1ms per event, it adds no meaningful latency.

**Do:**

- Create the monitor once at startup, reuse for all events
- Use `monitor.record()` synchronously in the hot path
- Load config at application start, not per-request

**Don't:**

- Create a new monitor per request (unnecessary overhead)
- Call `load_config()` per request (unnecessary file I/O)
- Record events asynchronously unless you need to (the sync path is fast enough)
