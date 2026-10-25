"""Metric checks against tiny hand-calculated inputs, plus cutoff (future-leakage) guards."""

import pytest

from app.config import load_settings
from app.data.loader import ScenarioRegistry
from app.investigations.questions import ask
from app.metrics import core
from app.metrics.facts import FactBuilder
from app.metrics.view import make_view
from app.schemas import BallState, MatchEvent, PlayerState, Position, TrackingFrame


@pytest.fixture(scope="module")
def hero():
    return ScenarioRegistry(load_settings().fixtures_dir).get("rb_press_hero")


def _frame(fid, t, x, y, holder="A1"):
    return TrackingFrame(
        frame_id=fid,
        time_s=t,
        ball=BallState(x=x, y=y, z=0, vx=0, vy=0, possession_player_id=holder),
        players=[PlayerState(player_id="A1", team_id="A", x=x, y=y, vx=0, vy=0, observed_fields=["x", "y"])],
    )


def _pass(outcome, start=(0, 0), end=(3, 4)):
    return MatchEvent(
        event_id="e", scenario_id="s", time_s=0, type="pass", team_id="A", player_id="A1", recipient_id="A2",
        start_position=Position(x=start[0], y=start[1]),
        end_position=Position(x=end[0], y=end[1]) if end else None,
        outcome=outcome, related_frame_ids=[0],
    )


# -- hand-calculated -----------------------------------------------------------


def test_pass_distance_3_4_5():
    assert core.pass_distance(_pass("complete")) == pytest.approx(5.0)
    assert core.pass_distance(_pass(None, end=None)) is None


def test_pass_completion_excludes_unknown_outcomes():
    c = core.pass_completion([_pass("complete"), _pass("incomplete"), _pass(None)])
    assert (c.completed, c.attempted, c.unknown) == (1, 2, 1)
    assert c.rate == pytest.approx(0.5)
    assert core.pass_completion([]).rate is None  # zero denominator


def test_running_distance_and_speed_interval():
    # Two 0.1 s steps of (0.3, 0.4): 0.5 m each -> 1.0 m, 5.0 m/s.
    frames = [_frame(0, 0.0, 0, 0), _frame(1, 0.1, 0.3, 0.4), _frame(2, 0.2, 0.6, 0.8)]
    r = core.tracked_running(frames, "A1", 10)
    assert r.distance_m == pytest.approx(1.0)
    assert r.top_speed_ms == pytest.approx(5.0)
    assert (r.intervals_used, r.intervals_expected, r.gaps) == (2, 2, 0)


def test_running_does_not_bridge_gaps_and_rejects_bad_timestamps():
    frames = [_frame(0, 0.0, 0, 0), _frame(1, 0.1, 0.3, 0.4), _frame(5, 0.5, 9.0, 9.0)]
    r = core.tracked_running(frames, "A1", 10)
    assert r.distance_m == pytest.approx(0.5)  # the 0.4 s jump is skipped, not counted
    assert (r.intervals_used, r.intervals_expected, r.gaps) == (1, 5, 1)
    with pytest.raises(core.TrackingError):
        core.tracked_running([_frame(0, 0.0, 0, 0), _frame(1, 0.0, 1, 1)], "A1", 10)


def test_possession_spells_from_transitions():
    frames = [
        _frame(0, 0.0, 0, 0, "A1"),
        _frame(1, 0.1, 0, 0, "A1"),
        _frame(2, 0.2, 0, 0, None),  # loose ball stays with the previous team
        _frame(3, 0.3, 0, 0, "B1"),
        _frame(4, 0.4, 0, 0, "B1"),
    ]
    spells = core.possession_spells(frames, {"A1": "A", "B1": "B"})
    assert [(s.team_id, s.start_s, s.end_s, s.ended) for s in spells] == [("A", 0.0, 0.3, True), ("B", 0.3, 0.4, False)]
    assert spells[0].duration_s == pytest.approx(0.3)


def test_lane_access_heuristic():
    # Lane (0,0)->(14,0); closest point is the midpoint, ball arrives after 7/14 = 0.5 s.
    far = core.lane_access((0, 0), (14, 0), {"D": (7, 3)})[0]
    assert far.defender_time_s == pytest.approx(0.25 + 2 / 7)
    assert far.margin_s == pytest.approx(0.5 - (0.25 + 2 / 7))
    assert core.lane_is_open([far])
    near = core.lane_access((0, 0), (14, 0), {"D": (7, 1.5)})[0]
    assert near.margin_s == pytest.approx(0.5 - (0.25 + 0.5 / 7))
    assert not core.lane_is_open([near])


def test_attacking_direction_normalisation():
    assert core.normalised_x(95.0, 1, 105.0) == 95.0
    assert core.normalised_x(95.0, -1, 105.0) == pytest.approx(10.0)


# -- availability -------------------------------------------------------------


def test_event_only_refuses_tracked_metrics(hero):
    m = hero.manifest.model_copy(update={"availability": "event-only"})
    view = make_view(hero.model_copy(update={"manifest": m, "frames": []}))
    b = FactBuilder(view)
    assert b.tracked_running("CED-02", 0, 20) is None
    assert b.possession_duration() == []
    assert {r.metric for r in b.refused} == {"tracked_running", "possession_duration"}
    first_pass = next(e for e in view.events if e.type == "pass")
    assert b.pass_distance(first_pass) is not None  # event metrics still work


# -- cutoff / future leakage ------------------------------------------------------


def test_view_hides_future_outcomes(hero):
    # Rossi -> Kiprono is played at 13.7 s and received at 14.6 s.
    view = make_view(hero, 14.0)
    p = next(e for e in view.events if e.type == "pass" and e.player_id == "HAR-11")
    assert p.outcome is None and p.end_position is None
    assert max(f.time_s for f in view.frames) <= 14.0
    assert all(e.time_s <= 14.0 for e in view.events)


@pytest.mark.parametrize("cursor", [5.0, 12.0, 14.0, 17.0])
@pytest.mark.parametrize("question", ["Should the right-back have pressed earlier?", "What passing options did Rossi have?", "How long did Harbor keep the ball?", "How far did Halvorsen run?"])
def test_answers_never_use_data_after_cursor(hero, cursor, question):
    res = ask(make_view(hero, cursor), question)
    future_events = {e.event_id for e in hero.events if e.time_s > cursor}
    cutoff_frame = max(f.frame_id for f in hero.frames if f.time_s <= cursor + 1e-6)
    for f in res.facts:
        assert f.time_window.end_s <= cursor + 1e-6
        assert not set(f.source_event_ids) & future_events
        if f.source_frame_range:
            assert f.source_frame_range[1] <= cutoff_frame


def test_facts_point_at_their_frames(hero):
    """Clicking a fact seeks to focus_time_s; that must be the frame the value was measured on."""
    res = ask(make_view(hero), "Should the right-back have pressed earlier?")
    by_id = {f.frame_id: f for f in hero.frames}
    tracked = [f for f in res.facts if f.metric in ("defender_distance", "open_lanes", "lane_access")]
    assert tracked
    for f in tracked:
        assert by_id[f.source_frame_range[0]].time_s == pytest.approx(f.focus_time_s)
    # Independently recompute one distance from raw frame data.
    d = next(f for f in res.facts if f.metric == "defender_distance")
    frame = by_id[d.source_frame_range[0]]
    pos = {p.player_id: (p.x, p.y) for p in frame.players}
    assert d.value == pytest.approx(core.dist(pos[d.subject_ids[0]], pos[d.subject_ids[1]]), abs=0.05)


def test_answer_sentences_only_cite_returned_facts(hero):
    res = ask(make_view(hero), "Should the right-back have pressed earlier?")
    ids = {f.fact_id for f in res.facts}
    assert res.answer and all(s.fact_ids and set(s.fact_ids) <= ids for s in res.answer)
    # Every number in a statement came from the fact's own value.
    for f in res.facts:
        if f.metric in ("pass_distance", "defender_distance", "response_time", "tracked_running", "possession_duration"):
            assert f"{f.value:.1f}" in f.statement


def test_router_unsupported_and_clarify(hero):
    view = make_view(hero)
    assert ask(view, "Who will win the league?").status == "unsupported"
    res = ask(view, "How far did #2 run?")
    assert res.status == "clarify" and "Halvorsen" in res.notes[0] and "Abara" in res.notes[0]
    assert ask(view, "How far did Cedar #2 run?").status == "answered"
