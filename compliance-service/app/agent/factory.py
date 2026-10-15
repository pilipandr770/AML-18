"""Builds the agent's runtime dependencies (LLM, chain adapter, executor)
lazily from config. Tests replace app.extensions["agent_runtime"]."""

from dataclasses import dataclass

from app.agent.chain import build_ledger
from app.agent.llm import AnthropicClient
from app.agent.operations import RecordingExecutor, WebhookExecutor


@dataclass
class AgentRuntime:
    llm: object
    ledger: object
    executor: object


def get_runtime(app) -> AgentRuntime:
    rt = app.extensions.get("agent_runtime")
    if rt is None:
        cfg = app.config
        rt = AgentRuntime(
            llm=AnthropicClient(cfg["ANTHROPIC_API_KEY"], cfg["ANTHROPIC_MODEL"],
                                cfg["AGENT_LLM_TIMEOUT_SECONDS"], cfg["AGENT_LLM_MAX_CALLS_PER_MINUTE"]),
            ledger=build_ledger(cfg),
            executor=WebhookExecutor() if cfg.get("AGENT_EXECUTOR") == "webhook" else RecordingExecutor(),
        )
        app.extensions["agent_runtime"] = rt
    return rt
