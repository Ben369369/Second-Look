"""Construction of the Microsoft Foundry chat client (Agent Framework).

Authentication: Microsoft Entra ID only, no API keys. Locally this is the Azure CLI
sign-in (`az login`); in a deployment, a service principal supplied through the
standard AZURE_CLIENT_ID / AZURE_TENANT_ID / AZURE_CLIENT_SECRET variables.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.config import Settings


def foundry_client_factory(settings: Settings) -> Callable[[], Any] | None:
    if not settings.foundry_configured:
        return None

    def make() -> Any:
        from agent_framework.foundry import FoundryChatClient
        from azure.identity import AzureCliCredential, ChainedTokenCredential, EnvironmentCredential

        from app.agents.workflow import FUNCTION_LIMITS

        return FoundryChatClient(
            project_endpoint=settings.foundry_project_endpoint,
            model=settings.foundry_model_deployment,
            credential=ChainedTokenCredential(EnvironmentCredential(), AzureCliCredential()),
            function_invocation_configuration=FUNCTION_LIMITS,  # type: ignore[arg-type]
        )

    return make
