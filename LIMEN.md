# Limen

**Version:** 6.0.0 · **Status:** Canonical · **Decided by:** [`RFC-LIMEN-002`](rfcs/RFC-limen-core.md)
**Supersedes:** `STD-LIMEN-01`, `-02` and `-03` 5.x, kept at the git tag `v5-final`

Limen is a standard for architecture documents (HLDs) that agents write from
requirements or extract from running systems, and a tool, `limen`, that checks
what can be checked mechanically. This file is the whole standard. Templates for
individual sections are in [`LIMEN-reference.md`](LIMEN-reference.md); load one
when you write that section.

## 1. What Limen is for

An agent asked to write an HLD will, left alone, produce something complete,
confident, well formatted and substantially untrue. It infers components from
imports, asserts trade-offs it never weighed, and describes planned behaviour as
if it already ran.

Limen exists to get a good design anyway. Claims that others build on say how
they are known, and claims about code point at the code. Uncertainty has a legal
place to live, so a guess never has to pose as a fact. The author tries to break
its own load-bearing claims before asserting them. A person confirms the framing
before the design compounds on it, and someone else audits the result by trying
to disprove it.

**Non-goal.** Limen does not make a system production-ready. It makes a design
document fit to be reviewed by people who can judge whether the system is.

## 2. Modes

Mode is decided first, recorded in front matter, and fixed for a document version.

| Mode | Use when | A `[verified]` claim points at |
| :--- | :--- | :--- |
| `greenfield` | The system does not exist yet | Requirements, published standards, arithmetic |
| `brownfield` | The system runs | The repository at one pinned commit |

In greenfield, everything about the system is `[proposed]`. Describe what it will
do, never what it does.

A brownfield document that proposes a change keeps the change in a **Proposed
change** section (§5.4), whose claims are `[proposed]`. Nothing outside that
section describes the change. This is the easiest separation to get wrong and the
most expensive: a reader who cannot tell what runs today from what is planned
cannot review either.

When a greenfield system ships, re-baseline it as brownfield in a major version:
pin the commit, turn each proposal that was built into a verified claim with a
pointer, and leave the rest proposed.

## 3. Evidence

### 3.1 Tiers

A claim that a decision, invariant, guarantee, limit, control or risk depends on
carries exactly one tier tag. Narrative and context need none.

| Tag | Means | Requires |
| :--- | :--- | :--- |
| `[verified]` | Read from code or config, or from a cited requirement or standard | A pointer (§3.2), an ADR, a named standard such as RFC 6749, or a link |
| `[inferred]` | Concluded from verified facts | The verified facts it rests on, named nearby |
| `[proposed]` | Not built | An owner as `@handle`, and a trigger: what would cause it to be picked up |
| `[unknown]` | Could not be determined | An open question `Q-nn` that the document defines |

A tag is a code span holding exactly the bracketed word. Prose that discusses a
tier names it in plain words, as in "a verified claim", so that a mention is
never mistaken for a claim.

An inferred claim may not introduce a fact its verified facts lack: "the
service uses a worker pool" is an unsourced fact, not an inference. Proposed
content reads "will" or "Proposed:", never "does".

### 3.2 Pointers

```
`<repo-relative-path>@<short-sha>::<symbol>`
```

For example `internal/ingest/handler.go@a1b2c3d::(*Handler).Upload`,
`deploy/k8s/ingest.yaml@a1b2c3d::spec.template.spec.containers[0].resources`, or
`db/migrations/0042_add_tenant_id.sql@a1b2c3d::uploads`.

- **The path is repo-relative**, never absolute or `file://`, and **the sha is
  the one baseline commit** declared as `baseline` in front matter.
- **Name a symbol:** a function, type, constant, config key or YAML path. A
  whole-file pointer cannot show drift inside the file, so `limen` warns on it.
  A line range (`@sha#L10-L45`) is a last resort; it rots on the next commit.
- **Quote the literal for any number**, after the pointer, and `limen` confirms
  the code still says it:
  `` `internal/ingest/limits.go@a1b2c3d::MaxPartBytes` = 25165824 ``.

## 4. The ten rules

1. **Pick the mode first** (§2).
2. **Tag what others build on** (§3.1). Context and narrative need no tag.
3. **Point at the code, not the file** (§3.2), at the one baseline commit, and
   quote the literal for any number.
4. **Unknown is free.** An `[unknown]` with an open question is always
   acceptable. A guess presented as fact is the worst outcome in this standard,
   and no audit penalizes a disclosed unknown.
5. **Try to break it before you claim it.** For each tagged claim in the
   invariants, data, failure and security sections, write one line saying what
   would make it false and what you checked, with the command when it can be
   rerun. For example: *Checked: every caller of `registerLayerTable` at
   `ed42d9a`; 9 call it directly, bypassing the queue.* A counterexample makes
   the claim a finding, not something to soften in prose.
6. **Decisions live in ADRs.** Each considers at least two options a competent
   engineer might choose, and states what the chosen one sacrifices. The HLD
   indexes decisions; it does not contain them.
7. **A test counts only once you have seen it fail.** Before marking an
   invariant `tested`, break the invariant with a temporary edit or an
   expected-failure test, watch its test fail, and note how.
8. **Stop at the checkpoints.** Present the framing and wait. Present the design
   with its audit and wait (§6).
9. **Repair, don't regenerate.** Change only what drifted. Claim only sections
   you wrote, and never overwrite one a person has edited (§8).
10. **Someone else audits**, in a clean context, with the document, the ADRs and
    the repository at the baseline, never the authoring transcript (§10).

## 5. The document

### 5.1 The skeleton

| § | Section | Holds |
| :--- | :--- | :--- |
| 0 | **Summary** | Written last, about two pages: what the system is, shaping decisions with their sacrifices, invariants with status, known divergences, top risks, blocking questions |
| 1 | Problem, scope and non-goals | A specific problem, and the non-goals a reviewer might have argued for |
| 2 | Stakeholders and constraints | Who needs what from the design (`C-nn`), and what cannot change and why (`K-nn`) |
| 3 | Quality priorities | 3 to 6 ranked attributes, each with a measurable scenario (`QA-nn`), and which wins when two conflict |
| 4 | Context and containers | One or two diagrams: deployment units, external systems, trust boundaries |
| 5 | Key decisions | An index into the ADRs, each with what it sacrifices |
| 6 | Invariants | What must always hold, how it was checked, and its status: `tested`, `untested` or `violated` |
| 7 | Data and consistency | Who owns each piece of state, guarantees per flow, what a half-failure leaves behind |
| 8 | Failure and degradation | Hard and soft dependencies, timeouts and their budget, what still works when each fails |
| 9 | Security | Assets, trust boundaries, stated assumptions, top threats with their residual risk |
| 10 | Risks and open questions | Risks (`R-nn`), debt, and open questions (`Q-nn`), each with an owner and a way to resolve it |

Each section may be one paragraph. Length follows the system, not the template.

Each template in `LIMEN-reference.md` says what audits most often find missing
from its section. Four hold everywhere. A problem is a specific bottleneck with
evidence, not a mission statement. A non-goal is one a reviewer might have argued
for. An invariant is falsifiable: "single writer of the `uploads` table", not
"handles uploads". And a `violated` invariant is the most valuable line an HLD
can contain.

### 5.2 Front matter

```yaml
---
title: Ingest Platform HLD
mode: brownfield        # greenfield | brownfield
baseline: a1b2c3d       # required in brownfield; every pointer uses it
version: 2.0.0          # major: a priority or shaping decision changed
status: draft           # draft | review | accepted | superseded
adr_dir: ../adr         # optional: where the ADR files live
---
```

Git already records authorship and history, so the front matter does not.

### 5.3 Files and registers

One file by default, `docs/architecture/hld.md`, split by section into several
files only when it grows. ADRs live outside the HLD, one per file
(`docs/adr/ADR-NNN-slug.md`), and are append-only: a reversed decision is a new
ADR that supersedes the old one.

Registers (`C-`, `K-`, `QA-`, `Q-`, `R-` and `FF-` ids) are tables in the
document. A register stays a YAML file beside the document only when a tool
outside the document reads it, and the document links to it. Ids are never
reused. `limen` finds an open question in a table row whose first cell is its
id, or in a YAML entry with `id: Q-nn`.

### 5.4 Triggered sections

A section is added when its trigger holds.

| Add | When | Template |
| :--- | :--- | :--- |
| Contract catalogue and versioning policy | Anything outside the team consumes an interface | `LIMEN-reference.md` §12 |
| Proposed change: to-be design, delta table, migration and decommission plan | A brownfield document proposes a change | `LIMEN-reference.md` §13 |
| STRIDE sweep per trust boundary | Regulated data, money, identity or safety is involved | `LIMEN-reference.md` §14 |
| SLOs and fitness functions | The system runs as a service people depend on | `LIMEN-reference.md` §15 |
| Data governance and deletion cascade | It stores personal or regulated data | `LIMEN-reference.md` §16 |
| Cost model | Cost is a stated constraint | `LIMEN-reference.md` §17 |
| Rollout, rollback and recovery | A failed deploy or lost data would hurt users | `LIMEN-reference.md` §18 |
| Component deep-dives and sequence flows | A container is too complex to explain in section 4 | `LIMEN-reference.md` §19 and `LIMEN-reference.md` §20 |

## 6. The loop

| Step | Writes | Then |
| :--- | :--- | :--- |
| **Frame** | Mode and baseline, sections 1 to 3, the open questions | **Checkpoint 1:** a person confirms the problem, the constraints and the priorities |
| **Design** | Sections 4 to 10, triggered sections, ADRs, then the summary | An independent audit (§10) |
| **Review** | Nothing | **Checkpoint 2:** a person reads the document and its audit together |

### 6.1 Frame

Nothing is designed before the frame is confirmed. A misread problem, a missed
constraint or a wrong top priority corrupts every decision downstream.

Constraints cannot be inferred from code alone. Probe for organisational,
legal, technical, commercial, temporal and operational ones; what you cannot
establish is an open question, not an assumption. Record every question whose
answer would change the design. An empty open-questions table means the agent had
nowhere it was willing to admit uncertainty, and the person at the checkpoint
should ask why.

At Checkpoint 1, the question that catches most errors is *"What constraint did
you not find, and did you ask or assume?"* If the system spans more than one team,
or the STRIDE trigger holds, the author offers a third checkpoint: containers and
key decisions, before the detail.

### 6.2 Design

For a new system or a change, make the alternatives real before deciding: at
least two candidates that differ in deployment units, state ownership,
consistency model, sync and async boundaries, or where trust boundaries sit. Walk
each through the top quality scenarios. The chosen one should lose somewhere; if
it wins every row, the others were straw men (`LIMEN-reference.md` §21).

Apply rule 5 while writing sections 6 to 9. Write the summary last. Then stamp
(§8.3), run `limen check`, and fix what it reports. A failing check means the
document is not ready to show anyone.

### 6.3 Review

The audit runs in a separate session (§10). At Checkpoint 2, read its
falsification attempts first: central claims that survived an honest attempt to
break them are worth more than a longer document whose claims were never tested.
If the user explicitly asks for everything in one pass, comply, and say so at the
top of the summary.

## 7. Extracting from code

Read sources in order of reliability, and record what each showed:

1. Build and dependency manifests: the dependency graph is ground truth.
2. Infrastructure and CI config: what actually deploys beats any README.
3. Config and environment schema: the true coupling surface.
4. Data schema and migrations: the most stable description of the domain.
5. Entry points and routers: what is reachable.
6. Background work (queues, workers, cron): rarely documented, always significant.
7. Authentication and authorisation middleware: where trust boundaries are.
8. Git history: hot spots and large changes show where the design is stressed.
9. Code owners: team boundaries are architectural boundaries.
10. Existing docs and ADRs, so you do not silently reverse someone's decision.

Confirm at call sites, never at imports, since a dependency may be vestigial.
Never infer behaviour from a name (`RetryQueue` may not retry), or deployment from
code layout (five packages may ship as one process). When sources conflict,
record both and raise a question. State what you read in full and what you
sampled.

## 8. Updating

### 8.1 Drift

```bash
limen check --docs docs/architecture --repo . --at HEAD
```

Each pointer is resolved again at HEAD and reported as resolved, moved, missing or
changed. Exit 3 means the checks pass but claims have drifted. In CI, run this as
advisory on code PRs and let drift open a ticket; block only PRs that change the
HLD. A check that blocks every code PR gets routed around.

### 8.2 Repair

1. Run the drift check.
2. Re-pin `baseline`.
3. Repair only what drifted. Regenerating clean sections buries the real change
   in diff noise.
4. Turn a claim you can no longer verify into `[unknown]` with a question. Never
   delete it silently, and never leave it asserted.
5. Bump the version (§5.2).
6. Re-audit when a decision, a priority or an invariant changed.

A section that cannot be re-verified yet is marked rather than rewritten:

```markdown
> [!WARNING]
> **Stale** as of `f4e5d6c`: claims below were last verified at `a1b2c3d`. See `Q-17`.
```

### 8.3 Ownership

`limen stamp` records who wrote each `##` section in `.limen-lock.yaml`, which is
committed beside the document. A section maps either to the hash of the content an
agent last wrote there, or to `human`. A section with no entry was written by a
person.

| Command | When |
| :--- | :--- |
| `limen stamp --all` | You have just written a new document |
| `limen stamp --mine "Heading"` | You wrote or edited this section in this run |
| `limen stamp --human "Heading"` | A person owns this section, and agents stop editing it |

Run `limen check` before you edit. If `ownership` reports that a section changed
after it was stamped and you did not change it, a person did: record it with
`--human` and leave it alone. Never `--mine` a section to make the check pass,
because that destroys the edit the check exists to protect. A person hands a
section back by deleting its line from the lock. Give headings exactly as
written, or as `file.md#Heading` when two files share one.

## 9. Checks

`limen check` runs five checks. It exits 0 when they pass, 1 when one fails (or
warns, under `--strict`), 2 when it cannot run, and 3 when the checks pass but
`--at` found drift.

| Check | Fails when |
| :--- | :--- |
| `pointers` | A pointer does not resolve at the baseline, a quoted literal no longer matches, a pointer uses another commit, a `[verified]` claim carries nothing to check it against, or a brownfield document has no baseline. A whole-file or name-only pointer warns |
| `diagrams` | A Mermaid diagram does not render. Habits that break other renderers warn (§11) |
| `ownership` | A section an agent stamped has changed since, and the change has not been attributed (§8.3) |
| `uncertainty` | A tag is malformed, an `[unknown]` names no open question, a question is cited but never defined, or a `[proposed]` lacks an owner or a trigger |
| `decisions` | A cited ADR has no file |

Whether the claims are true, whether the alternatives were real and whether
anything is missing are questions for the audit. A passing check says the document
can be audited, not that it is right.

## 10. The audit

### 10.1 Inputs

A different agent instance, in a clean context, receives the HLD, the ADRs, the
repository at the baseline commit, and this file. It never sees the authoring
transcript, plan or notes, because an author scores the reasoning it remembers
rather than the reasoning on the page. If only the author's model family is
available, the record says so: shared blind spots are likely. For a regulated
system, a person signs the audit.

### 10.2 What the auditor does

1. Checks that at least ten tagged claims are true: the sentence, not just that
   its pointer resolves.
2. Reruns a sample of the author's "Checked" lines (rule 5).
3. Tries to break the three claims the design leans on most, by reading call
   sites and, where it can, by running code at the baseline.
4. Confirms that each `tested` invariant's test can actually fail (rule 7).
5. Recomputes the arithmetic: sizing, timeout budgets, cost.
6. Runs the silence audit: for each stakeholder, what do they need to decide that
   the document does not tell them?

### 10.3 Findings and verdict

| Severity | Meaning |
| :--- | :--- |
| Blocker | A tagged claim is false and not disclosed, or a check fails |
| Major | A stakeholder cannot make a decision they need to make from this document |
| Minor | Anything else worth fixing |

The verdict is **ready for review** with no blockers or majors, **revise** with
majors only, and **not reviewable** with any blocker.

A disclosed `[unknown]` or a disclosed `violated` invariant never counts against
the document. Penalising honesty trains the next author to stop looking.

### 10.4 The audit record

The auditor writes `docs/architecture/audits/<date>-<version>.md` from the
template in `LIMEN-reference.md` §22, and its findings go back to the author
verbatim, never summarised by the author.

## 11. Diagrams

- Name each element identically in every diagram and in the prose.
- Give every diagram a sentence saying what the reader should conclude from it.
- Keep to about fifteen elements, and never draw a three-item list as a diagram.
- Sequence diagrams show a failure path, not only the happy path.
- Write Mermaid that renders everywhere: declare the direction (`graph TD`),
  quote labels that contain punctuation, use `<br/>` as the only HTML, and avoid
  LaTeX, Unicode arrows, odd node ids, and semicolons in sequence messages.
- Mark a diagram that is deliberately broken, to show what not to write, with
  `<!-- limen:ignore-diagram -->` on one of the two lines before its fence.

## 12. Right-sizing

Over-applying this standard is its most likely failure. A CLI tool gets the
skeleton with most sections a paragraph long, and no triggered sections it does
not trigger. A payments platform triggers most of them. The skeleton stays
because its sections are where the design value is; their length is what varies.

## 13. Migrating from 5.x

`limen migrate --docs docs/architecture` converts a 5.x document set in place;
run it with `--dry-run` first. It rewrites `[T0]` to `[T3]` as `[unknown]`,
`[verified]`, `[inferred]` and `[proposed]`, both brownfield modes as
`brownfield`, and `repo.commit` as `baseline`. It drops retired front matter and
the `frames:` and `c4:` comments, and moves ownership markers into
`.limen-lock.yaml`. A 5.x agent block whose hash no longer matched was edited by a
person, so its sections are recorded as theirs.

It leaves `[AS-IS]`/`[TO-BE]` markers, YAML registers and the prose alone; move
to-be content into a Proposed change section by hand. `limen check --legacy` reads
a 5.x document without changing it. The 5.x standards and validator remain at the
git tag `v5-final`.
