"""Supported question catalogue and the offline (rule-based) question router.

The router only picks an intent and its subjects; every number in the answer
comes from FactBuilder. In foundry mode (Stage 5) a model-backed planner will
replace `route`, producing the same typed Route.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.metrics.facts import FactBuilder, simulated_facts, with_plain
from app.metrics.view import SequenceView
from app.schemas import AnswerSentence, AskResponse, CompareRequest, Fact, MatchEvent, QuestionOption, ReplayBundle
from app.simulation.compare import LABELS as SIM_LABELS
from app.simulation.compare import compare
from app.simulation.engine import BranchError

CATALOGUE: list[QuestionOption] = [
    QuestionOption(intent="press_timing", label="Pressing decision", example="Should the right-back have pressed earlier?"),
    QuestionOption(intent="passing_options", label="Passing options", example="What passing options did #11 have?"),
    QuestionOption(intent="pass_distances", label="Pass lengths", example="How long were Harbor's passes?"),
    QuestionOption(intent="pass_completion", label="Pass completion", example="How many passes did Harbor complete?"),
    QuestionOption(intent="possession", label="Possession spells", example="How long did Harbor keep the ball?"),
    QuestionOption(intent="running", label="Distance and speed", example="How far did Halvorsen run?"),
    QuestionOption(intent="pressure", label="Pressure applied", example="Who pressed whom, and when?"),
    QuestionOption(intent="final_third", label="Final-third activity", example="How much of Harbor's play was in the final third?"),
]
LABELS = {q.intent: q.label for q in CATALOGUE}

# Keyword rules, checked in order; the first intent with a hit wins.
RULES: list[tuple[str, tuple[str, ...]]] = [
    ("press_timing", ("pressed earlier", "press earlier", "pressed sooner", "press sooner", "should have pressed", "should the right-back", "too late", "pressed late", "press late")),
    ("passing_options", ("option", "lane", "open", "available", "who could he pass", "who could she pass")),
    ("final_third", ("final third", "attacking third")),
    ("pass_completion", ("complet", "accura", "how many passes", "misplaced")),
    ("pass_distances", ("how long were", "pass length", "how far did the pass", "longest pass", "pass distance", "how far was the pass", "passes travel")),
    ("possession", ("possession", "keep the ball", "kept the ball", "hold on to")),
    ("running", ("run", "ran", "distance covered", "cover", "speed", "fast", "sprint", "ground")),
    ("pressure", ("pressure", "pressed", "pressing", "press", "closed down", "close down")),
]

ROLE_WORDS = {
    "right-back": "RB", "right back": "RB", "left-back": "LB", "left back": "LB",
    "goalkeeper": "GK", "keeper": "GK", "striker": "ST", "winger": "LW",
}


@dataclass
class Route:
    intent: str | None
    players: list[str] = field(default_factory=list)
    teams: list[str] = field(default_factory=list)
    ambiguous: list[str] = field(default_factory=list)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().replace("’", "'")).strip()


def resolve_players(view: SequenceView, q: str) -> tuple[list[str], list[str], list[str]]:
    """(player ids, team ids, ambiguity notes) mentioned in the question."""
    players: list[str] = []
    notes: list[str] = []
    teams = [t.team_id for t in view.manifest.teams if t.name.lower().split()[0] in q]
    for p in view.players.values():
        if p.name.split()[-1].lower() in q and p.player_id not in players:
            players.append(p.player_id)
    for num in re.findall(r"#\s?(\d{1,2})\b", q):
        cands = [p for p in view.players.values() if p.number == int(num) and (not teams or p.team_id in teams)]
        if len(cands) == 1:
            if cands[0].player_id not in players:
                players.append(cands[0].player_id)
        elif len(cands) > 1:
            notes.append(f"#{num} could be {' or '.join(view.label(c.player_id) for c in cands)}")
    for word, role in ROLE_WORDS.items():
        if word in q:
            cands = [p for p in view.players.values() if p.role == role and (not teams or p.team_id in teams)]
            if len(cands) == 1 and cands[0].player_id not in players:
                players.append(cands[0].player_id)
            elif len(cands) > 1:
                notes.append(f"'{word}' could be {' or '.join(view.label(c.player_id) for c in cands)}")
    return players, teams, notes


def route(view: SequenceView, question: str) -> Route:
    q = _norm(question)
    intent = next((name for name, words in RULES if any(w in q for w in words)), None)
    players, teams, notes = resolve_players(view, q)
    return Route(intent=intent, players=players, teams=teams, ambiguous=notes)


# ---------------------------------------------------------------------------
# Answer composition
# ---------------------------------------------------------------------------


class Answer:
    def __init__(self, view: SequenceView):
        self.v = view
        self.b = FactBuilder(view)
        self.facts: list[Fact] = []
        self.sentences: list[AnswerSentence] = []
        self.notes: list[str] = []

    def add(self, fact: Fact | None) -> Fact | None:
        if fact is not None and not fact.plain:
            fact = with_plain(self.v, [fact])[0]
        if fact is not None and fact.fact_id not in {f.fact_id for f in self.facts}:
            self.facts.append(fact)
        return fact

    def say(self, *facts: Fact | None, text: str | None = None) -> None:
        real = [f for f in facts if f is not None]
        if not real:
            return
        self.sentences.append(AnswerSentence(text=text or " ".join(f.statement for f in real), fact_ids=[f.fact_id for f in real]))


def _events(view: SequenceView, type_: str, **match) -> list[MatchEvent]:
    return [e for e in view.events if e.type == type_ and all(getattr(e, k) == val for k, val in match.items())]


def _attacking_team(view: SequenceView, r: Route) -> str:
    if r.teams:
        return r.teams[0]
    # Default: the team with the most on-ball events in the view.
    counts: dict[str, int] = {}
    for e in view.events:
        if e.type in ("pass", "carry", "shot"):
            counts[e.team_id] = counts.get(e.team_id, 0) + 1
    return max(counts, key=counts.get) if counts else view.manifest.teams[0].team_id  # type: ignore[arg-type]


def answer_press_timing(a: Answer, r: Route) -> str:
    v = a.v
    pressers = [p for p in r.players if _events(v, "pressure_start", player_id=p)]
    if not pressers:
        who = ", ".join(v.label(p) for p in r.players) or "the right-back"
        a.notes.append(f"No press by {who} is recorded before the data cutoff, so there is no pressing moment to examine yet.")
        return "insufficient_data"
    presser = pressers[0]
    press = _events(v, "pressure_start", player_id=presser)[0]
    target = press.related_player_ids[0]
    rec = [e for e in _events(v, "reception", player_id=target) if e.time_s <= press.time_s]
    if not rec:
        a.notes.append("The pressed player's reception is not in the available data.")
        return "insufficient_data"
    rec = rec[-1]
    a.say(a.add(a.b.defender_distance(presser, target, rec.time_s, "when the ball arrived", rec)))
    a.say(a.add(a.b.response_time(press, rec)))
    nxt = next((e for e in v.events if e.type in ("pass", "shot") and e.player_id == target and e.time_s >= press.time_s), None)
    if nxt is None:
        a.notes.append("What the pressed player did next is after the data cutoff.")
        _add_simulation(a, presser)
        return "answered"
    if nxt.type == "pass" and nxt.recipient_id:
        a.say(a.add(a.b.defender_distance(presser, target, nxt.time_s, "as the ball was released", nxt)))
        a.say(a.add(a.b.open_lanes(target, nxt.time_s, nxt)))
        a.say(a.add(a.b.lane_access(target, nxt.recipient_id, nxt.time_s, nxt)))
        a.say(a.add(a.b.pass_distance(nxt)))
    spells = [f for f in a.b.possession_duration(v.team_of(target)) if f.time_window.start_s <= nxt.time_s <= f.time_window.end_s]
    for f in spells:
        a.say(a.add(f))
    _add_simulation(a, presser)
    return "answered"


def _add_simulation(a: Answer, presser: str) -> None:
    """Counterfactual part: the default-assumption comparison from the pass that triggered the press.

    The simulator reads only the branch frame, which is within the cutoff, so this
    respects the same data cutoff as the observed facts.
    """
    v = a.v
    bundle = ReplayBundle(manifest=v.manifest, frames=v.frames, events=v.events)
    try:
        result = compare(bundle, CompareRequest(presser_id=presser))
    except BranchError as exc:
        a.notes.append(f"No simulated comparison: {exc}.")
        return
    facts = [a.add(f) for f in simulated_facts(v, result)]
    for f in facts:
        a.say(f)
    rec = result.recommendation
    verdict = (
        f"Under the predeclared decision rule, the simulations favour '{SIM_LABELS[rec.action].lower()}'."
        if rec.status == "recommend" and rec.action
        else "Under the predeclared decision rule, no choice is clearly best in these simulations."
    )
    a.sentences.append(AnswerSentence(text=verdict, fact_ids=[f.fact_id for f in facts if f is not None]))
    a.notes.append(
        f"Simulated results come from a rule-based model ({result.policy_version}, {result.config.rollouts} rollouts per choice, "
        f"cover delay {result.config.cover_delay_s} s, {result.config.attacker_policy} attackers). They are counts inside the simulator, "
        "not real-world probabilities. Change the assumptions on the What if? page."
    )


def answer_passing_options(a: Answer, r: Route) -> str:
    v = a.v
    # Named player, else the most recent ball carrier before the cutoff.
    carrier = r.players[0] if r.players else next(
        (f.ball.possession_player_id for f in reversed(v.frames) if f.ball and f.ball.possession_player_id), None
    )
    if carrier is None:
        a.notes.append("No ball carrier is known at the data cutoff.")
        return "insufficient_data"
    passes = _events(v, "pass", player_id=carrier)
    moments = [(p.time_s, p) for p in passes] or [(v.cursor_s, None)]
    for t, ev in moments:
        a.say(a.add(a.b.open_lanes(carrier, t, ev)))
        if ev is not None and ev.recipient_id:
            a.say(a.add(a.b.lane_access(carrier, ev.recipient_id, t, ev)))
    return "answered"


def answer_pass_distances(a: Answer, r: Route) -> str:
    v = a.v
    team = _attacking_team(v, r)
    passes = [e for e in _events(v, "pass", team_id=team) if not r.players or e.player_id in r.players or e.recipient_id in r.players]
    for p in passes:
        a.say(a.add(a.b.pass_distance(p)))
    return "answered" if a.facts else "insufficient_data"


def answer_pass_completion(a: Answer, r: Route) -> str:
    team = _attacking_team(a.v, r)
    a.say(a.add(a.b.pass_completion(team, 0.0, a.v.cursor_s)))
    return "answered" if a.facts else "insufficient_data"


def answer_possession(a: Answer, r: Route) -> str:
    for f in a.b.possession_duration(r.teams[0] if r.teams else None):
        a.say(a.add(f))
    a.say(a.add(a.b.transitions(0.0, a.v.cursor_s)))
    return "answered" if a.facts else "insufficient_data"


def answer_running(a: Answer, r: Route) -> str:
    v = a.v
    players = r.players
    if not players:
        # Top three by distance across all players.
        cands = [a.b.tracked_running(pid, 0.0, v.cursor_s) for pid in v.players]
        ranked = sorted([f for f in cands if f], key=lambda f: -(f.value or 0))[:3]
        if ranked:  # per-player refusals are noise once there is a ranking
            a.b.refused = [x for x in a.b.refused if x.metric != "tracked_running"]
        for f in ranked:
            a.say(a.add(f))
        if ranked:
            a.notes.append("No player named, so showing the three who covered the most ground.")
    for pid in players:
        a.say(a.add(a.b.tracked_running(pid, 0.0, v.cursor_s)))
    return "answered" if a.facts else "insufficient_data"


def answer_pressure(a: Answer, r: Route) -> str:
    v = a.v
    for e in _events(v, "pressure_start"):
        if r.players and e.player_id not in r.players and e.related_player_ids[0] not in r.players:
            continue
        a.say(a.add(a.b.defender_distance(e.player_id, e.related_player_ids[0], e.time_s, "when pressure began", e)))  # type: ignore[arg-type]
    if not a.facts:
        a.notes.append("No pressure events before the data cutoff.")
        return "insufficient_data"
    return "answered"


def answer_final_third(a: Answer, r: Route) -> str:
    team = _attacking_team(a.v, r)
    a.say(a.add(a.b.final_third_share(team, 0.0, a.v.cursor_s)))
    return "answered" if a.facts else "insufficient_data"


HANDLERS = {
    "press_timing": answer_press_timing,
    "passing_options": answer_passing_options,
    "pass_distances": answer_pass_distances,
    "pass_completion": answer_pass_completion,
    "possession": answer_possession,
    "running": answer_running,
    "pressure": answer_pressure,
    "final_third": answer_final_third,
}


def ask(view: SequenceView, question: str) -> AskResponse:
    r = route(view, question)
    base = dict(
        question=question,
        matched_by="offline-rules",
        cursor_s=view.cursor_s,
        dataset_hash=view.manifest.dataset_hash,
        supported_questions=CATALOGUE,
    )
    if r.intent is None:
        return AskResponse(
            **base, status="unsupported", intent=None, intent_label=None, answer=[], facts=[], refused=[],
            notes=["That question isn't one Second Look can answer from this data yet. Try one of the supported questions."],
        )
    if r.ambiguous and r.intent != "press_timing":
        return AskResponse(
            **base, status="clarify", intent=r.intent, intent_label=LABELS[r.intent], answer=[], facts=[], refused=[],
            notes=[f"Which player did you mean? {n}." for n in r.ambiguous],
        )
    if r.intent == "press_timing" and not r.players:
        # "the right-back" without a team: the defending right-back is the one who pressed.
        r.players = [p for p in view.players if view.players[p].role == "RB" and _events(view, "pressure_start", player_id=p)]
    a = Answer(view)
    status = HANDLERS[r.intent](a, r)
    return AskResponse(
        **base, status=status, intent=r.intent, intent_label=LABELS[r.intent], answer=a.sentences,
        facts=a.facts, refused=a.b.refused, notes=a.notes,
    )
