"""A scripted chat client for exercising the real Agent Framework loop without a model.

It subclasses the framework's own BaseChatClient with FunctionInvocationLayer, so
Agent.run, tool invocation, turn limits and response handling are the real code;
only the model's replies are scripted. Replies are chosen by role (from the system
instructions) via a callback that sees the conversation so far.
"""

from __future__ import annotations

import itertools
import json
from collections.abc import Callable
from typing import Any

from agent_framework import BaseChatClient, ChatResponse, Content, FunctionInvocationLayer, Message

Reply = dict[str, Any]  # {"tool": name, "args": {...}} or {"text": "..."} or {"raise": Exception}


def _role(messages, options) -> str:
    text = str((options or {}).get("instructions") or "") + " ".join(m.text or "" for m in messages if getattr(m, "role", "") == "system")
    for role in ("planner", "evidence analyst", "challenger", "producer"):
        if f"You are the {role}" in text:
            return role
    return "unknown"


class ScriptedChatClient(FunctionInvocationLayer, BaseChatClient):
    def __init__(self, script: Callable[[str, list[Any], int], Reply], **kwargs: Any):
        super().__init__(**kwargs)
        self.script = script
        self.calls: list[str] = []
        self._ids = itertools.count()

    async def _inner_get_response(self, *, messages, stream, options, **kwargs):  # type: ignore[override]
        role = _role(messages, options)
        turn = sum(1 for r in self.calls if r == role)
        self.calls.append(role)
        reply = self.script(role, list(messages), turn)
        if "raise" in reply:
            raise reply["raise"]
        if "tool" in reply:
            content = Content.from_function_call(f"call_{next(self._ids)}", reply["tool"], arguments=json.dumps(reply.get("args", {})))
        else:
            content = Content.from_text(reply["text"])
        return ChatResponse(messages=[Message("assistant", [content])])


def tool_results(messages) -> list[dict]:
    """Parsed results of every function call so far in the conversation."""
    out = []
    for m in messages:
        for c in getattr(m, "contents", []) or []:
            if getattr(c, "type", None) == "function_result":
                try:
                    out.append(json.loads(c.result if isinstance(c.result, str) else json.dumps(c.result)))
                except (TypeError, ValueError):
                    pass
    return out


def prompt_text(messages) -> str:
    return "\n".join(m.text or "" for m in messages if getattr(m, "role", "") == "user")
