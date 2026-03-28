"""Anomaly detector — evaluates anomaly rules against baselines."""

from __future__ import annotations

import time
from datetime import datetime, timezone

from theaios.agent_monitor.baselines import BaselineTracker
from theaios.agent_monitor.expressions import compile_expression, evaluate
from theaios.agent_monitor.types import (
    AnomalyAlert,
    AnomalyDetectionConfig,
    AnomalyRuleConfig,
    MetricSnapshot,
)


class AnomalyDetector:
    """Evaluates anomaly rules against statistical baselines.

    For each configured rule, computes the z-score of the current metric
    value and fires an alert if it exceeds the threshold. Supports
    cooldown to suppress duplicate alerts within a time window, and
    optional condition expressions evaluated against a time context.
    """

    def __init__(
        self,
        config: AnomalyDetectionConfig,
        baselines: BaselineTracker,
    ) -> None:
        self._config = config
        self._baselines = baselines
        # Pre-compile condition expressions
        self._compiled_conditions: dict[str, object] = {}
        for rule in config.rules:
            if rule.condition:
                self._compiled_conditions[rule.name] = compile_expression(rule.condition)
        # Cooldown tracking: (agent, rule_name) -> last_alert_timestamp
        self._last_alerts: dict[tuple[str, str], float] = {}

    def _build_time_context(self) -> dict[str, object]:
        """Build a time context dict for condition expression evaluation."""
        now = datetime.now(timezone.utc)
        return {
            "hour": now.hour,
            "minute": now.minute,
            "day_of_week": now.weekday(),  # 0=Monday, 6=Sunday
        }

    def _is_in_cooldown(self, agent: str, rule: AnomalyRuleConfig) -> bool:
        """Check if an alert for this agent/rule is still in cooldown."""
        key = (agent, rule.name)
        last_alert = self._last_alerts.get(key)
        if last_alert is None:
            return False
        return (time.time() - last_alert) < rule.cooldown_seconds

    def _get_metric_value(self, metrics: MetricSnapshot, metric_name: str) -> float | None:
        """Extract a metric value from a snapshot by name."""
        if hasattr(metrics, metric_name):
            val = getattr(metrics, metric_name)
            if isinstance(val, (int, float)):
                return float(val)
        return None

    def check(self, agent: str, metrics: MetricSnapshot) -> list[AnomalyAlert]:
        """Check all anomaly rules for a given agent and return any alerts.

        Parameters
        ----------
        agent : str
            The agent name to check.
        metrics : MetricSnapshot
            Current metric snapshot for the agent.

        Returns
        -------
        list[AnomalyAlert]
            List of anomaly alerts triggered. Empty if no anomalies detected.
        """
        if not self._config.enabled:
            return []

        alerts: list[AnomalyAlert] = []
        now = time.time()
        time_context = self._build_time_context()

        for rule in self._config.rules:
            # Check cooldown
            if self._is_in_cooldown(agent, rule):
                continue

            # Evaluate optional condition expression
            if rule.name in self._compiled_conditions:
                condition_ast = self._compiled_conditions[rule.name]
                result = evaluate(condition_ast, context=time_context)  # type: ignore[arg-type]
                if not result:
                    continue

            # Get metric value from snapshot
            value = self._get_metric_value(metrics, rule.metric)
            if value is None:
                continue

            # Compute z-score
            z = self._baselines.z_score(agent, rule.metric, value)
            if z is None:
                continue

            # Check threshold
            if abs(z) >= rule.z_threshold:
                alert = AnomalyAlert(
                    agent=agent,
                    rule=rule.name,
                    metric=rule.metric,
                    value=value,
                    z_score=round(z, 3),
                    threshold=rule.z_threshold,
                    severity=rule.severity,
                    message=(
                        f"Anomaly detected: {rule.metric}={value:.4f} "
                        f"(z={z:.2f}, threshold={rule.z_threshold})"
                    ),
                    timestamp=now,
                )
                alerts.append(alert)
                # Record alert time for cooldown
                self._last_alerts[(agent, rule.name)] = now

        return alerts
