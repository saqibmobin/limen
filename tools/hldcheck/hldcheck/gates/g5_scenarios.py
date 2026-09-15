"""G5 — response measures.

Every `QA-nn` is a complete six-part SEI scenario with a *quantified* response
measure (STD-ARCH-HLD-01 Q-1, STD-ARCH-HLD-02 §7.2). "Fast" and "highly
available" are not response measures; the number is the whole point, because it
is what makes the scenario testable.

Also checks the downstream traces the standard requires: Q-2 (every SLO cites a
QA-nn) and the conflict set (C3 S2 — a conflict set where every attribute wins
is not a conflict set).
"""
from __future__ import annotations

import re

from ..docset import DocSet
from ..model import GateResult

SIX_PARTS = ["source", "stimulus", "artifact", "environment", "response",
             "response_measure"]
NUMERIC_RE = re.compile(r"\d")
PRIORITY_RE = re.compile(r"^[HML]$", re.I)
MIN_SCENARIOS = 5

VAGUE = {"fast", "quick", "responsive", "highly available", "high availability",
         "scalable", "reliable", "secure", "performant", "low latency",
         "good", "acceptable", "reasonable", "minimal", "as needed"}


def _quantified(value) -> bool:
    if isinstance(value, (int, float)):
        return True
    if isinstance(value, dict):
        return any(_quantified(v) for v in value.values())
    if isinstance(value, list):
        return any(_quantified(v) for v in value)
    if isinstance(value, str):
        return bool(NUMERIC_RE.search(value))
    return False


def run(docs: DocSet, strict: bool = False) -> GateResult:
    gate = GateResult("G5", "Response measures")
    reg = docs.registers.get("quality_scenarios")
    scanned = docs.id_count("quality_scenarios")

    if not isinstance(reg, list) or not reg:
        if scanned:
            gate.fail(f"{scanned} QA-nn id(s) appear in the document but there is no "
                      "quality-scenarios register; G5 needs the structured form "
                      "(STD-ARCH-HLD-02 §7.2)")
        else:
            gate.fail("no quality attribute scenarios found. Architecture is driven "
                      "by quality attributes; without them the trade-offs have no "
                      "axis (STD-ARCH-HLD-01 §3.4)")
        gate.detail = "no quality-scenarios register"
        return gate

    ids: set[str] = set()
    unquantified = 0
    incomplete = 0

    for i, entry in enumerate(reg):
        if not isinstance(entry, dict):
            gate.fail(f"quality-scenarios[{i}] is not a mapping")
            continue
        qid = str(entry.get("id", f"index {i}"))
        ids.add(qid)

        missing = [p for p in SIX_PARTS if not entry.get(p)]
        if missing:
            incomplete += 1
            gate.fail(f"{qid} is not a complete six-part scenario; missing "
                      f"{', '.join(missing)}", detail={"id": qid, "missing": missing})

        measure = entry.get("response_measure")
        if measure and not _quantified(measure):
            unquantified += 1
            gate.fail(f"{qid} response measure is not quantified: {measure!r}. "
                      "A quality attribute without a number is decoration (Q-1)",
                      detail={"id": qid, "response_measure": measure})
        elif isinstance(measure, str) and measure.strip().lower() in VAGUE:
            unquantified += 1
            gate.fail(f"{qid} response measure '{measure}' is a vague adjective, "
                      "not a measure", detail={"id": qid})

        _check_priority(gate, qid, entry, strict)
        _check_traces(gate, qid, entry, strict)

    if len(reg) < MIN_SCENARIOS:
        gate.warn(f"only {len(reg)} scenario(s); STD-ARCH-HLD-01 Q-3 expects at "
                  f"least {MIN_SCENARIOS}. A system with fewer than 3 high-importance "
                  "quality attributes probably wants the P5 lightweight profile")

    _check_conflict_set(gate, docs, reg, ids, strict)
    _check_slo_ancestry(gate, docs, ids, strict)

    gate.stats = {"scenarios": len(reg), "incomplete": incomplete,
                  "unquantified": unquantified}
    gate.detail = (f"{len(reg)} scenario(s), {incomplete} incomplete, "
                   f"{unquantified} unquantified")
    return gate


def _check_priority(gate: GateResult, qid: str, entry: dict, strict: bool) -> None:
    prio = entry.get("priority")
    if prio is None:
        report = gate.fail if strict else gate.warn
        report(f"{qid} has no (importance, difficulty) priority pair; the ATAM "
               "utility tree needs it to prioritize", detail={"id": qid})
        return
    if not isinstance(prio, dict):
        gate.fail(f"{qid} priority must be a mapping with importance and difficulty",
                  detail={"id": qid})
        return
    for key in ("importance", "difficulty"):
        val = str(prio.get(key, ""))
        if not PRIORITY_RE.match(val):
            gate.fail(f"{qid} priority.{key} must be H, M or L (got {val!r})",
                      detail={"id": qid})


def _check_traces(gate: GateResult, qid: str, entry: dict, strict: bool) -> None:
    """C3 S3: scenarios trace downstream to SLOs and fitness functions."""
    prio = entry.get("priority") or {}
    if str(prio.get("importance", "")).upper() != "H":
        return
    if not entry.get("fitness_function"):
        report = gate.fail if strict else gate.warn
        report(f"{qid} is high-importance but names no fitness function; an "
               "unenforced quality attribute is a hope (STD-ARCH-HLD-01 F-1)",
               detail={"id": qid})
    if not entry.get("derived_slo") and not entry.get("slo"):
        gate.warn(f"{qid} is high-importance but names no derived SLO",
                  detail={"id": qid})


def _check_conflict_set(gate: GateResult, docs: DocSet, reg: list,
                        ids: set[str], strict: bool) -> None:
    traded = set()
    for entry in reg:
        if isinstance(entry, dict):
            for other in entry.get("traded_against") or []:
                traded.add(str(other))

    table_conflicts = 0
    for t in docs.tables():
        if t.column("tension") is not None and t.column("winner") is not None:
            table_conflicts += len(t.rows)

    if not traded and not table_conflicts:
        report = gate.fail if strict else gate.warn
        report("no conflict set found: no scenario declares `traded_against` and no "
               "conflict table is present. A quality model where nothing competes "
               "has not been prioritized (STD-ARCH-HLD-02 §7.3)")
        return

    dangling = [t for t in traded if t not in ids]
    for t in sorted(dangling):
        gate.fail(f"conflict set references {t}, which is not a registered scenario")


def _check_slo_ancestry(gate: GateResult, docs: DocSet, ids: set[str],
                        strict: bool) -> None:
    """Q-2: every SLO cites the QA-nn it derives from."""
    for t in docs.tables():
        derived = t.column("derived from", "derivedfrom", "scenario", "qa")
        header_blob = " ".join(t.headers).lower()
        if "sli" not in header_blob and "slo" not in header_blob:
            continue
        if derived is None:
            report = gate.fail if strict else gate.warn
            report("SLO table has no column tracing each SLO to a QA-nn scenario; "
                   "an SLO with no L1 ancestor measures something nobody "
                   "prioritized (Q-2)", file=t.file, line=t.line)
            continue
        for line, cells in t.rows:
            if derived >= len(cells):
                continue
            refs = re.findall(r"\bQA-\d+\b", cells[derived])
            if not refs:
                gate.fail("SLO row does not cite a QA-nn scenario (Q-2)",
                          file=t.file, line=line)
            for r in refs:
                if ids and r not in ids:
                    gate.fail(f"SLO cites {r}, which is not a registered scenario",
                              file=t.file, line=line)
