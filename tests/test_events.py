"""Tests for the EventStore."""

from __future__ import annotations

import time
from datetime import datetime, timezone

from theaios.agent_monitor.events import EventStore
from theaios.agent_monitor.types import AgentEvent


class TestEventStore:
    def test_write_and_read(self, tmp_dir) -> None:
        store = EventStore(path=str(tmp_dir / "events.jsonl"))
        event = AgentEvent(
            timestamp=time.time(),
            event_type="action",
            agent="test",
            data={"cost": 0.01},
        )
        store.write(event)
        events = store.read()
        assert len(events) == 1
        assert events[0]["agent"] == "test"

    def test_filter_by_agent(self, tmp_dir) -> None:
        store = EventStore(path=str(tmp_dir / "events.jsonl"))
        now = time.time()
        store.write(AgentEvent(timestamp=now, event_type="action", agent="alpha"))
        store.write(AgentEvent(timestamp=now, event_type="action", agent="beta"))
        store.write(AgentEvent(timestamp=now, event_type="action", agent="alpha"))
        events = store.read(agent="alpha")
        assert len(events) == 2
        assert all(e["agent"] == "alpha" for e in events)

    def test_filter_by_event_type(self, tmp_dir) -> None:
        store = EventStore(path=str(tmp_dir / "events.jsonl"))
        now = time.time()
        store.write(AgentEvent(timestamp=now, event_type="action", agent="test"))
        store.write(AgentEvent(timestamp=now, event_type="error", agent="test"))
        store.write(AgentEvent(timestamp=now, event_type="action", agent="test"))
        events = store.read(event_type="error")
        assert len(events) == 1
        assert events[0]["event_type"] == "error"

    def test_filter_by_since(self, tmp_dir) -> None:
        store = EventStore(path=str(tmp_dir / "events.jsonl"))
        now = time.time()
        store.write(AgentEvent(timestamp=now - 100, event_type="action", agent="test"))
        store.write(AgentEvent(timestamp=now - 50, event_type="action", agent="test"))
        store.write(AgentEvent(timestamp=now - 10, event_type="action", agent="test"))
        # since expects an ISO timestamp string
        since_ts = datetime.fromtimestamp(now - 60, tz=timezone.utc).isoformat()
        events = store.read(since=since_ts)
        assert len(events) == 2

    def test_tail(self, tmp_dir) -> None:
        store = EventStore(path=str(tmp_dir / "events.jsonl"))
        now = time.time()
        for i in range(10):
            store.write(
                AgentEvent(
                    timestamp=now + i,
                    event_type="action",
                    agent="test",
                    data={"i": i},
                )
            )
        events = store.tail(3)
        assert len(events) == 3
        assert events[-1]["data"]["i"] == 9

    def test_count(self, tmp_dir) -> None:
        store = EventStore(path=str(tmp_dir / "events.jsonl"))
        now = time.time()
        for i in range(5):
            store.write(AgentEvent(timestamp=now + i, event_type="action", agent="test"))
        assert store.count() == 5

    def test_prune_retention(self, tmp_dir) -> None:
        store = EventStore(path=str(tmp_dir / "events.jsonl"))
        now = time.time()
        # Event from 100 days ago
        store.write(
            AgentEvent(
                timestamp=now - 100 * 86400,
                event_type="action",
                agent="test",
            )
        )
        # Recent event
        store.write(AgentEvent(timestamp=now - 10, event_type="action", agent="test"))
        pruned = store.prune(retention_days=90)
        assert pruned == 1
        assert store.count() == 1

    def test_clear(self, tmp_dir) -> None:
        store = EventStore(path=str(tmp_dir / "events.jsonl"))
        now = time.time()
        for i in range(5):
            store.write(AgentEvent(timestamp=now + i, event_type="action", agent="test"))
        store.clear()
        assert store.count() == 0

    def test_empty_store(self, tmp_dir) -> None:
        store = EventStore(path=str(tmp_dir / "events.jsonl"))
        assert store.read() == []
        assert store.tail(10) == []
        assert store.count() == 0

    def test_combined_filters(self, tmp_dir) -> None:
        store = EventStore(path=str(tmp_dir / "events.jsonl"))
        now = time.time()
        store.write(
            AgentEvent(
                timestamp=now - 100,
                event_type="action",
                agent="alpha",
            )
        )
        store.write(
            AgentEvent(
                timestamp=now - 50,
                event_type="error",
                agent="alpha",
            )
        )
        store.write(
            AgentEvent(
                timestamp=now - 10,
                event_type="action",
                agent="beta",
            )
        )
        events = store.read(agent="alpha", event_type="action")
        assert len(events) == 1
