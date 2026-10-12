"""uncertainty — unknowns and proposals are honest.

Checks the claims whose tier says something is not yet true (LIMEN.md §3.1):

  FAIL  a tag token that is not a tag: bare in prose, inside a longer code span,
        or a 5.x `[Tn]` token
  FAIL  an `[unknown]` claim that names no open question
  FAIL  a reference to an open question the document does not define
  FAIL  a `[proposed]` claim with no owner, or no trigger

An open question is defined by a table row whose first cell is its `Q-nn` id, or
by an entry in a YAML register beside the document.
"""
from __future__ import annotations

import re

from ..docset import QID_RE, DocSet
from ..model import CheckResult

OWNER_RE = re.compile(r"(?:@[\w][\w.-]*|\bowner\s*[:=]\s*\S+)", re.I)
TRIGGER_RE = re.compile(
    r"\b(?:trigger|triggered|revisit|re-?open|when\b|once\b|if\b|upon\b|"
    r"threshold|expires?|deadline)\b", re.I
)
# "when the cache fills" is a trigger; "when needed" is not.
WEAK_TRIGGER_RE = re.compile(
    r"\b(?:when|if)\s+(?:needed|required|possible|appropriate)\b", re.I)


def run(docs: DocSet, strict: bool = False) -> CheckResult:
    check = CheckResult("uncertainty", "Unknowns and proposals are honest")
    defined = docs.question_ids()
    stray = unanchored = ownerless = triggerless = 0
    counts = {"unknown": 0, "proposed": 0}

    for u in docs.units():
        text = u.text
        if bad := u.stray_tags:
            stray += 1
            legacy = [t for t in bad if t.startswith("T")]
            if legacy:
                msg = (f"5.x tag `[{legacy[0]}]`: run `limen migrate` to rewrite it, "
                       "or check with --legacy")
            else:
                msg = ("tag is not in its own code span. A tag is a code span "
                       f"holding exactly `[{bad[0]}]`; if this discusses a tier, name "
                       "it in plain words")
            check.fail(msg, file=u.file, line=u.line, detail={"text": text[:160]})
            continue

        if "unknown" in u.tags:
            counts["unknown"] += 1
            if not QID_RE.search(text):
                unanchored += 1
                check.fail("`[unknown]` claim names no open question; give it a "
                           "`Q-nn` with an owner and a way to resolve it",
                           file=u.file, line=u.line, detail={"text": text[:160]})

        if "proposed" in u.tags:
            counts["proposed"] += 1
            if not OWNER_RE.search(text):
                ownerless += 1
                check.fail("`[proposed]` claim has no owner; a proposal nobody owns "
                           "is a wish. Name one as @handle or `owner: ...`",
                           file=u.file, line=u.line, detail={"text": text[:160]})
            triggers = TRIGGER_RE.findall(text)
            if not triggers or (WEAK_TRIGGER_RE.search(text) and len(triggers) == 1):
                triggerless += 1
                check.fail("`[proposed]` claim has no trigger; say what would cause "
                           "it to be picked up",
                           file=u.file, line=u.line, detail={"text": text[:160]})

    dangling: set[str] = set()
    for qid, rel, line in docs.question_refs():
        if qid not in defined and qid not in dangling:
            dangling.add(qid)
            check.fail(f"{qid} is referenced but the document never defines it",
                       file=rel, line=line)

    check.stats = {"unknown": counts["unknown"], "proposed": counts["proposed"],
                   "questions": len(defined), "stray_tags": stray,
                   "unknown_without_question": unanchored,
                   "proposed_without_owner": ownerless,
                   "proposed_without_trigger": triggerless,
                   "dangling_questions": len(dangling)}
    check.detail = (f"{counts['unknown']} unknown, {counts['proposed']} proposed, "
                    f"{len(defined)} open question(s) defined")
    return check
