---
id: ADR-002
title: Record section ownership in a lock file keyed by heading
status: accepted
date: 2026-10-09
superseded_by: null
---

# ADR-002: Record section ownership in a lock file keyed by heading

## Context

An agent that regenerates a document destroys whatever a person added to it. 5.x
prevented this with inline markers: every agent-written block was wrapped in
`<!-- agent:begin id="…" hash="sha256:…" -->`, and a hash that no longer matched
meant a person had edited the block. That worked, and it put machine bookkeeping
in front of every reader of every document, and made people edit inside markers
they had to leave intact.

## Options

**A. A lock file keyed by `##` heading (chosen).** `limen stamp` writes
`.limen-lock.yaml` beside the document, mapping each heading to the hash of what
an agent last wrote there, or to `human`. The prose carries no markup, and a
person edits without ceremony. The unit is a whole `##` section, and a renamed
heading loses its entry.

**B. Inline hashed markers, as in 5.x.** Ownership can be as fine as a paragraph,
and it travels with the text when sections move. Every reader sees the markers,
and an edit that breaks one breaks the record.

**C. Infer ownership from git authorship.** No bookkeeping at all. But agents
commit as the person running them, so git cannot tell an agent's edit from that
person's, which is the one distinction this exists to make.

**D. Keep no record.** Simplest. Agents then overwrite people's edits, which is
the failure the record exists to prevent.

## Decision

A. The prose is read by everyone and the lock only by tools, so the bookkeeping
belongs in the lock. B is the tempting alternative and loses on readability;
C cannot make the distinction at all.

## Consequences

- Sacrifices granularity: one edit anywhere in a long section makes the whole
  section a person's. Tracked as `Q-04`.
- A renamed heading drops its entry, so the section reads as a person's until
  stamped again. This fails safe (`R-07`).
- The record is only as good as the protocol: an agent that claims a section it
  did not write defeats it (`R-06`).
- Revisit if, after a month of real use, sections recorded as a person's cover so
  much of the document that agents cannot repair drift.
