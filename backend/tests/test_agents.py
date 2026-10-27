"""Agent workflow risks (spec §16, agent tests). The Agent Framework loop is real; replies are scripted."""

import asyncio
import json
import os
import re
from dataclasses import replace

import pytest

from app.agents.validate import validate_claim
from app.agents.workflow import MAX_RETRIES, Workflow
from app.config import load_settings
from app.data.loader import ScenarioRegistry
from app.investigations.questions import ask
from app.metrics.view import make_view
from app.schemas import Claim, InvestigationState
from fake_chat import ScriptedChatClient, prompt_text, tool_results

QUESTION = "Should the right-back have pressed earlier?"


@pytest.fixture(scope="module")
def bundle():
    return ScenarioRegistry(load_settings().fixtures_dir).get("rb_press_hero")


def _state(question=QUESTION):
    return InvestigationState(
        investigation_id="t", scenario_id="rb_press_hero", dataset_hash="x", cursor_s=21.9, question=question,
        audience="analyst", status="queued", provider_mode="foundry", provider_label="test",
    )


def _settings():
    return replace(load_settings(), mode="foundry", foundry_project_endpoint="https://example.invalid", foundry_model_deployment="test", investigation_timeout_seconds=60)


def _plan(intent="press_timing", players=("CED-02",), needs_sim=True, clarification=None):
    return json.dumps({"intent": intent, "player_ids": list(players), "team_ids": [], "needs_simulation": needs_sim, "clarification": clarification, "rationale": "Pressing decision by the right-back."})


def facts_in_prompt(messages):
    m = re.search(r"^Facts: (\[.*\])$", prompt_text(messages), re.M)  # the facts list is one line
    return json.loads(m.group(1)) if m else []


def honest_script(producer_extra=None, repair_ok=True):
    """Planner -> evidence (calls compute_metrics) -> challenger (both sim tools) -> producer."""

    def script(role, messages, turn):
        if role == "planner":
            return {"text": _plan()}  # the planner gets the catalogue and roster in its prompt
        if role == "evidence analyst":
            if turn == 0:
                return {"tool": "compute_metrics", "args": {"intent": "press_timing", "player_ids": ["CED-02"]}}
            ids = [f["fact_id"] for r in tool_results(messages) for f in r.get("facts", [])]
            return {"text": json.dumps({"supporting_fact_ids": ids[:4], "contradicting_fact_ids": [], "missing_data": []})}
        if role == "challenger":
            if turn == 0:
                return {"tool": "evaluate_interventions", "args": {}}
            if turn == 1:
                return {"tool": "search_reversal", "args": {}}
            return {"text": json.dumps({"finding_robust": False, "concerns": ["The answer depends on how quickly the cover arrives."]})}
        if role == "producer":
            facts = facts_in_prompt(messages)
            claims = [{"claim_type": f["class"], "text": f["statement"], "fact_ids": [f["fact_id"]]} for f in facts[:3]]
            claims.append({"claim_type": "interpretation", "text": "Pressing alone looks risky here; the cover timing matters.", "fact_ids": []})
            if producer_extra and (turn == 0 or not repair_ok):
                claims.append(producer_extra(facts))
            return {"text": json.dumps({"claims": claims})}
        raise AssertionError(role)

    return script


def run(bundle, script, question=QUESTION):
    client = ScriptedChatClient(script, function_invocation_configuration={"max_iterations": 4, "max_function_calls": 6})
    wf = Workflow(_state(question), make_view(bundle), _settings(), client_factory=lambda: client)
    return asyncio.run(wf.run_foundry()), client


def test_real_tool_calls_and_typed_handoffs(bundle):
    state, client = run(bundle, honest_script())
    assert state.status == "complete" and state.provider_mode == "foundry"
    tools = [t.tool for t in state.trace if t.kind == "tool"]
    assert {"compute_metrics", "evaluate_interventions", "search_reversal"} <= set(tools)
    assert state.tool_calls == len(tools)
    assert {f.evidence_class for f in state.facts} >= {"observed", "simulated"}
    assert state.simulation_run_ids and state.claims and not state.rejected_claims
    assert set(client.calls) == {"planner", "evidence analyst", "challenger", "producer"}


def test_altered_number_is_rejected_and_repaired_once(bundle):
    def altered(facts):
        f = next(x for x in facts if x["class"] == "observed")
        return {"claim_type": "observed", "text": re.sub(r"\d+\.\d", "9.9", f["statement"], count=1), "fact_ids": [f["fact_id"]]}

    state, client = run(bundle, honest_script(producer_extra=altered))
    assert any("numbers not found" in e for r in state.rejected_claims for e in r.errors)
    assert client.calls.count("producer") == 2  # exactly one repair round
    assert all("9.9" not in c.text for c in state.claims)


def test_repair_is_bounded_when_the_model_keeps_failing(bundle):
    bogus = lambda facts: {"claim_type": "observed", "text": "Halvorsen sprinted 99.9 m.", "fact_ids": ["made-up-id"]}  # noqa: E731
    state, client = run(bundle, honest_script(producer_extra=bogus, repair_ok=False))
    assert client.calls.count("producer") == 2
    assert state.status == "complete"
    assert all("99.9" not in c.text for c in state.claims)


def test_validator_rejects_fabrication_and_misattached_citations(bundle):
    view = make_view(bundle)
    res = ask(view, QUESTION)
    facts = {f.fact_id: f for f in res.facts}
    dist = next(f for f in res.facts if f.metric == "defender_distance")
    sim = next(f for f in res.facts if f.evidence_class == "simulated")
    players = view.players
    # Made-up fact id
    assert validate_claim(Claim(claim_type="observed", text="Halvorsen pressed.", fact_ids=["nope"]), facts, players)
    # Altered number on a real citation
    assert validate_claim(Claim(claim_type="observed", text=dist.statement.replace(f"{dist.value:.1f}", "4.2"), fact_ids=[dist.fact_id]), facts, players)
    # Real citation attached to an unrelated claim about another player
    assert any("Kiprono" in e for e in validate_claim(Claim(claim_type="observed", text="Kiprono was unmarked.", fact_ids=[dist.fact_id]), facts, players))
    # Wrong evidence class, and a simulated claim that does not say it is simulated
    assert validate_claim(Claim(claim_type="observed", text=sim.statement, fact_ids=[sim.fact_id]), facts, players)
    assert validate_claim(Claim(claim_type="simulated", text="Holding is best.", fact_ids=[sim.fact_id]), facts, players)
    # Numbers smuggled into an interpretation
    assert validate_claim(Claim(claim_type="interpretation", text="Pressing fails 36% of the time.", fact_ids=[]), facts, players)
    # The honest statement passes
    assert validate_claim(Claim(claim_type="observed", text=dist.statement, fact_ids=[dist.fact_id]), facts, players) == []


def test_unsupported_intent_returns_supported_options(bundle):
    script = lambda role, m, turn: {"text": _plan(intent="unsupported", players=(), needs_sim=False)}  # noqa: E731
    state, _ = run(bundle, script, question="Who will win the league?")
    assert state.status == "complete" and state.intent is None and not state.claims
    assert any("Supported questions" in n for n in state.notes)


def test_provider_failure_is_labelled_not_treated_as_missing_data(bundle):
    def script(role, messages, turn):
        return {"raise": ConnectionError("simulated network failure")}

    state, client = run(bundle, script)
    assert len(client.calls) == MAX_RETRIES + 1  # bounded retries, then fallback
    assert state.provider_mode == "fallback" and "fallback" in state.provider_label.lower()
    assert any(e.startswith("provider_error") for e in state.errors)
    assert state.status == "complete" and state.claims  # numerical evidence still available
    assert not any("insufficient" in n.lower() for n in state.notes)


def test_malformed_output_gets_one_repair_then_falls_back(bundle):
    def script(role, messages, turn):
        return {"text": "this is not json"}

    state, client = run(bundle, script)
    assert client.calls.count("planner") == 2  # original + one repair
    assert state.provider_mode == "fallback"


def test_tools_reject_invalid_arguments(bundle):
    from app.agents.tools import InvestigationContext, build_tools

    ctx = InvestigationContext(view=make_view(bundle))
    fresh = lambda: build_tools(ctx, "test")  # noqa: E731 -- data tools allow one call per agent run
    assert json.loads(fresh()["compute_metrics"](intent="bogus"))["error"] == "unknown_intent"
    assert json.loads(fresh()["compute_metrics"](intent="running", player_ids=["XYZ-99"]))["error"] == "unknown_player_ids"
    assert json.loads(fresh()["evaluate_interventions"](cover_delay_s=0.5, attacker_policy="chaotic"))["error"] == "invalid_arguments"
    # A second call within the same run is refused by the framework's own limit.
    tools = fresh()
    tools["compute_metrics"](intent="running", player_ids=["CED-02"])
    with pytest.raises(Exception, match="maximum invocation limit"):
        tools["compute_metrics"](intent="running", player_ids=["CED-02"])
    ctx.facts.clear()
    assert not ctx.facts and ctx.tool_calls == 4  # 3 rejected calls + 1 valid; the refused repeat is not logged


@pytest.mark.skipif(
    not (os.environ.get("SECOND_LOOK_LIVE_TESTS") == "1" and load_settings().model_configured),
    reason=(
        "LIVE TEST SKIPPED: set SECOND_LOOK_LIVE_TESTS=1 and either SECOND_LOOK_MODE=foundry with FOUNDRY_PROJECT_ENDPOINT/"
        "FOUNDRY_MODEL_DEPLOYMENT (and az login), or SECOND_LOOK_MODE=foundry_local with FOUNDRY_LOCAL_MODEL."
    ),
)
def test_live_model_smoke(bundle):
    from app.agents.provider import client_factory

    settings = load_settings()
    state0 = _state().model_copy(update={"provider_mode": settings.mode, "provider_label": settings.model_label})
    wf = Workflow(state0, make_view(bundle), settings, client_factory(settings))
    state = asyncio.run(wf.run_foundry())
    print("\nLIVE RESULT:", settings.model_label, "| mode", state.provider_mode, "| model calls", state.model_calls,
          "| tool calls", state.tool_calls, "| claims", len(state.claims), "| rejected", len(state.rejected_claims),
          "| elapsed ms", state.elapsed_ms, "| errors", state.errors)
    for t in state.trace:
        print("   ", t.agent, t.kind, t.tool or "", t.summary)
    assert state.provider_mode == settings.mode and not state.errors, state.errors  # a live run, not a fallback
    assert state.model_calls >= 4 and state.tool_calls >= 2
    assert state.claims and all(not validate_claim(c, {f.fact_id: f for f in state.facts}, make_view(bundle).players) for c in state.claims)
