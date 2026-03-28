# CLI Reference

The `agent-monitor` CLI lets you validate configs, record events, view metrics, manage kill switches, and export compliance reports from the terminal.

---

## Commands

### `agent-monitor version`

Show the installed version.

```bash
agent-monitor version
# agent-monitor 0.1.0
```

---

### `agent-monitor validate`

Check a config file for errors.

```bash
agent-monitor validate --config monitor.yaml
# Config is valid: 4 event types, 4 metrics, 2 anomaly rules, 1 kill policies
```

| Option | Default | Description |
|--------|---------|-------------|
| `--config`, `-c` | `monitor.yaml` | Config file path |

Exit code 0 = valid, 1 = errors found.

---

### `agent-monitor inspect`

Display a formatted summary of the config.

```bash
agent-monitor inspect --config monitor.yaml
```

| Option | Default | Description |
|--------|---------|-------------|
| `--config`, `-c` | `monitor.yaml` | Config file path |

Shows: event types, metrics, anomaly rules, kill policies, alert channels, compliance formats.

---

### `agent-monitor record`

Record a single event from the CLI.

```bash
agent-monitor record --config monitor.yaml \
  --event '{"event_type":"llm_call","agent":"sales-agent","data":{"latency_ms":350,"cost":0.007}}'
```

| Option | Default | Description |
|--------|---------|-------------|
| `--config`, `-c` | `monitor.yaml` | Config file path |
| `--event`, `-e` | **(required)** | Event as a JSON string |

**Event JSON format:**

```json
{
  "event_type": "llm_call",
  "agent": "sales-agent",
  "data": {"latency_ms": 350, "cost": 0.007},
  "session_id": "optional"
}
```

---

### `agent-monitor metrics`

View current metrics for an agent.

```bash
agent-monitor metrics --config monitor.yaml --agent sales-agent
agent-monitor metrics --config monitor.yaml --agent sales-agent --output json
```

| Option | Default | Description |
|--------|---------|-------------|
| `--config`, `-c` | `monitor.yaml` | Config file path |
| `--agent`, `-a` | **(required)** | Agent name |
| `--output`, `-o` | `console` | Output format: `console` or `json` |

---

### `agent-monitor kill`

Kill an agent or trigger global kill.

```bash
# Kill a specific agent
agent-monitor kill --config monitor.yaml --agent sales-agent --reason "Cost spike"

# Global kill
agent-monitor kill --config monitor.yaml --global --reason "Emergency"
```

| Option | Default | Description |
|--------|---------|-------------|
| `--config`, `-c` | `monitor.yaml` | Config file path |
| `--agent`, `-a` | -- | Agent to kill |
| `--global` | `false` | Kill all agents |
| `--reason`, `-r` | `"manual kill"` | Reason for the kill |

---

### `agent-monitor revive`

Revive a killed agent or clear global kill.

```bash
# Revive a specific agent
agent-monitor revive --config monitor.yaml --agent sales-agent

# Revive globally
agent-monitor revive --config monitor.yaml --global
```

| Option | Default | Description |
|--------|---------|-------------|
| `--config`, `-c` | `monitor.yaml` | Config file path |
| `--agent`, `-a` | -- | Agent to revive |
| `--global` | `false` | Revive all agents |

---

### `agent-monitor export`

Export a compliance report.

```bash
# JSON export to stdout
agent-monitor export --config monitor.yaml --format json

# SOC 2 export to file
agent-monitor export --config monitor.yaml --format soc2 --output-file report.json

# Filtered by agent
agent-monitor export --config monitor.yaml --format json --agent sales-agent
```

| Option | Default | Description |
|--------|---------|-------------|
| `--config`, `-c` | `monitor.yaml` | Config file path |
| `--format`, `-f` | `json` | Export format: `json`, `soc2`, `gdpr` |
| `--agent`, `-a` | -- | Filter by agent |
| `--since` | -- | Filter events after this ISO timestamp |
| `--until` | -- | Filter events before this ISO timestamp |
| `--output-file` | -- | Write output to file (default: stdout) |

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Validation error or agent is killed |
