"""JSONL event store — append-only storage for agent events."""

from __future__ import annotations

import json
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from theaios.agent_monitor.types import AgentEvent


class EventStore:
    """Append-only JSONL event store.

    Writes one JSON object per line. Every agent event is persisted,
    providing a complete audit trail for compliance and debugging.
    """

    def __init__(self, path: str = ".agent_monitor/events.jsonl") -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        return self._path

    def write(self, event: AgentEvent) -> None:
        """Append an agent event to the store."""
        entry = asdict(event)
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, default=str) + "\n")

    def read(
        self,
        *,
        since: str | None = None,
        until: str | None = None,
        agent: str | None = None,
        event_type: str | None = None,
        session_id: str | None = None,
        limit: int = 1000,
    ) -> list[dict[str, object]]:
        """Read events with optional filters.

        Parameters
        ----------
        since : str, optional
            ISO timestamp — only return events at or after this time.
        until : str, optional
            ISO timestamp — only return events before this time.
        agent : str, optional
            Filter by agent name.
        event_type : str, optional
            Filter by event type.
        session_id : str, optional
            Filter by session ID.
        limit : int
            Maximum number of entries to return.
        """
        if not self._path.exists():
            return []

        # Convert ISO timestamps to epoch for comparison
        since_ts: float | None = None
        until_ts: float | None = None
        if since:
            since_ts = datetime.fromisoformat(since).replace(tzinfo=timezone.utc).timestamp()
        if until:
            until_ts = datetime.fromisoformat(until).replace(tzinfo=timezone.utc).timestamp()

        entries: list[dict[str, object]] = []
        with open(self._path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                ts = entry.get("timestamp")
                if since_ts is not None and isinstance(ts, (int, float)) and ts < since_ts:
                    continue
                if until_ts is not None and isinstance(ts, (int, float)) and ts >= until_ts:
                    continue
                if agent and entry.get("agent") != agent:
                    continue
                if event_type and entry.get("event_type") != event_type:
                    continue
                if session_id and entry.get("session_id") != session_id:
                    continue

                entries.append(entry)
                if len(entries) >= limit:
                    break

        return entries

    def tail(self, n: int = 20) -> list[dict[str, object]]:
        """Return the last *n* events from the store."""
        if not self._path.exists():
            return []

        # Read all lines and take the last n — simple and correct for JSONL
        lines: list[str] = []
        with open(self._path, encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped:
                    lines.append(stripped)

        entries: list[dict[str, object]] = []
        for line in lines[-n:]:
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return entries

    def count(self) -> int:
        """Return the total number of events in the store."""
        if not self._path.exists():
            return 0

        count = 0
        with open(self._path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    count += 1
        return count

    def prune(self, retention_days: int = 90) -> int:
        """Remove events older than *retention_days*. Returns count of pruned events."""
        if not self._path.exists():
            return 0

        cutoff = time.time() - (retention_days * 86400)
        kept: list[str] = []
        pruned = 0

        with open(self._path, encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    entry = json.loads(stripped)
                except json.JSONDecodeError:
                    continue

                ts = entry.get("timestamp")
                if isinstance(ts, (int, float)) and ts < cutoff:
                    pruned += 1
                else:
                    kept.append(stripped)

        with open(self._path, "w", encoding="utf-8") as f:
            for line in kept:
                f.write(line + "\n")

        return pruned

    def clear(self) -> None:
        """Clear all events from the store."""
        if self._path.exists():
            self._path.unlink()
