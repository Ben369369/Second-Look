"""A read-only view of a sequence that cannot see past its cutoff.

Every metric reads data through a SequenceView. Frames after the cutoff are
dropped, and events are rewritten to what was knowable at the cutoff: a pass
whose reception happens later has no outcome or end position yet, and a carry
still in progress has no end position.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.schemas import MatchEvent, Player, ReplayBundle, ScenarioManifest, TrackingFrame

EPS = 1e-6


@dataclass(frozen=True)
class SequenceView:
    manifest: ScenarioManifest
    frames: list[TrackingFrame]
    events: list[MatchEvent]
    cursor_s: float
    players: dict[str, Player] = field(default_factory=dict)

    @property
    def scenario_id(self) -> str:
        return self.manifest.scenario_id

    def team_of(self, player_id: str) -> str:
        return self.players[player_id].team_id

    def direction(self, team_id: str) -> int:
        for d in self.manifest.attacking_directions:
            if d.team_id == team_id and d.period == self.manifest.period:
                return 1 if d.direction == "+x" else -1
        raise KeyError(f"no attacking direction for {team_id}")

    def frame_at(self, t: float) -> TrackingFrame | None:
        """Last frame at or before t (None if no tracking or t precedes the data)."""
        best = None
        for f in self.frames:
            if f.time_s <= t + EPS:
                best = f
            else:
                break
        return best

    def short(self, player_id: str) -> str:
        p = self.players.get(player_id)
        return f"#{p.number} {p.name.split()[-1]}" if p else player_id

    def label(self, player_id: str) -> str:
        p = self.players.get(player_id)
        if p is None:
            return player_id
        team = next((t.name for t in self.manifest.teams if t.team_id == p.team_id), p.team_id)
        return f"{team} #{p.number} {p.name}"


def make_view(bundle: ReplayBundle, cursor_s: float | None = None) -> SequenceView:
    m = bundle.manifest
    cutoff = m.duration_s if cursor_s is None else min(max(cursor_s, 0.0), m.duration_s)
    frames = [f for f in bundle.frames if f.time_s <= cutoff + EPS]
    events: list[MatchEvent] = []
    for e in bundle.events:
        if e.time_s > cutoff + EPS:
            continue
        # Decide by time, not by frame presence: event-only data has no frames at all.
        related = [fid for fid in e.related_frame_ids if fid / m.frame_rate_hz <= cutoff + EPS]
        truncated = len(related) < len(e.related_frame_ids)
        update: dict = {"related_frame_ids": related}
        if truncated and e.type in ("pass", "shot"):
            update |= {"outcome": None, "end_position": None}
        if truncated and e.type == "carry":
            update |= {"end_position": None}
        events.append(e.model_copy(update=update))
    players = {p.player_id: p for t in m.teams for p in t.players}
    return SequenceView(manifest=m, frames=frames, events=events, cursor_s=cutoff, players=players)
