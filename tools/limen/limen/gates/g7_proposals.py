"""G7 — proposal hygiene.

Every `[T3]` carries an owner and a trigger (STD-LIMEN-01 T-2): a proposal
with neither is a wish, and the audit treats it as noise. No `[T3]` is written
in the present tense, and in greenfield mode nothing is (Rule M-2) — describing
unbuilt behavior as existing is the exact failure this standard was built to
prevent.
"""
from __future__ import annotations

import re

from ..docset import DocSet, FUTURE_RE, OWNER_RE, TRIGGER_RE
from ..model import GateResult

PROPOSED_PREFIX_RE = re.compile(r"\bproposed\s*[:—-]|\bproposal\b", re.I)
# "when the cache fills" is a trigger; "when in doubt" is not.
WEAK_TRIGGER_RE = re.compile(r"\b(?:when|if)\s+(?:needed|required|possible|appropriate)\b",
                             re.I)


def run(docs: DocSet, strict: bool = False) -> GateResult:
    gate = GateResult("G7", "Proposal hygiene")
    units = [u for u in docs.units() if "3" in u.tiers]

    if not units:
        gate.detail = "no [T3] proposals found"
        return gate

    no_owner = no_trigger = present_tense = 0

    for u in units:
        text = u.text
        has_owner = bool(OWNER_RE.search(text))
        has_trigger = bool(TRIGGER_RE.search(text)) and not (
            WEAK_TRIGGER_RE.search(text) and len(TRIGGER_RE.findall(text)) == 1
        )

        if not has_owner:
            no_owner += 1
            gate.fail("[T3] proposal has no owner; a proposal nobody owns is a wish "
                      "(Rule T-2). Name one as @handle or `owner: …`",
                      file=u.file, line=u.line, detail={"text": text[:160]})
        if not has_trigger:
            no_trigger += 1
            gate.fail("[T3] proposal has no trigger condition; state what would "
                      "cause it to be picked up (Rule T-2)",
                      file=u.file, line=u.line, detail={"text": text[:160]})

        if not (FUTURE_RE.search(text) or PROPOSED_PREFIX_RE.search(text)):
            present_tense += 1
            report = gate.fail if strict else gate.warn
            report("[T3] reads as present tense; prefix it 'Proposed:' or use "
                   "'will' so it cannot be mistaken for existing behavior",
                   file=u.file, line=u.line, detail={"text": text[:160]})

    gate.stats = {"proposals": len(units), "without_owner": no_owner,
                  "without_trigger": no_trigger, "present_tense": present_tense}
    gate.detail = (f"{len(units)} [T3] item(s): {no_owner} without owner, "
                   f"{no_trigger} without trigger")
    return gate
