# CLI Reference

The `agent-monitor` CLI lets you validate configs, inspect parsed state, view metrics, query events, manage kill switches, and export compliance reports from the terminal.

---

## Global Options

The config file path is specified as a **group option** on the top-level command, before the subcommand:

```bash
agent-monitor -c monitor.yaml <command>
agent-monitor --config /path/to/monitor.yaml <command>
```

| Option | Default | Description |
|--------|---------|-------------|
| `-c`, `--config` | `monitor.yaml` | Path to monitor config file |

---

## Commands

### `agent-monitor version`

Show the installed version.

```bash
agent-monitor version
# theaios-agent-monitor 0.1.0
```

---

### `agent-monitor validate`

Check a config file for errors.

```bash
agent-monitor -c monitor.yaml validate
```

Exit code 0 = valid, 1 = errors found.

Output includes a summary of agents, anomaly rules, kill policies, and alert channels.

---

### `agent-monitor inspect`

Dump the parsed config as JSON. Useful for debugging interpolation and default values.

```bash
agent-monitor -c monitor.yaml inspect
```

---

### `agent-monitor status`

Show current agent metrics and kill switch state.

```bash
# All agents
agent-monitor -c monitor.yaml status

# Specific agent
agent-monitor -c monitor.yaml status --agent sales-agent

# Custom window
agent-monitor -c monitor.yaml status --window 60

# JSON output
agent-monitor -c monitor.yaml status --json
```

| Option | Default | Description |
|--------|---------|-------------|
| `-w`, `--window` | `300` | Window size in seconds |
| `-a`, `--agent` | -- | Filter by agent name |
| `--json` | `false` | Output as JSON |

---

### `agent-monitor events`

Query stored agent events from the JSONL event store.

```bash
# Recent events
agent-monitor -c monitor.yaml events

# Filter by agent
agent-monitor -c monitor.yaml events --agent sales-agent

# Filter by event type
agent-monitor -c monitor.yaml events --type denial

# Filter by time
agent-monitor -c monitor.yaml events --since "2026-03-01T00:00:00"

# Limit results
agent-monitor -c monitor.yaml events -n 50

# JSON output
agent-monitor -c monitor.yaml events --json
```

| Option | Default | Description |
|--------|---------|-------------|
| `-n`, `--limit` | `20` | Number of events to show |
| `-a`, `--agent` | -- | Filter by agent name |
| `-t`, `--type` | -- | Filter by event type |
| `--since` | -- | ISO timestamp filter |
| `--json` | `false` | Output as JSON |

---

### `agent-monitor alerts`

Show recent alerts from the alert log.

```bash
agent-monitor -c monitor.yaml alerts
agent-monitor -c monitor.yaml alerts -n 50
agent-monitor -c monitor.yaml alerts --json
```

| Option | Default | Description |
|--------|---------|-------------|
| `-n`, `--limit` | `20` | Number of alerts to show |
| `--json` | `false` | Output as JSON |

---

### `agent-monitor kill`

Kill an agent, session, or activate global kill. Takes a `TARGET` argument.

```bash
# Kill a specific agent
agent-monitor -c monitor.yaml kill sales-agent --reason "Cost spike"

# Kill a session
agent-monitor -c monitor.yaml kill sess-abc-123 --session --reason "Suspicious"

# Global kill
agent-monitor -c monitor.yaml kill ALL --global-kill --reason "Emergency"
```

| Argument/Option | Default | Description |
|--------|---------|-------------|
| `TARGET` | **(required)** | Agent name, session ID, or any string for global |
| `-r`, `--reason` | `""` | Reason for the kill |
| `--session` | `false` | Kill a session instead of an agent |
| `--global-kill` | `false` | Activate global kill |

---

### `agent-monitor revive`

Revive a killed agent, session, or deactivate global kill. Takes a `TARGET` argument.

```bash
# Revive a specific agent
agent-monitor -c monitor.yaml revive sales-agent

# Revive a session
agent-monitor -c monitor.yaml revive sess-abc-123 --session

# Deactivate global kill
agent-monitor -c monitor.yaml revive ALL --global-revive
```

| Argument/Option | Default | Description |
|--------|---------|-------------|
| `TARGET` | **(required)** | Agent name, session ID, or any string for global |
| `--session` | `false` | Revive a session instead of an agent |
| `--global-revive` | `false` | Deactivate global kill |

---

### `agent-monitor export`

Export a compliance report to stdout.

```bash
# JSON export
agent-monitor -c monitor.yaml export

# SOC 2 export
agent-monitor -c monitor.yaml export --format soc2

# GDPR export
agent-monitor -c monitor.yaml export --format gdpr

# Filtered by agent
agent-monitor -c monitor.yaml export --format json --agent sales-agent

# Filtered by time range
agent-monitor -c monitor.yaml export --format soc2 --since "2026-03-01T00:00:00" --until "2026-03-28T00:00:00"
```

| Option | Default | Description |
|--------|---------|-------------|
| `-f`, `--format` | `json` | Export format: `json`, `soc2`, `gdpr` |
| `-a`, `--agent` | -- | Filter by agent |
| `--since` | -- | ISO timestamp filter (start) |
| `--until` | -- | ISO timestamp filter (end) |

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Validation error, file not found, or other error |
