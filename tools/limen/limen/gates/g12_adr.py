"""G12 — ADR externality.

STD-LIMEN-01 A-1: the HLD *references* decisions, it does not *contain* them.
HLDs get rewritten; decision records must not be, because their value is the
record of what was true and considered at the time.

Checks:
  - every ADR-nnn referenced resolves to a file with valid MADR front matter
  - every trade-off row (a table with a Rejected/Alternative column) cites an ADR
  - every trade-off row names what it sacrifices — a row with an empty sacrifice
    column describes a preference, not a trade-off (A-2)
  - superseded ADRs are not still cited as current
"""
from __future__ import annotations

import re
from pathlib import Path

from ..docset import DocSet
from ..model import GateResult

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore

FRONT_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.S)
ADR_FILE_RE = re.compile(r"ADR-(\d{1,4})")
STATUSES = {"proposed", "accepted", "rejected", "deprecated", "superseded"}
REQUIRED = ["id", "title", "status", "date"]
CANDIDATE_DIRS = ["../adr", "adr", "../../docs/adr", "docs/adr", "../decisions"]


def _adr_dir(docs: DocSet) -> Path | None:
    declared = docs.front.get("adr_dir")
    candidates = ([str(declared)] if declared else []) + CANDIDATE_DIRS
    for rel in candidates:
        path = (docs.root / rel).resolve()
        if path.is_dir():
            return path
    return None


def _load_adrs(directory: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for path in sorted(directory.glob("*.md")):
        m = ADR_FILE_RE.search(path.name)
        if not m:
            continue
        key = f"ADR-{int(m.group(1)):03d}"
        front: dict = {}
        text = path.read_text(encoding="utf-8", errors="replace")
        fm = FRONT_RE.match(text)
        if fm and yaml is not None:
            try:
                front = yaml.safe_load(fm.group(1)) or {}
            except Exception:
                front = {"_invalid": True}
        out[key] = {"path": path, "front": front, "text": text,
                    "has_front": bool(fm)}
    return out


def run(docs: DocSet, strict: bool = False) -> GateResult:
    gate = GateResult("G12", "ADR externality")
    refs = docs.adr_refs()
    directory = _adr_dir(docs)

    if directory is None:
        if refs:
            gate.fail(f"{len({r for r, _, _ in refs})} ADR(s) are referenced but no "
                      "ADR directory was found; set `adr_dir` in front matter. "
                      "Decisions live outside the HLD (Rule A-1)")
        else:
            gate.fail("no ADR directory and no ADR references. Every shaping "
                      "decision at L1.10 needs an ADR (Rule A-1)")
        gate.detail = "no ADR directory"
        return gate

    adrs = _load_adrs(directory)
    dangling = _check_refs(gate, refs, adrs)
    invalid = _check_files(gate, adrs)
    rows, uncited, unsacrificed = _check_tradeoff_tables(gate, docs, adrs, strict)

    if not adrs:
        gate.fail(f"ADR directory {directory} contains no ADR files")

    gate.stats = {"adr_files": len(adrs), "referenced": len({r for r, _, _ in refs}),
                  "dangling": dangling, "invalid_front_matter": invalid,
                  "tradeoff_rows": rows, "rows_without_adr": uncited,
                  "rows_without_sacrifice": unsacrificed}
    gate.detail = (f"{len(adrs)} ADR file(s), {dangling} dangling reference(s), "
                   f"{uncited} trade-off row(s) with no ADR")
    return gate


def _check_refs(gate: GateResult, refs, adrs: dict) -> int:
    dangling = 0
    seen: set[str] = set()
    for adr_id, f, line in refs:
        if adr_id in adrs or adr_id in seen:
            continue
        seen.add(adr_id)
        dangling += 1
        gate.fail(f"{adr_id} is referenced but no such ADR file exists",
                  file=f, line=line, detail={"adr": adr_id})
    return dangling


def _check_files(gate: GateResult, adrs: dict) -> int:
    invalid = 0
    for adr_id, info in adrs.items():
        rel = info["path"].name
        if not info["has_front"]:
            invalid += 1
            gate.fail(f"{adr_id} has no YAML front matter; MADR format is required "
                      "(STD-LIMEN-02 §8)", file=rel)
            continue
        front = info["front"]
        if front.get("_invalid"):
            invalid += 1
            gate.fail(f"{adr_id} front matter is not valid YAML", file=rel)
            continue

        for key in REQUIRED:
            if not front.get(key):
                invalid += 1
                gate.fail(f"{adr_id} front matter is missing `{key}`", file=rel)

        status = str(front.get("status", "")).lower()
        if status and status not in STATUSES:
            gate.fail(f"{adr_id} status '{status}' is not one of {sorted(STATUSES)}",
                      file=rel)
        if status == "superseded" and not front.get("superseded_by"):
            gate.fail(f"{adr_id} is superseded but does not say by which ADR", file=rel)

        body = info["text"].lower()
        if "considered options" not in body and "options" not in body:
            gate.warn(f"{adr_id} has no considered-options section; the alternatives "
                      "are the reason ADRs are worth writing", file=rel)
        if not front.get("optimizes_for") and not front.get("sacrifices"):
            gate.warn(f"{adr_id} declares neither `optimizes_for` nor `sacrifices`; "
                      "a decision that trades nothing was not a decision (A-2)",
                      file=rel)
    return invalid


def _check_tradeoff_tables(gate: GateResult, docs: DocSet, adrs: dict,
                           strict: bool) -> tuple[int, int, int]:
    rows = uncited = unsacrificed = 0
    for t in docs.tables():
        rejected = t.column("rejected", "alternative", "alternatives")
        if rejected is None:
            continue
        adr_col = t.column("adr", "decision record")
        sacrifice_col = t.column("sacrifices", "sacrificed", "trade-off", "tradeoff")

        if adr_col is None:
            gate.fail("trade-off table has no ADR column; the HLD indexes decisions, "
                      "it does not contain them (Rule A-1)",
                      file=t.file, line=t.line, detail={"headers": t.headers})
            continue

        for line, cells in t.rows:
            rows += 1
            cell = cells[adr_col] if adr_col < len(cells) else ""
            found = re.findall(r"\bADR-(\d{1,4})\b", cell)
            if not found:
                uncited += 1
                gate.fail("trade-off row cites no ADR; the rationale exists only "
                          "inside the HLD body and will be lost on the next rewrite",
                          file=t.file, line=line)
            for num in found:
                adr_id = f"ADR-{int(num):03d}"
                info = adrs.get(adr_id)
                if info and str(info["front"].get("status", "")).lower() == "superseded":
                    gate.fail(f"trade-off row cites {adr_id}, which is superseded by "
                              f"{info['front'].get('superseded_by', 'another ADR')}",
                              file=t.file, line=line)

            if sacrifice_col is None:
                continue
            sac = cells[sacrifice_col].strip() if sacrifice_col < len(cells) else ""
            if not sac or sac in ("—", "-", "none", "n/a"):
                unsacrificed += 1
                report = gate.fail if strict else gate.warn
                report("trade-off row names nothing it sacrifices; that is a "
                       "preference, not a trade-off (A-2)", file=t.file, line=line)

        if sacrifice_col is None:
            report = gate.fail if strict else gate.warn
            report("trade-off table has no Sacrifices column; every decision names "
                   "what it gives up in QA-nn terms (A-2)",
                   file=t.file, line=t.line, detail={"headers": t.headers})
    return rows, uncited, unsacrificed
