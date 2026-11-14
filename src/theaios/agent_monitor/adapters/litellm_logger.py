"""Cost attribution and the kill switch for LiteLLM calls.

Requires ``litellm``: ``pip install "theaios-agent-monitor[litellm]"``.

Every completed call becomes a ``cost`` event (cost in USD as LiteLLM computes it, model,
tokens, latency), every failed call an ``error`` event, for the agent named in the call's
metadata::

    import litellm
    from theaios.agent_monitor.adapters.litellm_logger import MonitorLogger

    logger = MonitorLogger(monitor)
    litellm.callbacks = [logger]          # register once: LiteLLM keeps old registrations

    litellm.completion(model=..., messages=...,
                       metadata={"agent": "assistant", "session_id": "t1"}, user="alice")

**Kill switch.** For async calls (``litellm.acompletion``), a killed agent or session is
refused before the request is sent (``AgentKilled`` is raised). LiteLLM has no pre-call hook for sync calls that sees the metadata:
wrap them, ``completion = logger.guard(litellm.completion)``.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Any, TypeVar

from theaios.agent_monitor.engine import Monitor
from theaios.agent_monitor.kill_switch import AgentKilled
from theaios.agent_monitor.types import AgentEvent

try:
    from litellm.integrations.custom_logger import CustomLogger
except ImportError as e:  # pragma: no cover - exercised only without the extra
    raise ImportError(
        'The LiteLLM logger needs litellm. Install with: pip install "theaios-agent-monitor[litellm]"'
    ) from e

T = TypeVar("T")


class MonitorLogger(CustomLogger):  # type: ignore[misc, unused-ignore]
    """A LiteLLM ``CustomLogger`` that records cost and errors per agent.

    Parameters
    ----------
    monitor : Monitor
        Your monitor.
    default_agent : str
        The agent for calls whose metadata names none. Default ``"unknown"``.
    agent_key, session_key : str
        Metadata keys for the agent and the session. Default ``"agent"``, ``"session_id"``.
    """

    def __init__(
        self,
        monitor: Monitor,
        *,
        default_agent: str = "unknown",
        agent_key: str = "agent",
        session_key: str = "session_id",
    ) -> None:
        super().__init__()
        if not isinstance(monitor, Monitor):
            raise TypeError("MonitorLogger needs a Monitor")
        self._monitor = monitor
        self._default_agent = default_agent
        self._agent_key = agent_key
        self._session_key = session_key

    # LiteLLM calls these with keyword arguments: the parameter names must stay exactly so.

    def log_success_event(
        self, kwargs: Any, response_obj: Any, start_time: Any, end_time: Any
    ) -> None:  # noqa: ANN401
        self._record(kwargs, response_obj, start_time, end_time, ok=True)

    async def async_log_success_event(
        self, kwargs: Any, response_obj: Any, start_time: Any, end_time: Any
    ) -> None:  # noqa: ANN401
        self._record(kwargs, response_obj, start_time, end_time, ok=True)

    def log_failure_event(
        self, kwargs: Any, response_obj: Any, start_time: Any, end_time: Any
    ) -> None:  # noqa: ANN401
        self._record(kwargs, response_obj, start_time, end_time, ok=False)

    async def async_log_failure_event(
        self, kwargs: Any, response_obj: Any, start_time: Any, end_time: Any
    ) -> None:  # noqa: ANN401
        self._record(kwargs, response_obj, start_time, end_time, ok=False)

    async def async_pre_call_deployment_hook(
        self, kwargs: dict[str, Any], call_type: Any
    ) -> dict[str, Any] | None:  # noqa: ANN401
        """Called by LiteLLM before every async call: refuse a killed agent or session."""
        agent, session = self._who(kwargs)
        if self._monitor.is_killed(agent, session):
            raise AgentKilled(agent, session)
        return None

    def guard(self, fn: Callable[..., T]) -> Callable[..., T]:
        """Wrap a sync LiteLLM call (``litellm.completion``) with the kill switch."""

        def guarded(*args: Any, **kwargs: Any) -> T:  # noqa: ANN401
            agent, session = self._who(kwargs)
            if self._monitor.is_killed(agent, session):
                raise AgentKilled(agent, session)
            return fn(*args, **kwargs)

        guarded.__name__ = getattr(fn, "__name__", "guarded")
        guarded.__doc__ = getattr(fn, "__doc__", None)
        return guarded

    # ------------------------------------------------------------------------------------

    def _metadata(self, kwargs: Mapping[str, Any]) -> Mapping[str, Any]:
        params = kwargs.get("litellm_params")
        meta = params.get("metadata") if isinstance(params, Mapping) else None
        if not isinstance(meta, Mapping):
            meta = kwargs.get("metadata")  # before the call (pre-call hook, guard)
        return meta if isinstance(meta, Mapping) else {}

    def _who(self, kwargs: Mapping[str, Any]) -> tuple[str, str | None]:
        meta = self._metadata(kwargs)
        agent = meta.get(self._agent_key)
        session = meta.get(self._session_key)
        return (str(agent) if agent else self._default_agent, str(session) if session else None)

    def _record(
        self, kwargs: Any, response_obj: Any, start_time: Any, end_time: Any, *, ok: bool
    ) -> None:  # noqa: ANN401
        if not isinstance(kwargs, Mapping):
            return
        agent, session = self._who(kwargs)
        user = kwargs.get("user")
        data: dict[str, object] = {"model": str(kwargs.get("model") or "")}
        usage = getattr(response_obj, "usage", None)
        for name in ("prompt_tokens", "completion_tokens", "total_tokens"):
            value = getattr(usage, name, None)
            if isinstance(value, int):
                data[name] = value
        if not ok:
            exc = kwargs.get("exception") or response_obj
            data["error"] = f"{type(exc).__name__}: {exc}"[:500]
        cost = kwargs.get("response_cost")
        self._monitor.record(
            AgentEvent(
                timestamp=time.time(),
                agent=agent,
                event_type="cost" if ok else "error",
                data=data,
                session_id=session,
                user=str(user) if user else None,
                cost_usd=float(cost) if ok and isinstance(cost, (int, float)) else None,
                latency_ms=_ms(start_time, end_time),
            )
        )


def _ms(start: object, end: object) -> float | None:
    if isinstance(start, datetime) and isinstance(end, datetime):
        return (end - start).total_seconds() * 1000
    if isinstance(start, (int, float)) and isinstance(end, (int, float)):
        return (float(end) - float(start)) * 1000
    return None
