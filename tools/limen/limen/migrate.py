"""Convert a 5.x document set to the 6.0 form (LIMEN.md §13).

`limen migrate` rewrites the files on disk. `limen check --legacy` applies the
same conversion in memory, so a 5.x document can be checked before anyone
touches it.

What changes:

  tags          `[T0]`..`[T3]` become `[unknown]`, `[verified]`, `[inferred]`,
                `[proposed]`
  mode          brownfield-asis and brownfield-change become brownfield
  baseline      `repo.commit` becomes `baseline`; the rest of `repo` is dropped
  front matter  counts, level, profile, ungated and registers are dropped
  markup        `frames:` and `c4:` comments are removed
  ownership     `agent:`/`human:` markers are removed, and who wrote each `##`
                section moves to `.limen-lock.yaml`

What does not: `[AS-IS]`/`[TO-BE]` markers, YAML registers, ADRs, the prose.

A 5.x agent block whose hash no longer matched was edited by a person, so its
sections are recorded as theirs, which is what 5.x told the agent to do.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore

from . import lock as lockmod
from .docset import (FRONT_RE, LEGACY_TAGS, SIDECAR, DocSet, MdFile,
                     fenced_indices, file_sections)

MARKER_RE = re.compile(
    r"<!--\s*(?P<owner>agent|human):(?P<pos>begin|end)\s+(?P<attrs>[^>]*?)-->")
ATTR_RE = re.compile(r'(\w+)\s*=\s*"([^"]*)"')
MARKER_LINE_RE = re.compile(r"^\s*<!--\s*(?:agent|human):(?:begin|end)\b[^>]*-->\s*$")
RETIRED_LINE_RE = re.compile(r"^\s*<!--\s*(?:frames|c4)\s*:[^>]*-->\s*$")
LEGACY_SPAN_RE = re.compile(r"`\s*\[(T[0-3])\]\s*`")
LEGACY_TOKEN_RE = re.compile(r"\[T[0-3]\]")

OLD_MODES = {"brownfield-asis": "brownfield", "brownfield-change": "brownfield"}
DROPPED_KEYS = ("counts", "level", "profile", "profile_override", "ungated",
                "registers")
# Recorded for a 5.x block that a person changed, so `ownership` reports it
# under --legacy instead of passing it.
CHANGED = "sha256:changed-since-the-5.x-stamp"


# --------------------------------------------------------------------------
# 5.x ownership blocks
# --------------------------------------------------------------------------

@dataclass
class _Block:
    owner: str
    start: int          # 0-based line index of the begin marker
    end: int            # 0-based line index of the end marker
    intact: bool


def _blocks(f: MdFile) -> list[_Block]:
    fenced = fenced_indices(f.lines)
    out: list[_Block] = []
    open_: list[tuple[re.Match, int]] = []
    for m in MARKER_RE.finditer(f.text):
        line = f.line_of(m.start()) - 1
        if line in fenced:
            continue
        if m.group("pos") == "begin":
            open_.append((m, line))
        elif open_:
            begin, bline = open_.pop()
            content = f.text[begin.end():m.start()]
            if content.startswith("\n"):
                content = content[1:]
            if content.endswith("\n"):
                content = content[:-1]
            declared = dict(ATTR_RE.findall(begin.group("attrs"))).get("hash")
            actual = "sha256:" + hashlib.sha256(content.encode()).hexdigest()
            out.append(_Block(begin.group("owner"), bline, line,
                              begin.group("owner") == "agent" and declared == actual))
    return out


def _ownership(f: MdFile) -> dict[str, str]:
    """heading -> agent | human | changed, for sections a 5.x block covers.
    A section partly outside any block was not wholly an agent's: no entry."""
    blocks = _blocks(f)
    if not blocks:
        return {}
    out: dict[str, str] = {}
    for s in file_sections(f):
        kinds: set[str] = set()
        for i in range(s.line, s.end):          # content lines, after the heading
            text = f.lines[i]
            if not text.strip() or MARKER_LINE_RE.match(text):
                continue
            inner = [b for b in blocks if b.start < i < b.end]
            if not inner:
                kinds.add("none")
                continue
            b = max(inner, key=lambda b: b.start)
            kinds.add("human" if b.owner == "human"
                      else "agent" if b.intact else "changed")
        if "changed" in kinds:
            out[s.heading] = "changed"
        elif kinds == {"agent"}:
            out[s.heading] = "agent"
        elif "human" in kinds:
            out[s.heading] = "human"
    return out


# --------------------------------------------------------------------------
# Text and front matter
# --------------------------------------------------------------------------

def convert_text(text: str) -> tuple[str, int]:
    """Rewrite tags and drop retired markup. Returns (text, stray 5.x tokens)."""
    lines = text.splitlines()
    fenced = fenced_indices(lines)
    out: list[str] = []
    stray = 0
    i = 0
    while i < len(lines):
        line = lines[i]
        if i in fenced:
            out.append(line)
            i += 1
            continue
        if MARKER_LINE_RE.match(line) or RETIRED_LINE_RE.match(line):
            # Drop the line, and the blank after it if one already precedes it.
            if (out and not out[-1].strip() and i + 1 < len(lines)
                    and not lines[i + 1].strip()):
                i += 1
            i += 1
            continue
        line = MARKER_RE.sub("", line)
        line = LEGACY_SPAN_RE.sub(lambda m: f"`[{LEGACY_TAGS[m.group(1)]}]`", line)
        stray += len(LEGACY_TOKEN_RE.findall(line))
        out.append(line)
        i += 1
    return "\n".join(out) + ("\n" if text.endswith("\n") else ""), stray


def convert_front(front: dict) -> tuple[dict, list[str]]:
    notes: list[str] = []
    out: dict = {}
    repo = front.get("repo") if isinstance(front.get("repo"), dict) else None
    for key, value in front.items():
        if key in DROPPED_KEYS:
            notes.append(f"front matter: dropped `{key}`")
            continue
        if key == "mode":
            out["mode"] = OLD_MODES.get(str(value), value)
            if value == "brownfield-change":
                notes.append("mode brownfield-change is now brownfield: move the "
                             "to-be design into a 'Proposed change' section. "
                             "[AS-IS]/[TO-BE] markers were left in place")
            if repo and repo.get("commit") and "baseline" not in front:
                out["baseline"] = str(repo["commit"])
            continue
        if key == "repo" and repo is not None:
            if "mode" not in front and repo.get("commit") and "baseline" not in front:
                out["baseline"] = str(repo["commit"])
            kept = {k: v for k, v in repo.items() if k not in ("commit", "short")}
            if kept:
                notes.append(f"front matter: dropped `repo` fields {kept}; state "
                             "anything still true, such as sampling, in the document")
            continue
        out[key] = value
    return out, notes


def _dump_front(front: dict) -> str:
    return yaml.safe_dump(front, sort_keys=False, allow_unicode=True,
                          default_flow_style=False, width=1000)


# --------------------------------------------------------------------------
# Entry points
# --------------------------------------------------------------------------

def _convert(docs: DocSet) -> tuple[dict[str, str], dict[str, dict[str, str]], dict,
                                    list[str]]:
    """Returns (new text per file, ownership per file, new front, notes)."""
    texts: dict[str, str] = {}
    owners: dict[str, dict[str, str]] = {}
    notes: list[str] = []
    for f in docs.files:
        owners[f.rel] = _ownership(f)
        text, stray = convert_text(f.text)
        if stray:
            notes.append(f"{f.rel}: {stray} `[Tn]` token(s) outside a code span left "
                         "as they are; fix them by hand")
        texts[f.rel] = text
    front, front_notes = convert_front(docs.front)
    return texts, owners, front, notes + front_notes


def _lock_entries(f: MdFile, owners: dict[str, str], changed_value: str,
                  notes: list[str]) -> dict[str, str]:
    entries: dict[str, str] = {}
    seen: set[str] = set()
    for s in file_sections(f):
        if s.heading in seen:
            entries.pop(s.heading, None)
            notes.append(f"{f.rel}: heading '{s.heading}' appears twice; neither is "
                         "recorded until one is renamed")
            continue
        seen.add(s.heading)
        kind = owners.get(s.heading)
        if kind == "agent":
            entries[s.heading] = lockmod.digest(s)
        elif kind == "human":
            entries[s.heading] = lockmod.HUMAN
        elif kind == "changed":
            entries[s.heading] = changed_value
            if changed_value == lockmod.HUMAN:
                notes.append(f"{f.rel}#{s.heading}: a person edited this agent block "
                             "after it was stamped; recorded as theirs")
    return entries


def legacy_view(docs: DocSet) -> list[str]:
    """Read a 5.x document as 6.0, in memory only."""
    texts, owners, front, notes = _convert(docs)
    lock = None if docs.lock is not None else {}
    for f in docs.files:
        f.replace_text(texts[f.rel])
        if lock is not None:
            if entries := _lock_entries(f, owners[f.rel], CHANGED, notes):
                lock[f.rel] = entries
    docs.front = front
    if lock:
        docs.lock = lock
    docs.legacy = True
    return notes


def migrate(docs: DocSet, write: bool = True) -> list[str]:
    """Convert a 5.x document set on disk. Returns what was changed."""
    if yaml is None:
        raise RuntimeError("PyYAML is required to migrate front matter")
    texts, owners, front, notes = _convert(docs)
    changes: list[str] = []
    lock = {k: dict(v) for k, v in (docs.lock or {}).items()}

    for f in docs.files:
        text = texts[f.rel]
        if docs.front_source == f.rel and (m := FRONT_RE.match(text)):
            text = "---\n" + _dump_front(front) + "---\n" + text[m.end():]
        if text != f.text:
            changes.append(f"rewrote {f.rel}")
            if write:
                Path(f.path).write_text(text, encoding="utf-8")
        f.replace_text(text)
        if not lock.get(f.rel):
            if entries := _lock_entries(f, owners[f.rel], lockmod.HUMAN, notes):
                lock[f.rel] = entries

    if docs.front_source == SIDECAR:
        changes.append(f"rewrote {SIDECAR}")
        if write:
            (docs.root / SIDECAR).write_text(_dump_front(front), encoding="utf-8")

    if lock != (docs.lock or {}):
        agent = sum(1 for e in lock.values() for v in e.values() if v != lockmod.HUMAN)
        human = sum(1 for e in lock.values() for v in e.values() if v == lockmod.HUMAN)
        changes.append(f"wrote {lockmod.LOCK_NAME}: {agent} agent section(s), "
                       f"{human} a person's")
        if write:
            lockmod.write(docs.root, lock)
    docs.front = front
    docs.lock = lock or docs.lock
    return changes + notes
