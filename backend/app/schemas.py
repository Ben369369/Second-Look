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
    provider_mode: Literal["offline", "foundry"]
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
