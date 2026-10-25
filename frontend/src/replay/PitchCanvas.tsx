import { useEffect, useRef, useState } from "react";
import type { ReplayBundle } from "../api/types";
import { type Lookup, type RenderState, stateAt } from "./model";

/** A point is either pitch coordinates or a player ID resolved to that player's current position. */
export type AnchorPoint = { x: number; y: number } | string;

export interface Annotation {
  lines: { from: AnchorPoint; to: AnchorPoint; style: "measure" | "lane" | "threat"; label?: string }[];
  paths: { player_id: string; start_s: number; end_s: number }[];
}

interface Props {
  bundle: ReplayBundle;
  lookup: Lookup;
  t: number;
  highlight: ReadonlySet<string>;
  annotation: Annotation | null;
  showGrid: boolean;
  /** Accessible description of what the canvas shows right now. */
  label: string;
}

const PAD_M = 2.5;
const TRAIL_S = 1.5;
const SIGNAL = "#f08c00"; // highlight / measurement
const LANE = "#1b2a5e";
const THREAT = "#e03131";
const INK = "#1b2a5e";
const LINE = "#b3c0d4";

type Map2 = { sx: (x: number) => number; sy: (y: number) => number; scale: number };

export function PitchCanvas({ bundle, lookup, t, highlight, annotation, showGrid, label }: Props) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [box, setBox] = useState({ w: 800, h: 520 });
  const { length_m: L, width_m: W } = bundle.manifest.pitch;

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      setBox({ w: Math.max(280, Math.floor(width)), h: Math.max(180, Math.floor(height)) });
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Fit the pitch inside the pane, preserving aspect ratio.
  const aspect = (W + 2 * PAD_M) / (L + 2 * PAD_M);
  const width = Math.min(box.w, Math.floor(box.h / aspect));
  const height = Math.round(width * aspect);

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.round(width * dpr);
    canvas.height = Math.round(height * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const scale = width / (L + 2 * PAD_M);
    // Data y runs 0..W from the bottom touchline; screen y runs downward.
    const m: Map2 = { sx: (x) => (x + PAD_M) * scale, sy: (y) => (W - y + PAD_M) * scale, scale };
    const state = stateAt(bundle.frames, t);
    drawPitch(ctx, width, height, m, L, W, showGrid);
    if (annotation) drawPaths(ctx, bundle, annotation, t, m);
    drawBallTrail(ctx, bundle, t, m);
    if (annotation) drawLines(ctx, annotation, state, m);
    drawPlayers(ctx, state, lookup, highlight, m);
  }, [bundle, lookup, t, highlight, annotation, showGrid, width, height, L, W]);

  return (
    <div ref={wrapRef} className="pitch-wrap">
      <canvas
        ref={canvasRef}
        style={{ width: `${width}px`, height: `${height}px` }}
        role="img"
        aria-label={label}
        data-testid="pitch-canvas"
      />
    </div>
  );
}

function drawPitch(ctx: CanvasRenderingContext2D, w: number, h: number, m: Map2, L: number, W: number, grid: boolean) {
  const { sx, sy, scale } = m;
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, w, h);
  ctx.fillStyle = "#f1f5f2";
  ctx.fillRect(sx(0), sy(W), L * scale, W * scale);
  // Mowing stripes, very faint.
  ctx.fillStyle = "#e9f0eb";
  for (let i = 0; i < 14; i += 2) ctx.fillRect(sx((i * L) / 14), sy(W), (L / 14) * scale, W * scale);
  if (grid) {
    ctx.strokeStyle = "rgba(27, 42, 94, 0.07)";
    ctx.lineWidth = 1;
    for (let x = 5; x < L; x += 5) {
      ctx.beginPath();
      ctx.moveTo(Math.round(sx(x)) + 0.5, sy(W));
      ctx.lineTo(Math.round(sx(x)) + 0.5, sy(0));
      ctx.stroke();
    }
    for (let y = 4; y < W; y += 5) {
      ctx.beginPath();
      ctx.moveTo(sx(0), Math.round(sy(y)) + 0.5);
      ctx.lineTo(sx(L), Math.round(sy(y)) + 0.5);
      ctx.stroke();
    }
    // Thirds, in each team's frame of reference.
    ctx.setLineDash([3, 4]);
    ctx.strokeStyle = "rgba(27, 42, 94, 0.18)";
    for (const x of [35, 70]) {
      ctx.beginPath();
      ctx.moveTo(sx(x), sy(W));
      ctx.lineTo(sx(x), sy(0));
      ctx.stroke();
    }
    ctx.setLineDash([]);
  }
  ctx.strokeStyle = LINE;
  ctx.lineWidth = 1.25;
  const rect = (x0: number, y0: number, x1: number, y1: number) =>
    ctx.strokeRect(sx(x0), sy(y1), (x1 - x0) * scale, (y1 - y0) * scale);
  rect(0, 0, L, W);
  ctx.beginPath();
  ctx.moveTo(sx(L / 2), sy(0));
  ctx.lineTo(sx(L / 2), sy(W));
  ctx.stroke();
  ctx.beginPath();
  ctx.arc(sx(L / 2), sy(W / 2), 9.15 * scale, 0, Math.PI * 2);
  ctx.stroke();
  const spot = (x: number, y: number) => {
    ctx.fillStyle = LINE;
    ctx.fillRect(sx(x) - 1.5, sy(y) - 1.5, 3, 3);
  };
  spot(L / 2, W / 2);
  for (const side of [0, 1] as const) {
    const gx = side === 0 ? 0 : L;
    const dir = side === 0 ? 1 : -1;
    rect(Math.min(gx, gx + dir * 16.5), W / 2 - 20.16, Math.max(gx, gx + dir * 16.5), W / 2 + 20.16);
    rect(Math.min(gx, gx + dir * 5.5), W / 2 - 9.16, Math.max(gx, gx + dir * 5.5), W / 2 + 9.16);
    spot(gx + dir * 11, W / 2);
    const a = Math.acos(5.5 / 9.15);
    ctx.beginPath();
    if (side === 0) ctx.arc(sx(gx + 11), sy(W / 2), 9.15 * scale, -a, a);
    else ctx.arc(sx(gx - 11), sy(W / 2), 9.15 * scale, Math.PI - a, Math.PI + a);
    ctx.stroke();
    ctx.strokeRect(side === 0 ? sx(-1.5) : sx(L), sy(W / 2 + 3.66), 1.5 * scale, 7.32 * scale);
  }
  // Axis ticks every 10 m along the bottom edge.
  ctx.fillStyle = "#8a97ab";
  ctx.font = "500 9px system-ui, sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "top";
  for (let x = 0; x <= L; x += 10) ctx.fillText(String(x), sx(x), sy(0) + 3);
}

function drawBallTrail(ctx: CanvasRenderingContext2D, bundle: ReplayBundle, t: number, m: Map2) {
  const pts = bundle.frames.filter((f) => f.ball && f.time_s <= t && f.time_s >= t - TRAIL_S);
  if (pts.length < 2) return;
  ctx.strokeStyle = "rgba(27, 42, 94, 0.45)";
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  pts.forEach((f, i) => (i ? ctx.lineTo(m.sx(f.ball!.x), m.sy(f.ball!.y)) : ctx.moveTo(m.sx(f.ball!.x), m.sy(f.ball!.y))));
  ctx.stroke();
}

function drawPaths(ctx: CanvasRenderingContext2D, bundle: ReplayBundle, a: Annotation, t: number, m: Map2) {
  for (const p of a.paths) {
    const pts = bundle.frames
      .filter((f) => f.time_s >= p.start_s && f.time_s <= Math.min(p.end_s, t))
      .map((f) => f.players.find((q) => q.player_id === p.player_id))
      .filter((q) => q !== undefined);
    if (pts.length < 2) continue;
    ctx.strokeStyle = "rgba(240, 140, 0, 0.85)";
    ctx.lineWidth = 2;
    ctx.beginPath();
    pts.forEach((q, i) => (i ? ctx.lineTo(m.sx(q.x), m.sy(q.y)) : ctx.moveTo(m.sx(q.x), m.sy(q.y))));
    ctx.stroke();
  }
}

function drawLines(ctx: CanvasRenderingContext2D, a: Annotation, state: RenderState, m: Map2) {
  const pos = new Map(state.players.map((p) => [p.player_id, p]));
  const resolve = (pt: AnchorPoint) => (typeof pt === "string" ? pos.get(pt) : pt);
  for (const line of a.lines) {
    const p = resolve(line.from);
    const q = resolve(line.to);
    if (!p || !q) continue;
    const x0 = m.sx(p.x);
    const y0 = m.sy(p.y);
    const x1 = m.sx(q.x);
    const y1 = m.sy(q.y);
    const color = line.style === "threat" ? THREAT : line.style === "lane" ? LANE : SIGNAL;
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.setLineDash(line.style === "lane" ? [6, 4] : line.style === "threat" ? [2, 3] : []);
    ctx.beginPath();
    ctx.moveTo(x0, y0);
    ctx.lineTo(x1, y1);
    ctx.stroke();
    ctx.setLineDash([]);
    // Short lines would hide their label under player markers; the caption carries the value.
    if (line.label && Math.hypot(x1 - x0, y1 - y0) >= 60) {
      ctx.font = "600 11px system-ui, sans-serif";
      const tw = ctx.measureText(line.label).width + 10;
      const mx = (x0 + x1) / 2;
      const my = (y0 + y1) / 2;
      ctx.fillStyle = "#ffffff";
      ctx.fillRect(mx - tw / 2, my - 9, tw, 18);
      ctx.lineWidth = 1;
      ctx.strokeRect(mx - tw / 2, my - 9, tw, 18);
      ctx.fillStyle = color;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(line.label, mx, my + 0.5);
    }
  }
}

function drawPlayers(ctx: CanvasRenderingContext2D, state: RenderState, lookup: Lookup, highlight: ReadonlySet<string>, m: Map2) {
  const r = Math.max(7, 0.95 * m.scale);
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  const labels: { x: number; y: number; text: string }[] = [];
  for (const p of state.players) {
    const team = lookup.teams.get(p.team_id);
    const player = lookup.players.get(p.player_id);
    const x = m.sx(p.x);
    const y = m.sy(p.y);
    const hot = highlight.has(p.player_id);
    const dim = highlight.size > 0 && !hot;
    ctx.globalAlpha = dim ? 0.6 : 1;
    ctx.beginPath();
    if (team?.marker_shape === "square") ctx.rect(x - r, y - r, 2 * r, 2 * r);
    else ctx.arc(x, y, r, 0, Math.PI * 2);
    ctx.fillStyle = team?.color ?? "#999";
    ctx.fill();
    const onBall = state.possession === p.player_id;
    ctx.lineWidth = hot || onBall ? 2.5 : 1.5;
    ctx.strokeStyle = hot || onBall ? SIGNAL : "#ffffff";
    ctx.stroke();
    ctx.fillStyle = "#ffffff";
    ctx.font = `600 ${Math.round(r * 1.0)}px system-ui, sans-serif`;
    ctx.fillText(String(player?.number ?? "?"), x, y + 0.5);
    ctx.globalAlpha = 1;
    if (hot && player) labels.push({ x, y, text: `${player.number} ${player.name.split(" ").slice(-1)[0].toUpperCase()}` });
  }
  if (state.ball) {
    ctx.beginPath();
    ctx.arc(m.sx(state.ball.x), m.sy(state.ball.y), Math.max(3.5, 0.38 * m.scale), 0, Math.PI * 2);
    ctx.fillStyle = "#ffffff";
    ctx.fill();
    ctx.lineWidth = 1.75;
    ctx.strokeStyle = INK;
    ctx.stroke();
  }
  drawLabels(ctx, labels, r);
}

/** Name tags for highlighted players, placed to avoid each other and the markers they label. */
function drawLabels(ctx: CanvasRenderingContext2D, labels: { x: number; y: number; text: string }[], r: number) {
  ctx.font = "600 11px system-ui, sans-serif";
  const h = 17;
  const placed = labels.map(({ x, y }) => ({ x0: x - r, y0: y - r, x1: x + r, y1: y + r }));
  const overlaps = (a: (typeof placed)[number]) => placed.some((b) => a.x0 < b.x1 && b.x0 < a.x1 && a.y0 < b.y1 && b.y0 < a.y1);
  for (const { x, y, text } of labels) {
    const w = ctx.measureText(text).width + 8;
    const candidates = [
      { cx: x, cy: y - r - 11 },
      { cx: x, cy: y + r + 11 },
      { cx: x + r + 5 + w / 2, cy: y },
      { cx: x - r - 5 - w / 2, cy: y },
    ].map(({ cx, cy }) => ({ cx, cy, box: { x0: cx - w / 2, y0: cy - h / 2, x1: cx + w / 2, y1: cy + h / 2 } }));
    const pick = candidates.find((c) => !overlaps(c.box)) ?? candidates[0];
    placed.push(pick.box);
    ctx.fillStyle = INK;
    ctx.fillRect(pick.box.x0, pick.box.y0, w, h);
    ctx.fillStyle = "#ffffff";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(text, pick.cx, pick.cy + 0.5);
  }
}
