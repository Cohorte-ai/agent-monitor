<div align="center">
  <a href="https://cohorte-ai.github.io/agent-monitor/">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset=".github/images/TheAIOS-Agent-Monitor-darkmode.svg">
      <source media="(prefers-color-scheme: light)" srcset=".github/images/TheAIOS-Agent-Monitor.svg">
      <img alt="theaios-agent-monitor" src=".github/images/TheAIOS-Agent-Monitor.svg" width="60%">
    </picture>
  </a>
</div>

<div align="center">
  <h3>Governance-first observability for AI agents -- real-time metrics, anomaly detection, kill switches, compliance export.</h3>
</div>

<div align="center">
  <a href="https://opensource.org/licenses/Apache-2.0" target="_blank"><img src="https://img.shields.io/badge/license-Apache%202.0-blue" alt="License"></a>
  <a href="https://pypi.org/project/theaios-agent-monitor/" target="_blank"><img src="https://img.shields.io/pypi/v/theaios-agent-monitor" alt="PyPI"></a>
  <a href="https://cohorte-ai.github.io/agent-monitor/" target="_blank"><img src="https://img.shields.io/badge/docs-mkdocs-blue" alt="Docs"></a>
  <a href="https://x.com/CohorteAI" target="_blank"><img src="https://img.shields.io/twitter/follow/CohorteAI?style=social" alt="Follow @CohorteAI"></a>
</div>

<br>

> [!NOTE]
> Part of the [theaios](https://github.com/Cohorte-ai) ecosystem. Install with `pip install theaios-agent-monitor`.

## What It Does

Record every agent event. Compute real-time metrics over rolling windows. Detect anomalies via z-score baselines. Kill misbehaving agents instantly. Export compliance reports. All in-process, no external services, ~0.1ms per event.

This is **not** LangSmith, Langfuse, or Arize. Those are tracing platforms that collect data. This library collects data **and acts on it** -- anomaly detection triggers alerts, kill switches stop agents, compliance export generates audit reports. Governance, not just observation.

- **Event collection** -- record LLM calls, tool calls, guardrail decisions, errors, custom events
- **Real-time metrics** -- event count, denial rate, cost/minute, average latency over configurable rolling windows
- **Statistical baselines** -- Welford's online algorithm for running mean and stddev, z-score anomaly detection
- **Kill switches** -- instant agent/session/global kill, automatic kill policies on metric thresholds, persistence across restarts
- **Anomaly detection** -- z-score rules with configurable thresholds, cooldown periods, wildcard agent matching
- **Compliance export** -- SOC 2, GDPR, JSON reports with filtering by agent, time range, event type
- **Alert channels** -- console, JSONL file, webhook (Slack, PagerDuty, OpsGenie)
- **OpenTelemetry** -- optional export to any OTel-compatible backend
- **Guardrails adapter** -- auto-record every theaios-guardrails decision

## Quick Start

```bash
pip install theaios-agent-monitor
```

**1. Write a config:**

```yaml
# monitor.yaml
version: "1.0"
agent_name: my-agent

metrics:
  window_seconds: 300
  tracked: [event_count, denial_rate, cost_per_minute, avg_latency_ms]

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
```

**2. Use it:**

```python
from theaios.agent_monitor import Monitor, load_config, AgentEvent

monitor = Monitor(load_config("monitor.yaml"))

# Record events
monitor.record(AgentEvent(
    event_type="llm_call",
    agent="sales-agent",
    data={"model": "gpt-4", "latency_ms": 350.0, "cost": 0.007},
))

# View metrics
snap = monitor.get_metrics("sales-agent")
print(f"Events: {snap.event_count}")
print(f"Cost/min: ${snap.cost_per_minute:.4f}")
print(f"Denial rate: {snap.denial_rate:.1%}")

# Kill an agent
monitor.kill_agent("sales-agent", reason="Cost spike detected")
```

**Events** tell the monitor what's happening. Each event has an `event_type`, an `agent`, and a `data` dict:

```python
# LLM call with cost and latency
monitor.record(AgentEvent(
    event_type="llm_call", agent="my-agent",
    data={"model": "gpt-4", "latency_ms": 350.0, "cost": 0.007},
))

# Guardrail decision (feeds denial_rate metric)
monitor.record(AgentEvent(
    event_type="guardrail_decision", agent="my-agent",
    data={"rule": "block-injection", "outcome": "deny", "severity": "critical"},
))

# Tool call
monitor.record(AgentEvent(
    event_type="tool_call", agent="my-agent",
    data={"tool": "search_api", "latency_ms": 120.0, "success": True},
))

# Error
monitor.record(AgentEvent(
    event_type="error", agent="my-agent",
    data={"error_type": "TimeoutError", "message": "LLM call timed out"},
))
```

**3. CLI:**

```bash
agent-monitor validate --config monitor.yaml
agent-monitor inspect --config monitor.yaml
agent-monitor record --config monitor.yaml --event '{"event_type":"llm_call","agent":"test","data":{"cost":0.01}}'
agent-monitor metrics --config monitor.yaml --agent test
agent-monitor kill --config monitor.yaml --agent test --reason "Cost spike"
agent-monitor revive --config monitor.yaml --agent test
agent-monitor export --config monitor.yaml --format soc2
```

## Why This Library?

Every agentic system needs monitoring. The options today:

| Approach | Problem |
|----------|---------|
| **LangSmith / Langfuse** | Tracing only -- no kill switches, no anomaly detection, no compliance export |
| **Arize / Weights & Biases** | ML-focused, not agent-governance-focused, expensive at scale |
| **Datadog / Grafana** | Generic APM -- doesn't understand denial rates, guardrail decisions, or agent costs |
| **Build your own** | Months of engineering, no standard format, no z-score baselines |

theaios-agent-monitor is **governance-first** (kill switches and compliance, not just dashboards), **statistical** (z-score anomaly detection, not threshold-only), **instant** (in-process, ~0.1ms/event, no external services), and **declarative** (YAML configs that ops teams can read).

## Source Types

| Source | What it provides |
|--------|-----------------|
| **Events** | Append-only log of every agent action |
| **Metrics** | Rolling window: event_count, denial_rate, cost_per_minute, avg_latency_ms |
| **Baselines** | Welford's algorithm: running mean, stddev, z-score |
| **Anomalies** | Z-score threshold alerts with cooldown |
| **Kill switches** | Agent/session/global kill with auto-policies |
| **Compliance** | SOC 2, GDPR, JSON export |

## Documentation

Full documentation at **[cohorte-ai.github.io/agent-monitor](https://cohorte-ai.github.io/agent-monitor/)** -- including the [config syntax reference](https://cohorte-ai.github.io/agent-monitor/config-syntax/), [events](https://cohorte-ai.github.io/agent-monitor/events/), [metrics & baselines](https://cohorte-ai.github.io/agent-monitor/metrics-and-baselines/), [kill switches](https://cohorte-ai.github.io/agent-monitor/kill-switches/), [compliance](https://cohorte-ai.github.io/agent-monitor/compliance/), and [integration guide](https://cohorte-ai.github.io/agent-monitor/integration/).

## Part of the theaios Ecosystem

theaios-agent-monitor is one of the [theaios](https://github.com/Cohorte-ai) platform components. It works standalone or alongside:

- [theaios-guardrails](https://github.com/Cohorte-ai/guardrails) -- declarative guardrails for AI agent governance
- [theaios-context-router](https://github.com/Cohorte-ai/context-router) -- intelligent context routing for AI agents

## License

Apache 2.0 -- see [LICENSE](LICENSE).
