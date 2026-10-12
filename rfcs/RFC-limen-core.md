# RFC: Limen Core

**Document Reference:** `RFC-LIMEN-002`  
**Status:** Implemented in Limen 6.0  
**Target Release:** Limen 6.0  
**Related:** [`RFC-LIMEN-001`](archive/RFC-from-format-gates-to-claim-tests.md) (see §9), [`STD-LIMEN-01`](../STD-LIMEN-01-Framework.md), [`STD-LIMEN-02`](../STD-LIMEN-02-Templates.md), [`STD-LIMEN-03`](../STD-LIMEN-03-Audit.md), [`tools/limen`](../tools/limen/README.md)

---

## 1. Summary

Limen is harder to use than the value it delivers. The standard runs to 2,373
lines across three documents, with 44 named rules, 35 numbered sections (23 of
them always mandatory), 12 gates, 5 tailoring profiles and a 12-category weighted
score. The validator is about 3,700 lines. Most of that exists to make a handful
of good ideas checkable through markup, and authors spend their attention on the
markup instead of the design.

This proposal keeps the ideas and drops the machinery. Limen 6.0 becomes:

- **One core standard** of at most 400 lines, holding ten rules (§3).
- **One default skeleton** of ten short sections, plus sections added only when a
  stated trigger holds (§4).
- **Two human checkpoints and one independent audit**, in place of four gates (§5).
- **Five deterministic checks** plus drift detection, in place of twelve gates (§6).
- **An audit that reports findings and a verdict**, with no score (§7).
- **An optional reference** holding the deep-section templates, loaded when a
  section needs one.
- **Plain-word tier tags and two modes**, so that a reader can follow a document
  without knowing the standard (§12).

---

## 2. Why

**The output got heavier without getting more accurate.** The tern_poc HLD
documents a pre-launch app built by one engineer. It runs to 2,716 lines with 275
tier tags, and it passed 11 of 12 gates under `--strict`. Its independent audit
then refuted or weakened 9 of 10 load-bearing claims and found three real defects
in the system. What found them was the auditor trying to disprove claims, not the
document's structure. `RFC-LIMEN-001` §2 has the details.

**The tool spends its effort on its own markup.** Recent commits teach the
validator to accept correctly written markup (tier tags inside code spans, generic
TypeScript methods). One changed how prose may mention a tier, because the regex
could not tell a tag being used from one being discussed. Another documents
"the syntax the validator requires but the standards omitted."

**The standard says its score is not the signal.** It tells reviewers to read the
falsification attempts before anything else, because "a 92 with a refuted
falsification attempt is worth less than a 78 with three honest open questions."
The weights, profiles, floors and penalties behind that 92 are not earning their
complexity.

**Even the exemplar slipped.** The 250-line example HLD claimed CI enforcement
that did not exist, tagged as verified fact, and no gate could have caught it
(`7979d54`).

**What is worth keeping is small.** Uncertainty has a legal place to live. Claims
point at code at a pinned commit. A human confirms the framing before the design
compounds on it. Decisions live in ADRs with real alternatives. Someone else tries
to break the result. Human edits are never overwritten. These fit on one page, and
`-01` §11 is already most of it.

---

## 3. The ten rules

This is the core standard's operating card, in full.

1. **Pick the mode first.** `greenfield` if the system does not exist yet,
   `brownfield` if it does. A brownfield document that proposes a change keeps the
   change in its own section (§4.1), and nothing outside that section describes it.
2. **Tag what others build on.** A claim that a decision, invariant, guarantee,
   limit, control or risk depends on carries a tier:

   | Tag | Means | Requires |
   | :--- | :--- | :--- |
   | `[verified]` | Read from code or config, or from a cited requirement or standard | A pointer, or the citation |
   | `[inferred]` | Concluded from verified facts | The verified facts it rests on, named |
   | `[proposed]` | Not built yet | An owner and a trigger |
   | `[unknown]` | Could not be determined | An open question |

   Context and narrative need no tag.
3. **Point at the code, not the file.** `[verified]` claims cite
   `path@sha::symbol` at the document's one baseline commit, and quote the literal
   for any number.
4. **Unknown is free.** An `[unknown]` with an open question is always
   acceptable. A guess presented as fact is the worst outcome.
5. **Try to break it before you claim it.** For each tagged claim in the
   invariants, data, failure and security sections, say in one line what would
   make it false and what you checked, with the command when it can be rerun. A
   counterexample makes the claim a finding, not something to soften in prose.
6. **Decisions live in ADRs.** Each one considers at least two options a competent
   engineer might choose, and states what the chosen one sacrifices.
7. **A test counts only once you have seen it fail.** Before marking an invariant
   `tested`, break the invariant (a temporary edit, or an expected-failure test)
   and watch its test fail. Note how.
8. **Stop at the checkpoints.** Present the framing and wait. Present the design
   with its audit and wait (§5).
9. **Repair, don't regenerate.** Change only what drifted, and never overwrite a
   section a human has edited.
10. **Someone else audits.** The auditor gets a clean context: the document, the
    ADRs and the repo at the baseline, never the authoring transcript.

Rule 5 in practice, from the tern_poc evidence:

| Invariant | Tier | Basis | Checked | Status |
| :--- | :--- | :--- | :--- | :--- |
| All layer-table registration goes through the op queue | `[verified]` | `src/services/duckdb.ts@ed42d9a::enqueueDuckdbOp` | Every caller of `registerLayerTable` at `ed42d9a`: 9 call it directly | `violated` |

### 3.1 Extracting from code

The core keeps the brownfield discovery protocol (`-01` §6), condensed. Read
sources in order of reliability: build manifests, infrastructure and CI config,
config schema, data schema, entry points and routers, background work, auth
middleware, git history, code owners, then existing docs. Confirm at call sites,
not imports. Never infer behavior from a name. Record conflicting sources as open
questions. State what was sampled rather than read in full.

---

## 4. The skeleton

One file by default, split by section only when it grows. Registers become tables
inside the document and keep their `C-`, `K-`, `QA-`, `Q-`, `R-` and `FF-`
identifiers. A register stays a YAML file only when a tool outside the document
reads it, and the document links to it. In tern_poc that is
`fitness-functions.yaml`, which `scripts/benchmark-thresholds.spec.ts` reads to
keep the FF-02 thresholds in step with the benchmark.

| § | Section | Holds |
| :--- | :--- | :--- |
| 0 | **Summary** | Written last, about two pages: what the system is, shaping decisions with their sacrifices, invariants with status, known divergences, top risks, blocking questions |
| 1 | Problem, scope and non-goals | A specific problem, and non-goals a reviewer might have argued for |
| 2 | Stakeholders and constraints | Who needs what from this design, and what cannot change |
| 3 | Quality priorities | 3–6 ranked attributes, each with a measurable scenario, and which one wins when two conflict |
| 4 | Context and containers | One or two diagrams: deployment units, external systems, trust boundaries |
| 5 | Key decisions | An index into the ADRs, each with what it sacrifices |
| 6 | Invariants | What must always hold, how it was checked, status: `tested`, `untested` or `violated` |
| 7 | Data and consistency | Who owns each piece of state, guarantees per flow, what happens on a half-failure |
| 8 | Failure and degradation | Hard and soft dependencies, timeouts and their budget, what still works when each fails |
| 9 | Security | Assets, trust boundaries, stated assumptions, top threats with residual risk |
| 10 | Risks and open questions | The risk, debt and question tables |

Each section may be a paragraph. Length follows the system, not the template.

### 4.1 Triggered sections

A section is added when its trigger holds, not because a profile requires it.
Templates for each live in the reference.

| Add | When |
| :--- | :--- |
| Contract catalogue and versioning policy | Anything outside the team consumes an interface |
| Proposed change: the to-be design, a delta table, a migration and decommission plan | A brownfield document proposes a change |
| Full STRIDE sweep per boundary | Regulated data, money, identity or safety is involved |
| SLOs and fitness functions | The system runs as a service people depend on |
| Data governance and deletion cascade | It stores personal or regulated data |
| Cost model | Cost is a stated constraint |
| Rollout, rollback and DR | A failed deploy or lost data would hurt users |
| Component deep-dives and sequence flows | A container is too complex to explain in section 4 |

### 4.2 Front matter

```yaml
---
title: Terrn HLD
mode: brownfield
baseline: ed42d9a
version: 2.0.0
status: draft
---
```

Counts, register paths, profile, authors and the changelog leave the front matter.
Git records authorship and history already.

### 4.3 Ownership without markers

`agent:begin`/`agent:end` markers and inline hashes leave the prose. `limen stamp`
writes `.limen-lock.yaml`, which maps each `##` heading to a content hash or to
`human`, and the file is committed. A section with no entry was written by a
person. A recorded hash that no longer matches means the section changed after it
was stamped: the `ownership` check fails until the change is attributed, with
`--human` if a person made it or `--mine` if the agent did. Agents stop editing a
section recorded as a person's. Humans edit freely, with no ceremony.

---

## 5. The loop

| Step | Writes | Then |
| :--- | :--- | :--- |
| **Frame** | Mode and baseline, sections 1–3, the open questions | **Checkpoint 1:** a human confirms the problem, the constraints and the priorities |
| **Design** | Sections 4–10, triggered sections, ADRs, then the summary | Independent audit (§7) |
| **Review** | n/a | **Checkpoint 2:** a human reads the document and its audit together |

The first checkpoint catches what compounds: the wrong problem, a missed
constraint, the wrong priorities. That is the reason `-01` §3.1 gives for gating
in the first place. Separate human gates for mechanics and operations add a
round-trip without guarding against compounding, so this proposal folds them into
Design.

Two checkpoints are the default. At Checkpoint 1 the reviewer may ask to see the
containers and key decisions before the detail is written. The author suggests
this when the system spans more than one team, or when the full-STRIDE trigger in
§4.1 holds.

Updates follow `-01` §7.3 unchanged in spirit:

1. Run the drift check.
2. Re-pin the baseline.
3. Repair what drifted.
4. Turn claims that can no longer be verified into `[unknown]`.
5. Re-audit when a decision, priority or invariant changed.

---

## 6. Checks

| Check | Fails when | Replaces |
| :--- | :--- | :--- |
| `pointers` | A pointer does not resolve at the baseline, a quoted literal does not match, the document uses more than one baseline, or a `[verified]` claim carries nothing to check it against. A whole-file pointer warns | G1, G6 (unsupported claims), G9 (baseline) |
| `diagrams` | A Mermaid block does not render | G2 |
| `ownership` | A locked section's hash no longer matches and it has not been recorded as human-owned | G10 |
| `uncertainty` | A tag is malformed, an `[unknown]` has no open question, or a `[proposed]` lacks an owner or a trigger | G6 (form), G7 (owner, trigger), G8 (resolution) |
| `decisions` | A referenced ADR does not exist | G12 |

`--at HEAD` still reports each claim as resolved, moved, missing or changed, and
exits 3 on drift. It is the most valuable thing the validator does, and it stays.

**Retired:** G3 name consistency, G4 concern coverage, G5 response measures, G6's
coverage scan, the tense heuristics in G7 and G11, G8's non-empty rule, G9's
schema and counts, G11's markers, and G12's MADR schema. Together that is about
700 lines of gate code, plus extraction code in `docset.py` that only those gates
use. For one minor version, `--legacy` reads 5.x documents (tags, modes, front
matter and ownership markers) and `--gates` maps 5.x gate ids to checks; the 5.x
validator itself remains at the git tag `v5-final`.

**What CI blocks on:** the five checks on PRs that touch the HLD. Drift on code
PRs is advisory, as today (`-03` §6.4).

---

## 7. The audit

The auditor works from a clean context (rule 10) and does six things:

1. Checks that at least ten tagged claims are true: the sentence, not just that
   the symbol exists.
2. Reruns a sample of the author's "checked" lines (rule 5).
3. Tries to break the three claims the design leans on most.
4. Confirms that each `tested` invariant's test can actually fail (rule 7).
5. Recomputes the arithmetic: sizing, budgets, cost.
6. Runs the silence audit: for each stakeholder, what do they need that is not
   there?

**Output:** a list of findings, each with a severity, and a verdict.

| Severity | Meaning |
| :--- | :--- |
| Blocker | A tagged claim is false and not disclosed, or a check fails |
| Major | A stakeholder cannot make a decision they need to make from this document |
| Minor | Everything else worth fixing |

| Verdict | When |
| :--- | :--- |
| Ready for review | No blockers, no majors |
| Revise | Majors only |
| Not reviewable | Any blocker |

A disclosed `[unknown]` or a disclosed `violated` invariant never counts against
the document. Penalizing honesty trains the next author to stop looking.

There are no scores, weights, profiles, floors, penalties or bands.

---

## 8. What goes, what stays

| Today | Limen Core |
| :--- | :--- |
| Three standards, 2,373 lines | One core of at most 400 lines, plus an optional reference |
| 44 named rules | 10 |
| 35 sections, 23 always mandatory | 10 short sections, plus triggered ones |
| 4 gates, L0 to L3 | 2 checkpoints and an audit |
| 12 validator gates | 5 checks, plus drift |
| 5 profiles, 12 weighted categories, presence and substance split, floors, penalties, bands | Findings by severity, 3 verdicts |
| 3 modes | 2: `greenfield` and `brownfield` |
| Tier tags `[T0]`–`[T3]` | `[unknown]`, `[verified]`, `[inferred]`, `[proposed]` |
| 6 YAML registers and front-matter counts | Tables in the document; YAML only where a tool reads the register |
| `agent:` and `human:` markers with inline hashes | `.limen-lock.yaml` |
| `frames:` comments, `c4:` annotations | Nothing |
| `[AS-IS]`/`[TO-BE]` markers and tense rules | A separate Proposed change section; `[proposed]` with an owner and a trigger |
| A tier tag on every normative claim | Tags on the claims others build on |

**Kept:** the four tiers under plain names, the provenance format, drift
detection, ADRs outside the HLD, the independent audit, repair over regeneration,
the discovery protocol, and the re-baseline from greenfield to brownfield when a
system ships.

---

## 9. Relation to RFC-LIMEN-001

Both proposals start from the same evidence. `RFC-LIMEN-001` responds by adding
machinery for testing claims. This one responds by removing machinery for checking
markup, and keeps only the lightest form of claim testing.

| RFC-LIMEN-001 proposes | Limen Core |
| :--- | :--- |
| tern_poc evidence (its §2) | Adopted as motivation |
| Rule T-5 and a falsification register (`FA-nn`) | One inline "checked" line per claim (rule 5); no register |
| A probe tool API and `limen run-at` | Not needed; agents use their own tools and record the command |
| G13, mutation patches, `limen claimtest` | Rule 7: the author watches the test fail once, and the auditor confirms it |
| A critic role in the loop | Optional; not part of the standard |
| Design moves: candidates, walkthrough, premortem | Rule 6 keeps real alternatives and sacrifices; the rest becomes optional guidance in the reference |
| Summary page | Adopted (section 0) |
| Gate disposition, G1–G12 reduced and G13 added | Goes further: 5 checks, no G13 |
| Phase 0 evaluation set | Reduced to the trial in §10 |
| Auditor isolation; deterministic CI blocking, agentic review advisory | Adopted |

**Recommendation:** if this proposal is accepted, withdraw `RFC-LIMEN-001` and
keep its §2 as the record of why.

---

## 10. Rollout

1. **Write the core.** Draft the core standard and the reference from `-01`,
   `-02` and `-03`, then rewrite `examples/limen-hld/` in the new form as the
   before-and-after.
2. **Cut the validator.** Reduce it to the five checks and the lock file, keep
   `--legacy`, and add `limen migrate`. It moves inline block hashes into
   `.limen-lock.yaml`, rewrites `[T0]`–`[T3]` as the new tags, and rewrites
   both brownfield modes as `brownfield`. Version 6.0 reads 5.x documents and
   ignores retired markup; authors drop it at their next edit.
3. **Trial on tern_poc.** Convert the HLD to the core form, run an independent
   audit, and compare against the 1.1.0 audit.
4. **Retire the three standards.** Tag the last 5.x commit; the files remain in
   git history.

**Accepted if the tern_poc trial:**

- produces an HLD at most half the length of 1.1.0's 2,716 lines;
- shows no higher a share of refuted claims than the 1.1.0 audit found, sampling
  the same way;
- discloses at least one of the three system defects that audit found, through
  rule 5, before the auditor sees it.

---

## 11. Risks

| Risk | Mitigation |
| :--- | :--- |
| Mechanical catches are lost: an unframed concern (G4), a scenario without a measure (G5) | The audit's silence check and its "can a stakeholder decide" test cover both, on substance rather than form |
| An unsourced fact hides in untagged prose | Rule 2 tags anything something depends on; the auditor's claim sample includes untagged prose |
| Without profiles, the skeleton is too much for a tiny library or too little for a regulated system | Sections may be one paragraph; triggers add depth where risk is |
| No score means no number to compare across documents or over time | The standard already says the number misleads; comparing findings and verdicts is more honest |
| Headings are fragile keys for the lock file | Agents restamp when they rename a heading; a heading a human renames falls to human ownership, which is the safe default |
| Renaming tags and modes touches every existing document | `limen migrate` rewrites them mechanically, and `--legacy` accepts the old forms for one minor version |
| With `brownfield-change` gone, nothing in the front matter says a document designs a change | The Proposed change section is that signal, and its trigger brings the delta table and migration plan with it |

---

## 12. Decisions

The first draft left four questions open. They are decided as follows, and the
sections above reflect each decision.

1. **Tier tags become words.** `[verified]`, `[inferred]`, `[proposed]` and
   `[unknown]` replace `[T1]`, `[T2]`, `[T3]` and `[T0]`. A reader outside Limen
   can read them without the standard, and the old numbering put "unknown" at
   zero, which nobody guesses. Limen 6.0 is already a breaking release, so the
   migration is paid once: `limen migrate` rewrites the tags, and `--legacy`
   accepts the old ones for one minor version. A tag is still a code span, so
   prose that mentions a tier without carrying one stays distinguishable
   (`-01` Rule T-3).
2. **Two modes.** `brownfield-asis` and `brownfield-change` merge into
   `brownfield`. Mode answers one question, whether the system exists, and that
   decides what counts as evidence. Whether a change is proposed is a question
   about content. The triggered Proposed change section answers it (§4.1) and
   brings the delta table and migration plan with it. The re-baseline from
   greenfield to brownfield when a system ships is unchanged.
3. **Two checkpoints by default.** A third, between containers and detail, is
   added when the reviewer asks for it at Checkpoint 1. The author suggests it
   when the system spans more than one team or the full-STRIDE trigger holds
   (§5). A size threshold was considered and rejected: no line or container count
   predicts where a misunderstanding will compound, and the reviewer at
   Checkpoint 1 is better placed to judge.
4. **Registers are tables unless a tool reads them.** Something outside Limen
   does read them: tern_poc's `scripts/benchmark-thresholds.spec.ts` parses the
   FF-02 entry in `fitness-functions.yaml`. A register that a tool depends on
   stays a YAML file the document links to; every other register becomes a table
   (§4).

---

## 13. Implementation notes

Three places where the implementation departs from the text above, each in the
direction of less machinery. The sections above have been updated to match.

1. **Retired gates do not run under `--legacy`.** Keeping G3, G4, G5 and G11 in
   the tree as warnings would have kept most of the code this proposal removes.
   `--legacy` instead reads a 5.x document as 6.0 in memory, and anyone who needs
   the 5.x gates runs the 5.x validator from the `v5-final` tag.
2. **A changed section is attributed, not assumed.** §4.3 originally said a
   section whose hash no longer matched would be recorded as a person's
   automatically. An agent's own edits also change the hash, so `limen stamp`
   requires the change to be attributed: `--mine` for the agent's own edits,
   `--human` for a person's, and `--all` for a newly written document. `--mine`
   refuses a section already recorded as a person's.
3. **`pointers` also fails a `[verified]` claim with nothing behind it.** Rule 2
   requires a pointer, an ADR, a standard or a link; the check enforces it,
   because a verified claim nobody can check is the failure the tiers exist to
   prevent.
