# Configuration Reference

A monitor configuration is a single YAML file that defines agent tracking, metrics, baselines, anomaly rules, kill switch policies, alert channels, and storage settings.

This page is the complete reference.

---

## File Structure

Every config file has these top-level sections:

```yaml
version: "1.0"              # Required. Always "1.0" for now.
metadata:                    # Optional. Name, description, author.
variables:                   # Optional. Shared key-value pairs.
agents:                      # Optional. Per-agent tracking config.
storage:                     # Optional. Event storage settings.
metrics:                     # Optional. Metrics engine settings.
baselines:                   # Optional. Baseline tracking settings.
anomaly_detection:           # Optional. Anomaly detection rules.
kill_switch:                 # Optional. Kill switch policies.
alerts:                      # Optional. Alert channel configuration.
```

Only `version` is strictly required. All other sections use sensible defaults.

---

## Version

```yaml
version: "1.0"
```

Always `"1.0"` for the current release. The engine rejects unknown versions.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `version` | string | **Yes** | Config format version. Must be `"1.0"`. |

---

## Metadata

```yaml
metadata:
  name: my-monitor
  description: Production agent monitoring
  author: ops-team
```

Optional metadata for documentation and identification.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `metadata.name` | string | `""` | Monitor name. |
| `metadata.description` | string | `""` | Human-readable description. |
| `metadata.author` | string | `""` | Config author or team. |

---

## Variables

```yaml
variables:
  alert_webhook: "https://hooks.slack.com/services/xxx"
  cost_threshold: 5.0
```

Key-value pairs available for reference. Variables support `${ENV_VAR}` interpolation.

---

## Agents

```yaml
agents:
  sales-agent:
    enabled: true
    event_types:
      - action
      - denial
      - error
    tags:
      - production
      - sales
  finance-agent:
    enabled: true
```

Per-agent tracking configuration. If no agents are configured, all agents are tracked by default.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `agents.<name>.enabled` | bool | `true` | Whether to track this agent. |
| `agents.<name>.event_types` | list | `[]` (all) | Only track these event types. Empty = track all. |
| `agents.<name>.tags` | list | `[]` | Tags for this agent. |

### Valid Event Types

| Value | Description |
|-------|-------------|
| `action` | An agent action (LLM call, tool call, etc.) |
| `guardrail_trigger` | A guardrail evaluation (non-denial) |
| `denial` | A guardrail denial |
| `approval_request` | An action requiring human approval |
| `approval_response` | A human approval response |
| `cost` | A cost record |
| `error` | An error or exception |
| `session_start` | Session start |
| `session_end` | Session end |

---

## Storage

```yaml
storage:
  path: .agent_monitor/events.jsonl
  retention_days: 90
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `storage.path` | string | `.agent_monitor/events.jsonl` | Path to the JSONL event store. |
| `storage.retention_days` | int | `90` | Days to retain events. Must be >= 1. |

---

## Metrics

```yaml
metrics:
  default_window_seconds: 300
  max_window_seconds: 3600
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `metrics.default_window_seconds` | int | `300` | Default rolling window size in seconds. |
| `metrics.max_window_seconds` | int | `3600` | Maximum allowed window size. |

### Valid Metrics

These are the metrics computed by the engine:

| Metric | Description | Source |
|--------|-------------|--------|
| `event_count` | Total events in window | -- |
| `action_count` | Count of `action` events | `event_type` |
| `denial_count` | Count of `denial` events | `event_type` |
| `denial_rate` | Fraction of action+denial events that are denials | `event_type` |
| `approval_count` | Count of approval events | `event_type` |
| `approval_rate` | Fraction of events that are approvals | `event_type` |
| `error_count` | Count of `error` events | `event_type` |
| `cost_total` | Sum of `cost_usd` in window | `cost_usd` |
| `cost_per_minute` | `cost_total / (window_seconds / 60)` | `cost_usd` |
| `avg_latency_ms` | Mean latency for events with latency | `latency_ms` |

---

## Baselines

```yaml
baselines:
  enabled: true
  min_samples: 30
  metrics:
    - denial_rate
    - error_count
    - cost_per_minute
    - avg_latency_ms
  storage_path: .agent_monitor/baselines.json
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `baselines.enabled` | bool | `true` | Enable baseline tracking. |
| `baselines.min_samples` | int | `30` | Minimum data points before z-scores are computed. |
| `baselines.metrics` | list | `["denial_rate", "error_count", "cost_per_minute", "avg_latency_ms"]` | Which metrics to track baselines for. |
| `baselines.storage_path` | string | `.agent_monitor/baselines.json` | Path to persist baseline state. |

---

## Anomaly Detection

```yaml
anomaly_detection:
  enabled: true
  rules:
    - name: high-denial-rate
      metric: denial_rate
      z_threshold: 3.0
      severity: high
      cooldown_seconds: 300
```

### Top-Level Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `anomaly_detection.enabled` | bool | `true` | Enable anomaly detection. |
| `anomaly_detection.rules` | list | `[]` | Anomaly detection rules. |

### Rule Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | string | **Yes** | -- | Unique rule identifier. |
| `metric` | string | **Yes** | -- | Which metric to monitor. |
| `z_threshold` | float | No | `3.0` | Z-score threshold for triggering. |
| `severity` | string | No | `"high"` | Alert severity: `critical`, `high`, `medium`, `low`. |
| `cooldown_seconds` | int | No | `300` | Minimum seconds between repeated alerts. |
| `condition` | string | No | `""` | Optional condition expression. |

### How Rules Are Evaluated

1. For each agent's metric snapshot, iterate all anomaly rules
2. Compute z-score for the rule's metric against the baseline
3. If z-score exceeds `z_threshold` and cooldown has elapsed, trigger an alert
4. Record the alert time for cooldown tracking

---

## Kill Switch

```yaml
kill_switch:
  enabled: true
  state_path: .agent_monitor/kill_state.json
  policies:
    - name: auto-kill-on-high-cost
      metric: cost_per_minute
      operator: ">"
      threshold: 5.0
      action: kill_agent
      severity: critical
```

### Top-Level Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `kill_switch.enabled` | bool | `true` | Enable kill switch system. |
| `kill_switch.state_path` | string | `.agent_monitor/kill_state.json` | Path to persist kill state. |
| `kill_switch.policies` | list | `[]` | Auto-kill policies. |

### Policy Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | string | **Yes** | -- | Unique policy identifier. |
| `metric` | string | **Yes** | -- | Which metric to evaluate. |
| `operator` | string | **Yes** | -- | Comparison: `>`, `<`, `>=`, `<=`, `==`. |
| `threshold` | float | **Yes** | -- | Metric value that triggers the kill. |
| `action` | string | No | `"kill_agent"` | What to do: `kill_agent`, `kill_session`, `kill_global`. |
| `severity` | string | No | `"critical"` | Alert severity for the kill event. |
| `message` | string | No | `""` | Custom message for the kill alert. |

### Valid Kill Actions

| Value | What it does |
|-------|-------------|
| `kill_agent` | Kill the specific agent whose metric exceeded the threshold |
| `kill_session` | Kill the specific session (requires `session_id` on events) |
| `kill_global` | Kill all agents globally |

---

## Alerts

```yaml
alerts:
  channels:
    - type: console
    - type: file
      path: .agent_monitor/alerts.jsonl
      min_severity: medium
    - type: webhook
      url: "${ALERT_WEBHOOK_URL}"
      headers:
        Authorization: "Bearer ${WEBHOOK_TOKEN}"
      min_severity: high
```

### Channel Types

| Type | Required Fields | Description |
|------|----------------|-------------|
| `console` | -- | Print alerts to stderr |
| `file` | `path` | Append JSONL to a file |
| `webhook` | `url` | HTTP POST to a webhook endpoint |

### Channel Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **(required)** | Channel type: `console`, `file`, `webhook`. |
| `enabled` | bool | `true` | Enable this channel. |
| `path` | string | `""` | File path (for `file` channels). |
| `url` | string | `""` | Webhook endpoint URL (for `webhook` channels). |
| `min_severity` | string | `"low"` | Minimum severity to dispatch. |
| `headers` | dict | `{}` | HTTP headers (for `webhook` channels). Supports `${ENV_VAR}` interpolation. |

---

## Environment Variable Interpolation

All string values in the config support `${ENV_VAR}` and `${ENV_VAR:default}` interpolation:

```yaml
kill_switch:
  state_path: "${MONITOR_DATA_DIR:.agent_monitor}/kill_state.json"
alerts:
  channels:
    - type: webhook
      url: "${ALERT_WEBHOOK_URL}"
      headers:
        Authorization: "Bearer ${WEBHOOK_TOKEN}"
```

If the environment variable is not set and no default is provided, the placeholder is left as-is (no error, no expansion).

---

## Complete Enterprise Example

```yaml
version: "1.0"
metadata:
  name: acme-monitor
  description: Production monitoring for ACME AI agents
  author: platform-team

agents:
  sales-agent:
    enabled: true
    event_types: [action, denial, error, cost]
    tags: [production, sales]
  finance-agent:
    enabled: true
    tags: [production, finance]

storage:
  path: /var/lib/agent-monitor/events.jsonl
  retention_days: 365

metrics:
  default_window_seconds: 300
  max_window_seconds: 3600

baselines:
  enabled: true
  min_samples: 30
  metrics:
    - denial_rate
    - error_count
    - cost_per_minute
    - avg_latency_ms
  storage_path: /var/lib/agent-monitor/baselines.json

anomaly_detection:
  enabled: true
  rules:
    - name: high-denial-rate
      metric: denial_rate
      z_threshold: 3.0
      severity: high
      cooldown_seconds: 300

    - name: cost-spike
      metric: cost_per_minute
      z_threshold: 2.5
      severity: critical
      cooldown_seconds: 600

    - name: latency-anomaly
      metric: avg_latency_ms
      z_threshold: 3.0
      severity: medium
      cooldown_seconds: 120

kill_switch:
  enabled: true
  state_path: /var/lib/agent-monitor/kill_state.json
  policies:
    - name: auto-kill-on-high-cost
      metric: cost_per_minute
      operator: ">"
      threshold: 5.0
      action: kill_agent
      severity: critical

    - name: emergency-shutdown
      metric: event_count
      operator: ">"
      threshold: 10000
      action: kill_global
      severity: critical

alerts:
  channels:
    - type: console
    - type: file
      path: /var/log/agent-monitor/alerts.jsonl
      min_severity: medium
    - type: webhook
      url: https://hooks.slack.com/services/xxx
      headers:
        Content-Type: "application/json"
      min_severity: high
```

---

## Validation

Always validate your config before deploying:

```bash
agent-monitor -c monitor.yaml validate
```

The validator checks:

- Version is supported (`"1.0"`)
- All event types in agent configs are valid
- Storage retention_days >= 1
- Metrics window sizes are valid
- Baselines min_samples >= 1
- Anomaly rule names are unique, reference valid severities
- Kill policy operators, actions, and severities are valid
- Alert channels have required fields and valid types/severities
