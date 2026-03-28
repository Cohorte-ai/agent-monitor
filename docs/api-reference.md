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

- EventStore (in-memory event log)
- MetricsEngine (rolling window computation)
- BaselineTracker (Welford's algorithm)
- AnomalyDetector (z-score rules)
- KillSwitch (manual and automatic)
- AlertDispatcher (console, file, webhook)
- ComplianceExporter (SOC 2, GDPR, JSON)

### `monitor.record(event) -> bool | None`

Record an agent event. Returns `True` if accepted, `False`/`None` if the agent is killed.

```python
from theaios.agent_monitor import AgentEvent

result = monitor.record(AgentEvent(
    event_type="llm_call",
    agent="sales-agent",
    data={"latency_ms": 350.0, "cost": 0.007},
))
```

### `monitor.get_metrics(agent) -> MetricSnapshot`

Get the current metric snapshot for an agent.

```python
snap = monitor.get_metrics("sales-agent")
print(snap.event_count)
print(snap.denial_rate)
print(snap.cost_per_minute)
print(snap.avg_latency_ms)
```

### `monitor.get_events(**filters) -> list[AgentEvent]`

Get stored events with optional filtering.

```python
# All events
events = monitor.get_events()

# Filter by agent
events = monitor.get_events(agent="sales-agent")

# Filter by event type
events = monitor.get_events(event_type="error")
```

### `monitor.is_killed(agent) -> bool`

Check if an agent is killed.

### `monitor.kill_agent(agent, reason) -> None`

Kill a specific agent.

### `monitor.revive_agent(agent) -> None`

Revive a killed agent.

### `monitor.kill_session(session_id) -> None`

Kill a specific session.

### `monitor.kill_global(reason) -> None`

Kill all agents globally.

### `monitor.revive_global() -> None`

Revive all agents (clear global kill).

### `monitor.flush() -> None`

Clear all events and reset metrics. Kill state is preserved.

### `monitor.export_compliance(fmt, **filters) -> dict`

Export a compliance report.

```python
report = monitor.export_compliance(fmt="soc2")
report = monitor.export_compliance(fmt="json", agent="sales-agent")
report = monitor.export_compliance(fmt="gdpr", since=start_time, until=end_time)
```

---

## Data Types

### `AgentEvent`

```python
@dataclass
class AgentEvent:
    event_type: str                     # "llm_call", "tool_call", etc.
    agent: str                          # Agent identifier
    data: dict[str, object] = {}        # Arbitrary event data
    timestamp: float | None = None      # Epoch seconds
    session_id: str | None = None       # Optional session ID
```

### `MonitorConfig`

```python
@dataclass
class MonitorConfig:
    version: str = "1.0"
    agent_name: str = ""
    events: list[str] = []
    metrics: dict = {}
    baselines: dict = {}
    anomaly_rules: list[dict] = []
    kill_switch: dict | None = None
    alerts: dict = {}
    compliance: dict = {}
```

### `MetricSnapshot`

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

### `KillState`

```python
@dataclass
class KillState:
    killed_agents: dict[str, str] = {}      # agent -> reason
    killed_sessions: set[str] = set()
    global_kill: bool = False
```

---

## Enums

### `EventType`

| Value | String |
|-------|--------|
| `EventType.LLM_CALL` | `"llm_call"` |
| `EventType.TOOL_CALL` | `"tool_call"` |
| `EventType.GUARDRAIL_DECISION` | `"guardrail_decision"` |
| `EventType.ERROR` | `"error"` |
| `EventType.CUSTOM` | `"custom"` |

### `Severity`

| Value | String |
|-------|--------|
| `Severity.CRITICAL` | `"critical"` |
| `Severity.HIGH` | `"high"` |
| `Severity.MEDIUM` | `"medium"` |
| `Severity.LOW` | `"low"` |

### `MetricName`

| Value | String |
|-------|--------|
| `MetricName.EVENT_COUNT` | `"event_count"` |
| `MetricName.DENIAL_RATE` | `"denial_rate"` |
| `MetricName.COST_PER_MINUTE` | `"cost_per_minute"` |
| `MetricName.AVG_LATENCY_MS` | `"avg_latency_ms"` |

### `KillAction`

| Value | String |
|-------|--------|
| `KillAction.KILL_AGENT` | `"kill_agent"` |
| `KillAction.KILL_SESSION` | `"kill_session"` |
| `KillAction.KILL_GLOBAL` | `"kill_global"` |

---

## Validation Sets

| Constant | Contents |
|----------|---------|
| `VALID_EVENT_TYPES` | All valid event type strings |
| `VALID_SEVERITIES` | All valid severity strings |
| `VALID_METRICS` | All valid metric name strings |
| `VALID_KILL_ACTIONS` | All valid kill action strings |

---

## Exceptions

| Exception | Module | When |
|-----------|--------|------|
| `ConfigError` | `theaios.agent_monitor.config` | Config file is invalid |

---

## Submodules

### `theaios.agent_monitor.events.EventStore`

Low-level event storage. Use `Monitor` instead of this directly.

### `theaios.agent_monitor.metrics.MetricsEngine`

Low-level metrics computation. Use `Monitor.get_metrics()` instead.

### `theaios.agent_monitor.baselines.BaselineTracker`

Welford's algorithm for running statistics. Can be used standalone:

```python
from theaios.agent_monitor.baselines import BaselineTracker

tracker = BaselineTracker(min_samples=20)
tracker.update("agent", "metric", value)
z = tracker.z_score("agent", "metric", new_value)
```

### `theaios.agent_monitor.anomaly.AnomalyDetector`

Z-score anomaly detection. Used internally by `Monitor`.

### `theaios.agent_monitor.kill_switch.KillSwitch`

Kill switch state management. Used internally by `Monitor`.

### `theaios.agent_monitor.alerts.AlertDispatcher`

Alert channel dispatch. Used internally by `Monitor`.

### `theaios.agent_monitor.compliance.ComplianceExporter`

Compliance report generation. Use `Monitor.export_compliance()` instead.

### `theaios.agent_monitor.adapters.guardrails.GuardrailsMonitor`

Guardrails adapter. Bridges theaios-guardrails decisions into the monitor pipeline.
