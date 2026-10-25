"""Pure measurement functions. Inputs are plain values or schema objects; no I/O.

Method versions are recorded on every fact built from these functions. Bump the
version when a definition changes.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from app.schemas import MatchEvent, Position, TrackingFrame

METHOD_VERSIONS = {
    "pass_distance": "pass_distance/1",
    "pass_completion": "pass_completion/1",
    "possession_duration": "possession_duration/1",
    "tracked_running": "tracked_running/1",
    "defender_distance": "defender_distance/1",
    "lane_access": "lane_access/1",
    "open_lanes": "open_lanes/1",
    "final_third_share": "final_third_share/1",
    "transitions": "transitions/1",
    "response_time": "response_time/1",
}

# Lane-access heuristic constants (documented in docs/MODEL_CARD.md).
DEFENDER_SPEED = 7.0  # m/s, assumed closing speed
DEFENDER_REACTION = 0.25  # s, before a defender starts moving
DEFENDER_REACH = 1.0  # m, distance at which a defender can touch the ball
PASS_SPEED = 14.0  # m/s, assumed ground-pass speed
FINAL_THIRD_FROM = 70.0  # m from own goal line, in attacking-normalised x


def dist(a: Position | tuple[float, float], b: Position | tuple[float, float]) -> float:
    ax, ay = (a.x, a.y) if isinstance(a, Position) else a
    bx, by = (b.x, b.y) if isinstance(b, Position) else b
    return math.hypot(ax - bx, ay - by)


def pass_distance(e: MatchEvent) -> float | None:
    """Straight-line distance between recorded pass endpoints; None if the end is unknown."""
    if e.type != "pass" or e.end_position is None:
        return None
    return dist(e.start_position, e.end_position)


@dataclass(frozen=True)
class Completion:
    completed: int
    attempted: int  # passes with a known outcome
    unknown: int  # excluded from the denominator

    @property
    def rate(self) -> float | None:
        return self.completed / self.attempted if self.attempted else None


def pass_completion(passes: list[MatchEvent]) -> Completion:
    known = [p for p in passes if p.outcome is not None]
    return Completion(
        completed=sum(1 for p in known if p.outcome == "complete"),
        attempted=len(known),
        unknown=len(passes) - len(known),
    )


@dataclass(frozen=True)
class Running:
    distance_m: float
    top_speed_ms: float | None
    intervals_used: int
    intervals_expected: int
    gaps: int  # intervals skipped because they were longer than max_gap_s


class TrackingError(ValueError):
    pass


def tracked_running(
    frames: list[TrackingFrame], player_id: str, frame_rate_hz: float, max_gap_s: float | None = None
) -> Running:
    """Distance and top speed from consecutive samples of one player.

    Raises TrackingError on duplicate or non-increasing timestamps. Intervals
    longer than max_gap_s (default 1.5 sample periods) are not bridged.
    """
    dt_nominal = 1.0 / frame_rate_hz
    max_gap = max_gap_s if max_gap_s is not None else 1.5 * dt_nominal
    samples = []
    for f in frames:
        p = next((q for q in f.players if q.player_id == player_id and "x" in q.observed_fields), None)
        if p is not None:
            samples.append((f.time_s, p.x, p.y))
    total = 0.0
    top: float | None = None
    used = gaps = 0
    for (t0, x0, y0), (t1, x1, y1) in zip(samples, samples[1:]):
        dt = t1 - t0
        if dt <= 0:
            raise TrackingError(f"non-increasing timestamps at {t1}s")
        if dt > max_gap + 1e-9:
            gaps += 1
            continue
        d = math.hypot(x1 - x0, y1 - y0)
        total += d
        top = d / dt if top is None else max(top, d / dt)
        used += 1
    expected = round((frames[-1].time_s - frames[0].time_s) / dt_nominal) if len(frames) > 1 else 0
    return Running(distance_m=total, top_speed_ms=top, intervals_used=used, intervals_expected=expected, gaps=gaps)


@dataclass(frozen=True)
class PossessionSpell:
    team_id: str
    start_s: float
    end_s: float
    start_frame: int
    end_frame: int
    ended: bool  # False if still running at the end of the available data

    @property
    def duration_s(self) -> float:
        return self.end_s - self.start_s


def possession_spells(frames: list[TrackingFrame], team_of: dict[str, str]) -> list[PossessionSpell]:
    """Team possession spells from explicit possessor transitions.

    A spell starts on the first frame a team's player holds the ball and lasts,
    through loose-ball frames, until the first frame an opponent holds it.
    """
    spells: list[PossessionSpell] = []
    team: str | None = None
    start = start_f = None
    for f in frames:
        holder = f.ball.possession_player_id if f.ball else None
        if holder is None:
            continue
        t = team_of[holder]
        if team is None:
            team, start, start_f = t, f.time_s, f.frame_id
        elif t != team:
            spells.append(PossessionSpell(team, start, f.time_s, start_f, f.frame_id, True))  # type: ignore[arg-type]
            team, start, start_f = t, f.time_s, f.frame_id
    if team is not None and frames:
        spells.append(PossessionSpell(team, start, frames[-1].time_s, start_f, frames[-1].frame_id, False))  # type: ignore[arg-type]
    return spells


def point_segment(p: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> tuple[float, float]:
    """(distance from p to segment ab, fraction along ab of the closest point)."""
    ax, ay = a
    bx, by = b
    vx, vy = bx - ax, by - ay
    L2 = vx * vx + vy * vy
    k = 0.0 if L2 == 0 else max(0.0, min(1.0, ((p[0] - ax) * vx + (p[1] - ay) * vy) / L2))
    cx, cy = ax + k * vx, ay + k * vy
    return math.hypot(p[0] - cx, p[1] - cy), k


@dataclass(frozen=True)
class LaneAccess:
    defender_id: str
    distance_to_lane_m: float
    defender_time_s: float  # estimated time to reach the lane
    ball_time_s: float  # estimated time for a pass to reach that point
    margin_s: float  # ball_time - defender_time; positive means the defender gets there first


def lane_access(
    passer: tuple[float, float], receiver: tuple[float, float], defenders: dict[str, tuple[float, float]]
) -> list[LaneAccess]:
    """Prototype reachability heuristic for a straight ground pass, sorted most-threatening first.

    defender_time = reaction + max(0, distance_to_lane - reach) / defender_speed
    ball_time     = distance from passer to the closest lane point / pass_speed
    """
    lane_len = math.hypot(receiver[0] - passer[0], receiver[1] - passer[1])
    out = []
    for pid, pos in defenders.items():
        d, k = point_segment(pos, passer, receiver)
        d_time = DEFENDER_REACTION + max(0.0, d - DEFENDER_REACH) / DEFENDER_SPEED
        b_time = (k * lane_len) / PASS_SPEED
        out.append(LaneAccess(pid, d, d_time, b_time, b_time - d_time))
    return sorted(out, key=lambda la: -la.margin_s)


def lane_is_open(access: list[LaneAccess]) -> bool:
    return all(la.margin_s < 0 for la in access)


def normalised_x(x: float, direction: int, length: float) -> float:
    return x if direction > 0 else length - x
