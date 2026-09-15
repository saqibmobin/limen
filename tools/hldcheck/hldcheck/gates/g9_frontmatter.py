"""G9 — front matter valid.

Schema-valid front matter, exactly one baseline commit, and declared counts that
match the document's actual content (STD-ARCH-HLD-02 §2, STD-ARCH-HLD-03 §5).
"""
from __future__ import annotations

import re
from typing import Any

from ..docset import DocSet
from ..gitio import Git
from ..model import GateResult

REQUIRED = ["doc", "id", "title", "version", "status", "mode", "level", "profile",
            "repo", "authors", "owners"]

STATUS = {"draft", "gate-0", "gate-1", "gate-2", "audited", "superseded"}
MODES = {"greenfield", "brownfield-asis", "brownfield-change"}
PROFILES = {"P1-internal-tool", "P2-product-service", "P3-data-platform",
            "P4-regulated-critical", "P5-library-sdk"}
INSPECTED = {"full", "sampled"}

SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
DOC_ID_RE = re.compile(r"^HLD-[a-z0-9][a-z0-9-]*$")
SHA40_RE = re.compile(r"^[0-9a-f]{40}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

COUNT_KEYS = ["concerns", "constraints", "quality_scenarios", "open_questions"]


def _enum(gate: GateResult, front: dict, key: str, allowed: set[str], src: str) -> None:
    value = front.get(key)
    if value is not None and value not in allowed:
        gate.fail(f"front matter `{key}` is '{value}'; expected one of "
                  f"{', '.join(sorted(allowed))}", file=src)


def run(docs: DocSet, git: Git | None = None, strict: bool = False) -> GateResult:
    gate = GateResult("G9", "Front matter valid")
    front: dict[str, Any] = docs.front
    src = docs.front_source or "(none)"

    if not front:
        gate.fail("no front matter found: expected a YAML block at the top of the "
                  "first document or a 00-front-matter.yaml sidecar")
        gate.detail = "front matter missing"
        return gate

    for key in REQUIRED:
        if front.get(key) in (None, "", [], {}):
            gate.fail(f"front matter is missing required key `{key}`", file=src)

    if front.get("doc") not in (None, "hld"):
        gate.fail(f"front matter `doc` must be 'hld', got '{front.get('doc')}'", file=src)
    if (doc_id := front.get("id")) and not DOC_ID_RE.match(str(doc_id)):
        gate.fail(f"`id` '{doc_id}' should look like HLD-<slug>", file=src)
    if (ver := front.get("version")) and not SEMVER_RE.match(str(ver)):
        gate.fail(f"`version` '{ver}' is not semver (see STD-ARCH-HLD-01 §7.3)", file=src)

    _enum(gate, front, "status", STATUS, src)
    _enum(gate, front, "mode", MODES, src)
    _enum(gate, front, "profile", PROFILES, src)

    level = front.get("level")
    if level is not None and (not isinstance(level, int) or not 0 <= level <= 3):
        gate.fail(f"`level` must be an integer 0-3, got {level!r}", file=src)

    if not isinstance(front.get("ungated", False), bool):
        gate.fail("`ungated` must be a boolean", file=src)

    _check_repo(gate, front, src, git)
    _check_people(gate, front, src)
    _check_counts(gate, front, docs, src, strict)
    _check_changelog(gate, front, src)
    _check_override(gate, front, src)

    total = len(gate.items)
    gate.stats = {"checks": total, "failures": len(gate.failures),
                  "warnings": len(gate.warnings)}
    gate.detail = ("front matter valid" if gate.status == "pass"
                   else f"{len(gate.failures)} schema violation(s)")
    return gate


def _check_repo(gate: GateResult, front: dict, src: str, git: Git | None) -> None:
    repo = front.get("repo")
    if not isinstance(repo, dict):
        if repo is not None:
            gate.fail("`repo` must be a mapping", file=src)
        return

    if not repo.get("url"):
        gate.fail("`repo.url` is required", file=src)

    commit = str(repo.get("commit", ""))
    if not SHA40_RE.match(commit):
        gate.fail(f"`repo.commit` must be a full 40-character SHA, got '{commit}'. "
                  "One baseline per document version (STD-ARCH-HLD-01 §5.1)", file=src)
    else:
        short = str(repo.get("short", ""))
        if short and not commit.startswith(short.lower()):
            gate.fail(f"`repo.short` '{short}' is not a prefix of `repo.commit`", file=src)
        if not short:
            gate.warn("`repo.short` not declared; pointers will be matched against "
                      "the full commit only", file=src)
        if git is not None and git.rev_parse(commit) is None:
            gate.fail(f"baseline commit {commit[:12]} does not exist in the repository; "
                      "G1 cannot be verified against it", file=src)

    if not isinstance(repo.get("dirty", False), bool):
        gate.fail("`repo.dirty` must be a boolean", file=src)
    elif git is not None and repo.get("dirty") is False and git.is_dirty():
        gate.warn("`repo.dirty: false` but the working tree has uncommitted changes; "
                  "the baseline may not describe what was inspected", file=src)

    inspected = repo.get("inspected")
    if inspected is not None and inspected not in INSPECTED:
        gate.fail(f"`repo.inspected` must be one of {sorted(INSPECTED)}", file=src)
    if inspected == "sampled" and not repo.get("sampling_note"):
        gate.fail("`repo.inspected: sampled` requires `sampling_note` stating what was "
                  "sampled rather than inspected (STD-ARCH-HLD-01 D-6)", file=src)


def _check_people(gate: GateResult, front: dict, src: str) -> None:
    authors = front.get("authors")
    if isinstance(authors, list):
        for i, a in enumerate(authors):
            if not isinstance(a, dict) or not a.get("name") or not a.get("kind"):
                gate.fail(f"`authors[{i}]` needs at least `name` and `kind`", file=src)
            elif a.get("kind") not in ("agent", "human"):
                gate.fail(f"`authors[{i}].kind` must be 'agent' or 'human'", file=src)
    elif authors is not None:
        gate.fail("`authors` must be a list", file=src)

    owners = front.get("owners")
    if isinstance(owners, dict):
        for key in ("document", "system"):
            if not owners.get(key):
                gate.fail(f"`owners.{key}` is required", file=src)
    elif owners is not None:
        gate.fail("`owners` must be a mapping with `document` and `system`", file=src)


def _check_counts(gate: GateResult, front: dict, docs: DocSet, src: str,
                  strict: bool) -> None:
    counts = front.get("counts")
    if counts is None:
        gate.warn("`counts` not declared; cross-check of registers against document "
                  "content is skipped", file=src)
        return
    if not isinstance(counts, dict):
        gate.fail("`counts` must be a mapping", file=src)
        return

    for key in COUNT_KEYS:
        if key not in counts:
            continue
        actual = docs.id_count(key)
        declared = counts[key]
        if declared != actual:
            gate.fail(f"`counts.{key}` declares {declared} but {actual} distinct "
                      f"IDs were found in the document set", file=src,
                      detail={"declared": declared, "actual": actual})

    if "t3_items" in counts:
        actual = docs.t3_count()
        if counts["t3_items"] != actual:
            item = gate.fail if strict else gate.warn
            item(f"`counts.t3_items` declares {counts['t3_items']} but {actual} "
                 f"[T3] tags were found", file=src,
                 detail={"declared": counts["t3_items"], "actual": actual})

    if counts.get("open_questions") == 0 or (
        "open_questions" in counts and docs.id_count("open_questions") == 0
    ):
        gate.warn("zero open questions declared; G8 treats an empty register as a "
                  "signal the agent is guessing (STD-ARCH-HLD-03 §5)", file=src)


def _check_changelog(gate: GateResult, front: dict, src: str) -> None:
    log = front.get("changelog")
    if log is None:
        return
    if not isinstance(log, list):
        gate.fail("`changelog` must be a list", file=src)
        return
    for i, entry in enumerate(log):
        if not isinstance(entry, dict):
            gate.fail(f"`changelog[{i}]` must be a mapping", file=src)
            continue
        for key in ("version", "date", "trigger", "summary"):
            if not entry.get(key):
                gate.fail(f"`changelog[{i}]` is missing `{key}`", file=src)
        if (d := entry.get("date")) and not DATE_RE.match(str(d)):
            gate.fail(f"`changelog[{i}].date` '{d}' is not YYYY-MM-DD", file=src)


def _check_override(gate: GateResult, front: dict, src: str) -> None:
    override = front.get("profile_override")
    if override is None:
        return
    if not isinstance(override, dict) or not override.get("justification"):
        gate.fail("`profile_override` requires a `justification` "
                  "(STD-ARCH-HLD-03 §2.2)", file=src)
        return
    weights = override.get("weights", {})
    if isinstance(weights, dict) and len(weights) > 1:
        gate.fail(f"`profile_override` adjusts {len(weights)} categories; at most one "
                  "±4 override is allowed before the profile itself is wrong", file=src)
