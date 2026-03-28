# Events

Events are the core input to the monitor. Every agent action, LLM call, guardrail decision, and error is recorded as an event.

---

## AgentEvent

```python
@dataclass
class AgentEvent:
    event_type: str                     # "llm_call", "tool_call", etc.
    agent: str                          # Agent identifier
    data: dict[str, object] = {}        # Arbitrary event data
    timestamp: float | None = None      # Epoch seconds, defaults to time.time()
    session_id: str | None = None       # Optional session identifier
```

### Event Types

| Type | When to use | Expected `data` fields |
|------|------------|----------------------|
| `llm_call` | After an LLM API call completes | `model`, `prompt_tokens`, `completion_tokens`, `latency_ms`, `cost` |
| `tool_call` | After an agent tool invocation | `tool`, `latency_ms`, `success` |
| `guardrail_decision` | After a guardrail evaluates | `rule`, `outcome` (allow/deny/redact), `severity` |
| `error` | When something goes wrong | `error_type`, `message` |
| `custom` | Anything else | Your choice |

### Fields Used by Metrics

The metrics engine extracts specific fields from `data`:

| Field | Used by | Type |
|-------|---------|------|
| `data.latency_ms` | `avg_latency_ms` | float |
| `data.cost` | `cost_per_minute` | float |
| `data.outcome` | `denial_rate` | string ("allow" or "deny") |

All other fields in `data` are stored as-is and available for compliance export and querying.

---

## Recording Events

### Python API

```python
from theaios.agent_monitor import Monitor, load_config, AgentEvent

monitor = Monitor(load_config("monitor.yaml"))

# Record an LLM call
monitor.record(AgentEvent(
    event_type="llm_call",
    agent="sales-agent",
    data={"model": "gpt-4", "latency_ms": 350.0, "cost": 0.007},
))

# Record a guardrail denial
monitor.record(AgentEvent(
    event_type="guardrail_decision",
    agent="sales-agent",
    data={"rule": "block-injection", "outcome": "deny", "severity": "critical"},
))

# Record an error
monitor.record(AgentEvent(
    event_type="error",
    agent="sales-agent",
    data={"error_type": "TimeoutError", "message": "LLM call timed out"},
))
```

### CLI

```bash
agent-monitor record --config monitor.yaml \
  --event '{"event_type":"llm_call","agent":"sales-agent","data":{"latency_ms":350,"cost":0.007}}'
```

### Return Value

`monitor.record()` returns:

- `True` -- event was accepted and processed
- `False` / `None` -- event was rejected (agent is killed)

Always check the return value if your agent needs to react to kill switches.

---

## EventStore

The EventStore is the in-memory append-only log of all events. You don't interact with it directly -- the `Monitor` wraps it -- but it's useful to understand.

### Querying Events

```python
# All events
events = monitor.get_events()

# Filter by agent
events = monitor.get_events(agent="sales-agent")

# Filter by event type
events = monitor.get_events(event_type="error")

# Most recent N events
events = monitor.get_events(tail=10)
```

### Pruning

Over time, the event store grows. Prune old events to control memory:

```python
monitor.flush()  # Clear all events and reset metrics
```

---

## Timestamps

If `timestamp` is not provided, the monitor assigns `time.time()` when the event is recorded. For accurate metrics, provide timestamps from the point where the event actually occurred:

```python
import time

start = time.time()
response = llm.generate(prompt)
end = time.time()

monitor.record(AgentEvent(
    event_type="llm_call",
    agent="my-agent",
    timestamp=end,
    data={
        "latency_ms": (end - start) * 1000,
        "cost": response.usage.total_cost,
    },
))
```

---

## Session Tracking

The optional `session_id` field enables session-level kill switches. If you track sessions, include the ID on every event:

```python
monitor.record(AgentEvent(
    event_type="llm_call",
    agent="sales-agent",
    session_id="sess-abc-123",
    data={"latency_ms": 350.0, "cost": 0.007},
))

# Later: kill the entire session
monitor.kill_session("sess-abc-123")
```
