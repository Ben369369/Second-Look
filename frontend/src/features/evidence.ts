import type { Fact, ReplayBundle } from "../api/types";
import type { Annotation } from "../replay/PitchCanvas";

export const CLASS_CODE: Record<Fact["evidence_class"], string> = {
  observed: "OBS",
  estimated: "EST",
  simulated: "SIM",
};

export function formatValue(f: Fact): string {
  if (f.value === null) return "—";
  if (f.metric === "lane_access") return `${f.value > 0 ? "+" : ""}${f.value.toFixed(2)} s`;
  const n = Number.isInteger(f.value) ? String(f.value) : f.value.toFixed(1);
  // Ratio units ("of 9 outfield teammates") compress to "3 / 9"; the statement keeps the wording.
  const ratio = /^of (\d+)/.exec(f.unit);
  return ratio ? `${n} / ${ratio[1]}` : `${n} ${f.unit}`;
}

export const METRIC_LABEL: Record<string, string> = {
  pass_distance: "Pass distance",
  pass_completion: "Passes completed",
  possession_duration: "Possession spell",
  tracked_running: "Distance covered",
  defender_distance: "Defender distance",
  response_time: "Time to close down",
  lane_access: "Lane access",
  open_lanes: "Open passing lanes",
  final_third_share: "Final-third events",
  transitions: "Possession changes",
};

/** Telestration for a fact, drawn at the fact's focus moment. */
export function factAnnotation(f: Fact, bundle: ReplayBundle): Annotation | null {
  const [s0, s1, s2] = f.subject_ids;
  switch (f.metric) {
    case "defender_distance":
      return { lines: [{ from: s0, to: s1, style: "measure", label: `${f.value?.toFixed(1)} m` }], paths: [] };
    case "response_time":
      return { lines: [{ from: s0, to: s1, style: "measure" }], paths: [{ player_id: s0, start_s: f.time_window.start_s, end_s: f.time_window.end_s }] };
    case "open_lanes":
      return { lines: f.subject_ids.slice(1).map((m) => ({ from: s0, to: m, style: "lane" as const })), paths: [] };
    case "lane_access": {
      const frame = bundle.frames.find((fr) => Math.abs(fr.time_s - f.focus_time_s) < 1e-6);
      const pos = new Map(frame?.players.map((p) => [p.player_id, p]) ?? []);
      const a = pos.get(s0);
      const b = pos.get(s1);
      const d = pos.get(s2);
      if (!a || !b || !d) return null;
      const vx = b.x - a.x;
      const vy = b.y - a.y;
      const k = Math.max(0, Math.min(1, ((d.x - a.x) * vx + (d.y - a.y) * vy) / (vx * vx + vy * vy || 1)));
      return {
        lines: [
          { from: s0, to: s1, style: "lane" },
          { from: s2, to: { x: a.x + k * vx, y: a.y + k * vy }, style: "threat", label: formatValue(f) },
        ],
        paths: [],
      };
    }
    case "pass_distance": {
      const e = bundle.events.find((ev) => ev.event_id === f.source_event_ids[0]);
      if (!e?.end_position) return null;
      return { lines: [{ from: e.start_position, to: e.end_position, style: "measure", label: `${f.value?.toFixed(1)} m` }], paths: [] };
    }
    case "tracked_running":
      return { lines: [], paths: [{ player_id: s0, start_s: f.time_window.start_s, end_s: f.time_window.end_s }] };
    default:
      return null;
  }
}
