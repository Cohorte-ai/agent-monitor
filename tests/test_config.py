"""Tests for YAML config loading and validation."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from theaios.agent_monitor.config import ConfigError, load_config, validate_config
from theaios.agent_monitor.types import (
    AlertChannelConfig,
    AlertConfig,
    AnomalyDetectionConfig,
    AnomalyRuleConfig,
    KillPolicyConfig,
    KillSwitchConfig,
    MonitorConfig,
)


@pytest.fixture()
def valid_yaml(tmp_path: Path) -> Path:
    """Write a valid monitor.yaml and return its path."""
    content = textwrap.dedent("""\
        version: "1.0"

        metadata:
          name: test-monitor
          description: A test config

        agents:
          test-agent:
            enabled: true
            event_types:
              - action
              - denial
              - error

        storage:
          path: ".agent_monitor/events.jsonl"
          retention_days: 90

        metrics:
          default_window_seconds: 300
          max_window_seconds: 3600

        baselines:
          enabled: true
          min_samples: 20
          metrics:
            - denial_rate
            - error_count
            - cost_per_minute
            - avg_latency_ms
          storage_path: ".agent_monitor/baselines.json"

        anomaly_detection:
          enabled: true
          rules:
            - name: high-denial-rate
              metric: denial_rate
              z_threshold: 3.0
              severity: high
              cooldown_seconds: 300

            - name: cost-spike
              metric: cost_per_minute
              z_threshold: 2.5
              severity: critical
              cooldown_seconds: 600

        kill_switch:
          enabled: true
          policies:
            - name: auto-kill-on-high-cost
              metric: cost_per_minute
              operator: ">"
              threshold: 1.0
              action: kill_agent
              severity: critical

        alerts:
          channels:
            - type: console
            - type: file
              path: ".agent_monitor/alerts.jsonl"
    """)
    p = tmp_path / "monitor.yaml"
    p.write_text(content)
    return p


class TestLoadConfig:
    def test_load_valid_yaml(self, valid_yaml: Path) -> None:
        config = load_config(str(valid_yaml))
        assert config.version == "1.0"
        assert "test-agent" in config.agents
        assert len(config.anomaly_detection.rules) == 2
        assert config.kill_switch is not None

    def test_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError):
            load_config("nonexistent.yaml")

    def test_invalid_yaml(self, tmp_path: Path) -> None:
        p = tmp_path / "bad.yaml"
        p.write_text("not a mapping")
        with pytest.raises(ConfigError, match="YAML mapping"):
            load_config(str(p))

    def test_env_var_interpolation(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MY_MONITOR_DIR", "/tmp/monitor-data")
        content = textwrap.dedent("""\
            version: "1.0"
            baselines:
              storage_path: "${MY_MONITOR_DIR}/baselines.json"
            alerts:
              channels:
                - type: console
        """)
        p = tmp_path / "env.yaml"
        p.write_text(content)
        config = load_config(str(p))
        assert config.baselines.storage_path == "/tmp/monitor-data/baselines.json"

    def test_metrics_loaded(self, valid_yaml: Path) -> None:
        config = load_config(str(valid_yaml))
        assert config.metrics.default_window_seconds == 300
        assert config.metrics.max_window_seconds == 3600

    def test_anomaly_rules_loaded(self, valid_yaml: Path) -> None:
        config = load_config(str(valid_yaml))
        assert config.anomaly_detection.rules[0].name == "high-denial-rate"
        assert config.anomaly_detection.rules[1].name == "cost-spike"

    def test_kill_switch_loaded(self, valid_yaml: Path) -> None:
        config = load_config(str(valid_yaml))
        assert config.kill_switch is not None
        assert len(config.kill_switch.policies) == 1
        assert config.kill_switch.policies[0].action == "kill_agent"

    def test_alerts_loaded(self, valid_yaml: Path) -> None:
        config = load_config(str(valid_yaml))
        channels = config.alerts.channels
        assert len(channels) == 2
        assert channels[0].type == "console"
        assert channels[1].type == "file"


class TestValidateConfig:
    def test_valid_config(self, valid_yaml: Path) -> None:
        config = load_config(str(valid_yaml))
        errors = validate_config(config)
        assert errors == []

    def test_invalid_version(self) -> None:
        config = MonitorConfig(version="2.0")
        errors = validate_config(config)
        assert any("version" in e.lower() for e in errors)

    def test_invalid_severity_in_anomaly_rule(self) -> None:
        config = MonitorConfig(
            version="1.0",
            anomaly_detection=AnomalyDetectionConfig(
                enabled=True,
                rules=[
                    AnomalyRuleConfig(
                        name="bad-rule",
                        metric="event_count",
                        z_threshold=3.0,
                        severity="ultra",
                        cooldown_seconds=300,
                    )
                ],
            ),
        )
        errors = validate_config(config)
        assert any("severity" in e.lower() for e in errors)

    def test_duplicate_anomaly_rule_names(self) -> None:
        config = MonitorConfig(
            version="1.0",
            anomaly_detection=AnomalyDetectionConfig(
                enabled=True,
                rules=[
                    AnomalyRuleConfig(
                        name="dup-rule",
                        metric="event_count",
                        z_threshold=3.0,
                        severity="high",
                        cooldown_seconds=300,
                    ),
                    AnomalyRuleConfig(
                        name="dup-rule",
                        metric="denial_rate",
                        z_threshold=3.0,
                        severity="high",
                        cooldown_seconds=300,
                    ),
                ],
            ),
        )
        errors = validate_config(config)
        assert any("duplicate" in e.lower() for e in errors)

    def test_invalid_kill_action(self) -> None:
        config = MonitorConfig(
            version="1.0",
            kill_switch=KillSwitchConfig(
                enabled=True,
                policies=[
                    KillPolicyConfig(
                        name="bad-policy",
                        metric="cost_per_minute",
                        operator=">",
                        threshold=1.0,
                        action="restart",
                        severity="critical",
                    )
                ],
            ),
        )
        errors = validate_config(config)
        assert any("action" in e.lower() for e in errors)

    def test_invalid_alert_channel(self) -> None:
        config = MonitorConfig(
            version="1.0",
            alerts=AlertConfig(
                channels=[
                    AlertChannelConfig(type="smoke_signal"),
                ],
            ),
        )
        errors = validate_config(config)
        assert any("channel" in e.lower() for e in errors)
