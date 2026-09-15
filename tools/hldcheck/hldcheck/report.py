"""Output renderers: text (human), json (STD-ARCH-HLD-03 §6.3), sarif (code scanning)."""
from __future__ import annotations

import json
import sys
from typing import Any

from .model import FAIL, PASS, SKIP, WARN, GateResult

_GLYPH = {PASS: "PASS", FAIL: "FAIL", WARN: "WARN", SKIP: "SKIP"}
_COLOR = {PASS: "\033[32m", FAIL: "\033[31m", WARN: "\033[33m", SKIP: "\033[90m"}
_RESET = "\033[0m"
_DIM = "\033[2m"


def _c(text: str, color: str, enabled: bool) -> str:
    return f"{color}{text}{_RESET}" if enabled else text


def render_text(payload: dict, gates: list[GateResult], verbose: bool = False,
                stream=None) -> None:
    stream = stream or sys.stdout
    color = stream.isatty()
    w = stream.write

    w(f"hldcheck  {payload['doc']} v{payload['version']}  "
      f"baseline {payload['baseline'][:7]}")
    if payload.get("evaluated_at") and payload["evaluated_at"] != payload["baseline"]:
        w(f"  (drift scan at {payload['evaluated_at'][:7]})")
    w("\n\n")

    for gate in gates:
        w(f"  {_c(_GLYPH[gate.status], _COLOR[gate.status], color)}  "
          f"{gate.id}  {gate.name}")
        if gate.detail:
            w(f"  {_c('— ' + gate.detail, _DIM, color)}")
        w("\n")
        shown = [i for i in gate.items if i.status in (FAIL, WARN)] if not verbose \
            else gate.items
        for item in shown:
            loc = ""
            if item.file:
                loc = f"{item.file}:{item.line}" if item.line else item.file
            w(f"        {_c(_GLYPH[item.status].lower(), _COLOR[item.status], color)} "
              f"{loc}{'  ' if loc else ''}{item.summary}\n")
        hidden = len(gate.items) - len(shown)
        if not verbose and hidden:
            note = f"({hidden} passing checks hidden; -v to show)"
            w(f"        {_c(note, _DIM, color)}\n")

    s = payload["summary"]
    w(f"\n  {s['passed']} passed, {s['failed']} failed, {s['warned']} warned")
    if payload.get("skipped_gates"):
        w(f", {len(payload['skipped_gates'])} not implemented "
          f"({', '.join(payload['skipped_gates'])})")
    w("\n")

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


def render_sarif(payload: dict, gates: list[GateResult], stream=None) -> None:
    stream = stream or sys.stdout
    rules: dict[str, Any] = {}
    results = []
    for gate in gates:
        rules.setdefault(gate.id, {
            "id": gate.id,
            "name": gate.name,
            "shortDescription": {"text": gate.name},
            "helpUri": "https://example.invalid/STD-ARCH-HLD-03#gates",
        })
        for item in gate.items:
            if item.status not in (FAIL, WARN):
                continue
            result: dict[str, Any] = {
                "ruleId": gate.id,
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
            results.append(result)

    sarif = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [{
            "tool": {"driver": {
                "name": "hldcheck",
                "informationUri": "https://example.invalid/hldcheck",
                "rules": list(rules.values()),
            }},
            "results": results,
        }],
    }
    json.dump(sarif, stream, indent=2)
    stream.write("\n")
