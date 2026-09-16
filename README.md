# Limen: Start Here

Limen is a standard for architecture documents written by agents, plus a
validator that enforces it. Every factual claim is anchored to evidence and
re-checkable, uncertainty has a first-class place to live instead of being
quietly upgraded into a fact, and drift between the document and the thing it
describes is detected mechanically rather than noticed by accident.

It applies to systems that do not exist yet and to systems that already do. The
evidence differs; the discipline does not. See §2.

*Limen* is Latin for threshold. The standard is about what crosses one:
verified claim or guess, gate passed or failed, code that still matches its
description or code that has moved.

Four artifacts. Three documents and a validator.

| Artifact | Lines | What it is | Who loads it |
| :--- | ---: | :--- | :--- |
| [`STD-LIMEN-01-Framework.md`](STD-LIMEN-01-Framework.md) | 676 | **Process.** Modes, levels L0–L3, gates, evidence tiers, provenance format, discovery protocol, update mode, diagram rules | Authoring agent, every run |
| [`STD-LIMEN-02-Templates.md`](STD-LIMEN-02-Templates.md) | 808 | **Shapes.** Every section template, register schema, ADR format, required table columns | Authoring agent, one section at a time |
| [`STD-LIMEN-03-Audit.md`](STD-LIMEN-03-Audit.md) | 541 | **Judgment.** Tailoring profiles, scoring, auditor protocol, hard gates | Auditor agent only |
| [`tools/limen/`](tools/limen/README.md) | n/a | **Enforcement.** Validates all twelve hard gates mechanically | CI, and the agent before presenting |
| [`examples/limen-hld/`](examples/README.md) | 442 | **Exemplar.** A complete HLD that passes all twelve gates under `--strict`, describing limen itself | Read once before authoring |

The split is not cosmetic. An agent authoring L2 needs `-01` §3.6 and `-02` §12–14,
about 200 lines, not 2,000. And the auditor must **never** load the authoring
context, which is why judgment lives in its own file (`-03` §4.1).

---

## 1. Context load map

Load only what the current phase needs. A single 2,000-line standard in context
is the reason agents skim standards.

| Phase | Load | ~Lines |
| :--- | :--- | ---: |
| **Intake (L0)** | `-01` §1, §2, §6 · `-02` §1–§6 · `-03` §2 | ~320 |
| **Foundations (L1)** | `-01` §3.3–3.5, §4, §5, §9 · `-02` §7–§10 | ~340 |
| **Mechanics (L2)** | `-01` §3.6 · `-02` §12–§14 | ~260 |
| **Ops & evolution (L3)** | `-01` §3.7 · `-02` §17–§22 | ~250 |
| **Update run** | `-01` §5, §7 · `-02` §25 · limen drift output | ~150 |
| **Audit** | `-03` entire · `-01` §4, §5 · **not** `-01` §3 or `-02` | ~600 |

`-01` §11 (the operating rules card, 20 lines) is worth keeping resident across
every authoring phase.

---

## 2. Three modes: greenfield and brownfield

Mode is the first thing chosen at intake, and it decides what counts as evidence,
which sections are mandatory, and how the validator judges the document. It is
recorded in front matter and cannot change within a version.

| Mode | Use when | A `[T1]` claim is anchored to | What the mode makes mandatory |
| :--- | :--- | :--- | :--- |
| `greenfield` | The system does not exist yet | PRD and RFC requirements, external standards (RFC 6749, ISO, OWASP), arithmetic sizing bounds | Nothing may be described in the present tense. Every component is a proposal, so it is `[T3]` with an owner and a trigger |
| `brownfield-asis` | Documenting a system that already runs | The repository at one pinned commit | At least 70% of L2 claims carry resolvable provenance. No proposals mixed into as-is sections |
| `brownfield-change` | Designing a change to a system that already runs | The repo at a pinned commit for as-is; requirements for to-be | As-is and to-be live in physically separate sections. A delta table and a migration plan (L3.8) are required |

### Greenfield is not a lesser case

The provenance machinery looks like it needs existing code, and it does not. In
greenfield mode a `[T1]` claim cites a requirement, a published standard or an
arithmetic derivation, and the validator does not demand commit pointers: `limen
check` reports "no pointers (greenfield)" rather than failing G1. What it does
enforce instead is tense. Describing unbuilt behaviour as though it already works
is the single most common way an agent-written greenfield design misleads its
reader, so G11 treats it as a gate failure rather than a style note.

The parts of the standard that carry the most weight in greenfield are the ones
with no code in them at all: constraints, the quality tree, the six-part
scenarios, the trade-off index and the ADRs behind it. Those are what make a
design reviewable before anything is built.

### Brownfield gets the drift machinery

Once there is a repository, `[T1]` claims point at it, and the document can be
re-checked against the code forever after:

```bash
limen check --docs docs/architecture --repo . --at HEAD
```

This is the part greenfield cannot have yet, and the reason brownfield documents
carry a higher evidence bar.

### Which to pick

- Designing something that does not exist: `greenfield`.
- Writing down a system that already runs, with no change proposed: `brownfield-asis`.
- Changing an existing system: `brownfield-change`. This is the most common real
  case and the easiest to get wrong, because as-is and to-be blur together in
  prose. The standard forbids mixing them in a single paragraph, and the
  validator checks it.

### When a greenfield system gets built

The mode changes. Once the system ships, re-baseline the document as
`brownfield-asis`: pin the commit, and every `[T3]` proposal that actually got
built becomes a `[T1]` claim with a provenance pointer. Proposals that did not
get built stay `[T3]` or move to the roadmap. This is a major version bump,
because the evidence rules change underneath every claim in the document.

---

## 3. Authoring an HLD: the agent's loop

### First run in a repository

```bash
# 1. Pin the baseline. Everything [T1] resolves against this one commit.
git rev-parse HEAD

# 2. Confirm the validator runs before writing anything.
python3 tools/limen/bin/limen check --docs docs/architecture --repo . --gates G9
```

### The loop

```
L0  Intake          → present → HUMAN GATE 0
L1  Foundations     → present → HUMAN GATE 1
L2  Mechanics       → present → HUMAN GATE 2
L3  Ops & evolution → present → AUDIT (separate agent)
```

At each level the agent:

1. **Writes** sections into `docs/architecture/`, wrapped in
   `<!-- agent:begin id="L2.4" -->` markers.
2. **Stamps** block hashes: `limen stamp --docs docs/architecture`
3. **Validates**: `limen check --docs docs/architecture --repo .`
4. **Fixes** every gate failure. A gate failure means the document is not yet
   reviewable, so do not present it.
5. **Presents** a summary plus the open questions raised at this level, and stops.

The agent does not proceed to the next level until a human responds. That is the
whole point of the gates (`-01` §3.1): a misread requirement at L1 corrupts every
schema, flow and cost model below it.

### Non-negotiables while writing

From `-01` §11, the five that matter most:

- **Tag every claim** `[T0]`/`[T1]`/`[T2]`/`[T3]`. Untagged is invalid.
- **`[T0]` is free.** A fabricated `[T2]` is the worst outcome in this standard.
- **Provenance or it didn't happen**: `path@sha::symbol`, one baseline commit.
- **Quote the literal** for every limit, timeout, size, capacity value.
- **Confirm at call sites**, never at imports or names.

---

## 4. Updating an existing HLD

This is the majority of real work and it is **not** a re-run of §2.

```bash
# What has drifted since the baseline?
python3 tools/limen/bin/limen check --docs docs/architecture --repo . --at HEAD
# exit 3 = gates pass but claims have drifted
```

Then follow `-01` §7.3:

1. Read the drift report: `moved` / `missing` / `value-changed` per claim.
2. Re-pin `repo.commit`; record the old one under `supersedes`.
3. **Repair only what drifted.** Do not regenerate clean sections; churn buries
   the real change in diff noise.
4. Claims that cannot be re-verified become `[T0]` + a `Q-nn`. Never delete them
   silently, never leave them asserted.
5. Append to the front-matter `changelog`.
6. Bump: patch for provenance repair, minor for new components, **major for any
   change to L1.4 quality priorities or a shaping ADR** (which re-opens Gate 1).
7. Re-run `limen`, then re-audit at the profile's depth (`-03` §2.3).

**If `limen` reports a G10 hash mismatch, stop.** A human edited agent-owned
content. Promote that block to `<!-- human:begin -->` and raise a `Q-nn`. Do not
run `limen stamp` to make the error go away; that destroys the edit.

---

## 5. Auditing

The audit is a **separate agent invocation with a clean context**. Self-audit
scores the reasoning the author remembers, not the reasoning on the page.

Give the auditor exactly: the HLD files, the ADR directory, the repo at
`repo.commit`, and `-03` (plus `-01` §4–§5 for the tier and provenance rules).
Withhold the authoring transcript, plan, and notes.

The auditor must do more than read (`-03` §4.2): sample ≥10 provenance pointers,
attempt to **falsify** the three load-bearing `[T2]` claims, recompute the
timeout and sizing arithmetic, and run the silence audit: what a reader in each
stakeholder role needs and cannot find.

Output is `docs/architecture/audits/<date>-<version>.yaml` (`-03` §11).

> Read the audit in this order: **gates before scores, floors before totals, and
> the falsification section before anything else.** A 92 with a refuted
> falsification attempt is worth less than a 78 with three honest open questions.

---

## 6. The human's job at each gate

The gates are worthless if the answer is always "approved, continue."

| Gate | What you are actually deciding | The question that catches most errors |
| :--- | :--- | :--- |
| **0** Intake | Is the mode right, are the constraints real, is the profile right? | *"What constraint did you not find, and did you ask or assume?"* |
| **1** Foundations | Are these the quality attributes we care about, in this order? | *"Show me the conflict set. Which scenario loses, and who agreed to that?"* |
| **2** Mechanics | Do the contracts and data semantics match reality? | *"Which claim here would you least like to be wrong about?"* |
| **3** Audit | Is the document fit to review? | *"What did the falsification attempts find?"* |

At Gate 0 and Gate 1, also read the Open Questions register. **An empty one is a
red flag, not a clean bill of health.** It means the agent had nowhere it was
willing to admit uncertainty. Healthy is 5–20 at L0, declining across gates.

---

## 7. Wiring it into an agent harness

Paste into the repo's `CLAUDE.md` (or the equivalent for your agent):

```markdown
## Architecture documentation

HLDs in this repo follow `docs/standards/STD-LIMEN-01-Framework.md`.

When asked to create or update an HLD:
1. Read STD-LIMEN-01 §11 (operating rules) first, always.
2. Load only the phase you are in; see the context load map in the standards README.
3. Never one-shot all levels. Present L0, stop, and wait.
4. Before presenting anything, run:
   `python3 tools/limen/bin/limen check --docs docs/architecture --repo . --strict`
   Fix every failure. A gate failure means it is not ready to present.
5. Never self-audit. The audit is a separate invocation (STD-LIMEN-03 §4.1).
```

For updates, trigger on the drift check rather than on a schedule. Run
`limen check --at HEAD` in CI (advisory on code PRs, blocking on HLD PRs) and let
exit code 3 open the ticket. That is fitness function `FF-07`.

---

## 8. Right-sizing: the smallest legitimate HLD

The full standard describes a `P4-regulated-critical` document. Most systems are
not that, and a standard that produces 80 pages for a cron job will be ignored.

For `P1-internal-tool` or `P5-library-sdk`, a legitimate HLD is a **single file**
with: front matter, concerns, constraints, 3–5 quality scenarios, 2–4 ADRs, one
C4 L2 diagram, the contract catalogue, and the RAID log. The registers stay,
because they are the traceability backbone and they are cheap, but the deep-dive
sections collapse to a paragraph each.

The tailoring profile (`-03` §2) is the mechanism; a category weighted `0` is
marked `N/A` and excluded from the floors. Use it. Over-applying the standard is
its most likely failure mode in practice.

---

## 9. First-run checklist for a new repository

- [ ] `pip install pyyaml`; confirm mermaid-cli resolves (`--gates G2` on any doc)
- [ ] Create `docs/architecture/` and `docs/adr/`
- [ ] Add `.limen-cache.json` to `.gitignore`
- [ ] Copy these three standards into `docs/standards/`
- [ ] Add the `CLAUDE.md` block from §6
- [ ] Add the CI workflow from [`tools/limen/README.md`](tools/limen/README.md#ci)
      (**with `fetch-depth: 0`**, or G1 cannot reach the baseline commit)
- [ ] Read [`examples/limen-hld/`](examples/README.md) once, to see what a
      gate-passing document looks like end to end
- [ ] Run L0 on the repo and read the Open Questions before anything else

---

## Attribution

> Limen is not affiliated with or endorsed by arc42.org. arc42® is a
> registered trademark of Dr. Gernot Starke and Dr. Peter Hruschka.
