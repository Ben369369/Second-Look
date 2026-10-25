"""Seeded synthetic sequence generator.

The generator steps a small kinematic simulation at 10 Hz. Players steer toward
role/policy targets under speed and acceleration limits; the ball is either held
(follows the carrier), in flight (ground pass/shot at constant speed toward a
meeting point), or done. Events are emitted from state transitions inside the
loop, so tracking and events cannot independently contradict each other.

Conventions (see docs/DATA_CARD.md):
- Pitch 105 x 68 m, x along length, y across width, origin at a corner.
- Period 2: Harbor FC attacks +x, Cedar FC attacks -x (defends the x=105 goal).
- Cedar's right flank and Harbor's left flank are both at high y.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from app.schemas import SCHEMA_VERSION

GENERATOR_VERSION = "0.1.0"

PITCH_L = 105.0
PITCH_W = 68.0
FRAME_RATE = 10
DT = 1.0 / FRAME_RATE
MAX_ACCEL = 4.5  # m/s^2, players (accel and decel)
CARRY_SPEED = 6.0  # m/s, max speed while dribbling
RECEIVE_RADIUS = 1.0  # m, recipient must be this close to a stopped/arriving ball
BALL_HOLD_OFFSET = 0.5  # m ahead of carrier in the team's attacking direction
PRESSURE_ON = 3.0  # m, pressure_start threshold
PRESSURE_OFF = 4.0  # m, pressure_end threshold (hysteresis)
MAX_RECEPTION_WAIT_S = 3.0

CEDAR = "CED"
HARBOR = "HAR"
ATTACK_DIR = {HARBOR: 1.0, CEDAR: -1.0}
CEDAR_GOAL = np.array([PITCH_L, PITCH_W / 2])

# (player_id, team, number, name, role, home x, home y) — fictional people.
ROSTER: list[tuple[str, str, int, str, str, float, float]] = [
    ("CED-01", CEDAR, 1, "T. Achieng", "GK", 101.0, 34.0),
    ("CED-02", CEDAR, 2, "R. Halvorsen", "RB", 76.0, 55.0),
    ("CED-03", CEDAR, 3, "D. Mensah", "LB", 76.0, 13.0),
    ("CED-04", CEDAR, 4, "K. Oduya", "RCB", 82.0, 41.0),
    ("CED-05", CEDAR, 5, "L. Brandt", "LCB", 82.0, 27.0),
    ("CED-06", CEDAR, 6, "S. Kamau", "RCM", 70.0, 41.0),
    ("CED-08", CEDAR, 8, "P. Ferreira", "LCM", 70.0, 27.0),
    ("CED-07", CEDAR, 7, "J. Wanjiru", "RM", 66.0, 58.0),
    ("CED-11", CEDAR, 11, "M. Novak", "LM", 66.0, 10.0),
    ("CED-09", CEDAR, 9, "E. Otieno", "ST", 56.0, 38.0),
    ("CED-10", CEDAR, 10, "A. Lindqvist", "ST", 56.0, 29.0),
    ("HAR-01", HARBOR, 1, "B. Castell", "GK", 8.0, 34.0),
    ("HAR-02", HARBOR, 2, "N. Abara", "RB", 36.0, 8.0),
    ("HAR-03", HARBOR, 3, "I. Morrow", "LB", 36.0, 60.0),
    ("HAR-04", HARBOR, 4, "G. Pellerin", "LCB", 28.0, 44.0),
    ("HAR-05", HARBOR, 5, "O. Nyambura", "RCB", 28.0, 24.0),
    ("HAR-06", HARBOR, 6, "C. Duarte", "DM", 40.0, 34.0),
    ("HAR-08", HARBOR, 8, "F. Kiprono", "LCM", 50.0, 45.0),
    ("HAR-10", HARBOR, 10, "Y. Sato", "RCM", 52.0, 23.0),
    ("HAR-11", HARBOR, 11, "V. Rossi", "LW", 58.0, 62.0),
    ("HAR-07", HARBOR, 7, "H. Mbeki", "RW", 62.0, 7.0),
    ("HAR-09", HARBOR, 9, "W. Grant", "ST", 68.0, 34.0),
]

TEAM_META = {
    CEDAR: {"name": "Cedar FC", "short_name": "CED", "color": "#1e3a8a", "marker_shape": "circle"},
    HARBOR: {"name": "Harbor FC", "short_name": "HAR", "color": "#e03131", "marker_shape": "square"},
}


@dataclass(frozen=True)
class HeroConfig:
    """Parameters for the right-back pressing sequence family."""

    scenario_id: str = "rb_press_hero"
    seed: int = 20261025
    title: str = "Right flank build-up, 63rd minute"
    description: str = (
        "Harbor FC build down their left. Cedar FC's right-back (#2) holds off the "
        "winger before pressing; the winger finds the inside midfielder and the move "
        "ends in a saved shot."
    )
    rb_press_delay_s: float = 1.4  # after the winger's reception
    cover_delay_s: float | None = None  # None: covering midfielder stays zonal
    match_clock_offset_s: float = 63 * 60 + 12.0
    duration_cap_s: float = 30.0


# ---------------------------------------------------------------------------
# Ball script: the attacking side's on-ball plan. Off-ball behavior and all
# defending behavior come from policies, so defenders react to the ball.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Carry:
    player: str
    to: tuple[float, float] | None
    duration_s: float


@dataclass(frozen=True)
class Pass:
    passer: str
    recipient: str
    meet: tuple[float, float]


@dataclass(frozen=True)
class Shot:
    player: str


HERO_SCRIPT: list[Carry | Pass | Shot] = [
    Carry("HAR-05", (30.0, 26.0), 1.2),
    Pass("HAR-05", "HAR-06", (38.5, 32.5)),
    Carry("HAR-06", (40.5, 35.5), 1.0),
    Pass("HAR-06", "HAR-04", (31.5, 45.0)),
    Carry("HAR-04", (34.0, 46.0), 1.0),
    Pass("HAR-04", "HAR-03", (40.0, 59.0)),
    Carry("HAR-03", (47.0, 61.5), 2.4),
    Pass("HAR-03", "HAR-11", (57.5, 63.5)),
    Carry("HAR-11", (62.0, 60.5), 2.2),
    Pass("HAR-11", "HAR-08", (64.5, 48.0)),
    Carry("HAR-08", (72.0, 43.5), 1.6),
    Pass("HAR-08", "HAR-09", (86.0, 37.5)),
    Carry("HAR-09", (90.5, 36.0), 1.0),
    Shot("HAR-09"),
    Carry("CED-01", None, 2.5),
]


@dataclass
class Agent:
    player_id: str
    team: str
    number: int
    name: str
    role: str
    home: np.ndarray
    pos: np.ndarray
    vel: np.ndarray
    max_speed: float


@dataclass
class Flight:
    kind: str  # "pass" | "shot"
    passer: str
    recipient: str
    target: np.ndarray
    speed: float
    event_index: int


@dataclass
class SimState:
    t: float = 0.0
    mode: str = "held"  # held | flight
    carrier: str | None = None
    carrier_since: float = 0.0
    carry_start: np.ndarray | None = None
    flight: Flight | None = None
    flight_arrived_at: float | None = None
    script_idx: int = 0
    receptions: dict[str, float] = field(default_factory=dict)
    released: dict[str, float] = field(default_factory=dict)
    shot_taken_at: float | None = None
    pressure: tuple[str, str, int] | None = None  # (presser, carrier, start frame)


def _unit(v: np.ndarray) -> np.ndarray:
    n = float(np.linalg.norm(v))
    return v / n if n > 1e-9 else np.zeros(2)


def _clamp_pitch(p: np.ndarray, margin: float = 0.5) -> np.ndarray:
    return np.array([min(max(p[0], margin), PITCH_L - margin), min(max(p[1], margin), PITCH_W - margin)])


class HeroGenerator:
    def __init__(self, cfg: HeroConfig, script: list[Carry | Pass | Shot] | None = None):
        self.cfg = cfg
        self.script = script or HERO_SCRIPT
        self.rng = np.random.default_rng(cfg.seed)
        self.agents: dict[str, Agent] = {}
        for pid, team, num, name, role, hx, hy in ROSTER:
            jitter = self.rng.uniform(-0.8, 0.8, size=2)
            home = np.array([hx, hy]) + jitter
            self.agents[pid] = Agent(
                player_id=pid,
                team=team,
                number=num,
                name=name,
                role=role,
                home=home,
                pos=home.copy(),
                vel=np.zeros(2),
                max_speed=float(self.rng.uniform(7.0, 8.0)) if role != "GK" else 6.0,
            )
        # Per-pass meeting point jitter and speeds are drawn up front so the
        # random stream does not depend on loop timing.
        self.meet_jitter = [self.rng.uniform(-0.6, 0.6, size=2) for _ in self.script]
        self.pass_speed = [float(self.rng.uniform(13.0, 16.0)) for _ in self.script]
        self.state = SimState()
        self.ball = np.zeros(2)
        self.ball_vel = np.zeros(2)
        self.frames: list[dict] = []
        self.raw_events: list[dict] = []

    # -- shape --------------------------------------------------------------

    def _formation_target(self, a: Agent) -> np.ndarray:
        bx, by = self.ball
        if a.role == "GK":
            if a.team == CEDAR:
                return np.array([101.5, 34.0 + 0.25 * (by - 34.0)])
            return np.array([8.0 + 0.1 * (bx - 30.0), 34.0 + 0.2 * (by - 34.0)])
        if a.team == CEDAR:
            dx = float(np.clip(0.35 * (bx - 52.5), -10.0, 10.0))
            dy = 0.3 * (by - 34.0)
        else:
            dx = float(np.clip(0.45 * (bx - 40.0), -5.0, 22.0))
            dy = 0.15 * (by - 34.0)
        return _clamp_pitch(a.home + np.array([dx, dy]), margin=1.0)

    # -- policies -----------------------------------------------------------

    def _goal_side(self, of: np.ndarray, dist: float) -> np.ndarray:
        return of + dist * _unit(CEDAR_GOAL - of)

    def _target(self, a: Agent) -> np.ndarray:
        s = self.state
        t = s.t
        pid = a.player_id

        # The intended recipient of a ball in flight runs to the meeting point.
        if s.mode == "flight" and s.flight and pid == s.flight.recipient:
            return s.flight.target
        if s.mode == "held" and pid == s.carrier:
            step = self.script[s.script_idx] if s.script_idx < len(self.script) else None
            if isinstance(step, Carry) and step.player == pid and step.to is not None:
                return np.array(step.to)
            return a.pos.copy()

        carrier = self.agents[s.carrier] if (s.mode == "held" and s.carrier) else None
        r_w = s.receptions.get("HAR-11")
        r_8 = s.receptions.get("HAR-08")

        if pid == "CED-02":  # right-back: hold off the winger, then press
            if carrier is not None and carrier.player_id == "HAR-11" and r_w is not None:
                if t >= r_w + self.cfg.rb_press_delay_s:
                    return self._goal_side(carrier.pos, 1.0)
                return self._goal_side(carrier.pos, 6.5)
            winger = self.agents["HAR-11"]
            if winger.pos[1] > 50.0 and "HAR-11" not in s.released:
                return self._goal_side(winger.pos, 8.0)
        if pid == "CED-06":  # covering midfielder
            if carrier is not None and carrier.player_id == "HAR-08" and r_8 is not None and t >= r_8 + 0.5:
                return self._goal_side(carrier.pos, 1.0)
            if (
                self.cfg.cover_delay_s is not None
                and r_w is not None
                and t >= r_w + self.cfg.cover_delay_s
                and "HAR-11" not in s.released
            ):
                w, m = self.agents["HAR-11"].pos, self.agents["HAR-08"].pos
                return w + 0.6 * (m - w)
        if pid == "CED-04" and r_8 is not None:  # right centre-back tracks the striker's run
            return self._goal_side(self.agents["HAR-09"].pos, 2.0) + np.array([0.0, 1.5])
        if pid == "CED-01" and s.mode == "flight" and s.flight and s.flight.kind == "shot":
            return s.flight.target

        if pid == "HAR-08" and r_w is not None and "HAR-08" not in s.receptions:
            return np.array([64.5, 48.0])
        if pid == "HAR-08" and "HAR-08" in s.released:
            return np.array([80.0, 47.0])
        if pid == "HAR-03" and r_w is not None:  # overlapping decoy run
            return np.array([68.0, 64.5])
        if pid == "HAR-09" and r_8 is not None and "HAR-09" not in s.receptions:
            return np.array([86.0, 37.5])
        return self._formation_target(a)

    # -- kinematics ---------------------------------------------------------

    def _steer(self, a: Agent, target: np.ndarray) -> None:
        to = target - a.pos
        dist = float(np.linalg.norm(to))
        vmax = CARRY_SPEED if (self.state.mode == "held" and self.state.carrier == a.player_id) else a.max_speed
        if dist < 0.15:
            desired = np.zeros(2)
        else:
            speed = min(vmax, math.sqrt(2.0 * MAX_ACCEL * 0.8 * dist))
            desired = _unit(to) * speed
        dv = desired - a.vel
        dv_n = float(np.linalg.norm(dv))
        if dv_n > MAX_ACCEL * DT:
            dv = dv * (MAX_ACCEL * DT / dv_n)
        a.vel = a.vel + dv
        sp = float(np.linalg.norm(a.vel))
        if sp > vmax:
            a.vel = a.vel * (vmax / sp)
        new_pos = _clamp_pitch(a.pos + a.vel * DT)
        a.vel = (new_pos - a.pos) / DT
        a.pos = new_pos

    def _held_ball_pos(self, carrier: Agent) -> np.ndarray:
        return carrier.pos + np.array([ATTACK_DIR[carrier.team] * BALL_HOLD_OFFSET, 0.0])

    # -- events -------------------------------------------------------------

    def _frame_index(self) -> int:
        return len(self.frames) - 1

    def _emit(self, **kw) -> int:
        kw.setdefault("player_id", None)
        kw.setdefault("recipient_id", None)
        kw.setdefault("end_position", None)
        kw.setdefault("outcome", None)
        kw.setdefault("related_player_ids", [])
        kw.setdefault("related_frame_ids", [self._frame_index()])
        kw["time_s"] = round(kw["time_s"], 2)
        kw["start_position"] = {"x": round(float(kw["start_position"][0]), 2), "y": round(float(kw["start_position"][1]), 2)}
        if kw["end_position"] is not None:
            kw["end_position"] = {"x": round(float(kw["end_position"][0]), 2), "y": round(float(kw["end_position"][1]), 2)}
        self.raw_events.append(kw)
        return len(self.raw_events) - 1

    def _gain_possession(self, pid: str) -> None:
        s = self.state
        s.mode = "held"
        s.carrier = pid
        s.carrier_since = s.t
        s.carry_start = self.agents[pid].pos.copy()
        s.receptions[pid] = s.t
        s.flight = None
        s.flight_arrived_at = None
        s.script_idx += 1  # the pass/shot step is complete

    def _release(self) -> tuple[Agent, np.ndarray]:
        """Close the carry (if any) when the carrier plays the ball."""
        s = self.state
        carrier = self.agents[s.carrier]  # type: ignore[index]
        if s.carry_start is not None and float(np.linalg.norm(carrier.pos - s.carry_start)) >= 1.0:
            start_frame = round(s.carrier_since * FRAME_RATE)
            self._emit(
                type="carry",
                team_id=carrier.team,
                player_id=carrier.player_id,
                time_s=s.carrier_since,
                start_position=s.carry_start,
                end_position=carrier.pos,
                related_frame_ids=[start_frame, self._frame_index()],
            )
        self._end_pressure()
        s.released[carrier.player_id] = s.t
        return carrier, self.ball.copy()

    def _end_pressure(self) -> None:
        s = self.state
        if s.pressure is None:
            return
        presser, carrier_id, start_frame = s.pressure
        p = self.agents[presser]
        self._emit(
            type="pressure_end",
            team_id=p.team,
            player_id=presser,
            time_s=s.t,
            start_position=p.pos,
            related_player_ids=[carrier_id],
            related_frame_ids=[start_frame, self._frame_index()],
        )
        s.pressure = None

    def _update_pressure(self) -> None:
        s = self.state
        if s.mode != "held" or s.carrier is None:
            return
        carrier = self.agents[s.carrier]
        opponents = [a for a in self.agents.values() if a.team != carrier.team and a.role != "GK"]
        nearest = min(opponents, key=lambda a: float(np.linalg.norm(a.pos - carrier.pos)))
        d = float(np.linalg.norm(nearest.pos - carrier.pos))
        if s.pressure is None and d <= PRESSURE_ON:
            s.pressure = (nearest.player_id, carrier.player_id, self._frame_index())
            self._emit(
                type="pressure_start",
                team_id=nearest.team,
                player_id=nearest.player_id,
                time_s=s.t,
                start_position=nearest.pos,
                related_player_ids=[carrier.player_id],
            )
        elif s.pressure is not None:
            presser = self.agents[s.pressure[0]]
            if float(np.linalg.norm(presser.pos - carrier.pos)) > PRESSURE_OFF:
                self._end_pressure()

    # -- script progression -------------------------------------------------

    def _advance_script(self) -> None:
        s = self.state
        if s.mode != "held" or s.script_idx >= len(self.script):
            return
        step = self.script[s.script_idx]
        if isinstance(step, Carry):
            if s.t - s.carrier_since >= step.duration_s - 1e-9:
                s.script_idx += 1
            return
        if isinstance(step, Pass):
            assert step.passer == s.carrier, f"script expects {step.passer} on the ball, got {s.carrier}"
            passer, start = self._release()
            target = np.array(step.meet) + self.meet_jitter[s.script_idx]
            dist = float(np.linalg.norm(target - start))
            recip = self.agents[step.recipient]
            recip_eta = float(np.linalg.norm(target - recip.pos)) / (0.8 * recip.max_speed) + 0.5
            flight_time = max(dist / self.pass_speed[s.script_idx], recip_eta)
            idx = self._emit(
                type="pass",
                team_id=passer.team,
                player_id=passer.player_id,
                recipient_id=step.recipient,
                time_s=s.t,
                start_position=start,
                end_position=target,
            )
            s.mode = "flight"
            s.carrier = None
            s.flight = Flight("pass", passer.player_id, step.recipient, target, dist / flight_time, idx)
            return
        if isinstance(step, Shot):
            assert step.player == s.carrier
            shooter, start = self._release()
            gk = self.agents["CED-01"]
            save = gk.pos + np.array([-0.8, float(np.clip(start[1] - gk.pos[1], -1.5, 1.5)) * 0.5])
            idx = self._emit(
                type="shot",
                team_id=shooter.team,
                player_id=shooter.player_id,
                time_s=s.t,
                start_position=start,
                end_position=save,
            )
            s.mode = "flight"
            s.carrier = None
            s.shot_taken_at = s.t
            s.flight = Flight("shot", shooter.player_id, "CED-01", save, 20.0, idx)

    def _update_ball(self) -> None:
        s = self.state
        prev = self.ball.copy()
        if s.mode == "held" and s.carrier:
            self.ball = self._held_ball_pos(self.agents[s.carrier])
        elif s.mode == "flight" and s.flight:
            to = s.flight.target - self.ball
            d = float(np.linalg.norm(to))
            step = s.flight.speed * DT
            if d <= step:
                self.ball = s.flight.target.copy()
                if s.flight_arrived_at is None:
                    s.flight_arrived_at = s.t
            else:
                self.ball = self.ball + _unit(to) * step
        self.ball_vel = (self.ball - prev) / DT

    def _check_reception(self) -> None:
        s = self.state
        if s.mode != "flight" or s.flight is None:
            return
        recip = self.agents[s.flight.recipient]
        if float(np.linalg.norm(recip.pos - self.ball)) <= RECEIVE_RADIUS and s.flight_arrived_at is not None:
            ev = self.raw_events[s.flight.event_index]
            ev["outcome"] = "saved" if s.flight.kind == "shot" else "complete"
            ev["related_frame_ids"] = [ev["related_frame_ids"][0], self._frame_index()]
            if s.flight.kind == "pass":
                self._emit(
                    type="reception",
                    team_id=recip.team,
                    player_id=recip.player_id,
                    time_s=s.t,
                    start_position=self.ball,
                )
            self._gain_possession(recip.player_id)
        elif s.flight_arrived_at is not None and s.t - s.flight_arrived_at > MAX_RECEPTION_WAIT_S:
            raise RuntimeError(f"{recip.player_id} never reached the ball; fix the script geometry")

    # -- run ----------------------------------------------------------------

    def _record_frame(self) -> None:
        s = self.state
        self.frames.append(
            {
                "frame_id": len(self.frames),
                "time_s": round(s.t, 2),
                "ball": {
                    "x": round(float(self.ball[0]), 3),
                    "y": round(float(self.ball[1]), 3),
                    "z": 0.0,
                    "vx": round(float(self.ball_vel[0]), 3),
                    "vy": round(float(self.ball_vel[1]), 3),
                    "possession_player_id": s.carrier if s.mode == "held" else None,
                },
                "players": [
                    {
                        "player_id": a.player_id,
                        "team_id": a.team,
                        "x": round(float(a.pos[0]), 3),
                        "y": round(float(a.pos[1]), 3),
                        "vx": round(float(a.vel[0]), 3),
                        "vy": round(float(a.vel[1]), 3),
                        "observed_fields": ["x", "y", "vx", "vy"],
                    }
                    for a in self.agents.values()
                ],
            }
        )

    def run(self) -> tuple[list[dict], list[dict]]:
        s = self.state
        first = self.script[0]
        assert isinstance(first, Carry)
        s.carrier = first.player
        s.carrier_since = 0.0
        # Start everyone at their shape target for the opening ball position so
        # frame 0 is a settled state rather than a jump.
        self.ball = self._held_ball_pos(self.agents[first.player])
        for a in self.agents.values():
            if a.player_id != first.player:
                a.pos = self._formation_target(a)
        s.carry_start = self.agents[first.player].pos.copy()
        s.receptions[first.player] = 0.0
        self._record_frame()

        n_max = int(self.cfg.duration_cap_s * FRAME_RATE)
        for i in range(1, n_max + 1):
            s.t = i * DT
            targets = {pid: self._target(a) for pid, a in self.agents.items()}
            for pid, a in self.agents.items():
                self._steer(a, targets[pid])
            self._update_ball()
            self._record_frame()
            self._check_reception()
            self._advance_script()
            self._update_pressure()
            if s.script_idx >= len(self.script):
                break
        self._end_pressure()
        return self.frames, self._finalize_events()

    def _finalize_events(self) -> list[dict]:
        order = sorted(range(len(self.raw_events)), key=lambda i: (self.raw_events[i]["time_s"], i))
        out = []
        for n, i in enumerate(order):
            ev = dict(self.raw_events[i])
            ev["event_id"] = f"{self.cfg.scenario_id}-e{n:03d}"
            ev["scenario_id"] = self.cfg.scenario_id
            out.append(ev)
        return out


def dataset_hash(frames: list[dict], events: list[dict]) -> str:
    canonical = json.dumps({"frames": frames, "events": events}, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_manifest(cfg: HeroConfig, frames: list[dict], events: list[dict]) -> dict:
    teams = []
    for team_id in (CEDAR, HARBOR):
        teams.append(
            {
                "team_id": team_id,
                **TEAM_META[team_id],
                "players": [
                    {"player_id": pid, "team_id": tm, "number": num, "name": name, "role": role}
                    for pid, tm, num, name, role, _, _ in ROSTER
                    if tm == team_id
                ],
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "scenario_id": cfg.scenario_id,
        "version": "1",
        "seed": cfg.seed,
        "title": cfg.title,
        "description": cfg.description,
        "synthetic": True,
        "teams": teams,
        "pitch": {"length_m": PITCH_L, "width_m": PITCH_W},
        "frame_rate_hz": float(FRAME_RATE),
        "frame_count": len(frames),
        "duration_s": frames[-1]["time_s"],
        "period": 2,
        "match_clock_offset_s": cfg.match_clock_offset_s,
        "attacking_directions": [
            {"team_id": HARBOR, "period": 2, "direction": "+x"},
            {"team_id": CEDAR, "period": 2, "direction": "-x"},
        ],
        "fixture_paths": {"tracking": "tracking.json", "events": "events.json"},
        "generator_version": GENERATOR_VERSION,
        "dataset_hash": dataset_hash(frames, events),
        "availability": "full-tracking",
        "available_fields": ["player.x", "player.y", "player.vx", "player.vy", "ball.x", "ball.y", "ball.vx", "ball.vy", "ball.possession_player_id"],
        "known_limitations": [
            "Synthetic sequence generated by a rule-based kinematic simulator; not recorded from a real match.",
            "Ground passes only, at constant ball speed; no aerial play, spin, or deflections.",
            "Offside is not modelled.",
            "Player body orientation is not generated.",
            "Pressure events use a fixed 3 m start / 4 m end distance threshold.",
        ],
    }


def generate(cfg: HeroConfig) -> tuple[dict, list[dict], list[dict]]:
    frames, events = HeroGenerator(cfg).run()
    return build_manifest(cfg, frames, events), frames, events


def write_fixture(cfg: HeroConfig, out_root: Path) -> Path:
    manifest, frames, events = generate(cfg)
    out = out_root / cfg.scenario_id
    out.mkdir(parents=True, exist_ok=True)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (out / "tracking.json").write_text(json.dumps(frames, separators=(",", ":")) + "\n", encoding="utf-8")
    (out / "events.json").write_text(json.dumps(events, indent=1) + "\n", encoding="utf-8")
    return out
