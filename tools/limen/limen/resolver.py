"""Symbol resolution for provenance pointers (`path@sha::symbol`).

STD-LIMEN-01 §5 prefers symbols over line numbers because symbols survive
refactors. Resolution is layered, most precise first, and every result records
which layer answered so the report can flag low-durability pointers:

  structured  - YAML/JSON/HCL path walk (e.g. spec.template.spec.containers[0])
  declaration - language-aware declaration pattern (func/class/const/table/...)
  identifier  - word-boundary match of the bare identifier anywhere in the file
  line-range  - explicit #L10-L45 fallback, flagged as low durability

Tree-sitter would improve the `declaration` layer; these patterns are chosen to
be dependency-free and to fail closed (a miss is reported, never guessed).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

try:  # PyYAML is used when available; absence only disables structured YAML.
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore

STRUCTURED_EXT = {".yaml", ".yml", ".json"}
LOW_DURABILITY = {"line-range", "identifier"}


@dataclass
class Resolution:
    found: bool
    line: int | None = None
    method: str = "none"
    snippet: str = ""
    note: str = ""

    @property
    def durable(self) -> bool:
        return self.found and self.method not in LOW_DURABILITY


def _ext(path: str) -> str:
    dot = path.rfind(".")
    slash = path.rfind("/")
    return path[dot:].lower() if dot > slash else ""


# --------------------------------------------------------------------------
# Layer 1: structured documents
# --------------------------------------------------------------------------

_INDEX_RE = re.compile(r"^([^\[\]]*)((?:\[\d+\])*)$")


def _walk_structured(data, symbol: str):
    """Walk a dotted path with optional [n] indices. Returns (found, value)."""
    cur = data
    for raw in symbol.split("."):
        m = _INDEX_RE.match(raw)
        if not m:
            return False, None
        key, indices = m.group(1), m.group(2)
        if key:
            if isinstance(cur, dict) and key in cur:
                cur = cur[key]
            else:
                return False, None
        for idx in re.findall(r"\[(\d+)\]", indices):
            i = int(idx)
            if isinstance(cur, list) and i < len(cur):
                cur = cur[i]
            else:
                return False, None
    return True, cur


def _resolve_structured(path: str, text: str, symbol: str) -> Resolution | None:
    ext = _ext(path)
    if ext not in STRUCTURED_EXT:
        return None
    try:
        if ext == ".json":
            data = json.loads(text)
        elif yaml is not None:
            # Multi-document YAML: try each document.
            docs = [d for d in yaml.safe_load_all(text) if d is not None]
            data = docs[0] if len(docs) == 1 else docs
        else:
            return None
    except Exception:
        return None

    candidates = [data] if not isinstance(data, list) else [data, *data]
    for cand in candidates:
        ok, value = _walk_structured(cand, symbol)
        if ok:
            leaf = symbol.split(".")[-1].split("[")[0]
            line = _first_line_matching(text, rf"^\s*{re.escape(leaf)}\s*:")
            return Resolution(True, line, "structured", snippet=_render(value))
    return Resolution(False, None, "structured")


def _render(value) -> str:
    text = json.dumps(value, default=str) if not isinstance(value, str) else value
    return text[:200]


def _first_line_matching(text: str, pattern: str) -> int | None:
    rx = re.compile(pattern)
    for n, line in enumerate(text.splitlines(), 1):
        if rx.search(line):
            return n
    return None


# --------------------------------------------------------------------------
# Layer 2: language-aware declaration patterns
# --------------------------------------------------------------------------

def _decl_patterns(ext: str, name: str, receiver: str | None) -> list[str]:
    n = re.escape(name)
    r = re.escape(receiver) if receiver else None
    go_recv = rf"^\s*func\s*\(\s*\w+\s+\*?{r}\s*\)\s+{n}\s*\(" if r else None
    return {
        ".go": [
            p for p in (
                go_recv,
                rf"^\s*func\s+{n}\s*[\(\[]",
                rf"^\s*type\s+{n}\s+",
                rf"^\s*(?:const|var)\s+{n}\s*[=\s]",
                rf"^\s*{n}\s*(?:[\w\.\*\[\]]+)?\s*=\s*",   # inside const/var block
            ) if p
        ],
        ".py": [
            rf"^\s*(?:async\s+)?def\s+{n}\s*\(",
            rf"^\s*class\s+{n}\s*[\(:]",
            rf"^\s*{n}\s*(?::[^=]+)?=",
        ],
        ".rs": [
            rf"^\s*(?:pub\s+)?(?:async\s+)?fn\s+{n}\s*[\(<]",
            rf"^\s*(?:pub\s+)?(?:struct|enum|trait|type)\s+{n}\b",
            rf"^\s*(?:pub\s+)?(?:const|static)\s+{n}\s*:",
        ],
        ".java": [
            rf"^\s*(?:public|private|protected|static|final|abstract|\s)*class\s+{n}\b",
            rf"^\s*(?:public|private|protected|static|final|\s)*[\w<>\[\],\s]+\s{n}\s*\(",
        ],
        ".sql": [
            rf"(?i)^\s*create\s+(?:or\s+replace\s+)?(?:table|index|view|function|"
            rf"materialized\s+view|type)\s+(?:if\s+not\s+exists\s+)?[\"`\[]?{n}\b",
            rf"(?i)^\s*alter\s+table\s+[\"`\[]?{n}\b",
        ],
        ".proto": [
            rf"^\s*(?:service|message|enum)\s+{n}\s*\{{",
            rf"^\s*rpc\s+{n}\s*\(",
        ],
        ".tf": [
            rf'^\s*(?:resource|data)\s+"[^"]+"\s+"{n}"',
            rf'^\s*(?:module|variable|output|locals)\s+"{n}"',
        ],
        ".sh": [rf"^\s*(?:function\s+)?{n}\s*\(\)"],
    }.get(ext, [])


_TS_JS = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}


def _ts_patterns(name: str) -> list[str]:
    n = re.escape(name)
    return [
        rf"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s*\*?\s+{n}\s*[\(<]",
        rf"^\s*(?:export\s+)?(?:abstract\s+)?class\s+{n}\b",
        rf"^\s*(?:export\s+)?(?:const|let|var)\s+{n}\s*[:=]",
        rf"^\s*(?:export\s+)?(?:type|interface|enum)\s+{n}\b",
        rf"^\s*(?:public|private|protected|static|async|\s)*{n}\s*\(",  # class method
    ]


def _split_symbol(symbol: str) -> tuple[str, str | None]:
    """'(*Handler).Upload' -> ('Upload', 'Handler'); 'Config' -> ('Config', None)."""
    sym = symbol.strip()
    m = re.match(r"^\(\s*\*?\s*([\w\.]+)\s*\)\.(\w+)$", sym)
    if m:
        return m.group(2), m.group(1)
    if "::" in sym:  # Rust / C++ style
        head, _, tail = sym.rpartition("::")
        return tail, head.split("::")[-1] or None
    if "." in sym and not sym.startswith("."):
        head, _, tail = sym.rpartition(".")
        return tail, head.split(".")[-1] or None
    return sym, None


def _resolve_declaration(path: str, text: str, symbol: str) -> Resolution | None:
    ext = _ext(path)
    name, receiver = _split_symbol(symbol)
    patterns = _ts_patterns(name) if ext in _TS_JS else _decl_patterns(ext, name, receiver)
    if not patterns:
        return None
    lines = text.splitlines()
    for pattern in patterns:
        rx = re.compile(pattern)
        for n, line in enumerate(lines, 1):
            if rx.search(line):
                return Resolution(True, n, "declaration", snippet=line.strip()[:200])
    return Resolution(False, None, "declaration")


# --------------------------------------------------------------------------
# Layer 3: bare identifier
# --------------------------------------------------------------------------

def _resolve_identifier(text: str, symbol: str) -> Resolution:
    name, _ = _split_symbol(symbol)
    rx = re.compile(rf"(?<![\w.]){re.escape(name)}\b")
    for n, line in enumerate(text.splitlines(), 1):
        if rx.search(line):
            return Resolution(
                True, n, "identifier", snippet=line.strip()[:200],
                note="matched bare identifier; prefer a declaration-bearing symbol",
            )
    return Resolution(False, None, "identifier")


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------

def resolve(path: str, text: str, symbol: str | None,
            line_start: int | None = None, line_end: int | None = None) -> Resolution:
    """Locate `symbol` (or a line range) inside `text`."""
    if symbol:
        for layer in (_resolve_structured, _resolve_declaration):
            res = layer(path, text, symbol)
            if res is not None and res.found:
                return res
            if res is not None and res.method == "structured" and not res.found:
                # A structured file with a non-matching path: fall through to a
                # textual search before declaring it missing.
                break
        return _resolve_identifier(text, symbol)

    if line_start:
        total = len(text.splitlines())
        end = line_end or line_start
        if end <= total:
            snippet = text.splitlines()[line_start - 1][:200]
            return Resolution(
                True, line_start, "line-range", snippet=snippet,
                note="line ranges rot on the next commit; prefer ::symbol",
            )
        return Resolution(False, None, "line-range",
                          note=f"file has {total} lines, pointer needs {end}")

    # Whole-file pointer: existence was already established by the caller.
    return Resolution(True, None, "file")


def find_literal(text: str, resolution: Resolution, literal: str) -> tuple[bool, str | None]:
    """Confirm a quoted literal appears at/near the resolved symbol.

    Searches the resolved line first, then a small window after it (constants are
    often declared on the following line), then the whole file as a last resort.
    Returns (matched, where).
    """
    lines = text.splitlines()
    needle = literal.strip().strip("\"'")
    if not needle:
        return False, None

    def hit(s: str) -> bool:
        return needle in s

    if resolution.line:
        idx = resolution.line - 1
        if idx < len(lines) and hit(lines[idx]):
            return True, "declaration line"
        window = lines[idx: idx + 6]
        for offset, line in enumerate(window):
            if hit(line):
                return True, f"line {resolution.line + offset}"
    for n, line in enumerate(lines, 1):
        if hit(line):
            return True, f"line {n} (outside symbol)"
    return False, None
