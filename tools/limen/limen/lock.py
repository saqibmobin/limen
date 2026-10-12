"""Section ownership, recorded in `.limen-lock.yaml` (LIMEN.md §8.3).

The lock maps each file's `##` headings to either the hash of the content an
agent last wrote there, or the word `human`. A section with no entry was
written by a person. A recorded hash that no longer matches means someone
changed the section since an agent last stamped it, and the `ownership` check
fails until the change is attributed: `--mine` if the agent made it in this
run, `--human` if a person did.

Nothing here can tell who edited a file. The protection is the protocol: an
agent checks before it edits, and claims only the sections it wrote.
"""
from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore

from .docset import DocSet, Section
from .model import CheckError

LOCK_NAME = ".limen-lock.yaml"
HUMAN = "human"

HEADER = """\
# Written by `limen stamp`. Commit it; do not edit it by hand, except to delete
# a `human` line when the person who owns that section hands it back.
#
# Each `##` heading maps to the hash of the content an agent last wrote there,
# or to `human`. A section with no entry was written by a person.
"""


def normalize(body: str) -> str:
    """Canonical text hashed for a section: trailing whitespace and surrounding
    blank lines do not count as an edit."""
    lines = [line.rstrip() for line in body.splitlines()]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def digest(section: Section) -> str:
    return "sha256:" + hashlib.sha256(normalize(section.body).encode()).hexdigest()


def read(root: Path) -> dict[str, dict[str, str]] | None:
    path = Path(root) / LOCK_NAME
    if not path.exists():
        return None
    if yaml is None:
        raise CheckError("PyYAML is required to read the lock file")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        raise CheckError(f"invalid YAML in {LOCK_NAME}: {exc}") from exc
    if not isinstance(data, dict) or not all(isinstance(v, dict) for v in data.values()):
        raise CheckError(f"{LOCK_NAME} must map each file to a mapping of headings")
    return {str(f): {str(h): str(v) for h, v in entries.items()}
            for f, entries in data.items()}


def write(root: Path, lock: dict[str, dict[str, str]]) -> None:
    """Write the lock atomically, so an interrupted stamp leaves the old lock
    rather than half of a new one."""
    body = HEADER + "\n" + yaml.safe_dump(
        {f: dict(entries) for f, entries in sorted(lock.items()) if entries},
        sort_keys=False, allow_unicode=True, width=1000)
    fd, tmp = tempfile.mkstemp(dir=root, prefix=".limen-lock.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(body)
        os.replace(tmp, Path(root) / LOCK_NAME)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


# --------------------------------------------------------------------------
# stamp
# --------------------------------------------------------------------------

class StampError(Exception):
    """A stamp that would misattribute a section. Exit code 1."""


def _index(docs: DocSet) -> dict[str, dict[str, Section]]:
    """file -> heading -> section. Duplicate headings in one file are an error,
    because the lock could not tell them apart."""
    out: dict[str, dict[str, Section]] = {}
    for s in docs.sections():
        by_heading = out.setdefault(s.file, {})
        if s.heading in by_heading:
            raise StampError(f"{s.file}: heading '{s.heading}' appears twice; "
                             "rename one so ownership can be recorded")
        by_heading[s.heading] = s
    for f in docs.files:
        out.setdefault(f.rel, {})
    return out


def _find(index: dict[str, dict[str, Section]], spec: str) -> Section:
    """Resolve `Heading` or `file.md#Heading` to one section."""
    if "#" in spec:
        rel, _, heading = spec.partition("#")
        if rel in index:
            if heading in index[rel]:
                return index[rel][heading]
            raise StampError(f"no '## {heading}' in {rel}")
    hits = [s for by in index.values() for h, s in by.items() if h == spec]
    if len(hits) == 1:
        return hits[0]
    if not hits:
        raise StampError(f"no section headed '{spec}'. Use the heading text exactly "
                         "as written, without the '##'")
    where = ", ".join(f"{s.file}#{s.heading}" for s in hits)
    raise StampError(f"'{spec}' names more than one section ({where}); "
                     "use file.md#Heading")


def stamp(docs: DocSet, *, mine: list[str] = (), human: list[str] = (),
          new: bool = False) -> list[str]:
    """Attribute sections and rewrite the lock. Returns the changes made.

    new    record every section of each file that has no lock entries yet as the
           agent's. For a document an agent has just written.
    mine   record these sections as the agent's, at their current content.
    human  record these sections as a person's. Agents stop editing them.
    """
    index = _index(docs)
    lock = {f: dict(e) for f, e in (docs.lock or {}).items()}
    changes: list[str] = []

    for rel in list(lock):
        if rel not in index:
            del lock[rel]
            changes.append(f"dropped {rel}: no longer in the document set")
            continue
        for heading in list(lock[rel]):
            if heading not in index[rel]:
                del lock[rel][heading]
                changes.append(f"dropped {rel}#{heading}: the section is gone")

    if new:
        claimed = 0
        for rel, sections in index.items():
            if lock.get(rel):
                continue
            for heading, s in sections.items():
                lock.setdefault(rel, {})[heading] = digest(s)
                claimed += 1
        if not claimed:
            raise StampError("--all records a new document, but every file already "
                             "has entries in the lock. Name the sections you wrote "
                             "with --mine")
        changes.append(f"recorded {claimed} section(s) as agent-written")

    for spec in human:
        s = _find(index, spec)
        lock.setdefault(s.file, {})[s.heading] = HUMAN
        changes.append(f"{s.file}#{s.heading}: a person's")

    for spec in mine:
        s = _find(index, spec)
        if lock.get(s.file, {}).get(s.heading) == HUMAN:
            raise StampError(f"{s.file}#{s.heading} is recorded as a person's. Only "
                             f"that person can hand it back, by deleting its line "
                             f"from {LOCK_NAME}")
        lock.setdefault(s.file, {})[s.heading] = digest(s)
        changes.append(f"{s.file}#{s.heading}: agent-written")

    write(docs.root, lock)
    docs.lock = lock
    return changes
