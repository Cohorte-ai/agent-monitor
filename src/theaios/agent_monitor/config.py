"""YAML monitor config loader and validation."""

from __future__ import annotations

import os
import re
from pathlib import Path

import yaml

from theaios.agent_monitor.types import (
    VALID_ALERT_CHANNELS,
    VALID_EVENT_TYPES,
    VALID_KILL_ACTIONS,
    VALID_SEVERITIES,
    AgentTrackConfig,
    AlertChannelConfig,
    AlertConfig,
    AnomalyDetectionConfig,
    AnomalyRuleConfig,
    BaselineConfig,
    KillPolicyConfig,
    KillSwitchConfig,
    MetricsEngineConfig,
    MonitorConfig,
    MonitorMetadata,
    StorageConfig,
)

_ENV_PATTERN = re.compile(r"\$\{(\w+)(?::([^}]*))?\}")


class ConfigError(Exception):
    """Raised when a monitor config file is invalid."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("Invalid monitor config:\n  " + "\n  ".join(errors))


def _interpolate_env(value: str) -> str:
    """Replace ${ENV_VAR} and ${ENV_VAR:default} in a string."""

    def _replace(match: re.Match[str]) -> str:
        var_name = match.group(1)
        default = match.group(2)
        env_val = os.environ.get(var_name)
        if env_val is not None:
            return env_val
        if default is not None:
            return default
        return match.group(0)

    return _ENV_PATTERN.sub(_replace, value)


def _interpolate_recursive(obj: object) -> object:
    """Recursively interpolate environment variables in a data structure."""
    if isinstance(obj, str):
        return _interpolate_env(obj)
    if isinstance(obj, dict):
        return {k: _interpolate_recursive(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_interpolate_recursive(item) for item in obj]
    return obj


def load_config(path: str = "monitor.yaml") -> MonitorConfig:
    """Load a YAML monitor config file, validate, and return typed config."""
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Monitor config file not found: {path}")

    with open(config_path) as f:
        raw = yaml.safe_load(f)

    if not isinstance(raw, dict):
        raise ConfigError(["Config file must be a YAML mapping"])

    raw = _interpolate_recursive(raw)
    if not isinstance(raw, dict):
        raise ConfigError(["Config file must be a YAML mapping after interpolation"])

    config = _parse_config(raw)

    errors = validate_config(config)
    if errors:
        raise ConfigError(errors)

    return config


def _parse_config(raw: dict[str, object]) -> MonitorConfig:
    """Parse raw YAML dict into typed MonitorConfig."""

    # Version
    version = str(raw.get("version", "1.0"))

    # Metadata
    meta_raw = raw.get("metadata", {})
    if not isinstance(meta_raw, dict):
        meta_raw = {}
    metadata = MonitorMetadata(
        name=str(meta_raw.get("name", "")),
        description=str(meta_raw.get("description", "")),
        author=str(meta_raw.get("author", "")),
    )

    # Variables
    variables_raw = raw.get("variables", {})
    variables: dict[str, object] = dict(variables_raw) if isinstance(variables_raw, dict) else {}

    # Agents
    agents: dict[str, AgentTrackConfig] = {}
    agents_raw = raw.get("agents", {})
    if isinstance(agents_raw, dict):
        for name, araw in agents_raw.items():
            if not isinstance(araw, dict):
                araw = {}
            event_types_raw = araw.get("event_types", [])
            event_types = (
                [str(e) for e in event_types_raw] if isinstance(event_types_raw, list) else []
            )
            tags_raw = araw.get("tags", [])
            tags = [str(t) for t in tags_raw] if isinstance(tags_raw, list) else []
            agents[str(name)] = AgentTrackConfig(
                name=str(name),
                enabled=bool(araw.get("enabled", True)),
                event_types=event_types,
                tags=tags,
            )

    # Storage
    storage_raw = raw.get("storage", {})
    if not isinstance(storage_raw, dict):
        storage_raw = {}
    storage = StorageConfig(
        path=str(storage_raw.get("path", ".agent_monitor/events.jsonl")),
        retention_days=int(storage_raw.get("retention_days", 90)),
    )

    # Metrics
    metrics_raw = raw.get("metrics", {})
    if not isinstance(metrics_raw, dict):
        metrics_raw = {}
    metrics_config = MetricsEngineConfig(
        default_window_seconds=int(metrics_raw.get("default_window_seconds", 300)),
        max_window_seconds=int(metrics_raw.get("max_window_seconds", 3600)),
    )

    # Baselines
    baselines_raw = raw.get("baselines", {})
    if not isinstance(baselines_raw, dict):
        baselines_raw = {}
    bl_metrics_raw = baselines_raw.get(
        "metrics",
        [
            "denial_rate",
            "error_count",
            "cost_per_minute",
            "avg_latency_ms",
        ],
    )
    bl_metrics = [str(m) for m in bl_metrics_raw] if isinstance(bl_metrics_raw, list) else []
    baselines = BaselineConfig(
        enabled=bool(baselines_raw.get("enabled", True)),
        min_samples=int(baselines_raw.get("min_samples", 30)),
        metrics=bl_metrics,
        storage_path=str(baselines_raw.get("storage_path", ".agent_monitor/baselines.json")),
    )

    # Anomaly detection
    anomaly_raw = raw.get("anomaly_detection", {})
    if not isinstance(anomaly_raw, dict):
        anomaly_raw = {}
    anomaly_rules: list[AnomalyRuleConfig] = []
    rules_raw = anomaly_raw.get("rules", [])
    if isinstance(rules_raw, list):
        for rraw in rules_raw:
            if not isinstance(rraw, dict):
                continue
            anomaly_rules.append(
                AnomalyRuleConfig(
                    name=str(rraw.get("name", "")),
                    metric=str(rraw.get("metric", "")),
                    z_threshold=float(rraw.get("z_threshold", 3.0)),
                    severity=str(rraw.get("severity", "high")),
                    cooldown_seconds=int(rraw.get("cooldown_seconds", 300)),
                    condition=str(rraw.get("condition", "")),
                )
            )
    anomaly_detection = AnomalyDetectionConfig(
        enabled=bool(anomaly_raw.get("enabled", True)),
        rules=anomaly_rules,
    )

    # Kill switch
    kill_raw = raw.get("kill_switch", {})
    if not isinstance(kill_raw, dict):
        kill_raw = {}
    kill_policies: list[KillPolicyConfig] = []
    policies_raw = kill_raw.get("policies", [])
    if isinstance(policies_raw, list):
        for praw in policies_raw:
            if not isinstance(praw, dict):
                continue
            kill_policies.append(
                KillPolicyConfig(
                    name=str(praw.get("name", "")),
                    metric=str(praw.get("metric", "")),
                    operator=str(praw.get("operator", ">")),
                    threshold=float(praw.get("threshold", 0)),
                    action=str(praw.get("action", "kill_agent")),
                    severity=str(praw.get("severity", "critical")),
                    message=str(praw.get("message", "")),
                )
            )
    kill_switch = KillSwitchConfig(
        enabled=bool(kill_raw.get("enabled", True)),
        policies=kill_policies,
        state_path=str(kill_raw.get("state_path", ".agent_monitor/kill_state.json")),
    )

    # Alerts
    alerts_raw = raw.get("alerts", {})
    if not isinstance(alerts_raw, dict):
        alerts_raw = {}
    alert_channels: list[AlertChannelConfig] = []
    channels_raw = alerts_raw.get("channels", [])
    if isinstance(channels_raw, list):
        for craw in channels_raw:
            if not isinstance(craw, dict):
                continue
            headers_raw = craw.get("headers", {})
            headers = (
                {str(k): str(v) for k, v in headers_raw.items()}
                if isinstance(headers_raw, dict)
                else {}
            )
            alert_channels.append(
                AlertChannelConfig(
                    type=str(craw.get("type", "")),
                    enabled=bool(craw.get("enabled", True)),
                    path=str(craw.get("path", "")),
                    url=str(craw.get("url", "")),
                    min_severity=str(craw.get("min_severity", "low")),
                    headers=headers,
                )
            )
    alerts = AlertConfig(channels=alert_channels)

    return MonitorConfig(
        version=version,
        metadata=metadata,
        variables=variables,
        agents=agents,
        storage=storage,
        metrics=metrics_config,
        baselines=baselines,
        anomaly_detection=anomaly_detection,
        kill_switch=kill_switch,
        alerts=alerts,
    )


def validate_config(config: MonitorConfig) -> list[str]:
    """Return list of validation errors (empty = valid)."""
    errors: list[str] = []

    # Version
    if config.version not in ("1.0",):
        errors.append(f"Unsupported config version: '{config.version}' (expected '1.0')")

    # Agents
    for name, agent in config.agents.items():
        for et in agent.event_types:
            if et not in VALID_EVENT_TYPES:
                errors.append(
                    f"agents.{name}: invalid event_type '{et}', "
                    f"expected one of {sorted(VALID_EVENT_TYPES)}"
                )

    # Storage
    if config.storage.retention_days < 1:
        errors.append("storage.retention_days must be >= 1")

    # Metrics
    if config.metrics.default_window_seconds < 1:
        errors.append("metrics.default_window_seconds must be >= 1")
    if config.metrics.max_window_seconds < config.metrics.default_window_seconds:
        errors.append("metrics.max_window_seconds must be >= default_window_seconds")

    # Baselines
    if config.baselines.min_samples < 1:
        errors.append("baselines.min_samples must be >= 1")

    # Anomaly rules
    seen_rule_names: set[str] = set()
    for i, rule in enumerate(config.anomaly_detection.rules):
        prefix = f"anomaly_detection.rules[{i}]"
        if not rule.name:
            errors.append(f"{prefix}: 'name' is required")
        elif rule.name in seen_rule_names:
            errors.append(f"{prefix}: duplicate rule name '{rule.name}'")
        else:
            seen_rule_names.add(rule.name)
        if not rule.metric:
            errors.append(f"{prefix} ({rule.name}): 'metric' is required")
        if rule.z_threshold <= 0:
            errors.append(f"{prefix} ({rule.name}): z_threshold must be > 0")
        if rule.severity not in VALID_SEVERITIES:
            errors.append(
                f"{prefix} ({rule.name}): invalid severity '{rule.severity}', "
                f"expected one of {sorted(VALID_SEVERITIES)}"
            )

    # Kill policies
    valid_operators = {">", "<", ">=", "<=", "=="}
    seen_policy_names: set[str] = set()
    for i, policy in enumerate(config.kill_switch.policies):
        prefix = f"kill_switch.policies[{i}]"
        if not policy.name:
            errors.append(f"{prefix}: 'name' is required")
        elif policy.name in seen_policy_names:
            errors.append(f"{prefix}: duplicate policy name '{policy.name}'")
        else:
            seen_policy_names.add(policy.name)
        if not policy.metric:
            errors.append(f"{prefix} ({policy.name}): 'metric' is required")
        if policy.operator not in valid_operators:
            errors.append(
                f"{prefix} ({policy.name}): invalid operator '{policy.operator}', "
                f"expected one of {sorted(valid_operators)}"
            )
        if policy.action not in VALID_KILL_ACTIONS:
            errors.append(
                f"{prefix} ({policy.name}): invalid action '{policy.action}', "
                f"expected one of {sorted(VALID_KILL_ACTIONS)}"
            )
        if policy.severity not in VALID_SEVERITIES:
            errors.append(
                f"{prefix} ({policy.name}): invalid severity '{policy.severity}', "
                f"expected one of {sorted(VALID_SEVERITIES)}"
            )

    # Alert channels
    for i, channel in enumerate(config.alerts.channels):
        prefix = f"alerts.channels[{i}]"
        if channel.type not in VALID_ALERT_CHANNELS:
            errors.append(
                f"{prefix}: invalid channel type '{channel.type}', "
                f"expected one of {sorted(VALID_ALERT_CHANNELS)}"
            )
        if channel.type == "file" and not channel.path:
            errors.append(f"{prefix}: file channel requires 'path'")
        if channel.type == "webhook" and not channel.url:
            errors.append(f"{prefix}: webhook channel requires 'url'")
        if channel.min_severity not in VALID_SEVERITIES:
            errors.append(
                f"{prefix}: invalid min_severity '{channel.min_severity}', "
                f"expected one of {sorted(VALID_SEVERITIES)}"
            )

    return errors
