"""G6 — tier tagging.

Every normative claim carries `[T0]`/`[T1]`/`[T2]`/`[T3]`. Tagging is what makes
the audit mechanical rather than interpretive (STD-LIMEN-01 T-3).

"Normative" cannot be decided perfectly by regex, so this gate targets the claims
that actually matter and leaves ordinary explanatory prose alone:

  FAIL  a unit carrying a provenance pointer but no tier tag — it asserts a fact
        about code without saying it is one
  FAIL  a table whose cells carry pointers or tier tags but which has no Tier
        column
  FAIL  a [T1] claim with no pointer, ADR reference or standard citation
  WARN  a unit stating a quantity (250 ms, 24 MiB, 99.9%) with no tier tag
        (FAIL under --strict)

Also enforces T-4: a [T2] synthesis may not introduce a factual claim absent
from its supporting [T1] set — approximated as "a [T2] unit carrying a pointer
is really an untagged [T1]".
"""
from __future__ import annotations

import re

from ..docset import DocSet
from ..model import GateResult

# An external standard is a legitimate T1 anchor in greenfield mode.
STANDARD_RE = re.compile(
    r"\b(?:RFC\s?\d{3,5}|ISO[/\s-]?\w+|IEEE\s?\d+|NIST\s?[\w.-]+|"
    r"OWASP|SOC\s?2|GDPR|PCI[\s-]?DSS|HIPAA|C4|arc42)\b", re.I
)
CITATION_RE = re.compile(r"\[[^\]]+\]\(https?://[^)]+\)|https?://\S+")
# An ADR reference anchors a [T1] claim as well as a code pointer does: the
# decision record is a file, and G12 proves it exists.
ADR_ANCHOR_RE = re.compile(r"\bADR-\d{1,4}\b")
EXEMPT_SECTIONS = {"L0.7"}     # discovery report is a table of raw findings


def run(docs: DocSet, strict: bool = False) -> GateResult:
    gate = GateResult("G6", "Tier tagging")
    units = docs.units()
    if not units:
        gate.detail = "no prose units found"
        return gate

    untagged_pointer = 0
    untagged_quantity = 0
    bad_t1 = 0
    laundered = 0

    for u in units:
        if u.section in EXEMPT_SECTIONS:
            continue
        tiers = u.tiers
        text = u.text

        if u.has_pointer and not tiers:
            untagged_pointer += 1
            gate.fail("claim carries a provenance pointer but no tier tag; a fact "
                      "about code is [T1] and must say so", file=u.file, line=u.line,
                      detail={"kind": u.kind, "text": text[:160]})
            continue

        if "1" in tiers and not u.has_pointer:
            anchored = (STANDARD_RE.search(text) or CITATION_RE.search(text)
                        or ADR_ANCHOR_RE.search(text))
            if not anchored:
                bad_t1 += 1
                gate.fail("[T1] claim has no provenance pointer, ADR reference or "
                          "external-standard citation; verified fact means "
                          "verifiable (STD-LIMEN-01 §4)",
                          file=u.file, line=u.line,
                          detail={"kind": u.kind, "text": text[:160]})

        if "2" in tiers and "1" not in tiers and u.has_pointer:
            laundered += 1
            gate.fail("[T2] synthesis carries its own provenance pointer, so it is "
                      "really an untagged [T1] fact (Rule T-4 anti-laundering)",
                      file=u.file, line=u.line, detail={"text": text[:160]})

        if not tiers and _asserts_quantity(text):
            untagged_quantity += 1
            report = gate.fail if strict else gate.warn
            report("claim states a quantity but carries no tier tag",
                   file=u.file, line=u.line,
                   detail={"kind": u.kind, "text": text[:160]})

    missing_col = _check_tables(gate, docs)

    gate.stats = {
        "units": len(units),
        "untagged_with_pointer": untagged_pointer,
        "untagged_with_quantity": untagged_quantity,
        "unsupported_t1": bad_t1,
        "laundered_t2": laundered,
        "tables_missing_tier_column": missing_col,
    }
    gate.detail = (f"{untagged_pointer} untagged pointer claim(s), {bad_t1} "
                   f"unsupported [T1], {missing_col} table(s) missing a Tier column")
    return gate


def _asserts_quantity(text: str) -> bool:
    from ..docset import QUANTITY_RE
    if not QUANTITY_RE.search(text):
        return False
    # Cross-references, headings and pure register rows are not claims.
    if re.match(r"^\s*(?:see|per|cf\.|§)\b", text, re.I):
        return False
    return True


def _check_tables(gate: GateResult, docs: DocSet) -> int:
    missing = 0
    for t in docs.tables():
        if t.section in EXEMPT_SECTIONS or not t.is_normative:
            continue
        if t.column("tier") is not None:
            _check_table_cells(gate, t)
            continue
        missing += 1
        gate.fail("table states grounded claims but has no Tier column; every "
                  "normative table needs one (STD-LIMEN-01 T-3)",
                  file=t.file, line=t.line,
                  detail={"headers": t.headers})
    return missing


def _check_table_cells(gate: GateResult, t) -> None:
    col = t.column("tier")
    for line, cells in t.rows:
        if col >= len(cells):
            continue
        cell = cells[col].strip()
        if not cell or cell in ("—", "-"):
            continue
        from ..docset import TIER_TAG_RE
        if not TIER_TAG_RE.search(cell):
            gate.warn(f"Tier cell {cell!r} is not a [T0]-[T3] tag",
                      file=t.file, line=line)
