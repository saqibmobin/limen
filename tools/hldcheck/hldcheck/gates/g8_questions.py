"""G8 — open questions present.

Tier 0 is the load-bearing addition in v4: an agent with nowhere to put "I could
not determine this" will silently promote a guess to [T2]. This gate keeps that
escape hatch open and honest.

Note the unusual polarity: **an empty register fails.** An L0 with zero open
questions is a signal the agent is guessing, not a clean bill of health
(STD-ARCH-HLD-03 §5 G8). Nothing here penalizes disclosed uncertainty — Rule S-3
forbids that, because an auditor that punishes honest gaps trains the next agent
to fabricate.
"""
from __future__ import annotations

import re

from ..docset import DocSet, QID_RE
from ..model import GateResult

REQUIRED_FIELDS = ["question", "owner", "resolution_path"]
OPEN_STATUSES = {"open", None, ""}
KNOWN_STATUSES = {"open", "answered", "wont-resolve", "wontresolve", "closed"}


def run(docs: DocSet, strict: bool = False) -> GateResult:
    gate = GateResult("G8", "Open questions present")
    reg = docs.registers.get("open_questions")
    level = docs.front.get("level")

    entries: dict[str, dict] = {}
    if isinstance(reg, list):
        for e in reg:
            if isinstance(e, dict) and e.get("id"):
                entries[str(e["id"])] = e
    elif reg is not None:
        gate.fail("open-questions register is not a list")

    referenced: dict[str, tuple[str, int]] = {}
    for f in docs.files:
        for n, line in enumerate(f.lines, 1):
            if f.fenced(n - 1):
                continue
            for m in QID_RE.finditer(line):
                referenced.setdefault(m.group(0), (f.rel, n))

    if not isinstance(reg, list):
        if referenced:
            gate.fail(f"{len(referenced)} Q-nn id(s) appear in the document but there "
                      "is no open-questions register (STD-ARCH-HLD-02 §5)")
        else:
            gate.fail("no open-questions register. Every [T0] needs somewhere to "
                      "point, and an L0 with no open questions means the agent had "
                      "nowhere it was willing to admit uncertainty")
        gate.detail = "no open-questions register"
        return gate

    if not entries:
        gate.fail("the open-questions register is empty. An L0 with zero open "
                  "questions is a signal the agent is guessing; healthy is 5-20 at "
                  "L0, declining across gates")

    _check_entries(gate, entries, strict)
    orphan_t0 = _check_t0_links(gate, docs, entries)

    dangling = sorted(set(referenced) - set(entries))
    for qid in dangling:
        f, line = referenced[qid]
        gate.fail(f"{qid} is referenced but not in the register", file=f, line=line)

    unreferenced = sorted(set(entries) - set(referenced))
    for qid in unreferenced:
        gate.warn(f"{qid} is registered but never referenced from the document; "
                  "link it from the claim it blocks")

    open_count = sum(1 for e in entries.values()
                     if str(e.get("status", "open")).lower() in OPEN_STATUSES)
    if level == 0 and open_count == 0 and entries:
        gate.fail("no open questions remain at L0, but L0 is where uncertainty is "
                  "supposed to be highest")

    gate.stats = {"registered": len(entries), "open": open_count,
                  "referenced": len(referenced), "dangling": len(dangling),
                  "unreferenced": len(unreferenced), "orphan_t0": orphan_t0}
    gate.detail = (f"{len(entries)} question(s), {open_count} open, "
                   f"{len(dangling)} dangling reference(s)")
    return gate


def _check_entries(gate: GateResult, entries: dict, strict: bool) -> None:
    for qid, e in entries.items():
        status = str(e.get("status", "open")).lower()
        if status not in KNOWN_STATUSES:
            gate.fail(f"{qid} has unknown status '{status}'; expected one of "
                      f"{sorted(KNOWN_STATUSES)}")
        is_open = status in OPEN_STATUSES

        for field in REQUIRED_FIELDS:
            if e.get(field):
                continue
            if field == "question" or is_open:
                gate.fail(f"{qid} is missing `{field}`; an open question without an "
                          "owner and a resolution path will never be resolved",
                          detail={"id": qid})

        if status == "answered" and not e.get("answer"):
            gate.fail(f"{qid} is marked answered but records no answer",
                      detail={"id": qid})
        if is_open and not e.get("blocks"):
            report = gate.fail if strict else gate.warn
            report(f"{qid} does not say what it blocks; without that nobody can "
                   "judge its priority", detail={"id": qid})
        if not e.get("matters_because") and is_open:
            gate.warn(f"{qid} does not say why it matters", detail={"id": qid})


def _check_t0_links(gate: GateResult, docs: DocSet, entries: dict) -> int:
    """Every [T0] claim must resolve to a Q-nn."""
    orphans = 0
    for u in docs.units():
        if "0" not in u.tiers:
            continue
        refs = QID_RE.findall(u.text)
        if not refs:
            orphans += 1
            gate.fail("[T0] claim does not reference a Q-nn; open questions must be "
                      "registered, not left floating in prose",
                      file=u.file, line=u.line, detail={"text": u.text[:160]})
            continue
        for r in refs:
            if r not in entries:
                gate.fail(f"[T0] claim references {r}, which is not registered",
                          file=u.file, line=u.line)
    return orphans
