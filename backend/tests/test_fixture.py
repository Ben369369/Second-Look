import copy
import json
import math

import pytest

from app.config import BACKEND_ROOT
from app.data.generator import PRESSURE_OFF, PRESSURE_ON, HeroConfig, generate
from app.data.loader import load_scenario
from app.data.validation import validate_fixture
from app.schemas import MatchEvent, ScenarioManifest, TrackingFrame

HERO_DIR = BACKEND_ROOT / "fixtures" / "development" / "rb_press_hero"


@pytest.fixture(scope="module")
def hero():
    return generate(HeroConfig())


def _typed(manifest, frames, events):
    return (
        ScenarioManifest.model_validate(manifest),
        [TrackingFrame.model_validate(f) for f in frames],
        [MatchEvent.model_validate(e) for e in events],
    )


def test_same_seed_same_dataset(hero):
    again = generate(HeroConfig())
    assert again[0]["dataset_hash"] == hero[0]["dataset_hash"]


def test_different_seed_changes_dataset(hero):
    other = generate(HeroConfig(seed=7))
    assert other[0]["dataset_hash"] != hero[0]["dataset_hash"]


def test_committed_fixture_matches_generator(hero):
    """Catches generator edits that were not followed by scripts/generate_fixtures.py."""
    on_disk = json.loads((HERO_DIR / "manifest.json").read_text(encoding="utf-8"))
    assert on_disk["dataset_hash"] == hero[0]["dataset_hash"]
    load_scenario(HERO_DIR)  # schema + hash + validity


def test_generated_fixture_is_valid(hero):
    assert validate_fixture(*_typed(*hero)) == []


def test_sequence_length_and_roster(hero):
    manifest, frames, _ = hero
    assert 20.0 <= manifest["duration_s"] <= 40.0
    assert all(len(f["players"]) == 22 for f in frames)
    assert all(f["ball"] is not None for f in frames)


def test_validator_detects_teleport(hero):
    manifest, frames, events = copy.deepcopy(hero)
    frames[50]["players"][3]["x"] += 5.0  # 5 m in 0.1 s = 50 m/s
    issues = validate_fixture(*_typed(manifest, frames, events))
    assert any("speed" in i for i in issues)


def test_validator_detects_out_of_bounds_and_bad_timestamps(hero):
    manifest, frames, events = copy.deepcopy(hero)
    frames[10]["players"][0]["y"] = 70.0
    frames[20]["time_s"] = frames[19]["time_s"]
    issues = validate_fixture(*_typed(manifest, frames, events))
    assert any("out of bounds" in i for i in issues)
    assert any("non-increasing" in i for i in issues)


def test_validator_detects_unexplained_possession_change(hero):
    manifest, frames, events = copy.deepcopy(hero)
    events = [e for e in events if e["type"] != "reception"]
    issues = validate_fixture(*_typed(manifest, frames, events))
    assert any("without a reception" in i for i in issues)


def test_pass_endpoints_agree_with_tracking(hero):
    _, frames, events = hero
    for e in events:
        if e["type"] != "pass":
            continue
        start_frame = frames[e["related_frame_ids"][0]]
        end_frame = frames[e["related_frame_ids"][-1]]
        ball0, ball1 = start_frame["ball"], end_frame["ball"]
        assert math.dist((ball0["x"], ball0["y"]), (e["start_position"]["x"], e["start_position"]["y"])) < 0.05
        assert math.dist((ball1["x"], ball1["y"]), (e["end_position"]["x"], e["end_position"]["y"])) < 0.05
        # The recipient holds the ball on the frame after the reception frame.
        assert frames[e["related_frame_ids"][-1] + 1]["ball"]["possession_player_id"] == e["recipient_id"]


def test_pressure_events_match_distance_thresholds(hero):
    _, frames, events = hero
    for e in events:
        if e["type"] not in ("pressure_start", "pressure_end"):
            continue
        f = frames[e["related_frame_ids"][-1]]
        pos = {p["player_id"]: (p["x"], p["y"]) for p in f["players"]}
        d = math.dist(pos[e["player_id"]], pos[e["related_player_ids"][0]])
        if e["type"] == "pressure_start":
            assert d <= PRESSURE_ON + 1e-6
        else:
            # Ends either by distance or because the carrier released the ball.
            released = any(
                x["type"] in ("pass", "shot") and x["time_s"] == e["time_s"] and x["player_id"] == e["related_player_ids"][0]
                for x in events
            )
            assert released or d > PRESSURE_OFF


def test_hero_contains_the_investigated_moment(hero):
    """The right-back press on the winger, followed by the inside pass, must exist."""
    _, _, events = hero
    press = [e for e in events if e["type"] == "pressure_start" and e["player_id"] == "CED-02"]
    inside = [e for e in events if e["type"] == "pass" and e["player_id"] == "HAR-11" and e["recipient_id"] == "HAR-08"]
    assert press and inside and press[0]["time_s"] < inside[0]["time_s"]
