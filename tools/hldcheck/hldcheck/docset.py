"""Discovery and parsing of an HLD document set.

Handles both layouts from STD-ARCH-HLD-01 §10.1: a directory of numbered
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

# v3-style pointers that v4 forbids (STD-ARCH-HLD-01 §5.1).
LEGACY_POINTER_RE = re.compile(r"`?(?P<uri>file://[^\s`)]+)`?")
ABSOLUTE_POINTER_RE = re.compile(r"`(?P<path>/[^`\s@]+)@[0-9a-fA-F]{7,40}")

FENCE_RE = re.compile(r"^(?P<indent>\s*)(?P<ticks>`{3,}|~{3,})\s*(?P<lang>[\w+-]*)\s*$")

MARKER_RE = re.compile(
    r"<!--\s*(?P<owner>agent|human):(?P<pos>begin|end)\s+(?P<attrs>[^>]*?)-->"
)
ATTR_RE = re.compile(r'(\w+)\s*=\s*"([^"]*)"')

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

    @property
    def lines(self) -> list[str]:
        return self.text.splitlines()

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
SKIP_DIRS = {"audits", "node_modules", ".git"}


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
