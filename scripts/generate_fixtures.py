"""Regenerate development fixtures deterministically.

Usage (from the repo root):
    backend/.venv/Scripts/python.exe scripts/generate_fixtures.py      # Windows
    backend/.venv/bin/python scripts/generate_fixtures.py              # macOS/Linux
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.data.generator import HeroConfig, write_fixture  # noqa: E402
from app.data.loader import load_scenario  # noqa: E402

DEVELOPMENT = [HeroConfig()]


def main() -> None:
    out_root = ROOT / "backend" / "fixtures" / "development"
    for cfg in DEVELOPMENT:
        out = write_fixture(cfg, out_root)
        bundle = load_scenario(out)  # re-load: schema, hash, and validity checks
        m = bundle.manifest
        print(f"{m.scenario_id}: {m.frame_count} frames, {len(bundle.events)} events, {m.dataset_hash[:19]}...")


if __name__ == "__main__":
    main()
