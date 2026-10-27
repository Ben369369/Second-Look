"""Short-horizon responsive rollouts from a recorded branch frame.

Everything here is a transparent, rule-based model (policy version below). It
is not fitted to real football and its outputs are simulator counts, never
real-world probabilities.

Design notes
- Only the state at the branch frame is read (positions, velocities, possessor,
  roster roles, attacking direction). Recorded frames after it are never used.
- Coordinates are rotated so the attacking team always attacks +x; results are
  rotated back for display.
- Rollouts are vectorised over R trials. Randomness for trial r at step s for
  player i comes from row r of a generator seeded by (seed, step), so every
  intervention sees the same random draws (common random numbers) and the
  comparison between interventions is paired.
- Changes to one player propagate through the policies: the presser's
  position changes the carrier's pressure, option values and execution error;
  the overlap runner reacts to the presser stepping out; defenders react to
  whoever has the ball.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

import numpy as np

from app.schemas import ReplayBundle

POLICY_VERSION = "rules/1"

Action = Literal["hold", "press_earlier", "press_with_cover"]
AttackerPolicy = Literal["patient", "direct"]
ACTIONS: tuple[Action, ...] = ("hold", "press_earlier", "press_with_cover")

DT = 0.1
ACCEL = 4.5  # m/s^2
VMAX = 7.5  # m/s outfield
VMAX_GK = 6.0
VMAX_CARRY = 6.0
HOLD_OFFSET = 0.5
RECEIVE_REACH = 1.2  # m, a loose ball is taken by the nearest player this close
FIRST_TOUCH_REACH = 2.0  # m, the intended receiver controls an arriving pass within this
MAX_LEAD = 6.0  # m, passes are played ahead of a moving receiver by at most this
PASS_SPEED = 14.0
TACKLE_REACH = 1.0
TACKLE_P_STEP = 0.07  # per 0.1 s while a defender is within reach
MIN_HOLD_S = 0.5  # carrier keeps the ball at least this long after receiving
DECISION_EVERY_S = 0.3
CHASER_REACTION_S = 0.4
EARLY_PRESS_S = 0.3  # press_earlier: presser starts closing this long after the branch
CONTAIN_DIST = 6.0  # hold: presser stays this far goal-side
OVERLAP_TRIGGER = 4.0  # m, presser this close to the carrier triggers the overlap run
COVER_SCREEN_FRACTION = 0.5  # press_with_cover: cover screens the midpoint of the carrier -> inside-option lane
CARRY_STEP = 4.0  # m, carry target distance
AVOID_RADIUS = 7.0  # m, a carrier veers away from a defender this close in front
SPACE_GRID = np.array([(dx, dy) for dx in (-4.0, 0.0, 4.0, 8.0) for dy in (-6.0, -3.0, 0.0, 3.0, 6.0)])
ENGAGE_DIST = 1.0
ZONE_RADIUS = 18.0  # presser only follows a carrier within this distance

# Lane-access heuristic, shared with metrics/core.py (lane_access/1).
DEF_REACTION = 0.25
DEF_SPEED = 7.0
DEF_REACH = 1.0

# Option value = (1 - risk) * gain - risk * loss_cost, with
# gain = w_prog * progress + w_dz * dangerous-zone value + w_space * receiver space.
# temp scales the Gumbel choice noise (higher = less deterministic).
POLICY_WEIGHTS: dict[str, dict[str, float]] = {
    "patient": {"w_prog": 1.0, "w_dz": 1.0, "w_space": 0.5, "loss_cost": 1.4, "temp": 0.25},
    "direct": {"w_prog": 1.6, "w_dz": 1.4, "w_space": 0.3, "loss_cost": 0.8, "temp": 0.25},
}


@dataclass(frozen=True)
class SimConfig:
    rollouts: int = 200
    horizon_s: float = 8.0
    seed: int = 20261026
    cover_delay_s: float = 0.6
    attacker_policy: AttackerPolicy = "patient"
    execution_noise: float = 1.0


@dataclass(frozen=True)
class Branch:
    """Roles resolved from the observed state at the branch frame."""

    frame_id: int
    time_s: float
    carrier: str
    presser: str
    cover: str
    inside_option: str
    overlap_runner: str | None
    striker: str


@dataclass
class Rollouts:
    action: Action
    danger: np.ndarray  # (R,) bool: attacking team controlled the ball in a dangerous zone
    danger_t: np.ndarray  # (R,) float, nan if none
    regain: np.ndarray  # (R,) bool: defending team won the ball
    regain_t: np.ndarray  # (R,) float, nan if none
    retained: np.ndarray  # (R,) bool: attacking team still has the ball at the horizon
    first_pass_t: np.ndarray  # (R,) float, nan if the original carrier never passed
    pos: np.ndarray  # (S+1, R, N, 2) pitch coordinates
    ball: np.ndarray  # (S+1, R, 2)
    holder: np.ndarray  # (S+1, R) int, -1 when loose or in flight
    events: list[list[tuple[float, str, int, int]]]  # per rollout: (t, kind, from, to)


class BranchError(ValueError):
    pass


DANGER_DEPTH = 30.0  # m from the goal line
DANGER_HALF_WIDTH = 20.16  # m, penalty-area half width


def danger_zone(x: np.ndarray, y: np.ndarray, L: float, W: float) -> np.ndarray:
    """Dangerous zone (prototype convention): the penalty area and the 13.5 m in front of it,
    at penalty-area width, i.e. within 30 m of goal and 20.16 m of the centre line. Attacking coordinates."""
    return (x >= L - DANGER_DEPTH) & (np.abs(y - W / 2) <= DANGER_HALF_WIDTH)


def _normal_two_tail(z: np.ndarray) -> np.ndarray:
    """P(|Z| > z) for standard normal Z, via the Abramowitz-Stegun 7.1.26 erf approximation (|error| < 1.5e-7)."""
    x = np.abs(z) / math.sqrt(2.0)
    t = 1.0 / (1.0 + 0.3275911 * x)
    poly = t * (0.254829592 + t * (-0.284496736 + t * (1.421413741 + t * (-1.453152027 + t * 1.061405429))))
    return poly * np.exp(-x * x)  # erfc(x)


class Simulator:
    def __init__(self, bundle: ReplayBundle, frame_id: int, presser_id: str, cover_id: str | None = None):
        m = bundle.manifest
        self.L, self.W = m.pitch.length_m, m.pitch.width_m
        frame = next((f for f in bundle.frames if f.frame_id == frame_id), None)
        if frame is None or frame.ball is None:
            raise BranchError(f"frame {frame_id} has no tracking data")
        team_of = {p.player_id: t.team_id for t in m.teams for p in t.players}
        role_of = {p.player_id: p.role for t in m.teams for p in t.players}
        holder = frame.ball.possession_player_id
        b = frame.ball
        self.start_flight: tuple[np.ndarray, float] | None = None  # (meeting point, ball speed), pitch coords
        if holder is None:
            # Ball in flight: the intended receiver is the outfield player closest to the ball's
            # observed direction of travel, ahead of the ball (uses only this frame's ball velocity).
            speed = math.hypot(b.vx, b.vy)
            if speed < 3.0:
                raise BranchError("the ball is neither held nor travelling at the branch frame")
            u = np.array([b.vx, b.vy]) / speed
            # The passing team is the last team in possession before this frame (past data only).
            last = next(
                (f.ball.possession_player_id for f in reversed(bundle.frames)
                 if f.frame_id < frame_id and f.ball and f.ball.possession_player_id),
                None,
            )
            if last is None:
                raise BranchError("no earlier possession to identify the passing team")
            best = None
            for pl in frame.players:
                if role_of[pl.player_id] == "GK" or team_of[pl.player_id] != team_of[last]:
                    continue
                rel = np.array([pl.x - b.x, pl.y - b.y])
                along = float(rel @ u)
                if 0.0 < along < 45.0:
                    perp = abs(float(rel[0] * u[1] - rel[1] * u[0]))
                    if best is None or perp < best[0]:
                        best = (perp, pl.player_id, along)
            if best is None or best[0] > 4.0:
                raise BranchError("cannot identify the intended receiver of the ball in flight")
            holder = best[1]
            self.start_flight = (np.array([b.x, b.y]) + best[2] * u, speed)
        att_team = team_of[holder]
        if presser_id not in team_of or team_of[presser_id] == att_team or role_of[presser_id] == "GK":
            raise BranchError("presser must be an outfield player of the defending team")
        direction = next(d.direction for d in m.attacking_directions if d.team_id == att_team and d.period == m.period)
        self.flip = direction == "-x"

        self.ids = [p.player_id for p in frame.players]
        self.N = len(self.ids)
        idx = {pid: i for i, pid in enumerate(self.ids)}
        pos = np.array([[p.x, p.y] for p in frame.players], dtype=float)
        vel = np.array([[p.vx, p.vy] for p in frame.players], dtype=float)
        self.pos0 = self._to_att(pos)
        self.vel0 = -vel if self.flip else vel
        self.ball0 = self.flight_target0 = None
        self.flight_speed0 = PASS_SPEED
        if self.start_flight is not None:
            self.ball0 = self._to_att(np.array([b.x, b.y]))
            self.flight_target0 = self._to_att(self.start_flight[0])
            self.flight_speed0 = self.start_flight[1]
        self.is_att = np.array([team_of[pid] == att_team for pid in self.ids])
        self.is_gk = np.array([role_of[pid] == "GK" for pid in self.ids])
        self.att_out = np.where(self.is_att & ~self.is_gk)[0]
        self.def_out = np.where(~self.is_att & ~self.is_gk)[0]
        self.vmax = np.where(self.is_gk, VMAX_GK, VMAX)

        c = idx[holder]
        p = idx[presser_id]
        P = self.pos0
        side = 1.0 if P[c, 1] >= self.W / 2 else -1.0  # carrier's flank (+1: high y)
        # Inside option: most advanced teammate within 25 m who is more central than the carrier.
        central = [j for j in self.att_out if j != c and abs(P[j, 1] - self.W / 2) < abs(P[c, 1] - self.W / 2)]
        near = [j for j in central if np.linalg.norm(P[j] - P[c]) < 25.0] or [j for j in self.att_out if j != c]
        s = max(near, key=lambda j: P[j, 0] - 0.3 * np.linalg.norm(P[j] - P[c]))
        # Overlap runner: nearest teammate on the same flank, behind the ball.
        flank = [j for j in self.att_out if j not in (c, s) and side * (P[j, 1] - self.W / 2) > 12 and P[j, 0] < P[c, 0]]
        o = min(flank, key=lambda j: np.linalg.norm(P[j] - P[c])) if flank else None
        f = max((j for j in self.att_out if j not in (c, s)), key=lambda j: P[j, 0])
        if cover_id is not None:
            if cover_id not in idx or team_of[cover_id] == att_team or role_of[cover_id] == "GK" or cover_id == presser_id:
                raise BranchError("cover player must be another outfield player of the defending team")
            k = idx[cover_id]
        else:
            # Cover: the defending midfielder/defender nearest the inside option (forwards excluded).
            cands = [j for j in self.def_out if j != p and role_of[self.ids[j]] != "ST"] or [j for j in self.def_out if j != p]
            k = min(cands, key=lambda j: np.linalg.norm(P[j] - P[s]))
        self.c, self.p, self.k, self.s, self.o, self.f = c, p, k, s, o, f
        self.side = side
        self.branch = Branch(
            frame_id=frame_id,
            time_s=frame.time_s,
            carrier=holder,
            presser=presser_id,
            cover=self.ids[k],
            inside_option=self.ids[s],
            overlap_runner=self.ids[o] if o is not None else None,
            striker=self.ids[f],
        )
        # Team-shape anchors inferred from the observed state: home = position minus current shift.
        self.home = P - self._shift(P[c][None, :])[0]
        self.goal = np.array([self.L, self.W / 2])

    # -- coordinates --------------------------------------------------------

    def _to_att(self, xy: np.ndarray) -> np.ndarray:
        if not self.flip:
            return xy.copy()
        out = xy.copy()
        out[..., 0] = self.L - xy[..., 0]
        out[..., 1] = self.W - xy[..., 1]
        return out

    def _clamp(self, xy: np.ndarray, margin: float = 0.5) -> np.ndarray:
        out = xy.copy()
        out[..., 0] = np.clip(out[..., 0], margin, self.L - margin)
        out[..., 1] = np.clip(out[..., 1], margin, self.W - margin)
        return out

    def _shift(self, ball: np.ndarray) -> np.ndarray:
        """(R,N,2) team-shape shift for ball positions (R,2)."""
        bx, by = ball[:, 0:1], ball[:, 1:2]
        att_dx = np.clip(0.45 * (bx - 40.0), -5.0, 22.0)
        def_dx = np.clip(0.35 * (bx - self.L / 2), -10.0, 10.0)
        dx = np.where(self.is_att[None, :], att_dx, def_dx)
        dy = np.where(self.is_att[None, :], 0.15, 0.3) * (by - self.W / 2)
        out = np.stack([dx, dy], axis=-1)
        out[:, self.is_gk] = 0.0
        return out

    def _goal_side(self, of: np.ndarray, dist: float) -> np.ndarray:
        d = self.goal - of
        n = np.linalg.norm(d, axis=-1, keepdims=True)
        return of + dist * d / np.maximum(n, 1e-9)

    def _find_space(self, base: np.ndarray, D: np.ndarray) -> np.ndarray:
        """Among grid points around `base` (R,2), pick the one furthest from the nearest defender,
        with a mild preference for staying near `base`."""
        cand = self._clamp(base[:, None, :] + SPACE_GRID[None], 2.0)  # (R,C,2)
        dmin = np.min(np.linalg.norm(cand[:, :, None] - D[:, None], axis=-1), axis=2)  # (R,C)
        score = np.minimum(dmin, 10.0) - 0.15 * np.linalg.norm(SPACE_GRID, axis=-1)[None]
        return cand[np.arange(len(base)), np.argmax(score, axis=1)]

    def _carry_targets(self, P: np.ndarray, D: np.ndarray) -> np.ndarray:
        """Dribble target CARRY_STEP ahead, toward the edge of the box, veering away from a defender close in front."""
        aim = np.array([self.L - 22.0, self.W / 2])
        d = aim - P
        d = d / np.maximum(np.linalg.norm(d, axis=-1, keepdims=True), 1e-9)
        rel = D - P[:, None]  # (n, Dn, 2)
        dist = np.linalg.norm(rel, axis=-1)
        j = np.argmin(dist, axis=1)
        nr = rel[np.arange(len(P)), j]
        nd = dist[np.arange(len(P)), j]
        ahead = (nr * d).sum(-1) > 0
        push = np.where(((nd < AVOID_RADIUS) & ahead)[:, None], -0.9 * nr / np.maximum(nd, 1e-9)[:, None], 0.0)
        d = d + push
        d = d / np.maximum(np.linalg.norm(d, axis=-1, keepdims=True), 1e-9)
        return self._clamp(P + CARRY_STEP * d)

    # -- run ------------------------------------------------------------------

    def run(self, action: Action, cfg: SimConfig) -> Rollouts:
        R, N = cfg.rollouts, self.N
        steps = int(round(cfg.horizon_s / DT))
        wts = POLICY_WEIGHTS[cfg.attacker_policy]
        ri = np.arange(R)

        pos = np.repeat(self.pos0[None], R, axis=0)
        vel = np.repeat(self.vel0[None], R, axis=0)
        holder = np.full(R, self.c)
        ball = pos[:, self.c] + np.array([HOLD_OFFSET, 0.0])
        in_flight = np.zeros(R, bool)
        flight_target = np.zeros((R, 2))
        flight_speed = np.full(R, PASS_SPEED)
        flight_recv = np.full(R, -1)
        if self.ball0 is not None:
            # Branch with the pass to the carrier still travelling.
            ball = np.repeat(self.ball0[None], R, axis=0)
            holder[:] = -1
            in_flight[:] = True
            flight_target[:] = self.flight_target0
            flight_speed[:] = self.flight_speed0
            flight_recv[:] = self.c
        carrier_since = np.zeros(R)  # time the current holder received (branch counts as reception)
        next_decision = np.full(R, MIN_HOLD_S)
        carry_target = self._carry_targets(pos[:, self.c], pos[:, self.def_out])

        danger = np.zeros(R, bool)
        danger_t = np.full(R, np.nan)
        regain = np.zeros(R, bool)
        regain_t = np.full(R, np.nan)
        first_pass_t = np.full(R, np.nan)
        events: list[list[tuple[float, str, int, int]]] = [[] for _ in range(R)]

        hist_pos = np.zeros((steps + 1, R, N, 2))
        hist_ball = np.zeros((steps + 1, R, 2))
        hist_holder = np.zeros((steps + 1, R), int)
        hist_pos[0], hist_ball[0], hist_holder[0] = pos, ball, holder

        def record_outcomes(t: float) -> None:
            att_hold = (holder >= 0) & self.is_att[np.maximum(holder, 0)]
            def_hold = (holder >= 0) & ~self.is_att[np.maximum(holder, 0)]
            new_d = att_hold & ~danger & ~regain & danger_zone(ball[:, 0], ball[:, 1], self.L, self.W)
            danger_t[new_d] = t
            danger[new_d] = True
            new_r = def_hold & ~regain & ~danger
            regain_t[new_r] = t
            regain[new_r] = True

        for step in range(1, steps + 1):
            t = step * DT
            # Common random numbers: row r is trial r, column i is player i.
            U = np.random.default_rng([cfg.seed, step]).random((R, N, 16))

            att_hold = (holder >= 0) & self.is_att[np.maximum(holder, 0)]
            def_hold = (holder >= 0) & ~self.is_att[np.maximum(holder, 0)]
            loose = (holder < 0) & ~in_flight
            # Phase 1: the original carrier has (or is about to receive) the ball.
            orig = (holder == self.c) | ((holder < 0) & (flight_recv == self.c))

            # ---- targets -------------------------------------------------
            targets = self._clamp(self.home[None] + self._shift(ball), margin=1.0)
            gk = np.where(self.is_gk)[0]
            for g in gk:
                gx = self.L - 3.5 if not self.is_att[g] else 3.5
                targets[:, g] = np.stack([np.full(R, gx), self.W / 2 + 0.25 * (ball[:, 1] - self.W / 2)], -1)

            pc = pos[:, self.c]
            # Inside option offers into the half-space while the original carrier has the ball.
            offer = self._find_space(pc + np.array([4.0, -self.side * 13.0]), pos[:, self.def_out])
            targets[orig, self.s] = offer[orig]
            # Overlap: when the presser engages the carrier (closer than containing distance), the fullback runs beyond.
            if self.o is not None:
                stepped = orig & (np.linalg.norm(pos[:, self.p] - pc, axis=-1) < OVERLAP_TRIGGER)
                run = self._clamp(pc + np.array([10.0, self.side * 1.5]), 1.0)
                targets[stepped, self.o] = run[stepped]
            # Striker runs the channel once the ball is in the opponent half.
            fwd = att_hold & (ball[:, 0] > 55.0)
            chan = np.stack([np.clip(ball[:, 0] + 14.0, 80.0, self.L - 10.0), np.full(R, self.W / 2 + self.side * 3.0)], -1)
            chan = self._find_space(chan, pos[:, self.def_out])
            targets[fwd, self.f] = chan[fwd]
            # When the ball is wide and advanced, the inside option attacks the box for a cut-back.
            wide_adv = att_hold & ~orig & (ball[:, 0] > 78.0) & (np.abs(ball[:, 1] - self.W / 2) > 15.0)
            box_pt = self._find_space(np.stack([np.full(R, self.L - 11.0), np.full(R, self.W / 2 + self.side * 4.0)], -1), pos[:, self.def_out])
            targets[wide_adv, self.s] = box_pt[wide_adv]

            # Presser policy: the intervention under test.
            dist_pc = np.linalg.norm(pos[:, self.p] - pc, axis=-1)
            in_zone = orig & (dist_pc < ZONE_RADIUS)
            if action == "hold":
                engage = in_zone & (dist_pc < 3.0)
            else:
                engage = in_zone & (t >= EARLY_PRESS_S)
            contain = in_zone & ~engage
            targets[engage, self.p] = self._goal_side(pc, ENGAGE_DIST)[engage]
            targets[contain, self.p] = self._goal_side(pc, CONTAIN_DIST)[contain]
            # Cover: after the cover delay a designated teammate screens the carrier -> inside-option lane.
            if action == "press_with_cover" and t >= cfg.cover_delay_s:
                screen = pc + COVER_SCREEN_FRACTION * (pos[:, self.s] - pc)
                targets[orig, self.k] = screen[orig]

            # Any other attacking carrier is closed down by the nearest outfield defender after a reaction time.
            h = np.maximum(holder, 0)
            hp = pos[ri, h]
            other = att_hold & ~orig & (t - carrier_since >= CHASER_REACTION_S)
            if other.any():
                dd = np.linalg.norm(pos[:, self.def_out] - hp[:, None], axis=-1)
                chaser = self.def_out[np.argmin(dd, axis=1)]
                gs = self._goal_side(hp, ENGAGE_DIST)
                targets[ri[other], chaser[other]] = gs[other]
            # Defending carrier (after a regain) carries away; nearest attacker counter-presses.
            if def_hold.any():
                targets[ri[def_hold], h[def_hold]] = self._clamp(hp - np.array([4.0, 0.0]))[def_hold]
                da = np.linalg.norm(pos[:, self.att_out] - hp[:, None], axis=-1)
                cp = self.att_out[np.argmin(da, axis=1)]
                targets[ri[def_hold], cp[def_hold]] = hp[def_hold]
            # Attacking carrier dribbles toward its carry target.
            targets[ri[att_hold], h[att_hold]] = carry_target[att_hold]
            # Ball in flight or just arrived: the intended receiver (or interceptor) runs to the meeting point.
            fl = (holder < 0) & (flight_recv >= 0)
            targets[ri[fl], flight_recv[fl]] = flight_target[fl]
            # Loose ball: nearest player of each team goes for it.
            if loose.any():
                for team_idx in (self.att_out, self.def_out):
                    dl = np.linalg.norm(pos[:, team_idx] - ball[:, None], axis=-1)
                    near = team_idx[np.argmin(dl, axis=1)]
                    targets[ri[loose], near[loose]] = ball[loose]

            # ---- kinematics ------------------------------------------------
            vcap = np.repeat(self.vmax[None], R, axis=0)
            vcap[ri[att_hold], h[att_hold]] = VMAX_CARRY
            to = targets - pos
            dist = np.linalg.norm(to, axis=-1, keepdims=True)
            speed = np.minimum(vcap[..., None], np.sqrt(2 * ACCEL * 0.8 * dist))
            desired = np.where(dist > 0.15, to / np.maximum(dist, 1e-9) * speed, 0.0)
            dv = desired - vel
            dvn = np.linalg.norm(dv, axis=-1, keepdims=True)
            dv = np.where(dvn > ACCEL * DT, dv * (ACCEL * DT / np.maximum(dvn, 1e-9)), dv)
            vel = vel + dv
            sp = np.linalg.norm(vel, axis=-1, keepdims=True)
            vel = np.where(sp > vcap[..., None], vel * (vcap[..., None] / np.maximum(sp, 1e-9)), vel)
            new_pos = self._clamp(pos + vel * DT)
            vel = (new_pos - pos) / DT
            pos = new_pos

            # ---- ball --------------------------------------------------------
            held = holder >= 0
            off = np.where(self.is_att[h][:, None], HOLD_OFFSET, -HOLD_OFFSET) * np.array([1.0, 0.0])
            ball = np.where(held[:, None], pos[ri, h] + off, ball)
            if in_flight.any():
                to_b = flight_target - ball
                db = np.linalg.norm(to_b, axis=-1)
                stepb = flight_speed * DT
                arrive = in_flight & (db <= stepb)
                move = in_flight & ~arrive
                ball = np.where(move[:, None], ball + to_b / np.maximum(db, 1e-9)[:, None] * stepb[:, None], ball)
                ball = np.where(arrive[:, None], flight_target, ball)
                # On arrival the intended receiver (or interceptor) controls it if close enough;
                # otherwise the ball is loose and whoever reaches it first takes it.
                rp = pos[ri, np.maximum(flight_recv, 0)]
                touch = arrive & (flight_recv >= 0) & (np.linalg.norm(rp - ball, axis=-1) <= FIRST_TOUCH_REACH)
                for r in np.where(touch)[0]:
                    events[r].append((round(t, 1), "pickup", -1, int(flight_recv[r])))
                holder = np.where(touch, flight_recv, holder)
                carrier_since = np.where(touch, t, carrier_since)
                next_decision = np.where(touch, t + MIN_HOLD_S, next_decision)
                flight_recv = np.where(touch, -1, flight_recv)
                in_flight &= ~arrive
            # Loose-ball pickup.
            loose = (holder < 0) & ~in_flight
            if loose.any():
                dl = np.linalg.norm(pos - ball[:, None], axis=-1)
                dl[:, self.is_gk] = np.inf
                nearest = np.argmin(dl, axis=1)
                take = loose & (dl[ri, nearest] <= RECEIVE_REACH)
                for r in np.where(take)[0]:
                    events[r].append((round(t, 1), "pickup", -1, int(nearest[r])))
                holder = np.where(take, nearest, holder)
                flight_recv = np.where(take, -1, flight_recv)
                carrier_since = np.where(take, t, carrier_since)
                next_decision = np.where(take, t + MIN_HOLD_S, next_decision)

            # ---- duels: tackle on an attacking carrier -----------------------
            att_hold = (holder >= 0) & self.is_att[np.maximum(holder, 0)]
            h = np.maximum(holder, 0)
            hp = pos[ri, h]
            dd = np.linalg.norm(pos[:, self.def_out] - hp[:, None], axis=-1)
            nd = np.argmin(dd, axis=1)
            near_def = self.def_out[nd]
            tackled = att_hold & (dd[ri, nd] <= TACKLE_REACH) & (U[ri, h, 13] < TACKLE_P_STEP * cfg.execution_noise)
            for r in np.where(tackled)[0]:
                events[r].append((round(t, 1), "tackle", int(h[r]), int(near_def[r])))
            holder = np.where(tackled, near_def, holder)
            carrier_since = np.where(tackled, t, carrier_since)

            # ---- carrier decisions ------------------------------------------
            att_hold = (holder >= 0) & self.is_att[np.maximum(holder, 0)]
            h = np.maximum(holder, 0)
            decide = att_hold & ~in_flight & (t >= next_decision)
            if decide.any():
                self._decide(
                    decide, t, pos, vel, h, U, wts, cfg, in_flight, flight_target, flight_speed, flight_recv,
                    holder, carry_target, next_decision, first_pass_t, events,
                )
                holder = np.where(in_flight, -1, holder)

            record_outcomes(t)
            hist_pos[step], hist_ball[step], hist_holder[step] = pos, ball, holder

        att_end = (holder >= 0) & self.is_att[np.maximum(holder, 0)]
        att_flight = in_flight & (flight_recv >= 0) & self.is_att[np.maximum(flight_recv, 0)]
        if self.flip:
            hist_pos = self._to_att(hist_pos)
            hist_ball = self._to_att(hist_ball)
        return Rollouts(
            action=action,
            danger=danger,
            danger_t=danger_t,
            regain=regain,
            regain_t=regain_t,
            retained=~regain & (att_end | att_flight),
            first_pass_t=first_pass_t,
            pos=hist_pos,
            ball=hist_ball,
            holder=hist_holder,
            events=events,
        )

    def _decide(self, decide, t, pos, vel, h, U, wts, cfg, in_flight, flight_target, flight_speed, flight_recv,
                holder, carry_target, next_decision, first_pass_t, events) -> None:
        """Choose pass / carry / hold for carriers due a decision (mutates state arrays in place)."""
        R = pos.shape[0]
        ri = np.arange(R)
        P = pos[ri, h]  # (R,2) carrier
        mates = self.att_out  # (M,)
        M = pos[:, mates]  # (R,M,2)
        D = pos[:, self.def_out]  # (R,Dn,2)

        # Lane access for every carrier -> mate lane against every defender.
        v = M - P[:, None]  # (R,M,2)
        L2 = np.maximum((v**2).sum(-1), 1e-9)  # (R,M)
        w = D[:, None, :, :] - P[:, None, None, :]  # (R,M,Dn,2)
        k = np.clip((w * v[:, :, None, :]).sum(-1) / L2[:, :, None], 0.0, 1.0)  # (R,M,Dn)
        closest = P[:, None, None, :] + k[..., None] * v[:, :, None, :]
        d_lane = np.linalg.norm(D[:, None] - closest, axis=-1)
        d_time = DEF_REACTION + np.maximum(0.0, d_lane - DEF_REACH) / DEF_SPEED
        b_time = k * np.sqrt(L2)[:, :, None] / PASS_SPEED
        margin = b_time - d_time  # > 0: defender gets there first
        best_def = np.argmax(margin, axis=2)  # (R,M)
        max_margin = np.take_along_axis(margin, best_def[..., None], 2)[..., 0]
        p_int = 1.0 / (1.0 + np.exp(-(max_margin - 0.05) / 0.06))

        # Pressure on the carrier and resulting execution error.
        d_near = np.min(np.linalg.norm(D - P[:, None], axis=-1), axis=1)  # (R,)
        pressure = np.clip((3.0 - d_near) / 3.0, 0.0, 1.0)
        dist_pass = np.sqrt(L2)
        sigma = cfg.execution_noise * (0.4 + 1.4 * pressure[:, None]) * (dist_pass / 15.0)  # (R,M)
        # Misplaced if the perpendicular error exceeds 1.6 m (receiver reach plus a step).
        p_mis = _normal_two_tail(1.6 / np.maximum(sigma, 1e-6))

        prog = np.clip((M[..., 0] - P[:, None, 0]) / 15.0, -1.0, 1.5)
        in_dz = danger_zone(M[..., 0], M[..., 1], self.L, self.W)
        dz = np.where(in_dz & (M[..., 0] >= self.L - 16.5), 1.0, np.where(in_dz, 0.7, np.where(M[..., 0] > 70.0, 0.25, 0.0)))
        space = np.clip(np.min(np.linalg.norm(D[:, None] - M[:, :, None], axis=-1), axis=2) / 8.0, 0.0, 1.0)
        risk = 1.0 - (1.0 - p_int) * (1.0 - p_mis)
        gain = wts["w_prog"] * prog + wts["w_dz"] * dz + wts["w_space"] * space
        u_pass = (1.0 - risk) * gain - risk * wts["loss_cost"]
        u_pass = np.where(mates[None, :] == h[:, None], -np.inf, u_pass)
        # Carrying or holding risks a tackle when a defender is close.
        carry_risk = 0.5 * pressure
        carry_gain = 0.15 * wts["w_prog"] + wts["w_space"] * np.clip(d_near / 8.0, 0, 1)
        u_carry = (1.0 - carry_risk) * carry_gain - carry_risk * wts["loss_cost"]
        hold_risk = 0.6 * pressure
        u_hold = -hold_risk * wts["loss_cost"]
        util = np.concatenate([u_pass, u_carry[:, None], u_hold[:, None]], axis=1)  # (R, M+2)

        carry_all = self._carry_targets(P, D)

        # Gumbel-max choice using the carrier's coupled uniforms (options 0..11).
        n_opt = util.shape[1]
        g = -np.log(-np.log(np.clip(U[ri, h, :n_opt], 1e-12, 1 - 1e-12)))
        choice = np.argmax(util / wts["temp"] + g, axis=1)

        for r in np.where(decide)[0]:
            ch = int(choice[r])
            if ch < len(mates):
                recv = int(mates[ch])
                if np.isnan(first_pass_t[r]) and h[r] == self.c:
                    first_pass_t[r] = t
                if U[r, h[r], 12] < p_int[r, ch]:
                    dfi = int(self.def_out[best_def[r, ch]])
                    kk = float(np.clip(k[r, ch, best_def[r, ch]], 0.1, 0.95))
                    target = P[r] + kk * v[r, ch]
                    flight_recv[r] = dfi
                    events[r].append((round(t, 1), "pass_intercepted", int(h[r]), dfi))
                else:
                    # Execution error perpendicular to the pass line (Box-Muller from coupled uniforms).
                    z = math.sqrt(-2 * math.log(max(U[r, h[r], 14], 1e-12))) * math.cos(2 * math.pi * U[r, h[r], 15])
                    perp = np.array([-v[r, ch, 1], v[r, ch, 0]]) / math.sqrt(L2[r, ch])
                    lead = vel[r, recv] * (math.sqrt(L2[r, ch]) / PASS_SPEED)
                    ln = float(np.linalg.norm(lead))
                    if ln > MAX_LEAD:
                        lead = lead * (MAX_LEAD / ln)
                    target = M[r, ch] + lead + perp * z * sigma[r, ch]
                    flight_recv[r] = recv
                    events[r].append((round(t, 1), "pass", int(h[r]), recv))
                flight_target[r] = self._clamp(target[None])[0]
                flight_speed[r] = PASS_SPEED
                in_flight[r] = True
                holder[r] = -1
            elif ch == len(mates):
                carry_target[r] = carry_all[r]
                next_decision[r] = t + DECISION_EVERY_S
            else:
                # Hold: shield the ball, stepping away from the nearest defender.
                away = P[r] - D[r, int(np.argmin(np.linalg.norm(D[r] - P[r], axis=-1)))]
                carry_target[r] = self._clamp((P[r] + away / max(np.linalg.norm(away), 1e-9))[None])[0]
                next_decision[r] = t + DECISION_EVERY_S


def default_branch(bundle: ReplayBundle, presser_id: str) -> int:
    """The pressing trigger: first frame after the pass to the player `presser_id` later pressed is released.

    Branching while the ball travels gives the presser and the cover the pass's travel time to react,
    which is when a press on a wide player is normally triggered.
    """
    press = next((e for e in bundle.events if e.type == "pressure_start" and e.player_id == presser_id), None)
    if press is None or not press.related_player_ids:
        raise BranchError(f"no recorded press by {presser_id}")
    target = press.related_player_ids[0]
    passes = [e for e in bundle.events if e.type == "pass" and e.recipient_id == target and e.time_s <= press.time_s]
    if not passes:
        raise BranchError("the pass to the pressed player is not recorded")
    # The pass event's frame still shows the passer in possession; the ball travels from the next frame.
    return passes[-1].related_frame_ids[0] + 1
