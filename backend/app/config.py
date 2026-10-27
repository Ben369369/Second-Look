"""App-owned configuration. Names here are Second Look conventions, not SDK-native variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

REPO_ROOT = Path(__file__).resolve().parents[2]
# Fixtures live inside backend/ so a deployment of backend/ alone (e.g. a Vercel service) includes them.
BACKEND_ROOT = Path(__file__).resolve().parents[1]

# offline: rule-based, no model. foundry: Microsoft Foundry cloud project. foundry_local: Foundry Local on this device.
ProviderMode = Literal["offline", "foundry", "foundry_local"]
MODES = ("offline", "foundry", "foundry_local")


@dataclass(frozen=True)
class Settings:
    mode: ProviderMode
    fixtures_dir: Path
    foundry_project_endpoint: str | None
    foundry_model_deployment: str | None
    foundry_local_model: str | None
    foundry_local_device: str | None
    simulation_max_rollouts: int
    investigation_timeout_seconds: int

    @property
    def foundry_configured(self) -> bool:
        return bool(self.foundry_project_endpoint and self.foundry_model_deployment)

    @property
    def model_configured(self) -> bool:
        if self.mode == "foundry":
            return self.foundry_configured
        if self.mode == "foundry_local":
            return bool(self.foundry_local_model)
        return False

    @property
    def model_name(self) -> str | None:
        return {"foundry": self.foundry_model_deployment, "foundry_local": self.foundry_local_model}.get(self.mode)

    @property
    def model_label(self) -> str:
        if self.mode == "foundry_local":
            return f"Foundry Local (on-device) · {self.foundry_local_model} · Agent Framework"
        return f"Microsoft Foundry · {self.foundry_model_deployment} · Agent Framework"


def load_settings() -> Settings:
    # A local .env at the repo root is read if present (never committed); real environment variables win.
    try:
        from dotenv import load_dotenv

        load_dotenv(REPO_ROOT / ".env", override=False)
    except ImportError:
        pass
    mode = os.environ.get("SECOND_LOOK_MODE", "offline").strip().lower()
    if mode not in MODES:
        mode = "offline"
    return Settings(
        mode=mode,  # type: ignore[arg-type]
        fixtures_dir=Path(os.environ.get("SECOND_LOOK_FIXTURES_DIR", BACKEND_ROOT / "fixtures" / "development")),
        foundry_project_endpoint=os.environ.get("FOUNDRY_PROJECT_ENDPOINT") or None,
        foundry_model_deployment=os.environ.get("FOUNDRY_MODEL_DEPLOYMENT") or None,
        foundry_local_model=os.environ.get("FOUNDRY_LOCAL_MODEL") or None,
        foundry_local_device=(os.environ.get("FOUNDRY_LOCAL_DEVICE") or None),
        simulation_max_rollouts=int(os.environ.get("SIMULATION_MAX_ROLLOUTS", "200")),
        investigation_timeout_seconds=int(os.environ.get("INVESTIGATION_TIMEOUT_SECONDS", "60")),
    )
