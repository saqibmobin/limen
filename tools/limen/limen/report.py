"""Output renderers: text (people), json (tools), sarif (code scanning)."""
from __future__ import annotations

import json
import sys
from typing import Any

from .model import FAIL, PASS, SKIP, WARN, CheckResult

_GLYPH = {PASS: "PASS", FAIL: "FAIL", WARN: "WARN", SKIP: "SKIP"}
_COLOR = {PASS: "\033[32m", FAIL: "\033[31m", WARN: "\033[33m", SKIP: "\033[90m"}
_RESET = "\033[0m"
_DIM = "\033[2m"


def _c(text: str, color: str, enabled: bool) -> str:
    return f"{color}{text}{_RESET}" if enabled else text


def render_text(payload: dict, results: list[CheckResult], verbose: bool = False,
                stream=None) -> None:
    stream = stream or sys.stdout
    color = stream.isatty()
    w = stream.write

    w(f"limen  {payload['doc']} v{payload['version']}  "
      f"baseline {payload['baseline'][:7]}")
    if payload.get("evaluated_at") and payload["evaluated_at"] != payload["baseline"]:
        w(f"  (drift scan at {payload['evaluated_at'][:7]})")
    if payload.get("legacy"):
        w("  (read as 5.x; run `limen migrate` to convert)")
    w("\n\n")

    for note in payload.get("notes", []):
        w(f"  {_c('note', _DIM, color)}  {note}\n")
    if payload.get("notes"):
        w("\n")

    width = max((len(r.id) for r in results), default=0)
    for r in results:
        w(f"  {_c(_GLYPH[r.status], _COLOR[r.status], color)}  "
          f"{r.id.ljust(width)}  {r.name}")
        if r.detail:
            w(f"  {_c('(' + r.detail + ')', _DIM, color)}")
        w("\n")
        shown = r.items if verbose else [i for i in r.items if i.status in (FAIL, WARN)]
        for item in shown:
            loc = ""
            if item.file:
                loc = f"{item.file}:{item.line}" if item.line else item.file
            w(f"        {_c(_GLYPH[item.status].lower(), _COLOR[item.status], color)} "
              f"{loc}{'  ' if loc else ''}{item.summary}\n")
        hidden = len(r.items) - len(shown)
        if not verbose and hidden:
            w(f"        {_c(f'({hidden} passing items hidden; -v to show)', _DIM, color)}\n")

    s = payload["summary"]
    w(f"\n  {s['passed']} passed, {s['failed']} failed, {s['warned']} warned\n")
    drift = payload.get("drift")
    if drift and any(drift.get(k) for k in ("moved", "missing", "value_changed")):
        w(f"  drift: {drift['moved']} moved, {drift['missing']} missing, "
          f"{drift['value_changed']} value-changed\n")
    w("\n")


def render_json(payload: dict, stream=None) -> None:
    stream = stream or sys.stdout
    json.dump(payload, stream, indent=2)
    stream.write("\n")


_SARIF_LEVEL = {FAIL: "error", WARN: "warning", PASS: "note", SKIP: "note"}


def render_sarif(payload: dict, results: list[CheckResult], stream=None) -> None:
    stream = stream or sys.stdout
    rules: dict[str, Any] = {}
    out = []
    for r in results:
        rules.setdefault(r.id, {
            "id": r.id,
            "name": r.name,
            "shortDescription": {"text": r.name},
        })
        for item in r.items:
            if item.status not in (FAIL, WARN):
                continue
            result: dict[str, Any] = {
                "ruleId": r.id,
                "level": _SARIF_LEVEL[item.status],
                "message": {"text": item.summary},
            }
            if item.file:
                result["locations"] = [{
                    "physicalLocation": {
                        "artifactLocation": {"uri": item.file},
                        "region": {"startLine": item.line or 1},
                    }
                }]
            out.append(result)

    sarif = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [{
            "tool": {"driver": {"name": "limen", "rules": list(rules.values())}},
            "results": out,
        }],
    }
    json.dump(sarif, stream, indent=2)
    stream.write("\n")
