# Configuration Reference

A monitor configuration is a single YAML file that defines event types, metrics, baselines, anomaly rules, kill switch policies, alert channels, and compliance export settings.

This page is the complete reference.

---

## File Structure

Every config file has these top-level sections:

```yaml
version: "1.0"              # Required. Always "1.0" for now.
agent_name: my-agent         # Required. Default agent identifier.
events:                      # Optional. Accepted event types.
metrics:                     # Optional. Metrics computation settings.
baselines:                   # Optional. Baseline tracking settings.
anomaly_rules:               # Optional. Anomaly detection rules.
kill_switch:                 # Optional. Kill switch policies.
alerts:                      # Required. Alert channel configuration.
compliance:                  # Optional. Compliance export settings.
```

Only `version`, `agent_name`, and `alerts` are required.

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

## Agent Name

```yaml
agent_name: my-agent
```

The default agent identifier. Used when events don't specify an agent and for config identification.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `agent_name` | string | **Yes** | Default agent name. Must be non-empty. |

---

## Events

```yaml
events:
  - llm_call
  - tool_call
  - guardrail_decision
  - error
  - custom
```

List of accepted event types. Events with types not in this list can still be recorded (the list is advisory, not enforcing).

### Valid Event Types

| Value | Description |
|-------|-------------|
| `llm_call` | An LLM API call |
| `tool_call` | An agent tool invocation |
| `guardrail_decision` | A guardrail evaluation result |
| `error` | An error or exception |
| `custom` | Any user-defined event |

---

## Metrics

```yaml
metrics:
  window_seconds: 300
  tracked:
    - event_count
    - denial_rate
    - cost_per_minute
    - avg_latency_ms
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `window_seconds` | int | `300` | Rolling window size in seconds for metric computation. |
| `tracked` | list | `["event_count"]` | Which metrics to compute. |

### Valid Metrics

| Value | Description | Source |
|-------|-------------|--------|
| `event_count` | Total events in window | -- |
| `denial_rate` | Fraction of guardrail decisions that are denials | `data.outcome` |
| `cost_per_minute` | Total cost divided by window minutes | `data.cost` |
| `avg_latency_ms` | Mean latency in milliseconds | `data.latency_ms` |

---

## Baselines

```yaml
baselines:
  min_samples: 20
  z_score_threshold: 3.0
  save_path: "${MONITOR_DATA_DIR}/baselines.json"
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `min_samples` | int | `20` | Minimum data points before z-scores are computed. |
| `z_score_threshold` | float | `3.0` | Default z-score threshold (overridden by individual anomaly rules). |
| `save_path` | string | `""` | Path to persist baseline state. Empty = no persistence. |

---

## Anomaly Rules

```yaml
anomaly_rules:
  - name: high-denial-rate
    metric: denial_rate
    agent: "*"
    z_score_threshold: 3.0
    severity: high
    cooldown_seconds: 300
```

Each rule is an object with:

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | string | **Yes** | -- | Unique rule identifier. |
| `metric` | string | **Yes** | -- | Which metric to monitor. Must be a valid metric name. |
| `agent` | string | **Yes** | -- | Agent to match. `"*"` matches all agents. |
| `z_score_threshold` | float | **Yes** | -- | Z-score threshold for triggering. |
| `severity` | string | **Yes** | -- | Alert severity: `critical`, `high`, `medium`, `low`. |
| `cooldown_seconds` | int | No | `300` | Minimum seconds between repeated alerts. |

### How Rules Are Evaluated

1. For each agent's metric snapshot, iterate all anomaly rules
2. Skip rules where `agent` doesn't match (unless `agent: "*"`)
3. Compute z-score for the rule's metric against the baseline
4. If z-score exceeds `z_score_threshold` and cooldown has elapsed, trigger an alert
5. Record the alert time for cooldown tracking

---

## Kill Switch

```yaml
kill_switch:
  persistence_path: "${MONITOR_DATA_DIR}/kill_state.json"
  policies:
    - name: auto-kill-on-high-cost
      metric: cost_per_minute
      threshold: 5.0
      action: kill_agent
      severity: critical
```

### Top-Level Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `persistence_path` | string | `""` | Path to persist kill state. Empty = no persistence. |
| `policies` | list | `[]` | Auto-kill policies. |

### Policy Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | **Yes** | Unique policy identifier. |
| `metric` | string | **Yes** | Which metric to evaluate. |
| `threshold` | float | **Yes** | Metric value that triggers the kill. |
| `action` | string | **Yes** | What to do: `kill_agent`, `kill_session`, `kill_global`. |
| `severity` | string | **Yes** | Alert severity for the kill event. |

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
      path: "${MONITOR_DATA_DIR}/alerts.jsonl"
    - type: webhook
      url: "${ALERT_WEBHOOK_URL}"
      method: POST
      headers:
        Authorization: "Bearer ${WEBHOOK_TOKEN}"
```

### Channel Types

| Type | Required Fields | Description |
|------|----------------|-------------|
| `console` | -- | Print alerts to stderr |
| `file` | `path` | Append JSONL to a file |
| `webhook` | `url` | HTTP POST to a webhook endpoint |

### Webhook Channel Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `url` | string | **(required)** | Webhook endpoint URL. |
| `method` | string | `"POST"` | HTTP method. |
| `headers` | dict | `{}` | HTTP headers. Supports `${ENV_VAR}` interpolation. |

---

## Compliance

```yaml
compliance:
  export_formats:
    - soc2
    - gdpr
    - json
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `export_formats` | list | `["json"]` | Available export formats. |

### Valid Export Formats

| Value | Description |
|-------|-------------|
| `soc2` | SOC 2 Type II audit format |
| `gdpr` | GDPR data processing records |
| `json` | Generic JSON export |

---

## Environment Variable Interpolation

All string values in the config support `${ENV_VAR}` interpolation:

```yaml
kill_switch:
  persistence_path: "${MONITOR_DATA_DIR}/kill_state.json"
alerts:
  channels:
    - type: webhook
      url: "${ALERT_WEBHOOK_URL}"
      headers:
        Authorization: "Bearer ${WEBHOOK_TOKEN}"
```

If the environment variable is not set, the placeholder is left as-is (no error, no expansion).

---

## Complete Enterprise Example

```yaml
version: "1.0"
agent_name: acme-monitor

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
  min_samples: 30
  z_score_threshold: 3.0
  save_path: /var/lib/agent-monitor/baselines.json

anomaly_rules:
  - name: high-denial-rate
    metric: denial_rate
    agent: "*"
    z_score_threshold: 3.0
    severity: high
    cooldown_seconds: 300

  - name: cost-spike
    metric: cost_per_minute
    agent: "*"
    z_score_threshold: 2.5
    severity: critical
    cooldown_seconds: 600

  - name: latency-anomaly
    metric: avg_latency_ms
    agent: "*"
    z_score_threshold: 3.0
    severity: medium
    cooldown_seconds: 120

kill_switch:
  persistence_path: /var/lib/agent-monitor/kill_state.json
  policies:
    - name: auto-kill-on-high-cost
      metric: cost_per_minute
      threshold: 5.0
      action: kill_agent
      severity: critical

    - name: emergency-shutdown
      metric: event_count
      threshold: 10000
      action: kill_global
      severity: critical

alerts:
  channels:
    - type: console
    - type: file
      path: /var/log/agent-monitor/alerts.jsonl
    - type: webhook
      url: https://hooks.slack.com/services/xxx
      headers:
        Content-Type: "application/json"

compliance:
  export_formats:
    - soc2
    - gdpr
    - json
```

---

## Validation

Always validate your config before deploying:

```bash
agent-monitor validate --config monitor.yaml
```

The validator checks:

- Version is supported (`"1.0"`)
- `agent_name` is non-empty
- All event types are valid
- All metrics are valid
- Anomaly rule names are unique and reference valid metrics/severities
- Kill policy actions are valid
- Alert channels have required fields
