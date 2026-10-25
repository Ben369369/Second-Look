import type { MatchEvent, Player, ReplayBundle, Team, TrackingFrame } from "../api/types";

/** Index of the last recorded frame at or before t, and the blend toward the next one. */
export function frameCursor(frames: TrackingFrame[], t: number): { index: number; alpha: number } {
  if (frames.length === 0) return { index: 0, alpha: 0 };
  if (t <= frames[0].time_s) return { index: 0, alpha: 0 };
  const last = frames.length - 1;
  if (t >= frames[last].time_s) return { index: last, alpha: 0 };
  let lo = 0;
  let hi = last;
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    if (frames[mid].time_s <= t) lo = mid;
    else hi = mid;
  }
  const span = frames[hi].time_s - frames[lo].time_s;
  return { index: lo, alpha: span > 0 ? (t - frames[lo].time_s) / span : 0 };
}

export interface RenderPlayer {
  player_id: string;
  team_id: string;
  x: number;
  y: number;
}

export interface RenderState {
  frameIndex: number;
  ball: { x: number; y: number } | null;
  possession: string | null;
  players: RenderPlayer[];
}

const lerp = (a: number, b: number, k: number) => a + (b - a) * k;

/**
 * Display-rate state between two recorded frames. Interpolated positions are a
 * rendering aid only; they are not observations. Possession is taken from the
 * recorded frame at or before t, never interpolated.
 */
export function stateAt(frames: TrackingFrame[], t: number): RenderState {
  const { index, alpha } = frameCursor(frames, t);
  const a = frames[index];
  const b = frames[Math.min(index + 1, frames.length - 1)];
  const bPos = new Map(b.players.map((p) => [p.player_id, p]));
  return {
    frameIndex: index,
    possession: a.ball?.possession_player_id ?? null,
    ball: a.ball && b.ball ? { x: lerp(a.ball.x, b.ball.x, alpha), y: lerp(a.ball.y, b.ball.y, alpha) } : null,
    players: a.players.map((p) => {
      const q = bPos.get(p.player_id) ?? p;
      return { player_id: p.player_id, team_id: p.team_id, x: lerp(p.x, q.x, alpha), y: lerp(p.y, q.y, alpha) };
    }),
  };
}

export function formatClock(totalSeconds: number): string {
  const s = Math.max(0, Math.floor(totalSeconds + 1e-6));
  const m = Math.floor(s / 60);
  return `${String(m).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

export interface Lookup {
  players: Map<string, Player>;
  teams: Map<string, Team>;
}

export function buildLookup(bundle: ReplayBundle): Lookup {
  const teams = new Map(bundle.manifest.teams.map((t) => [t.team_id, t]));
  const players = new Map(bundle.manifest.teams.flatMap((t) => t.players.map((p) => [p.player_id, p] as const)));
  return { players, teams };
}

export function playerLabel(lookup: Lookup, id: string | null): string {
  if (!id) return "unknown player";
  const p = lookup.players.get(id);
  if (!p) return id;
  const team = lookup.teams.get(p.team_id)?.name ?? p.team_id;
  return `${team} #${p.number} ${p.name}`;
}

export function shortPlayer(lookup: Lookup, id: string | null): string {
  const p = id ? lookup.players.get(id) : undefined;
  return p ? `#${p.number} ${p.name.split(" ").slice(-1)[0]}` : (id ?? "?");
}

const TYPE_LABEL: Record<MatchEvent["type"], string> = {
  pass: "Pass",
  reception: "Reception",
  carry: "Carry",
  shot: "Shot",
  tackle: "Tackle",
  interception: "Interception",
  turnover: "Turnover",
  pressure_start: "Pressure on",
  pressure_end: "Pressure off",
  stoppage: "Stoppage",
};

export function describeEvent(lookup: Lookup, e: MatchEvent): string {
  const who = shortPlayer(lookup, e.player_id);
  switch (e.type) {
    case "pass":
      return `${who} → ${shortPlayer(lookup, e.recipient_id)}${e.outcome ? ` (${e.outcome})` : ""}`;
    case "pressure_start":
    case "pressure_end":
      return `${who} on ${shortPlayer(lookup, e.related_player_ids[0] ?? null)}`;
    case "shot":
      return `${who}${e.outcome ? ` — ${e.outcome}` : ""}`;
    default:
      return who;
  }
}

export const eventTypeLabel = (e: MatchEvent) => TYPE_LABEL[e.type];

/** Player IDs an event concerns, for highlighting. */
export function eventPlayers(e: MatchEvent): string[] {
  return [e.player_id, e.recipient_id, ...e.related_player_ids].filter((x): x is string => !!x);
}
