---
id: ADR-001
title: Resolve symbols with layered regex rather than tree-sitter
status: accepted
date: 2026-09-16
deciders: ["@maintainer"]
optimizes_for: [QA-03]
sacrifices: [QA-05]
constraints: [K-01, K-02]
affects_sections: [L2.1]
---

# ADR-001: Resolve symbols with layered regex rather than tree-sitter

## Context and problem statement

G1 must locate a named symbol inside a file at a pinned commit, across whatever
languages the documented repository happens to use. The locator decides whether a
claim is reported as grounded or as unresolved, so both its misses and its false
matches are visible to every reader of the document.

## Decision drivers

- `K-01` PyYAML is the only third-party dependency.
- `K-02` must run with no network access, so no grammar downloads at runtime.
- `QA-03` portability: an air-gapped reviewer must get the same result.
- `QA-05` a passing run must carry information, which argues for precision.
- `K-03` one maintainer, so per-language grammar upkeep is a real cost.

## Considered options

### Option A: Layered regex, most precise first (chosen)

Structured path walk for YAML and JSON, then language-aware declaration patterns,
then a bare identifier match, then an explicit line range.

- **Pros:** No dependencies, no grammars to ship, works on any file the parser has
  never seen. Each layer records how it matched, so a weak match can be reported
  as low-durability rather than silently accepted.
- **Cons:** Declaration patterns are hand-written per language and will miss
  unusual formatting. Precision is lower than a real parser.

### Option B: tree-sitter with bundled grammars

- **Pros:** Correct parsing, accurate symbol ranges, one mechanism for every
  supported language.
- **Cons:** A compiled dependency and a grammar per language, against `K-01`.
  Languages without a bundled grammar fail closed with no fallback, which is a
  worse failure than an imprecise match.

### Option C: Exact string search only

- **Pros:** Trivial, no per-language knowledge at all.
- **Cons:** Cannot distinguish a declaration from a mention, so a symbol deleted
  but still referenced in a comment would resolve. That defeats the gate.

## Decision outcome

Chosen: **Option A**. Portability and zero dependencies are constraints rather
than preferences, and the layered design converts the precision loss into
something visible: a match made by the weakest layer is reported, and `--strict`
rejects it. Option C fails the gate's purpose; Option B fails `K-01`.

## Consequences

- **Positive:** Runs anywhere Python does. A file type nobody anticipated still
  resolves through the identifier layer rather than erroring.
- **Negative:** Declaration patterns need extending per language, and a miss
  presents as an unresolved claim, which costs author trust. Tracked as `Q-01`.
- **Revisit trigger:** if the measured miss rate on a real multi-language
  repository exceeds 5%, reopen with Option B.
