"""MonitorMiddleware on a real LangChain 1.x agent (fake model, offline)."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import pytest

pytest.importorskip("langchain.agents")

from langchain.agents import create_agent  # noqa: E402
from langchain.agents.middleware import AgentMiddleware  # noqa: E402
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel  # noqa: E402
from langchain_core.messages import AIMessage, ToolMessage  # noqa: E402
from langchain_core.tools import tool  # noqa: E402
from langgraph.checkpoint.memory import InMemorySaver  # noqa: E402
from langgraph.types import Command, interrupt  # noqa: E402

from theaios.agent_monitor import AgentKilled, Monitor  # noqa: E402
from theaios.agent_monitor.adapters.langchain_agent import MonitorMiddleware  # noqa: E402
from theaios.agent_monitor.types import MonitorConfig  # noqa: E402

RAN: list[str] = []


@tool
def read_docs() -> str:
    """Read docs."""
    RAN.append("read_docs")
    return "ok"


@tool
def send_email(to: str) -> str:
    """Send an email."""
    RAN.append("send_email")
    return "sent"


@tool
def flaky() -> str:
    """Fails."""
    raise ValueError("backend down")


class Model(GenericFakeChatModel):
    def bind_tools(self, tools: Any, **kw: Any) -> Model:
        return self


class DenySend(AgentMiddleware):  # stands in for agent-auth / guardrails
    def wrap_tool_call(self, request: Any, handler: Any) -> Any:
        if request.tool_call["name"] == "send_email":
            return ToolMessage(
                content="Not authorized",
                name="send_email",
                tool_call_id=request.tool_call["id"],
                status="error",
                artifact={
                    "theaios": {"component": "agent-auth", "codes": ["deny"], "reason": "no grant"}
                },
            )
        return handler(request)

    async def awrap_tool_call(self, request: Any, handler: Any) -> Any:
        if request.tool_call["name"] == "send_email":
            return self.wrap_tool_call(request, lambda r: None)
        return await handler(request)


class AskFirst(AgentMiddleware):
    def wrap_tool_call(self, request: Any, handler: Any) -> Any:
        decision = interrupt(
            {
                "type": "theaios.approval",
                "component": "guardrails",
                "proposal_id": "p1",
                "tier": "soft",
            }
        )
        return (
            handler(request)
            if decision.get("approve")
            else ToolMessage(
                content="rejected",
                name=request.tool_call["name"],
                tool_call_id=request.tool_call["id"],
                status="error",
                artifact={"theaios": {"component": "guardrails", "codes": ["rejected"]}},
            )
        )


@dataclass
class Ctx:
    user_id: str | None = None


def _call(name: str, cid: str, **args: Any) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": cid}])


CFG = {"configurable": {"thread_id": "t1"}}


@pytest.fixture(autouse=True)
def _reset() -> None:
    RAN.clear()


def _agent(monitor: Monitor, script: list[AIMessage], *inner: AgentMiddleware) -> Any:
    model = Model(messages=iter([*script, AIMessage(content="done")]))
    return create_agent(
        model,
        [read_docs, send_email, flaky],
        middleware=[MonitorMiddleware(monitor), *inner],
        context_schema=Ctx,
        checkpointer=InMemorySaver(),
        name="assistant",
    )


def _events(monitor: Monitor) -> list[tuple[str, str]]:
    return [(str(e["event_type"]), str(e["data"].get("tool"))) for e in monitor.get_events()]  # type: ignore[union-attr]


def test_every_outcome_is_recorded(basic_config: MonitorConfig) -> None:
    monitor = Monitor(basic_config)
    script = [_call("read_docs", "c1"), _call("send_email", "c2", to="x"), _call("flaky", "c3")]
    agent = _agent(monitor, script, DenySend())
    with pytest.raises(ValueError):
        agent.invoke({"messages": [("user", "x")]}, CFG, context=Ctx("alice"))
    assert _events(monitor) == [
        ("action", "read_docs"),
        ("denial", "send_email"),
        ("error", "flaky"),
    ]
    deny: Any = monitor.get_events()[1]
    assert deny["agent"] == "assistant" and deny["session_id"] == "t1" and deny["user"] == "alice"
    assert deny["data"]["component"] == "agent-auth" and deny["data"]["reason"] == "no grant"
    assert deny["latency_ms"] is not None


def test_a_killed_agent_is_stopped_before_its_next_model_call(basic_config: MonitorConfig) -> None:
    monitor = Monitor(basic_config)
    monitor.kill_agent("assistant", "runaway")
    agent = _agent(monitor, [_call("read_docs", "c1")])
    with pytest.raises(AgentKilled):
        agent.invoke({"messages": [("user", "x")]}, CFG)
    assert RAN == []


def test_a_killed_session_stops_tool_calls(basic_config: MonitorConfig) -> None:
    monitor = Monitor(basic_config)

    class KillAfterModel(AgentMiddleware):
        def after_model(self, state: Any, runtime: Any) -> None:
            monitor.kill_session("t1", "operator")
            return None

    agent = _agent(monitor, [_call("read_docs", "c1")], KillAfterModel())
    with pytest.raises(AgentKilled):
        agent.invoke({"messages": [("user", "x")]}, CFG)
    assert RAN == []


def test_a_pause_is_recorded_once_then_the_outcome(basic_config: MonitorConfig) -> None:
    monitor = Monitor(basic_config)
    agent = _agent(monitor, [_call("send_email", "c1", to="x")], AskFirst())
    out = agent.invoke({"messages": [("user", "x")]}, CFG, version="v2")
    assert out.interrupts and _events(monitor) == [("approval_request", "send_email")]
    first: Any = monitor.get_events()[0]
    assert first["data"]["proposal_id"] == "p1"
    agent.invoke(Command(resume={"approve": True}), CFG, version="v2")
    assert _events(monitor) == [("approval_request", "send_email"), ("action", "send_email")]


def test_the_async_path_records_too(basic_config: MonitorConfig) -> None:
    monitor = Monitor(basic_config)
    agent = _agent(
        monitor, [_call("read_docs", "c1"), _call("send_email", "c2", to="x")], DenySend()
    )
    asyncio.run(agent.ainvoke({"messages": [("user", "x")]}, CFG))
    assert _events(monitor) == [("action", "read_docs"), ("denial", "send_email")]
