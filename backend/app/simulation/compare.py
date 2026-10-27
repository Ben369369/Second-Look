"""Intervention comparison, the predeclared decision rule, and the challenger grid."""

from __future__ import annotations

import hashlib
import json
import time
from collections import OrderedDict

import numpy as np

from app.schemas import (
    ActionResult,
    BranchInfo,
    ChallengeCell,
    ChallengeRequest,
    ChallengeResult,
    CompareRequest,
    ComparisonResult,
    PairedDiff,
    Position,
    RateSummary,
    Recommendation,
    ReplayBundle,
    SampleRollout,
    SimConfigOut,
    SimEvent,
    SimFrame,
    SimPlayer,
)
from app.simulation.engine import (
    ACTIONS,
    COVER_SCREEN_FRACTION,
    DANGER_DEPTH,
    EARLY_PRESS_S,
    POLICY_VERSION,
    BranchError,
    Rollouts,
    SimConfig,
    Simulator,
    default_branch,
)
from app.simulation.stats import paired_bootstrap, wilson

LABELS = {"hold": "Hold position", "press_earlier": "Press earlier", "press_with_cover": "Press with cover"}

# Predeclared decision rule (fixed before any comparison is run).
PRIMARY = "danger"  # lower is better
MARGIN = 0.05  # practical margin, 5 percentage points
MIN_ROLLOUTS = 64
RULE_TEXT = (
    "Recommend an action only if its simulated dangerous-possession rate is lower than every other action's "
    f"by at least {MARGIN * 100:.0f} percentage points, with the 95% paired-bootstrap interval of each difference "
    f"excluding zero, from at least {MIN_ROLLOUTS} rollouts per action. Otherwise report no clear winner."
)

ASSUMPTIONS = [
    "Rule-based synthetic players (policy " + POLICY_VERSION + "); not fitted to real matches. Rates are counts within this simulator, not real-world probabilities.",
    "Branch at the pass that triggered the recorded press; only the state at that frame is used.",
    f"Dangerous possession: the attacking team controls the ball within {DANGER_DEPTH:.0f} m of goal and inside the penalty-area width.",
    f"Press earlier: the presser starts closing {EARLY_PRESS_S} s after the branch. Hold: the presser contains about 6 m goal-side.",
    f"Press with cover: as press earlier, plus the cover player screens the midpoint ({COVER_SCREEN_FRACTION:.0%}) of the carrier → inside-option lane after the cover delay.",
    "Intervals show Monte Carlo sampling uncertainty only, not uncertainty about whether the model represents football well.",
]

_CACHE: OrderedDict[str, ComparisonResult] = OrderedDict()
_CACHE_MAX = 64


def _key(*parts) -> str:
    return hashlib.sha256(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()[:16]


def _rate(x: np.ndarray) -> RateSummary:
    k, n = int(x.sum()), int(x.size)
    lo, hi = wilson(k, n)
    return RateSummary(count=k, n=n, rate=k / n if n else 0.0, ci95=(round(lo, 4), round(hi, 4)))


def _median(x: np.ndarray) -> float | None:
    v = x[~np.isnan(x)]
    return round(float(np.median(v)), 2) if v.size else None


def decide(results: dict[str, Rollouts], seed: int) -> tuple[Recommendation, list[PairedDiff]]:
    rates = {a: float(r.danger.mean()) for a, r in results.items()}
    best = min(results, key=lambda a: (rates[a], ACTIONS.index(a)))
    diffs: list[PairedDiff] = []
    reasons: list[str] = []
    clear = True
    for other in results:
        if other == best:
            continue
        d, ci = paired_bootstrap(results[best].danger, results[other].danger, seed=seed)
        diffs.append(PairedDiff(metric="danger", better=best, other=other, diff=round(d, 4), ci95=(round(ci[0], 4), round(ci[1], 4))))
        if d < MARGIN or ci[0] <= 0:
            clear = False
            reasons.append(
                f"{LABELS[best]} vs {LABELS[other]}: danger differs by {d * 100:+.1f} points "
                f"(95% interval {ci[0] * 100:+.1f} to {ci[1] * 100:+.1f}), "
                + ("below the 5-point margin." if d < MARGIN else "interval includes zero.")
            )
        else:
            reasons.append(f"{LABELS[best]} has {d * 100:.1f} points less danger than {LABELS[other]} (95% interval {ci[0] * 100:.1f} to {ci[1] * 100:.1f}).")
    # Secondary outcome stays visible: regain difference against each alternative.
    for other in results:
        if other != best:
            d, ci = paired_bootstrap(results[other].regain, results[best].regain, seed=seed + 1)
            diffs.append(PairedDiff(metric="regain", better=best, other=other, diff=round(-d, 4), ci95=(round(-ci[1], 4), round(-ci[0], 4))))
    n = min(r.danger.size for r in results.values())
    if n < MIN_ROLLOUTS:
        return Recommendation(status="inconclusive", action=None, rule=RULE_TEXT, reasons=[f"Only {n} rollouts per action; the rule needs {MIN_ROLLOUTS}."]), diffs
    if clear:
        return Recommendation(status="recommend", action=best, rule=RULE_TEXT, reasons=reasons), diffs
    return Recommendation(status="no_clear_winner", action=None, rule=RULE_TEXT, reasons=reasons), diffs


def _sample(sim: Simulator, r: Rollouts) -> SampleRollout:
    """One rollout whose outcome matches this action's most common outcome (shown for illustration)."""
    outcome = np.where(r.danger, 0, np.where(r.regain, 1, 2))
    modal = int(np.bincount(outcome, minlength=3).argmax())
    i = int(np.where(outcome == modal)[0][0])
    frames = []
    for s in range(r.pos.shape[0]):
        h = int(r.holder[s, i])
        frames.append(
            SimFrame(
                t=round(s * 0.1, 1),
                ball=Position(x=round(float(r.ball[s, i, 0]), 2), y=round(float(r.ball[s, i, 1]), 2)),
                holder=sim.ids[h] if h >= 0 else None,
                players=[SimPlayer(player_id=pid, x=round(float(r.pos[s, i, j, 0]), 2), y=round(float(r.pos[s, i, j, 1]), 2)) for j, pid in enumerate(sim.ids)],
            )
        )
    events = [SimEvent(t=t, kind=k, from_id=sim.ids[a] if a >= 0 else None, to_id=sim.ids[b]) for t, k, a, b in r.events[i]]
    return SampleRollout(action=r.action, rollout_index=i, outcome=("danger", "regain", "neither")[modal], frames=frames, events=events)


def _resolve(bundle: ReplayBundle, presser_id: str | None, frame_id: int | None) -> tuple[str, int]:
    if presser_id is None:
        rbs = [p.player_id for t in bundle.manifest.teams for p in t.players if p.role == "RB"]
        pressed = {e.player_id for e in bundle.events if e.type == "pressure_start"}
        cands = [p for p in rbs if p in pressed]
        if not cands:
            raise BranchError("no right-back press is recorded; pass presser_id explicitly")
        presser_id = cands[0]
    return presser_id, frame_id if frame_id is not None else default_branch(bundle, presser_id)


def compare(bundle: ReplayBundle, req: CompareRequest) -> ComparisonResult:
    presser, frame_id = _resolve(bundle, req.presser_id, req.frame_id)
    cfg = SimConfig(rollouts=req.rollouts, seed=req.seed, cover_delay_s=req.cover_delay_s, attacker_policy=req.attacker_policy)
    key = _key(bundle.manifest.dataset_hash, frame_id, presser, cfg.__dict__, POLICY_VERSION)
    if key in _CACHE:
        _CACHE.move_to_end(key)
        return _CACHE[key].model_copy(update={"cached": True})
    t0 = time.perf_counter()
    sim = Simulator(bundle, frame_id, presser)
    results = {a: sim.run(a, cfg) for a in ACTIONS}
    rec, diffs = decide(results, cfg.seed)
    out = ComparisonResult(
        run_id=f"sim-{key}",
        scenario_id=bundle.manifest.scenario_id,
        dataset_hash=bundle.manifest.dataset_hash,
        evidence_class="simulated",
        policy_version=POLICY_VERSION,
        branch=BranchInfo(**sim.branch.__dict__),
        config=SimConfigOut(**cfg.__dict__),
        actions=[
            ActionResult(
                action=a,
                label=LABELS[a],
                danger=_rate(r.danger),
                regain=_rate(r.regain),
                retained=_rate(r.retained),
                median_regain_s=_median(r.regain_t),
                median_first_pass_s=_median(r.first_pass_t),
            )
            for a, r in results.items()
        ],
        diffs=diffs,
        recommendation=rec,
        samples=[_sample(sim, r) for r in results.values()],
        assumptions=ASSUMPTIONS,
        compute_ms=int((time.perf_counter() - t0) * 1000),
        cached=False,
    )
    _CACHE[key] = out
    while len(_CACHE) > _CACHE_MAX:
        _CACHE.popitem(last=False)
    return out


def challenge(bundle: ReplayBundle, req: ChallengeRequest) -> ChallengeResult:
    """Search a fixed, bounded grid of assumptions for settings that change the baseline finding."""
    presser, frame_id = _resolve(bundle, req.presser_id, req.frame_id)
    t0 = time.perf_counter()
    sim = Simulator(bundle, frame_id, presser)

    # Only press_with_cover depends on the cover delay, so the other two actions are run
    # once per attacker policy and reused (identical seeds, so identical results).
    memo: dict[tuple[str, str, float], Rollouts] = {}

    def run(action: str, delay: float, policy: str) -> Rollouts:
        k = (action, policy, delay if action == "press_with_cover" else -1.0)
        if k not in memo:
            cfg = SimConfig(rollouts=req.rollouts, seed=req.seed, cover_delay_s=delay, attacker_policy=policy)  # type: ignore[arg-type]
            memo[k] = sim.run(action, cfg)  # type: ignore[arg-type]
        return memo[k]

    def cell(delay: float, policy: str) -> ChallengeCell:
        cfg = SimConfig(rollouts=req.rollouts, seed=req.seed, cover_delay_s=delay, attacker_policy=policy)  # type: ignore[arg-type]
        res = {a: run(a, delay, policy) for a in ACTIONS}
        rec, _ = decide(res, cfg.seed)
        return ChallengeCell(
            cover_delay_s=delay,
            attacker_policy=policy,  # type: ignore[arg-type]
            status=rec.status,
            action=rec.action,
            danger={a: round(float(r.danger.mean()), 4) for a, r in res.items()},
            regain={a: round(float(r.regain.mean()), 4) for a, r in res.items()},
        )

    baseline = cell(req.baseline_cover_delay_s, req.baseline_attacker_policy)
    cells = [cell(d, p) for p in req.attacker_policies for d in req.cover_delays]
    changed = [c for c in cells if (c.status, c.action) != (baseline.status, baseline.action)]
    domain = (
        f"cover delay ∈ {{{', '.join(f'{d:g}' for d in req.cover_delays)}}} s × attacker policy ∈ {{{', '.join(req.attacker_policies)}}}, "
        f"{req.rollouts} rollouts per action per setting"
    )
    def describe(c: ChallengeCell) -> str:
        return f"{LABELS[c.action]} recommended" if c.status == "recommend" and c.action else ("no clear winner" if c.status == "no_clear_winner" else "inconclusive")

    tally: dict[str, int] = {}
    for c in cells:
        tally[describe(c)] = tally.get(describe(c), 0) + 1
    tally_txt = "; ".join(f"{k} in {v}" for k, v in sorted(tally.items(), key=lambda kv: -kv[1]))
    if changed:
        conclusion = (
            f"The finding depends on the assumptions. At your settings: {describe(baseline)}. "
            f"Across the {len(cells)} tested settings: {tally_txt}."
        )
    else:
        conclusion = (
            f"Stable across the tested grid: {describe(baseline)} in all {len(cells)} settings. "
            "This does not establish robustness outside the tested grid."
        )
    return ChallengeResult(
        run_id=f"chl-{_key(bundle.manifest.dataset_hash, frame_id, presser, req.model_dump(), POLICY_VERSION)}",
        scenario_id=bundle.manifest.scenario_id,
        evidence_class="simulated",
        policy_version=POLICY_VERSION,
        rollouts_per_action=req.rollouts,
        baseline=baseline,
        cells=cells,
        changed=changed,
        tested_domain=domain,
        conclusion=conclusion,
        compute_ms=int((time.perf_counter() - t0) * 1000),
    )
