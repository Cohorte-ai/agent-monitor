"""Statistical baseline tracker using Welford's online algorithm."""

from __future__ import annotations

import json
import math
import time
from dataclasses import asdict
from pathlib import Path

from theaios.agent_monitor.types import Baseline


class BaselineTracker:
    """Incremental mean/stddev tracker using Welford's online algorithm.

    Maintains per-agent, per-metric baselines that update incrementally
    without storing the full history. Supports persistence to JSON.
    """

    def __init__(
        self,
        storage_path: str = ".agent_monitor/baselines.json",
        min_samples: int = 30,
    ) -> None:
        self._storage_path = Path(storage_path)
        self._min_samples = min_samples
        # Internal state: (agent, metric) -> (count, mean, M2)
        self._state: dict[tuple[str, str], tuple[int, float, float]] = {}
        # Cached Baseline objects
        self._baselines: dict[tuple[str, str], Baseline] = {}

    def update(self, agent: str, metric: str, value: float) -> None:
        """Update the baseline for a given agent and metric with a new value.

        Uses Welford's online algorithm for numerically stable incremental
        computation of mean and variance.
        """
        key = (agent, metric)
        count, mean, m2 = self._state.get(key, (0, 0.0, 0.0))

        count += 1
        delta = value - mean
        mean += delta / count
        delta2 = value - mean
        m2 += delta * delta2

        self._state[key] = (count, mean, m2)

        # Update cached baseline
        stddev = math.sqrt(m2 / count) if count > 1 else 0.0
        self._baselines[key] = Baseline(
            agent=agent,
            metric=metric,
            mean=round(mean, 6),
            stddev=round(stddev, 6),
            sample_count=count,
            last_updated=time.time(),
        )

    def get_baseline(self, agent: str, metric: str) -> Baseline | None:
        """Return the current baseline for an agent/metric pair, or None."""
        return self._baselines.get((agent, metric))

    def z_score(self, agent: str, metric: str, value: float) -> float | None:
        """Compute the z-score for a value against the baseline.

        Returns None if the baseline has fewer than min_samples data points
        or if stddev is zero (all identical values).
        """
        baseline = self._baselines.get((agent, metric))
        if baseline is None:
            return None
        if baseline.sample_count < self._min_samples:
            return None
        if baseline.stddev == 0:
            return None
        return (value - baseline.mean) / baseline.stddev

    def save(self) -> None:
        """Persist baselines and internal state to disk."""
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)

        data: dict[str, object] = {
            "baselines": {f"{k[0]}:{k[1]}": asdict(v) for k, v in self._baselines.items()},
            "state": {
                f"{k[0]}:{k[1]}": {"count": v[0], "mean": v[1], "m2": v[2]}
                for k, v in self._state.items()
            },
        }

        with open(self._storage_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

    def load(self) -> None:
        """Load baselines and internal state from disk."""
        if not self._storage_path.exists():
            return

        with open(self._storage_path, encoding="utf-8") as f:
            data = json.load(f)

        # Restore baselines
        baselines_raw = data.get("baselines", {})
        if isinstance(baselines_raw, dict):
            for key_str, braw in baselines_raw.items():
                if not isinstance(braw, dict):
                    continue
                parts = key_str.split(":", 1)
                if len(parts) != 2:
                    continue
                agent, metric = parts
                self._baselines[(agent, metric)] = Baseline(
                    agent=agent,
                    metric=metric,
                    mean=float(braw.get("mean", 0)),
                    stddev=float(braw.get("stddev", 0)),
                    sample_count=int(braw.get("sample_count", 0)),
                    last_updated=float(braw.get("last_updated", 0)),
                )

        # Restore internal state
        state_raw = data.get("state", {})
        if isinstance(state_raw, dict):
            for key_str, sraw in state_raw.items():
                if not isinstance(sraw, dict):
                    continue
                parts = key_str.split(":", 1)
                if len(parts) != 2:
                    continue
                agent, metric = parts
                self._state[(agent, metric)] = (
                    int(sraw.get("count", 0)),
                    float(sraw.get("mean", 0)),
                    float(sraw.get("m2", 0)),
                )
