"""ownership — no agent overwrites what a person wrote.

Each section an agent wrote is recorded in `.limen-lock.yaml` with the hash of
its content. A section whose content no longer matches was changed after the
agent stamped it. Until that change is attributed, an agent cannot tell a
person's edit from its own, so the check fails (LIMEN.md §8.3).
"""
from __future__ import annotations

from ..docset import DocSet
from ..lock import HUMAN, LOCK_NAME, digest
from ..model import CheckResult, Item


def run(docs: DocSet, strict: bool = False) -> CheckResult:
    check = CheckResult("ownership", "Human edits preserved")
    if docs.lock is None:
        check.warn(f"no {LOCK_NAME}: nothing is recorded as agent-written, so a "
                   "person's edit cannot be told from an agent's. After writing a "
                   "new document, run `limen stamp --all`")
        check.detail = "no lock file"
        return check

    sections: dict[str, dict[str, object]] = {}
    for s in docs.sections():
        by_heading = sections.setdefault(s.file, {})
        if s.heading in by_heading:
            check.fail(f"heading '{s.heading}' appears twice in {s.file}; the lock "
                       "cannot tell the two apart. Rename one", file=s.file, line=s.line)
        by_heading[s.heading] = s

    agent = human = changed = 0
    for rel, entries in docs.lock.items():
        if rel not in sections and not any(f.rel == rel for f in docs.files):
            check.warn(f"{LOCK_NAME} names {rel}, which is not in the document set")
            continue
        for heading, value in entries.items():
            if value == HUMAN:
                human += 1
                continue
            agent += 1
            s = sections.get(rel, {}).get(heading)
            if s is None:
                check.warn(f"'{heading}' is recorded as agent-written but no longer "
                           "exists; if you renamed it, stamp the new heading with "
                           "--mine", file=rel)
            elif digest(s) != value:
                changed += 1
                spec = f"{rel}#{heading}"
                check.fail(f"'{heading}' changed after it was stamped. If a person "
                           f"edited it, it is theirs: run `limen stamp --human "
                           f"\"{spec}\"` and do not overwrite it. If you edited it in "
                           f"this run: `limen stamp --mine \"{spec}\"`",
                           file=rel, line=s.line, detail={"recorded": value,
                                                          "actual": digest(s)})
            else:
                check.add(Item("pass", f"'{heading}' unchanged since stamped",
                               rel, s.line))

    recorded = {(f, h) for f, entries in docs.lock.items() for h in entries}
    unrecorded = sum(1 for f, by in sections.items() for h in by
                     if (f, h) not in recorded)
    check.stats = {"agent": agent, "human": human, "changed": changed,
                   "unrecorded": unrecorded}
    check.detail = (f"{agent} agent section(s), {human} a person's, "
                    f"{unrecorded} unrecorded (a person's)"
                    + (f", {changed} changed since stamped" if changed else ""))
    return check
