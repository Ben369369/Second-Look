"""Bounded multi-agent investigation workflow (Microsoft Agent Framework).

Roles and typed handoffs:
  Planner           question -> PlanOut (supported intent, players, whether a counterfactual is needed)
  Evidence analyst  PlanOut -> tool calls (compute_metrics, get_events) -> EvidenceOut (fact ids)
  Challenger        facts -> tool calls (evaluate_interventions, search_reversal) -> ChallengeOut
  Producer          facts + challenge -> ProducerOut (claim objects citing fact ids)
  Validator         deterministic code: every claim checked against the approved facts; one repair round.

The model never produces a number that is not in a cited, code-generated fact.
Offline mode runs the same tools with the rule-based router instead of models and
is labelled as such; provider failures fall back to it with a "fallback" label.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from typing import Any

from pydantic import BaseModel

from app.agents.tools import InvestigationContext, build_tools
from app.agents.validate import validate_claims
from app.config import Settings
from app.investigations.questions import CATALOGUE, LABELS, ask, route
from app.metrics.facts import sim_run_id
from app.metrics.view import SequenceView
from app.schemas import Claim, Fact, InvestigationState, RejectedClaim, TraceStep

MAX_RETRIES = 2
# On-device reply caps (tokens): JSON hand-offs are short; the producer writes several sentences.
LOCAL_MAX_TOKENS = {"ProducerOut": 900}
MAX_FACT_CLAIMS = 6
MIN_FACT_CLAIMS = 3
MAX_INTERPRETATIONS = 2
LOCAL_MAX_TOKENS_DEFAULT = 700
PER_CALL_TIMEOUT_S = 30.0
FUNCTION_LIMITS = {"max_iterations": 4, "max_function_calls": 6, "max_duration_seconds": 30}

OFFLINE_LABEL = "Offline demonstration — no language model connected"
FALLBACK_LABEL = "Fallback — the language model failed; answer built from rule-based templates"


# ---- typed handoffs (all fields required, for strict structured output) ----


class PlanOut(BaseModel):
    intent: str
    player_ids: list[str]
    team_ids: list[str]
    needs_simulation: bool
    clarification: str | None
    rationale: str


class EvidenceOut(BaseModel):
    supporting_fact_ids: list[str]
    contradicting_fact_ids: list[str]
    missing_data: list[str]


class ChallengeOut(BaseModel):
    finding_robust: bool | None
    concerns: list[str]


class InterpretationOut(BaseModel):
    text: str
    fact_ids: list[str]


class ProducerOut(BaseModel):
    # The producer selects facts (code renders their sentences) and writes only interpretations.
    fact_ids: list[str]
    interpretations: list[InterpretationOut]


INTENTS = ", ".join(f"{q.intent} ({q.label}: e.g. '{q.example}')" for q in CATALOGUE)

PLANNER = f"""You are the planner for Second Look, which answers questions about ONE synthetic football sequence.
Classify the user's question into exactly one supported intent: {INTENTS}.
If none fits, use intent "unsupported". The players in this sequence are listed in the prompt.
Fill player_ids/team_ids only with ids from that list. Ask for clarification (clarification field) only if the
question is materially ambiguous (e.g. a shirt number that exists on both teams); otherwise set it to null.
needs_simulation is true only for counterfactual questions (what would have happened if...).
Questions about what a player or team should have done, other than the pressing decision (press earlier, hold, or
press with cover), are "unsupported": the simulator does not model them.
Keep rationale to one short sentence without numbers."""

EVIDENCE = """You are the evidence analyst. Call compute_metrics for the planned intent (and players), and get_events if
you need the event sequence. Then return the fact ids that support answering the question and any that cut against
an obvious reading. Only use fact ids returned by your tool calls. List missing data in plain words, without numbers."""

CHALLENGER = """You are the challenger. Test whether the pressing finding survives different assumptions.
Call evaluate_interventions (defaults are fine) and then search_reversal. Report finding_robust = true only if the
reversal search found no setting that changes the finding; false if it did; null if the tools failed.
Concerns: up to three short sentences, WITHOUT numbers, naming assumptions or missing data that could change the answer."""

PRODUCER = """You are the producer. Build the answer from the facts provided.
- fact_ids: choose 3 to 5 fact ids, in the order a viewer should read them. Code shows each fact's own sentence, so
  you never reword a fact. For a pressing question include the sim_compare and sim_verdict facts.
- interpretations: at most 2 sentences, each under 30 words, saying what the chosen facts mean for the question, each
  citing the fact ids it rests on. No numbers. Only name players who are subjects of the cited facts. No certainty
  words (always, never, guaranteed), no causes (because, led to), no events such as goals, and no comparisons between
  choices (the comparison facts already do that). If it is about the simulation, say "in the simulation".
- An interpretation says what the evidence means or depends on (an assumption, the timing of the cover, missing data),
  never which choice did better: the facts you select already say that.
- Take the challenger's verdict into account: if the finding is not robust, one interpretation says what it depends on.
- {audience}"""

AUDIENCE = {
    "casual": "Audience: a football fan. Choose the fewest facts that tell the story; plain words in interpretations.",
    "analyst": "Audience: an analyst. Include the evidence that limits or qualifies the conclusion.",
}


class ProviderError(RuntimeError):
    pass


# Compact output shapes for on-device models (see Workflow._call).
SHAPE_HINTS = {
    "PlanOut": '{"intent": "press_timing", "player_ids": ["CED-02"], "team_ids": [], "needs_simulation": true, "clarification": null, "rationale": "one short sentence"}',
    "EvidenceOut": '{"supporting_fact_ids": ["<fact_id>"], "contradicting_fact_ids": [], "missing_data": []}',
    "ChallengeOut": '{"finding_robust": false, "concerns": ["short sentence without numbers"]}',
    "ProducerOut": '{"fact_ids": ["<fact_id>", "<fact_id>"], "interpretations": [{"text": "short sentence without numbers", "fact_ids": ["<fact_id>"]}]}',
}


def _strict_ok(text: str, out_type: type[BaseModel]) -> bool:
    try:
        out_type.model_validate_json(_extract_json(text))
        return True
    except Exception:
        return False


def _parse_reply(text: str, out_type: type[BaseModel]) -> BaseModel | None:
    """Strict parse first; if that fails, repair JSON *syntax* only (stray brackets, quotes,
    trailing commas) and validate the result against the full schema. Content is never invented:
    anything the schema rejects is still rejected."""
    candidate = _extract_json(text)
    try:
        return out_type.model_validate_json(candidate)
    except Exception:
        pass
    from json_repair import repair_json

    # Known quirk of small local models: "]]}" for "]}" and no comma between objects. None of
    # the output schemas here contains a list of lists, so collapsing "]]" is safe for them.
    patched = re.sub(r"\]\s*\]", "]", candidate)
    patched = re.sub(r"\}\s*\{", "},{", patched)
    for attempt in (patched, repair_json(patched), repair_json(candidate)):
        try:
            return out_type.model_validate_json(attempt)
        except Exception:
            continue
    return None


def _extract_json(text: str) -> str:
    """The outermost JSON object in a reply (tolerates code fences or a sentence around it).
    Validation against the schema still decides whether it is accepted."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)  # reasoning blocks from local models (e.g. Qwen3)
    start, end = text.find("{"), text.rfind("}")
    return text[start : end + 1] if 0 <= start < end else text


CASUAL_CAVEAT = (
    "This is a made-up match and the alternatives come from a simplified simulation of football, "
    "so treat them as a way to explore the argument, not a verdict."
)


def casual_claims(intent: str | None, facts: list[Fact]) -> list[Claim]:
    """Casual presentation: one finding, one trade-off, the context, one caveat. Built only from
    the facts' code-rendered plain sentences, so numbers cannot differ from the analyst view."""
    by_metric: dict[str, list[Fact]] = {}
    for f in facts:
        by_metric.setdefault(f.metric, []).append(f)
    kind = {"observed": "observed", "estimated": "estimated", "simulated": "simulated"}

    def claim(f: Fact) -> Claim:
        return Claim(claim_type=kind[f.evidence_class], text=f.plain or f.statement, fact_ids=[f.fact_id])  # type: ignore[arg-type]

    out: list[Claim] = []
    if intent == "press_timing" and by_metric.get("sim_verdict"):
        out.append(claim(by_metric["sim_verdict"][0]))  # finding: what the rule supports and what it leaves open
        out.extend(claim(f) for f in by_metric.get("sim_compare", []))  # the comparisons behind it
        for metric in ("defender_distance", "response_time"):  # what actually happened
            if metric in by_metric:
                out.append(claim(by_metric[metric][0]))
    else:
        order = [f for f in facts if f.evidence_class != "simulated"][:3]
        out.extend(claim(f) for f in order)
    out.append(Claim(claim_type="interpretation", text=CASUAL_CAVEAT, fact_ids=[f for c in out for f in c.fact_ids]))
    return out


class Workflow:
    def __init__(self, state: InvestigationState, view: SequenceView, settings: Settings, client_factory: Any = None):
        self.state = state
        self.ctx = InvestigationContext(view=view)
        self.settings = settings
        self.client_factory = client_factory
        self.deadline = time.perf_counter() + settings.investigation_timeout_seconds
        # Local models are slower; give each call a proportional share of the larger budget.
        self.per_call_timeout = max(PER_CALL_TIMEOUT_S, settings.investigation_timeout_seconds / 3)
        self.t_start = time.perf_counter()
        self.chosen: list[str] = []

    # -- helpers ----------------------------------------------------------------

    def _trace(self, agent: str, kind: str, summary: str, duration_ms: int = 0, tool: str | None = None) -> None:
        self.ctx.trace.append(TraceStep(agent=agent, kind=kind, summary=summary, duration_ms=duration_ms, tool=tool))  # type: ignore[arg-type]

    def _with_casual(self) -> None:
        facts = list(self.ctx.facts.values())
        if facts:
            ok, _ = validate_claims(casual_claims(self.state.intent, facts), self.ctx.facts, self.ctx.view.players)
            self.state.casual_claims = ok

    def _sync(self) -> None:
        s = self.state
        s.facts = list(self.ctx.facts.values())
        s.simulation_run_ids = list(self.ctx.sim_run_ids)
        s.trace = list(self.ctx.trace)
        s.tool_calls = self.ctx.tool_calls
        s.challenge_summary = self.ctx.challenge_summary
        s.elapsed_ms = int((time.perf_counter() - self.t_start) * 1000)

    async def _call(self, agent: Any, name: str, prompt: str, out_type: type[BaseModel], repaired: bool = False) -> BaseModel:
        """One model call with structured output, bounded by the deadline.

        Transient failures are retried at most MAX_RETRIES times. Output that does not
        match the schema gets exactly one repair attempt with the validation error.
        """
        last: Exception | None = None
        # The schema is also spelled out in the prompt, for models (e.g. small local ones)
        # that ignore the structured-output setting.
        if self.settings.mode == "foundry_local":
            # On-device models read prompts slowly, so they get a compact example of the shape
            # instead of the full JSON schema (the reply is still validated against the full model).
            full_prompt = f"{prompt}\n\nReply with only JSON shaped like:\n{SHAPE_HINTS[out_type.__name__]}\n/no_think"
        else:
            schema = json.dumps(out_type.model_json_schema(), separators=(",", ":"))
            full_prompt = f"{prompt}\n\nReply with only a JSON object matching this JSON schema:\n{schema}"
        for attempt in range(MAX_RETRIES + 1):
            # Tool call limits are per run: a retry starts a fresh conversation and may call them again.
            for t in getattr(agent, "default_options", {}).get("tools", []) or []:
                if hasattr(t, "invocation_count"):
                    t.invocation_count = 0
            remaining = self.deadline - time.perf_counter()
            if remaining <= 1.0:
                raise ProviderError("investigation time budget exhausted")
            t0 = time.perf_counter()
            try:
                # Foundry Local's server mishandles the structured-output setting (it returns the
                # schema's field names), so local models rely on the schema in the prompt; the
                # reply is validated against the same Pydantic model either way.
                # Local replies are also capped in length so a runaway generation cannot eat the budget.
                options = (
                    {"max_tokens": LOCAL_MAX_TOKENS.get(out_type.__name__, LOCAL_MAX_TOKENS_DEFAULT)}
                    if self.settings.mode == "foundry_local"
                    else {"response_format": out_type}
                )
                res = await asyncio.wait_for(agent.run(full_prompt, options=options), timeout=min(self.per_call_timeout, remaining))
            except (asyncio.TimeoutError, OSError, ConnectionError) as exc:
                last = exc
            except Exception as exc:  # SDK/HTTP errors: retried as transient, then surfaced as provider failure
                last = exc
            else:
                self.state.model_calls += 1
                usage = getattr(res, "usage_details", None) or {}
                for key, attr in (("input_token_count", "input_tokens"), ("output_token_count", "output_tokens")):
                    val = usage.get(key) if isinstance(usage, dict) else getattr(usage, key, None)
                    if isinstance(val, int):
                        setattr(self.state, attr, (getattr(self.state, attr) or 0) + val)
                try:  # the framework parses structured output lazily and raises on malformed JSON
                    value = res.value if isinstance(res.value, out_type) else None
                except Exception:
                    value = None
                if value is None:
                    try:
                        value = _parse_reply(res.text, out_type)
                        if value is not None and not _strict_ok(res.text, out_type):
                            self._trace(name, "repair", "JSON syntax repaired (json-repair); content validated against the schema")
                        if value is None:
                            raise ValueError("reply is not valid JSON for the schema")
                    except Exception as exc:
                        self._trace(name, "error", f"malformed structured output ({type(exc).__name__})", int((time.perf_counter() - t0) * 1000))
                        if repaired:
                            raise ProviderError(f"{name} returned malformed output twice") from exc
                        self._trace(name, "repair", "one repair attempt with the schema error")
                        fix = f"{prompt}\n\nYour previous reply did not match the required JSON schema ({str(exc)[:300]}). Reply again with valid JSON only."
                        return await self._call(agent, name, fix, out_type, repaired=True)
                self._trace(name, "model", f"returned {out_type.__name__}", int((time.perf_counter() - t0) * 1000))
                return value
            self._trace(name, "error", f"attempt {attempt + 1} failed: {type(last).__name__}", int((time.perf_counter() - t0) * 1000))
            if attempt < MAX_RETRIES:
                await asyncio.sleep(min(2.0 * (attempt + 1), max(0.0, self.deadline - time.perf_counter() - 1.0)))
        raise ProviderError(f"{name}: {type(last).__name__}: {str(last)[:160]}")

    def _facts_for_prompt(self, ids: list[str] | None = None) -> str:
        facts = [self.ctx.facts[i] for i in (ids or self.ctx.facts) if i in self.ctx.facts]
        return json.dumps(
            [{"fact_id": f.fact_id, "class": f.evidence_class, "subjects": f.subject_ids, "statement": f.statement, "plain": f.plain} for f in facts]
        )

    def _render(self, out: ProducerOut) -> list[Claim]:
        """Turn the producer's selection into claims: fact sentences come from code, never from the model."""
        kind = {"observed": "observed", "estimated": "estimated", "simulated": "simulated"}
        picked = [i for i in dict.fromkeys(out.fact_ids) if i in self.ctx.facts][:MAX_FACT_CLAIMS]
        if any(i not in self.ctx.facts for i in out.fact_ids):
            self._trace("validator", "validation", "producer selected fact ids that no tool returned; ignored")
        verdict = next((i for i, f in self.ctx.facts.items() if f.metric == "sim_verdict"), None)
        if verdict and verdict not in picked:
            picked.insert(0, verdict)
            self._trace("producer", "rule", "the decision rule's verdict is always shown; added")
        if len(picked) < MIN_FACT_CLAIMS:
            extra = [i for i in self.chosen if i not in picked][: MIN_FACT_CLAIMS - len(picked)]
            if extra:
                picked += extra
                self._trace("producer", "rule", f"added {len(extra)} of the evidence analyst's facts to reach the minimum of {MIN_FACT_CLAIMS}")
        claims = []
        for i in picked:
            f = self.ctx.facts[i]
            text = (f.plain or f.statement) if self.state.audience == "casual" else f.statement
            claims.append(Claim(claim_type=kind[f.evidence_class], text=text, fact_ids=[i]))  # type: ignore[arg-type]
        claims += [Claim(claim_type="interpretation", text=x.text, fact_ids=x.fact_ids) for x in out.interpretations[:MAX_INTERPRETATIONS]]
        return claims

    def _template_claims(self, facts: list[Fact]) -> list[Claim]:
        kind = {"observed": "observed", "estimated": "estimated", "simulated": "simulated"}
        return [Claim(claim_type=kind[f.evidence_class], text=f.statement, fact_ids=[f.fact_id]) for f in facts]  # type: ignore[arg-type]

    # -- offline / fallback ------------------------------------------------------------

    def run_offline(self, label_mode: str = "offline") -> InvestigationState:
        s, v = self.state, self.ctx.view
        t0 = time.perf_counter()
        res = ask(v, s.question)
        self.ctx.register(res.facts)
        for f in res.facts:
            run = sim_run_id(f)
            if run and run not in self.ctx.sim_run_ids:
                self.ctx.sim_run_ids.append(run)
        self._trace("router", "rule", f"keyword rules matched intent: {res.intent or 'none'} ({res.status})", int((time.perf_counter() - t0) * 1000))
        sims = {f.method_version for f in res.facts if f.evidence_class == "simulated"}
        if sims:
            self._trace("simulator", "rule", f"simulated comparison ({', '.join(sims)}) from the pass that triggered the press")
        claims: list[Claim] = []
        if s.audience == "casual" and res.facts:
            claims = casual_claims(res.intent, list(self.ctx.facts.values()))
            self._trace("producer", "rule", f"casual template: {len(claims)} claims from the same facts")
        else:
            for sent in res.answer:
                classes = {self.ctx.facts[i].evidence_class for i in sent.fact_ids if i in self.ctx.facts}
                ctype = "simulated" if classes == {"simulated"} else "estimated" if "estimated" in classes else "observed"
                claims.append(Claim(claim_type=ctype, text=sent.text, fact_ids=sent.fact_ids))  # type: ignore[arg-type]
        ok, bad = validate_claims(claims, self.ctx.facts, v.players)
        self._trace("validator", "validation", f"{len(ok)} claims approved, {len(bad)} rejected")
        s.claims = ok
        s.rejected_claims = [RejectedClaim(claim=c, errors=e) for c, e in bad]
        s.intent, s.intent_label = res.intent, res.intent_label
        s.outcome = res.status
        s.notes = res.notes + ([f"Supported questions: {', '.join(q.example for q in CATALOGUE)}"] if res.status == "unsupported" else [])
        s.provider_mode = label_mode  # type: ignore[assignment]
        s.provider_label = {"offline": OFFLINE_LABEL, "fallback": FALLBACK_LABEL}.get(label_mode, s.provider_label)
        s.status = "complete"
        self._with_casual()
        self._sync()
        return s

    # -- foundry ------------------------------------------------------------------------

    async def run_foundry(self) -> InvestigationState:
        from agent_framework import Agent

        s, v = self.state, self.ctx.view
        guard = route(v, s.question)
        if guard.unknown_names or guard.other_decision:
            # Deterministic guard: unknown players and unmodelled what-ifs are refused the same way in every mode,
            # before a model can turn them into a confident answer to a different question.
            self._trace("router", "rule", "outside what Second Look can answer (unknown player or unmodelled what-if); refused before any model call")
            return self.run_offline(label_mode=s.provider_mode)
        try:
            client = self.client_factory()
            tools_for = lambda agent: build_tools(self.ctx, agent)  # noqa: E731

            # 1. Planner
            s.status = "planning"
            # The catalogue and roster are small, so the planner gets them in its prompt (no tool loop).
            roster = "; ".join(f"{pid} = {v.label(pid)} ({p.role})" for pid, p in v.players.items())
            planner = Agent(client, PLANNER, name="planner")
            plan: PlanOut = await self._call(
                planner,
                "planner",
                f"Question: {s.question}\nData cutoff: {v.cursor_s:.1f} s into the sequence.\n"
                f"Teams: CED = Cedar FC, HAR = Harbor FC.\nPlayers: {roster}",
                PlanOut,
            )  # type: ignore[assignment]
            s.plan_summary = plan.rationale[:200]
            if plan.intent not in LABELS:
                s.intent = None
                s.outcome = "unsupported"
                s.notes = ["That question isn't one Second Look can answer from this data.", f"Supported questions: {', '.join(q.example for q in CATALOGUE)}"]
                s.status = "complete"
                self._sync()
                return s
            s.intent, s.intent_label = plan.intent, LABELS[plan.intent]
            if plan.clarification:
                s.outcome = "clarify"
                s.notes.append(f"Clarification needed: {plan.clarification}")
                s.status = "complete"
                self._sync()
                return s
            self._sync()

            # 2. Evidence analyst
            s.status = "evidence"
            ev_tools = tools_for("evidence analyst")
            analyst = Agent(client, EVIDENCE, name="evidence_analyst", tools=[ev_tools["compute_metrics"], ev_tools["get_events"]])
            try:
                evidence: EvidenceOut = await self._call(
                    analyst, "evidence analyst",
                    f"Question: {s.question}\nPlan: {plan.model_dump_json()}\nCall compute_metrics with intent '{plan.intent}'.",
                    EvidenceOut,
                )  # type: ignore[assignment]
            except ProviderError as exc:
                if not self.ctx.facts or "malformed" not in str(exc):
                    raise
                # Its tool call succeeded; only the selection is unusable. Keep every fact the tool returned.
                self._trace("evidence analyst", "error", "selection unusable after one repair; continuing with every fact its tool returned")
                evidence = EvidenceOut(supporting_fact_ids=list(self.ctx.facts), contradicting_fact_ids=[], missing_data=[])
            if not self.ctx.facts:
                # The model skipped its tool: compute deterministically rather than answer without evidence.
                self._trace("evidence analyst", "error", "no tool call made; computing metrics directly")
                ev_tools["compute_metrics"](intent=plan.intent, player_ids=plan.player_ids, team_ids=plan.team_ids)
            chosen = [i for i in evidence.supporting_fact_ids + evidence.contradicting_fact_ids if i in self.ctx.facts]
            self.chosen = chosen or [i for i, f in self.ctx.facts.items() if f.evidence_class != "simulated"]
            if len(chosen) < len(evidence.supporting_fact_ids + evidence.contradicting_fact_ids):
                self._trace("validator", "validation", "evidence analyst cited fact ids that no tool returned; ignored")
            s.notes.extend(m for m in evidence.missing_data if not any(ch.isdigit() for ch in m))
            self._sync()

            # 3. Challenger (counterfactual questions)
            if plan.intent == "press_timing" or plan.needs_simulation:
                s.status = "challenging"
                ch_tools = tools_for("challenger")
                challenger = Agent(client, CHALLENGER, name="challenger", tools=[ch_tools["evaluate_interventions"], ch_tools["search_reversal"]])
                chal: ChallengeOut = await self._call(challenger, "challenger", f"Question: {s.question}", ChallengeOut)  # type: ignore[assignment]
                concerns = [c for c in chal.concerns[:3] if not any(ch.isdigit() for ch in c)]
                s.notes.extend(concerns)
                searched = None if self.ctx.reversal_changed is None else self.ctx.reversal_changed == 0
                if searched is not None and chal.finding_robust is not None and chal.finding_robust != searched:
                    self._trace("validator", "validation", f"challenger called the finding {'robust' if chal.finding_robust else 'not robust'}; its reversal search says otherwise, so the search result is used")
                robust = {True: "robust", False: "not robust", None: "unknown"}[searched if searched is not None else chal.finding_robust]
                challenge_note = f"finding {robust}; concerns: {'; '.join(concerns) or 'none'}"
                self._trace("challenger", "rule", f"challenger verdict passed to the producer: {robust}")
                self._sync()
            else:
                challenge_note = "not run (no simulation needed)"

            # 4. Producer + validation (one repair round)
            s.status = "producing"
            producer = Agent(client, PRODUCER.format(audience=AUDIENCE[s.audience]), name="producer")
            sim_ids = [i for i, f in self.ctx.facts.items() if f.evidence_class == "simulated"]
            fact_ids = list(dict.fromkeys((chosen or list(self.ctx.facts)) + sim_ids))
            prompt = (
                f"Question: {s.question}\nChallenger: {challenge_note}\nReversal search: {self.ctx.challenge_summary or 'none'}\n"
                f"Facts: {self._facts_for_prompt(fact_ids)}"
            )
            out: ProducerOut = await self._call(producer, "producer", prompt, ProducerOut)  # type: ignore[assignment]
            s.status = "validating"
            ok, bad = validate_claims(self._render(out), self.ctx.facts, v.players)
            self._trace("validator", "validation", f"{len(ok)} claims approved, {len(bad)} rejected")
            if bad:
                feedback = "\n".join(f"- {c.text[:120]} -> {'; '.join(e)}" for c, e in bad)
                self._trace("producer", "repair", f"one repair attempt for {len(bad)} rejected claims")
                out2: ProducerOut = await self._call(
                    producer, "producer", prompt + f"\nThese were rejected by validation; fix or drop them:\n{feedback}", ProducerOut
                )  # type: ignore[assignment]
                ok2, bad2 = validate_claims(self._render(out2), self.ctx.facts, v.players)
                self._trace("validator", "validation", f"after repair: {len(ok2)} approved, {len(bad2)} rejected")
                ok, bad = ok2, bad + bad2
            s.rejected_claims = [RejectedClaim(claim=c, errors=e) for c, e in bad]
            if not ok:
                self._trace("validator", "fallback", "no claim passed validation; showing code-rendered fact statements")
                ok = self._template_claims([self.ctx.facts[i] for i in fact_ids][:6])
            s.claims = ok
            s.outcome = "answered" if self.ctx.facts else "insufficient_data"
            s.status = "complete"
            self._with_casual()
            self._sync()
            return s
        except ProviderError as exc:
            s.errors.append(f"provider_error: {exc}")
            self._trace("workflow", "fallback", "language model unavailable; switching to the rule-based pipeline")
            # Keep the trace so far, start a clean evidence set for the fallback answer.
            self.ctx.facts.clear()
            return self.run_offline(label_mode="fallback")
