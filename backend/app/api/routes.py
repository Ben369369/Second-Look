from __future__ import annotations

from fastapi import APIRouter, Query, Request

from app.data.loader import ScenarioRegistry
from app.errors import ApiError
from app.investigations.questions import CATALOGUE, ask
from app.metrics.facts import FactBuilder
from app.metrics.view import make_view
from app.schemas import (
    AskRequest,
    AskResponse,
    Capabilities,
    FactPacket,
    QuestionOption,
    ReplayBundle,
    ScenarioManifest,
    ScenarioSummary,
    TimeWindow,
)

router = APIRouter(prefix="/api")

OFFLINE_LABEL = "Offline demonstration — no language model connected"


def _registry(request: Request) -> ScenarioRegistry:
    return request.app.state.registry


def _bundle(request: Request, scenario_id: str) -> ReplayBundle:
    bundle = _registry(request).get(scenario_id)
    if bundle is None:
        raise ApiError(404, "scenario_not_found", f"No scenario named '{scenario_id[:64]}'.")
    return bundle


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/capabilities", response_model=Capabilities)
def capabilities(request: Request) -> Capabilities:
    settings = request.app.state.settings
    # Stage 1: no model integration exists yet, so the provider is always offline.
    return Capabilities(
        provider_mode="offline",
        provider_label=OFFLINE_LABEL,
        model_configured=settings.foundry_configured,
        scenarios=_registry(request).ids(),
        languages=["en"],
        synthetic_data_only=True,
    )


@router.get("/scenarios", response_model=list[ScenarioSummary])
def list_scenarios(request: Request) -> list[ScenarioSummary]:
    out = []
    for sid in _registry(request).ids():
        m = _bundle(request, sid).manifest
        out.append(
            ScenarioSummary(
                scenario_id=m.scenario_id,
                title=m.title,
                description=m.description,
                availability=m.availability,
                duration_s=m.duration_s,
                dataset_hash=m.dataset_hash,
            )
        )
    return out


@router.get("/scenarios/{scenario_id}", response_model=ScenarioManifest)
def get_manifest(scenario_id: str, request: Request) -> ScenarioManifest:
    return _bundle(request, scenario_id).manifest


@router.get("/scenarios/{scenario_id}/replay", response_model=ReplayBundle)
def get_replay(scenario_id: str, request: Request) -> ReplayBundle:
    return _bundle(request, scenario_id)


@router.get("/questions", response_model=list[QuestionOption])
def questions() -> list[QuestionOption]:
    return CATALOGUE


@router.get("/scenarios/{scenario_id}/facts", response_model=FactPacket)
def get_facts(
    scenario_id: str,
    request: Request,
    start_s: float = Query(0.0, ge=0),
    end_s: float | None = Query(None, ge=0),
    cursor_s: float | None = Query(None, ge=0),
) -> FactPacket:
    """Facts computable from data up to cursor_s (default: whole sequence), within [start_s, end_s]."""
    bundle = _bundle(request, scenario_id)
    view = make_view(bundle, cursor_s)
    end = min(end_s if end_s is not None else view.cursor_s, view.cursor_s)
    if start_s > end:
        raise ApiError(422, "invalid_window", "start_s must not be after end_s or the cursor.")
    b = FactBuilder(view)
    facts = []
    for e in view.events:
        if start_s <= e.time_s <= end:
            if e.type == "pass":
                facts.append(b.pass_distance(e))
            elif e.type == "pressure_start":
                facts.append(b.defender_distance(e.player_id, e.related_player_ids[0], e.time_s, "when pressure began", e))  # type: ignore[arg-type]
    for team in view.manifest.teams:
        facts.append(b.pass_completion(team.team_id, start_s, end))
    facts += b.possession_duration()
    facts.append(b.transitions(start_s, end))
    for pid in view.players:
        facts.append(b.tracked_running(pid, start_s, end))
    # Teams with no passes in the window are an expected absence, not a refusal worth reporting.
    refused = [r for r in b.refused if r.metric != "pass_completion"]
    return FactPacket(
        scenario_id=scenario_id,
        dataset_hash=view.manifest.dataset_hash,
        cursor_s=view.cursor_s,
        window=TimeWindow(start_s=start_s, end_s=end),
        facts=[f for f in facts if f is not None],
        refused=refused,
    )


@router.post("/scenarios/{scenario_id}/ask", response_model=AskResponse)
def ask_question(scenario_id: str, body: AskRequest, request: Request) -> AskResponse:
    """Answer a supported factual question from data up to the cursor (offline rule-based routing)."""
    bundle = _bundle(request, scenario_id)
    return ask(make_view(bundle, body.cursor_s), body.question)
