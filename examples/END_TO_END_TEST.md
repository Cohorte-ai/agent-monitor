# theaios-agent-monitor — End-to-End Test Guide

Test every feature from a fresh install. No repo cloning needed, no API keys, no cost.

**Requirements:** Python 3.10+
**Estimated time:** ~10 minutes
**Cost:** $0 (pure in-process monitoring, no external calls)

---

## Setup

### macOS / Linux

```bash
mkdir monitor-test && cd monitor-test
python3 -m venv .venv
source .venv/bin/activate
pip install theaios-agent-monitor
```

### Windows (PowerShell)

```powershell
mkdir monitor-test; cd monitor-test
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install theaios-agent-monitor
```

---

## Generate test data

Create a config file for testing. On macOS/Linux use the commands below. On Windows, create these files manually or use the Python script at the end of this section.

### Config file: `basic.yaml`

```bash
cat > basic.yaml << 'EOF'
version: "1.0"
agent_name: test-agent

events:
  - llm_call
  - tool_call
  - guardrail_decision
  - error

metrics:
  window_seconds: 300
  tracked:
    - event_count
    - denial_rate
    - cost_per_minute
    - avg_latency_ms

baselines:
  min_samples: 5

anomaly_rules:
  - name: high-denial-rate
    metric: denial_rate
    agent: "*"
    z_score_threshold: 2.5
    severity: high
    cooldown_seconds: 0

kill_switch:
  policies:
    - name: auto-kill-on-high-cost
      metric: cost_per_minute
      threshold: 5.0
      action: kill_agent
      severity: critical

alerts:
  channels:
    - type: console
    - type: file
      path: ./alerts.jsonl

compliance:
  export_formats:
    - soc2
    - gdpr
    - json
EOF
```

### Windows alternative: Python script to generate config

```powershell
python -c "
import textwrap, pathlib
pathlib.Path('basic.yaml').write_text(textwrap.dedent('''
version: \"1.0\"
agent_name: test-agent
events:
  - llm_call
  - tool_call
  - guardrail_decision
  - error
metrics:
  window_seconds: 300
  tracked:
    - event_count
    - denial_rate
    - cost_per_minute
    - avg_latency_ms
baselines:
  min_samples: 5
anomaly_rules:
  - name: high-denial-rate
    metric: denial_rate
    agent: \"*\"
    z_score_threshold: 2.5
    severity: high
    cooldown_seconds: 0
kill_switch:
  policies:
    - name: auto-kill-on-high-cost
      metric: cost_per_minute
      threshold: 5.0
      action: kill_agent
      severity: critical
alerts:
  channels:
    - type: console
    - type: file
      path: ./alerts.jsonl
compliance:
  export_formats:
    - soc2
    - gdpr
    - json
''').strip())
print('Created basic.yaml')
"
```

---

# Part 1: CLI

## 1. Version & Help

```bash
agent-monitor version
agent-monitor --help
```

Expected: version `0.1.0`, commands listed (`validate`, `inspect`, `record`, `metrics`, `kill`, `revive`, `export`, `version`).

---

## 2. Validate a Config

```bash
agent-monitor validate --config basic.yaml
```

Expected: `Config is valid: 4 event types, 4 metrics, 1 anomaly rules, 1 kill policies`

---

## 3. Validate an Invalid Config

### macOS / Linux

```bash
cat > bad_config.yaml << 'EOF'
version: "1.0"
agent_name: ""
events:
  - banana
anomaly_rules:
  - name: ""
    metric: throughput
    agent: "*"
    z_score_threshold: 3.0
    severity: ultra
    cooldown_seconds: 300
kill_switch:
  policies:
    - name: bad-policy
      metric: cost_per_minute
      threshold: 1.0
      action: restart
      severity: critical
EOF
agent-monitor validate --config bad_config.yaml
```

Expected: validation errors for missing agent_name, invalid event type, invalid metric, invalid severity, invalid kill action. Exit code 1.

---

## 4. Inspect a Config

```bash
agent-monitor inspect --config basic.yaml
```

Expected: formatted summary showing event types, metrics, anomaly rules, kill policies, alert channels.

---

## 5. Record an Event (CLI)

```bash
agent-monitor record --config basic.yaml --event '{"event_type":"llm_call","agent":"sales-agent","data":{"model":"gpt-4","latency_ms":350,"cost":0.007}}'
```

Expected: `Event recorded` confirmation.

---

## 6. View Metrics

```bash
agent-monitor metrics --config basic.yaml --agent sales-agent
```

Expected: metric snapshot showing event_count, denial_rate, cost_per_minute, avg_latency_ms.

---

## 7. Kill an Agent

```bash
agent-monitor kill --config basic.yaml --agent sales-agent --reason "Suspicious activity"
```

Expected: `Agent 'sales-agent' killed: Suspicious activity`

---

## 8. Revive an Agent

```bash
agent-monitor revive --config basic.yaml --agent sales-agent
```

Expected: `Agent 'sales-agent' revived`

---

## 9. Export Compliance Report

```bash
agent-monitor export --config basic.yaml --format json
agent-monitor export --config basic.yaml --format soc2
```

Expected: JSON report with events and summary. SOC 2 report with control-relevant fields.

---

# Part 2: Python API

## 10. Load Config and Record Events

```python
from theaios.agent_monitor import Monitor, load_config, AgentEvent

config = load_config("basic.yaml")
monitor = Monitor(config)

monitor.record(AgentEvent(
    event_type="llm_call",
    agent="sales-agent",
    data={"model": "gpt-4", "latency_ms": 350.0, "cost": 0.007},
))

snap = monitor.get_metrics("sales-agent")
print(f"Event count: {snap.event_count}")
print(f"Avg latency: {snap.avg_latency_ms:.1f}ms")
```

Expected: event_count=1, avg_latency=350.0ms.

---

## 11. Guardrail Decisions — Denial Rate

```python
from theaios.agent_monitor import Monitor, AgentEvent
from theaios.agent_monitor.types import MonitorConfig

config = MonitorConfig(
    version="1.0",
    agent_name="test",
    alerts={"channels": [{"type": "console"}]},
)
monitor = Monitor(config)

for outcome in ["allow", "deny", "allow", "deny", "allow"]:
    monitor.record(AgentEvent(
        event_type="guardrail_decision",
        agent="test-agent",
        data={"outcome": outcome, "rule": "test-rule"},
    ))

snap = monitor.get_metrics("test-agent")
print(f"Denial rate: {snap.denial_rate:.1%}")
```

Expected: `Denial rate: 40.0%`

---

## 12. Kill Switch — Manual Kill and Revive

```python
from theaios.agent_monitor import Monitor, AgentEvent
from theaios.agent_monitor.types import MonitorConfig

config = MonitorConfig(version="1.0", agent_name="test", alerts={"channels": []})
monitor = Monitor(config)

print(f"Killed? {monitor.is_killed('agent-a')}")

monitor.kill_agent("agent-a", reason="Cost spike")
print(f"Killed? {monitor.is_killed('agent-a')}")

result = monitor.record(AgentEvent(
    event_type="llm_call", agent="agent-a", data={},
))
print(f"Record result: {result}")

monitor.revive_agent("agent-a")
print(f"After revive: {monitor.is_killed('agent-a')}")
```

Expected: False, True, False/None, False.

---

## 13. Kill Switch — Auto-Kill on Threshold

```python
from theaios.agent_monitor import Monitor, AgentEvent
from theaios.agent_monitor.types import MonitorConfig

config = MonitorConfig(
    version="1.0",
    agent_name="test",
    metrics={"window_seconds": 60, "tracked": ["cost_per_minute"]},
    kill_switch={
        "policies": [{
            "name": "auto-kill",
            "metric": "cost_per_minute",
            "threshold": 1.0,
            "action": "kill_agent",
            "severity": "critical",
        }],
    },
    alerts={"channels": [{"type": "console"}]},
)
monitor = Monitor(config)

for i in range(50):
    ok = monitor.record(AgentEvent(
        event_type="llm_call", agent="expensive-bot",
        data={"cost": 0.5, "latency_ms": 50.0},
    ))
    if ok is False:
        print(f"Agent killed after {i+1} events")
        break

print(f"Is killed? {monitor.is_killed('expensive-bot')}")
```

Expected: agent gets killed when cost_per_minute exceeds $1.00.

---

## 14. Compliance Export — SOC 2

```python
from theaios.agent_monitor import Monitor, AgentEvent
from theaios.agent_monitor.types import MonitorConfig

config = MonitorConfig(
    version="1.0",
    agent_name="test",
    compliance={"export_formats": ["soc2", "json"]},
    alerts={"channels": []},
)
monitor = Monitor(config)

for i in range(10):
    monitor.record(AgentEvent(
        event_type="llm_call", agent="test-agent",
        data={"cost": 0.01, "latency_ms": 100.0},
    ))

report = monitor.export_compliance(fmt="soc2")
print(f"Format: {report['format']}")
print(f"Total events: {report['summary']['total_events']}")
print(f"Generated at: {report['generated_at']}")
```

Expected: SOC 2 report with 10 events and a timestamp.

---

## 15. Multiple Agents — Independent Metrics

```python
from theaios.agent_monitor import Monitor, AgentEvent
from theaios.agent_monitor.types import MonitorConfig

config = MonitorConfig(version="1.0", agent_name="test", alerts={"channels": []})
monitor = Monitor(config)

for _ in range(3):
    monitor.record(AgentEvent(
        event_type="llm_call", agent="alpha",
        data={"latency_ms": 100.0, "cost": 0.01},
    ))
for _ in range(5):
    monitor.record(AgentEvent(
        event_type="llm_call", agent="beta",
        data={"latency_ms": 200.0, "cost": 0.02},
    ))

snap_a = monitor.get_metrics("alpha")
snap_b = monitor.get_metrics("beta")
print(f"Alpha: {snap_a.event_count} events, {snap_a.avg_latency_ms:.0f}ms avg")
print(f"Beta:  {snap_b.event_count} events, {snap_b.avg_latency_ms:.0f}ms avg")
```

Expected: Alpha: 3 events, 100ms avg. Beta: 5 events, 200ms avg.

---

# Part 3: Edge Cases

## 16. Unknown Agent — Empty Metrics

```python
from theaios.agent_monitor import Monitor
from theaios.agent_monitor.types import MonitorConfig

config = MonitorConfig(version="1.0", agent_name="test", alerts={"channels": []})
monitor = Monitor(config)

snap = monitor.get_metrics("nonexistent")
print(f"Event count: {snap.event_count}")
print(f"Denial rate: {snap.denial_rate}")
```

Expected: event_count=0, denial_rate=0.0.

---

## 17. Global Kill Switch

```python
from theaios.agent_monitor import Monitor
from theaios.agent_monitor.types import MonitorConfig

config = MonitorConfig(version="1.0", agent_name="test", alerts={"channels": []})
monitor = Monitor(config)

monitor.kill_global(reason="Emergency shutdown")
print(f"Agent A killed? {monitor.is_killed('agent-a')}")
print(f"Agent B killed? {monitor.is_killed('agent-b')}")

monitor.revive_global()
print(f"After revive — Agent A killed? {monitor.is_killed('agent-a')}")
```

Expected: True, True, False.

---

## 18. Flush Resets Everything

```python
from theaios.agent_monitor import Monitor, AgentEvent
from theaios.agent_monitor.types import MonitorConfig

config = MonitorConfig(version="1.0", agent_name="test", alerts={"channels": []})
monitor = Monitor(config)

for _ in range(5):
    monitor.record(AgentEvent(
        event_type="llm_call", agent="test",
        data={"latency_ms": 100.0, "cost": 0.01},
    ))

print(f"Before flush: {monitor.get_metrics('test').event_count} events")
monitor.flush()
print(f"After flush:  {monitor.get_metrics('test').event_count} events")
```

Expected: 5 events before flush, 0 after.

---

## 19. Compliance Export — Filtered by Agent

```python
from theaios.agent_monitor import Monitor, AgentEvent
from theaios.agent_monitor.types import MonitorConfig

config = MonitorConfig(
    version="1.0", agent_name="test",
    compliance={"export_formats": ["json"]},
    alerts={"channels": []},
)
monitor = Monitor(config)

monitor.record(AgentEvent(event_type="llm_call", agent="alpha", data={"cost": 0.01}))
monitor.record(AgentEvent(event_type="llm_call", agent="beta", data={"cost": 0.02}))
monitor.record(AgentEvent(event_type="llm_call", agent="alpha", data={"cost": 0.03}))

report = monitor.export_compliance(fmt="json", agent="alpha")
print(f"Events for alpha: {report['summary']['total_events']}")
for e in report["events"]:
    print(f"  agent={e['agent']}")
```

Expected: 2 events, all for agent alpha.

---

## 20. Baseline Tracker — Z-Score

```python
from theaios.agent_monitor.baselines import BaselineTracker

tracker = BaselineTracker(min_samples=5)

# Feed normal values
for val in [10.0, 11.0, 9.5, 10.5, 10.0, 9.8, 10.2, 10.1, 9.9, 10.3]:
    tracker.update("test-agent", "event_count", val)

baseline = tracker.get_baseline("test-agent", "event_count")
print(f"Mean: {baseline['mean']:.2f}")
print(f"StdDev: {baseline['stddev']:.2f}")

# Check z-score for a normal value
z_normal = tracker.z_score("test-agent", "event_count", 10.0)
print(f"Z-score (10.0): {z_normal:.2f}")

# Check z-score for an anomalous value
z_anomaly = tracker.z_score("test-agent", "event_count", 50.0)
print(f"Z-score (50.0): {z_anomaly:.2f}")
```

Expected: mean ~10.1, stddev ~0.4, z_normal ~0, z_anomaly >> 3.

---

# Summary Checklist

| # | Feature | Type | Status |
|---|---------|------|--------|
| 1 | Version/help | CLI | |
| 2 | Validate valid config | CLI | |
| 3 | Validate invalid config | CLI | |
| 4 | Inspect config | CLI | |
| 5 | Record event | CLI | |
| 6 | View metrics | CLI | |
| 7 | Kill agent | CLI | |
| 8 | Revive agent | CLI | |
| 9 | Export compliance | CLI | |
| 10 | Load and record | Python | |
| 11 | Denial rate tracking | Python | |
| 12 | Manual kill/revive | Python | |
| 13 | Auto-kill on threshold | Python | |
| 14 | SOC 2 compliance export | Python | |
| 15 | Multiple agents | Python | |
| 16 | Unknown agent | Edge | |
| 17 | Global kill switch | Edge | |
| 18 | Flush resets | Edge | |
| 19 | Filtered compliance | Edge | |
| 20 | Baseline z-score | Edge | |
