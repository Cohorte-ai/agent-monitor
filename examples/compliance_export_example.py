"""Compliance Export Example — Record events and export a SOC 2 report."""

from __future__ import annotations

import json
import time

from theaios.agent_monitor import Monitor, AgentEvent
from theaios.agent_monitor.types import (
    AlertChannelConfig,
    AlertConfig,
    MonitorConfig,
)

config = MonitorConfig(
    version="1.0",
    alerts=AlertConfig(channels=[AlertChannelConfig(type="console")]),
)

monitor = Monitor(config)

# Record a mix of events
now = time.time()
events = [
    AgentEvent(
        timestamp=now,
        event_type="action", agent="finance-agent",
        cost_usd=0.01, latency_ms=300.0,
        data={"model": "gpt-4"},
    ),
    AgentEvent(
        timestamp=now + 0.1,
        event_type="denial", agent="finance-agent",
        data={"rule": "block-injection", "severity": "critical"},
    ),
    AgentEvent(
        timestamp=now + 0.2,
        event_type="action", agent="sales-agent",
        cost_usd=0.005, latency_ms=200.0,
        data={"model": "gpt-4"},
    ),
    AgentEvent(
        timestamp=now + 0.3,
        event_type="guardrail_trigger", agent="sales-agent",
        data={"rule": "redact-pii", "outcome": "redact", "severity": "low"},
    ),
    AgentEvent(
        timestamp=now + 0.4,
        event_type="action", agent="finance-agent",
        latency_ms=50.0,
        data={"tool": "read_ledger"},
    ),
    AgentEvent(
        timestamp=now + 0.5,
        event_type="error", agent="sales-agent",
        data={"error_type": "RateLimitError", "message": "API rate limit exceeded"},
    ),
]

for event in events:
    monitor.record(event)

print(f"Recorded {len(events)} events\n")

# --- SOC 2 Export ---
print("=== SOC 2 Report ===")
soc2_output = monitor.compliance_exporter.export(format="soc2")
soc2_report = json.loads(soc2_output)
print(f"Format: {soc2_report['format']}")
print(f"Total events: {soc2_report['summary']['total_events']}")
print(f"Generated at: {soc2_report['generated_at']}")
print()

# --- GDPR Export ---
print("=== GDPR Report ===")
gdpr_output = monitor.compliance_exporter.export(format="gdpr")
gdpr_report = json.loads(gdpr_output)
print(f"Format: {gdpr_report['format']}")
print(f"Total events: {gdpr_report['summary']['total_processing_events']}")
print()

# --- JSON Export ---
print("=== JSON Export ===")
json_output = monitor.compliance_exporter.export(format="json")
json_report = json.loads(json_output)
print(json.dumps(json_report, indent=2, default=str))

# --- Filtered Export ---
print("\n=== Filtered Export (finance-agent only) ===")
filtered_output = monitor.compliance_exporter.export(format="json", agent="finance-agent")
filtered_report = json.loads(filtered_output)
print(f"Events for finance-agent: {filtered_report['total_events']}")
