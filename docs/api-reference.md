# Python API Reference

## Core Functions

### `load_config(path) -> MonitorConfig`

Load and validate a YAML config file.

```python
from theaios.agent_monitor import load_config

config = load_config("monitor.yaml")
```

Raises `FileNotFoundError` if the file doesn't exist, `ConfigError` if validation fails.

---

## Monitor

### `Monitor(config)`

The main monitoring engine. Create once, record many events.

```python
from theaios.agent_monitor import Monitor, load_config

monitor = Monitor(load_config("monitor.yaml"))
```

On construction, the monitor initializes:

- EventStore (JSONL event log)
- MetricsEngine (rolling window computation)
- BaselineTracker (Welford's algorithm)
- AnomalyDetector (z-score rules)
- KillSwitch (manual and automatic)
- AlertDispatcher (console, file, webhook)
- ComplianceExporter (SOC 2, GDPR, JSON)

### `monitor.record(event) -> None`

Record an agent event through the full monitoring pipeline. Returns `None` (not a boolean).

When the agent is killed, the event is silently dropped.

```python
import time
from theaios.agent_monitor import AgentEvent

monitor.record(AgentEvent(
    timestamp=time.time(),
    event_type="action",
    agent="sales-agent",
    cost_usd=0.007,
    latency_ms=350.0,
    data={"model": "gpt-4"},
))
```

### `monitor.get_metrics(agent, window=None) -> MetricSnapshot`

Get the current metric snapshot for an agent.

```python
snap = monitor.get_metrics("sales-agent")
print(snap.event_count)
print(snap.action_count)
print(snap.denial_count)
print(snap.denial_rate)
print(snap.cost_per_minute)
print(snap.avg_latency_ms)
```

Optional `window` parameter overrides the default window size (in seconds).

### `monitor.get_all_metrics(window=None) -> list[MetricSnapshot]`

Get current metrics for all tracked agents.

### `monitor.get_events(**filters) -> list[dict[str, object]]`

Query stored events with optional filtering. Returns a list of **dicts** (not `AgentEvent` objects).

```python
# All events
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

### `monitor.is_killed(agent, session_id=None) -> bool`

Check if an agent (or session) is killed.

### `monitor.kill_agent(agent, reason="") -> None`

Kill a specific agent.

### `monitor.kill_session(session_id, reason="") -> None`

Kill a specific session.

### `monitor.kill_global(reason="") -> None`

Kill all agents globally.

### `monitor.revive(agent=None, session_id=None) -> None`

Revive a specific agent or session.

```python
monitor.revive(agent="sales-agent")
monitor.revive(session_id="sess-abc-123")
```

### `monitor.revive_global() -> None`

Deactivate global kill switch.

### `monitor.flush() -> None`

Clear all in-memory metric streams. Persisted events and kill state are not affected.

---

## Properties

### `monitor.event_store -> EventStore`

Access the underlying event store.

### `monitor.metrics_engine -> MetricsEngine`

Access the underlying metrics engine.

### `monitor.baseline_tracker -> BaselineTracker`

Access the underlying baseline tracker.

### `monitor.kill_switch_engine -> KillSwitch`

Access the underlying kill switch.

### `monitor.compliance_exporter -> ComplianceExporter`

Access the underlying compliance exporter.

```python
# Export a compliance report via the exporter
output = monitor.compliance_exporter.export(format="soc2")
output = monitor.compliance_exporter.export(format="json", agent="sales-agent")
output = monitor.compliance_exporter.export(format="gdpr", since="2026-03-01T00:00:00")
```

---

## Data Types

### `AgentEvent`

```python
@dataclass
class AgentEvent:
    timestamp: float                    # Required. Epoch seconds.
    agent: str                          # Required. Agent identifier.
    event_type: str                     # Required. Event type string.
    data: dict[str, object] = {}        # Arbitrary event data.
    session_id: str | None = None       # Optional session ID.
    user: str | None = None             # Optional user identifier.
    cost_usd: float | None = None       # Optional cost in USD.
    latency_ms: float | None = None     # Optional latency in ms.
    tags: list[str] = []                # Optional tags.
```

### `MonitorConfig`

```python
@dataclass
class MonitorConfig:
    version: str = "1.0"
    metadata: MonitorMetadata = MonitorMetadata()
    variables: dict[str, object] = {}
    agents: dict[str, AgentTrackConfig] = {}
    storage: StorageConfig = StorageConfig()
    metrics: MetricsEngineConfig = MetricsEngineConfig()
    baselines: BaselineConfig = BaselineConfig()
    anomaly_detection: AnomalyDetectionConfig = AnomalyDetectionConfig()
    kill_switch: KillSwitchConfig = KillSwitchConfig()
    alerts: AlertConfig = AlertConfig()
```

### `MetricSnapshot`

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

### `KillState`

```python
@dataclass
class KillState:
    killed_agents: set[str] = set()
    killed_sessions: set[str] = set()
    global_kill: bool = False
    reasons: dict[str, str] = {}
```

### `Baseline`

```python
@dataclass
class Baseline:
    agent: str
    metric: str
    mean: float = 0.0
    stddev: float = 0.0
    sample_count: int = 0
    last_updated: float = 0.0
```

### `AnomalyAlert`

```python
@dataclass
class AnomalyAlert:
    agent: str
    rule: str
    metric: str
    value: float
    z_score: float
    threshold: float
    severity: str
    message: str
    timestamp: float = 0.0
```

---

## Enums

### `EventType`

| Value | String |
|-------|--------|
| `EventType.ACTION` | `"action"` |
| `EventType.GUARDRAIL_TRIGGER` | `"guardrail_trigger"` |
| `EventType.APPROVAL_REQUEST` | `"approval_request"` |
| `EventType.APPROVAL_RESPONSE` | `"approval_response"` |
| `EventType.DENIAL` | `"denial"` |
| `EventType.COST` | `"cost"` |
| `EventType.ERROR` | `"error"` |
| `EventType.SESSION_START` | `"session_start"` |
| `EventType.SESSION_END` | `"session_end"` |

### `Severity`

| Value | String |
|-------|--------|
| `Severity.CRITICAL` | `"critical"` |
| `Severity.HIGH` | `"high"` |
| `Severity.MEDIUM` | `"medium"` |
| `Severity.LOW` | `"low"` |

### `KillAction`

| Value | String |
|-------|--------|
| `KillAction.KILL_AGENT` | `"kill_agent"` |
| `KillAction.KILL_SESSION` | `"kill_session"` |
| `KillAction.KILL_GLOBAL` | `"kill_global"` |

### `ComplianceFormat`

| Value | String |
|-------|--------|
| `ComplianceFormat.SOC2` | `"soc2"` |
| `ComplianceFormat.GDPR` | `"gdpr"` |
| `ComplianceFormat.JSON` | `"json"` |

### `AlertChannelType`

| Value | String |
|-------|--------|
| `AlertChannelType.CONSOLE` | `"console"` |
| `AlertChannelType.FILE` | `"file"` |
| `AlertChannelType.WEBHOOK` | `"webhook"` |

---

## Validation Sets

| Constant | Contents |
|----------|---------|
| `VALID_EVENT_TYPES` | All valid event type strings |
| `VALID_SEVERITIES` | All valid severity strings |
| `VALID_METRICS` | All valid metric name strings |
| `VALID_KILL_ACTIONS` | All valid kill action strings |
| `VALID_ALERT_CHANNELS` | All valid alert channel type strings |
| `VALID_COMPLIANCE_FORMATS` | All valid compliance format strings |

---

## Exceptions

| Exception | Module | When |
|-----------|--------|------|
| `ConfigError` | `theaios.agent_monitor.config` | Config file is invalid |

---

## Submodules

### `theaios.agent_monitor.events.EventStore`

JSONL event storage. Use `Monitor` instead of this directly.

### `theaios.agent_monitor.metrics.MetricsEngine`

Rolling window metrics computation. Use `Monitor.get_metrics()` instead.

### `theaios.agent_monitor.baselines.BaselineTracker`

Welford's algorithm for running statistics. Can be used standalone:

```python
from theaios.agent_monitor.baselines import BaselineTracker

tracker = BaselineTracker(min_samples=30)
tracker.update("agent", "metric", value)
baseline = tracker.get_baseline("agent", "metric")  # returns Baseline or None
z = tracker.z_score("agent", "metric", new_value)    # returns float or None
```

### `theaios.agent_monitor.anomaly.AnomalyDetector`

Z-score anomaly detection. Used internally by `Monitor`.

### `theaios.agent_monitor.kill_switch.KillSwitch`

Kill switch state management. Used internally by `Monitor`.

### `theaios.agent_monitor.alerts.AlertDispatcher`

Alert channel dispatch. Used internally by `Monitor`.

### `theaios.agent_monitor.compliance.ComplianceExporter`

Compliance report generation. Use `monitor.compliance_exporter` to access.

```python
output = monitor.compliance_exporter.export(format="soc2")
# Returns a JSON string
```

### `theaios.agent_monitor.adapters.guardrails.GuardrailsMonitor`

Guardrails adapter. Wraps a theaios-guardrails `Engine` and auto-records every `evaluate()` call as an agent event.

```python
from theaios.agent_monitor.adapters.guardrails import GuardrailsMonitor

gm = GuardrailsMonitor(engine=guardrails_engine, monitor=monitor)
decision = gm.evaluate(guard_event)  # records the decision automatically
```
