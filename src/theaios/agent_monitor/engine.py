"""Monitor engine — the main orchestrator for agent observability."""

from __future__ import annotations

import dataclasses
import warnings
from typing import Protocol

from theaios.agent_monitor.alerts import AlertDispatcher
from theaios.agent_monitor.anomaly import AnomalyDetector
from theaios.agent_monitor.baselines import BaselineTracker
from theaios.agent_monitor.compliance import ComplianceExporter
from theaios.agent_monitor.events import EventStore
from theaios.agent_monitor.kill_switch import KillSwitch
from theaios.agent_monitor.metrics import MetricsEngine
from theaios.agent_monitor.types import (
    AgentEvent,
    AnomalyAlert,
    MetricSnapshot,
    MonitorConfig,
)


# Tag on events recorded while their agent or session was killed.
AFTER_KILL = "after_kill"


class EventExporter(Protocol):
    """Anything with ``export_event(event)``, e.g. :class:`~theaios.agent_monitor.adapters.otel.OTelExporter`."""

    def export_event(self, event: AgentEvent) -> None: ...


class Monitor:
    """Governance-first observability engine for AI agents.

    Orchestrates the full monitoring pipeline: event storage, metrics
    computation, baseline tracking, anomaly detection, kill switch
    evaluation, and alert dispatching.

    The ``record()`` method is the hot path — every agent event flows
    through it:

    1. Check kill switch (reject if killed)
    2. Filter by agent track config
    3. Append to EventStore
    4. Ingest into MetricsEngine
    5. Update baselines
    6. Check anomalies
    7. Evaluate kill policies
    8. Dispatch alerts
    """

    def __init__(self, config: MonitorConfig) -> None:
        self._config = config

        # Core components
        self._event_store = EventStore(path=config.storage.path)
        self._metrics = MetricsEngine(
            default_window_seconds=config.metrics.default_window_seconds,
            max_window_seconds=config.metrics.max_window_seconds,
        )
        self._baselines = BaselineTracker(
            storage_path=config.baselines.storage_path,
            min_samples=config.baselines.min_samples,
        )
        self._anomaly = AnomalyDetector(
            config=config.anomaly_detection,
            baselines=self._baselines,
        )
        self._kill_switch = KillSwitch(config=config.kill_switch)
        self._alerts = AlertDispatcher(config=config.alerts)
        self._compliance = ComplianceExporter(event_store=self._event_store)
        self._exporters: list[EventExporter] = []

    def add_exporter(self, exporter: EventExporter) -> None:
        """Send every recorded event to ``exporter.export_event(event)`` too, after it is
        stored. An exporter that fails never stops recording (it warns)."""
        if not callable(getattr(exporter, "export_event", None)):
            raise TypeError("an exporter needs an export_event(event) method")
        self._exporters.append(exporter)

    @property
    def event_store(self) -> EventStore:
        return self._event_store

    @property
    def metrics_engine(self) -> MetricsEngine:
        return self._metrics

    @property
    def baseline_tracker(self) -> BaselineTracker:
        return self._baselines

    @property
    def kill_switch_engine(self) -> KillSwitch:
        return self._kill_switch

    @property
    def compliance_exporter(self) -> ComplianceExporter:
        return self._compliance

    def record(self, event: AgentEvent) -> None:
        """Record an agent event through the full monitoring pipeline.

        This is the hot path. Every event flows through:
        kill check -> filter -> store -> metrics -> baselines -> anomaly -> kill policies -> alerts.
        """
        # 1. Kill switch: what a killed agent still did (an action already running, spend
        # through an unguarded call) is stored and exported, tagged, but feeds no metrics,
        # baselines, anomaly detection or kill policies.
        killed = self._kill_switch.is_killed(event.agent, event.session_id)
        if killed and AFTER_KILL not in event.tags:
            event = dataclasses.replace(event, tags=[*event.tags, AFTER_KILL])

        # 2. Filter by agent track config
        if not self._should_track(event):
            return

        # 3. Append to EventStore, then hand to exporters (never fatal)
        self._store_and_export(event)
        if killed:
            return

        # 4. Ingest into MetricsEngine
        self._metrics.ingest(event)

        # 5. Update baselines for tracked metrics
        if self._config.baselines.enabled:
            snapshot = self._metrics.get_metrics(event.agent)
            for metric_name in self._config.baselines.metrics:
                if hasattr(snapshot, metric_name):
                    val = getattr(snapshot, metric_name)
                    if isinstance(val, (int, float)):
                        self._baselines.update(event.agent, metric_name, float(val))

        # 6. Check anomalies
        anomaly_alerts: list[AnomalyAlert] = []
        if self._config.anomaly_detection.enabled:
            snapshot = self._metrics.get_metrics(event.agent)
            anomaly_alerts = self._anomaly.check(event.agent, snapshot)

        # 7. Evaluate kill policies
        triggered_policies: list[str] = []
        if self._config.kill_switch.enabled:
            snapshot = self._metrics.get_metrics(event.agent)
            triggered_policies = self._kill_switch.evaluate_policies(event.agent, snapshot)

        # 8. Dispatch alerts
        for alert in anomaly_alerts:
            self._alerts.dispatch(alert)

        for policy_name in triggered_policies:
            reason = f"Kill policy '{policy_name}' triggered for agent '{event.agent}'"
            self._alerts.dispatch_kill(event.agent, reason)

    def _store_and_export(self, event: AgentEvent) -> None:
        self._event_store.write(event)
        for exporter in self._exporters:
            try:
                exporter.export_event(event)
            except Exception as exc:  # noqa: BLE001 - an exporter must not break recording
                warnings.warn(
                    f"agent-monitor exporter {type(exporter).__name__} failed: {exc}",
                    RuntimeWarning,
                    stacklevel=2,
                )

    def _should_track(self, event: AgentEvent) -> bool:
        """Check if an event should be tracked based on agent config."""
        # If no agents are configured, track everything
        if not self._config.agents:
            return True

        agent_config = self._config.agents.get(event.agent)
        if agent_config is None:
            # Agent not in config — track by default (permissive)
            return True

        if not agent_config.enabled:
            return False

        # If event_types filter is set, only track matching types
        if agent_config.event_types and event.event_type not in agent_config.event_types:
            return False

        return True

    def is_killed(self, agent: str, session_id: str | None = None) -> bool:
        """Check if an agent or session is killed."""
        return self._kill_switch.is_killed(agent, session_id)

    def kill_agent(self, agent: str, reason: str = "") -> None:
        """Kill a specific agent."""
        self._kill_switch.kill_agent(agent, reason)
        if reason:
            self._alerts.dispatch_kill(agent, reason)

    def kill_session(self, session_id: str, reason: str = "") -> None:
        """Kill a specific session."""
        self._kill_switch.kill_session(session_id, reason)

    def kill_global(self, reason: str = "") -> None:
        """Activate global kill — stops all agents."""
        self._kill_switch.kill_global(reason)
        if reason:
            self._alerts.dispatch_kill("*", reason, severity="critical")

    def revive(self, agent: str | None = None, session_id: str | None = None) -> None:
        """Revive a specific agent or session."""
        self._kill_switch.revive(agent, session_id)

    def revive_global(self) -> None:
        """Deactivate global kill switch."""
        self._kill_switch.revive_global()

    def get_metrics(self, agent: str, window: int | None = None) -> MetricSnapshot:
        """Get current metrics for a specific agent."""
        return self._metrics.get_metrics(agent, window)

    def get_all_metrics(self, window: int | None = None) -> list[MetricSnapshot]:
        """Get current metrics for all tracked agents."""
        return self._metrics.get_all_metrics(window)

    def get_events(
        self,
        *,
        since: str | None = None,
        until: str | None = None,
        agent: str | None = None,
        event_type: str | None = None,
        limit: int = 1000,
    ) -> list[dict[str, object]]:
        """Query stored events with optional filters."""
        return self._event_store.read(
            since=since,
            until=until,
            agent=agent,
            event_type=event_type,
            limit=limit,
        )

    def flush(self) -> None:
        """Flush all in-memory state (metrics streams). Persisted data is not affected."""
        self._metrics.flush()
