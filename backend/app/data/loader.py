"""Load and validate scenario fixtures from disk.

Scenario IDs are matched against a registry built from directory names; a
request can never turn into an arbitrary file path.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from app.data.generator import dataset_hash
from app.data.validation import validate_fixture
from app.schemas import MatchEvent, ReplayBundle, ScenarioManifest, TrackingFrame

SCENARIO_ID_RE = re.compile(r"^[a-z0-9_]{1,64}$")


class FixtureError(RuntimeError):
    pass


def _safe_child(base: Path, rel: str) -> Path:
    p = (base / rel).resolve()
    if base.resolve() not in p.parents:
        raise FixtureError(f"fixture path escapes scenario directory: {rel}")
    return p


def load_scenario(directory: Path) -> ReplayBundle:
    manifest = ScenarioManifest.model_validate_json((directory / "manifest.json").read_text(encoding="utf-8"))
    raw_frames = json.loads(_safe_child(directory, manifest.fixture_paths.tracking).read_text(encoding="utf-8"))
    raw_events = json.loads(_safe_child(directory, manifest.fixture_paths.events).read_text(encoding="utf-8"))
    if dataset_hash(raw_frames, raw_events) != manifest.dataset_hash:
        raise FixtureError(f"{manifest.scenario_id}: dataset hash mismatch; regenerate the fixture")
    frames = [TrackingFrame.model_validate(f) for f in raw_frames]
    events = [MatchEvent.model_validate(e) for e in raw_events]
    issues = validate_fixture(manifest, frames, events)
    if issues:
        raise FixtureError(f"{manifest.scenario_id}: {len(issues)} validation issues, first: {issues[0]}")
    return ReplayBundle(manifest=manifest, frames=frames, events=events)


class ScenarioRegistry:
    def __init__(self, root: Path):
        self.root = root
        self._dirs: dict[str, Path] = {}
        if root.is_dir():
            for d in sorted(root.iterdir()):
                if d.is_dir() and SCENARIO_ID_RE.match(d.name) and (d / "manifest.json").is_file():
                    self._dirs[d.name] = d

    def ids(self) -> list[str]:
        return list(self._dirs)

    def get(self, scenario_id: str) -> ReplayBundle | None:
        if not SCENARIO_ID_RE.match(scenario_id) or scenario_id not in self._dirs:
            return None
        return self._load(scenario_id)

    @lru_cache(maxsize=16)
    def _load(self, scenario_id: str) -> ReplayBundle:
        return load_scenario(self._dirs[scenario_id])
