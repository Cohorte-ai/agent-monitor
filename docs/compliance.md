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
import json

output = monitor.compliance_exporter.export(format="soc2")
report = json.loads(output)
```

SOC 2 reports include:

| Field | Description |
|-------|-------------|
| `format` | `"soc2"` |
| `report_title` | `"SOC2 AI Agent Compliance Report"` |
| `generated_at` | ISO timestamp of report generation |
| `period` | Time period covered |
| `summary` | Event counts, denial rates, error rates, unique agents/sessions |
| `access_controls` | Agents observed, denial events, approval events |
| `availability` | Error events |
| `guardrail_enforcement` | Guardrail trigger events |

### GDPR

GDPR reports focus on data processing: which agents processed data, what types of events were recorded, and what data subjects (users) are involved.

```python
import json

output = monitor.compliance_exporter.export(format="gdpr")
report = json.loads(output)
```

GDPR reports include:

| Field | Description |
|-------|-------------|
| `format` | `"gdpr"` |
| `report_title` | `"GDPR AI Agent Data Processing Report"` |
| `generated_at` | ISO timestamp |
| `summary` | Total processing events, unique data subjects, total cost |
| `data_subjects` | Users observed, events per user |
| `processing_activities` | Event type counts, agent counts |
| `data_retention` | Oldest and newest event timestamps |

### JSON

Generic machine-readable export. Contains all events and summary statistics.

```python
import json

output = monitor.compliance_exporter.export(format="json")
report = json.loads(output)
```

JSON reports include:

| Field | Description |
|-------|-------------|
| `format` | `"json"` |
| `generated_at` | ISO timestamp |
| `filters` | Applied filters (since, until, agent) |
| `total_events` | Count of events |
| `events` | All events in the time range |

---

## Filtering

All exports support filtering by agent and time range.

### Filter by Agent

```python
output = monitor.compliance_exporter.export(format="json", agent="sales-agent")
```

### Filter by Time Range

```python
output = monitor.compliance_exporter.export(
    format="soc2",
    since="2026-03-01T00:00:00",
    until="2026-03-28T00:00:00",
)
```

### CLI Export

```bash
# JSON export
agent-monitor -c monitor.yaml export --format json

# SOC 2 export
agent-monitor -c monitor.yaml export --format soc2

# GDPR export
agent-monitor -c monitor.yaml export --format gdpr

# Filtered by agent
agent-monitor -c monitor.yaml export --format json --agent sales-agent

# Filtered by time range
agent-monitor -c monitor.yaml export --format soc2 --since "2026-03-01T00:00:00" --until "2026-03-28T00:00:00"
```

---

## Example Reports

### SOC 2 Report Structure

```json
{
  "format": "soc2",
  "report_title": "SOC2 AI Agent Compliance Report",
  "generated_at": "2026-03-28T14:23:01.123Z",
  "period": {
    "since": "beginning",
    "until": "2026-03-28T14:23:01.123Z"
  },
  "summary": {
    "total_events": 1247,
    "total_actions": 890,
    "total_denials": 23,
    "total_approvals": 12,
    "total_errors": 14,
    "total_guardrail_triggers": 98,
    "denial_rate": 0.0184,
    "error_rate": 0.0112,
    "unique_agents": 3,
    "unique_sessions": 45
  },
  "access_controls": {
    "agents_observed": ["finance-agent", "hr-agent", "sales-agent"],
    "denial_events": [...],
    "approval_events": [...]
  },
  "availability": {
    "error_events": [...]
  },
  "guardrail_enforcement": {
    "trigger_events": [...]
  }
}
```

### GDPR Report Structure

```json
{
  "format": "gdpr",
  "report_title": "GDPR AI Agent Data Processing Report",
  "generated_at": "2026-03-28T14:23:01.123Z",
  "summary": {
    "total_processing_events": 1247,
    "unique_data_subjects": 5,
    "total_processing_cost_usd": 12.34
  },
  "data_subjects": {
    "users_observed": ["alice@example.com", "bob@example.com"],
    "events_per_user": {"alice@example.com": 523, "bob@example.com": 412}
  },
  "processing_activities": {
    "event_type_counts": {"action": 890, "denial": 23, "error": 14},
    "agent_counts": {"sales-agent": 523, "finance-agent": 412}
  },
  "data_retention": {
    "oldest_event_timestamp": 1711584000.0,
    "newest_event_timestamp": 1711670400.0
  }
}
```

---

## Scheduling Exports

The library does not include a built-in scheduler. Use your platform's scheduling mechanism:

```bash
# Cron: daily SOC 2 export at midnight
0 0 * * * agent-monitor -c /etc/agent-monitor/monitor.yaml export --format soc2 > /var/reports/soc2-$(date +\%Y-\%m-\%d).json
```

```python
import time
import json

# Python: export after every N events
event_count = 0
for event in event_stream:
    monitor.record(event)
    event_count += 1
    if event_count % 10000 == 0:
        output = monitor.compliance_exporter.export(format="json")
        save_report(output)
```
