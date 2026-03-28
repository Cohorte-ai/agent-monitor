"""Agent Monitor Quickstart — Record events and view metrics in 10 lines."""

from __future__ import annotations

import time

from theaios.agent_monitor import Monitor, load_config, AgentEvent

# Load the config
config = load_config("examples/configs/basic.yaml")
monitor = Monitor(config)

# 1. Record an action (e.g., LLM call)
monitor.record(AgentEvent(
    timestamp=time.time(),
    event_type="action",
    agent="sales-agent",
    cost_usd=0.007,
    latency_ms=420.0,
    data={
        "model": "gpt-4",
        "prompt_tokens": 150,
        "completion_tokens": 80,
    },
))
print("Recorded action event")

# 2. Record a denial (guardrail blocked the request)
monitor.record(AgentEvent(
    timestamp=time.time(),
    event_type="denial",
    agent="sales-agent",
    data={
        "rule": "block-injection",
        "severity": "critical",
    },
))
print("Recorded denial event")

# 3. Record a guardrail trigger (non-denial, e.g., redact)
monitor.record(AgentEvent(
    timestamp=time.time(),
    event_type="guardrail_trigger",
    agent="sales-agent",
    data={
        "rule": "redact-pii",
        "outcome": "redact",
        "severity": "low",
    },
))
print("Recorded guardrail_trigger event")

# 4. Record a cost event
monitor.record(AgentEvent(
    timestamp=time.time(),
    event_type="cost",
    agent="sales-agent",
    cost_usd=0.003,
    data={
        "model": "gpt-4",
        "reason": "embedding call",
    },
))
print("Recorded cost event")

# 5. Record an error
monitor.record(AgentEvent(
    timestamp=time.time(),
    event_type="error",
    agent="sales-agent",
    data={
        "error_type": "TimeoutError",
        "message": "External API call timed out",
    },
))
print("Recorded error event")

# 6. View metrics
snap = monitor.get_metrics("sales-agent")
print(f"\n--- Metrics for sales-agent ---")
print(f"Event count:      {snap.event_count}")
print(f"Action count:     {snap.action_count}")
print(f"Denial count:     {snap.denial_count}")
print(f"Denial rate:      {snap.denial_rate:.1%}")
print(f"Cost/min:         ${snap.cost_per_minute:.4f}")
print(f"Avg latency:      {snap.avg_latency_ms:.1f}ms")

# 7. View recent events
events = monitor.get_events(agent="sales-agent")
print(f"\nTotal events:     {len(events)}")
for e in events:
    print(f"  [{e['event_type']}] {e.get('data', {})}")
