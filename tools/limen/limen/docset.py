"""Discovery and parsing of an HLD document set.

Handles both layouts from STD-LIMEN-01 §10.1: a directory of numbered
markdown files with a registers/ sibling, and a single-file HLD with embedded
registers.
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

# v3-style pointers that v4 forbids (STD-LIMEN-01 §5.1).
LEGACY_POINTER_RE = re.compile(r"`?(?P<uri>file://[^\s`)]+)`?")
ABSOLUTE_POINTER_RE = re.compile(r"`(?P<path>/[^`\s@]+)@[0-9a-fA-F]{7,40}")

FENCE_RE = re.compile(r"^(?P<indent>\s*)(?P<ticks>`{3,}|~{3,})\s*(?P<lang>[\w+-]*)\s*$")

MARKER_RE = re.compile(
    r"<!--\s*(?P<owner>agent|human):(?P<pos>begin|end)\s+(?P<attrs>[^>]*?)-->"
)
ATTR_RE = re.compile(r'(\w+)\s*=\s*"([^"]*)"')

HEADING_RE = re.compile(r"^(#{1,6})\s+(?P<title>.+?)\s*$")
SECTION_ID_RE = re.compile(r"^(?P<id>L\d\.\d{1,2}(?:\.\d+)?)\b")
FRAMES_RE = re.compile(r"<!--\s*frames:\s*(?P<ids>[^>]*?)\s*-->")
TIER_TAG_RE = re.compile(r"\[T([0-3])\]")
ADR_REF_RE = re.compile(r"\bADR-(\d{1,4})\b")
QID_RE = re.compile(r"\bQ-\d+\b")
BULLET_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+\S")
TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$")
TABLE_SEP_RE = re.compile(r"^\s*\|[\s:|-]+\|\s*$")
POINTER_BARE_RE = re.compile(r"[^\s`]+@[0-9a-fA-F]{7,40}(?:::[^\s`]+)?")

# Quantities that make a sentence a factual claim about the system.
QUANTITY_RE = re.compile(
    r"\b\d[\d,.]*\s*(?:ms|µs|us|ns|s|sec|secs|seconds|m|min|mins|h|hr|hrs|d|days|"
    r"B|KB|KiB|MB|MiB|GB|GiB|TB|TiB|QPS|qps|RPS|rps|TPS|tps|%|rows|bytes|"
    r"connections|threads|workers|replicas|instances)\b"
)

OWNER_RE = re.compile(r"(?:@[\w][\w.-]*|\bowner\s*[:=]\s*\S+)", re.I)
TRIGGER_RE = re.compile(
    r"\b(?:trigger|triggered|revisit|re-?open|when\b|once\b|if\b|upon\b|"
    r"threshold|expires?|deadline)\b", re.I
)
FUTURE_RE = re.compile(
    r"\b(?:proposed|proposal|will|would|shall|should|plan(?:ned|s)?|target|"
    r"intend(?:ed|s)?|plan to|plan for|future|plan\b)\b", re.I
)
PRESENT_CLAIM_RE = re.compile(
    r"\bthe\s+(?:system|service|platform|api|gateway|worker|pipeline|component)\s+"
    r"(?!will|would|shall|should|must|may|can|might|is\s+expected|is\s+proposed)"
    r"(?:currently\s+)?[a-z]+s\b"
)
ASIS_RE = re.compile(r"\[AS-IS\]", re.I)
TOBE_RE = re.compile(r"\[TO-BE\]", re.I)

ID_PATTERNS = {
    "quality_scenarios": re.compile(r"\bQA-\d+\b"),
    "concerns": re.compile(r"\bC-\d+\b"),
    "constraints": re.compile(r"\bK-\d+\b"),
    "open_questions": re.compile(r"(?<!Q)(?<![A-Za-z])Q-\d+\b"),
    "risks": re.compile(r"\bR-\d+\b"),
    "fitness_functions": re.compile(r"\bFF-\d+\b"),
}
T3_RE = re.compile(r"\[T3\]")


@dataclass
class MdFile:
    path: Path
    rel: str
    text: str
    _lines: list[str] | None = None
    _fenced: set[int] | None = None

    @property
    def lines(self) -> list[str]:
        if self._lines is None or "\n".join(self._lines) != self.text.rstrip("\n"):
            self._lines = self.text.splitlines()
            self._fenced = None
        return self._lines

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
            self._fenced = _fenced_indices(self.lines)
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
class Block:
    owner: str         # "agent" | "human"
    id: str
    file: str
    begin_line: int
    end_line: int | None
    declared_hash: str | None
    content: str
    attrs: dict[str, str] = field(default_factory=dict)

    @property
    def actual_hash(self) -> str:
        return "sha256:" + hashlib.sha256(
            normalize_block(self.content).encode()
        ).hexdigest()


def normalize_block(content: str) -> str:
    """Canonical bytes hashed for G10.

    One leading and one trailing newline are stripped so that marker placement
    does not change the digest; everything else is preserved exactly.
    """
    if content.startswith("\n"):
        content = content[1:]
    if content.endswith("\n"):
        content = content[:-1]
    return content


@dataclass
class Section:
    """A heading whose title starts with an `L<level>.<n>` id."""

    id: str
    title: str
    file: str
    line: int
    frames: list[str] | None      # None = no frames comment; [] = explicit "—"
    body: str = ""


@dataclass
class Unit:
    """A reviewable chunk of prose: one bullet, paragraph, or table row."""

    kind: str                     # bullet | paragraph | table-row
    text: str
    file: str
    line: int
    section: str | None = None

    @property
    def tiers(self) -> list[str]:
        return TIER_TAG_RE.findall(self.text)

    @property
    def has_pointer(self) -> bool:
        return bool(POINTER_BARE_RE.search(self.text))


@dataclass
class Table:
    headers: list[str]
    rows: list[tuple[int, list[str]]]      # (line, cells)
    file: str
    line: int
    section: str | None = None

    def column(self, *names: str) -> int | None:
        for i, h in enumerate(self.headers):
            norm = re.sub(r"[^a-z]", "", h.lower())
            for n in names:
                if re.sub(r"[^a-z]", "", n.lower()) in norm:
                    return i
        return None

    @property
    def is_normative(self) -> bool:
        blob = " ".join(c for _, cells in self.rows for c in cells)
        return bool(TIER_TAG_RE.search(blob) or POINTER_BARE_RE.search(blob))


@dataclass
class DocSet:
    root: Path
    files: list[MdFile]
    front: dict[str, Any]
    front_source: str | None
    registers: dict[str, Any] = field(default_factory=dict)

    # -- aggregate extraction -------------------------------------------------

    def pointers(self) -> list[Pointer]:
        found: list[Pointer] = []
        for f in self.files:
            for m in POINTER_RE.finditer(f.text):
                literal = None
                tail = m.group("tail")
                if tail:
                    literal = tail.lstrip().lstrip("=").strip().rstrip(".") or None
                found.append(
                    Pointer(
                        raw=m.group(0).strip(),
                        path=m.group("path"),
                        sha=m.group("sha").lower(),
                        symbol=(m.group("symbol") or "").strip() or None,
                        line_start=int(m.group("l1")) if m.group("l1") else None,
                        line_end=int(m.group("l2")) if m.group("l2") else None,
                        literal=literal,
                        file=f.rel,
                        line=f.line_of(m.start()),
                    )
                )
        return found

    def legacy_pointers(self) -> list[tuple[str, int, str]]:
        """v3-style `file://` and absolute-path pointers, which v4 forbids."""
        out = []
        for f in self.files:
            for rx, label in ((LEGACY_POINTER_RE, "file:// URI"),
                              (ABSOLUTE_POINTER_RE, "absolute path")):
                for m in rx.finditer(f.text):
                    out.append((f.rel, f.line_of(m.start()), f"{label}: {m.group(0)}"))
        return out

    def diagrams(self, langs=("mermaid",)) -> list[Diagram]:
        out: list[Diagram] = []
        for f in self.files:
            out.extend(_extract_fences(f, langs))
        for path in sorted(self.root.rglob("*.mmd")):
            out.append(
                Diagram(
                    file=str(path.relative_to(self.root)),
                    line=1,
                    lang="mermaid",
                    source=path.read_text(encoding="utf-8"),
                )
            )
        return out

    def blocks(self) -> tuple[list[Block], list[tuple[str, int, str]]]:
        """Returns (well-formed blocks, structural errors)."""
        blocks: list[Block] = []
        errors: list[tuple[str, int, str]] = []
        for f in self.files:
            b, e = _extract_blocks(f)
            blocks.extend(b)
            errors.extend(e)
        return blocks, errors

    def sections(self) -> list[Section]:
        out: list[Section] = []
        for f in self.files:
            lines = f.lines
            for i, line in enumerate(lines):
                if f.fenced(i):
                    continue
                m = HEADING_RE.match(line)
                if not m:
                    continue
                sid = SECTION_ID_RE.match(m.group("title"))
                if not sid:
                    continue
                frames: list[str] | None = None
                for look in lines[i + 1: i + 5]:
                    if fm := FRAMES_RE.search(look):
                        raw = fm.group("ids").strip()
                        frames = [] if raw in ("—", "-", "", "none") else [
                            t.strip() for t in re.split(r"[,\s]+", raw) if t.strip()
                        ]
                        break
                    if HEADING_RE.match(look):
                        break
                body_end = len(lines)
                for j in range(i + 1, len(lines)):
                    if HEADING_RE.match(lines[j]) and not f.fenced(j):
                        body_end = j
                        break
                out.append(Section(
                    id=sid.group("id"), title=m.group("title"), file=f.rel,
                    line=i + 1, frames=frames,
                    body="\n".join(lines[i + 1: body_end]),
                ))
        return out

    def units(self) -> list[Unit]:
        out: list[Unit] = []
        for f in self.files:
            lines = f.lines
            section: str | None = None
            i = f.body_start
            while i < len(lines):
                if f.fenced(i):
                    i += 1
                    continue
                raw = lines[i]
                stripped = raw.strip()

                if m := HEADING_RE.match(raw):
                    sid = SECTION_ID_RE.match(m.group("title"))
                    section = sid.group("id") if sid else section
                    i += 1
                    continue
                if not stripped or stripped.startswith("<!--") or MARKER_RE.match(stripped):
                    i += 1
                    continue
                if TABLE_ROW_RE.match(raw):
                    if not TABLE_SEP_RE.match(raw):
                        out.append(Unit("table-row", stripped, f.rel, i + 1, section))
                    i += 1
                    continue
                if BULLET_RE.match(raw):
                    start, buf = i, [stripped]
                    i += 1
                    while (i < len(lines) and lines[i].strip()
                           and not BULLET_RE.match(lines[i])
                           and not HEADING_RE.match(lines[i])
                           and not TABLE_ROW_RE.match(lines[i])
                           and lines[i].startswith((" ", "\t"))):
                        buf.append(lines[i].strip())
                        i += 1
                    out.append(Unit("bullet", " ".join(buf), f.rel, start + 1, section))
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
                    out.append(Unit("paragraph", " ".join(buf), f.rel, start + 1, section))
                else:
                    i += 1
        return out

    def tables(self) -> list[Table]:
        out: list[Table] = []
        for f in self.files:
            lines = f.lines
            section: str | None = None
            i = f.body_start
            while i < len(lines):
                if f.fenced(i):
                    i += 1
                    continue
                if m := HEADING_RE.match(lines[i]):
                    sid = SECTION_ID_RE.match(m.group("title"))
                    section = sid.group("id") if sid else section
                    i += 1
                    continue
                if (TABLE_ROW_RE.match(lines[i]) and i + 1 < len(lines)
                        and TABLE_SEP_RE.match(lines[i + 1])):
                    headers = _cells(lines[i])
                    start = i + 1
                    i += 2
                    rows: list[tuple[int, list[str]]] = []
                    while i < len(lines) and TABLE_ROW_RE.match(lines[i]):
                        rows.append((i + 1, _cells(lines[i])))
                        i += 1
                    out.append(Table(headers, rows, f.rel, start, section))
                    continue
                i += 1
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

    def diagram_elements(self) -> list[tuple[str, Diagram]]:
        """Named elements (nodes, participants, subgraphs) per diagram."""
        out: list[tuple[str, Diagram]] = []
        for d in self.diagrams():
            for name in _diagram_names(d.source):
                out.append((name, d))
        return out

    def id_count(self, kind: str) -> int:
        reg = self.registers.get(kind)
        if isinstance(reg, list):
            return len(reg)
        rx = ID_PATTERNS.get(kind)
        if not rx:
            return 0
        seen: set[str] = set()
        for f in self.files:
            seen.update(rx.findall(f.text))
        return len(seen)

    def t3_count(self) -> int:
        return sum(len(T3_RE.findall(f.text)) for f in self.files)


# --------------------------------------------------------------------------
# Extraction helpers
# --------------------------------------------------------------------------

def _fenced_indices(lines: list[str]) -> set[int]:
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


def _cells(row: str) -> list[str]:
    parts = row.strip().split("|")
    if parts and not parts[0].strip():
        parts = parts[1:]
    if parts and not parts[-1].strip():
        parts = parts[:-1]
    return [p.strip() for p in parts]


_NODE_LABEL_RE = re.compile(
    r"(?<![\w\"])[A-Za-z_]\w*(?:\[\[|\(\(|\[\(|\[|\(|\{\{|\{|>)\s*"
    r"(?:\"(?P<quoted>[^\"]*)\"|(?P<bare>[^\]\)\}\n\"]+))"
)
# `-->|label|` and `-- label -->` annotate edges, not elements.
_EDGE_LABEL_RE = re.compile(r"\|[^|\n]*\||(?<=-)-\s+[^->\n]+\s+--(?=>)")
_SUBGRAPH_RE = re.compile(r"^\s*subgraph\s+(?:\w+\s*)?\[?\"?(?P<name>[^\"\]\n]+)\"?\]?")
_PARTICIPANT_RE = re.compile(
    r"^\s*(?:participant|actor)\s+\w+\s+as\s+\"?(?P<name>[^\"\n]+?)\"?\s*$"
)
_PARTICIPANT_BARE_RE = re.compile(r"^\s*(?:participant|actor)\s+(?P<name>[\w ]+?)\s*$")


def _diagram_names(source: str) -> list[str]:
    """Human-facing element names in a mermaid diagram."""
    names: list[str] = []
    for line in source.splitlines():
        if line.strip().startswith("%%"):
            continue
        if m := _SUBGRAPH_RE.match(line):
            names.append(m.group("name").strip())
            continue
        if m := _PARTICIPANT_RE.match(line):
            names.append(m.group("name").strip())
            continue
        if m := _PARTICIPANT_BARE_RE.match(line):
            names.append(m.group("name").strip())
            continue
        for m in _NODE_LABEL_RE.finditer(_EDGE_LABEL_RE.sub(" ", line)):
            label = (m.group("quoted") or m.group("bare") or "").strip()
            label = re.sub(r"<br\s*/?>", " ", label)
            label = re.sub(r"\s+", " ", label).strip()
            if label and not label.startswith("-"):
                names.append(label)
    seen: set[str] = set()
    return [n for n in names if not (n in seen or seen.add(n))]


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


def _fence_spans(f: MdFile) -> list[tuple[int, int]]:
    """Character spans of fenced code blocks, so markers inside examples are
    ignored (these standards document their own marker syntax in fences)."""
    spans: list[tuple[int, int]] = []
    offset = 0
    lines = f.text.splitlines(keepends=True)
    i = 0
    while i < len(lines):
        m = FENCE_RE.match(lines[i].rstrip("\n"))
        if not m:
            offset += len(lines[i])
            i += 1
            continue
        ticks, indent = m.group("ticks"), m.group("indent")
        close = re.compile(rf"^{re.escape(indent)}{ticks[0]}{{{len(ticks)},}}\s*$")
        start = offset
        offset += len(lines[i])
        i += 1
        while i < len(lines) and not close.match(lines[i].rstrip("\n")):
            offset += len(lines[i])
            i += 1
        if i < len(lines):
            offset += len(lines[i])
            i += 1
        spans.append((start, offset))
    return spans


def _extract_blocks(f: MdFile):
    blocks: list[Block] = []
    errors: list[tuple[str, int, str]] = []
    spans = _fence_spans(f)

    def in_fence(pos: int) -> bool:
        return any(a <= pos < b for a, b in spans)

    open_stack: list[tuple[re.Match, dict[str, str], int]] = []
    for m in MARKER_RE.finditer(f.text):
        if in_fence(m.start()):
            continue
        attrs = dict(ATTR_RE.findall(m.group("attrs")))
        line = f.line_of(m.start())
        owner, pos = m.group("owner"), m.group("pos")
        bid = attrs.get("id")
        if not bid:
            errors.append((f.rel, line, f"{owner}:{pos} marker has no id attribute"))
            continue
        if pos == "begin":
            if open_stack:
                prev = open_stack[-1][1].get("id")
                errors.append((f.rel, line,
                               f"nested block: '{bid}' opened while '{prev}' is open"))
            open_stack.append((m, attrs, line))
        else:
            if not open_stack:
                errors.append((f.rel, line, f"{owner}:end '{bid}' has no matching begin"))
                continue
            bm, battrs, bline = open_stack.pop()
            if battrs.get("id") != bid:
                errors.append((f.rel, line,
                               f"end id '{bid}' does not match begin id "
                               f"'{battrs.get('id')}'"))
            if bm.group("owner") != owner:
                errors.append((f.rel, line,
                               f"ownership mismatch: {bm.group('owner')}:begin "
                               f"closed by {owner}:end"))
            blocks.append(
                Block(
                    owner=bm.group("owner"),
                    id=battrs.get("id", bid),
                    file=f.rel,
                    begin_line=bline,
                    end_line=line,
                    declared_hash=battrs.get("hash"),
                    content=f.text[bm.end():m.start()],
                    attrs=battrs,
                )
            )
    for bm, battrs, bline in open_stack:
        errors.append((f.rel, bline,
                       f"{bm.group('owner')}:begin '{battrs.get('id')}' is never closed"))
    return blocks, errors


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------

FRONT_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.S)
SKIP_DIRS = {"audits", "adr", "decisions", "node_modules", ".git"}


def _yaml_load(text: str, where: str):
    if yaml is None:
        raise CheckError("PyYAML is required to parse front matter and registers")
    try:
        return yaml.safe_load(text)
    except Exception as exc:
        raise CheckError(f"invalid YAML in {where}: {exc}") from exc


def load(docs: Path) -> DocSet:
    docs = Path(docs).resolve()
    if docs.is_file():
        root, paths = docs.parent, [docs]
    elif docs.is_dir():
        root = docs
        paths = sorted(
            p for p in docs.rglob("*.md")
            if not SKIP_DIRS & set(p.relative_to(docs).parts)
        )
    else:
        raise CheckError(f"docs path not found: {docs}")
    if not paths:
        raise CheckError(f"no markdown files under {docs}")

    files = [
        MdFile(p, str(p.relative_to(root)), p.read_text(encoding="utf-8"))
        for p in paths
    ]

    front: dict[str, Any] = {}
    front_source: str | None = None
    sidecar = root / "00-front-matter.yaml"
    if sidecar.exists():
        front = _yaml_load(sidecar.read_text(encoding="utf-8"), sidecar.name) or {}
        front_source = sidecar.name
    else:
        for f in files:
            m = FRONT_RE.match(f.text)
            if m:
                front = _yaml_load(m.group(1), f.rel) or {}
                front_source = f.rel
                break

    registers: dict[str, Any] = {}
    declared = front.get("registers") or {}
    reg_dir = root / "registers"
    if isinstance(declared, dict):
        for name, rel in declared.items():
            path = (root / str(rel)).resolve()
            if path.exists():
                registers[name] = _yaml_load(path.read_text(encoding="utf-8"), str(rel))
    if reg_dir.is_dir():
        for path in sorted(reg_dir.glob("*.y*ml")):
            key = path.stem.replace("-", "_")
            registers.setdefault(key, _yaml_load(path.read_text(encoding="utf-8"), path.name))

    return DocSet(root=root, files=files, front=front,
                  front_source=front_source, registers=registers)
