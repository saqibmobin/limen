"""G10 — block ownership respected.

Agent-owned regions carry a content hash. A mismatch means a human edited
agent-owned content, and STD-ARCH-HLD-01 U-2 says the agent must NOT overwrite
it: promote the block to human ownership and raise a Q-nn. Human blocks are
never modified by an agent (U-3).

`--stamp` recomputes agent hashes in place. It is a deliberate authoring step,
run immediately after writing a block — never to clear a mismatch, which would
destroy the human edit the mismatch is reporting.
"""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from ..docset import DocSet, normalize_block
from ..model import GateResult, Item

HASH_ATTR_RE = re.compile(r'(hash\s*=\s*")([^"]*)(")')
BEGIN_LINE_RE = re.compile(r'(<!--\s*agent:begin\s+[^>]*?-->)')


def run(docs: DocSet, strict: bool = False) -> GateResult:
    gate = GateResult("G10", "Block ownership respected")
    blocks, errors = docs.blocks()

    for rel, line, message in errors:
        gate.fail(f"malformed ownership marker: {message}", file=rel, line=line)

    if not blocks and not errors:
        gate.detail = ("no ownership markers found; update-safety cannot be "
                       "guaranteed (STD-ARCH-HLD-01 §7.1)")
        gate.warn(gate.detail)
        return gate

    dupes = [bid for bid, n in Counter(b.id for b in blocks).items() if n > 1]
    for bid in sorted(dupes):
        where = [f"{b.file}:{b.begin_line}" for b in blocks if b.id == bid]
        gate.fail(f"duplicate block id '{bid}' at {', '.join(where)}; ids must be "
                  "unique across the document set")

    agent = [b for b in blocks if b.owner == "agent"]
    human = [b for b in blocks if b.owner == "human"]
    unhashed = mismatched = 0

    for b in agent:
        if not b.declared_hash:
            unhashed += 1
            gate.fail("agent block has no `hash` attribute, so human edits to it "
                      "cannot be detected; run `hldcheck --stamp` after authoring",
                      file=b.file, line=b.begin_line, detail={"id": b.id})
            continue
        if b.declared_hash.strip() != b.actual_hash:
            mismatched += 1
            gate.fail(
                f"agent block '{b.id}' was edited by a human (hash mismatch). "
                "Do NOT overwrite it: promote the block to <!-- human:begin --> "
                "ownership and raise a Q-nn (STD-ARCH-HLD-01 U-2)",
                file=b.file, line=b.begin_line,
                detail={"id": b.id, "declared": b.declared_hash,
                        "actual": b.actual_hash},
            )
        else:
            gate.add(Item("pass", f"agent block '{b.id}' intact", b.file, b.begin_line))

    for b in human:
        if b.declared_hash:
            gate.warn(f"human block '{b.id}' carries a hash attribute; human blocks "
                      "are not hash-tracked and the attribute will be ignored",
                      file=b.file, line=b.begin_line)
        if not b.content.strip():
            report = gate.fail if strict else gate.warn
            report(f"human block '{b.id}' is empty", file=b.file, line=b.begin_line)

    gate.stats = {"blocks": len(blocks), "agent": len(agent), "human": len(human),
                  "unhashed": unhashed, "mismatched": mismatched}
    gate.detail = (f"{len(blocks)} block(s): {len(agent)} agent, {len(human)} human"
                   + (f", {mismatched} human-edited" if mismatched else ""))
    return gate


def stamp(docs: DocSet) -> list[str]:
    """Rewrite agent:begin hashes in place. Returns human-readable changes."""
    blocks, _ = docs.blocks()
    changed: list[str] = []

    by_file: dict[str, list] = {}
    for b in blocks:
        if b.owner == "agent":
            by_file.setdefault(b.file, []).append(b)

    for rel, items in by_file.items():
        mdfile = next(f for f in docs.files if f.rel == rel)
        text = mdfile.text
        # Rewrite from the end so earlier offsets stay valid.
        for b in sorted(items, key=lambda x: x.begin_line, reverse=True):
            actual = "sha256:" + __import__("hashlib").sha256(
                normalize_block(b.content).encode()).hexdigest()
            if b.declared_hash == actual:
                continue
            pattern = re.compile(
                r'<!--\s*agent:begin\s+[^>]*?id\s*=\s*"' + re.escape(b.id) + r'"[^>]*?-->'
            )
            m = pattern.search(text)
            if not m:
                continue
            marker = m.group(0)
            if HASH_ATTR_RE.search(marker):
                new_marker = HASH_ATTR_RE.sub(rf'\1{actual}\3', marker)
            else:
                new_marker = marker.replace("-->", f'hash="{actual}" -->')
            text = text[:m.start()] + new_marker + text[m.end():]
            changed.append(f"{rel}:{b.begin_line} {b.id} -> {actual[:19]}…")
        if text != mdfile.text:
            Path(mdfile.path).write_text(text, encoding="utf-8")
            mdfile.text = text
    return changed
