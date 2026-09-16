#!/usr/bin/env python3
"""`limen xrefs` — cross-reference checker for the STD-LIMEN standards.

The standards cite each other constantly (`-03` §9, §3.7.2, Rule U-2). Those
citations rot silently when sections are renumbered, and a wrong pointer in a
standard about grounding claims is a bad look. This validates every internal
section and rule reference against the headings and rule definitions that
actually exist.

Usage:  limen xrefs [--dir .]
Exit:   0 clean, 1 broken references found
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

DOCS = {
    "-01": "STD-LIMEN-01-Framework.md",
    "-02": "STD-LIMEN-02-Templates.md",
    "-03": "STD-LIMEN-03-Audit.md",
}

# A `§` preceded by one of these belongs to an external document.
EXTERNAL = re.compile(r"(?:arc42|DPA|ISO|IEEE|RFC|SEI|AWS|MADR)\s*$", re.I)
SECTION_REF = re.compile(r"(`?-0[123]`?\s*)?§\s*([0-9]+(?:\.[0-9]+){0,3})")
RULE_REF = re.compile(r"(?:Rule\s+|\(|see\s+|per\s+)([A-Z]{1,2}-\d+)\b")
# Register ids (C-01, QA-03) are zero-padded; rule ids (A-1, T-3) are not.
REGISTER_PREFIXES = {"C", "K", "Q", "R", "I", "FF", "QA", "SLO", "SLI", "TB",
                     "ADR", "TD", "P", "A"}


def headings(text: str) -> set[str]:
    """Every section number a `§` may legitimately point at."""
    out: set[str] = set()
    for m in re.finditer(r"^#{2,4}\s+([0-9]+(?:\.[0-9]+){0,2})[.\s]", text, re.M):
        parts = m.group(1).split(".")
        for i in range(1, len(parts) + 1):
            out.add(".".join(parts[:i]))
    return out


def rule_ids(text: str) -> set[str]:
    """Rule and corollary definitions, in every form the standards use."""
    out = set(re.findall(r"\*\*(?:Rule|Corollary)\s+([A-Z]{1,2}-\d+)", text))
    # `- **D-1.** ...` and `- **V-14.** ...` keep the period inside the bold.
    out |= set(re.findall(r"^\s*(?:[-*]\s+)?\*\*([A-Z]{1,2}-\d+)\.?\*\*", text, re.M))
    return out


def run(directory: Path) -> int:
    """Validate every internal section and rule citation. Returns an exit code."""
    texts, missing_files = {}, []
    for key, name in DOCS.items():
        path = Path(directory) / name
        if path.exists():
            texts[key] = path.read_text(encoding="utf-8")
        else:
            missing_files.append(name)
    if missing_files:
        print(f"limen xrefs: not found: {', '.join(missing_files)}", file=sys.stderr)
        return 1

    anchors = {k: headings(t) for k, t in texts.items()}
    rules: set[str] = set()
    for t in texts.values():
        rules |= rule_ids(t)

    problems: list[tuple[str, int, str, str]] = []
    for key, text in texts.items():
        lines = text.splitlines()
        for n, line in enumerate(lines, 1):
            for m in SECTION_REF.finditer(line):
                if EXTERNAL.search(line[:m.start()]):
                    continue
                prefix, ref = m.group(1), m.group(2)
                target = re.sub(r"[`\s]", "", prefix) if prefix else key
                if target in anchors and ref not in anchors[target]:
                    problems.append((DOCS[key], n,
                                     f"§{ref} does not exist in {DOCS[target]}",
                                     line.strip()[:100]))
        for m in RULE_REF.finditer(text):
            rid = m.group(1)
            head, num = rid.split("-")
            if rid in rules or (head in REGISTER_PREFIXES and len(num) >= 2):
                continue
            n = text.count("\n", 0, m.start()) + 1
            problems.append((DOCS[key], n, f"rule {rid} is never defined",
                             lines[n - 1].strip()[:100]))

    unique = sorted(set(problems))
    for f, n, what, ctx in unique:
        print(f"{f}:{n}\n    {what}\n    {ctx}\n")
    total = sum(len(a) for a in anchors.values())
    print(f"{len(unique)} broken reference(s) across {len(texts)} documents "
          f"({total} section anchors, {len(rules)} rules)")
    return 1 if unique else 0
