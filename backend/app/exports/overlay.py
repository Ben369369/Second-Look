"""Recap plan and timed overlay cues built from an investigation's approved claims.

Timebase: seconds from the start of the recorded sequence ("sequence_s"). The recap
plays the replay at PLAYBACK_RATE, so a 22 s sequence becomes a ~44 s recap.
Recorded cues start at the moment their facts describe; the simulated "what if"
results close the recap on one SIMULATION-labelled card. Cue text is only ever
approved claim text.
"""

from __future__ import annotations

from app.schemas import Claim, ExportBundle, Fact, InvestigationState, OverlayCue, RecapInsight, ReplayBundle

SCHEMA_VERSION = "overlay/1"
PLAYBACK_RATE = 0.5
CUE_SECONDS = 3.0  # sequence seconds (6 s of viewing at half speed)
TRADEOFF_SECONDS = 5.0  # the closing simulated trade-off card (10 s of viewing)
LEAD_IN_S = 0.5
MIN_CUE_S = 1.0
MAX_INSIGHTS = 4

SPOTLIGHT = {"defender_distance", "response_time", "tracked_running"}


class CueError(ValueError):
    pass


def _pick_insights(claims: list[Claim]) -> tuple[list[Claim], list[Claim]]:
    """Up to 3 recorded insights (one of each kind first) plus one closing trade-off card: the decision
    rule's verdict when the answer has it (one sentence a broadcast can show), else the simulated claims."""
    recorded = [c for c in claims if c.claim_type in ("observed", "estimated", "insufficient_data")]
    picked: list[Claim] = []
    for kind in ("observed", "estimated", "insufficient_data"):
        c = next((c for c in recorded if c.claim_type == kind and c not in picked), None)
        if c:
            picked.append(c)
    picked += [c for c in recorded if c not in picked]
    sims = [c for c in claims if c.claim_type == "simulated"]
    verdict = [c for c in sims if any(i.startswith("sim_verdict:") for i in c.fact_ids)]
    sims = verdict[:1] or sims[:2]
    return picked[: MAX_INSIGHTS - (1 if sims else 0)], sims


def build_export(state: InvestigationState, bundle: ReplayBundle) -> ExportBundle:
    facts: dict[str, Fact] = {f.fact_id: f for f in state.facts}
    players = {p.player_id: p for t in bundle.manifest.teams for p in t.players}
    duration = bundle.manifest.duration_s
    caveat = next((c.text for c in state.claims if c.claim_type == "interpretation"), None)
    sim_assumptions = next((f.limitations[0] for f in state.facts if f.evidence_class == "simulated" and f.limitations), None)

    recorded, tradeoff = _pick_insights(state.claims)
    groups: list[tuple[float, list[Claim]]] = []
    for c in recorded:
        cited = [facts[i] for i in c.fact_ids if i in facts]
        start = min((f.focus_time_s for f in cited), default=0.0)
        groups.append((max(0.0, start - LEAD_IN_S), [c]))
    groups.sort(key=lambda g: g[0])
    if tradeoff:
        last = groups[-1][0] + MIN_CUE_S if groups else 0.0
        groups.append((max(last, duration - TRADEOFF_SECONDS), tradeoff))

    # Each cue starts at its own moment and is cut short when the next begins (minimum MIN_CUE_S),
    # so recorded cues are on screen while the replay shows what they describe.
    starts: list[float] = []
    for start, _ in groups:
        starts.append(max(start, starts[-1] + MIN_CUE_S) if starts else start)

    cues: list[OverlayCue] = []
    insights: list[RecapInsight] = []
    for i, (start, (_, group)) in enumerate(zip(starts, groups)):
        if start + MIN_CUE_S > duration:  # no room left on the timeline
            break
        simulated = group[0].claim_type == "simulated"
        nxt = starts[i + 1] if i + 1 < len(starts) else duration
        length = min(TRADEOFF_SECONDS if simulated else CUE_SECONDS, nxt - start, duration - start)
        fact_ids = list(dict.fromkeys(fid for c in group for fid in c.fact_ids))
        cited = [facts[fid] for fid in fact_ids if fid in facts]
        subjects = list(dict.fromkeys(s for f in cited for s in f.subject_ids if s in players))
        kind = group[0].claim_type
        if simulated:
            gtype, title = "tradeoff_card", "SIMULATION · alternative choices"
        elif kind == "insufficient_data":
            gtype, title = "insufficient_data_card", "Not enough data"
        elif cited and cited[0].metric in SPOTLIGHT and subjects:
            p = players[subjects[0]]
            gtype, title = "player_spotlight", f"#{p.number} {p.name}"
        else:
            gtype, title = "event_comparison", {"observed": "Measured", "estimated": "Estimate"}.get(kind, "Note")
        cue_id = f"{state.investigation_id}-c{len(cues)}"
        cues.append(
            OverlayCue(
                schema_version=SCHEMA_VERSION,
                cue_id=cue_id,
                source_run_id=state.investigation_id,
                scenario_hash=state.dataset_hash,
                timebase="sequence_s",
                branch="simulated" if simulated else "recorded",
                start_s=round(start, 2),
                duration_s=round(length, 2),
                graphic_type=gtype,  # type: ignore[arg-type]
                title=title,
                body="\n".join(c.text for c in group),
                language="en",
                audience=state.audience,
                highlighted_player_ids=subjects,
                fact_ids=fact_ids,
                simulation_run_ids=list(state.simulation_run_ids) if simulated else [],
                evidence_class=kind if kind in ("observed", "estimated", "simulated") else "interpretation",  # type: ignore[arg-type]
                assumptions_summary=sim_assumptions if simulated else caveat,
                status="approved",
            )
        )
        insights.append(RecapInsight(order=len(insights) + 1, claims=group, cue_id=cue_id))

    out = ExportBundle(
        schema_version=SCHEMA_VERSION,
        investigation_id=state.investigation_id,
        scenario_id=state.scenario_id,
        scenario_hash=state.dataset_hash,
        question=state.question,
        audience=state.audience,
        provider_mode=state.provider_mode,
        provider_label=state.provider_label,
        timebase="sequence_s",
        sequence_duration_s=duration,
        playback_rate=PLAYBACK_RATE,
        recap_duration_s=round(duration / PLAYBACK_RATE, 1),
        insights=insights,
        cues=cues,
        synthetic_data=True,
    )
    validate_export(out, state, bundle)
    return out


def validate_export(out: ExportBundle, state: InvestigationState, bundle: ReplayBundle) -> None:
    """Reject exports that could mislead: bad timing, unknown references, unlabelled simulations, unapproved text."""
    fact_ids = {f.fact_id for f in state.facts}
    focus = {f.fact_id: f.focus_time_s for f in state.facts}
    players = {p.player_id for t in bundle.manifest.teams for p in t.players}
    approved = {c.text for c in state.claims}
    prev_end = 0.0
    for cue in out.cues:
        if cue.start_s < 0 or cue.duration_s <= 0:
            raise CueError(f"{cue.cue_id}: invalid timing")
        if cue.start_s + cue.duration_s > out.sequence_duration_s + 1e-6:
            raise CueError(f"{cue.cue_id}: ends after the sequence")
        if cue.start_s + 1e-6 < prev_end:
            raise CueError(f"{cue.cue_id}: overlaps the previous cue")
        prev_end = cue.start_s + cue.duration_s
        if not set(cue.fact_ids) <= fact_ids:
            raise CueError(f"{cue.cue_id}: references unknown facts")
        if not set(cue.simulation_run_ids) <= set(state.simulation_run_ids):
            raise CueError(f"{cue.cue_id}: references unknown simulation runs")
        if not set(cue.highlighted_player_ids) <= players:
            raise CueError(f"{cue.cue_id}: unknown players")
        if cue.evidence_class == "simulated" and ("SIMULATION" not in cue.title or cue.branch != "simulated"):
            raise CueError(f"{cue.cue_id}: simulated cue without a simulation label")
        if any(line not in approved for line in cue.body.split("\n")):
            raise CueError(f"{cue.cue_id}: body is not made of approved claims")
        # A recorded cue must be on screen at (or within a lead-in of) the moment its facts describe.
        if cue.branch == "recorded" and cue.fact_ids:
            t = min(focus[f] for f in cue.fact_ids)
            if not (cue.start_s - 1e-6 <= t + MIN_CUE_S and t - LEAD_IN_S - 1e-6 <= cue.start_s + cue.duration_s):
                raise CueError(f"{cue.cue_id}: not on screen at its fact's moment ({t:.1f} s)")
