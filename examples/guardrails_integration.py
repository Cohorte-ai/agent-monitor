"""Guardrails Integration Example — Monitor wrapping a guardrails engine.

This example shows how GuardrailsMonitor bridges theaios-guardrails
decisions into the agent-monitor pipeline. The guardrails engine is
mocked here so you don't need it installed.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from theaios.agent_monitor import Monitor, AgentEvent
from theaios.agent_monitor.adapters.guardrails import GuardrailsMonitor
from theaios.agent_monitor.types import MonitorConfig

# Set up the monitor
config = MonitorConfig(
    version="1.0",
    agent_name="guardrails-integration-demo",
    metrics={
        "window_seconds": 300,
        "tracked": ["event_count", "denial_rate", "avg_latency_ms"],
    },
    alerts={"channels": [{"type": "console"}]},
)
monitor = Monitor(config)

# Wrap it with the guardrails adapter
gm = GuardrailsMonitor(monitor=monitor)

# --- Simulate guardrail evaluations ---

# 1. Normal input — ALLOW
allow_decision = MagicMock()
allow_decision.outcome = "allow"
allow_decision.rule = None
allow_decision.severity = None
allow_decision.evaluation_time_ms = 0.005

gm.record_decision(agent="sales-agent", decision=allow_decision)
print("Recorded: ALLOW decision")

# 2. Injection attempt — DENY
deny_decision = MagicMock()
deny_decision.outcome = "deny"
deny_decision.rule = "block-injection"
deny_decision.severity = "critical"
deny_decision.evaluation_time_ms = 0.003

gm.record_decision(agent="sales-agent", decision=deny_decision)
print("Recorded: DENY decision (block-injection)")

# 3. External email — REQUIRE_APPROVAL
approval_decision = MagicMock()
approval_decision.outcome = "require_approval"
approval_decision.rule = "external-email-approval"
approval_decision.severity = "medium"
approval_decision.evaluation_time_ms = 0.004

gm.record_decision(agent="sales-agent", decision=approval_decision)
print("Recorded: REQUIRE_APPROVAL decision")

# 4. PII in output — REDACT
redact_decision = MagicMock()
redact_decision.outcome = "redact"
redact_decision.rule = "redact-pii"
redact_decision.severity = "high"
redact_decision.evaluation_time_ms = 0.008

gm.record_decision(agent="sales-agent", decision=redact_decision)
print("Recorded: REDACT decision")

# --- View metrics ---
snap = monitor.get_metrics("sales-agent")
print(f"\n--- Metrics for sales-agent ---")
print(f"Total events:     {snap.event_count}")
print(f"Denial rate:      {snap.denial_rate:.1%}")

# --- View events ---
events = monitor.get_events(agent="sales-agent")
print(f"\n--- Events ---")
for e in events:
    print(f"  [{e.event_type}] outcome={e.data.get('outcome', '?')} rule={e.data.get('rule', '-')}")
