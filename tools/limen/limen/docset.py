"""Discovery and parsing of an HLD document set.

A document set is one markdown file or a directory of them. Front matter sits at
the top of the first file that has any, or in a `00-front-matter.yaml` sidecar.
Registers are tables in the documents, or YAML files beside them when a tool
outside the document reads them (LIMEN.md §5.3).
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore

from .model import CheckError

# `path@sha::symbol`, `path@sha#L10-L45`, `path/@sha`, with an optional
# ` = <literal>` assertion immediately after the closing backtick.
POINTER_RE = re.compile(
    r"`(?P<path>[^`\s@]+)@(?P<sha>[0-9a-fA-F]{7,40})"
    r"(?:::(?P<symbol>[^`#]+?))?"
    r"(?:#L(?P<l1>\d+)(?:-L(?P<l2>\d+))?)?`"
    r"(?P<tail>\s*={1,2}\s*[^\n,)|`]+)?"
)
POINTER_BARE_RE = re.compile(r"[^\s`]+@[0-9a-fA-F]{7,40}(?:::[^\s`]+)?")

# Pointer forms that cannot be re-checked by anyone else (LIMEN.md §3.2).
LEGACY_POINTER_RE = re.compile(r"`?(?P<uri>file://[^\s`)]+)`?")
ABSOLUTE_POINTER_RE = re.compile(r"`(?P<path>/[^`\s@]+)@[0-9a-fA-F]{7,40}")

FENCE_RE = re.compile(r"^(?P<indent>\s*)(?P<ticks>`{3,}|~{3,})\s*(?P<lang>[\w+-]*)\s*$")
HEADING_RE = re.compile(r"^(?P<level>#{1,6})\s+(?P<title>.+?)\s*$")
BULLET_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+\S")
TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$")
TABLE_SEP_RE = re.compile(r"^\s*\|[\s:|-]+\|\s*$")
ADR_REF_RE = re.compile(r"\bADR-(\d{1,4})\b")
QID_RE = re.compile(r"\bQ-\d+\b")

# --------------------------------------------------------------------------
# Tier tags
# --------------------------------------------------------------------------

TAGS = ("unknown", "verified", "inferred", "proposed")
# The 5.x tags, read under --legacy and rewritten by `limen migrate`.
LEGACY_TAGS = {"T0": "unknown", "T1": "verified", "T2": "inferred", "T3": "proposed"}

# A tag token. Not one followed by `(` or `[`, which is markdown link text.
TAG_TOKEN_RE = re.compile(r"\[(unknown|verified|inferred|proposed|T[0-3])\](?![(\[])")
# A tag is a code span holding exactly the bracketed word. The token anywhere
# else, bare in prose or inside a longer span, is either a mention that should
# name the tier in plain words, or a tag whose backticks are misplaced.
CODE_SPAN_RE = re.compile(r"(?<!`)(`+)(?!`)(.+?)(?<!`)\1(?!`)")
EXACT_TAG_RE = re.compile(r"\s*\[(unknown|verified|inferred|proposed)\]\s*")


def tags(text: str) -> list[str]:
    """The well-formed tags in text, as tier names."""
    return [m.group(1) for s in CODE_SPAN_RE.finditer(text)
            if (m := EXACT_TAG_RE.fullmatch(s.group(2)))]


def stray_tags(text: str) -> list[str]:
    """Tag tokens that are not well-formed tags, including 5.x `[Tn]` tokens."""
    stray: list[str] = []
    last = 0
    for s in CODE_SPAN_RE.finditer(text):
        stray += TAG_TOKEN_RE.findall(text[last:s.start()])
        if not EXACT_TAG_RE.fullmatch(s.group(2)):
            stray += TAG_TOKEN_RE.findall(s.group(2))
        last = s.end()
    return stray + TAG_TOKEN_RE.findall(text[last:])


# --------------------------------------------------------------------------
# Data types
# --------------------------------------------------------------------------

@dataclass
class MdFile:
    path: Path
    rel: str
    text: str
    _lines: list[str] | None = None
    _fenced: set[int] | None = None

    @property
    def lines(self) -> list[str]:
        if self._lines is None:
            self._lines = self.text.splitlines()
        return self._lines

    def replace_text(self, text: str) -> None:
        self.text = text
        self._lines = None
        self._fenced = None

    @property
    def body_start(self) -> int:
        """0-based index of the first line after YAML front matter."""
        lines = self.lines
        if not lines or lines[0].strip() != "---":
            return 0
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                return i + 1
        return 0

    def fenced(self, index: int) -> bool:
        """True if line `index` (0-based) sits inside a fenced code block."""
        if self._fenced is None:
            self._fenced = fenced_indices(self.lines)
        return index in self._fenced

    def line_of(self, offset: int) -> int:
        return self.text.count("\n", 0, offset) + 1


@dataclass
class Pointer:
    raw: str
    path: str
    sha: str
    symbol: str | None
    line_start: int | None
    line_end: int | None
    literal: str | None
    file: str
    line: int


@dataclass
class Diagram:
    file: str
    line: int          # line of the opening fence
    lang: str
    source: str

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.source.encode()).hexdigest()


@dataclass
class Unit:
    """A reviewable chunk of prose: one bullet, paragraph, or table row."""

    kind: str                     # bullet | paragraph | table-row
    text: str
    file: str
    line: int
    heading: str | None = None

    @property
    def tags(self) -> list[str]:
        return tags(self.text)

    @property
    def stray_tags(self) -> list[str]:
        return stray_tags(self.text)

    @property
    def has_pointer(self) -> bool:
        return bool(POINTER_BARE_RE.search(self.text))


@dataclass
class Section:
    """A `##` heading and everything up to the next `#` or `##` heading."""

    file: str
    heading: str
    line: int          # 1-based line of the heading
    body: str
    end: int = 0       # 0-based index of the first line after the section


@dataclass
class DocSet:
    root: Path
    files: list[MdFile]
    front: dict[str, Any]
    front_source: str | None
    lock: dict[str, dict[str, str]] | None = None
    legacy: bool = False
    _data: list[tuple[str, Any]] | None = field(default=None, repr=False)

    @property
    def mode(self) -> str:
        return str(self.front.get("mode") or "")

    @property
    def baseline(self) -> str:
        return str(self.front.get("baseline") or "").strip().lower()

    # -- extraction ------------------------------------------------------

    def pointers(self) -> list[Pointer]:
        found: list[Pointer] = []
        for f in self.files:
            for m in POINTER_RE.finditer(f.text):
                if f.fenced(f.line_of(m.start()) - 1):
                    continue
                literal = None
                if tail := m.group("tail"):
                    literal = tail.lstrip().lstrip("=").strip().rstrip(".") or None
                found.append(Pointer(
                    raw=m.group(0).strip(),
                    path=m.group("path"),
                    sha=m.group("sha").lower(),
                    symbol=(m.group("symbol") or "").strip() or None,
                    line_start=int(m.group("l1")) if m.group("l1") else None,
                    line_end=int(m.group("l2")) if m.group("l2") else None,
                    literal=literal,
                    file=f.rel,
                    line=f.line_of(m.start()),
                ))
        return found

    def legacy_pointers(self) -> list[tuple[str, int, str]]:
        """`file://` and absolute-path pointers, which nobody else can resolve."""
        out = []
        for f in self.files:
            for rx, label in ((LEGACY_POINTER_RE, "file:// URI"),
                              (ABSOLUTE_POINTER_RE, "absolute path")):
                for m in rx.finditer(f.text):
                    if not f.fenced(f.line_of(m.start()) - 1):
                        out.append((f.rel, f.line_of(m.start()), f"{label}: {m.group(0)}"))
        return out

    def diagrams(self, langs=("mermaid",)) -> list[Diagram]:
        out: list[Diagram] = []
        for f in self.files:
            out.extend(_extract_fences(f, langs))
        for path in sorted(self.root.rglob("*.mmd")):
            out.append(Diagram(file=str(path.relative_to(self.root)), line=1,
                               lang="mermaid", source=path.read_text(encoding="utf-8")))
        return out

    def sections(self) -> list[Section]:
        out: list[Section] = []
        for f in self.files:
            out.extend(file_sections(f))
        return out

    def units(self) -> list[Unit]:
        out: list[Unit] = []
        for f in self.files:
            out.extend(_units(f))
        return out

    def adr_refs(self) -> list[tuple[str, str, int]]:
        """(ADR id, file, line) for every ADR reference outside code fences."""
        out: list[tuple[str, str, int]] = []
        for f in self.files:
            for n, line in enumerate(f.lines, 1):
                if f.fenced(n - 1):
                    continue
                for m in ADR_REF_RE.finditer(line):
                    out.append((f"ADR-{int(m.group(1)):03d}", f.rel, n))
        return out

    def question_refs(self) -> list[tuple[str, str, int]]:
        """(Q id, file, line) for every open-question reference outside fences."""
        out: list[tuple[str, str, int]] = []
        for f in self.files:
            for n, line in enumerate(f.lines, 1):
                if not f.fenced(n - 1):
                    out.extend((m.group(0), f.rel, n) for m in QID_RE.finditer(line))
        return out

    def question_ids(self) -> dict[str, tuple[str, int]]:
        """Open questions the document defines: a table row whose first cell is
        a `Q-nn` id, or an entry with `id: Q-nn` in a YAML register."""
        out: dict[str, tuple[str, int]] = {}
        for u in self.units():
            if u.kind != "table-row":
                continue
            first = _cells(u.text)[0] if _cells(u.text) else ""
            qid = first.strip("`* ")
            if re.fullmatch(r"Q-\d+", qid):
                out.setdefault(qid, (u.file, u.line))
        for rel, data in self.data_files():
            if not isinstance(data, list):
                continue
            for entry in data:
                if isinstance(entry, dict) and re.fullmatch(r"Q-\d+", str(entry.get("id", ""))):
                    out.setdefault(str(entry["id"]), (rel, 0))
        return out

    def data_files(self) -> list[tuple[str, Any]]:
        """Parsed YAML files in the document set, other than front matter and
        limen's own files."""
        if self._data is None:
            self._data = []
            for path in sorted(self.root.rglob("*.y*ml")):
                rel = path.relative_to(self.root)
                if (SKIP_DIRS & set(rel.parts) or path.name in OWN_FILES):
                    continue
                self._data.append((str(rel), _yaml_load(path.read_text(encoding="utf-8"),
                                                        str(rel))))
        return self._data


# --------------------------------------------------------------------------
# Extraction helpers
# --------------------------------------------------------------------------

def fenced_indices(lines: list[str]) -> set[int]:
    """0-based indices of every line inside (or delimiting) a fenced block."""
    out: set[int] = set()
    i = 0
    while i < len(lines):
        m = FENCE_RE.match(lines[i])
        if not m:
            i += 1
            continue
        ticks, indent = m.group("ticks"), m.group("indent")
        close = re.compile(rf"^{re.escape(indent)}{ticks[0]}{{{len(ticks)},}}\s*$")
        out.add(i)
        i += 1
        while i < len(lines) and not close.match(lines[i]):
            out.add(i)
            i += 1
        if i < len(lines):
            out.add(i)
            i += 1
    return out


def file_sections(f: MdFile) -> list[Section]:
    """`##` sections of one file. Content before the first `##` is not a
    section; a `#` heading ends the section before it."""
    lines = f.lines
    heads: list[tuple[int, int, str]] = []        # (index, level, title)
    for i in range(f.body_start, len(lines)):
        if f.fenced(i):
            continue
        if m := HEADING_RE.match(lines[i]):
            heads.append((i, len(m.group("level")), m.group("title")))
    out: list[Section] = []
    for n, (i, level, title) in enumerate(heads):
        if level != 2:
            continue
        end = len(lines)
        for j, lvl, _ in heads[n + 1:]:
            if lvl <= 2:
                end = j
                break
        out.append(Section(f.rel, title, i + 1, "\n".join(lines[i + 1:end]), end))
    return out


def _cells(row: str) -> list[str]:
    parts = row.strip().split("|")
    if parts and not parts[0].strip():
        parts = parts[1:]
    if parts and not parts[-1].strip():
        parts = parts[:-1]
    return [p.strip() for p in parts]


def _units(f: MdFile) -> list[Unit]:
    out: list[Unit] = []
    lines = f.lines
    heading: str | None = None
    i = f.body_start
    while i < len(lines):
        if f.fenced(i):
            i += 1
            continue
        raw = lines[i]
        stripped = raw.strip()

        if m := HEADING_RE.match(raw):
            heading = m.group("title")
            i += 1
            continue
        if not stripped or stripped.startswith("<!--"):
            i += 1
            continue
        if TABLE_ROW_RE.match(raw):
            if not TABLE_SEP_RE.match(raw):
                out.append(Unit("table-row", stripped, f.rel, i + 1, heading))
            i += 1
            continue
        if BULLET_RE.match(raw):
            start, buf = i, [stripped]
            i += 1
            while (i < len(lines) and lines[i].strip()
                   and not BULLET_RE.match(lines[i])
                   and not HEADING_RE.match(lines[i])
                   and not TABLE_ROW_RE.match(lines[i])
                   and not f.fenced(i)
                   and lines[i].startswith((" ", "\t"))):
                buf.append(lines[i].strip())
                i += 1
            out.append(Unit("bullet", " ".join(buf), f.rel, start + 1, heading))
            continue

        start, buf = i, []
        while (i < len(lines) and lines[i].strip()
               and not BULLET_RE.match(lines[i])
               and not HEADING_RE.match(lines[i])
               and not TABLE_ROW_RE.match(lines[i])
               and not lines[i].strip().startswith("<!--")
               and not f.fenced(i)):
            buf.append(lines[i].strip())
            i += 1
        if buf:
            out.append(Unit("paragraph", " ".join(buf), f.rel, start + 1, heading))
        else:
            i += 1
    return out


def _extract_fences(f: MdFile, langs: tuple[str, ...]) -> list[Diagram]:
    out: list[Diagram] = []
    lines = f.lines
    i = 0
    while i < len(lines):
        m = FENCE_RE.match(lines[i])
        if not m:
            i += 1
            continue
        ticks, lang, indent = m.group("ticks"), m.group("lang").lower(), m.group("indent")
        close = re.compile(rf"^{re.escape(indent)}{ticks[0]}{{{len(ticks)},}}\s*$")
        start = i
        i += 1
        body: list[str] = []
        while i < len(lines) and not close.match(lines[i]):
            body.append(lines[i])
            i += 1
        if lang in langs:
            out.append(Diagram(f.rel, start + 1, lang, "\n".join(body) + "\n"))
        i += 1
    return out


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------

FRONT_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.S)
SIDECAR = "00-front-matter.yaml"
SKIP_DIRS = {"audits", "adr", "decisions", "node_modules", ".git"}
# limen's own files, which are not part of the document.
OWN_FILES = {".limen-lock.yaml", SIDECAR}


def _yaml_load(text: str, where: str):
    if yaml is None:
        raise CheckError("PyYAML is required to parse front matter and registers")
    try:
        return yaml.safe_load(text)
    except Exception as exc:
        raise CheckError(f"invalid YAML in {where}: {exc}") from exc


def load(docs: Path) -> DocSet:
    from . import lock  # lock reads sections, which live here

    docs = Path(docs).resolve()
    if docs.is_file():
        root, paths = docs.parent, [docs]
    elif docs.is_dir():
        root = docs
        paths = sorted(p for p in docs.rglob("*.md")
                       if not SKIP_DIRS & set(p.relative_to(docs).parts))
    else:
        raise CheckError(f"docs path not found: {docs}")
    if not paths:
        raise CheckError(f"no markdown files under {docs}")

    files = [MdFile(p, str(p.relative_to(root)), p.read_text(encoding="utf-8"))
             for p in paths]

    front: dict[str, Any] = {}
    front_source: str | None = None
    sidecar = root / SIDECAR
    if sidecar.exists():
        front = _yaml_load(sidecar.read_text(encoding="utf-8"), sidecar.name) or {}
        front_source = sidecar.name
    else:
        for f in files:
            if m := FRONT_RE.match(f.text):
                front = _yaml_load(m.group(1), f.rel) or {}
                front_source = f.rel
                break
    if not isinstance(front, dict):
        raise CheckError(f"front matter in {front_source} is not a mapping")

    return DocSet(root=root, files=files, front=front, front_source=front_source,
                  lock=lock.read(root))
