"""Shared data models for the Agent Monitor engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class EventType(Enum):
    """Types of agent events tracked by the monitor."""

    ACTION = "action"
    GUARDRAIL_TRIGGER = "guardrail_trigger"
    APPROVAL_REQUEST = "approval_request"
    APPROVAL_RESPONSE = "approval_response"
    DENIAL = "denial"
    COST = "cost"
    ERROR = "error"
    SESSION_START = "session_start"
    SESSION_END = "session_end"


class Severity(Enum):
    """Alert severity levels, ordered from lowest to highest."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class KillAction(Enum):
    """Actions that can be taken by the kill switch."""

    KILL_AGENT = "kill_agent"
    KILL_SESSION = "kill_session"
    KILL_GLOBAL = "kill_global"


class AlertChannelType(Enum):
    """Supported alert channel types."""

    CONSOLE = "console"
    FILE = "file"
    WEBHOOK = "webhook"


class ComplianceFormat(Enum):
    """Supported compliance export formats."""

    SOC2 = "soc2"
    GDPR = "gdpr"
    JSON = "json"


VALID_EVENT_TYPES = {e.value for e in EventType}
VALID_SEVERITIES = {s.value for s in Severity}
VALID_KILL_ACTIONS = {k.value for k in KillAction}
VALID_ALERT_CHANNELS = {c.value for c in AlertChannelType}
VALID_COMPLIANCE_FORMATS = {f.value for f in ComplianceFormat}
VALID_METRICS = {
    "event_count",
    "action_count",
    "denial_count",
    "denial_rate",
    "approval_count",
    "approval_rate",
    "error_count",
    "cost_total",
    "cost_per_minute",
    "avg_latency_ms",
}

SEVERITY_ORDER: dict[str, int] = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
}


# ---------------------------------------------------------------------------
# Runtime data models
# ---------------------------------------------------------------------------


@dataclass
class AgentEvent:
    """A single event emitted by an AI agent.

    Represents an observable action, guardrail trigger, approval,
    denial, cost record, or error within the agentic system.
    """

    timestamp: float
    agent: str
    event_type: str
    data: dict[str, object] = field(default_factory=dict)
    session_id: str | None = None
    user: str | None = None
    cost_usd: float | None = None
    latency_ms: float | None = None
    tags: list[str] = field(default_factory=list)


@dataclass
class MetricSnapshot:
    """Point-in-time metrics for a single agent within a rolling window."""

    agent: str
    window_seconds: int
    timestamp: float
    event_count: int = 0
    action_count: int = 0
    denial_count: int = 0
    denial_rate: float = 0.0
    approval_count: int = 0
    approval_rate: float = 0.0
    error_count: int = 0
    cost_total: float = 0.0
    cost_per_minute: float = 0.0
    avg_latency_ms: float = 0.0


@dataclass
class Baseline:
    """Statistical baseline for a single metric of a single agent."""

    agent: str
    metric: str
    mean: float = 0.0
    stddev: float = 0.0
    sample_count: int = 0
    last_updated: float = 0.0


@dataclass
class AnomalyAlert:
    """An anomaly detected by the anomaly detector."""

    agent: str
    rule: str
    metric: str
    value: float
    z_score: float
    threshold: float
    severity: str
    message: str
    timestamp: float = 0.0


@dataclass
class KillState:
    """Current state of all kill switches."""

    killed_agents: set[str] = field(default_factory=set)
    killed_sessions: set[str] = field(default_factory=set)
    global_kill: bool = False
    reasons: dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Configuration data models (parsed from YAML)
# ---------------------------------------------------------------------------


@dataclass
class AgentTrackConfig:
    """Per-agent tracking configuration."""

    name: str
    enabled: bool = True
    event_types: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


@dataclass
class BaselineConfig:
    """Configuration for baseline tracking."""

    enabled: bool = True
    min_samples: int = 30
    metrics: list[str] = field(
        default_factory=lambda: [
            "denial_rate",
            "error_count",
            "cost_per_minute",
            "avg_latency_ms",
        ]
    )
    storage_path: str = ".agent_monitor/baselines.json"


@dataclass
class AnomalyRuleConfig:
    """A single anomaly detection rule."""

    name: str
    metric: str
    z_threshold: float = 3.0
    severity: str = "high"
    cooldown_seconds: int = 300
    condition: str = ""


@dataclass
class AnomalyDetectionConfig:
    """Configuration for anomaly detection."""

    enabled: bool = True
    rules: list[AnomalyRuleConfig] = field(default_factory=list)


@dataclass
class KillPolicyConfig:
    """A single kill switch policy — auto-kills when conditions are met."""

    name: str
    metric: str
    operator: str  # >, <, >=, <=, ==
    threshold: float
    action: str = "kill_agent"
    severity: str = "critical"
    message: str = ""


@dataclass
class KillSwitchConfig:
    """Configuration for the kill switch system."""

    enabled: bool = True
    policies: list[KillPolicyConfig] = field(default_factory=list)
    state_path: str = ".agent_monitor/kill_state.json"


@dataclass
class AlertChannelConfig:
    """Configuration for a single alert channel."""

    type: str
    enabled: bool = True
    path: str = ""
    url: str = ""
    min_severity: str = "low"
    headers: dict[str, str] = field(default_factory=dict)


@dataclass
class AlertConfig:
    """Configuration for the alert dispatcher."""

    channels: list[AlertChannelConfig] = field(default_factory=list)


@dataclass
class StorageConfig:
    """Configuration for event storage."""

    path: str = ".agent_monitor/events.jsonl"
    retention_days: int = 90


@dataclass
class MetricsEngineConfig:
    """Configuration for the metrics engine."""

    default_window_seconds: int = 300
    max_window_seconds: int = 3600


@dataclass
class MonitorMetadata:
    """Monitor-level metadata."""

    name: str = ""
    description: str = ""
    author: str = ""


@dataclass
class MonitorConfig:
    """Top-level monitor configuration — maps 1:1 to monitor.yaml."""

    version: str = "1.0"
    metadata: MonitorMetadata = field(default_factory=MonitorMetadata)
    variables: dict[str, object] = field(default_factory=dict)
    agents: dict[str, AgentTrackConfig] = field(default_factory=dict)
    storage: StorageConfig = field(default_factory=StorageConfig)
    metrics: MetricsEngineConfig = field(default_factory=MetricsEngineConfig)
    baselines: BaselineConfig = field(default_factory=BaselineConfig)
    anomaly_detection: AnomalyDetectionConfig = field(default_factory=AnomalyDetectionConfig)
    kill_switch: KillSwitchConfig = field(default_factory=KillSwitchConfig)
    alerts: AlertConfig = field(default_factory=AlertConfig)
