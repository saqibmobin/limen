#!/usr/bin/env python3
"""`limen xrefs` — cross-reference checker for the Limen standard.

LIMEN.md, its reference and the README cite each other by section (`§5.2`,
`LIMEN-reference.md §7`) and by rule number (`rule 5`). Those citations rot
silently when sections are renumbered, and a wrong pointer in a standard about
grounding claims is a bad look.

A bare `§n` points into the document it appears in; `LIMEN.md §n` and
`LIMEN-reference.md §n` point into those documents from anywhere.

Usage:  limen xrefs [--dir .]
Exit:   0 clean, 1 broken references found
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

CORE = "LIMEN.md"
REFERENCE = "LIMEN-reference.md"
TARGETS = (CORE, REFERENCE)
# Documents that cite the standard but are not cited by section themselves.
CITERS = ("README.md",)

SECTION_REF = re.compile(
    r"(?:`?(?P<doc>LIMEN(?:-reference)?\.md)`?\s*)?§\s*(?P<ref>\d+(?:\.\d+){0,2})")
RULE_REF = re.compile(r"\brules?\s+(\d+)\b", re.I)
RULE_DEF = re.compile(r"^(\d+)\.\s+\*\*")
FENCE = re.compile(r"^\s*(```|~~~)")


def headings(text: str) -> set[str]:
    """Every section number a `§` may point at."""
    out: set[str] = set()
    for m in re.finditer(r"^#{2,4}\s+(\d+(?:\.\d+){0,2})[.\s]", text, re.M):
        parts = m.group(1).split(".")
        for i in range(1, len(parts) + 1):
            out.add(".".join(parts[:i]))
    return out


def rule_count(core: str) -> int:
    """Rules are the numbered bold items in the core's rules section."""
    m = re.search(r"^## \d+\.\s+The (?:ten )?rules\s*$(.*?)(?=^## )", core, re.M | re.S)
    if not m:
        return 0
    return max((int(r.group(1)) for line in m.group(1).splitlines()
                if (r := RULE_DEF.match(line))), default=0)


def run(directory: Path) -> int:
    directory = Path(directory)
    texts: dict[str, str] = {}
    for name in TARGETS + CITERS:
        path = directory / name
        if path.exists():
            texts[name] = path.read_text(encoding="utf-8")
    missing = [n for n in TARGETS if n not in texts]
    if missing:
        print(f"limen xrefs: not found: {', '.join(missing)}", file=sys.stderr)
        return 1

    anchors = {n: headings(texts[n]) for n in TARGETS}
    rules = rule_count(texts[CORE])
    problems: list[tuple[str, int, str, str]] = []

    for name, text in texts.items():
        in_fence = False
        for n, line in enumerate(text.splitlines(), 1):
            if FENCE.match(line):
                in_fence = not in_fence
            if in_fence:
                continue
            for m in SECTION_REF.finditer(line):
                target = m.group("doc") or (name if name in TARGETS else None)
                if target and m.group("ref") not in anchors[target]:
                    problems.append((name, n, f"§{m.group('ref')} does not exist "
                                              f"in {target}", line.strip()[:100]))
            for m in RULE_REF.finditer(line):
                if not 1 <= int(m.group(1)) <= rules:
                    problems.append((name, n, f"rule {m.group(1)} does not exist "
                                              f"({CORE} defines {rules})",
                                     line.strip()[:100]))

    for f, n, what, ctx in sorted(set(problems)):
        print(f"{f}:{n}\n    {what}\n    {ctx}\n")
    total = sum(len(a) for a in anchors.values())
    print(f"{len(set(problems))} broken reference(s) across {len(texts)} documents "
          f"({total} section anchors, {rules} rules)")
    return 1 if problems else 0
