"""Monitoring for LangChain 1.x agents (``create_agent``) and Deep Agents, as middleware.

Requires ``langchain>=1.0`` and ``langgraph>=1.0``: ``pip install "theaios-agent-monitor[langchain-agent]"``.

Put it first in the middleware list (the outermost), so it sees every outcome of the
middlewares inside it:

- **kill switch**: before every model call and every tool call, a killed agent or session
  stops the run (:class:`AgentKilled` is raised);
- every tool call becomes an event: ``action`` (ran), ``denial`` (refused by an inner
  middleware such as agent-auth or guardrails, with its decision), ``error`` (the tool failed
  or raised), and ``approval_request`` when the run pauses for a person.

Agent = ``agent=`` or the graph's name; session = the LangGraph ``thread_id``; user =
``user=`` or ``runtime.context.user_id``.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from theaios.agent_monitor.engine import Monitor
from theaios.agent_monitor.kill_switch import AgentKilled
from theaios.agent_monitor.types import AgentEvent

try:
    from langchain.agents.middleware import AgentMiddleware, ToolCallRequest
    from langchain_core.messages import ToolMessage
    from langgraph.errors import GraphBubbleUp, GraphInterrupt
    from langgraph.types import Command
except ImportError as e:  # pragma: no cover - exercised only without the extra
    raise ImportError(
        "The LangChain agent middleware needs langchain>=1.0 and langgraph>=1.0. "
        'Install with: pip install "theaios-agent-monitor[langchain-agent]"'
    ) from e

Handler = Callable[[ToolCallRequest], "ToolMessage | Command[Any]"]
AsyncHandler = Callable[[ToolCallRequest], Awaitable["ToolMessage | Command[Any]"]]


class MonitorMiddleware(AgentMiddleware):  # type: ignore[type-arg, unused-ignore]
    """Record every tool call of an agent and enforce the kill switch.

    Parameters
    ----------
    monitor : Monitor
        Your monitor.
    agent : str, optional
        The agent name. Default: the graph's name, else ``"default"``.
    user : callable, optional
        ``user(request) -> str | None``; default ``runtime.context.user_id``.
    """

    def __init__(
        self,
        monitor: Monitor,
        *,
        agent: str | None = None,
        user: Callable[[Any], str | None] | None = None,
    ) -> None:
        super().__init__()
        if not isinstance(monitor, Monitor):
            raise TypeError("MonitorMiddleware needs a Monitor")
        self._monitor = monitor
        self._agent = agent
        self._user = user

    # Kill switch before every model call -------------------------------------------------

    def before_model(self, state: Any, runtime: Any) -> dict[str, Any] | None:  # noqa: ANN401
        self._check_alive(_config(runtime), runtime)
        return None

    async def abefore_model(self, state: Any, runtime: Any) -> dict[str, Any] | None:  # noqa: ANN401
        self._check_alive(_config(runtime), runtime)
        return None

    # Every tool call -----------------------------------------------------------------------

    def wrap_tool_call(
        self, request: ToolCallRequest, handler: Handler
    ) -> ToolMessage | Command[Any]:
        who = self._who(request)
        self._check_alive(_config(request.runtime), request.runtime)
        start = time.perf_counter()
        try:
            result = handler(request)
        except GraphInterrupt as pause:
            self._record_pause(request, who, pause)
            raise
        except GraphBubbleUp:  # LangGraph control flow (e.g. a Command to the parent graph)
            raise
        except BaseException as exc:
            self._record(request, who, "error", start, {"error": f"{type(exc).__name__}: {exc}"})
            raise
        self._record_result(request, who, start, result)
        return result

    async def awrap_tool_call(
        self, request: ToolCallRequest, handler: AsyncHandler
    ) -> ToolMessage | Command[Any]:
        who = self._who(request)
        self._check_alive(_config(request.runtime), request.runtime)
        start = time.perf_counter()
        try:
            result = await handler(request)
        except GraphInterrupt as pause:
            self._record_pause(request, who, pause)
            raise
        except GraphBubbleUp:  # LangGraph control flow (e.g. a Command to the parent graph)
            raise
        except BaseException as exc:
            self._record(request, who, "error", start, {"error": f"{type(exc).__name__}: {exc}"})
            raise
        self._record_result(request, who, start, result)
        return result

    # ------------------------------------------------------------------------------------

    def _check_alive(self, config: Mapping[str, Any], runtime: Any) -> None:  # noqa: ANN401
        agent = self._agent or _agent_name(config)
        session = _thread(config)
        if self._monitor.is_killed(agent, session):
            raise AgentKilled(agent, session)

    def _who(self, request: ToolCallRequest) -> tuple[str, str | None, str | None]:
        config = _config(request.runtime)
        agent = self._agent or _agent_name(config)
        if self._user is not None:
            user = self._user(request)
        else:
            context = getattr(request.runtime, "context", None)
            user = (
                context.get("user_id")
                if isinstance(context, Mapping)
                else getattr(context, "user_id", None)
            )
        return agent, _thread(config), (str(user) if user else None)

    def _record_result(
        self,
        request: ToolCallRequest,
        who: tuple[str, str | None, str | None],
        start: float,
        result: object,
    ) -> None:
        if isinstance(result, ToolMessage) and result.status == "error":
            artifact = result.artifact if isinstance(result.artifact, Mapping) else {}
            decision = artifact.get("theaios") if isinstance(artifact, Mapping) else None
            if isinstance(decision, Mapping):
                data = {
                    k: decision.get(k)
                    for k in ("component", "codes", "reason", "proposal_id")
                    if decision.get(k) is not None
                }
                self._record(request, who, "denial", start, data)
                return
            self._record(request, who, "error", start, {"error": str(result.content)[:500]})
            return
        self._record(request, who, "action", start, {})

    def _record_pause(
        self,
        request: ToolCallRequest,
        who: tuple[str, str | None, str | None],
        pause: GraphInterrupt,
    ) -> None:
        asks = [i.value for i in (pause.args[0] if pause.args else []) if hasattr(i, "value")]
        ask = asks[0] if asks and isinstance(asks[0], Mapping) else {}
        data = {k: ask.get(k) for k in ("component", "proposal_id", "tier") if ask.get(k)}
        self._record(request, who, "approval_request", None, data)

    def _record(
        self,
        request: ToolCallRequest,
        who: tuple[str, str | None, str | None],
        event_type: str,
        start: float | None,
        data: dict[str, object],
    ) -> None:
        agent, session, user = who
        self._monitor.record(
            AgentEvent(
                timestamp=time.time(),
                agent=agent,
                event_type=event_type,
                data={
                    "tool": str(request.tool_call["name"]),
                    "tool_call_id": str(request.tool_call.get("id") or ""),
                    **data,
                },
                session_id=session,
                user=user,
                latency_ms=(time.perf_counter() - start) * 1000 if start is not None else None,
            )
        )


def _config(runtime: Any) -> Mapping[str, Any]:  # noqa: ANN401
    config = getattr(runtime, "config", None)
    if config is None:  # before_model's Runtime has no config attribute: use the context var
        from langgraph.config import get_config

        try:
            config = get_config()
        except RuntimeError:
            config = {}
    return config or {}


def _agent_name(config: Mapping[str, Any]) -> str:
    name = (config.get("metadata") or {}).get("lc_agent_name")
    return str(name) if name else "default"


def _thread(config: Mapping[str, Any]) -> str | None:
    thread = (config.get("configurable") or {}).get("thread_id")
    return str(thread) if thread else None
