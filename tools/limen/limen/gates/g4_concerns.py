"""G4 — concern coverage.

The completeness criterion from ISO/IEC/IEEE 42010, made mechanical: every
`C-nn` is framed by at least one section, and every section declares what it
frames — explicitly `—` when it frames nothing (STD-LIMEN-01 O-1/O-2).

An unframed concern is a coverage gap. A section framing no concern should be
cut; that is the tailoring mechanism working, not a nuisance finding.
"""
from __future__ import annotations

import re

from ..docset import DocSet
from ..model import GateResult

CONCERN_ID_RE = re.compile(r"^C-\d+$")
ROLES = {"uses", "operates", "builds", "audits", "funds", "governs"}
MIN_ROLES = 4


def _registered_concerns(docs: DocSet) -> tuple[dict[str, dict], str]:
    reg = docs.registers.get("concerns")
    if isinstance(reg, list):
        out = {}
        for entry in reg:
            if isinstance(entry, dict) and entry.get("id"):
                out[str(entry["id"])] = entry
        return out, "register"
    found = {}
    for f in docs.files:
        for m in re.finditer(r"\bC-\d+\b", f.text):
            found.setdefault(m.group(0), {})
    return found, "scanned"


def run(docs: DocSet, strict: bool = False) -> GateResult:
    gate = GateResult("G4", "Concern coverage")
    concerns, source = _registered_concerns(docs)
    sections = docs.sections()

    if not concerns:
        gate.fail("no stakeholder concerns found; L0.3 requires a concern register "
                  "with C-nn ids (STD-LIMEN-02 §3)")
        gate.detail = "no concerns registered"
        return gate
    if source == "scanned":
        gate.warn("no concerns register file found; ids were scanned out of the "
                  "prose, so stakeholder roles and priorities cannot be checked")

    if not sections:
        gate.fail("no sections with `L<level>.<n>` ids found; G4 cannot map "
                  "concerns to sections (STD-LIMEN-02 §23)")
        gate.detail = "no identifiable sections"
        return gate

    framed: dict[str, list[str]] = {cid: [] for cid in concerns}
    undeclared = 0
    dangling = 0

    for s in sections:
        if s.frames is None:
            undeclared += 1
            gate.fail(f"section {s.id} does not declare what it frames; add "
                      "`<!-- frames: C-01, C-02 -->` or `<!-- frames: — -->`",
                      file=s.file, line=s.line, detail={"section": s.id})
            continue
        for cid in s.frames:
            if not CONCERN_ID_RE.match(cid):
                gate.fail(f"section {s.id} frames '{cid}', which is not a C-nn id",
                          file=s.file, line=s.line)
                continue
            if cid not in concerns:
                dangling += 1
                gate.fail(f"section {s.id} frames {cid}, which is not in the concern "
                          "register", file=s.file, line=s.line,
                          detail={"section": s.id, "concern": cid})
                continue
            framed[cid].append(s.id)

    unframed = [cid for cid, secs in framed.items() if not secs]
    for cid in sorted(unframed):
        entry = concerns.get(cid) or {}
        text = str(entry.get("concern", "")).strip()
        gate.fail(f"{cid} is framed by no section" + (f": \"{text[:80]}\"" if text else "")
                  + " — an unframed concern is a coverage gap",
                  detail={"concern": cid, "stakeholder": entry.get("stakeholder")})

    if source == "register":
        _check_roles(gate, concerns, strict)
        _check_declared_framing(gate, concerns, framed)

    gate.stats = {
        "concerns": len(concerns),
        "sections": len(sections),
        "unframed": len(unframed),
        "sections_without_declaration": undeclared,
        "dangling_refs": dangling,
    }
    gate.detail = (f"{len(concerns)} concern(s), {len(unframed)} unframed, "
                   f"{undeclared} section(s) without a frames declaration")
    return gate


def _check_roles(gate: GateResult, concerns: dict, strict: bool) -> None:
    roles = {str(e.get("role", "")).lower() for e in concerns.values() if e.get("role")}
    roles.discard("")
    unknown = roles - ROLES
    for r in sorted(unknown):
        gate.warn(f"concern role '{r}' is not one of {sorted(ROLES)}")
    if len(roles) < MIN_ROLES:
        report = gate.fail if strict else gate.warn
        report(f"only {len(roles)} distinct stakeholder role(s) ({sorted(roles)}); "
               f"STD-LIMEN-03 C1 S1 expects at least {MIN_ROLES}. A register "
               "listing only builders has not been done")


def _check_declared_framing(gate: GateResult, concerns: dict, framed: dict) -> None:
    """The register's own framed_by should agree with the document."""
    for cid, entry in concerns.items():
        declared = entry.get("framed_by")
        if not isinstance(declared, list):
            continue
        actual = set(framed.get(cid, []))
        missing = [s for s in declared if s not in actual]
        if missing:
            gate.warn(f"{cid} claims to be framed by {missing}, but "
                      f"{'no such section declares it' if not actual else sorted(actual)}"
                      " — register and document disagree",
                      detail={"concern": cid, "declared": declared,
                              "actual": sorted(actual)})
