"""Simulator risks that could invalidate the demonstration (spec §16, simulation tests)."""

import numpy as np
import pytest

from app.config import load_settings
from app.data.loader import ScenarioRegistry
from app.schemas import ChallengeRequest, CompareRequest
from app.simulation.compare import challenge, compare, decide
from app.simulation.engine import ACTIONS, DT, VMAX, SimConfig, Simulator, default_branch
from app.simulation.stats import paired_bootstrap, wilson

SMALL = SimConfig(rollouts=64)


@pytest.fixture(scope="module")
def bundle():
    return ScenarioRegistry(load_settings().fixtures_dir).get("rb_press_hero")


@pytest.fixture(scope="module")
def sim(bundle):
    return Simulator(bundle, default_branch(bundle, "CED-02"), "CED-02")


@pytest.fixture(scope="module")
def runs(sim):
    return {a: sim.run(a, SMALL) for a in ACTIONS}


def test_branch_is_the_pass_trigger_and_roles_come_from_geometry(bundle, sim):
    b = sim.branch
    pass_ev = next(e for e in bundle.events if e.type == "pass" and e.recipient_id == "HAR-11")
    assert b.frame_id == pass_ev.related_frame_ids[0] + 1  # first frame with the ball travelling
    assert (b.carrier, b.presser, b.cover, b.inside_option) == ("HAR-11", "CED-02", "CED-06", "HAR-08")


def test_same_seed_same_results(sim, runs):
    again = sim.run("press_with_cover", SMALL)
    ref = runs["press_with_cover"]
    assert np.array_equal(again.danger, ref.danger) and np.array_equal(again.pos, ref.pos)


def test_all_actions_start_from_the_recorded_state(bundle, sim, runs):
    frame = next(f for f in bundle.frames if f.frame_id == sim.branch.frame_id)
    recorded = np.array([[p.x, p.y] for p in frame.players])
    for r in runs.values():
        assert np.allclose(r.pos[0], recorded)


def test_no_teleporting(runs):
    for r in runs.values():
        step = np.linalg.norm(np.diff(r.pos, axis=0), axis=-1)
        assert step.max() <= VMAX * DT + 1e-6
        ball_step = np.linalg.norm(np.diff(r.ball, axis=0), axis=-1)
        assert ball_step.max() < 3.0  # ground-pass speed, or a short snap onto a receiver's foot


def test_opponents_respond_to_the_intervention(sim):
    """Changing only the presser changes the attacking carrier's choices: with identical random draws,
    the distribution of the winger's first pass shifts when the right-back presses instead of holding."""
    cfg = SimConfig(rollouts=200)
    c = sim.ids.index(sim.branch.carrier)

    def first_targets(action):
        r = sim.run(action, cfg)
        out = []
        for ev in r.events:
            first = next((e for e in ev if e[1] in ("pass", "pass_intercepted") and e[2] == c), None)
            out.append(first[3] if first else -1)
        return np.array(out)

    hold, press = first_targets("hold"), first_targets("press_earlier")
    keys = set(hold) | set(press)
    tv = 0.5 * sum(abs((hold == k).mean() - (press == k).mean()) for k in keys)
    assert tv > 0.1
    assert (hold != press).mean() > 0.1  # the same trial, same draws, different choice


def test_cover_delay_acts_only_through_the_cover_player(sim, runs):
    # A cover that never starts within the horizon must reproduce press_earlier exactly (paired randomness).
    never = sim.run("press_with_cover", SimConfig(rollouts=64, cover_delay_s=99.0))
    assert np.array_equal(never.pos, runs["press_earlier"].pos)
    # An early cover moves the cover player differently, and that changes outcomes.
    early = runs["press_with_cover"]
    k = sim.ids.index(sim.branch.cover)
    assert not np.allclose(early.pos[15, :, k], never.pos[15, :, k])
    assert not np.array_equal(early.danger, never.danger)


def test_recorded_future_is_never_read(bundle, sim):
    """Corrupting every frame after the branch must not change any rollout."""
    ref = sim.run("press_earlier", SMALL)
    bf = sim.branch.frame_id
    frames = [
        f if f.frame_id <= bf else f.model_copy(update={"players": [p.model_copy(update={"x": 1.0, "y": 1.0}) for p in f.players]})
        for f in bundle.frames
    ]
    corrupted = bundle.model_copy(update={"frames": frames, "events": [e for e in bundle.events if e.time_s <= sim.branch.time_s]})
    other = Simulator(corrupted, bf, "CED-02").run("press_earlier", SMALL)
    assert np.array_equal(ref.pos, other.pos) and np.array_equal(ref.danger, other.danger)


def test_rates_are_actual_counts(bundle):
    res = compare(bundle, CompareRequest(rollouts=64))
    for a in res.actions:
        assert a.danger.n == 64 and a.danger.rate == pytest.approx(a.danger.count / 64)
        assert a.danger.ci95[0] <= a.danger.rate <= a.danger.ci95[1]
    assert {s.action for s in res.samples} == set(ACTIONS)


def test_interval_sanity():
    assert wilson(5, 10) == pytest.approx((0.2366, 0.7634), abs=1e-4)
    assert wilson(0, 10)[0] == 0.0
    same = np.array([0, 1, 1, 0, 1] * 20)
    assert paired_bootstrap(same, same) == (0.0, (0.0, 0.0))
    # b is a strictly better copy of a on 30 of 100 paired trials: diff exactly 0.3, interval brackets it.
    a = np.zeros(100)
    b = np.zeros(100)
    b[:30] = 1
    d, (lo, hi) = paired_bootstrap(a, b, seed=1)
    assert d == pytest.approx(0.3) and lo < 0.3 < hi and lo > 0.15


def test_decision_rule_needs_enough_rollouts_and_a_margin(sim):
    tiny = {a: sim.run(a, SimConfig(rollouts=32)) for a in ACTIONS}
    rec, _ = decide(tiny, seed=0)
    assert rec.status == "inconclusive"


def test_challenger_respects_bounds_and_can_find_no_winner(bundle):
    req = ChallengeRequest(cover_delays=[0.0, 0.6, 1.2], attacker_policies=["patient"], rollouts=64)
    res = challenge(bundle, req)
    assert len(res.cells) == 3
    assert {c.cover_delay_s for c in res.cells} == {0.0, 0.6, 1.2}
    assert "0, 0.6, 1.2" in res.tested_domain and "64 rollouts" in res.tested_domain
    statuses = {c.status for c in res.cells} | {res.baseline.status}
    assert "no_clear_winner" in statuses  # the app does not always pick a winner
