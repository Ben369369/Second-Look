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
from app.simulation.compare import compare
from app.simulation.engine import BranchError

CATALOGUE: list[QuestionOption] = [
    QuestionOption(intent="press_timing", label="Pressing decision", example="Should the right-back have pressed earlier?"),
    QuestionOption(intent="passing_options", label="Passing options", example="What passing options did Harbor's #11 have?"),
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
    ("pass_distances", ("how long were", "pass length", "how far did the pass", "longest pass", "pass distance", "how far was the pass", "passes travel", "pass travel", "pass go")),
    ("possession", ("possession", "keep the ball", "kept the ball", "hold on to")),
    ("running", ("run", "ran", "distance covered", "covered the most", "cover the most", "most ground", "ground covered", "speed", "fast", "sprint", "how far did")),
    ("pressure", ("pressure", "pressed", "pressing", "press", "closed down", "close down")),
]
# Keywords match at the start of a word ("complet" matches "completed"; "run" does not match "Brunner").
RULE_RES = [(name, re.compile(r"\b(" + "|".join(re.escape(w) for w in words) + ")")) for name, words in RULES]

ROLE_WORDS = {
    "right-back": "RB", "right back": "RB", "left-back": "LB", "left back": "LB",
    "goalkeeper": "GK", "keeper": "GK", "striker": "ST", "winger": "LW",
}

# "What should have happened" questions. Only the right-back's pressing decision can be simulated.
DECISION_RE = re.compile(r"\b(should|shouldn't|what if|instead|would (it|he|she|they) have|had (he|she|they)|better (to|if|off)|could (he|she|they) have)\b")
PRESS_DECISION_RE = re.compile(r"\b(press(ed|ing)?|close[sd]? (him|her|them) down|closing down)\b")
OTHER_ACTION_RE = re.compile(
    r"\b(make (a|his|her|the) run|run (in )?(behind|forward|into|in)|made a run|drop(ped|ping)? (back|deep|in)|park(ed|ing)? the bus|"
    r"low block|shoot|shot|cross(ed)?|dribble|pass(ed)? (it|the ball)|switch(ed)? play|overlap)\b"
)
SUBJECT_RE = re.compile(
    r"\b(should|did|does|was|is|has|had|could|would|can|will)\s+([a-z'’-]+)\s+(?:have\s+|has\s+|had\s+|been\s+)?"
    r"(press|pressed|pressing|run|ran|make|made|hold|held|pass|passed|shoot|shot|go|went|move|moved|drop|dropped|stay|stayed|"
    r"track|tracked|close|closed|cover|covered|sprint|sprinted|play|played|do|did)\b"
)
# Words that can fill that subject slot without being a name.
SUBJECT_WORDS = {
    "the", "he", "she", "they", "it", "his", "her", "their", "we", "you", "i", "a", "an", "that", "this", "anyone", "someone",
    "everyone", "nobody", "somebody", "team", "player", "players", "defender", "defenders", "attacker", "attackers",
    "midfielder", "midfielders", "winger", "striker", "keeper", "goalkeeper", "fullback", "full-back", "right-back",
    "left-back", "harbor", "cedar", "number", "no", "shirt", "each", "every", "all", "both", "one", "who", "what",
}
SHIRT_RE = re.compile(r"(?:#\s?|\bnumber\s|\bno\.?\s?|\bshirt\s)(\d{1,2})\b")
# Capitalised words that are not player names (question words, football terms, team words).
NOT_NAMES = {
    "should", "would", "could", "what", "who", "whom", "how", "why", "when", "where", "which", "was", "were", "did", "does",
    "do", "is", "are", "can", "if", "the", "a", "an", "and", "or", "in", "at", "on", "after", "before", "then", "i", "he",
    "she", "they", "his", "her", "their", "it", "fc", "cedar", "harbor", "right", "left", "back", "ball", "team", "number",
    "no", "shirt", "attacking", "defending", "keeper", "goalkeeper", "striker", "winger", "midfielder", "defender",
    "forward", "fan", "analyst", "simulation", "press", "pressing", "pass", "passing", "hold", "holding", "yes", "ok",
}


@dataclass
class Route:
    intent: str | None
    players: list[str] = field(default_factory=list)
    teams: list[str] = field(default_factory=list)
    ambiguous: list[str] = field(default_factory=list)
    unknown_names: list[str] = field(default_factory=list)
    other_decision: bool = False  # a "should have" question about something the simulator does not model


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
    # "attacking #8" / "defending number 4": the team in possession, or the other one.
    side = teams
    if not teams and re.search(r"\b(attacking|attacker|in possession)\b", q):
        side = [_attacking_team(view, Route(intent=None))]
    elif not teams and re.search(r"\b(defending|defender)\b", q):
        att = _attacking_team(view, Route(intent=None))
        side = [t.team_id for t in view.manifest.teams if t.team_id != att]
    for num in SHIRT_RE.findall(q):
        cands = [p for p in view.players.values() if p.number == int(num) and (not side or p.team_id in side)]
        if len(cands) == 1:
            if cands[0].player_id not in players:
                players.append(cands[0].player_id)
        elif len(cands) > 1:
            notes.append(f"#{num} could be {' or '.join(view.label(c.player_id) for c in cands)}")
    for word, role in ROLE_WORDS.items():
        if word in q:
            cands = [p for p in view.players.values() if p.role == role and (not side or p.team_id in side)]
            if len(cands) == 1 and cands[0].player_id not in players:
                players.append(cands[0].player_id)
            elif len(cands) > 1:
                notes.append(f"'{word}' could be {' or '.join(view.label(c.player_id) for c in cands)}")
    return players, teams, notes


def unknown_names(view: SequenceView, question: str) -> list[str]:
    """Capitalised, name-like words that match no player or team in this sequence (e.g. "Messi")."""
    known = {w.lower() for p in view.players.values() for w in re.split(r"[\s.]+", p.name) if w}
    known |= {w.lower() for t in view.manifest.teams for w in t.name.split()}
    out: list[str] = []
    for m in re.finditer(r"\b[A-Z][a-zA-Z'’-]+", question):
        w = m.group(0)
        base = re.sub(r"['’]s$", "", w).lower()
        if base in known or base in NOT_NAMES or w in out:
            continue
        # A capitalised sentence opener ("Tell me ...") is only a name if a verb follows ("Messi should ...").
        opener = not question[: m.start()].strip() or question[: m.start()].rstrip()[-1] in ".?!"
        if opener and not re.match(r"\s+(should|was|did|is|could|would|has|had|pressed|made|ran)\b", question[m.end():], re.I):
            continue
        out.append(w)
    # Lower-case names in the subject slot ("should messi press", "how far did messi run").
    for m in SUBJECT_RE.finditer(question.lower()):
        w = m.group(2)
        base = re.sub(r"['’]s$", "", w)
        if base not in known and base not in NOT_NAMES and base not in SUBJECT_WORDS and not any(o.lower() == base for o in out):
            out.append(w)
    # Shirt numbers nobody in this sequence wears: a reference was given but resolves to no one.
    worn = {pl.number for pl in view.players.values()}
    for num in SHIRT_RE.findall(_norm(question)):
        if int(num) not in worn and f"#{int(num)}" not in out:
            out.append(f"#{int(num)}")
    return out


def route(view: SequenceView, question: str) -> Route:
    q = _norm(question)
    intent = next((name for name, rx in RULE_RES if rx.search(q)), None)
    players, teams, notes = resolve_players(view, q)
    r = Route(intent=intent, players=players, teams=teams, ambiguous=notes, unknown_names=unknown_names(view, question))
    if DECISION_RE.search(q):
        # A decision question is the pressing decision only if it is about pressing and no other action.
        if PRESS_DECISION_RE.search(q) and not OTHER_ACTION_RE.search(q):
            r.intent = "press_timing"
        elif re.search(r"\b(right-back|right back|halvorsen)\b", q) and re.search(r"\b(hold|held|stay(ed)?)\b", q) and not OTHER_ACTION_RE.search(q):
            r.intent = "press_timing"
        else:
            r.other_decision = True
    return r


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
    # The answer states the verdict and the paired comparisons; per-choice counts stay in the evidence.
    for f in facts:
        if f is not None and f.metric in ("sim_verdict", "sim_compare"):
            a.say(f)
    a.notes.append(
        f"Simulated results come from a rule-based model ({result.policy_version}, {result.config.rollouts} rollouts per choice, "
        f"cover delay {result.config.cover_delay_s} s, {result.config.attacker_policy} attackers). They are counts inside the simulator, "
        "not real-world probabilities. Change the assumptions on the Three choices page."
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
    if r.unknown_names:
        names = [n for n in r.unknown_names if not n.startswith("#")][:3]
        numbers = [n for n in r.unknown_names if n.startswith("#")][:3]
        missing = ([f"There is no player called {', '.join(names)} in this sequence."] if names else []) + (
            [f"No player wears {', '.join(numbers)} in this sequence."] if numbers else []
        )
        return AskResponse(
            **base, status="clarify", intent=r.intent, intent_label=LABELS.get(r.intent or ""), answer=[], facts=[], refused=[],
            notes=[" ".join(missing) + " Name a Cedar FC or Harbor FC player, or use a shirt number such as #8."],
        )
    if r.other_decision:
        # Honest refusal: only the right-back's press can be simulated. Show the passing picture at that moment instead.
        a = Answer(view)
        # The ball carrier at the pressing moment (the player Cedar's right-back pressed), else the latest carrier.
        press = next((e for e in view.events if e.type == "pressure_start" and view.players[e.player_id].role == "RB"), None)
        carrier = [press.related_player_ids[0]] if press and press.related_player_ids else []
        answer_passing_options(a, Route(intent="passing_options", players=carrier))
        return AskResponse(
            **base, status="unsupported", intent=None, intent_label=None, answer=a.sentences, facts=a.facts, refused=a.b.refused,
            notes=[
                "Second Look can only simulate one decision in this move: whether Cedar's right-back should have held, pressed "
                "earlier, or pressed with cover. It cannot test other what-ifs (runs, a deeper block, a midfielder dropping) yet, "
                "because each needs its own behaviour rules and tests. Here is what the data shows about the passing options at that moment."
            ],
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
    if r.intent == "press_timing":
        # Lead with the finding: the rule's verdict, then its comparisons, then what was measured.
        rank = {"sim_verdict": 0, "sim_compare": 1}
        metric = {f.fact_id: f.metric for f in a.facts}
        a.sentences.sort(key=lambda s: min((rank.get(metric.get(i, ""), 2) for i in s.fact_ids), default=2))
    return AskResponse(
        **base, status=status, intent=r.intent, intent_label=LABELS[r.intent], answer=a.sentences,
        facts=a.facts, refused=a.b.refused, notes=a.notes,
    )
