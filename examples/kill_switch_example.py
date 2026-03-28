"""Kill Switch Example — Manual and automatic kill/revive."""

from __future__ import annotations

from theaios.agent_monitor import Monitor, AgentEvent
from theaios.agent_monitor.types import MonitorConfig

# Config with auto-kill policy: kill agent if cost_per_minute exceeds $1.00
config = MonitorConfig(
    version="1.0",
    agent_name="kill-switch-demo",
    metrics={"window_seconds": 60, "tracked": ["cost_per_minute", "event_count"]},
    kill_switch={
        "policies": [{
            "name": "auto-kill-expensive",
            "metric": "cost_per_minute",
            "threshold": 1.0,
            "action": "kill_agent",
            "severity": "critical",
        }],
    },
    alerts={"channels": [{"type": "console"}]},
)

monitor = Monitor(config)

# --- Manual Kill ---
print("=== Manual Kill ===")
print(f"Is killed? {monitor.is_killed('sales-agent')}")

monitor.kill_agent("sales-agent", reason="Suspicious behavior detected")
print(f"Is killed? {monitor.is_killed('sales-agent')}")

# Try to record an event — should be rejected
result = monitor.record(AgentEvent(
    event_type="llm_call", agent="sales-agent",
    data={"cost": 0.01, "latency_ms": 100.0},
))
print(f"Record result (killed agent): {result}")

# Revive the agent
monitor.revive_agent("sales-agent")
print(f"After revive — is killed? {monitor.is_killed('sales-agent')}")

# --- Automatic Kill ---
print("\n=== Automatic Kill (Cost Threshold) ===")

# Record many expensive events to trigger auto-kill
for i in range(50):
    ok = monitor.record(AgentEvent(
        event_type="llm_call", agent="expensive-bot",
        data={"cost": 0.5, "latency_ms": 50.0},
    ))
    if ok is False:
        print(f"Event {i+1} rejected — agent was killed")
        break
else:
    print("All events accepted (threshold may not have been reached yet)")

print(f"Is expensive-bot killed? {monitor.is_killed('expensive-bot')}")

# --- Global Kill ---
print("\n=== Global Kill ===")
monitor.kill_global(reason="Emergency: system-wide shutdown")
print(f"Is agent-a killed? {monitor.is_killed('agent-a')}")
print(f"Is agent-b killed? {monitor.is_killed('agent-b')}")

monitor.revive_global()
print(f"After global revive — is agent-a killed? {monitor.is_killed('agent-a')}")
