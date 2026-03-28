"""Tests for the ComplianceExporter."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from theaios.agent_monitor.compliance import ComplianceExporter
from theaios.agent_monitor.events import EventStore
from theaios.agent_monitor.types import AgentEvent


@pytest.fixture()
def populated_store(tmp_dir: Path) -> EventStore:
    """Create a store with diverse events."""
    store = EventStore(path=str(tmp_dir / "events.jsonl"))
    now = time.time()
    store.write(
        AgentEvent(
            timestamp=now - 200,
            event_type="action",
            agent="alpha",
            data={"model": "gpt-4"},
            cost_usd=0.01,
        )
    )
    store.write(
        AgentEvent(
            timestamp=now - 100,
            event_type="denial",
            agent="alpha",
            data={"rule": "block-injection", "outcome": "deny"},
        )
    )
    store.write(
        AgentEvent(
            timestamp=now - 50,
            event_type="action",
            agent="beta",
            data={"model": "gpt-4"},
            cost_usd=0.02,
        )
    )
    store.write(
        AgentEvent(
            timestamp=now - 10,
            event_type="error",
            agent="alpha",
            data={"error_type": "Timeout"},
        )
    )
    return store


class TestComplianceExporter:
    def test_export_soc2_format(self, populated_store: EventStore) -> None:
        exporter = ComplianceExporter(event_store=populated_store)
        report_str = exporter.export(format="soc2")
        report = json.loads(report_str)
        assert report["format"] == "soc2"
        assert "summary" in report
        assert report["summary"]["total_events"] == 4

    def test_export_gdpr_format(self, populated_store: EventStore) -> None:
        exporter = ComplianceExporter(event_store=populated_store)
        report_str = exporter.export(format="gdpr")
        report = json.loads(report_str)
        assert report["format"] == "gdpr"
        assert "data_subjects" in report

    def test_export_json_format(self, populated_store: EventStore) -> None:
        exporter = ComplianceExporter(event_store=populated_store)
        report_str = exporter.export(format="json")
        report = json.loads(report_str)
        assert report["format"] == "json"
        assert report["total_events"] == 4

    def test_filter_by_since(self, populated_store: EventStore) -> None:
        exporter = ComplianceExporter(event_store=populated_store)
        now = time.time()
        since_iso = datetime.fromtimestamp(now - 60, tz=timezone.utc).isoformat()
        report_str = exporter.export(format="json", since=since_iso)
        report = json.loads(report_str)
        # Only events within last 60s should be included
        assert report["total_events"] < 4

    def test_filter_by_until(self, populated_store: EventStore) -> None:
        exporter = ComplianceExporter(event_store=populated_store)
        now = time.time()
        until_iso = datetime.fromtimestamp(now - 150, tz=timezone.utc).isoformat()
        report_str = exporter.export(format="json", until=until_iso)
        report = json.loads(report_str)
        # Only events before now-150 should be included
        assert report["total_events"] < 4

    def test_filter_by_agent(self, populated_store: EventStore) -> None:
        exporter = ComplianceExporter(event_store=populated_store)
        report_str = exporter.export(format="json", agent="alpha")
        report = json.loads(report_str)
        for event in report["events"]:
            assert event["agent"] == "alpha"

    def test_empty_store_export(self, tmp_dir: Path) -> None:
        store = EventStore(path=str(tmp_dir / "empty.jsonl"))
        exporter = ComplianceExporter(event_store=store)
        report_str = exporter.export(format="json")
        report = json.loads(report_str)
        assert report["total_events"] == 0
        assert report["events"] == []

    def test_soc2_includes_control_fields(self, populated_store: EventStore) -> None:
        exporter = ComplianceExporter(event_store=populated_store)
        report_str = exporter.export(format="soc2")
        report = json.loads(report_str)
        # SOC 2 reports should include control-relevant fields
        assert "generated_at" in report
        assert "summary" in report
