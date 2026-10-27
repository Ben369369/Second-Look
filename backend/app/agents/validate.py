"""Deterministic validation of claims against approved facts.

Factual claims (observed / estimated / simulated) must be the code-rendered
sentences of the facts they cite: a model chooses which facts to present, but it
never words a quantity, unit, player relation or comparison itself. Comparisons
between simulated choices are facts too (metric `sim_compare`, `sim_verdict`).

Interpretations are the only free text. They are checked for what code can
check (citations, numbers, named players, certainty and causal wording, events
the data does not contain, comparisons between choices, simulation labelling),
which limits what they can assert; it does not prove an interpretation true.
Anything that fails is rejected, never silently shown.
"""

from __future__ import annotations

import re

from app.schemas import Claim, Fact, Player

DIGIT_RE = re.compile(r"\d")
SIM_MARKERS = ("simulat", "in the model", "model run", "rollout")
NUMBER_WORDS = re.compile(
    r"\b(three|four|five|six|seven|eight|nine|ten|eleven|twelve|twenty|thirty|forty|fifty|hundred|thousand|percent|per cent|"
    r"twice|double|triple|half of|quarter of|majority|minority)\b"
)
CERTAINTY = re.compile(
    r"\b(guarantee[sd]?|always|never|certain(ly)?|definitely|undoubtedly|prove[sdn]?|impossible|inevitabl[ey]|"
    r"no doubt|for sure)\b"
)
CAUSAL = re.compile(r"\b(caused?|causes|because|due to|led to|leads to|resulted in|result of|responsible for)\b")
# Events this data never records; an interpretation asserting them is unsupported.
EVENT_WORDS = re.compile(r"\b(scored?|scoring|goals?|assists?|fouls?|fouled|tackled?|yellow card|red card|penalty|offside|injur(y|ed))\b")
COUNTERFACTUAL = re.compile(r"\b(would have|could have|might have|if (he|she|they) had|had (he|she|they))\b")
ACTIONS = {
    "hold": re.compile(r"\b(hold(ing)?|held|stay(ing|ed)? (back|in position))\b"),
    "press_earlier": re.compile(r"\bpress(ing|ed)? (earlier|sooner)\b"),
    "press_with_cover": re.compile(r"\b(cover(ing|ed)?|with cover)\b"),
}
COMPARATIVE = re.compile(r"\b(than|safer|riskier|better|worse|more|less|fewer|best|worst|prefer(able|red)?)\b")


def _squash(text: str) -> str:
    return " ".join(text.split())


def code_rendered(text: str, cited: list[Fact]) -> bool:
    """True if the text consists only of the cited facts' code-rendered sentences."""
    rest = _squash(text)
    sentences = sorted({_squash(s) for f in cited for s in (f.statement, f.plain) if s}, key=len, reverse=True)
    for s in sentences:
        rest = rest.replace(s, " ")
    return bool(sentences) and not rest.strip()


def validate_claim(claim: Claim, facts: dict[str, Fact], players: dict[str, Player]) -> list[str]:
    errors: list[str] = []
    cited = [facts[i] for i in claim.fact_ids if i in facts]
    unknown = [i for i in claim.fact_ids if i not in facts]
    if unknown:
        errors.append(f"cites unknown fact ids: {', '.join(unknown[:3])}")
    text = claim.text.lower()

    if claim.claim_type in ("interpretation", "insufficient_data"):
        if DIGIT_RE.search(claim.text) or NUMBER_WORDS.search(text):
            errors.append(f"{claim.claim_type} claims may not contain numbers or quantities")
        if claim.claim_type == "interpretation":
            if not cited:
                errors.append("interpretation must cite at least one approved fact")
            if m := CERTAINTY.search(text):
                errors.append(f"interpretation states certainty the evidence cannot support ('{m.group(0)}')")
            if m := CAUSAL.search(text):
                errors.append(f"interpretation makes a causal claim ('{m.group(0)}')")
            if m := EVENT_WORDS.search(text):
                errors.append(f"interpretation mentions an event the data does not record ('{m.group(0)}')")
            named = [a for a, rx in ACTIONS.items() if rx.search(text)]
            if len(named) >= 2 and COMPARATIVE.search(text):
                errors.append("interpretation compares choices; comparisons must come from a cited comparison fact")
            sim_cited = any(f.evidence_class == "simulated" for f in cited)
            if (sim_cited or COUNTERFACTUAL.search(text)) and not any(m in text for m in SIM_MARKERS):
                errors.append("interpretation about alternatives must say it refers to the simulation")
            if COUNTERFACTUAL.search(text) and not sim_cited:
                errors.append("counterfactual interpretation must cite simulated facts")
    else:
        if not cited:
            errors.append(f"{claim.claim_type} claim must cite at least one approved fact")
        elif not code_rendered(claim.text, cited):
            errors.append("factual claims must use the code-rendered sentences of the cited facts, not a rewording")
        classes = {f.evidence_class for f in cited}
        if claim.claim_type == "simulated":
            if classes - {"simulated"}:
                errors.append("simulated claim cites non-simulated facts")
            if not any(m in text for m in SIM_MARKERS):
                errors.append("simulated claim must say it is a simulation result")
        elif claim.claim_type == "observed" and classes - {"observed"}:
            errors.append(f"observed claim cites {', '.join(sorted(classes - {'observed'}))} facts")
        elif claim.claim_type == "estimated" and "estimated" not in classes:
            errors.append("estimated claim must cite at least one estimated fact")

    # Player references must be subjects of the cited facts.
    subjects = {s for f in cited for s in f.subject_ids}
    for pid, p in players.items():
        surname = p.name.split()[-1].lower()
        if re.search(rf"\b{re.escape(surname)}\b", text) and pid not in subjects:
            errors.append(f"names {p.name}, who is not a subject of the cited facts")
    return errors


def validate_claims(claims: list[Claim], facts: dict[str, Fact], players: dict[str, Player]) -> tuple[list[Claim], list[tuple[Claim, list[str]]]]:
    ok: list[Claim] = []
    bad: list[tuple[Claim, list[str]]] = []
    for c in claims:
        errs = validate_claim(c, facts, players)
        if errs:
            bad.append((c, errs))
        else:
            ok.append(c)
    return ok, bad
