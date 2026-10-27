"""Tools the agents may call. Each investigation gets its own bound set.

Every tool reads through the investigation's cutoff view (observed data) or
starts the simulator at a branch frame inside the cutoff, registers any facts
it produces, records itself in the trace, and returns compact JSON. Tools are
the only way numbers enter an investigation.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Annotated, Any

from agent_framework import tool
from pydantic import Field

from app.investigations.questions import CATALOGUE, HANDLERS, LABELS, Answer, Route
from app.metrics.facts import simulated_facts
from app.metrics.view import SequenceView
from app.schemas import ChallengeRequest, CompareRequest, Fact, ReplayBundle, TraceStep
from app.simulation.compare import challenge, compare
from app.simulation.engine import BranchError

MAX_TOOL_RESULT_FACTS = 24


@dataclass
class InvestigationContext:
    view: SequenceView
    facts: dict[str, Fact] = field(default_factory=dict)
    sim_run_ids: list[str] = field(default_factory=list)
    trace: list[TraceStep] = field(default_factory=list)
    tool_calls: int = 0
    notes: list[str] = field(default_factory=list)
    challenge_summary: str | None = None
    reversal_changed: int | None = None  # settings in the grid that change the finding

    @property
    def bundle(self) -> ReplayBundle:
        v = self.view
        return ReplayBundle(manifest=v.manifest, frames=v.frames, events=v.events)

    def register(self, facts: list[Fact]) -> None:
        for f in facts:
            self.facts[f.fact_id] = f

    def log_tool(self, agent: str, name: str, summary: str, t0: float) -> None:
        self.tool_calls += 1
        self.trace.append(TraceStep(agent=agent, kind="tool", tool=name, summary=summary, duration_ms=int((time.perf_counter() - t0) * 1000)))


def _fact_brief(f: Fact) -> dict[str, Any]:
    return {"fact_id": f.fact_id, "class": f.evidence_class, "metric": f.metric, "subjects": f.subject_ids, "statement": f.statement}


def build_tools(ctx: InvestigationContext, agent: str) -> dict[str, Any]:
    """Function tools bound to one investigation, labelled with the calling agent for the trace."""
    v = ctx.view
    roster = {pid: v.label(pid) for pid in v.players}

    @tool(name="list_supported_questions", description="List the question types Second Look can answer from data, with examples.", approval_mode="never_require")
    def list_supported_questions() -> str:
        t0 = time.perf_counter()
        out = [q.model_dump() for q in CATALOGUE]
        ctx.log_tool(agent, "list_supported_questions", f"{len(out)} supported intents", t0)
        return json.dumps({"intents": out, "players": roster})

    @tool(
        name="compute_metrics",
        description=(
            "Compute approved facts (observed measurements and labelled estimates) for one supported intent, "
            "using only data up to the investigation's cutoff. Returns fact ids and code-rendered statements."
        ),
        approval_mode="never_require",
        max_invocations=1,  # one call per agent run; small models otherwise repeat it
    )
    def compute_metrics(
        intent: Annotated[str, Field(description="One of the supported intent names, e.g. press_timing, passing_options, running.")],
        player_ids: Annotated[list[str], Field(description="Player ids the question is about, e.g. CED-02. May be empty.")] = [],  # noqa: B006
        team_ids: Annotated[list[str], Field(description="Team ids (CED, HAR). May be empty.")] = [],  # noqa: B006
    ) -> str:
        t0 = time.perf_counter()
        if intent not in HANDLERS:
            ctx.log_tool(agent, "compute_metrics", f"rejected unknown intent '{intent[:40]}'", t0)
            return json.dumps({"error": "unknown_intent", "supported": list(HANDLERS)})
        bad = [p for p in player_ids if p not in v.players]
        if bad:
            ctx.log_tool(agent, "compute_metrics", f"rejected unknown player ids {bad[:3]}", t0)
            return json.dumps({"error": "unknown_player_ids", "unknown": bad[:5], "valid_examples": list(v.players)[:6]})
        teams = [t for t in team_ids if t in {tm.team_id for tm in v.manifest.teams}]
        players = list(player_ids)
        if intent == "press_timing" and not players:
            players = [p for p in v.players if v.players[p].role == "RB" and any(e.type == "pressure_start" and e.player_id == p for e in v.events)]
        a = Answer(v)
        status = HANDLERS[intent](a, Route(intent=intent, players=players, teams=teams))
        ctx.register(a.facts)
        ctx.notes.extend(n for n in a.notes if n not in ctx.notes)
        facts = a.facts[:MAX_TOOL_RESULT_FACTS]
        ctx.log_tool(agent, "compute_metrics", f"{LABELS[intent]}: {len(a.facts)} facts, {len(a.b.refused)} refused ({status})", t0)
        return json.dumps(
            {"status": status, "facts": [_fact_brief(f) for f in facts], "refused": [r.model_dump() for r in a.b.refused], "notes": a.notes}
        )

    @tool(name="get_events", description="List recorded events between two times (seconds from sequence start), up to the cutoff.", approval_mode="never_require")
    def get_events(
        start_s: Annotated[float, Field(description="Window start, seconds.")] = 0.0,
        end_s: Annotated[float, Field(description="Window end, seconds.")] = 60.0,
    ) -> str:
        t0 = time.perf_counter()
        evs = [e for e in v.events if start_s <= e.time_s <= end_s][:40]
        ctx.log_tool(agent, "get_events", f"{len(evs)} events in {start_s:g}–{min(end_s, v.cursor_s):g} s", t0)
        return json.dumps(
            [{"event_id": e.event_id, "t": e.time_s, "type": e.type, "player": e.player_id, "recipient": e.recipient_id, "outcome": e.outcome} for e in evs]
        )

    @tool(
        name="evaluate_interventions",
        description=(
            "Run the bounded simulator for hold / press earlier / press with cover from the pass that triggered the press. "
            "Returns simulated facts (ids + statements) and the predeclared rule's verdict."
        ),
        approval_mode="never_require",
        max_invocations=1,  # one call per agent run; small models otherwise repeat it
    )
    def evaluate_interventions(
        cover_delay_s: Annotated[float, Field(ge=0.0, le=3.0, description="Seconds before the cover player starts screening the inside lane.")] = 0.6,
        attacker_policy: Annotated[str, Field(description="'patient' or 'direct'.")] = "patient",
    ) -> str:
        t0 = time.perf_counter()
        if attacker_policy not in ("patient", "direct") or not (0.0 <= cover_delay_s <= 3.0):
            ctx.log_tool(agent, "evaluate_interventions", "rejected out-of-range assumptions", t0)
            return json.dumps({"error": "invalid_arguments", "allowed": {"cover_delay_s": [0, 3], "attacker_policy": ["patient", "direct"]}})
        try:
            res = compare(ctx.bundle, CompareRequest(cover_delay_s=cover_delay_s, attacker_policy=attacker_policy))  # type: ignore[arg-type]
        except BranchError as exc:
            ctx.log_tool(agent, "evaluate_interventions", f"no branch: {exc}", t0)
            return json.dumps({"error": "no_branch", "message": str(exc)})
        facts = simulated_facts(v, res)
        ctx.register(facts)
        if res.run_id not in ctx.sim_run_ids:
            ctx.sim_run_ids.append(res.run_id)
        rec = res.recommendation
        ctx.log_tool(agent, "evaluate_interventions", f"run {res.run_id}: {rec.status}{' ' + rec.action if rec.action else ''} (cover {cover_delay_s:g} s, {attacker_policy})", t0)
        return json.dumps(
            {
                "run_id": res.run_id,
                "facts": [_fact_brief(f) for f in facts],
                "recommendation": {"status": rec.status, "action": rec.action, "reasons": rec.reasons},
                "assumptions": res.assumptions,
            }
        )

    @tool(
        name="search_reversal",
        description="Search a fixed grid of cover delays and attacker policies for settings where the simulated finding changes.",
        approval_mode="never_require",
        max_invocations=1,  # one call per agent run; small models otherwise repeat it
    )
    def search_reversal(
        baseline_cover_delay_s: Annotated[float, Field(ge=0.0, le=3.0)] = 0.6,
        baseline_attacker_policy: Annotated[str, Field(description="'patient' or 'direct'.")] = "patient",
    ) -> str:
        t0 = time.perf_counter()
        if baseline_attacker_policy not in ("patient", "direct"):
            ctx.log_tool(agent, "search_reversal", "rejected invalid policy", t0)
            return json.dumps({"error": "invalid_arguments"})
        try:
            res = challenge(ctx.bundle, ChallengeRequest(baseline_cover_delay_s=baseline_cover_delay_s, baseline_attacker_policy=baseline_attacker_policy))  # type: ignore[arg-type]
        except BranchError as exc:
            ctx.log_tool(agent, "search_reversal", f"no branch: {exc}", t0)
            return json.dumps({"error": "no_branch", "message": str(exc)})
        ctx.challenge_summary = res.conclusion
        ctx.reversal_changed = len(res.changed)
        if res.run_id not in ctx.sim_run_ids:
            ctx.sim_run_ids.append(res.run_id)
        ctx.log_tool(agent, "search_reversal", f"{len(res.changed)} of {len(res.cells)} settings change the finding", t0)
        return json.dumps(
            {
                "run_id": res.run_id,
                "conclusion": res.conclusion,
                "tested_domain": res.tested_domain,
                "changed_settings": [{"cover_delay_s": c.cover_delay_s, "attacker_policy": c.attacker_policy, "status": c.status, "action": c.action} for c in res.changed],
            }
        )

    return {
        "list_supported_questions": list_supported_questions,
        "compute_metrics": compute_metrics,
        "get_events": get_events,
        "evaluate_interventions": evaluate_interventions,
        "search_reversal": search_reversal,
    }
