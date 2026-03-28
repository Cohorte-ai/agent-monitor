"""Guardrails Integration Example — Monitor wrapping a guardrails engine.

This example shows how GuardrailsMonitor bridges theaios-guardrails
decisions into the agent-monitor pipeline. The guardrails engine is
mocked here so you don't need it installed.

The adapter wraps the guardrails Engine: instead of calling engine.evaluate(),
you call wrapped.evaluate(), and the adapter automatically records the
decision as an AgentEvent.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from theaios.agent_monitor import Monitor
from theaios.agent_monitor.adapters.guardrails import GuardrailsMonitor
from theaios.agent_monitor.types import (
    AlertChannelConfig,
    AlertConfig,
    MonitorConfig,
)

# Set up the monitor
config = MonitorConfig(
    version="1.0",
    alerts=AlertConfig(channels=[AlertChannelConfig(type="console")]),
)
monitor = Monitor(config)

# Mock the guardrails engine
mock_engine = MagicMock()

# Wrap it with the guardrails adapter
gm = GuardrailsMonitor(engine=mock_engine, monitor=monitor)

# --- Simulate guardrail evaluations ---

# 1. Normal input — ALLOW
allow_decision = MagicMock()
allow_decision.outcome = "allow"
allow_decision.rule = None
allow_decision.reason = None
allow_decision.severity = None
allow_decision.dry_run = False
allow_decision.matched_rules = []
mock_engine.evaluate.return_value = allow_decision

allow_event = MagicMock()
allow_event.agent = "sales-agent"
allow_event.session_id = None
allow_event.scope = "input"

gm.evaluate(allow_event)
print("Recorded: ALLOW decision (maps to event_type='action')")

# 2. Injection attempt — DENY
deny_decision = MagicMock()
deny_decision.outcome = "deny"
deny_decision.rule = "block-injection"
deny_decision.reason = "Prompt injection detected"
deny_decision.severity = "critical"
deny_decision.dry_run = False
deny_decision.matched_rules = ["block-injection"]
mock_engine.evaluate.return_value = deny_decision

deny_event = MagicMock()
deny_event.agent = "sales-agent"
deny_event.session_id = None
deny_event.scope = "input"

gm.evaluate(deny_event)
print("Recorded: DENY decision (maps to event_type='denial')")

# 3. External email — REQUIRE_APPROVAL
approval_decision = MagicMock()
approval_decision.outcome = "require_approval"
approval_decision.rule = "external-email-approval"
approval_decision.reason = "External email requires approval"
approval_decision.severity = "medium"
approval_decision.dry_run = False
approval_decision.matched_rules = ["external-email-approval"]
mock_engine.evaluate.return_value = approval_decision

approval_event = MagicMock()
approval_event.agent = "sales-agent"
approval_event.session_id = None
approval_event.scope = "action"

gm.evaluate(approval_event)
print("Recorded: REQUIRE_APPROVAL decision (maps to event_type='approval_request')")

# 4. PII in output — REDACT
redact_decision = MagicMock()
redact_decision.outcome = "redact"
redact_decision.rule = "redact-pii"
redact_decision.reason = "PII detected in output"
redact_decision.severity = "high"
redact_decision.dry_run = False
redact_decision.matched_rules = ["redact-pii"]
mock_engine.evaluate.return_value = redact_decision

redact_event = MagicMock()
redact_event.agent = "sales-agent"
redact_event.session_id = None
redact_event.scope = "output"

gm.evaluate(redact_event)
print("Recorded: REDACT decision (maps to event_type='action')")

# --- View metrics ---
snap = monitor.get_metrics("sales-agent")
print(f"\n--- Metrics for sales-agent ---")
print(f"Total events:     {snap.event_count}")
print(f"Action count:     {snap.action_count}")
print(f"Denial count:     {snap.denial_count}")
print(f"Denial rate:      {snap.denial_rate:.1%}")

# --- View events ---
events = monitor.get_events(agent="sales-agent")
print(f"\n--- Events ---")
for e in events:
    print(f"  [{e['event_type']}] outcome={e.get('data', {}).get('outcome', '?')} rule={e.get('data', {}).get('rule', '-')}")
