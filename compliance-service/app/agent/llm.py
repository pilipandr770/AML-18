"""LLM client boundary. The agent talks to this interface only; the real
implementation wraps the Anthropic Messages API (tool use), tests use a
scripted fake. Timeouts and a per-minute call cap are enforced here, and
any failure surfaces as LLMUnavailable so callers fall back to
needs_review -- never to auto-clear."""

import threading
import time
from collections import deque
from dataclasses import dataclass, field


class LLMUnavailable(Exception):
    pass


@dataclass
class LLMResponse:
    stop_reason: str  # "tool_use" | "end_turn" | other
    blocks: list = field(default_factory=list)  # {"type":"text","text":..} | {"type":"tool_use","id","name","input"}


class RateLimiter:
    def __init__(self, max_calls: int, window_seconds: float = 60.0):
        self.max_calls = max_calls
        self.window = window_seconds
        self._calls: deque = deque()
        self._lock = threading.Lock()

    def check(self):
        now = time.monotonic()
        with self._lock:
            while self._calls and now - self._calls[0] > self.window:
                self._calls.popleft()
            if len(self._calls) >= self.max_calls:
                raise LLMUnavailable("LLM rate limit reached")
            self._calls.append(now)


class AnthropicClient:
    def __init__(self, api_key: str, model: str, timeout_seconds: float, max_calls_per_minute: int):
        if not api_key or not model:
            raise LLMUnavailable("ANTHROPIC_API_KEY / ANTHROPIC_MODEL not configured")
        import anthropic

        self._anthropic = anthropic
        self._client = anthropic.Anthropic(api_key=api_key, timeout=timeout_seconds, max_retries=1)
        self.model = model
        self._limiter = RateLimiter(max_calls_per_minute)

    def complete(self, system: str, messages: list, tools: list, max_tokens: int = 1024) -> LLMResponse:
        self._limiter.check()
        try:
            resp = self._client.messages.create(
                model=self.model, max_tokens=max_tokens, system=system, messages=messages, tools=tools,
            )
        except self._anthropic.APIError as exc:
            raise LLMUnavailable(f"LLM call failed: {type(exc).__name__}") from exc
        except Exception as exc:  # network/timeouts surface as generic errors in some SDK paths
            raise LLMUnavailable(f"LLM call failed: {type(exc).__name__}") from exc

        blocks = []
        for b in resp.content:
            if b.type == "text":
                blocks.append({"type": "text", "text": b.text})
            elif b.type == "tool_use":
                blocks.append({"type": "tool_use", "id": b.id, "name": b.name, "input": dict(b.input)})
        return LLMResponse(stop_reason=resp.stop_reason, blocks=blocks)


class ScriptedLLM:
    """Test double: replays a list of LLMResponse objects (or raises an
    exception instance placed in the list). Records what it was sent."""

    def __init__(self, script):
        self.script = list(script)
        self.calls: list = []

    def complete(self, system, messages, tools, max_tokens=1024):
        self.calls.append({"system": system, "messages": [dict(m) for m in messages], "tools": tools})
        if not self.script:
            raise LLMUnavailable("script exhausted")
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item
