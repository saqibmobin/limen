"""decisions — every decision the document cites exists.

Decisions live in ADR files, not in the HLD (LIMEN.md rule 6). This check
confirms each `ADR-nnn` the document references resolves to a file. Whether the
decision weighed real alternatives is the auditor's question, not this one's.
"""
from __future__ import annotations

import re
from pathlib import Path

from ..docset import DocSet
from ..model import CheckResult

ADR_FILE_RE = re.compile(r"ADR-(\d{1,4})")
CANDIDATE_DIRS = ["adr", "../adr", "docs/adr", "../../docs/adr", "../decisions"]


def adr_dir(docs: DocSet) -> Path | None:
    declared = docs.front.get("adr_dir")
    for rel in ([str(declared)] if declared else []) + CANDIDATE_DIRS:
        path = (docs.root / rel).resolve()
        if path.is_dir():
            return path
    return None


def run(docs: DocSet, strict: bool = False) -> CheckResult:
    check = CheckResult("decisions", "Decisions resolve")
    refs = docs.adr_refs()
    directory = adr_dir(docs)

    if not refs:
        check.warn("the document cites no ADRs; shaping decisions belong in ADR "
                   "files that the key-decisions section indexes")
        check.detail = "no ADRs cited"
        return check
    if directory is None:
        check.fail(f"{len({r for r, _, _ in refs})} ADR(s) are cited but no ADR "
                   "directory was found; set `adr_dir` in front matter")
        check.detail = "no ADR directory"
        return check

    files = {f"ADR-{int(m.group(1)):03d}" for p in directory.glob("*.md")
             if (m := ADR_FILE_RE.search(p.name))}
    dangling: set[str] = set()
    for adr, rel, line in refs:
        if adr not in files and adr not in dangling:
            dangling.add(adr)
            check.fail(f"{adr} is cited but there is no such file in {directory.name}/",
                       file=rel, line=line)

    cited = {r for r, _, _ in refs}
    check.stats = {"adr_files": len(files), "cited": len(cited),
                   "dangling": len(dangling)}
    check.detail = f"{len(cited)} cited, {len(files)} on file, {len(dangling)} missing"
    return check
