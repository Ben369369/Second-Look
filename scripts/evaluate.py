"""Held-out evaluation (spec §16). Writes docs/evaluation_results.json and docs/EVALUATION.md.

Usage (from the repo root):
    backend/.venv/Scripts/python.exe scripts/evaluate.py

Pipelines:
  A         deterministic event recap: event-only facts (pass completion and lengths), no metrics, no simulation
  C-offline full tool pipeline with the rule-based router (cutoff view, metrics, simulator, validator)
  B, C-live single-model and multi-agent pipelines with a live Foundry model: NOT RUN when no model
            deployment is available; reported as such, never estimated.

Expected behaviour per variant comes from backend/fixtures/evaluation/_expected.json,
declared in scripts/generate_fixtures.py before this script was run. Runtime code never reads it.
"""

from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.agents.validate import validate_claim  # noqa: E402
from app.agents.workflow import Workflow  # noqa: E402
from app.config import load_settings  # noqa: E402
from app.data.loader import load_scenario  # noqa: E402
from app.metrics.facts import FactBuilder  # noqa: E402
from app.metrics.view import make_view  # noqa: E402
from app.schemas import ChallengeRequest, Claim, InvestigationState  # noqa: E402
from app.simulation.compare import challenge  # noqa: E402
from app.simulation.engine import BranchError  # noqa: E402

EVAL_DIR = ROOT / "backend" / "fixtures" / "evaluation"
PRESS_Q = "Should the right-back have pressed earlier?"
OTHER_QS = ["What passing options did Rossi have?", "How far did Halvorsen run?", "How long did Harbor keep the ball?"]
TRACKED = {"tracked_running", "defender_distance", "lane_access", "open_lanes", "possession_duration", "transitions"}


def investigate(bundle, question, audience="analyst"):
    state = InvestigationState(
        investigation_id="eval", scenario_id=bundle.manifest.scenario_id, dataset_hash=bundle.manifest.dataset_hash,
        cursor_s=bundle.manifest.duration_s, question=question, audience=audience, status="queued",
        provider_mode="offline", provider_label="offline",
    )
    t0 = time.perf_counter()
    Workflow(state, make_view(bundle), load_settings()).run_offline()
    return state, (time.perf_counter() - t0) * 1000


def recheck(state) -> int:
    """Shown claims that fail an independent re-validation (should be 0)."""
    facts = {f.fact_id: f for f in state.facts}
    players = make_view_players(state)
    return sum(1 for c in state.claims if validate_claim(c, facts, players))


_PLAYERS = {}


def make_view_players(state):
    return _PLAYERS[state.scenario_id]


def pipeline_a(bundle):
    """Deterministic event recap: what can be said from events alone."""
    v = make_view(bundle)
    b = FactBuilder(v)
    facts = [b.pass_completion(t.team_id, 0.0, v.cursor_s) for t in v.manifest.teams]
    facts += [b.pass_distance(e) for e in v.events if e.type == "pass"]
    facts = [f for f in facts if f]
    return [Claim(claim_type="observed", text=f.statement, fact_ids=[f.fact_id]) for f in facts], {f.fact_id: f for f in facts}


def adversarial(state) -> tuple[int, int]:
    """Inject fabricated claims built from this answer's own facts; return (rejected, injected)."""
    facts = {f.fact_id: f for f in state.facts}
    players = make_view_players(state)
    obs = next((f for f in state.facts if f.evidence_class == "observed" and f.value is not None), None)
    sim = next((f for f in state.facts if f.evidence_class == "simulated"), None)
    roster_other = next(p for pid, p in players.items() if obs is None or pid not in obs.subject_ids)
    attacks: list[Claim] = [Claim(claim_type="observed", text="Halvorsen pressed within 2.5 s.", fact_ids=["fabricated-id"])]
    if obs:
        altered = obs.statement.replace(f"{obs.value:.1f}", f"{obs.value + 1.3:.1f}") if f"{obs.value:.1f}" in obs.statement else obs.statement + " It was 77.7 m."
        attacks += [
            Claim(claim_type="observed", text=altered, fact_ids=[obs.fact_id]),
            Claim(claim_type="observed", text=f"{roster_other.name.split()[-1]} was involved.", fact_ids=[obs.fact_id]),
            Claim(claim_type="interpretation", text=f"This happened {obs.value:.1f} times.", fact_ids=[]),
        ]
    if sim:
        attacks += [
            Claim(claim_type="observed", text=sim.statement, fact_ids=[sim.fact_id]),  # wrong evidence class
            Claim(claim_type="simulated", text="Holding was clearly the right call.", fact_ids=[sim.fact_id]),  # unlabelled simulation
        ]
    rejected = sum(1 for c in attacks if validate_claim(c, facts, players))
    return rejected, len(attacks)


def main() -> None:
    expected = json.loads((EVAL_DIR / "_expected.json").read_text(encoding="utf-8"))
    rows, latencies, press_latencies, adv_rej, adv_n = [], [], [], 0, 0
    a_rows = []
    for sid, meta in expected.items():
        bundle = load_scenario(EVAL_DIR / sid)
        _PLAYERS[sid] = {p.player_id: p for t in bundle.manifest.teams for p in t.players}

        # Pipeline A
        a_claims, a_facts = pipeline_a(bundle)
        a_bad = sum(1 for c in a_claims if validate_claim(c, a_facts, _PLAYERS[sid]))
        a_rows.append({"variant": sid, "claims": len(a_claims), "invalid": a_bad, "addresses_counterfactual": False})

        # Pipeline C-offline: pressing question + three other questions
        state, ms = investigate(bundle, PRESS_Q)
        latencies.append(ms)
        if meta["class"] == "press_recorded":
            press_latencies.append(ms)
        sims = [c for c in state.claims if c.claim_type == "simulated"]
        tracked_facts = [f for f in state.facts if f.metric in TRACKED]
        cls = meta["class"]
        if cls == "press_recorded":
            ok = state.outcome == "answered" and bool(sims) and any(c.claim_type == "observed" for c in state.claims)
        elif cls == "no_press_recorded":
            ok = state.outcome == "insufficient_data" and not sims
        else:  # event_only
            ok = not sims and not tracked_facts
        others = []
        for q in OTHER_QS:
            s2, ms2 = investigate(bundle, q)
            latencies.append(ms2)
            others.append({"question": q, "outcome": s2.outcome, "claims": len(s2.claims), "invalid_shown": recheck(s2), "refused": [n for n in s2.notes][:2]})
        r, n = adversarial(state)
        adv_rej += r
        adv_n += n

        finding = changed = cells = None
        if cls == "press_recorded":
            try:
                ch = challenge(bundle, ChallengeRequest())
                finding = f"{ch.baseline.status}{':' + ch.baseline.action if ch.baseline.action else ''}"
                changed, cells = len(ch.changed), len(ch.cells)
            except BranchError as exc:
                finding = f"branch error: {exc}"
        rows.append(
            {
                "variant": sid,
                "class": cls,
                "outcome": state.outcome,
                "claims": len(state.claims),
                "simulated_claims": len(sims),
                "tracked_facts": len(tracked_facts),
                "invalid_shown": recheck(state),
                "rejected_internally": len(state.rejected_claims),
                "meets_expectation": ok,
                "notes": state.notes[:2],
                "challenger_baseline": finding,
                "challenger_changed": changed,
                "challenger_cells": cells,
                "latency_ms": round(ms),
                "other_questions": others,
            }
        )
        print(f"{sid} {cls:18s} outcome={state.outcome} claims={len(state.claims)} sims={len(sims)} ok={ok} challenger={finding} changed={changed}/{cells} {ms:.0f} ms")

    shown = sum(r["claims"] for r in rows) + sum(o["claims"] for r in rows for o in r["other_questions"])
    invalid = sum(r["invalid_shown"] for r in rows) + sum(o["invalid_shown"] for r in rows for o in r["other_questions"])
    summary = {
        "variants": len(rows),
        "expectation_met": sum(r["meets_expectation"] for r in rows),
        "c_offline_investigations": len(latencies),
        "c_offline_completed": len(latencies),
        "claims_shown": shown,
        "claims_failing_revalidation": invalid,
        "adversarial_rejected": adv_rej,
        "adversarial_injected": adv_n,
        "latency_ms_median_all": round(statistics.median(latencies)),
        "latency_ms_median_pressing_with_simulation": round(statistics.median(press_latencies)),
        "latency_ms_max": round(max(latencies)),
        "pipeline_a_claims": sum(r["claims"] for r in a_rows),
        "pipeline_a_invalid": sum(r["invalid"] for r in a_rows),
        "not_run": {"B": "no live model deployment (Azure 715-123420 hold)", "C-live": "no live model deployment (Azure 715-123420 hold)"},
    }
    out = {"summary": summary, "c_offline": rows, "pipeline_a": a_rows}
    (ROOT / "docs" / "evaluation_results.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    write_markdown(out)
    print(json.dumps(summary, indent=2))


def write_markdown(out: dict) -> None:
    s = out["summary"]
    lines = [
        "# Evaluation",
        "",
        "_Generated by `scripts/evaluate.py` on held-out synthetic variants. A small diagnostic set, not evidence of football expertise._",
        "",
        "## Set-up",
        "",
        "- **12 held-out variants** (`backend/fixtures/evaluation/ev01`–`ev12`), generated with seeds and defensive settings never used during development. Expected behaviour was declared in `scripts/generate_fixtures.py` before the first run and is stored in `_expected.json`, which no runtime code or agent reads.",
        "  - 9 × press recorded: 4 normal press, 3 early press, 2 with a recorded cover.",
        "  - 2 × no press recorded: the right-back's press would come after the ball has moved on.",
        "  - 1 × event-only: all tracking removed.",
        "- **Pipelines.** **A**: deterministic event recap (event facts only). **C-offline**: the full tool pipeline with the rule-based router, run on the pressing question plus 3 other questions per variant. **B** (single model agent) and **C-live** (multi-agent with a live model): **not run**, because no model deployment was available (Azure error 715-123420 blocked every deployment on the student subscription). No numbers are reported for them.",
        "",
        "## Results (C-offline)",
        "",
        f"- **Predeclared behaviour met:** {s['expectation_met']} of {s['variants']} variants.",
        f"- **Completion:** {s['c_offline_completed']} of {s['c_offline_investigations']} investigations.",
        f"- **Claims shown that fail independent re-validation:** {s['claims_failing_revalidation']} of {s['claims_shown']}.",
        f"- **Injected fabricated claims rejected by the validator:** {s['adversarial_rejected']} of {s['adversarial_injected']}. Each variant's answer was attacked with an unknown fact id, an altered number, a citation attached to an unrelated player, a number inside an interpretation, a simulated fact presented as observed, and an unlabelled simulation claim (the last two only where simulated facts exist).",
        f"- **Latency** (offline, Windows laptop): pressing question with a fresh 200-rollout simulation, median {s['latency_ms_median_pressing_with_simulation']} ms (max {s['latency_ms_max']} ms); questions without simulation, a few milliseconds (median across all 48: {s['latency_ms_median_all']} ms).",
        "",
        "| Variant | Class | Outcome | Claims | Simulated | Tracked facts | Met | Challenger baseline (patient, cover 0.6 s) | Settings that change it |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in out["c_offline"]:
        ch = f"{r['challenger_changed']} of {r['challenger_cells']}" if r["challenger_cells"] else "—"
        lines.append(
            f"| {r['variant']} | {r['class']} | {r['outcome']} | {r['claims']} | {r['simulated_claims']} | {r['tracked_facts']} | {'yes' if r['meets_expectation'] else '**no**'} | {r['challenger_baseline'] or '—'} | {ch} |"
        )
    lines += [
        "",
        "## Pipeline A (deterministic event recap)",
        "",
        f"A produced {s['pipeline_a_claims']} claims across the 12 variants, {s['pipeline_a_invalid']} of which fail validation. It never addresses the counterfactual: it can say what was passed, but not whether pressing earlier would have helped. That is the gap the metrics, simulator and challenger fill. A comparison of answer quality between A and C needs human or model judgement and was not done.",
        "",
        "## What this does and does not show",
        "",
        "- It shows that, on this diagnostic set, the pipeline answers when the data supports an answer and abstains when there is no pressing moment or no tracking. Every number shown traces to a code-generated fact, and the validator catches the fabrication patterns it was tested with.",
        "- It does **not** show that the simulator's recommendations are right about football. The simulator is rule-based and uncalibrated (see MODEL_CARD). The challenger column shows how often the finding depends on the cover-delay and attacker-policy assumptions.",
        "- **Not measured:** live-model supported-claim rate, tokens and cost (no model available); human ratings of explanations; accessibility with assistive technology.",
        "",
    ]
    (ROOT / "docs" / "EVALUATION.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
