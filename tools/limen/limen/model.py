"""Core data types shared by every gate.

Status vocabulary is deliberately small: a gate either passed, failed, warned
(partial gates under non-strict mode), or was skipped (not applicable / tool
unavailable).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

PASS = "pass"
FAIL = "fail"
WARN = "warn"
SKIP = "skip"

# Ordering used when folding item statuses into a gate status.
_RANK = {PASS: 0, SKIP: 0, WARN: 1, FAIL: 2}


@dataclass
class Item:
    """One checked thing: a provenance pointer, a diagram, a block, a field."""

    status: str
    summary: str
    file: str | None = None
    line: int | None = None
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"status": self.status, "summary": self.summary}
        if self.file:
            out["file"] = self.file
        if self.line:
            out["line"] = self.line
        if self.detail:
            out["detail"] = self.detail
        return out


@dataclass
class GateResult:
    """Outcome of one gate (G1, G2, G9, G10, ...)."""

    id: str
    name: str
    status: str = PASS
    detail: str = ""
    items: list[Item] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)

    def add(self, item: Item) -> Item:
        self.items.append(item)
        if _RANK[item.status] > _RANK[self.status]:
            self.status = item.status
        return item

    def fail(self, summary: str, **kw: Any) -> Item:
        return self.add(Item(FAIL, summary, **kw))

    def warn(self, summary: str, **kw: Any) -> Item:
        return self.add(Item(WARN, summary, **kw))

    def ok(self, summary: str, **kw: Any) -> Item:
        return self.add(Item(PASS, summary, **kw))

    def skip(self, detail: str) -> "GateResult":
        self.status = SKIP
        self.detail = detail
        return self

    @property
    def failures(self) -> list[Item]:
        return [i for i in self.items if i.status == FAIL]

    @property
    def warnings(self) -> list[Item]:
        return [i for i in self.items if i.status == WARN]

    def to_dict(self, include_passing: bool = False) -> dict[str, Any]:
        items = self.items if include_passing else [
            i for i in self.items if i.status in (FAIL, WARN)
        ]
        out: dict[str, Any] = {"id": self.id, "name": self.name, "status": self.status}
        if self.detail:
            out["detail"] = self.detail
        if self.stats:
            out["stats"] = self.stats
        if items:
            out["items"] = [i.to_dict() for i in items]
        return out


class CheckError(Exception):
    """Validator could not run (bad input, missing repo). Exit code 2."""
