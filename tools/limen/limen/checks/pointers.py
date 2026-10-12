"""pointers — claims about code still point at real code.

Every `path@sha::symbol` pointer is resolved at the document's baseline commit,
and every quoted literal is compared with the code. With --at, each pointer is
resolved again at a second revision and drift is reported (LIMEN.md §9).

Also checked here, because the baseline is what pointers anchor to: the mode is
one the standard knows, a brownfield document has a baseline, and every
`[verified]` claim carries something a reader could check it against.

Outcomes per pointer: resolved | missing | value-changed | moved (drift only).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..docset import DocSet, Pointer
from ..gitio import Git
from ..model import CheckResult, Item
from ..resolver import find_literal, resolve

MODES = {"greenfield", "brownfield"}

# What else a `[verified]` claim may rest on besides a pointer: a decision
# record, a published standard, or a link (LIMEN.md §3.1).
STANDARD_RE = re.compile(
    r"\b(?:RFC\s?\d{3,5}|ISO[/\s-]?\w+|IEEE\s?\d+|NIST\s?[\w.-]+|"
    r"OWASP|SOC\s?2|GDPR|PCI[\s-]?DSS|HIPAA)\b", re.I
)
CITATION_RE = re.compile(r"\[[^\]]+\]\(https?://[^)]+\)|https?://\S+")
ADR_RE = re.compile(r"\bADR-\d{1,4}\b")


@dataclass
class PointerResult:
    pointer: Pointer
    outcome: str                 # resolved | missing | value-changed
    method: str = "none"
    line: int | None = None
    note: str = ""
    durable: bool = True


def _check_at(git: Git, rev: str, p: Pointer) -> PointerResult:
    kind = git.path_kind(rev, p.path)
    if kind is None:
        return PointerResult(p, "missing", note=f"path not found at {rev[:7]}")
    if kind == "tree":
        return PointerResult(p, "resolved", method="tree")

    text = git.blob_text(rev, p.path)
    if text is None:
        return PointerResult(p, "resolved", method="binary",
                             note="binary blob; symbol not verified", durable=False)

    res = resolve(p.path, text, p.symbol, p.line_start, p.line_end)
    if not res.found:
        detail = res.note or f"symbol '{p.symbol}' not found in {p.path}"
        return PointerResult(p, "missing", method=res.method, note=detail)

    result = PointerResult(p, "resolved", method=res.method, line=res.line,
                           note=res.note, durable=res.durable)
    if p.literal:
        matched, where = find_literal(text, res, p.literal)
        if not matched:
            result.outcome = "value-changed"
            result.note = (f"quoted literal {p.literal!r} not found at or near "
                           f"{p.symbol or p.path}")
        elif where and "outside symbol" in where:
            result.note = f"literal found {where}; the quote is weakly anchored"
            result.durable = False
    return result


def _check_front(check: CheckResult, docs: DocSet, has_pointers: bool) -> bool:
    """Mode and baseline. Returns False when pointers cannot be resolved."""
    src = docs.front_source
    mode = docs.mode
    if not docs.front:
        check.fail("no front matter: the first file must start with a YAML block "
                   "declaring at least `mode` (LIMEN.md §5.2)")
        return False
    if mode not in MODES:
        hint = (" (a 5.x mode: run `limen migrate`, or check with --legacy)"
                if mode.startswith("brownfield-") else "")
        check.fail(f"front matter `mode` is {mode or 'missing'!r}; expected "
                   f"greenfield or brownfield{hint}", file=src)
    if not docs.baseline:
        if mode == "brownfield":
            check.fail("a brownfield document needs a `baseline` commit in front "
                       "matter; every verified claim resolves against it", file=src)
            return False
        if has_pointers:
            check.fail("the document carries pointers but declares no `baseline` "
                       "commit to resolve them against", file=src)
            return False
    return True


def _check_bases(check: CheckResult, docs: DocSet) -> int:
    """Every `[verified]` claim carries a pointer, an ADR, a standard or a link."""
    bare = 0
    for u in docs.units():
        if "verified" not in u.tags or u.has_pointer:
            continue
        text = u.text
        if STANDARD_RE.search(text) or CITATION_RE.search(text) or ADR_RE.search(text):
            continue
        bare += 1
        check.fail("`[verified]` claim carries no pointer, ADR, standard or link, so "
                   "nobody can check it. Point at the code, or tag it `[inferred]` "
                   "and name the verified facts it rests on",
                   file=u.file, line=u.line, detail={"text": text[:160]})
    return bare


def run(docs: DocSet, git: Git | None, at: str | None = None,
        strict: bool = False) -> tuple[CheckResult, dict]:
    check = CheckResult("pointers", "Pointers resolve")
    drift = {"resolved": 0, "moved": 0, "missing": 0, "value_changed": 0}

    pointers = docs.pointers()
    if not _check_front(check, docs, bool(pointers)):
        check.detail = "no baseline to resolve against"
        return check, drift
    unbased = _check_bases(check, docs)

    for rel, line, what in docs.legacy_pointers():
        check.fail(f"pointer nobody else can resolve ({what}); use "
                   "`path@sha::symbol` with a repo-relative path", file=rel, line=line)

    if not pointers:
        if docs.mode == "brownfield":
            check.fail("a brownfield document with no pointers: verified claims must "
                       "point at the code they were read from")
            check.detail = "no pointers in a brownfield document"
        else:
            check.detail = "no pointers (greenfield)"
        return check, drift

    if git is None:
        check.skip("no repository to resolve pointers against")
        return check, drift
    baseline = git.rev_parse(docs.baseline)
    if baseline is None:
        check.fail(f"baseline commit {docs.baseline[:12]} is not in this repository; "
                   "fetch it (CI needs fetch-depth: 0) or re-pin the baseline",
                   file=docs.front_source)
        check.detail = "baseline commit unavailable"
        return check, drift

    at_rev = git.rev_parse(at) if at else None
    if at and at_rev is None:
        check.warn(f"--at revision '{at}' could not be resolved; drift scan skipped")

    counts = {"resolved": 0, "missing": 0, "value-changed": 0}
    weak = whole = mixed = 0
    for p in pointers:
        if not baseline.startswith(p.sha):
            mixed += 1
            check.fail(f"pointer uses commit {p.sha} but the baseline is "
                       f"{baseline[:7]}; one baseline per document version",
                       file=p.file, line=p.line, detail={"pointer": p.raw})
            continue

        result = _check_at(git, baseline, p)
        counts[result.outcome] += 1
        detail = {"pointer": p.raw, "method": result.method}
        if result.line:
            detail["resolved_line"] = result.line
        if result.note:
            detail["note"] = result.note

        if result.outcome == "missing":
            check.fail(f"unresolved: {result.note}", file=p.file, line=p.line,
                       detail=detail)
        elif result.outcome == "value-changed":
            check.fail(f"literal mismatch: {result.note}", file=p.file, line=p.line,
                       detail=detail)
        elif result.method in ("file", "tree"):
            whole += 1
            check.warn("whole-file pointer: a change inside the file cannot be seen "
                       "as drift. Name the symbol the claim is about",
                       file=p.file, line=p.line, detail=detail)
        elif not result.durable:
            weak += 1
            check.warn(f"weak pointer ({result.method}): "
                       f"{result.note or 'name a declaration, not a mention'}",
                       file=p.file, line=p.line, detail=detail)
        else:
            check.add(Item("pass", f"resolved via {result.method}", p.file, p.line,
                           detail))

        if at_rev and at_rev != baseline and result.outcome == "resolved":
            _record_drift(check, git, at_rev, p, result, drift)

    check.stats = {
        "total": len(pointers),
        "resolved": counts["resolved"],
        "missing": counts["missing"],
        "value_changed": counts["value-changed"],
        "mixed_baseline": mixed,
        "whole_file": whole,
        "weak": weak,
        "verified_without_basis": unbased,
    }
    check.detail = (f"{counts['resolved']}/{len(pointers)} resolve"
                    + (f", {counts['value-changed']} value-changed"
                       if counts["value-changed"] else "")
                    + (f", {whole} whole-file" if whole else ""))
    return check, drift


def _record_drift(check: CheckResult, git: Git, at_rev: str, p: Pointer,
                  baseline_result: PointerResult, drift: dict) -> None:
    """Compare the baseline outcome against the same pointer at --at."""
    now = _check_at(git, at_rev, p)
    if now.outcome == "missing":
        drift["missing"] += 1
        check.warn(f"DRIFT: no longer resolves at {at_rev[:7]}: {now.note}",
                   file=p.file, line=p.line,
                   detail={"pointer": p.raw, "drift": "missing"})
    elif now.outcome == "value-changed":
        drift["value_changed"] += 1
        check.warn(f"DRIFT: literal changed at {at_rev[:7]}: {now.note}",
                   file=p.file, line=p.line,
                   detail={"pointer": p.raw, "drift": "value-changed"})
    elif now.line != baseline_result.line:
        drift["moved"] += 1
        check.warn(f"DRIFT: symbol moved (line {baseline_result.line} to {now.line}) "
                   f"at {at_rev[:7]}; re-pin the baseline",
                   file=p.file, line=p.line,
                   detail={"pointer": p.raw, "drift": "moved",
                           "was_line": baseline_result.line, "now_line": now.line})
    else:
        drift["resolved"] += 1
