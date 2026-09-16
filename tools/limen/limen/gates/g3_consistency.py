"""G3 — model name consistency.

STD-LIMEN-01 V-1: an element's name is identical across every diagram and
every prose mention. V-2: every C4 L3 component belongs to exactly one L2
container that exists in the L1 context.

Three checks, deliberately separated by how deterministic they are:

  containment   FAIL always. Needs `<!-- c4: level=3 parent="X" -->` annotations;
                skipped with a note when a document does not annotate its levels.
  near-duplicate  FAIL above a high similarity band ("Ingest Service" vs
                "Ingestion Service"), WARN in a lower band.
  prose-absent  WARN (FAIL under --strict). An element named in a diagram and
                never written in prose is unreviewable (V-6).
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher

from ..docset import DocSet
from ..model import GateResult

C4_ANNOTATION_RE = re.compile(
    r"<!--\s*c4:\s*level\s*=\s*(?P<level>[123])"
    r"(?:\s+parent\s*=\s*\"(?P<parent>[^\"]*)\")?\s*-->"
)
PROSE_TERM_RE = re.compile(r"`([A-Za-z][\w][\w .\-/]{2,40})`")

# Same thing, written two ways. Expanded before comparison so that
# "ingest-svc" and "Ingest Service" collide instead of merely resembling.
ABBREV = {
    "svc": "service", "srv": "service", "api": "api", "gw": "gateway",
    "db": "database", "mq": "queue", "k8s": "kubernetes", "lb": "loadbalancer",
    "auth": "authentication", "cfg": "configuration", "repo": "repository",
    "mgr": "manager", "ctrl": "controller", "proc": "processor", "svcs": "service",
}

HIGH_BAND = 0.86     # near-certain inconsistency
LOW_BAND = 0.72      # worth a look

# Generic infrastructure nouns that legitimately appear in diagrams without
# being named entities in the prose.
GENERIC = {
    "user", "users", "client", "clients", "browser", "internet", "database",
    "object storage", "cache", "queue", "cdn", "load balancer", "dns", "email",
    "sms", "logs", "metrics", "monitoring", "start", "end", "yes", "no",
}


def normalize(name: str) -> str:
    tokens = re.split(r"[^a-z0-9]+", name.lower())
    return "".join(ABBREV.get(t, t) for t in tokens if t)


def _annotations(docs: DocSet) -> dict[int, tuple[int, str | None]]:
    """diagram-line -> (level, parent) from `<!-- c4: ... -->` comments."""
    out: dict[int, tuple[int, str | None]] = {}
    for f in docs.files:
        lines = f.lines
        for n, line in enumerate(lines, 1):
            if m := C4_ANNOTATION_RE.search(line):
                for look in range(n, min(n + 4, len(lines) + 1)):
                    if look <= len(lines) and lines[look - 1].strip().startswith("```"):
                        out[look] = (int(m.group("level")), m.group("parent"))
                        break
    return out


def run(docs: DocSet, strict: bool = False) -> GateResult:
    gate = GateResult("G3", "Model name consistency")
    elements = docs.diagram_elements()
    if not elements:
        gate.detail = "no diagram elements found"
        return gate

    annotations = _annotations(docs)
    by_level: dict[int, set[str]] = {}
    for name, d in elements:
        level, _ = annotations.get(d.line, (None, None))
        if level:
            by_level.setdefault(level, set()).add(name)

    containment = _check_containment(gate, docs, elements, annotations, by_level)
    dupes = _check_near_duplicates(gate, docs, elements, strict)
    absent = _check_prose_presence(gate, docs, elements, strict)

    gate.stats = {
        "elements": len({n for n, _ in elements}),
        "diagrams": len({d.line for _, d in elements}),
        "annotated_levels": sorted(by_level),
        "near_duplicates": dupes,
        "absent_from_prose": absent,
        "containment_checked": containment,
    }
    gate.detail = (f"{gate.stats['elements']} element(s), {dupes} near-duplicate "
                   f"name(s), {absent} absent from prose")
    return gate


def _check_containment(gate, docs, elements, annotations, by_level) -> bool:
    if not annotations:
        gate.warn("no `<!-- c4: level=N parent=\"X\" -->` annotations found; C4 "
                  "containment (V-2) cannot be checked. Annotate each diagram to "
                  "enable it")
        return False

    parents_available = by_level.get(2, set()) | by_level.get(1, set())
    checked = False
    for _, d in {id(d): (n, d) for n, d in elements}.values():
        level, parent = annotations.get(d.line, (None, None))
        if level != 3:
            continue
        checked = True
        if not parent:
            gate.fail("a level-3 diagram does not declare its parent container; "
                      'annotate it `<!-- c4: level=3 parent="..." -->` so V-2 '
                      "containment can be verified", file=d.file, line=d.line)
            continue
        if not any(normalize(parent) == normalize(p) for p in parents_available):
            gate.fail(f"level-3 diagram declares parent '{parent}', which is not a "
                      f"container in any level-1/2 diagram (V-2 orphan)",
                      file=d.file, line=d.line,
                      detail={"parent": parent, "available": sorted(parents_available)})
    return checked


def _check_near_duplicates(gate, docs, elements, strict) -> int:
    pool: dict[str, tuple[str, int]] = {}      # name -> (file, line)
    for name, d in elements:
        pool.setdefault(name, (d.file, d.line))

    prose_terms: dict[str, tuple[str, int]] = {}
    diagram_norms = {normalize(n) for n in pool}
    for f in docs.files:
        for n, line in enumerate(f.lines, 1):
            if f.fenced(n - 1):
                continue
            for m in PROSE_TERM_RE.finditer(line):
                term = m.group(1).strip()
                if "@" in term or re.match(r"^[A-Z]+-\d+$", term):
                    continue
                norm = normalize(term)
                if norm in diagram_norms and term not in pool:
                    prose_terms.setdefault(term, (f.rel, n))

    names = sorted(set(pool) | set(prose_terms))
    where = {**pool, **prose_terms}
    found = 0
    seen_pairs: set[tuple[str, str]] = set()

    for i, a in enumerate(names):
        na = normalize(a)
        if not na or a.lower() in GENERIC:
            continue
        for b in names[i + 1:]:
            nb = normalize(b)
            if not nb or b.lower() in GENERIC or na == nb and a == b:
                continue
            key = (a, b)
            if key in seen_pairs:
                continue
            seen_pairs.add(key)

            if na == nb:
                ratio = 1.0
            else:
                ratio = SequenceMatcher(None, na, nb).ratio()
            if ratio < LOW_BAND:
                continue

            found += 1
            fa, la = where[a]
            msg = (f"element named two ways: '{a}' ({fa}:{la}) vs '{b}' "
                   f"({where[b][0]}:{where[b][1]}) — one name per element (V-1)")
            if ratio >= HIGH_BAND:
                gate.fail(msg, file=fa, line=la,
                          detail={"a": a, "b": b, "similarity": round(ratio, 3)})
            else:
                report = gate.fail if strict else gate.warn
                report(f"possible {msg}", file=fa, line=la,
                       detail={"a": a, "b": b, "similarity": round(ratio, 3)})
    return found


def _check_prose_presence(gate, docs, elements, strict) -> int:
    # Whitespace is collapsed before matching: prose wraps, and an element name
    # split across a line break is still present to a reader.
    prose = re.sub(r"\s+", " ", " ".join(
        line for f in docs.files
        for n, line in enumerate(f.lines, 1)
        if not f.fenced(n - 1)
    ))
    absent = 0
    for name, d in {n: d for n, d in elements}.items():
        if name.lower() in GENERIC or len(name) < 4:
            continue
        if re.sub(r"\s+", " ", name) in prose:
            continue
        absent += 1
        report = gate.fail if strict else gate.warn
        report(f"element '{name}' appears in a diagram but not in the prose; every "
               "diagram needs a prose companion naming what it shows (V-6)",
               file=d.file, line=d.line, detail={"element": name})
    return absent
