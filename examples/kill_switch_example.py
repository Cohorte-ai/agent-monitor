"""Kill Switch Example — Manual and automatic kill/revive."""

from __future__ import annotations

import time

from theaios.agent_monitor import Monitor, AgentEvent
from theaios.agent_monitor.types import (
    AlertChannelConfig,
    AlertConfig,
    KillPolicyConfig,
    KillSwitchConfig,
    MetricsEngineConfig,
    MonitorConfig,
)

# Config with auto-kill policy: kill agent if cost_per_minute exceeds $1.00
config = MonitorConfig(
    version="1.0",
    metrics=MetricsEngineConfig(default_window_seconds=60),
    kill_switch=KillSwitchConfig(
        enabled=True,
        policies=[
            KillPolicyConfig(
                name="auto-kill-expensive",
                metric="cost_per_minute",
                operator=">",
                threshold=1.0,
                action="kill_agent",
                severity="critical",
            ),
        ],
    ),
    alerts=AlertConfig(channels=[AlertChannelConfig(type="console")]),
)

monitor = Monitor(config)

# --- Manual Kill ---
print("=== Manual Kill ===")
print(f"Is killed? {monitor.is_killed('sales-agent')}")

monitor.kill_agent("sales-agent", reason="Suspicious behavior detected")
print(f"Is killed? {monitor.is_killed('sales-agent')}")

# Try to record an event — it will be silently dropped (record() returns None)
monitor.record(AgentEvent(
    timestamp=time.time(),
    event_type="action", agent="sales-agent",
    cost_usd=0.01, latency_ms=100.0,
))
# Verify the event was not counted
snap = monitor.get_metrics("sales-agent")
print(f"Events recorded while killed: {snap.event_count}")

# Revive the agent
monitor.revive(agent="sales-agent")
print(f"After revive — is killed? {monitor.is_killed('sales-agent')}")

# --- Automatic Kill ---
print("\n=== Automatic Kill (Cost Threshold) ===")

# Record many expensive events to trigger auto-kill
for i in range(50):
    if monitor.is_killed("expensive-bot"):
        print(f"Agent was killed after {i} recorded events")
        break
    monitor.record(AgentEvent(
        timestamp=time.time(),
        event_type="action", agent="expensive-bot",
        cost_usd=0.5, latency_ms=50.0,
    ))
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
