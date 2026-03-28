# Concepts

How theaios-agent-monitor works under the hood.

---

## The Event Model

Everything in agent-monitor starts with an **event** -- something happening in your agentic system that needs to be recorded and analyzed.

```python
AgentEvent(
    event_type="llm_call",               # What kind of event
    agent="sales-agent",                  # Which agent
    data={                                # Arbitrary event data
        "model": "gpt-4",
        "prompt_tokens": 150,
        "completion_tokens": 80,
        "latency_ms": 350.0,
        "cost": 0.007,
    },
    timestamp=1234567890.0,               # Optional: defaults to time.time()
    session_id="sess-123",                # Optional: for session-level kill
)
```

The `data` dict is freeform -- you put whatever fields are relevant. The metrics engine knows how to extract `latency_ms`, `cost`, and `outcome` from standard locations, but everything else is stored as-is for compliance export and auditing.

### Event Types

| Event Type | When to record | Typical data fields |
|-----------|----------------|-------------------|
| `llm_call` | An LLM API call completes | `model`, `prompt_tokens`, `completion_tokens`, `latency_ms`, `cost` |
| `tool_call` | An agent calls a tool | `tool`, `latency_ms`, `success` |
| `guardrail_decision` | A guardrail evaluates an event | `rule`, `outcome` (allow/deny/redact), `severity` |
| `error` | Something goes wrong | `error_type`, `message` |
| `custom` | Anything else | Your choice |

---

## The Monitor Pipeline

When `monitor.record(event)` is called, the event flows through six stages:

```
Event arrives
    |
    +-- 1. Kill Switch Check
    |     Is this agent killed?
    |     YES --> reject event, return False
    |     NO  --> continue
    |
    +-- 2. Event Storage
    |     Append to the EventStore (in-memory, append-only)
    |
    +-- 3. Metrics Computation
    |     Update the MetricsEngine with the new event
    |     Compute rolling window metrics
    |
    +-- 4. Baseline Update
    |     Feed current metric values into the BaselineTracker
    |     Update mean and stddev via Welford's algorithm
    |
    +-- 5. Anomaly Detection
    |     For each anomaly rule, compute z-score against baseline
    |     If z-score > threshold --> trigger alert
    |
    +-- 6. Kill Switch Evaluation
          For each kill policy, check metric against threshold
          If exceeded --> kill the agent automatically
```

This entire pipeline runs synchronously and in-process. No external calls. No background threads. No message queues. The pipeline adds microseconds of overhead per event.

---

## Metrics Engine

The metrics engine computes four real-time metrics over a configurable rolling window:

| Metric | How it's computed | Source field |
|--------|------------------|-------------|
| `event_count` | Count of events in the window | -- |
| `denial_rate` | Fraction of `guardrail_decision` events with `outcome=deny` | `data.outcome` |
| `cost_per_minute` | Sum of `cost` fields divided by window duration in minutes | `data.cost` |
| `avg_latency_ms` | Mean of `latency_ms` fields for events in the window | `data.latency_ms` |

The rolling window is configured by `metrics.window_seconds` (default: 300 seconds). Events older than the window are excluded from the snapshot.

### MetricSnapshot

```python
@dataclass
class MetricSnapshot:
    agent: str
    event_count: int = 0
    denial_rate: float = 0.0
    cost_per_minute: float = 0.0
    avg_latency_ms: float = 0.0
    timestamp: float = ...
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
    Baselines require `min_samples` data points before z-scores are computed. This prevents false alerts during cold start. Default: 20 samples.

---

## Anomaly Detection

Anomaly rules define when to trigger alerts. Each rule specifies:

- **metric** -- which metric to monitor
- **agent** -- which agent (or `*` for all)
- **z_score_threshold** -- how many standard deviations before alerting
- **severity** -- alert severity (critical, high, medium, low)
- **cooldown_seconds** -- minimum time between repeated alerts for the same rule

```yaml
anomaly_rules:
  - name: cost-spike
    metric: cost_per_minute
    agent: "*"
    z_score_threshold: 2.5
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

When an agent is killed, `monitor.record()` returns `False` and the event is not processed. This is the fastest possible circuit breaker -- it runs before any metrics computation.

### Auto-Kill Policies

Kill policies evaluate after every metric snapshot. If a metric exceeds the threshold, the corresponding action fires automatically:

```yaml
kill_switch:
  policies:
    - name: auto-kill-on-high-cost
      metric: cost_per_minute
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
| `soc2` | SOC 2 Type II audits | Events, summary, controls, generated_at |
| `gdpr` | GDPR data processing records | Events, agents (data subjects), processing activities |
| `json` | Generic machine-readable export | Events, summary |

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
