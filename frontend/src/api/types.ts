// Mirrors backend/app/schemas.py. Keep the two aligned when either changes.

export type EventType =
  | "pass"
  | "reception"
  | "carry"
  | "shot"
  | "tackle"
  | "interception"
  | "turnover"
  | "pressure_start"
  | "pressure_end"
  | "stoppage";

export type Availability = "event-only" | "full-tracking" | "degraded-tracking";

export interface Position {
  x: number;
  y: number;
}

export interface BallState extends Position {
  z: number;
  vx: number;
  vy: number;
  possession_player_id: string | null;
}

export interface PlayerState extends Position {
  player_id: string;
  team_id: string;
  vx: number;
  vy: number;
  observed_fields: string[];
}

export interface TrackingFrame {
  frame_id: number;
  time_s: number;
  ball: BallState | null;
  players: PlayerState[];
}

export interface MatchEvent {
  event_id: string;
  scenario_id: string;
  time_s: number;
  type: EventType;
  team_id: string;
  player_id: string | null;
  recipient_id: string | null;
  start_position: Position;
  end_position: Position | null;
  outcome: string | null;
  related_frame_ids: number[];
  related_player_ids: string[];
}

export interface Player {
  player_id: string;
  team_id: string;
  number: number;
  name: string;
  role: string;
}

export interface Team {
  team_id: string;
  name: string;
  short_name: string;
  color: string;
  marker_shape: "circle" | "square";
  players: Player[];
}

export interface ScenarioManifest {
  schema_version: string;
  scenario_id: string;
  version: string;
  seed: number;
  title: string;
  description: string;
  synthetic: true;
  teams: Team[];
  pitch: { length_m: number; width_m: number };
  frame_rate_hz: number;
  frame_count: number;
  duration_s: number;
  period: number;
  match_clock_offset_s: number;
  attacking_directions: { team_id: string; period: number; direction: "+x" | "-x" }[];
  fixture_paths: { tracking: string; events: string };
  generator_version: string;
  dataset_hash: string;
  availability: Availability;
  available_fields: string[];
  known_limitations: string[];
}

export interface ScenarioSummary {
  scenario_id: string;
  title: string;
  description: string;
  availability: Availability;
  duration_s: number;
  dataset_hash: string;
}

export interface ReplayBundle {
  manifest: ScenarioManifest;
  frames: TrackingFrame[];
  events: MatchEvent[];
}

export interface Capabilities {
  provider_mode: "offline" | "foundry" | "foundry_local";
  provider_label: string;
  model_configured: boolean;
  scenarios: string[];
  languages: string[];
  synthetic_data_only: true;
}

export type EvidenceClass = "observed" | "estimated" | "simulated";

export interface Fact {
  fact_id: string;
  evidence_class: EvidenceClass;
  metric: string;
  subject_ids: string[];
  value: number | null;
  unit: string;
  time_window: { start_s: number; end_s: number };
  focus_time_s: number;
  source_event_ids: string[];
  source_frame_range: [number, number] | null;
  method_version: string;
  coverage: { availability: Availability; frames_used: number; frames_expected: number; complete: boolean; note: string | null };
  limitations: string[];
  statement: string;
  plain: string;
}

export interface RefusedMetric {
  metric: string;
  subject_ids: string[];
  reason: string;
}

export interface FactPacket {
  scenario_id: string;
  dataset_hash: string;
  cursor_s: number;
  window: { start_s: number; end_s: number };
  facts: Fact[];
  refused: RefusedMetric[];
}

export interface QuestionOption {
  intent: string;
  label: string;
  example: string;
}

export interface AskResponse {
  question: string;
  status: "answered" | "unsupported" | "clarify" | "insufficient_data";
  intent: string | null;
  intent_label: string | null;
  matched_by: "offline-rules";
  cursor_s: number;
  dataset_hash: string;
  answer: { text: string; fact_ids: string[] }[];
  facts: Fact[];
  refused: RefusedMetric[];
  notes: string[];
  supported_questions: QuestionOption[];
}

// ---- simulation (evidence class "simulated") ----

export type SimAction = "hold" | "press_earlier" | "press_with_cover";
export type AttackerPolicy = "patient" | "direct";

export interface CompareRequest {
  presser_id?: string | null;
  frame_id?: number | null;
  cover_delay_s: number;
  attacker_policy: AttackerPolicy;
  rollouts?: number;
  seed?: number;
}

export interface RateSummary {
  count: number;
  n: number;
  rate: number;
  ci95: [number, number];
}

export interface ActionResult {
  action: SimAction;
  label: string;
  danger: RateSummary;
  regain: RateSummary;
  retained: RateSummary;
  median_regain_s: number | null;
  median_first_pass_s: number | null;
}

export interface PairedDiff {
  metric: "danger" | "regain";
  better: SimAction;
  other: SimAction;
  diff: number;
  ci95: [number, number];
}

export interface Recommendation {
  status: "recommend" | "no_clear_winner" | "inconclusive";
  action: SimAction | null;
  rule: string;
  reasons: string[];
}

export interface SimFrame {
  t: number;
  ball: Position;
  holder: string | null;
  players: { player_id: string; x: number; y: number }[];
}

export interface SampleRollout {
  action: SimAction;
  rollout_index: number;
  outcome: "danger" | "regain" | "neither";
  frames: SimFrame[];
  events: { t: number; kind: string; from_id: string | null; to_id: string }[];
}

export interface BranchInfo {
  frame_id: number;
  time_s: number;
  carrier: string;
  presser: string;
  cover: string;
  inside_option: string;
  overlap_runner: string | null;
  striker: string;
}

export interface ComparisonResult {
  run_id: string;
  scenario_id: string;
  dataset_hash: string;
  evidence_class: "simulated";
  policy_version: string;
  branch: BranchInfo;
  config: { cover_delay_s: number; attacker_policy: AttackerPolicy; rollouts: number; seed: number; horizon_s: number; execution_noise: number };
  actions: ActionResult[];
  diffs: PairedDiff[];
  recommendation: Recommendation;
  samples: SampleRollout[];
  assumptions: string[];
  compute_ms: number;
  cached: boolean;
}

export interface ChallengeCell {
  cover_delay_s: number;
  attacker_policy: AttackerPolicy;
  status: Recommendation["status"];
  action: SimAction | null;
  danger: Record<string, number>;
  regain: Record<string, number>;
}

export interface ChallengeResult {
  run_id: string;
  scenario_id: string;
  evidence_class: "simulated";
  policy_version: string;
  rollouts_per_action: number;
  baseline: ChallengeCell;
  cells: ChallengeCell[];
  changed: ChallengeCell[];
  tested_domain: string;
  conclusion: string;
  compute_ms: number;
}

// ---- investigations (agent workflow) ----

export type ClaimType = "observed" | "estimated" | "simulated" | "interpretation" | "insufficient_data";

export interface Claim {
  claim_type: ClaimType;
  text: string;
  fact_ids: string[];
}

export interface TraceStep {
  agent: string;
  kind: "model" | "tool" | "validation" | "repair" | "fallback" | "error" | "rule";
  summary: string;
  tool: string | null;
  duration_ms: number;
}

export interface InvestigationState {
  investigation_id: string;
  scenario_id: string;
  dataset_hash: string;
  cursor_s: number;
  question: string;
  audience: "casual" | "analyst";
  status: "queued" | "planning" | "evidence" | "challenging" | "producing" | "validating" | "complete" | "failed";
  outcome: "answered" | "unsupported" | "clarify" | "insufficient_data" | null;
  provider_mode: "offline" | "foundry" | "foundry_local" | "fallback";
  provider_label: string;
  model_deployment: string | null;
  intent: string | null;
  intent_label: string | null;
  plan_summary: string | null;
  facts: Fact[];
  simulation_run_ids: string[];
  challenge_summary: string | null;
  claims: Claim[];
  casual_claims: Claim[];
  rejected_claims: { claim: Claim; errors: string[] }[];
  notes: string[];
  errors: string[];
  trace: TraceStep[];
  model_calls: number;
  tool_calls: number;
  input_tokens: number | null;
  output_tokens: number | null;
  elapsed_ms: number;
}

// ---- recap and overlay export ----

export interface OverlayCue {
  schema_version: string;
  cue_id: string;
  source_run_id: string;
  scenario_hash: string;
  timebase: "sequence_s";
  branch: "recorded" | "simulated";
  start_s: number;
  duration_s: number;
  graphic_type: "player_spotlight" | "event_comparison" | "tradeoff_card" | "insufficient_data_card";
  title: string;
  body: string;
  language: string;
  audience: "casual" | "analyst";
  highlighted_player_ids: string[];
  fact_ids: string[];
  simulation_run_ids: string[];
  evidence_class: EvidenceClass | "interpretation";
  assumptions_summary: string | null;
  status: "approved";
}

export interface ExportBundle {
  schema_version: string;
  investigation_id: string;
  scenario_id: string;
  scenario_hash: string;
  question: string;
  audience: "casual" | "analyst";
  provider_mode: "offline" | "foundry" | "foundry_local" | "fallback";
  provider_label: string;
  timebase: "sequence_s";
  sequence_duration_s: number;
  playback_rate: number;
  recap_duration_s: number;
  insights: { order: number; claims: Claim[]; cue_id: string }[];
  cues: OverlayCue[];
  synthetic_data: true;
}
