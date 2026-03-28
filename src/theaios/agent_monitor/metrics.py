"""In-memory rolling window metrics engine."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass

from theaios.agent_monitor.types import AgentEvent, MetricSnapshot


@dataclass
class _EventRecord:
    """Lightweight record of an ingested event for metric computation."""

    timestamp: float
    event_type: str
    cost_usd: float
    latency_ms: float


class MetricsEngine:
    """Rolling window metrics engine using in-memory deques.

    Tracks per-agent event streams and computes real-time metric
    snapshots over configurable time windows.
    """

    def __init__(
        self,
        default_window_seconds: int = 300,
        max_window_seconds: int = 3600,
    ) -> None:
        self._default_window = default_window_seconds
        self._max_window = max_window_seconds
        self._streams: dict[str, deque[_EventRecord]] = defaultdict(deque)

    def ingest(self, event: AgentEvent) -> None:
        """Ingest an agent event into the metrics stream."""
        record = _EventRecord(
            timestamp=event.timestamp,
            event_type=event.event_type,
            cost_usd=event.cost_usd or 0.0,
            latency_ms=event.latency_ms or 0.0,
        )
        self._streams[event.agent].append(record)

    def _prune(self, agent: str, cutoff: float) -> None:
        """Remove expired entries from an agent's stream."""
        stream = self._streams[agent]
        while stream and stream[0].timestamp < cutoff:
            stream.popleft()

    def get_metrics(
        self,
        agent: str,
        window: int | None = None,
    ) -> MetricSnapshot:
        """Compute a metric snapshot for a single agent.

        Parameters
        ----------
        agent : str
            The agent name.
        window : int, optional
            Window size in seconds. Defaults to the configured default.
        """
        now = time.time()
        window_seconds = min(window or self._default_window, self._max_window)
        cutoff = now - window_seconds

        self._prune(agent, cutoff)
        stream = self._streams.get(agent, deque())

        event_count = 0
        action_count = 0
        denial_count = 0
        approval_count = 0
        error_count = 0
        cost_total = 0.0
        latency_sum = 0.0
        latency_count = 0

        for record in stream:
            event_count += 1
            if record.event_type == "action":
                action_count += 1
            elif record.event_type == "denial":
                denial_count += 1
            elif record.event_type in ("approval_request", "approval_response"):
                approval_count += 1
            elif record.event_type == "error":
                error_count += 1

            cost_total += record.cost_usd
            if record.latency_ms > 0:
                latency_sum += record.latency_ms
                latency_count += 1

        # Compute rates
        total_decisions = action_count + denial_count
        denial_rate = (denial_count / total_decisions) if total_decisions > 0 else 0.0
        approval_rate = (approval_count / event_count) if event_count > 0 else 0.0

        # Cost per minute
        window_minutes = window_seconds / 60.0
        cost_per_minute = (cost_total / window_minutes) if window_minutes > 0 else 0.0

        # Average latency
        avg_latency_ms = (latency_sum / latency_count) if latency_count > 0 else 0.0

        return MetricSnapshot(
            agent=agent,
            window_seconds=window_seconds,
            timestamp=now,
            event_count=event_count,
            action_count=action_count,
            denial_count=denial_count,
            denial_rate=round(denial_rate, 4),
            approval_count=approval_count,
            approval_rate=round(approval_rate, 4),
            error_count=error_count,
            cost_total=round(cost_total, 6),
            cost_per_minute=round(cost_per_minute, 6),
            avg_latency_ms=round(avg_latency_ms, 2),
        )

    def get_all_metrics(
        self,
        window: int | None = None,
    ) -> list[MetricSnapshot]:
        """Compute metric snapshots for all tracked agents."""
        return [self.get_metrics(agent, window) for agent in sorted(self._streams)]

    def flush(self) -> None:
        """Clear all in-memory metric streams."""
        self._streams.clear()
