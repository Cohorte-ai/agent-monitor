# theaios-agent-monitor

**Governance-first observability for AI agents -- real-time metrics, anomaly detection, kill switches, compliance export.**

theaios-agent-monitor is a monitoring engine that lets you observe, baseline, and control AI agent behavior with YAML configs. Record events, compute real-time metrics, detect anomalies via z-score baselines, trigger automatic kill switches, and export compliance reports. No external services. No vendor lock-in.

## Why Governance-First?

Because monitoring AI agents is not the same as monitoring web apps. The failure modes are different:

- An agent that starts denying everything is broken -- even if the server is up
- A cost spike from $0.01/min to $5/min is invisible to standard APM tools
- A sudden change in denial patterns means your guardrails are either catching a real attack or misconfigured
- When something goes wrong, you need to **kill the agent instantly** -- not wait for an on-call rotation

theaios-agent-monitor is built for these scenarios. Traditional observability tools (Datadog, Grafana, LangSmith) collect data. This library collects data **and acts on it** -- anomaly detection, automatic kill switches, compliance export.

## What It Does

```
Agent event (action, guardrail_trigger, denial, approval_request, cost, error, ...)
    |
    v
EventStore (append-only JSONL log)
    |
    v
MetricsEngine (rolling window: event_count, denial_rate, cost/min, latency)
    |
    v
BaselineTracker (Welford's algorithm: mean, stddev, z-score)
    |
    v
AnomalyDetector (z-score threshold rules with cooldown)
    |
    v
KillSwitch (manual or auto kill/revive, persistence)
    |
    v
AlertDispatcher (console, file, webhook)
    |
    v
ComplianceExporter (SOC 2, GDPR, JSON)
```

Every event is recorded. Every metric is computed in real time. Every anomaly is detectable. Every agent is killable.

## Quick Start

```bash
pip install theaios-agent-monitor
```

```yaml
# monitor.yaml
version: "1.0"
metadata:
  name: my-monitor

metrics:
  default_window_seconds: 300

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
```

```python
import time
from theaios.agent_monitor import Monitor, load_config, AgentEvent

monitor = Monitor(load_config("monitor.yaml"))

monitor.record(AgentEvent(
    timestamp=time.time(), event_type="action", agent="sales-agent",
    cost_usd=0.007, latency_ms=350.0,
    data={"model": "gpt-4"},
))

snap = monitor.get_metrics("sales-agent")
print(f"Events: {snap.event_count}, Cost/min: ${snap.cost_per_minute:.4f}")
```

## Documentation

| Page | What you'll learn |
|------|-------------------|
| [Concepts](concepts.md) | Monitor pipeline, event model, metrics, baselines, anomaly detection, kill switches |
| [Config Syntax](config-syntax.md) | Complete YAML reference for every field |
| [Events](events.md) | Event types, how to record, EventStore |
| [Metrics & Baselines](metrics-and-baselines.md) | Metrics engine, Welford's algorithm, z-score |
| [Kill Switches](kill-switches.md) | Kill/revive, auto-kill policies, persistence |
| [Compliance](compliance.md) | SOC 2, GDPR, JSON export |
| [Integration](integration.md) | Guardrails adapter, OpenTelemetry, custom adapters |
| [CLI Reference](cli.md) | `agent-monitor version`, `validate`, `inspect`, `status`, `events`, `kill`, `revive`, `export` |
| [Python API](api-reference.md) | `Monitor`, `load_config`, `AgentEvent`, all data types |
| [AI Config Generator](ai-config-generator.md) | Copy-paste prompts for generating monitor.yaml with any LLM |

## Part of the theaios Ecosystem

theaios-agent-monitor is one of the [theaios](https://github.com/Cohorte-ai) platform components. It works standalone or alongside:

- [theaios-guardrails](https://github.com/Cohorte-ai/guardrails) -- declarative guardrails for AI agent governance
- [theaios-context-router](https://github.com/Cohorte-ai/context-router) -- intelligent context routing for AI agents
