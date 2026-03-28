# Concepts

How theaios-agent-monitor works under the hood.

---

## The Event Model

Everything in agent-monitor starts with an **event** -- something happening in your agentic system that needs to be recorded and analyzed.

```python
import time

AgentEvent(
    timestamp=time.time(),                # Required: epoch seconds
    agent="sales-agent",                  # Required: which agent
    event_type="action",                  # Required: what kind of event
    data={                                # Optional: arbitrary event data
        "model": "gpt-4",
        "prompt_tokens": 150,
        "completion_tokens": 80,
    },
    cost_usd=0.007,                       # Optional: cost in USD
    latency_ms=350.0,                     # Optional: latency in ms
    session_id="sess-123",                # Optional: for session-level kill
    user="user@example.com",              # Optional: user identifier
    tags=["production"],                  # Optional: tags for filtering
)
```

Cost and latency are top-level fields on `AgentEvent` (not inside `data`). The `data` dict is freeform -- you put whatever additional fields are relevant. Everything is stored as-is for compliance export and auditing.

### Event Types

| Event Type | When to record | What it feeds |
|-----------|----------------|---------------|
| `action` | An agent performs an action (LLM call, tool call, etc.) | `action_count`, `event_count` |
| `guardrail_trigger` | A guardrail evaluates (non-denial: allow, redact, log) | `event_count` |
| `denial` | A guardrail denies a request | `denial_count`, `denial_rate` |
| `approval_request` | An action requires human approval | `approval_count` |
| `approval_response` | A human responds to an approval request | `approval_count` |
| `cost` | An explicit cost record | `cost_total`, `cost_per_minute` |
| `error` | Something goes wrong | `error_count` |
| `session_start` | An agent session begins | `event_count` |
| `session_end` | An agent session ends | `event_count` |

---

## The Monitor Pipeline

When `monitor.record(event)` is called, the event flows through seven stages:

```
Event arrives
    |
    +-- 1. Kill Switch Check
    |     Is this agent/session killed?
    |     YES --> silently drop event, return None
    |     NO  --> continue
    |
    +-- 2. Agent Track Filter
    |     Is this agent/event_type tracked by config?
    |     NO  --> silently drop event
    |     YES --> continue
    |
    +-- 3. Event Storage
    |     Append to the EventStore (JSONL on disk)
    |
    +-- 4. Metrics Computation
    |     Update the MetricsEngine with the new event
    |     Compute rolling window metrics
    |
    +-- 5. Baseline Update
    |     Feed current metric values into the BaselineTracker
    |     Update mean and stddev via Welford's algorithm
    |
    +-- 6. Anomaly Detection
    |     For each anomaly rule, compute z-score against baseline
    |     If z-score > threshold --> trigger alert
    |
    +-- 7. Kill Switch Evaluation
          For each kill policy, check metric against threshold
          If exceeded --> kill the agent automatically
```

This entire pipeline runs synchronously and in-process. No external calls. No background threads. No message queues. The pipeline adds microseconds of overhead per event.

---

## Metrics Engine

The metrics engine computes rolling-window metrics for each agent independently. Key metrics:

| Metric | How it's computed | Source field |
|--------|------------------|-------------|
| `event_count` | Count of events in the window | -- |
| `action_count` | Count of `action` events | `event_type` |
| `denial_count` | Count of `denial` events | `event_type` |
| `denial_rate` | `denial_count / (action_count + denial_count)` | `event_type` |
| `approval_count` | Count of approval events | `event_type` |
| `error_count` | Count of `error` events | `event_type` |
| `cost_total` | Sum of `cost_usd` in the window | `cost_usd` |
| `cost_per_minute` | `cost_total / (window_seconds / 60)` | `cost_usd` |
| `avg_latency_ms` | Mean of `latency_ms` for events with latency | `latency_ms` |

The rolling window is configured by `metrics.default_window_seconds` (default: 300 seconds). Events older than the window are automatically excluded.

### MetricSnapshot

```python
@dataclass
class MetricSnapshot:
    agent: str
    window_seconds: int
    timestamp: float
    event_count: int = 0
    action_count: int = 0
    denial_count: int = 0
    denial_rate: float = 0.0
    approval_count: int = 0
    approval_rate: float = 0.0
    error_count: int = 0
    cost_total: float = 0.0
    cost_per_minute: float = 0.0
    avg_latency_ms: float = 0.0
```

---

## Baselines (Welford's Algorithm)

The baseline tracker uses **Welford's online algorithm** to maintain running mean and standard deviation for each metric, per agent. This is an incremental algorithm -- it doesn't store historical values, just the running statistics.

After each metric computation, the current value is fed into the baseline:

```
update("sales-agent", "cost_per_minute", 0.03)
    --> count += 1
    --> delta = value - mean
    --> mean += delta / count
    --> M2 += delta * (value - mean)
    --> variance = M2 / count
    --> stddev = sqrt(variance)
```

The z-score for any new value is:

```
z = (value - mean) / stddev
```

A z-score of 3.0 means the value is 3 standard deviations above the mean -- a strong signal of anomalous behavior.

!!! tip "Min samples"
    Baselines require `min_samples` data points before z-scores are computed. This prevents false alerts during cold start. Default: 30 samples.

---

## Anomaly Detection

Anomaly rules define when to trigger alerts. Each rule specifies:

- **metric** -- which metric to monitor
- **z_threshold** -- how many standard deviations before alerting
- **severity** -- alert severity (critical, high, medium, low)
- **cooldown_seconds** -- minimum time between repeated alerts for the same rule

```yaml
anomaly_detection:
  enabled: true
  rules:
    - name: cost-spike
      metric: cost_per_minute
      z_threshold: 2.5
      severity: critical
      cooldown_seconds: 600
```

When a metric's z-score exceeds the threshold, the detector:

1. Creates an alert with the rule name, metric value, z-score, and severity
2. Dispatches the alert to all configured channels
3. Records the alert time for cooldown tracking

The cooldown prevents alert storms. If `cooldown_seconds: 600`, the same rule won't fire again for 10 minutes even if the anomaly persists.

---

## Kill Switches

Kill switches are the most important safety mechanism. They provide three levels of control:

| Level | Method | What it does |
|-------|--------|-------------|
| Agent | `kill_agent(name, reason)` | Blocks all events for a specific agent |
| Session | `kill_session(session_id)` | Blocks all events for a specific session |
| Global | `kill_global(reason)` | Blocks all events for all agents |

When an agent is killed, `monitor.record()` silently drops the event (returns `None`). The event is not processed. This is the fastest possible circuit breaker -- it runs before any metrics computation.

### Auto-Kill Policies

Kill policies evaluate after every metric snapshot. If a metric exceeds the threshold, the corresponding action fires automatically:

```yaml
kill_switch:
  enabled: true
  policies:
    - name: auto-kill-on-high-cost
      metric: cost_per_minute
      operator: ">"
      threshold: 5.0
      action: kill_agent
      severity: critical
```

Actions: `kill_agent`, `kill_session`, `kill_global`.

### Persistence

Kill state can be persisted to disk. On restart, the monitor loads the saved state -- agents that were killed stay killed until explicitly revived.

---

## Alert Channels

Alerts are dispatched to one or more channels:

| Channel | Output | Use case |
|---------|--------|----------|
| `console` | stderr | Development, debugging |
| `file` | JSONL file | Production logging, audit trail |
| `webhook` | HTTP POST | PagerDuty, Slack, OpsGenie |

All channels receive the same alert payload:

```json
{
  "timestamp": "2026-03-28T14:23:01.123Z",
  "rule": "cost-spike",
  "agent": "sales-agent",
  "severity": "critical",
  "message": "cost_per_minute z-score 4.2 exceeds threshold 2.5",
  "metric_value": 2.5,
  "z_score": 4.2
}
```

---

## Compliance Export

The compliance exporter generates reports from the event store. Three formats are supported:

| Format | Purpose | Fields |
|--------|---------|--------|
| `soc2` | SOC 2 Type II audits | Events, summary, access controls, guardrail enforcement |
| `gdpr` | GDPR data processing records | Events, data subjects, processing activities |
| `json` | Generic machine-readable export | Events, filters, total count |

Reports can be filtered by agent, time range, and event type.

---

## Performance

The monitor is designed for inline use -- it runs in the same process as your agent.

| Metric | Value |
|--------|-------|
| Record + metrics computation | <0.1ms per event |
| Baseline update | <0.01ms per metric |
| Anomaly detection | <0.01ms per rule |
| Memory per event | ~200 bytes |
| Dependencies | 3 (pyyaml, click, rich) |

This is fast because there are no external calls, no serialization overhead, and no background threads. Everything is a pure in-memory computation.
