"""In-process investigation registry.

Prototype limits (documented): one server process; at most MAX_ACTIVE running and
MAX_KEPT stored investigations; entries expire after TTL_S; everything is lost on
restart. Multi-worker deployment would need shared storage.
"""

from __future__ import annotations

import asyncio
import os
import time
import uuid
from collections import OrderedDict
from typing import Any

from app.agents.workflow import OFFLINE_LABEL, Workflow
from app.config import Settings
from app.metrics.view import make_view
from app.schemas import InvestigationRequest, InvestigationState, ReplayBundle

MAX_KEPT = 64
MAX_ACTIVE = 4
TTL_S = 30 * 60


class RegistryFull(RuntimeError):
    pass


class InvestigationRegistry:
    def __init__(self, settings: Settings, client_factory: Any = None):
        self.settings = settings
        self.client_factory = client_factory
        self._items: OrderedDict[str, tuple[float, InvestigationState]] = OrderedDict()
        self._tasks: dict[str, asyncio.Task] = {}

    def _expire(self) -> None:
        now = time.time()
        for k in [k for k, (t, _) in self._items.items() if now - t > TTL_S]:
            self._items.pop(k, None)
        while len(self._items) > MAX_KEPT:
            self._items.popitem(last=False)

    @property
    def model_enabled(self) -> bool:
        return self.settings.mode != "offline" and self.settings.model_configured and self.client_factory is not None

    def get(self, investigation_id: str) -> InvestigationState | None:
        self._expire()
        item = self._items.get(investigation_id)
        return item[1] if item else None

    async def start(self, bundle: ReplayBundle, req: InvestigationRequest) -> InvestigationState:
        self._expire()
        active = sum(1 for t in self._tasks.values() if not t.done())
        # One on-device model serves one investigation at a time; parallel runs just slow each other down.
        limit = 1 if self.settings.mode == "foundry_local" else MAX_ACTIVE
        if active >= limit:
            raise RegistryFull("too many investigations running; try again shortly")
        view = make_view(bundle, req.cursor_s)
        state = InvestigationState(
            investigation_id=uuid.uuid4().hex[:12],
            scenario_id=bundle.manifest.scenario_id,
            dataset_hash=bundle.manifest.dataset_hash,
            cursor_s=view.cursor_s,
            question=req.question,
            audience=req.audience,
            status="queued",
            provider_mode=self.settings.mode if self.model_enabled else "offline",
            provider_label=self.settings.model_label if self.model_enabled else OFFLINE_LABEL,
            model_deployment=self.settings.model_name if self.model_enabled else None,
        )
        self._items[state.investigation_id] = (time.time(), state)
        wf = Workflow(state, view, self.settings, self.client_factory)
        if not self.model_enabled:
            # Offline runs are deterministic and fast enough to finish within the request.
            await asyncio.to_thread(wf.run_offline)
            return state
        if os.environ.get("VERCEL") == "1":
            # Serverless functions may be frozen after the response, so run within the request.
            await self._run(wf)
            return state
        self._tasks[state.investigation_id] = asyncio.create_task(self._run(wf))
        return state

    async def _run(self, wf: Workflow) -> None:
        try:
            await wf.run_foundry()
        except Exception as exc:  # never leave an investigation stuck in a running state
            wf.state.errors.append(f"workflow_error: {type(exc).__name__}")
            wf.state.status = "failed"
