# Events

Events are the core input to the monitor. Every agent action, guardrail trigger, denial, cost record, and error is recorded as an event.

---

## AgentEvent

```python
@dataclass
class AgentEvent:
    timestamp: float                    # Required. Epoch seconds (use time.time())
    agent: str                          # Required. Agent identifier
    event_type: str                     # Required. "action", "denial", etc.
    data: dict[str, object] = {}        # Arbitrary event data
    session_id: str | None = None       # Optional session identifier
    user: str | None = None             # Optional user identifier
    cost_usd: float | None = None       # Optional cost in USD
    latency_ms: float | None = None     # Optional latency in milliseconds
    tags: list[str] = []                # Optional tags for filtering
```

### Event Types

| Type | When to use | What it feeds |
|------|------------|---------------|
| `action` | After an agent performs any action (LLM call, tool call, etc.) | `action_count`, `event_count` |
| `guardrail_trigger` | After a guardrail evaluates (non-denial outcomes: allow, redact, log) | `event_count` |
| `denial` | When a guardrail denies a request | `denial_count`, `denial_rate` |
| `approval_request` | When an action requires human approval | `approval_count` |
| `approval_response` | When a human responds to an approval request | `approval_count` |
| `cost` | To record a cost event explicitly | `cost_total`, `cost_per_minute` |
| `error` | When something goes wrong | `error_count` |
| `session_start` | When an agent session begins | `event_count` |
| `session_end` | When an agent session ends | `event_count` |

### Fields Used by Metrics

The metrics engine extracts specific fields from `AgentEvent`:

| Field | Used by | Type |
|-------|---------|------|
| `latency_ms` | `avg_latency_ms` | float |
| `cost_usd` | `cost_total`, `cost_per_minute` | float |
| `event_type` | `action_count`, `denial_count`, `denial_rate`, `error_count`, `approval_count` | string |

All other fields (including anything in `data`) are stored as-is and available for compliance export and querying.

---

## Recording Events

### Python API

```python
import time
from theaios.agent_monitor import Monitor, load_config, AgentEvent

monitor = Monitor(load_config("monitor.yaml"))

# Record an action (e.g., LLM call)
monitor.record(AgentEvent(
    timestamp=time.time(),
    event_type="action",
    agent="sales-agent",
    cost_usd=0.007,
    latency_ms=350.0,
    data={"model": "gpt-4"},
))

# Record a denial
monitor.record(AgentEvent(
    timestamp=time.time(),
    event_type="denial",
    agent="sales-agent",
    data={"rule": "block-injection", "severity": "critical"},
))

# Record an error
monitor.record(AgentEvent(
    timestamp=time.time(),
    event_type="error",
    agent="sales-agent",
    data={"error_type": "TimeoutError", "message": "LLM call timed out"},
))
```

### Return Value

`monitor.record()` returns `None`. It does not return a boolean.

When an agent is killed, the event is silently dropped -- not stored, not processed. To check whether an agent is killed before recording, use `monitor.is_killed(agent)`.

---

## EventStore

The EventStore is the append-only JSONL log of all events. You don't interact with it directly -- the `Monitor` wraps it -- but it's useful to understand.

### Querying Events

```python
# All events (returns list of dicts, not AgentEvent objects)
events = monitor.get_events()

# Filter by agent
events = monitor.get_events(agent="sales-agent")

# Filter by event type
events = monitor.get_events(event_type="error")

# Filter by time range (ISO timestamps)
events = monitor.get_events(since="2026-03-01T00:00:00", until="2026-03-28T00:00:00")

# Limit results
events = monitor.get_events(limit=10)
```

### Pruning

Over time, the event store grows. Flush metrics streams to control memory:

```python
monitor.flush()  # Clear in-memory metric streams (persisted events are not affected)
```

---

## Timestamps

`timestamp` is a **required** field on `AgentEvent`. Always provide it using `time.time()`:

```python
import time

start = time.time()
response = llm.generate(prompt)
end = time.time()

monitor.record(AgentEvent(
    timestamp=end,
    event_type="action",
    agent="my-agent",
    latency_ms=(end - start) * 1000,
    cost_usd=response.usage.total_cost,
))
```

---

## Session Tracking

The optional `session_id` field enables session-level kill switches. If you track sessions, include the ID on every event:

```python
import time

monitor.record(AgentEvent(
    timestamp=time.time(),
    event_type="action",
    agent="sales-agent",
    session_id="sess-abc-123",
    cost_usd=0.007,
    latency_ms=350.0,
))

# Later: kill the entire session
monitor.kill_session("sess-abc-123")
```
