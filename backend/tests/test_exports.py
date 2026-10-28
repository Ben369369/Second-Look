"""Audience modes, recap and overlay export (spec §13 audience modes, §14 export, §16 UI/export checks)."""

import pytest
from fastapi.testclient import TestClient

from app.agents.validate import validate_claims
from app.config import load_settings
from app.data.loader import ScenarioRegistry
from app.exports.overlay import CueError, build_export, validate_export
from app.main import create_app

QUESTION = "Should the right-back have pressed earlier?"


@pytest.fixture(scope="module")
def client():
    return TestClient(create_app())


@pytest.fixture(scope="module")
def bundle():
    return ScenarioRegistry(load_settings().fixtures_dir).get("rb_press_hero")


def _investigate(client, audience, question=QUESTION):
    r = client.post("/api/investigations", json={"question": question, "audience": audience})
    assert r.status_code == 200
    return r.json()


def test_audiences_share_the_same_facts(client, bundle):
    casual, analyst = _investigate(client, "casual"), _investigate(client, "analyst")
    c_facts = {f["fact_id"]: f for f in casual["facts"]}
    a_facts = {f["fact_id"]: f for f in analyst["facts"]}
    assert c_facts.keys() == a_facts.keys()
    assert all(c_facts[k]["value"] == a_facts[k]["value"] for k in c_facts)
    cited = {i for c in casual["casual_claims"] for i in c["fact_ids"]}
    assert cited <= a_facts.keys()
    # Casual is shorter and plainer, but every claim still passes the same validator.
    assert len(casual["casual_claims"]) < len(analyst["claims"])
    assert not casual["rejected_claims"]
    assert any(c["claim_type"] == "interpretation" for c in casual["casual_claims"])  # the caveat
    # Whichever audience was selected when asking, both presentations exist.
    assert casual["claims"] and analyst["casual_claims"]


def test_casual_numbers_are_identical_to_analyst_numbers(client, bundle):
    from app.schemas import Claim, Fact

    casual = _investigate(client, "casual")
    facts = {f["fact_id"]: Fact.model_validate(f) for f in casual["facts"]}
    players = {p.player_id: p for t in bundle.manifest.teams for p in t.players}
    ok, bad = validate_claims([Claim.model_validate(c) for c in casual["casual_claims"]], facts, players)
    assert not bad and len(ok) == len(casual["casual_claims"])


@pytest.mark.parametrize("audience", ["casual", "analyst"])
def test_export_is_timed_labelled_and_traceable(client, audience):
    state = _investigate(client, audience)
    r = client.get(f"/api/investigations/{state['investigation_id']}/export")
    assert r.status_code == 200
    out = r.json()
    cues = out["cues"]
    assert 2 <= len(cues) <= 4 and out["timebase"] == "sequence_s" and out["synthetic_data"] is True
    assert out["recap_duration_s"] == pytest.approx(out["sequence_duration_s"] / out["playback_rate"], abs=0.1)
    assert 30 <= out["recap_duration_s"] <= 60
    facts = {f["fact_id"]: f for f in state["facts"]}
    approved = {c["text"] for c in state["casual_claims" if audience == "casual" else "claims"]}
    prev_end = 0.0
    for cue in cues:
        assert cue["start_s"] >= prev_end - 1e-6 and cue["duration_s"] > 0
        assert cue["start_s"] + cue["duration_s"] <= out["sequence_duration_s"] + 1e-6
        prev_end = cue["start_s"] + cue["duration_s"]
        assert set(cue["fact_ids"]) <= facts.keys()
        assert all(line in approved for line in cue["body"].split("\n"))
        assert cue["source_run_id"] == state["investigation_id"] and cue["audience"] == audience
        if cue["evidence_class"] == "simulated":
            assert cue["branch"] == "simulated" and "SIMULATION" in cue["title"] and cue["simulation_run_ids"]
        else:
            t = min(facts[i]["focus_time_s"] for i in cue["fact_ids"])
            assert cue["start_s"] <= t + 1.0 and t - 0.5 <= cue["start_s"] + cue["duration_s"]


def test_export_validator_rejects_tampering(client, bundle):
    from app.schemas import InvestigationState

    state = InvestigationState.model_validate(_investigate(client, "analyst"))
    good = build_export(state, bundle)

    def mutate(i, **upd):
        cues = list(good.cues)
        cues[i] = cues[i].model_copy(update=upd)
        return good.model_copy(update={"cues": cues})

    sim_i = next(i for i, c in enumerate(good.cues) if c.evidence_class == "simulated")
    rec_i = next(i for i, c in enumerate(good.cues) if c.branch == "recorded")
    for bad in (
        mutate(rec_i, body=good.cues[rec_i].body.replace("8.5", "4.5")),  # altered number
        mutate(sim_i, title="Alternative choices"),  # simulation label removed
        mutate(rec_i, start_s=0.0, duration_s=1.0),  # off its moment
        mutate(rec_i, fact_ids=["made-up"]),  # unknown reference
        mutate(len(good.cues) - 1, duration_s=60.0),  # runs past the sequence
    ):
        with pytest.raises(CueError):
            validate_export(bad, state, bundle)


def test_export_errors(client):
    assert client.get("/api/investigations/nope/export").status_code == 404


def test_fan_started_investigation_exports_both_audiences(client):
    state = _investigate(client, "casual")
    for audience in ("analyst", "casual"):
        r = client.get(f"/api/investigations/{state['investigation_id']}/export", params={"audience": audience})
        assert r.status_code == 200 and r.json()["audience"] == audience
