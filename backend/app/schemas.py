"""Pydantic contracts shared by the API, fixtures, and (mirrored) frontend types.

Keep frontend/src/api/types.ts aligned with this file.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "1.0"

EventType = Literal[
    "pass",
    "reception",
    "carry",
    "shot",
    "tackle",
    "interception",
    "turnover",
    "pressure_start",
    "pressure_end",
    "stoppage",
]
Availability = Literal["event-only", "full-tracking", "degraded-tracking"]
Direction = Literal["+x", "-x"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Position(Strict):
    x: float
    y: float


class BallState(Strict):
    x: float
    y: float
    z: float
    vx: float
    vy: float
    possession_player_id: str | None


class PlayerState(Strict):
    player_id: str
    team_id: str
    x: float
    y: float
    vx: float
    vy: float
    observed_fields: list[str]


class TrackingFrame(Strict):
    frame_id: int
    time_s: float
    ball: BallState | None
    players: list[PlayerState]


class MatchEvent(Strict):
    event_id: str
    scenario_id: str
    time_s: float
    type: EventType
    team_id: str
    player_id: str | None
    recipient_id: str | None
    start_position: Position
    end_position: Position | None
    outcome: str | None
    related_frame_ids: list[int]
    # Extension beyond the core spec fields: other players the event concerns
    # (e.g. the ball carrier under pressure). Empty when not applicable.
    related_player_ids: list[str] = Field(default_factory=list)


class Player(Strict):
    player_id: str
    team_id: str
    number: int
    name: str
    role: str


class Team(Strict):
    team_id: str
    name: str
    short_name: str
    color: str
    marker_shape: Literal["circle", "square"]
    players: list[Player]


class PitchDimensions(Strict):
    length_m: float
    width_m: float


class AttackingDirection(Strict):
    team_id: str
    period: int
    direction: Direction


class FixturePaths(Strict):
    tracking: str
    events: str


class ScenarioManifest(Strict):
    schema_version: str
    scenario_id: str
    version: str
    seed: int
    title: str
    description: str
    synthetic: Literal[True]
    teams: list[Team]
    pitch: PitchDimensions
    frame_rate_hz: float
    frame_count: int
    duration_s: float
    period: int
    match_clock_offset_s: float
    attacking_directions: list[AttackingDirection]
    fixture_paths: FixturePaths
    generator_version: str
    dataset_hash: str
    availability: Availability
    available_fields: list[str]
    known_limitations: list[str]


class ScenarioSummary(Strict):
    scenario_id: str
    title: str
    description: str
    availability: Availability
    duration_s: float
    dataset_hash: str


class ReplayBundle(Strict):
    manifest: ScenarioManifest
    frames: list[TrackingFrame]
    events: list[MatchEvent]


class Capabilities(Strict):
    provider_mode: Literal["offline", "foundry", "foundry_local"]
    provider_label: str
    model_configured: bool
    scenarios: list[str]
    languages: list[str]
    synthetic_data_only: Literal[True]


class ErrorBody(Strict):
    code: str
    message: str


# ---------------------------------------------------------------------------
# Facts and evidence
# ---------------------------------------------------------------------------

EvidenceClass = Literal["observed", "estimated", "simulated"]


class TimeWindow(Strict):
    start_s: float
    end_s: float


class Coverage(Strict):
    availability: Availability
    frames_used: int
    frames_expected: int
    complete: bool
    note: str | None = None


class Fact(Strict):
    fact_id: str
    evidence_class: EvidenceClass
    metric: str
    subject_ids: list[str]
    value: float | None
    unit: str
    time_window: TimeWindow
    # The moment the replay should show for this fact.
    focus_time_s: float
    source_event_ids: list[str]
    source_frame_range: tuple[int, int] | None
    method_version: str
    coverage: Coverage
    limitations: list[str]
    # Rendered by code from `value`; never written by a model.
    statement: str
    # Plain-language version for casual audiences, rendered by code from the same value.
    plain: str = ""


class RefusedMetric(Strict):
    metric: str
    subject_ids: list[str] = Field(default_factory=list)
    reason: str


class FactPacket(Strict):
    scenario_id: str
    dataset_hash: str
    cursor_s: float
    window: TimeWindow
    facts: list[Fact]
    refused: list[RefusedMetric]


class QuestionOption(Strict):
    intent: str
    label: str
    example: str


class AskRequest(Strict):
    question: str = Field(min_length=1, max_length=300)
    # Data cutoff. None means the whole recorded sequence (post-event analysis).
    cursor_s: float | None = Field(default=None, ge=0)


class AnswerSentence(Strict):
    text: str
    fact_ids: list[str]


class AskResponse(Strict):
    question: str
    status: Literal["answered", "unsupported", "clarify", "insufficient_data"]
    intent: str | None
    intent_label: str | None
    matched_by: Literal["offline-rules"]
    cursor_s: float
    dataset_hash: str
    answer: list[AnswerSentence]
    facts: list[Fact]
    refused: list[RefusedMetric]
    notes: list[str]
    supported_questions: list[QuestionOption]


# ---------------------------------------------------------------------------
# Simulation (evidence class "simulated")
# ---------------------------------------------------------------------------

SimAction = Literal["hold", "press_earlier", "press_with_cover"]
AttackerPolicyName = Literal["patient", "direct"]


class CompareRequest(Strict):
    presser_id: str | None = Field(default=None, description="Defending player whose pressing decision is tested; default: the right-back who pressed.")
    frame_id: int | None = Field(default=None, ge=0, description="Branch frame; default: the pass that triggered the recorded press.")
    cover_delay_s: float = Field(default=0.6, ge=0.0, le=3.0)
    attacker_policy: AttackerPolicyName = "patient"
    rollouts: int = Field(default=200, ge=32, le=512)
    seed: int = 20261026


class RateSummary(Strict):
    count: int
    n: int
    rate: float
    ci95: tuple[float, float]


class ActionResult(Strict):
    action: SimAction
    label: str
    danger: RateSummary
    regain: RateSummary
    retained: RateSummary
    median_regain_s: float | None
    median_first_pass_s: float | None


class PairedDiff(Strict):
    metric: Literal["danger", "regain"]
    better: SimAction
    other: SimAction
    diff: float  # rate(other) - rate(better)
    ci95: tuple[float, float]


class Recommendation(Strict):
    status: Literal["recommend", "no_clear_winner", "inconclusive"]
    action: SimAction | None
    rule: str
    reasons: list[str]


class SimPlayer(Strict):
    player_id: str
    x: float
    y: float


class SimFrame(Strict):
    t: float
    ball: Position
    holder: str | None
    players: list[SimPlayer]


class SimEvent(Strict):
    t: float
    kind: str
    from_id: str | None
    to_id: str


class SampleRollout(Strict):
    action: SimAction
    rollout_index: int
    outcome: Literal["danger", "regain", "neither"]
    frames: list[SimFrame]
    events: list[SimEvent]


class BranchInfo(Strict):
    frame_id: int
    time_s: float
    carrier: str
    presser: str
    cover: str
    inside_option: str
    overlap_runner: str | None
    striker: str


class SimConfigOut(Strict):
    cover_delay_s: float
    attacker_policy: AttackerPolicyName
    rollouts: int
    seed: int
    horizon_s: float
    execution_noise: float


class ComparisonResult(Strict):
    run_id: str
    scenario_id: str
    dataset_hash: str
    evidence_class: Literal["simulated"]
    policy_version: str
    branch: BranchInfo
    config: SimConfigOut
    actions: list[ActionResult]
    diffs: list[PairedDiff]
    recommendation: Recommendation
    samples: list[SampleRollout]
    assumptions: list[str]
    compute_ms: int
    cached: bool


class ChallengeRequest(Strict):
    presser_id: str | None = None
    frame_id: int | None = Field(default=None, ge=0)
    cover_delays: list[float] = Field(default_factory=lambda: [0.0, 0.3, 0.6, 0.9, 1.2, 1.8], min_length=1, max_length=8)
    attacker_policies: list[AttackerPolicyName] = Field(default_factory=lambda: ["patient", "direct"], min_length=1, max_length=2)
    rollouts: int = Field(default=128, ge=32, le=256)
    seed: int = 20261026
    baseline_cover_delay_s: float = Field(default=0.6, ge=0.0, le=3.0)
    baseline_attacker_policy: AttackerPolicyName = "patient"


class ChallengeCell(Strict):
    cover_delay_s: float
    attacker_policy: AttackerPolicyName
    status: Literal["recommend", "no_clear_winner", "inconclusive"]
    action: SimAction | None
    danger: dict[str, float]
    regain: dict[str, float]


class ChallengeResult(Strict):
    run_id: str
    scenario_id: str
    evidence_class: Literal["simulated"]
    policy_version: str
    rollouts_per_action: int
    baseline: ChallengeCell
    cells: list[ChallengeCell]
    changed: list[ChallengeCell]
    tested_domain: str
    conclusion: str
    compute_ms: int


# ---------------------------------------------------------------------------
# Investigations (agent workflow)
# ---------------------------------------------------------------------------

ClaimType = Literal["observed", "estimated", "simulated", "interpretation", "insufficient_data"]
ProviderMode = Literal["offline", "foundry", "foundry_local", "fallback"]
InvestigationStatus = Literal["queued", "planning", "evidence", "challenging", "producing", "validating", "complete", "failed"]


class Claim(Strict):
    claim_type: ClaimType
    text: str = Field(max_length=500)
    fact_ids: list[str] = Field(default_factory=list)


class RejectedClaim(Strict):
    claim: Claim
    errors: list[str]


class TraceStep(Strict):
    agent: str
    kind: Literal["model", "tool", "validation", "repair", "fallback", "error", "rule"]
    summary: str
    tool: str | None = None
    duration_ms: int = 0


class InvestigationRequest(Strict):
    question: str = Field(min_length=1, max_length=300)
    cursor_s: float | None = Field(default=None, ge=0)
    audience: Literal["casual", "analyst"] = "analyst"


class InvestigationState(Strict):
    investigation_id: str
    scenario_id: str
    dataset_hash: str
    cursor_s: float
    question: str
    audience: Literal["casual", "analyst"]
    status: InvestigationStatus
    outcome: Literal["answered", "unsupported", "clarify", "insufficient_data"] | None = None
    provider_mode: ProviderMode
    provider_label: str
    model_deployment: str | None = None
    intent: str | None = None
    intent_label: str | None = None
    plan_summary: str | None = None
    facts: list[Fact] = Field(default_factory=list)
    simulation_run_ids: list[str] = Field(default_factory=list)
    challenge_summary: str | None = None
    claims: list[Claim] = Field(default_factory=list)
    # The fan view of the same facts, rendered by code in the same run, so switching audience never re-runs.
    casual_claims: list[Claim] = Field(default_factory=list)
    rejected_claims: list[RejectedClaim] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    trace: list[TraceStep] = Field(default_factory=list)
    model_calls: int = 0
    tool_calls: int = 0
    input_tokens: int | None = None
    output_tokens: int | None = None
    elapsed_ms: int = 0


# ---------------------------------------------------------------------------
# Recap and overlay export
# ---------------------------------------------------------------------------

GraphicType = Literal["player_spotlight", "event_comparison", "tradeoff_card", "insufficient_data_card"]


class OverlayCue(Strict):
    schema_version: str
    cue_id: str
    source_run_id: str
    scenario_hash: str
    timebase: Literal["sequence_s"]
    branch: Literal["recorded", "simulated"]
    start_s: float = Field(ge=0)
    duration_s: float = Field(gt=0)
    graphic_type: GraphicType
    title: str
    body: str
    language: str
    audience: Literal["casual", "analyst"]
    highlighted_player_ids: list[str]
    fact_ids: list[str]
    simulation_run_ids: list[str]
    evidence_class: EvidenceClass | Literal["interpretation"]
    assumptions_summary: str | None
    status: Literal["approved"]


class RecapInsight(Strict):
    order: int
    claims: list[Claim]  # approved claims shown together on one cue
    cue_id: str


class ExportBundle(Strict):
    schema_version: str
    investigation_id: str
    scenario_id: str
    scenario_hash: str
    question: str
    audience: Literal["casual", "analyst"]
    provider_mode: ProviderMode
    provider_label: str
    timebase: Literal["sequence_s"]
    sequence_duration_s: float
    playback_rate: float
    recap_duration_s: float
    insights: list[RecapInsight]
    cues: list[OverlayCue]
    synthetic_data: Literal[True]
