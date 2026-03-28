"""JSON export utilities for agent monitor data."""

from __future__ import annotations

import json
from dataclasses import asdict

from theaios.agent_monitor.types import KillState, MetricSnapshot


def export_json(
    snapshots: list[MetricSnapshot],
    kill_state: KillState | None = None,
) -> str:
    """Export metrics and kill state as a JSON string.

    Parameters
    ----------
    snapshots : list[MetricSnapshot]
        Metric snapshots to export.
    kill_state : KillState, optional
        Current kill switch state.

    Returns
    -------
    str
        Pretty-printed JSON string.
    """
    data: dict[str, object] = {
        "metrics": [asdict(s) for s in snapshots],
    }

    if kill_state is not None:
        data["kill_state"] = {
            "killed_agents": sorted(kill_state.killed_agents),
            "killed_sessions": sorted(kill_state.killed_sessions),
            "global_kill": kill_state.global_kill,
            "reasons": kill_state.reasons,
        }

    return json.dumps(data, indent=2, default=str)
