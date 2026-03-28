"""Compliance exporter — generates structured compliance reports."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from theaios.agent_monitor.events import EventStore


class ComplianceExporter:
    """Generates structured compliance reports from the event store.

    Supports SOC2, GDPR, and raw JSON export formats.
    """

    def __init__(self, event_store: EventStore) -> None:
        self._store = event_store

    def export(
        self,
        format: str = "json",
        since: str | None = None,
        until: str | None = None,
        agent: str | None = None,
    ) -> str:
        """Export a compliance report as a JSON string.

        Parameters
        ----------
        format : str
            One of "soc2", "gdpr", or "json".
        since : str, optional
            ISO timestamp — include events at or after this time.
        until : str, optional
            ISO timestamp — include events before this time.
        agent : str, optional
            Filter by agent name.

        Returns
        -------
        str
            JSON-formatted compliance report.
        """
        events = self._store.read(since=since, until=until, agent=agent, limit=100_000)

        if format == "soc2":
            return self._export_soc2(events, since, until, agent)
        elif format == "gdpr":
            return self._export_gdpr(events, since, until, agent)
        else:
            return self._export_json(events, since, until, agent)

    def _export_json(
        self,
        events: list[dict[str, object]],
        since: str | None,
        until: str | None,
        agent: str | None,
    ) -> str:
        """Raw JSON export of all events."""
        report: dict[str, object] = {
            "format": "json",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "filters": {
                "since": since,
                "until": until,
                "agent": agent,
            },
            "total_events": len(events),
            "events": events,
        }
        return json.dumps(report, indent=2, default=str)

    def _export_soc2(
        self,
        events: list[dict[str, object]],
        since: str | None,
        until: str | None,
        agent: str | None,
    ) -> str:
        """SOC2-oriented compliance report.

        Focuses on access controls, denials, approvals, and error rates.
        """
        # Aggregate statistics
        total = len(events)
        actions = [e for e in events if e.get("event_type") == "action"]
        denials = [e for e in events if e.get("event_type") == "denial"]
        approvals = [
            e for e in events if e.get("event_type") in ("approval_request", "approval_response")
        ]
        errors = [e for e in events if e.get("event_type") == "error"]
        guardrail_triggers = [e for e in events if e.get("event_type") == "guardrail_trigger"]

        # Unique agents and sessions
        agents_seen = {str(e.get("agent", "")) for e in events if e.get("agent")}
        sessions_seen = {str(e.get("session_id", "")) for e in events if e.get("session_id")}

        report: dict[str, object] = {
            "format": "soc2",
            "report_title": "SOC2 AI Agent Compliance Report",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "period": {
                "since": since or "beginning",
                "until": until or datetime.now(timezone.utc).isoformat(),
            },
            "filters": {"agent": agent},
            "summary": {
                "total_events": total,
                "total_actions": len(actions),
                "total_denials": len(denials),
                "total_approvals": len(approvals),
                "total_errors": len(errors),
                "total_guardrail_triggers": len(guardrail_triggers),
                "denial_rate": round(len(denials) / total, 4) if total > 0 else 0.0,
                "error_rate": round(len(errors) / total, 4) if total > 0 else 0.0,
                "unique_agents": len(agents_seen),
                "unique_sessions": len(sessions_seen),
            },
            "access_controls": {
                "agents_observed": sorted(agents_seen),
                "denial_events": denials[:100],
                "approval_events": approvals[:100],
            },
            "availability": {
                "error_events": errors[:100],
            },
            "guardrail_enforcement": {
                "trigger_events": guardrail_triggers[:100],
            },
        }
        return json.dumps(report, indent=2, default=str)

    def _export_gdpr(
        self,
        events: list[dict[str, object]],
        since: str | None,
        until: str | None,
        agent: str | None,
    ) -> str:
        """GDPR-oriented compliance report.

        Focuses on data processing activities, user tracking, and
        data subject access rights.
        """
        total = len(events)

        # Track unique users
        users_seen = {str(e.get("user", "")) for e in events if e.get("user")}

        # Per-user event counts
        user_event_counts: dict[str, int] = {}
        for event in events:
            user = str(event.get("user", ""))
            if user:
                user_event_counts[user] = user_event_counts.get(user, 0) + 1

        # Cost tracking (relevant for data processing records)
        costs = [float(str(e.get("cost_usd", 0))) for e in events if e.get("cost_usd")]
        total_cost = sum(costs)

        report: dict[str, object] = {
            "format": "gdpr",
            "report_title": "GDPR AI Agent Data Processing Report",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "period": {
                "since": since or "beginning",
                "until": until or datetime.now(timezone.utc).isoformat(),
            },
            "filters": {"agent": agent},
            "summary": {
                "total_processing_events": total,
                "unique_data_subjects": len(users_seen),
                "total_processing_cost_usd": round(total_cost, 6),
            },
            "data_subjects": {
                "users_observed": sorted(users_seen),
                "events_per_user": user_event_counts,
            },
            "processing_activities": {
                "event_type_counts": self._count_by_field(events, "event_type"),
                "agent_counts": self._count_by_field(events, "agent"),
            },
            "data_retention": {
                "oldest_event_timestamp": (events[0].get("timestamp") if events else None),
                "newest_event_timestamp": (events[-1].get("timestamp") if events else None),
            },
        }
        return json.dumps(report, indent=2, default=str)

    @staticmethod
    def _count_by_field(
        events: list[dict[str, object]],
        field: str,
    ) -> dict[str, int]:
        """Count events grouped by a field value."""
        counts: dict[str, int] = {}
        for event in events:
            key = str(event.get(field, "unknown"))
            counts[key] = counts.get(key, 0) + 1
        return counts
