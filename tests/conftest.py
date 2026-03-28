"""Shared fixtures for Agent Monitor tests."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from theaios.agent_monitor.types import (
    AgentEvent,
    AlertChannelConfig,
    AlertConfig,
    MonitorConfig,
    StorageConfig,
)


@pytest.fixture()
def tmp_dir(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture()
def basic_config(tmp_path: Path) -> MonitorConfig:
    """A minimal valid config for testing."""
    return MonitorConfig(
        version="1.0",
        alerts=AlertConfig(
            channels=[AlertChannelConfig(type="console")],
        ),
        storage=StorageConfig(path=str(tmp_path / "events.jsonl")),
    )


@pytest.fixture()
def sample_event() -> AgentEvent:
    """A simple agent event."""
    return AgentEvent(
        timestamp=time.time(),
        event_type="action",
        agent="test-agent",
        data={
            "model": "gpt-4",
            "prompt_tokens": 100,
            "completion_tokens": 50,
        },
        latency_ms=350.0,
        cost_usd=0.005,
    )


@pytest.fixture()
def sample_events() -> list[AgentEvent]:
    """A diverse list of events for testing."""
    now = time.time()
    return [
        AgentEvent(
            event_type="action",
            agent="agent-alpha",
            timestamp=now - 200,
            data={
                "model": "gpt-4",
                "prompt_tokens": 100,
                "completion_tokens": 50,
            },
            latency_ms=350.0,
            cost_usd=0.005,
        ),
        AgentEvent(
            event_type="guardrail_trigger",
            agent="agent-alpha",
            timestamp=now - 150,
            data={
                "rule": "block-injection",
                "outcome": "deny",
                "severity": "critical",
            },
        ),
        AgentEvent(
            event_type="action",
            agent="agent-beta",
            timestamp=now - 100,
            data={
                "tool": "search_api",
                "success": True,
            },
            latency_ms=120.0,
        ),
        AgentEvent(
            event_type="guardrail_trigger",
            agent="agent-alpha",
            timestamp=now - 50,
            data={
                "rule": "redact-pii",
                "outcome": "allow",
                "severity": "low",
            },
        ),
        AgentEvent(
            event_type="error",
            agent="agent-beta",
            timestamp=now - 10,
            data={
                "error_type": "TimeoutError",
                "message": "LLM call timed out after 30s",
            },
        ),
        AgentEvent(
            event_type="action",
            agent="agent-alpha",
            timestamp=now - 5,
            data={
                "model": "gpt-4",
                "prompt_tokens": 200,
                "completion_tokens": 80,
            },
            latency_ms=500.0,
            cost_usd=0.008,
        ),
    ]
