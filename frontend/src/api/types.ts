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
  provider_mode: "offline" | "foundry";
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
