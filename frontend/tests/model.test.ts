import { describe, expect, it } from "vitest";
import type { TrackingFrame } from "../src/api/types";
import { formatClock, frameCursor, stateAt } from "../src/replay/model";

const frame = (id: number, t: number, x: number, holder: string | null): TrackingFrame => ({
  frame_id: id,
  time_s: t,
  ball: { x, y: 10, z: 0, vx: 0, vy: 0, possession_player_id: holder },
  players: [{ player_id: "P", team_id: "A", x, y: 20, vx: 0, vy: 0, observed_fields: ["x", "y"] }],
});

const frames = [frame(0, 0, 0, "P"), frame(1, 0.1, 1, null), frame(2, 0.2, 3, null)];

describe("frameCursor", () => {
  it("clamps before the first and after the last frame", () => {
    expect(frameCursor(frames, -1)).toEqual({ index: 0, alpha: 0 });
    expect(frameCursor(frames, 5)).toEqual({ index: 2, alpha: 0 });
  });

  it("finds the frame at or before t and the blend factor", () => {
    const c = frameCursor(frames, 0.15);
    expect(c.index).toBe(1);
    expect(c.alpha).toBeCloseTo(0.5);
    expect(frameCursor(frames, 0.1)).toEqual({ index: 1, alpha: 0 });
  });
});

describe("stateAt", () => {
  it("interpolates positions between recorded frames", () => {
    const s = stateAt(frames, 0.15);
    expect(s.players[0].x).toBeCloseTo(2);
    expect(s.ball?.x).toBeCloseTo(2);
  });

  it("takes possession from the recorded frame, never interpolated", () => {
    expect(stateAt(frames, 0.05).possession).toBe("P");
    expect(stateAt(frames, 0.1).possession).toBeNull();
  });
});

describe("formatClock", () => {
  it("formats match minutes and seconds", () => {
    expect(formatClock(63 * 60 + 12)).toBe("63:12");
    expect(formatClock(63 * 60 + 12 + 7.9)).toBe("63:19");
    expect(formatClock(5)).toBe("00:05");
  });
});
