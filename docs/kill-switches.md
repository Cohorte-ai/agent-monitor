# Kill Switches

The kill switch is the most important safety mechanism in agent monitoring. It provides instant circuit-breaking at three levels.

---

## Why Kill Switches?

Standard monitoring alerts a human who then decides what to do. For AI agents, that's too slow. A runaway agent can:

- Spend $1,000 in API costs in minutes
- Send hundreds of unauthorized emails
- Exfiltrate sensitive data before anyone notices

Kill switches stop the agent immediately. No human in the loop for the emergency stop -- humans handle the investigation after the agent is safe.

---

## Three Levels

### Agent Kill

Block all events for a specific agent.

```python
monitor.kill_agent("sales-agent", reason="Cost spike detected")
```

### Session Kill

Block all events for a specific session.

```python
monitor.kill_session("sess-abc-123")
```

### Global Kill

Block all events for all agents. Emergency use only.

```python
monitor.kill_global(reason="System-wide anomaly")
```

---

## Manual Kill/Revive

### Kill

```python
# Kill a specific agent
monitor.kill_agent("sales-agent", reason="Investigation in progress")

# Kill a session
monitor.kill_session("sess-abc-123")

# Kill everything
monitor.kill_global(reason="Emergency shutdown")
```

### Check Status

```python
monitor.is_killed("sales-agent")                          # True/False
monitor.is_killed("sales-agent", session_id="sess-123")   # Also checks session
```

### Revive

```python
# Revive a specific agent
monitor.revive(agent="sales-agent")

# Revive a specific session
monitor.revive(session_id="sess-abc-123")

# Deactivate global kill
monitor.revive_global()
```

### CLI

```bash
# Kill an agent
agent-monitor -c monitor.yaml kill sales-agent --reason "Cost spike"

# Kill a session
agent-monitor -c monitor.yaml kill sess-abc-123 --session --reason "Suspicious"

# Global kill
agent-monitor -c monitor.yaml kill ALL --global-kill --reason "Emergency"

# Revive an agent
agent-monitor -c monitor.yaml revive sales-agent

# Revive a session
agent-monitor -c monitor.yaml revive sess-abc-123 --session

# Deactivate global kill
agent-monitor -c monitor.yaml revive ALL --global-revive
```

---

## Auto-Kill Policies

Auto-kill policies trigger automatically when a metric exceeds a threshold. No human intervention needed.

```yaml
kill_switch:
  enabled: true
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
```

### Policy Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Unique policy identifier |
| `metric` | string | Which metric to evaluate |
| `operator` | string | Comparison: `>`, `<`, `>=`, `<=`, `==` |
| `threshold` | float | Value that triggers the kill |
| `action` | string | `kill_agent`, `kill_session`, or `kill_global` |
| `severity` | string | Alert severity for the kill event |
| `message` | string | Optional custom message |

### How Policies Are Evaluated

After every metric snapshot:

1. For each policy, check if `metric <operator> threshold` is true
2. If yes, execute the action (kill agent/session/global)
3. Dispatch a kill alert to all configured channels

### Example: Cost Guard

```yaml
kill_switch:
  enabled: true
  policies:
    - name: cost-guard
      metric: cost_per_minute
      operator: ">"
      threshold: 1.0
      action: kill_agent
      severity: critical
```

If any agent's cost exceeds $1.00/minute, that agent is automatically killed. Other agents continue operating normally.

### Example: Global Emergency

```yaml
kill_switch:
  enabled: true
  policies:
    - name: flood-protection
      metric: event_count
      operator: ">"
      threshold: 50000
      action: kill_global
      severity: critical
```

If the total event count across any single agent exceeds 50,000, all agents are killed. This prevents runaway loops.

---

## Persistence

Kill state can survive restarts:

```yaml
kill_switch:
  state_path: /var/lib/agent-monitor/kill_state.json
```

When configured, the kill switch saves its state to disk after every kill/revive operation (via `save()`). On startup, call `load()` to restore saved state.

This means:

- An auto-killed agent stays killed after a restart
- A manually killed agent stays killed after a restart
- Only an explicit `revive(agent=...)` or `revive_global()` restores the agent

---

## How Events Are Rejected

When `monitor.record()` is called for a killed agent:

1. The kill switch is checked **first**, before any other processing
2. If the agent is killed, the event is **not** stored, metrics are **not** updated
3. `record()` returns `None` (it always returns `None`)

This is the fastest possible circuit breaker -- no metrics computation, no baseline updates, no anomaly detection. Just a set lookup (O(1)).

---

## Kill State Inspection

```python
state = monitor.kill_switch_engine.get_state()
print(state.killed_agents)    # {"sales-agent"}
print(state.killed_sessions)  # {"sess-abc-123"}
print(state.global_kill)      # False
print(state.reasons)          # {"agent:sales-agent": "Cost spike detected"}
```

---

## Best Practices

1. **Always set auto-kill on cost.** LLM API costs can spiral. A $5/min threshold is a reasonable starting point.

2. **Use agent-level kills, not global.** A misbehaving agent should not take down the entire system.

3. **Enable persistence.** Without persistence, a restart clears all kill states -- the agent you just killed comes back alive.

4. **Log kill reasons.** The `reason` parameter is stored and exported in compliance reports. Future-you will thank past-you.

5. **Test revive regularly.** Make sure your operators know how to revive agents. A killed agent that nobody knows how to revive is a production incident.
