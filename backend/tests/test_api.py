import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture(scope="module")
def client():
    return TestClient(create_app())


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


def test_capabilities_is_offline_and_sanitized(client):
    body = client.get("/api/capabilities").json()
    assert body["provider_mode"] == "offline"
    assert "no language model" in body["provider_label"]
    assert body["synthetic_data_only"] is True
    assert "endpoint" not in str(body).lower()


def test_scenario_list_and_manifest(client):
    summaries = client.get("/api/scenarios").json()
    assert [s["scenario_id"] for s in summaries] == ["rb_press_hero"]
    m = client.get("/api/scenarios/rb_press_hero").json()
    assert m["synthetic"] is True and m["frame_rate_hz"] == 10


def test_replay_bundle(client):
    body = client.get("/api/scenarios/rb_press_hero/replay").json()
    assert len(body["frames"]) == body["manifest"]["frame_count"]
    assert body["events"][0]["event_id"] == "rb_press_hero-e000"


@pytest.mark.parametrize("bad", ["nope", "..%2F..%2Fbackend", "RB_PRESS_HERO", "a" * 65])
def test_unknown_or_unsafe_scenario_ids_are_404(client, bad):
    r = client.get(f"/api/scenarios/{bad}")
    assert r.status_code == 404


def test_question_catalogue(client):
    intents = [q["intent"] for q in client.get("/api/questions").json()]
    assert "press_timing" in intents and len(intents) >= 6


def test_fact_packet_respects_cursor(client):
    body = client.get("/api/scenarios/rb_press_hero/facts", params={"cursor_s": 10}).json()
    assert body["cursor_s"] == 10 and body["facts"]
    assert all(f["time_window"]["end_s"] <= 10 for f in body["facts"])
    assert {f["evidence_class"] for f in body["facts"]} <= {"observed", "estimated"}


def test_fact_packet_rejects_inverted_window(client):
    r = client.get("/api/scenarios/rb_press_hero/facts", params={"start_s": 15, "end_s": 5})
    assert r.status_code == 422 and r.json()["code"] == "invalid_window"


def test_ask_endpoint(client):
    r = client.post("/api/scenarios/rb_press_hero/ask", json={"question": "Should the right-back have pressed earlier?"})
    body = r.json()
    assert r.status_code == 200 and body["status"] == "answered" and body["matched_by"] == "offline-rules"
    assert client.post("/api/scenarios/rb_press_hero/ask", json={"question": ""}).status_code == 422
    assert client.post("/api/scenarios/nope/ask", json={"question": "x"}).status_code == 404
