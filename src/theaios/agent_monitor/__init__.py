"""TheAIOS Agent Monitor — governance-first observability for AI agents."""

from __future__ import annotations

from theaios.agent_monitor.config import ConfigError, load_config
from theaios.agent_monitor.engine import Monitor
from theaios.agent_monitor.types import (
    AgentEvent,
    AgentTrackConfig,
    AlertChannelConfig,
    AlertChannelType,
    AlertConfig,
    AnomalyAlert,
    AnomalyDetectionConfig,
    AnomalyRuleConfig,
    Baseline,
    BaselineConfig,
    ComplianceFormat,
    EventType,
    KillAction,
    KillPolicyConfig,
    KillState,
    KillSwitchConfig,
    MetricSnapshot,
    MetricsEngineConfig,
    MonitorConfig,
    MonitorMetadata,
    Severity,
    StorageConfig,
)

__version__ = "0.1.0"

__all__ = [
    # Core
    "Monitor",
    "load_config",
    "record",
    "ConfigError",
    # Runtime types
    "AgentEvent",
    "MetricSnapshot",
    "Baseline",
    "AnomalyAlert",
    "KillState",
    # Enums
    "EventType",
    "Severity",
    "KillAction",
    "AlertChannelType",
    "ComplianceFormat",
    # Config types
    "MonitorConfig",
    "MonitorMetadata",
    "AgentTrackConfig",
    "BaselineConfig",
    "AnomalyRuleConfig",
    "AnomalyDetectionConfig",
    "KillPolicyConfig",
    "KillSwitchConfig",
    "AlertChannelConfig",
    "AlertConfig",
    "StorageConfig",
    "MetricsEngineConfig",
]

# ---------------------------------------------------------------------------
# Convenience singleton
# ---------------------------------------------------------------------------

_DEFAULT_MONITOR: Monitor | None = None


def record(event: AgentEvent) -> None:
    """Record an event using the default monitor singleton.

    On first call, loads the config from ``monitor.yaml`` in the
    current working directory (if it exists) or uses defaults.
    """
    global _DEFAULT_MONITOR
    if _DEFAULT_MONITOR is None:
        try:
            config = load_config()
        except FileNotFoundError:
            config = MonitorConfig()
        _DEFAULT_MONITOR = Monitor(config)
    _DEFAULT_MONITOR.record(event)
