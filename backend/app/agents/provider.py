"""Construction of the Agent Framework chat client for the configured provider.

- foundry: Microsoft Foundry cloud project. Microsoft Entra ID only, no API keys:
  `az login` locally, or AZURE_CLIENT_ID / AZURE_TENANT_ID / AZURE_CLIENT_SECRET in a deployment.
- foundry_local: Foundry Local on this device (no Azure subscription). Install the runtime
  (`winget install Microsoft.FoundryLocal`), then `foundry server start` and
  `foundry model load <FOUNDRY_LOCAL_MODEL>` before starting the app.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from collections.abc import Callable
from typing import Any

from app.config import Settings


def client_factory(settings: Settings) -> Callable[[], Any] | None:
    if not settings.model_configured:
        return None
    from app.agents.workflow import FUNCTION_LIMITS

    if settings.mode == "foundry_local":
        cache: dict[str, Any] = {}

        def make_local() -> Any:
            # Agent Framework's FoundryLocalClient pins an SDK (foundry-local-sdk 0.5.1) whose
            # start-up command no longer exists in the current Foundry Local CLI (0.12), so we
            # talk to the running Foundry Local server through its OpenAI-compatible endpoint
            # with Agent Framework's chat-completions client. Start it with `foundry server start`
            # and `foundry model load <model>`.
            if "client" not in cache:
                from agent_framework.openai import OpenAIChatCompletionClient
                from openai import AsyncOpenAI

                # A hard per-request timeout at the HTTP layer, so the investigation budget holds
                # even if a local generation runs long; no hidden SDK retries (the workflow retries).
                http = AsyncOpenAI(
                    base_url=_foundry_local_endpoint() + "/v1",
                    api_key="foundry-local",  # the local server does not check keys
                    timeout=max(30.0, settings.investigation_timeout_seconds / 3),
                    max_retries=0,
                )
                cache["client"] = OpenAIChatCompletionClient(
                    model=_loaded_model_id(settings.foundry_local_model or ""),
                    async_client=http,
                    function_invocation_configuration=FUNCTION_LIMITS,  # type: ignore[arg-type]
                )
            return cache["client"]

        return make_local

    def make() -> Any:
        from agent_framework.foundry import FoundryChatClient
        from azure.identity import AzureCliCredential, ChainedTokenCredential, EnvironmentCredential

        return FoundryChatClient(
            project_endpoint=settings.foundry_project_endpoint,
            model=settings.foundry_model_deployment,
            credential=ChainedTokenCredential(EnvironmentCredential(), AzureCliCredential()),
            function_invocation_configuration=FUNCTION_LIMITS,  # type: ignore[arg-type]
        )

    return make


def _foundry_cli(*args: str) -> dict:
    out = subprocess.run(["foundry", *args, "-o", "json"], capture_output=True, text=True, timeout=60, encoding="utf-8", errors="replace").stdout
    out = re.sub(r"\x1b\[[0-9;]*m", "", out)
    return json.loads(out[out.find("{") :])


def _foundry_local_endpoint() -> str:
    """Base URL of the running Foundry Local server (the port changes on every start)."""
    url = os.environ.get("FOUNDRY_LOCAL_ENDPOINT")
    if url:
        return url.rstrip("/")
    status = _foundry_cli("server", "status")
    if not status.get("running") or not status.get("webUrls"):
        raise RuntimeError("Foundry Local server is not running; run `foundry server start`.")
    return status["webUrls"][0].rstrip("/")


def _loaded_model_id(alias: str) -> str:
    """The server addresses models by variant id (e.g. qwen3-8b-generic-gpu:2); resolve the alias."""
    info = _foundry_cli("model", "info", alias)
    model = info.get("model", info)
    variants = model.get("variants") or []
    gpu = next((v for v in variants if v.get("device") == "Gpu"), variants[0] if variants else None)
    return (gpu or model).get("id", alias)


# Backwards-compatible name used by earlier code and tests.
foundry_client_factory = client_factory
