import type { ReplayBundle } from "../api/types";

// Chart series read straight off recorded tracking frames (observed geometry).
// No smoothing or interpolation: one point per 10 Hz frame.

export interface Pair {
  key: string;
  a: string;
  b: string;
}

export function pairDistanceSeries(bundle: ReplayBundle, pairs: Pair[]): Record<string, number>[] {
  return bundle.frames.map((f) => {
    const pos = new Map(f.players.map((p) => [p.player_id, p]));
    const row: Record<string, number> = { t: f.time_s };
    for (const { key, a, b } of pairs) {
      const p = pos.get(a);
      const q = pos.get(b);
      if (p && q) row[key] = Math.round(Math.hypot(p.x - q.x, p.y - q.y) * 10) / 10;
    }
    return row;
  });
}

/** Frame-to-frame speed of one player, m/s. The first frame has no prior sample and is omitted. */
export function speedSeries(bundle: ReplayBundle, playerId: string): { t: number; speed: number }[] {
  const out: { t: number; speed: number }[] = [];
  for (let i = 1; i < bundle.frames.length; i++) {
    const f0 = bundle.frames[i - 1];
    const f1 = bundle.frames[i];
    const p = f0.players.find((x) => x.player_id === playerId);
    const q = f1.players.find((x) => x.player_id === playerId);
    const dt = f1.time_s - f0.time_s;
    if (p && q && dt > 0) out.push({ t: f1.time_s, speed: Math.round((Math.hypot(q.x - p.x, q.y - p.y) / dt) * 10) / 10 });
  }
  return out;
}

/** Pairs worth charting: each recorded pressure (presser → pressed carrier). */
export function pressurePairs(bundle: ReplayBundle, shortName: (id: string) => string): Pair[] {
  const seen = new Set<string>();
  const pairs: Pair[] = [];
  for (const e of bundle.events) {
    if (e.type !== "pressure_start" || !e.player_id || !e.related_player_ids[0]) continue;
    const id = `${e.player_id}>${e.related_player_ids[0]}`;
    if (seen.has(id)) continue;
    seen.add(id);
    pairs.push({ key: `${shortName(e.player_id)} → ${shortName(e.related_player_ids[0])}`, a: e.player_id, b: e.related_player_ids[0] });
  }
  return pairs;
}
