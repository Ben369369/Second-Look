"""Build typed Fact objects from a SequenceView.

Statements are rendered here, from the computed value, so text and number can
never disagree. A model may later choose and order facts, but not write them.
"""

from __future__ import annotations

from app.metrics import core
from app.metrics.core import METHOD_VERSIONS as MV
from app.metrics.view import SequenceView
from app.schemas import Coverage, Fact, MatchEvent, RefusedMetric, TimeWindow, TrackingFrame

TRACKING_LIMIT = "Synthetic tracking at 10 Hz; positions are simulator output, not real measurements."


def _fmt_t(view: SequenceView, t: float) -> str:
    s = int(view.manifest.match_clock_offset_s + t + 1e-6)
    return f"{s // 60:02d}:{s % 60:02d}"


def _coverage(view: SequenceView, frames_used: int, frames_expected: int, note: str | None = None) -> Coverage:
    return Coverage(
        availability=view.manifest.availability,
        frames_used=frames_used,
        frames_expected=frames_expected,
        complete=frames_used >= frames_expected,
        note=note,
    )


def _event_coverage(view: SequenceView) -> Coverage:
    return _coverage(view, 0, 0, "Computed from events only.")


def _fid(metric: str, subjects: list[str], t: float) -> str:
    return f"{metric}:{'+'.join(subjects) or 'all'}@{t:.1f}"


def _frame(view: SequenceView, t: float) -> TrackingFrame | None:
    return view.frame_at(t) if view.manifest.availability != "event-only" else None


class FactBuilder:
    def __init__(self, view: SequenceView):
        self.v = view
        self.refused: list[RefusedMetric] = []

    def refuse(self, metric: str, reason: str, subjects: list[str] | None = None) -> None:
        self.refused.append(RefusedMetric(metric=metric, subject_ids=subjects or [], reason=reason))

    # -- observed: events ----------------------------------------------------

    def pass_distance(self, e: MatchEvent) -> Fact | None:
        d = core.pass_distance(e)
        subjects = [x for x in (e.player_id, e.recipient_id) if x]
        if d is None:
            self.refuse("pass_distance", "Pass end point is not known at the data cutoff.", subjects)
            return None
        v = self.v
        return Fact(
            fact_id=_fid("pass_distance", [e.event_id], e.time_s),
            evidence_class="observed",
            metric="pass_distance",
            subject_ids=subjects,
            value=round(d, 1),
            unit="m",
            time_window=TimeWindow(start_s=e.time_s, end_s=e.time_s),
            focus_time_s=e.time_s,
            source_event_ids=[e.event_id],
            source_frame_range=(e.related_frame_ids[0], e.related_frame_ids[-1]) if e.related_frame_ids else None,
            method_version=MV["pass_distance"],
            coverage=_event_coverage(v),
            limitations=["Straight line between recorded start and end points; ball path is a ground pass."],
            statement=f"{v.label(e.player_id)}'s pass to {v.label(e.recipient_id)} at {_fmt_t(v, e.time_s)} travelled {d:.1f} m.",  # type: ignore[arg-type]
        )

    def pass_completion(self, team_id: str, start_s: float, end_s: float) -> Fact | None:
        v = self.v
        passes = [e for e in v.events if e.type == "pass" and e.team_id == team_id and start_s <= e.time_s <= end_s]
        c = core.pass_completion(passes)
        team = next(t.name for t in v.manifest.teams if t.team_id == team_id)
        if c.attempted == 0:
            self.refuse("pass_completion", f"No {team} passes with a known outcome in the window.", [team_id])
            return None
        excl = f" {c.unknown} pass{'es' if c.unknown != 1 else ''} with no outcome yet excluded." if c.unknown else ""
        return Fact(
            fact_id=_fid("pass_completion", [team_id], end_s),
            evidence_class="observed",
            metric="pass_completion",
            subject_ids=[team_id],
            value=c.completed,
            unit=f"of {c.attempted} passes",
            time_window=TimeWindow(start_s=start_s, end_s=end_s),
            focus_time_s=passes[0].time_s,
            source_event_ids=[p.event_id for p in passes],
            source_frame_range=None,
            method_version=MV["pass_completion"],
            coverage=_event_coverage(v),
            limitations=["Denominator counts only passes whose outcome is known at the cutoff."],
            statement=f"{team} completed {c.completed} of {c.attempted} passes between {_fmt_t(v, start_s)} and {_fmt_t(v, end_s)}.{excl}",
        )

    def transitions(self, start_s: float, end_s: float) -> Fact | None:
        v = self.v
        if not v.frames:
            self.refuse("transitions", "Possession changes need tracking possession data.")
            return None
        spells = self._spells()
        changes = [s for s in spells[1:] if start_s <= s.start_s <= end_s]
        return Fact(
            fact_id=_fid("transitions", [], end_s),
            evidence_class="observed",
            metric="transitions",
            subject_ids=[],
            value=len(changes),
            unit="possession changes",
            time_window=TimeWindow(start_s=start_s, end_s=end_s),
            focus_time_s=changes[0].start_s if changes else start_s,
            source_event_ids=[],
            source_frame_range=(v.frames[0].frame_id, v.frames[-1].frame_id),
            method_version=MV["transitions"],
            coverage=_coverage(v, len(v.frames), len(v.frames)),
            limitations=["Descriptive count for this short sequence only."],
            statement=f"Possession changed hands {len(changes)} time{'s' if len(changes) != 1 else ''} between {_fmt_t(v, start_s)} and {_fmt_t(v, end_s)}.",
        )

    def final_third_share(self, team_id: str, start_s: float, end_s: float) -> Fact | None:
        v = self.v
        on_ball = [
            e
            for e in v.events
            if e.team_id == team_id and e.type in ("pass", "reception", "carry", "shot") and start_s <= e.time_s <= end_s
        ]
        team = next(t.name for t in v.manifest.teams if t.team_id == team_id)
        if not on_ball:
            self.refuse("final_third_share", f"No {team} on-ball events in the window.", [team_id])
            return None
        direction = v.direction(team_id)
        L = v.manifest.pitch.length_m
        inside = [e for e in on_ball if core.normalised_x(e.start_position.x, direction, L) >= core.FINAL_THIRD_FROM]
        return Fact(
            fact_id=_fid("final_third_share", [team_id], end_s),
            evidence_class="observed",
            metric="final_third_share",
            subject_ids=[team_id],
            value=len(inside),
            unit=f"of {len(on_ball)} on-ball events",
            time_window=TimeWindow(start_s=start_s, end_s=end_s),
            focus_time_s=inside[0].time_s if inside else on_ball[0].time_s,
            source_event_ids=[e.event_id for e in inside],
            source_frame_range=None,
            method_version=MV["final_third_share"],
            coverage=_event_coverage(v),
            limitations=["Final-third event share, not touches: counts pass, reception, carry and shot events by start position."],
            statement=f"{len(inside)} of {team}'s {len(on_ball)} on-ball events started in the final third.",
        )

    def response_time(self, pressure: MatchEvent, reception: MatchEvent) -> Fact:
        v = self.v
        gap = pressure.time_s - reception.time_s
        return Fact(
            fact_id=_fid("response_time", [pressure.player_id, reception.player_id], pressure.time_s),  # type: ignore[list-item]
            evidence_class="observed",
            metric="response_time",
            subject_ids=[pressure.player_id, reception.player_id],  # type: ignore[list-item]
            value=round(gap, 1),
            unit="s",
            time_window=TimeWindow(start_s=reception.time_s, end_s=pressure.time_s),
            focus_time_s=pressure.time_s,
            source_event_ids=[reception.event_id, pressure.event_id],
            source_frame_range=(reception.related_frame_ids[0], pressure.related_frame_ids[0]),
            method_version=MV["response_time"],
            coverage=_event_coverage(v),
            limitations=["Pressure starts when the nearest outfield opponent is within 3 m of the carrier (recording convention)."],
            statement=(
                f"{v.label(pressure.player_id)} got within 3 m of {v.label(reception.player_id)} "  # type: ignore[arg-type]
                f"{gap:.1f} s after {v.short(reception.player_id)} received the ball."  # type: ignore[arg-type]
            ),
        )

    # -- observed: tracking -------------------------------------------------

    def _spells(self) -> list[core.PossessionSpell]:
        return core.possession_spells(self.v.frames, {pid: p.team_id for pid, p in self.v.players.items()})

    def possession_duration(self, team_id: str | None = None) -> list[Fact]:
        v = self.v
        if v.manifest.availability == "event-only" or not v.frames:
            self.refuse("possession_duration", "Possession spells need possession data from tracking.")
            return []
        out = []
        for s in self._spells():
            if team_id and s.team_id != team_id:
                continue
            team = next(t.name for t in v.manifest.teams if t.team_id == s.team_id)
            tail = "and ended when the opponent gained the ball" if s.ended else "and was still going at the data cutoff"
            out.append(
                Fact(
                    fact_id=_fid("possession_duration", [s.team_id], s.start_s),
                    evidence_class="observed",
                    metric="possession_duration",
                    subject_ids=[s.team_id],
                    value=round(s.duration_s, 1),
                    unit="s",
                    time_window=TimeWindow(start_s=s.start_s, end_s=s.end_s),
                    focus_time_s=s.start_s,
                    source_event_ids=[],
                    source_frame_range=(s.start_frame, s.end_frame),
                    method_version=MV["possession_duration"],
                    coverage=_coverage(v, s.end_frame - s.start_frame + 1, s.end_frame - s.start_frame + 1),
                    limitations=[
                        "Spell of this sequence only, from possessor transitions; not match possession share.",
                        *([] if s.ended else ["Lower bound: the spell continues beyond the available data."]),
                    ],
                    statement=f"{team}'s possession from {_fmt_t(v, s.start_s)} lasted {s.duration_s:.1f} s {tail}.",
                )
            )
        return out

    def tracked_running(self, player_id: str, start_s: float, end_s: float) -> Fact | None:
        v = self.v
        if v.manifest.availability == "event-only":
            self.refuse("tracked_running", "Event-only data has no tracking, so running distance cannot be measured.", [player_id])
            return None
        frames = [f for f in v.frames if start_s - 1e-6 <= f.time_s <= end_s + 1e-6]
        if len(frames) < 2:
            self.refuse("tracked_running", "Fewer than two tracking frames in the window.", [player_id])
            return None
        try:
            r = core.tracked_running(frames, player_id, v.manifest.frame_rate_hz)
        except core.TrackingError as exc:
            self.refuse("tracked_running", f"Tracking timestamps are invalid ({exc}).", [player_id])
            return None
        if r.intervals_used == 0:
            self.refuse("tracked_running", "No usable tracking samples for this player.", [player_id])
            return None
        partial = r.intervals_used < r.intervals_expected
        note = f"{r.gaps} gap(s) not bridged; distance is a lower bound." if partial else None
        top = f", top speed {r.top_speed_ms:.1f} m/s" if r.top_speed_ms is not None else ""
        return Fact(
            fact_id=_fid("tracked_running", [player_id], end_s),
            evidence_class="observed",
            metric="tracked_running",
            subject_ids=[player_id],
            value=round(r.distance_m, 1),
            unit="m",
            time_window=TimeWindow(start_s=frames[0].time_s, end_s=frames[-1].time_s),
            focus_time_s=frames[0].time_s,
            source_event_ids=[],
            source_frame_range=(frames[0].frame_id, frames[-1].frame_id),
            method_version=MV["tracked_running"],
            coverage=_coverage(v, r.intervals_used, r.intervals_expected, note),
            limitations=[TRACKING_LIMIT, "Speed from frame-to-frame displacement over 0.1 s intervals."],
            statement=(
                f"{v.label(player_id)} covered {r.distance_m:.1f} m between {_fmt_t(v, frames[0].time_s)} "
                f"and {_fmt_t(v, frames[-1].time_s)}{top}."
            ),
        )

    def defender_distance(self, defender_id: str, carrier_id: str, t: float, moment: str, source: MatchEvent | None = None) -> Fact | None:
        v = self.v
        f = _frame(v, t)
        if f is None:
            self.refuse("defender_distance", "No tracking frame at that moment.", [defender_id, carrier_id])
            return None
        pos = {p.player_id: (p.x, p.y) for p in f.players}
        if defender_id not in pos or carrier_id not in pos:
            self.refuse("defender_distance", "A player is missing from the tracking frame.", [defender_id, carrier_id])
            return None
        d = core.dist(pos[defender_id], pos[carrier_id])
        return Fact(
            fact_id=_fid("defender_distance", [defender_id, carrier_id], f.time_s),
            evidence_class="observed",
            metric="defender_distance",
            subject_ids=[defender_id, carrier_id],
            value=round(d, 1),
            unit="m",
            time_window=TimeWindow(start_s=f.time_s, end_s=f.time_s),
            focus_time_s=f.time_s,
            source_event_ids=[source.event_id] if source else [],
            source_frame_range=(f.frame_id, f.frame_id),
            method_version=MV["defender_distance"],
            coverage=_coverage(v, 1, 1),
            limitations=[TRACKING_LIMIT],
            statement=f"{v.label(defender_id)} was {d:.1f} m from {v.label(carrier_id)} {moment} ({_fmt_t(v, f.time_s)}).",
        )

    # -- estimated ----------------------------------------------------------

    def lane_access(self, passer_id: str, receiver_id: str, t: float, source: MatchEvent | None = None) -> Fact | None:
        """How close the nearest defender was to cutting a passer→receiver lane."""
        v = self.v
        f = _frame(v, t)
        if f is None:
            self.refuse("lane_access", "Lane access needs tracking positions.", [passer_id, receiver_id])
            return None
        pos = {p.player_id: (p.x, p.y) for p in f.players}
        team = v.team_of(passer_id)
        defenders = {
            pid: xy for pid, xy in pos.items() if v.team_of(pid) != team and v.players[pid].role != "GK"
        }
        access = core.lane_access(pos[passer_id], pos[receiver_id], defenders)
        top = access[0]
        verdict = "could reach the lane before the ball" if top.margin_s > 0 else "could not reach the lane before the ball"
        return Fact(
            fact_id=_fid("lane_access", [passer_id, receiver_id], f.time_s),
            evidence_class="estimated",
            metric="lane_access",
            subject_ids=[passer_id, receiver_id, top.defender_id],
            value=round(top.margin_s, 2),
            unit="s (ball time − defender time; > 0 means defender first)",
            time_window=TimeWindow(start_s=f.time_s, end_s=f.time_s),
            focus_time_s=f.time_s,
            source_event_ids=[source.event_id] if source else [],
            source_frame_range=(f.frame_id, f.frame_id),
            method_version=MV["lane_access"],
            coverage=_coverage(v, 1, 1),
            limitations=[
                f"Prototype heuristic: defender needs {core.DEFENDER_REACTION} s to react, closes at {core.DEFENDER_SPEED} m/s, "
                f"reaches {core.DEFENDER_REACH} m; pass travels at {core.PASS_SPEED} m/s in a straight line.",
                "Not a calibrated probability. Ignores body orientation and anticipation.",
            ],
            statement=(
                f"Estimate: the defender best placed to cut the {v.short(passer_id)} → {v.short(receiver_id)} lane "
                f"was {v.label(top.defender_id)}, {top.distance_to_lane_m:.1f} m away, who by the reachability "
                f"heuristic {verdict} (margin {top.margin_s:+.2f} s)."
            ),
        )

    def open_lanes(self, carrier_id: str, t: float, source: MatchEvent | None = None) -> Fact | None:
        v = self.v
        f = _frame(v, t)
        if f is None:
            self.refuse("open_lanes", "Passing lanes need tracking positions.", [carrier_id])
            return None
        pos = {p.player_id: (p.x, p.y) for p in f.players}
        team = v.team_of(carrier_id)
        mates = [pid for pid in pos if v.team_of(pid) == team and pid != carrier_id and v.players[pid].role != "GK"]
        defenders = {pid: xy for pid, xy in pos.items() if v.team_of(pid) != team and v.players[pid].role != "GK"}
        open_ids = [m for m in mates if core.lane_is_open(core.lane_access(pos[carrier_id], pos[m], defenders))]
        names = ", ".join(f"#{v.players[m].number}" for m in sorted(open_ids, key=lambda m: v.players[m].number)) or "none"
        return Fact(
            fact_id=_fid("open_lanes", [carrier_id], f.time_s),
            evidence_class="estimated",
            metric="open_lanes",
            subject_ids=[carrier_id, *open_ids],
            value=len(open_ids),
            unit=f"of {len(mates)} outfield teammates",
            time_window=TimeWindow(start_s=f.time_s, end_s=f.time_s),
            focus_time_s=f.time_s,
            source_event_ids=[source.event_id] if source else [],
            source_frame_range=(f.frame_id, f.frame_id),
            method_version=MV["open_lanes"],
            coverage=_coverage(v, 1, 1),
            limitations=[
                "Prototype reachability heuristic for straight ground passes (see lane_access/1).",
                "Counts lanes no defender can reach first; ignores offside, pass difficulty and receiver pressure.",
            ],
            statement=(
                f"Estimate: at {_fmt_t(v, f.time_s)} {v.label(carrier_id)} had {len(open_ids)} of {len(mates)} "
                f"outfield teammates in open passing lanes ({names})."
            ),
        )
