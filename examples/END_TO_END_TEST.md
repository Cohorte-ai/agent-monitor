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
metadata:
  name: test-monitor
  description: End-to-end test config

storage:
  path: .agent_monitor/events.jsonl
  retention_days: 90

metrics:
  default_window_seconds: 300
  max_window_seconds: 3600

baselines:
  enabled: true
  min_samples: 5
  metrics:
    - denial_rate
    - error_count
    - cost_per_minute
    - avg_latency_ms

anomaly_detection:
  enabled: true
  rules:
    - name: high-denial-rate
      metric: denial_rate
      z_threshold: 2.5
      severity: high
      cooldown_seconds: 0

kill_switch:
  enabled: true
  policies:
    - name: auto-kill-on-high-cost
      metric: cost_per_minute
      operator: ">"
      threshold: 5.0
      action: kill_agent
      severity: critical

alerts:
  channels:
    - type: console
    - type: file
      path: ./alerts.jsonl
EOF
```

### Windows alternative: Python script to generate config

```powershell
python -c "
import textwrap, pathlib
pathlib.Path('basic.yaml').write_text(textwrap.dedent('''
version: \"1.0\"
metadata:
  name: test-monitor
  description: End-to-end test config
storage:
  path: .agent_monitor/events.jsonl
  retention_days: 90
metrics:
  default_window_seconds: 300
  max_window_seconds: 3600
baselines:
  enabled: true
  min_samples: 5
  metrics:
    - denial_rate
    - error_count
    - cost_per_minute
    - avg_latency_ms
anomaly_detection:
  enabled: true
  rules:
    - name: high-denial-rate
      metric: denial_rate
      z_threshold: 2.5
      severity: high
      cooldown_seconds: 0
kill_switch:
  enabled: true
  policies:
    - name: auto-kill-on-high-cost
      metric: cost_per_minute
      operator: \">\"
      threshold: 5.0
      action: kill_agent
      severity: critical
alerts:
  channels:
    - type: console
    - type: file
      path: ./alerts.jsonl
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

Expected: version `0.1.0`, commands listed (`validate`, `inspect`, `status`, `events`, `alerts`, `kill`, `revive`, `export`, `version`).

---

## 2. Validate a Config

```bash
agent-monitor -c basic.yaml validate
```

Expected: `Config valid: basic.yaml` with a summary of agents, anomaly rules, kill policies, and alert channels.

---

## 3. Validate an Invalid Config

### macOS / Linux

```bash
cat > bad_config.yaml << 'EOF'
version: "1.0"
agents:
  bad-agent:
    event_types:
      - banana
anomaly_detection:
  rules:
    - name: ""
      metric: throughput
      z_threshold: 3.0
      severity: ultra
kill_switch:
  policies:
    - name: bad-policy
      metric: cost_per_minute
      operator: ">"
      threshold: 1.0
      action: restart
      severity: critical
alerts:
  channels:
    - type: invalid_channel
EOF
agent-monitor -c bad_config.yaml validate
```

Expected: validation errors for invalid event type, missing rule name, invalid severity, invalid kill action, invalid channel type. Exit code 1.

---

## 4. Inspect a Config

```bash
agent-monitor -c basic.yaml inspect
```

Expected: full parsed config dumped as JSON.

---

## 5. View Status

```bash
agent-monitor -c basic.yaml status
```

Expected: empty metrics table (no events recorded yet) and kill switch state.

---

## 6. Query Events

```bash
agent-monitor -c basic.yaml events
```

Expected: empty events table (no events recorded yet).

---

## 7. Kill an Agent

```bash
agent-monitor -c basic.yaml kill sales-agent --reason "Suspicious activity"
```

Expected: `Agent 'sales-agent' killed.`

---

## 8. Revive an Agent

```bash
agent-monitor -c basic.yaml revive sales-agent
```

Expected: `Agent 'sales-agent' revived.`

---

## 9. Export Compliance Report

```bash
agent-monitor -c basic.yaml export --format json
agent-monitor -c basic.yaml export --format soc2
```

Expected: JSON report with events and summary. SOC 2 report with access control fields.

---

# Part 2: Python API

## 10. Load Config and Record Events

```python
import time
from theaios.agent_monitor import Monitor, load_config, AgentEvent

config = load_config("basic.yaml")
monitor = Monitor(config)

monitor.record(AgentEvent(
    timestamp=time.time(),
    event_type="action",
    agent="sales-agent",
    cost_usd=0.007,
    latency_ms=350.0,
    data={"model": "gpt-4"},
))

snap = monitor.get_metrics("sales-agent")
print(f"Event count: {snap.event_count}")
print(f"Avg latency: {snap.avg_latency_ms:.1f}ms")
```

Expected: event_count=1, avg_latency=350.0ms.

---

## 11. Denial Rate Tracking

```python
import time
from theaios.agent_monitor import Monitor, AgentEvent
from theaios.agent_monitor.types import AlertChannelConfig, AlertConfig, MonitorConfig

config = MonitorConfig(
    version="1.0",
    alerts=AlertConfig(channels=[AlertChannelConfig(type="console")]),
)
monitor = Monitor(config)

for event_type in ["action", "denial", "action", "denial", "action"]:
    monitor.record(AgentEvent(
        timestamp=time.time(),
        event_type=event_type,
        agent="test-agent",
        data={"rule": "test-rule"},
    ))

snap = monitor.get_metrics("test-agent")
print(f"Denial rate: {snap.denial_rate:.1%}")
```

Expected: `Denial rate: 40.0%` (2 denials out of 3 actions + 2 denials = 5 decisions).

---

## 12. Kill Switch — Manual Kill and Revive

```python
import time
from theaios.agent_monitor import Monitor, AgentEvent
from theaios.agent_monitor.types import AlertConfig, MonitorConfig

config = MonitorConfig(version="1.0", alerts=AlertConfig(channels=[]))
monitor = Monitor(config)

print(f"Killed? {monitor.is_killed('agent-a')}")

monitor.kill_agent("agent-a", reason="Cost spike")
print(f"Killed? {monitor.is_killed('agent-a')}")

# record() returns None — event is silently dropped
monitor.record(AgentEvent(
    timestamp=time.time(), event_type="action", agent="agent-a", data={},
))
snap = monitor.get_metrics("agent-a")
print(f"Events while killed: {snap.event_count}")

monitor.revive(agent="agent-a")
print(f"After revive: {monitor.is_killed('agent-a')}")
```

Expected: False, True, 0, False.

---

## 13. Kill Switch — Auto-Kill on Threshold

```python
import time
from theaios.agent_monitor import Monitor, AgentEvent
from theaios.agent_monitor.types import (
    AlertChannelConfig, AlertConfig,
    KillPolicyConfig, KillSwitchConfig,
    MetricsEngineConfig, MonitorConfig,
)

config = MonitorConfig(
    version="1.0",
    metrics=MetricsEngineConfig(default_window_seconds=60),
    kill_switch=KillSwitchConfig(
        enabled=True,
        policies=[
            KillPolicyConfig(
                name="auto-kill",
                metric="cost_per_minute",
                operator=">",
                threshold=1.0,
                action="kill_agent",
                severity="critical",
            ),
        ],
    ),
    alerts=AlertConfig(channels=[AlertChannelConfig(type="console")]),
)
monitor = Monitor(config)

for i in range(50):
    if monitor.is_killed("expensive-bot"):
        print(f"Agent killed after {i} recorded events")
        break
    monitor.record(AgentEvent(
        timestamp=time.time(),
        event_type="action", agent="expensive-bot",
        cost_usd=0.5, latency_ms=50.0,
    ))

print(f"Is killed? {monitor.is_killed('expensive-bot')}")
```

Expected: agent gets killed when cost_per_minute exceeds $1.00.

---

## 14. Compliance Export — SOC 2

```python
import time
import json
from theaios.agent_monitor import Monitor, AgentEvent
from theaios.agent_monitor.types import AlertConfig, MonitorConfig

config = MonitorConfig(version="1.0", alerts=AlertConfig(channels=[]))
monitor = Monitor(config)

for i in range(10):
    monitor.record(AgentEvent(
        timestamp=time.time(),
        event_type="action", agent="test-agent",
        cost_usd=0.01, latency_ms=100.0,
    ))

output = monitor.compliance_exporter.export(format="soc2")
report = json.loads(output)
print(f"Format: {report['format']}")
print(f"Total events: {report['summary']['total_events']}")
print(f"Generated at: {report['generated_at']}")
```

Expected: SOC 2 report with 10 events and a timestamp.

---

## 15. Multiple Agents — Independent Metrics

```python
import time
from theaios.agent_monitor import Monitor, AgentEvent
from theaios.agent_monitor.types import AlertConfig, MonitorConfig

config = MonitorConfig(version="1.0", alerts=AlertConfig(channels=[]))
monitor = Monitor(config)

for _ in range(3):
    monitor.record(AgentEvent(
        timestamp=time.time(),
        event_type="action", agent="alpha",
        latency_ms=100.0, cost_usd=0.01,
    ))
for _ in range(5):
    monitor.record(AgentEvent(
        timestamp=time.time(),
        event_type="action", agent="beta",
        latency_ms=200.0, cost_usd=0.02,
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
from theaios.agent_monitor.types import AlertConfig, MonitorConfig

config = MonitorConfig(version="1.0", alerts=AlertConfig(channels=[]))
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
from theaios.agent_monitor.types import AlertConfig, MonitorConfig

config = MonitorConfig(version="1.0", alerts=AlertConfig(channels=[]))
monitor = Monitor(config)

monitor.kill_global(reason="Emergency shutdown")
print(f"Agent A killed? {monitor.is_killed('agent-a')}")
print(f"Agent B killed? {monitor.is_killed('agent-b')}")

monitor.revive_global()
print(f"After revive — Agent A killed? {monitor.is_killed('agent-a')}")
```

Expected: True, True, False.

---

## 18. Flush Resets Metrics

```python
import time
from theaios.agent_monitor import Monitor, AgentEvent
from theaios.agent_monitor.types import AlertConfig, MonitorConfig

config = MonitorConfig(version="1.0", alerts=AlertConfig(channels=[]))
monitor = Monitor(config)

for _ in range(5):
    monitor.record(AgentEvent(
        timestamp=time.time(),
        event_type="action", agent="test",
        latency_ms=100.0, cost_usd=0.01,
    ))

print(f"Before flush: {monitor.get_metrics('test').event_count} events")
monitor.flush()
print(f"After flush:  {monitor.get_metrics('test').event_count} events")
```

Expected: 5 events before flush, 0 after.

---

## 19. Compliance Export — Filtered by Agent

```python
import time
import json
from theaios.agent_monitor import Monitor, AgentEvent
from theaios.agent_monitor.types import AlertConfig, MonitorConfig

config = MonitorConfig(version="1.0", alerts=AlertConfig(channels=[]))
monitor = Monitor(config)

monitor.record(AgentEvent(timestamp=time.time(), event_type="action", agent="alpha", cost_usd=0.01))
monitor.record(AgentEvent(timestamp=time.time(), event_type="action", agent="beta", cost_usd=0.02))
monitor.record(AgentEvent(timestamp=time.time(), event_type="action", agent="alpha", cost_usd=0.03))

output = monitor.compliance_exporter.export(format="json", agent="alpha")
report = json.loads(output)
print(f"Events for alpha: {report['total_events']}")
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
print(f"Mean: {baseline.mean:.2f}")
print(f"StdDev: {baseline.stddev:.2f}")
print(f"Samples: {baseline.sample_count}")

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
| 5 | View status | CLI | |
| 6 | Query events | CLI | |
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
| 18 | Flush resets metrics | Edge | |
| 19 | Filtered compliance | Edge | |
| 20 | Baseline z-score | Edge | |
