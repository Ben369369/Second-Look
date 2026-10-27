"""Regenerate development and held-out evaluation fixtures deterministically.

Usage (from the repo root):
    backend/.venv/Scripts/python.exe scripts/generate_fixtures.py      # Windows
    backend/.venv/bin/python scripts/generate_fixtures.py              # macOS/Linux

Evaluation fixtures (backend/fixtures/evaluation) are never served by the app: the
scenario registry only reads backend/fixtures/development. Their expected behaviour
is declared here, before any evaluation run, and written to _expected.json, which no
runtime code or agent reads.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.data.generator import HeroConfig, write_fixture  # noqa: E402
from app.data.loader import load_scenario  # noqa: E402

DEVELOPMENT = [HeroConfig()]

NEUTRAL = dict(title="Evaluation sequence", description="Synthetic right-flank build-up (held-out evaluation variant).")

# (id, seed, right-back press delay after the winger's reception, recorded cover delay, event-only, expected class)
EVALUATION = [
    ("ev01", 23, 1.4, None, False, "press_recorded"),
    ("ev02", 41, 1.4, None, False, "press_recorded"),
    ("ev03", 67, 1.4, None, False, "press_recorded"),
    ("ev04", 97, 1.4, None, False, "press_recorded"),
    ("ev05", 11, 0.4, None, False, "press_recorded"),
    ("ev06", 53, 0.4, None, False, "press_recorded"),
    ("ev07", 79, 0.4, None, False, "press_recorded"),
    ("ev08", 23, 0.6, 0.3, False, "press_recorded"),
    ("ev09", 67, 0.6, 0.3, False, "press_recorded"),
    ("ev10", 11, 2.2, None, False, "no_press_recorded"),
    ("ev11", 97, 2.2, None, False, "no_press_recorded"),
    ("ev12", 53, 1.4, None, True, "event_only"),
]

EXPECTED = {
    "press_recorded": "Answer the pressing question with observed, estimated and simulated facts; the simulated finding follows the predeclared rule.",
    "no_press_recorded": "Abstain on the pressing question (no pressing moment exists); no simulated claims.",
    "event_only": "Refuse tracked and spatial metrics and the simulation; event-based facts only; no simulated claims.",
}


def main() -> None:
    dev_root = ROOT / "backend" / "fixtures" / "development"
    for cfg in DEVELOPMENT:
        out = write_fixture(cfg, dev_root)
        b = load_scenario(out)  # re-load: schema, hash, and validity checks
        print(f"{b.manifest.scenario_id}: {b.manifest.frame_count} frames, {len(b.events)} events, {b.manifest.dataset_hash[:19]}...")

    eval_root = ROOT / "backend" / "fixtures" / "evaluation"
    expected = {}
    for sid, seed, press, cover, event_only, cls in EVALUATION:
        cfg = HeroConfig(scenario_id=sid, seed=seed, rb_press_delay_s=press, cover_delay_s=cover, **NEUTRAL)
        out = write_fixture(cfg, eval_root, event_only=event_only)
        b = load_scenario(out)
        expected[sid] = {"class": cls, "expected": EXPECTED[cls], "seed": seed, "rb_press_delay_s": press, "cover_delay_s": cover, "event_only": event_only}
        print(f"{sid}: {b.manifest.availability}, {b.manifest.frame_count} frames, {len(b.events)} events")
    (eval_root / "_expected.json").write_text(json.dumps(expected, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
