"""Deterministic validation of model-written claims against approved facts.

A claim may only state numbers that appear in the facts it cites, may only name
players who are subjects of those facts, and must match the evidence class of
its citations. Anything else is rejected, never silently shown.
"""

from __future__ import annotations

import re

from app.schemas import Claim, Fact, Player

NUMBER_RE = re.compile(r"(?<![\w#])[-+]?\d+(?:\.\d+)?")
SIM_MARKERS = ("simulat", "in the model", "model run", "rollout")
# Small integers commonly used as plain words ("one of two options", "the 2nd half") are not quantities.
IGNORED_NUMBERS = {"0", "1", "2"}


def _numbers(text: str) -> set[str]:
    out = set()
    for m in NUMBER_RE.findall(text):
        n = m.lstrip("+")
        if "." in n:
            n = n.rstrip("0").rstrip(".")
        out.add(n)
    return out


def _fact_numbers(f: Fact) -> set[str]:
    nums = _numbers(f.statement) | _numbers(f.plain) | _numbers(f.unit)
    if f.value is not None:
        v = float(f.value)
        nums |= _numbers(f"{v:g}") | _numbers(f"{v:.1f}") | _numbers(f"{v:.0f}")
    return nums


def validate_claim(claim: Claim, facts: dict[str, Fact], players: dict[str, Player]) -> list[str]:
    errors: list[str] = []
    cited = [facts[i] for i in claim.fact_ids if i in facts]
    unknown = [i for i in claim.fact_ids if i not in facts]
    if unknown:
        errors.append(f"cites unknown fact ids: {', '.join(unknown[:3])}")

    numbers = _numbers(claim.text) - IGNORED_NUMBERS
    if claim.claim_type in ("interpretation", "insufficient_data"):
        if numbers:
            errors.append(f"{claim.claim_type} claims may not contain numbers ({', '.join(sorted(numbers))})")
    else:
        if not cited:
            errors.append(f"{claim.claim_type} claim must cite at least one approved fact")
        allowed = set().union(*(_fact_numbers(f) for f in cited)) if cited else set()
        stray = sorted(n for n in numbers if n not in allowed)
        if stray:
            errors.append(f"numbers not found in the cited facts: {', '.join(stray)}")

        classes = {f.evidence_class for f in cited}
        if claim.claim_type == "simulated":
            if classes - {"simulated"}:
                errors.append("simulated claim cites non-simulated facts")
            if not any(m in claim.text.lower() for m in SIM_MARKERS):
                errors.append("simulated claim must say it is a simulation result")
        elif claim.claim_type == "observed" and classes - {"observed"}:
            errors.append(f"observed claim cites {', '.join(sorted(classes - {'observed'}))} facts")
        elif claim.claim_type == "estimated" and "estimated" not in classes:
            errors.append("estimated claim must cite at least one estimated fact")

    # Player references must be subjects of the cited facts (interpretations may name any cited subject too).
    subjects = {s for f in cited for s in f.subject_ids}
    lowered = claim.text.lower()
    for pid, p in players.items():
        surname = p.name.split()[-1].lower()
        if re.search(rf"\b{re.escape(surname)}\b", lowered) and pid not in subjects:
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
