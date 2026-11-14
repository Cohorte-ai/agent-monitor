# LangChain agents and LiteLLM

## LangChain 1.x / Deep Agents middleware

```bash
pip install "theaios-agent-monitor[langchain-agent]"
```

```python
from langchain.agents import create_agent
from theaios.agent_monitor import Monitor, load_config
from theaios.agent_monitor.adapters.langchain_agent import MonitorMiddleware

monitor = Monitor(load_config("monitor.yaml"))
agent = create_agent(model, tools, name="assistant", context_schema=Ctx, checkpointer=saver,
                     middleware=[MonitorMiddleware(monitor), AgentAuthMiddleware(engine),
                                 FlowMiddleware(guard)])
```

Put it **first** (the outermost), so it sees what the middlewares inside it decide.

- **Kill switch**: before every model call and every tool call, a killed agent or session
  stops the run: `AgentKilled` is raised (`monitor.kill_agent("assistant")`,
  `monitor.kill_session(thread_id)`, `monitor.kill_global()`).
- **Events**, one per tool call: `action` (it ran), `denial` (an inner middleware refused it:
  agent-auth, guardrails; the event carries its component, codes and reason), `error` (the tool
  failed), and `approval_request` once when the run pauses for a person. Model calls are not
  events (their cost comes from LiteLLM, below).
- Agent = `agent=` or the graph's name; session = the LangGraph `thread_id`; user = `user=` or
  `runtime.context.user_id`.

Deep Agents does not pass the main agent's middleware to its sub-agents: add a
`MonitorMiddleware` to each sub-agent's `middleware` (same monitor).

Events of a killed agent are not stored (the monitor drops them): the run stops, and the
refusal is the `AgentKilled` exception your application catches.

## LiteLLM: cost per agent, kill switch

```bash
pip install "theaios-agent-monitor[litellm]"
```

```python
import litellm
from theaios.agent_monitor.adapters.litellm_logger import MonitorLogger

logger = MonitorLogger(monitor)
litellm.callbacks = [logger]     # register once: LiteLLM keeps earlier registrations

litellm.completion(model="gpt-4.1-mini", messages=messages,
                   metadata={"agent": "assistant", "session_id": thread_id}, user="alice")
```

- Every completed call is a `cost` event (LiteLLM's computed cost in USD, model, tokens,
  latency); a failed call is an `error` event. Agent and session come from the call's
  `metadata` (keys configurable), the user from `user=`.
- **Kill switch**: async calls (`acompletion`) of a killed agent or session are refused before
  they are sent. LiteLLM offers no hook for sync calls that sees the metadata: wrap them,
  `completion = logger.guard(litellm.completion)`.
- Per-agent API keys are a LiteLLM proxy feature (virtual keys), not part of this adapter.
