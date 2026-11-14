"""MonitorLogger with real LiteLLM calls (mock_response: offline, no key, no spend)."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Iterator
from typing import Any

import pytest

litellm = pytest.importorskip("litellm")

from theaios.agent_monitor import AgentKilled, Monitor  # noqa: E402
from theaios.agent_monitor.adapters.litellm_logger import MonitorLogger  # noqa: E402
from theaios.agent_monitor.types import MonitorConfig  # noqa: E402

MSG = [{"role": "user", "content": "hi"}]


@pytest.fixture
def logger(basic_config: MonitorConfig) -> Iterator[MonitorLogger]:
    litellm.logging_callback_manager._reset_all_callbacks()
    lg = MonitorLogger(Monitor(basic_config))
    litellm.callbacks = [lg]
    yield lg
    litellm.logging_callback_manager._reset_all_callbacks()


def _wait(monitor: Monitor, n: int) -> list[Any]:
    deadline = time.time() + 5  # LiteLLM runs sync success callbacks in a thread pool
    while time.time() < deadline:
        events = monitor.get_events()
        if len(events) >= n:
            return events
        time.sleep(0.02)
    return monitor.get_events()


def test_a_call_is_a_cost_event_for_the_agent_in_its_metadata(logger: MonitorLogger) -> None:
    litellm.completion(
        model="gpt-4o-mini",
        messages=MSG,
        mock_response="hello",
        metadata={"agent": "assistant", "session_id": "t1"},
        user="alice",
    )
    (event,) = _wait(logger._monitor, 1)
    assert event["event_type"] == "cost" and event["agent"] == "assistant"
    assert event["session_id"] == "t1" and event["user"] == "alice"
    assert event["data"]["model"] == "gpt-4o-mini"
    assert isinstance(event["cost_usd"], float) and event["cost_usd"] > 0


def test_a_call_without_an_agent_is_attributed_to_the_default(logger: MonitorLogger) -> None:
    litellm.completion(model="gpt-4o-mini", messages=MSG, mock_response="hello")
    (event,) = _wait(logger._monitor, 1)
    assert event["agent"] == "unknown" and event["session_id"] is None


def test_a_killed_agent_is_refused_before_an_async_call(logger: MonitorLogger) -> None:
    logger._monitor.kill_agent("assistant", "budget")
    with pytest.raises(AgentKilled):
        asyncio.run(
            litellm.acompletion(
                model="gpt-4o-mini",
                messages=MSG,
                mock_response="x",
                metadata={"agent": "assistant"},
            )
        )
    asyncio.run(
        litellm.acompletion(
            model="gpt-4o-mini", messages=MSG, mock_response="x", metadata={"agent": "other"}
        )
    )  # others still run


def test_guard_refuses_a_killed_session_for_sync_calls(logger: MonitorLogger) -> None:
    logger._monitor.kill_session("t9", "operator")
    completion = logger.guard(litellm.completion)
    with pytest.raises(AgentKilled):
        completion(
            model="gpt-4o-mini",
            messages=MSG,
            mock_response="x",
            metadata={"agent": "assistant", "session_id": "t9"},
        )
    assert (
        completion(
            model="gpt-4o-mini",
            messages=MSG,
            mock_response="ok",
            metadata={"agent": "assistant", "session_id": "t1"},
        )
        .choices[0]
        .message.content
        == "ok"
    )


def test_a_failed_call_is_an_error_event(logger: MonitorLogger) -> None:
    with pytest.raises(Exception):
        litellm.completion(
            model="gpt-4o-mini",
            messages=MSG,
            num_retries=0,
            mock_response=litellm.RateLimitError("slow down", "openai", "gpt-4o-mini"),
            metadata={"agent": "assistant"},
        )
    events = _wait(logger._monitor, 1)
    assert [e["event_type"] for e in events] == ["error"] and events[0]["agent"] == "assistant"
    assert events[0]["cost_usd"] is None and "slow down" in events[0]["data"]["error"]
