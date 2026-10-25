"""Physical and logical validity checks for a tracking + events fixture.

Returns a list of human-readable issues; an empty list means the fixture passed.
Thresholds are deliberately a little looser than the generator's own limits so
rounding to millimetres does not trip them.
"""

from __future__ import annotations

import math

from app.schemas import MatchEvent, ScenarioManifest, TrackingFrame

MAX_PLAYER_SPEED = 9.0  # m/s
MAX_PLAYER_ACCEL = 6.0  # m/s^2
MAX_BALL_SPEED = 35.0  # m/s
HELD_BALL_RADIUS = 1.0  # m
RECEPTION_RADIUS = 1.6  # m (receive radius + held offset)


def validate_fixture(manifest: ScenarioManifest, frames: list[TrackingFrame], events: list[MatchEvent]) -> list[str]:
    issues: list[str] = []
    L, W = manifest.pitch.length_m, manifest.pitch.width_m
    dt_expected = 1.0 / manifest.frame_rate_hz

    if len(frames) != manifest.frame_count:
        issues.append(f"frame_count {manifest.frame_count} != {len(frames)} frames")
    roster = {p.player_id for t in manifest.teams for p in t.players}

    prev: TrackingFrame | None = None
    prev_vel: dict[str, tuple[float, float]] = {}
    for f in frames:
        ids = {p.player_id for p in f.players}
        if ids != roster:
            issues.append(f"frame {f.frame_id}: player set differs from roster")
        for p in f.players:
            if not (0 <= p.x <= L and 0 <= p.y <= W):
                issues.append(f"frame {f.frame_id}: {p.player_id} out of bounds ({p.x}, {p.y})")
        if f.ball is not None:
            b = f.ball
            if not (0 <= b.x <= L and 0 <= b.y <= W):
                issues.append(f"frame {f.frame_id}: ball out of bounds")
            if b.possession_player_id is not None:
                holder = next((p for p in f.players if p.player_id == b.possession_player_id), None)
                if holder is None:
                    issues.append(f"frame {f.frame_id}: unknown possessor {b.possession_player_id}")
                elif math.dist((holder.x, holder.y), (b.x, b.y)) > HELD_BALL_RADIUS:
                    issues.append(f"frame {f.frame_id}: ball not at possessor {b.possession_player_id}")
        if prev is not None:
            dt = f.time_s - prev.time_s
            if dt <= 0:
                issues.append(f"frame {f.frame_id}: non-increasing timestamp")
                prev = f
                continue
            if abs(dt - dt_expected) > 1e-6:
                issues.append(f"frame {f.frame_id}: irregular interval {dt:.4f}s")
            prev_pos = {p.player_id: (p.x, p.y) for p in prev.players}
            for p in f.players:
                px, py = prev_pos[p.player_id]
                vx, vy = (p.x - px) / dt, (p.y - py) / dt
                if math.hypot(vx, vy) > MAX_PLAYER_SPEED:
                    issues.append(f"frame {f.frame_id}: {p.player_id} speed {math.hypot(vx, vy):.1f} m/s")
                if p.player_id in prev_vel:
                    pvx, pvy = prev_vel[p.player_id]
                    acc = math.hypot(vx - pvx, vy - pvy) / dt
                    if acc > MAX_PLAYER_ACCEL:
                        issues.append(f"frame {f.frame_id}: {p.player_id} accel {acc:.1f} m/s^2")
                prev_vel[p.player_id] = (vx, vy)
            if f.ball and prev.ball:
                bs = math.dist((f.ball.x, f.ball.y), (prev.ball.x, prev.ball.y)) / dt
                if bs > MAX_BALL_SPEED:
                    issues.append(f"frame {f.frame_id}: ball speed {bs:.1f} m/s")
        prev = f

    by_id = {f.frame_id: f for f in frames}
    times = [e.time_s for e in events]
    if times != sorted(times):
        issues.append("events are not time-ordered")
    if len({e.event_id for e in events}) != len(events):
        issues.append("duplicate event ids")

    for i, e in enumerate(events):
        for fid in e.related_frame_ids:
            if fid not in by_id:
                issues.append(f"{e.event_id}: unknown frame {fid}")
        if e.player_id is not None and e.player_id not in roster:
            issues.append(f"{e.event_id}: unknown player {e.player_id}")
        if e.type == "pass":
            rec = next((r for r in events[i + 1 :] if r.type == "reception"), None)
            if e.outcome == "complete" and (rec is None or rec.player_id != e.recipient_id):
                issues.append(f"{e.event_id}: completed pass without matching reception")
            if e.end_position is None:
                issues.append(f"{e.event_id}: pass without end position")
        if e.type == "reception":
            f = by_id.get(e.related_frame_ids[0])
            if f is not None and f.ball is not None:
                holder = next(p for p in f.players if p.player_id == e.player_id)
                if math.dist((holder.x, holder.y), (f.ball.x, f.ball.y)) > RECEPTION_RADIUS:
                    issues.append(f"{e.event_id}: receiver not at ball")

    # Possession may only change through a loose-ball phase, and each gain of
    # possession must be explained by an event on the preceding frame: a
    # reception by that player, or a saved shot (goalkeeper gathers).
    receptions = {(e.player_id, e.related_frame_ids[0]) for e in events if e.type == "reception"}
    saves = {e.related_frame_ids[-1] for e in events if e.type == "shot" and e.outcome == "saved"}
    prev_holder: str | None = frames[0].ball.possession_player_id if frames and frames[0].ball else None
    for f in frames[1:]:
        h = f.ball.possession_player_id if f.ball else None
        if h is not None and prev_holder is not None and h != prev_holder:
            issues.append(f"frame {f.frame_id}: possession jumped {prev_holder} -> {h} without a loose ball")
        if h is not None and prev_holder is None:
            if (h, f.frame_id - 1) not in receptions and (f.frame_id - 1) not in saves:
                issues.append(f"frame {f.frame_id}: {h} gained possession without a reception or save event")
        prev_holder = h
    return issues
