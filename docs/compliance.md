# Compliance Export

Generate audit-ready reports from monitored events. Three formats: SOC 2, GDPR, and JSON.

---

## Why Compliance Export?

If your AI agents operate in a regulated environment (finance, healthcare, legal, enterprise SaaS), you need to prove:

- **What happened** -- every agent action, every guardrail decision
- **When it happened** -- timestamped event log
- **What controls were in place** -- anomaly rules, kill switches, guardrails
- **What anomalies were detected** -- and what was done about them

The compliance exporter transforms the raw event store into structured reports that auditors expect.

---

## Export Formats

### SOC 2

SOC 2 Type II reports focus on operational controls: what monitoring was in place, what events were recorded, and what actions were taken.

```python
report = monitor.export_compliance(fmt="soc2")
```

SOC 2 reports include:

| Field | Description |
|-------|-------------|
| `format` | `"soc2"` |
| `generated_at` | ISO timestamp of report generation |
| `summary` | Event counts, denial rates, agent list |
| `events` | All events in the time range |
| `controls` | Active anomaly rules and kill policies |

### GDPR

GDPR reports focus on data processing: which agents processed data, what types of events were recorded, and what data subjects (agents) are involved.

```python
report = monitor.export_compliance(fmt="gdpr")
```

GDPR reports include:

| Field | Description |
|-------|-------------|
| `format` | `"gdpr"` |
| `generated_at` | ISO timestamp |
| `summary` | Event counts |
| `events` | All events in the time range |
| `agents` | List of unique agents with event counts |

### JSON

Generic machine-readable export. Contains all events and summary statistics.

```python
report = monitor.export_compliance(fmt="json")
```

JSON reports include:

| Field | Description |
|-------|-------------|
| `format` | `"json"` |
| `generated_at` | ISO timestamp |
| `summary` | Event counts by type and agent |
| `events` | All events in the time range |

---

## Filtering

All exports support filtering by agent, time range, and event type.

### Filter by Agent

```python
report = monitor.export_compliance(fmt="json", agent="sales-agent")
```

### Filter by Time Range

```python
import time
report = monitor.export_compliance(
    fmt="soc2",
    since=time.time() - 86400,  # Last 24 hours
    until=time.time(),
)
```

### CLI Export

```bash
# JSON export
agent-monitor export --config monitor.yaml --format json

# SOC 2 export
agent-monitor export --config monitor.yaml --format soc2

# Filtered by agent
agent-monitor export --config monitor.yaml --format json --agent sales-agent

# Output to file
agent-monitor export --config monitor.yaml --format soc2 --output-file report.json
```

---

## Example Reports

### SOC 2 Report Structure

```json
{
  "format": "soc2",
  "generated_at": "2026-03-28T14:23:01.123Z",
  "summary": {
    "total_events": 1247,
    "event_types": {
      "llm_call": 890,
      "guardrail_decision": 245,
      "tool_call": 98,
      "error": 14
    },
    "agents": ["sales-agent", "finance-agent", "hr-agent"],
    "denial_count": 23,
    "kill_events": 1
  },
  "controls": {
    "anomaly_rules": 4,
    "kill_policies": 2,
    "alert_channels": 3
  },
  "events": [...]
}
```

### GDPR Report Structure

```json
{
  "format": "gdpr",
  "generated_at": "2026-03-28T14:23:01.123Z",
  "summary": {
    "total_events": 1247,
    "processing_purpose": "AI agent monitoring and governance"
  },
  "agents": [
    {"name": "sales-agent", "event_count": 523},
    {"name": "finance-agent", "event_count": 412},
    {"name": "hr-agent", "event_count": 312}
  ],
  "events": [...]
}
```

---

## Scheduling Exports

The library does not include a built-in scheduler. Use your platform's scheduling mechanism:

```bash
# Cron: daily SOC 2 export at midnight
0 0 * * * agent-monitor export --config /etc/agent-monitor/monitor.yaml --format soc2 --output-file /var/reports/soc2-$(date +\%Y-\%m-\%d).json
```

```python
# Python: export after every N events
event_count = 0
for event in event_stream:
    monitor.record(event)
    event_count += 1
    if event_count % 10000 == 0:
        report = monitor.export_compliance(fmt="json")
        save_report(report)
```
