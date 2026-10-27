"""App-owned configuration. Names here are Second Look conventions, not SDK-native variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

REPO_ROOT = Path(__file__).resolve().parents[2]
# Fixtures live inside backend/ so a deployment of backend/ alone (e.g. a Vercel service) includes them.
BACKEND_ROOT = Path(__file__).resolve().parents[1]

ProviderMode = Literal["offline", "foundry"]


@dataclass(frozen=True)
class Settings:
    mode: ProviderMode
    fixtures_dir: Path
    foundry_project_endpoint: str | None
    foundry_model_deployment: str | None
    simulation_max_rollouts: int
    investigation_timeout_seconds: int

    @property
    def foundry_configured(self) -> bool:
        return bool(self.foundry_project_endpoint and self.foundry_model_deployment)


def load_settings() -> Settings:
    # A local .env at the repo root is read if present (never committed); real environment variables win.
    try:
        from dotenv import load_dotenv

        load_dotenv(REPO_ROOT / ".env", override=False)
    except ImportError:
        pass
    mode = os.environ.get("SECOND_LOOK_MODE", "offline").strip().lower()
    if mode not in ("offline", "foundry"):
        mode = "offline"
    return Settings(
        mode=mode,  # type: ignore[arg-type]
        fixtures_dir=Path(os.environ.get("SECOND_LOOK_FIXTURES_DIR", BACKEND_ROOT / "fixtures" / "development")),
        foundry_project_endpoint=os.environ.get("FOUNDRY_PROJECT_ENDPOINT") or None,
        foundry_model_deployment=os.environ.get("FOUNDRY_MODEL_DEPLOYMENT") or None,
        simulation_max_rollouts=int(os.environ.get("SIMULATION_MAX_ROLLOUTS", "200")),
        investigation_timeout_seconds=int(os.environ.get("INVESTIGATION_TIMEOUT_SECONDS", "60")),
    )
