"""G11 — mode discipline.

Modes exist so a reader always knows whether a sentence describes what is or
what is proposed. The two ways that breaks:

  greenfield          present-tense description of unbuilt behavior (Rule M-2)
  brownfield-change   a paragraph mixing as-is and to-be (Rule M-1), or a
                      missing migration plan (L3.8)

Marker checks are deterministic and fail. Tense detection is heuristic and warns
unless --strict, because English is not a grammar this tool can fully parse.
"""
from __future__ import annotations

import re

from ..docset import ASIS_RE, DocSet, FUTURE_RE, PRESENT_CLAIM_RE, TOBE_RE
from ..model import GateResult

MIGRATION_HEADING_RE = re.compile(
    r"\bL3\.8\b|\bmigration\b|\bdecommission\b|\bstrangler\b|\bcutover\b", re.I
)
DELTA_HEADER_HINTS = (("as-is", "to-be"), ("asis", "tobe"), ("current", "target"))


def run(docs: DocSet, strict: bool = False) -> GateResult:
    gate = GateResult("G11", "Mode discipline")
    mode = str(docs.front.get("mode", "")).strip()

    if not mode:
        gate.fail("no `mode` in front matter; mode determines which sections are "
                  "required and how evidence is judged (STD-ARCH-HLD-01 §1)")
        gate.detail = "no mode declared"
        return gate

    if mode == "greenfield":
        stats = _greenfield(gate, docs, strict)
    elif mode == "brownfield-change":
        stats = _brownfield_change(gate, docs, strict)
    elif mode == "brownfield-asis":
        stats = _brownfield_asis(gate, docs, strict)
    else:
        gate.fail(f"unknown mode '{mode}'")
        return gate

    gate.stats = {"mode": mode, **stats}
    gate.detail = f"mode {mode}: " + ", ".join(f"{k}={v}" for k, v in stats.items())
    return gate


def _greenfield(gate: GateResult, docs: DocSet, strict: bool) -> dict:
    present = 0
    for u in docs.units():
        tiers = u.tiers
        if "1" in tiers:
            continue     # in greenfield, [T1] anchors to requirements and standards
        m = PRESENT_CLAIM_RE.search(u.text)
        if not m:
            continue
        if FUTURE_RE.search(u.text):
            continue
        present += 1
        report = gate.fail if strict else gate.warn
        report(f"greenfield document describes unbuilt behavior in the present "
               f"tense: \"{m.group(0)}…\". Use 'will' or 'Proposed:' (Rule M-2)",
               file=u.file, line=u.line, detail={"text": u.text[:160]})
    return {"present_tense_claims": present}


def _brownfield_change(gate: GateResult, docs: DocSet, strict: bool) -> dict:
    mixed = 0
    asis_units = tobe_units = 0

    for u in docs.units():
        has_asis, has_tobe = bool(ASIS_RE.search(u.text)), bool(TOBE_RE.search(u.text))
        asis_units += has_asis
        tobe_units += has_tobe
        if has_asis and has_tobe:
            mixed += 1
            gate.fail("this unit marks both [AS-IS] and [TO-BE]; no paragraph may "
                      "describe current and target state together (Rule M-1)",
                      file=u.file, line=u.line, detail={"text": u.text[:160]})
        elif has_asis and FUTURE_RE.search(u.text):
            report = gate.fail if strict else gate.warn
            report("an [AS-IS] unit uses future tense; if it needs 'will', it "
                   "belongs in a [TO-BE] block (Rule M-1)",
                   file=u.file, line=u.line, detail={"text": u.text[:160]})

    if not asis_units and not tobe_units:
        gate.fail("brownfield-change mode but the document uses no [AS-IS]/[TO-BE] "
                  "markers; as-is and to-be must be physically separate")
    elif not tobe_units:
        gate.fail("brownfield-change mode with no [TO-BE] content; the proposed "
                  "change is not described")

    migration = _has_migration_section(docs)
    if not migration:
        gate.fail("brownfield-change mode requires L3.8 Migration & decommission; "
                  "no such section found (STD-ARCH-HLD-01 §3.7.2)")
    else:
        _check_delta_table(gate, docs)

    return {"mixed_units": mixed, "asis_units": asis_units,
            "tobe_units": tobe_units, "migration_section": bool(migration)}


def _brownfield_asis(gate: GateResult, docs: DocSet, strict: bool) -> dict:
    """As-is documents must not smuggle in proposals as current behavior."""
    proposals = 0
    for u in docs.units():
        if "3" not in u.tiers:
            continue
        if ASIS_RE.search(u.text):
            proposals += 1
            report = gate.fail if strict else gate.warn
            report("[T3] proposal inside an [AS-IS] unit; brownfield-asis documents "
                   "describe what exists, with proposals kept separate",
                   file=u.file, line=u.line, detail={"text": u.text[:160]})
    return {"proposals_in_asis": proposals}


def _has_migration_section(docs: DocSet) -> bool:
    if any(s.id.startswith("L3.8") for s in docs.sections()):
        return True
    for f in docs.files:
        for n, line in enumerate(f.lines, 1):
            if f.fenced(n - 1) or not line.startswith("#"):
                continue
            if MIGRATION_HEADING_RE.search(line):
                return True
    return False


def _check_delta_table(gate: GateResult, docs: DocSet) -> None:
    for t in docs.tables():
        headers = " ".join(t.headers).lower()
        if any(a in headers and b in headers for a, b in DELTA_HEADER_HINTS):
            if t.column("class", "change") is None:
                gate.warn("delta table has no change-class column "
                          "(unchanged/modified/new/removed)",
                          file=t.file, line=t.line)
            return
    gate.warn("no as-is/to-be delta table found in the migration section "
              "(STD-ARCH-HLD-02 §20.1)")
