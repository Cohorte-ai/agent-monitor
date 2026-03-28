"""Agent Monitor Quickstart — Record events and view metrics in 10 lines."""

from __future__ import annotations

from theaios.agent_monitor import Monitor, load_config, AgentEvent

# Load the config
config = load_config("examples/configs/basic.yaml")
monitor = Monitor(config)

# 1. Record an LLM call
monitor.record(AgentEvent(
    event_type="llm_call",
    agent="sales-agent",
    data={
        "model": "gpt-4",
        "prompt_tokens": 150,
        "completion_tokens": 80,
        "latency_ms": 420.0,
        "cost": 0.007,
    },
))
print("Recorded LLM call")

# 2. Record a guardrail decision (deny)
monitor.record(AgentEvent(
    event_type="guardrail_decision",
    agent="sales-agent",
    data={
        "rule": "block-injection",
        "outcome": "deny",
        "severity": "critical",
    },
))
print("Recorded guardrail denial")

# 3. Record a guardrail decision (allow)
monitor.record(AgentEvent(
    event_type="guardrail_decision",
    agent="sales-agent",
    data={
        "rule": "redact-pii",
        "outcome": "allow",
        "severity": "low",
    },
))
print("Recorded guardrail allow")

# 4. Record a tool call
monitor.record(AgentEvent(
    event_type="tool_call",
    agent="sales-agent",
    data={
        "tool": "search_crm",
        "latency_ms": 85.0,
        "success": True,
    },
))
print("Recorded tool call")

# 5. Record an error
monitor.record(AgentEvent(
    event_type="error",
    agent="sales-agent",
    data={
        "error_type": "TimeoutError",
        "message": "External API call timed out",
    },
))
print("Recorded error")

# 6. View metrics
snap = monitor.get_metrics("sales-agent")
print(f"\n--- Metrics for sales-agent ---")
print(f"Event count:      {snap.event_count}")
print(f"Denial rate:      {snap.denial_rate:.1%}")
print(f"Cost/min:         ${snap.cost_per_minute:.4f}")
print(f"Avg latency:      {snap.avg_latency_ms:.1f}ms")

# 7. View recent events
events = monitor.get_events(agent="sales-agent")
print(f"\nTotal events:     {len(events)}")
for e in events:
    print(f"  [{e.event_type}] {e.data}")
