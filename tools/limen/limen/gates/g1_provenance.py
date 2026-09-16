"""G1 — provenance resolves.

Every `[T1]` claim carries a `path@sha::symbol` pointer. This gate resolves all
of them against the declared baseline commit and, with --at, against a second
revision to report drift (STD-LIMEN-01 §5, STD-LIMEN-03 §5-§6).

Outcomes per pointer: resolved | missing | value-changed | moved (drift only).
"""
from __future__ import annotations

from dataclasses import dataclass

from ..docset import DocSet, Pointer
from ..gitio import Git
from ..model import GateResult, Item
from ..resolver import find_literal, resolve

DEFAULT_MIN_RESOLUTION = 0.95


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
            result.note = (f"asserted literal {p.literal!r} not found at or near "
                           f"{p.symbol or p.path}")
        elif where and "outside symbol" in where:
            result.note = f"literal found {where}; assertion is weakly anchored"
            result.durable = False
    return result


def run(docs: DocSet, git: Git, at: str | None = None,
        min_resolution: float = DEFAULT_MIN_RESOLUTION,
        strict: bool = False) -> tuple[GateResult, dict]:
    gate = GateResult("G1", "Provenance resolves")
    drift = {"resolved": 0, "moved": 0, "missing": 0, "value_changed": 0}

    repo = docs.front.get("repo") or {}
    baseline = str(repo.get("commit", "")).lower()
    short = str(repo.get("short", "")).lower()
    if not baseline:
        gate.fail("no `repo.commit` in front matter; provenance cannot be anchored")
        gate.detail = "no baseline declared"
        return gate, drift

    resolved_baseline = git.rev_parse(baseline)
    if resolved_baseline is None:
        gate.fail(f"baseline commit {baseline[:12]} is not present in this repository; "
                  "fetch it or re-pin the baseline before validating")
        gate.detail = "baseline commit unavailable"
        return gate, drift

    for rel, line, what in docs.legacy_pointers():
        gate.fail(f"forbidden pointer form ({what}); use `path@sha::symbol` "
                  "(STD-LIMEN-01 §5.1)", file=rel, line=line)

    pointers = docs.pointers()
    if not pointers:
        if str(docs.front.get("mode", "")).startswith("brownfield"):
            gate.fail("no provenance pointers found in a brownfield document; "
                      "[T1] claims must be anchored to code")
            gate.detail = "no pointers in a brownfield document"
        else:
            gate.detail = "no pointers (greenfield)"
        return gate, drift

    counts = {"resolved": 0, "missing": 0, "value-changed": 0}
    low_durability = 0
    mixed = 0

    at_rev = git.rev_parse(at) if at else None
    if at and at_rev is None:
        gate.warn(f"--at revision '{at}' could not be resolved; drift scan skipped")

    for p in pointers:
        if not (baseline.startswith(p.sha) or (short and p.sha.startswith(short))
                or p.sha.startswith(baseline[:7])):
            mixed += 1
            gate.fail(f"pointer uses commit {p.sha} but the declared baseline is "
                      f"{short or baseline[:7]}; one baseline per document version",
                      file=p.file, line=p.line, detail={"pointer": p.raw})
            continue

        result = _check_at(git, resolved_baseline, p)
        counts[result.outcome] = counts.get(result.outcome, 0) + 1
        if result.outcome == "resolved" and not result.durable:
            low_durability += 1

        detail = {"pointer": p.raw, "method": result.method}
        if result.line:
            detail["resolved_line"] = result.line
        if result.note:
            detail["note"] = result.note

        if result.outcome == "missing":
            gate.fail(f"unresolved: {result.note}", file=p.file, line=p.line,
                      detail=detail)
        elif result.outcome == "value-changed":
            gate.fail(f"literal mismatch: {result.note}", file=p.file, line=p.line,
                      detail=detail)
        elif not result.durable:
            gate.warn(f"low-durability pointer ({result.method}): "
                      f"{result.note or 'prefer a declaration-bearing ::symbol'}",
                      file=p.file, line=p.line, detail=detail)
        else:
            gate.add(Item("pass", f"resolved via {result.method}", p.file, p.line, detail))

        if at_rev and at_rev != resolved_baseline:
            _record_drift(gate, git, at_rev, p, result, drift)

    total = len(pointers)
    rate = counts["resolved"] / total if total else 1.0
    gate.stats = {
        "total": total,
        "resolved": counts["resolved"],
        "missing": counts["missing"],
        "value_changed": counts["value-changed"],
        "mixed_baseline": mixed,
        "low_durability": low_durability,
        "resolution_rate": round(rate, 4),
        "threshold": min_resolution,
    }

    if rate < min_resolution:
        gate.fail(f"provenance resolution {rate:.0%} is below the {min_resolution:.0%} "
                  f"threshold ({counts['resolved']}/{total})")
    if counts["value-changed"]:
        gate.fail(f"{counts['value-changed']} quoted literal(s) no longer match the "
                  "code; every quoted literal must match (STD-LIMEN-03 G1)")
    if low_durability and strict:
        gate.fail(f"{low_durability} pointer(s) resolved only by line range or bare "
                  "identifier; --strict requires declaration-bearing symbols")

    gate.detail = (f"{rate:.0%} resolution ({counts['resolved']}/{total})"
                   + (f", {counts['value-changed']} value-changed"
                      if counts["value-changed"] else ""))
    return gate, drift


def _record_drift(gate: GateResult, git: Git, at_rev: str, p: Pointer,
                  baseline_result: PointerResult, drift: dict) -> None:
    """Compare the baseline outcome against the same pointer at --at."""
    now = _check_at(git, at_rev, p)
    if baseline_result.outcome != "resolved":
        return  # already reported against the baseline

    if now.outcome == "missing":
        drift["missing"] += 1
        gate.warn(f"DRIFT: no longer resolves at {at_rev[:7]} — {now.note}",
                  file=p.file, line=p.line,
                  detail={"pointer": p.raw, "drift": "missing"})
    elif now.outcome == "value-changed":
        drift["value_changed"] += 1
        gate.warn(f"DRIFT: literal changed at {at_rev[:7]} — {now.note}",
                  file=p.file, line=p.line,
                  detail={"pointer": p.raw, "drift": "value-changed"})
    elif now.line != baseline_result.line:
        drift["moved"] += 1
        gate.warn(f"DRIFT: symbol moved (line {baseline_result.line} → {now.line}) "
                  f"at {at_rev[:7]}; re-pin the baseline",
                  file=p.file, line=p.line,
                  detail={"pointer": p.raw, "drift": "moved",
                          "was_line": baseline_result.line, "now_line": now.line})
    else:
        drift["resolved"] += 1
