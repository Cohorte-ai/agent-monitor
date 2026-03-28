"""Compliance Export Example — Record events and export a SOC 2 report."""

from __future__ import annotations

import json

from theaios.agent_monitor import Monitor, AgentEvent
from theaios.agent_monitor.types import MonitorConfig

config = MonitorConfig(
    version="1.0",
    agent_name="compliance-demo",
    metrics={"window_seconds": 300, "tracked": ["event_count", "denial_rate"]},
    compliance={"export_formats": ["soc2", "gdpr", "json"]},
    alerts={"channels": [{"type": "console"}]},
)

monitor = Monitor(config)

# Record a mix of events
events = [
    AgentEvent(
        event_type="llm_call", agent="finance-agent",
        data={"model": "gpt-4", "cost": 0.01, "latency_ms": 300.0},
    ),
    AgentEvent(
        event_type="guardrail_decision", agent="finance-agent",
        data={"rule": "block-injection", "outcome": "deny", "severity": "critical"},
    ),
    AgentEvent(
        event_type="llm_call", agent="sales-agent",
        data={"model": "gpt-4", "cost": 0.005, "latency_ms": 200.0},
    ),
    AgentEvent(
        event_type="guardrail_decision", agent="sales-agent",
        data={"rule": "redact-pii", "outcome": "allow", "severity": "low"},
    ),
    AgentEvent(
        event_type="tool_call", agent="finance-agent",
        data={"tool": "read_ledger", "latency_ms": 50.0, "success": True},
    ),
    AgentEvent(
        event_type="error", agent="sales-agent",
        data={"error_type": "RateLimitError", "message": "API rate limit exceeded"},
    ),
]

for event in events:
    monitor.record(event)

print(f"Recorded {len(events)} events\n")

# --- SOC 2 Export ---
print("=== SOC 2 Report ===")
soc2_report = monitor.export_compliance(fmt="soc2")
print(f"Format: {soc2_report['format']}")
print(f"Total events: {soc2_report['summary']['total_events']}")
print(f"Generated at: {soc2_report['generated_at']}")
print()

# --- GDPR Export ---
print("=== GDPR Report ===")
gdpr_report = monitor.export_compliance(fmt="gdpr")
print(f"Format: {gdpr_report['format']}")
print(f"Total events: {gdpr_report['summary']['total_events']}")
print()

# --- JSON Export ---
print("=== JSON Export ===")
json_report = monitor.export_compliance(fmt="json")
print(json.dumps(json_report, indent=2, default=str))

# --- Filtered Export ---
print("\n=== Filtered Export (finance-agent only) ===")
filtered_report = monitor.export_compliance(fmt="json", agent="finance-agent")
print(f"Events for finance-agent: {filtered_report['summary']['total_events']}")
