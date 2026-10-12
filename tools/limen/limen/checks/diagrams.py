"""diagrams — every diagram renders.

Two layers:
  1. Static lint of the Mermaid habits that break third-party renderers even
     when mermaid itself is tolerant (LIMEN.md §11). Cheap, runs everywhere,
     and warns rather than fails.
  2. Actual render via mermaid-cli. Authoritative, needs a browser.

Renders are content-hash cached, so only changed diagrams pay the browser cost.
A diagram preceded by `<!-- limen:ignore-diagram -->` is skipped, for
documents that show deliberately invalid examples.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ..docset import DocSet, Diagram
from ..model import CheckResult, Item

CACHE_NAME = ".limen-cache.json"
IGNORE_MARK = "limen:ignore-diagram"
PARSE_ERR_RE = re.compile(r"Parse error on line (\d+)")

FLOWCHART_RE = re.compile(r"^\s*(graph|flowchart)\b(.*)$", re.M)
DIRECTIONS = {"TD", "TB", "BT", "LR", "RL"}

# `id[label]`, `id(label)`, `id{label}`, `id[[label]]`, `id((label))`, ...
NODE_RE = re.compile(r"(?<![\w\"])([A-Za-z_][\w]*)\s*(\[\[|\(\(|\[\(|\[|\(|\{\{|\{|>)"
                     r"(?P<label>[^\]\)\}\n]*)")
SPECIALS = set("()/:,#;")
HTML_RE = re.compile(r"<(?!br\s*/?>)(?!/)[a-zA-Z][a-zA-Z0-9]*\b[^>]*>")
LATEX_RE = re.compile(r"\$[^$\n]+\$")
UNICODE_ARROW_RE = re.compile(r"[←-⇿⟰-⟿⤀-⥿]")
BAD_ID_RE = re.compile(r"^\s*([^\s\"'\[\(\{<%-][^\s\[\(\{<]*)\s*(?:\[|\(|\{)")


# --------------------------------------------------------------------------
# mermaid-cli discovery
# --------------------------------------------------------------------------

def find_mmdc(explicit: str | None = None) -> list[str] | None:
    """Resolve a runnable mermaid-cli command, preferring a direct binary."""
    if explicit:
        return explicit.split()
    if env := os.environ.get("MMDC"):
        return env.split()
    if path := shutil.which("mmdc"):
        return [path]
    if shutil.which("npx"):
        for args in (["npx", "--offline", "-p", "@mermaid-js/mermaid-cli", "mmdc"],
                     ["npx", "--yes", "-p", "@mermaid-js/mermaid-cli", "mmdc"]):
            try:
                proc = subprocess.run([*args, "-V"], capture_output=True, timeout=180)
                if proc.returncode == 0:
                    return args
            except (subprocess.TimeoutExpired, OSError):
                continue
    return None


# --------------------------------------------------------------------------
# Static lint
# --------------------------------------------------------------------------

def lint(d: Diagram) -> list[tuple[str, str, int]]:
    """Returns (rule, message, line-within-diagram)."""
    out: list[tuple[str, str, int]] = []
    src = d.source
    lines = src.splitlines()
    header = FLOWCHART_RE.search(src)

    if header and header.group(2).strip().split(" ")[0].upper() not in DIRECTIONS:
        out.append(("direction", "flowchart has no explicit direction "
                                 "(use `graph TD` or `graph LR`)", 1))

    for n, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("%%"):
            continue

        for m in NODE_RE.finditer(line):
            label = m.group("label")
            if not label or label.startswith('"'):
                continue
            if SPECIALS & set(label):
                out.append(("quote-labels", f'unquoted node label contains a special '
                                   f'character: {m.group(1)}{m.group(2)}{label}…  '
                                   f'— wrap it in double quotes', n))

        if HTML_RE.search(line):
            out.append(("no-html", "raw HTML tag in a node label; only <br/> is allowed", n))
        if LATEX_RE.search(line):
            out.append(("no-latex", "LaTeX math does not render on GitHub or most "
                                "markdown viewers", n))
        if UNICODE_ARROW_RE.search(line):
            out.append(("no-unicode-arrows", "Unicode arrow in diagram source; use mermaid edge "
                                "syntax (-->)", n))
        if header and (m := BAD_ID_RE.match(line)):
            node_id = m.group(1)
            if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", node_id):
                out.append(("node-ids", f"node id '{node_id}' must match "
                                    f"[A-Za-z][A-Za-z0-9_]*; put display text in "
                                    f"the label", n))
    return out


# --------------------------------------------------------------------------
# Render
# --------------------------------------------------------------------------

def _render_one(cmd: list[str], d: Diagram, timeout: int) -> tuple[bool, str]:
    with tempfile.TemporaryDirectory(prefix="limen-") as tmp:
        src = Path(tmp) / "d.mmd"
        out = Path(tmp) / "d.svg"
        src.write_text(d.source, encoding="utf-8")
        try:
            proc = subprocess.run([*cmd, "-i", str(src), "-o", str(out), "-q"],
                                  capture_output=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return False, f"render timed out after {timeout}s"
        except OSError as exc:
            return False, f"could not run mermaid-cli: {exc}"
        if proc.returncode == 0 and out.exists() and out.stat().st_size > 0:
            return True, ""
        blob = (proc.stdout + proc.stderr).decode("utf-8", "replace")
        return False, _summarize_error(blob)


def _summarize_error(blob: str) -> str:
    """Pull the useful head off a mermaid/puppeteer stack trace."""
    keep: list[str] = []
    for line in blob.splitlines():
        if re.match(r"^\s*(at\s|Parser\.parseError|node:internal)", line):
            break
        if line.strip() and not line.startswith("Generating"):
            keep.append(line.rstrip())
    return " / ".join(keep[:6]) or blob.strip().splitlines()[0] if blob.strip() else \
        "render failed with no diagnostic output"


def _load_cache(root: Path) -> dict:
    path = root / CACHE_NAME
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def _save_cache(root: Path, cache: dict) -> None:
    try:
        (root / CACHE_NAME).write_text(json.dumps(cache, indent=1, sort_keys=True))
    except OSError:
        pass


def _ignored(docs: DocSet, d: Diagram) -> bool:
    for f in docs.files:
        if f.rel != d.file:
            continue
        lines = f.lines
        window = lines[max(0, d.line - 3): d.line - 1]
        return any(IGNORE_MARK in line for line in window)
    return False


def run(docs: DocSet, mmdc: str | None = None, strict: bool = False,
        use_cache: bool = True, jobs: int = 4, timeout: int = 120) -> CheckResult:
    check = CheckResult("diagrams", "Diagrams render")
    diagrams = [d for d in docs.diagrams() if not _ignored(docs, d)]
    if not diagrams:
        check.detail = "no diagrams found"
        return check

    lint_hits = 0
    for d in diagrams:
        for rule, message, offset in lint(d):
            lint_hits += 1
            report = check.fail if strict else check.warn
            report(f"[{rule}] {message}", file=d.file, line=d.line + offset,
                   detail={"rule": rule})

    cmd = find_mmdc(mmdc)
    cache = _load_cache(docs.root) if use_cache else {}
    rendered = cached = failed = 0

    if cmd is None:
        check.warn("mermaid-cli not found; render verification skipped. Install with "
                   "`npm i -g @mermaid-js/mermaid-cli`, or set MMDC, or pass --mmdc. "
                   "Static lint results above still apply.")
        check.stats = {"diagrams": len(diagrams), "lint_findings": lint_hits,
                       "rendered": 0, "skipped": len(diagrams)}
        check.detail = f"{len(diagrams)} diagram(s), render skipped (no mermaid-cli)"
        return check

    todo = []
    for d in diagrams:
        if use_cache and cache.get(d.digest) == "pass":
            cached += 1
        else:
            todo.append(d)

    if todo:
        with ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
            results = list(pool.map(lambda d: (d, *_render_one(cmd, d, timeout)), todo))
        for d, ok, message in results:
            if ok:
                rendered += 1
                cache[d.digest] = "pass"
                check.add(Item("pass", "renders", d.file, d.line))
            else:
                failed += 1
                cache.pop(d.digest, None)
                line = d.line
                if m := PARSE_ERR_RE.search(message):
                    line = d.line + int(m.group(1))
                check.fail(f"render failed: {message}", file=d.file, line=line,
                           detail={"source_head": d.source.splitlines()[:1]})

    if use_cache:
        _save_cache(docs.root, cache)

    check.stats = {"diagrams": len(diagrams), "rendered": rendered, "cached": cached,
                   "failed": failed, "lint_findings": lint_hits}
    check.detail = (f"{len(diagrams)} diagram(s): {rendered + cached} render, "
                    f"{failed} fail, {lint_hits} lint finding(s)")
    return check
