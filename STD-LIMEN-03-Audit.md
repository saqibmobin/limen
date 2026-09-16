# Engineering Standard: Agent-Authored HLD — Audit, Tailoring & Validation

**Document Reference:** `STD-LIMEN-03`
**Version:** 5.0.0
**Status:** Canonical
**Supersedes:** `STD-ARCH-HLD-03` v4.0.0 (identical content; renamed to Limen)
**Companions:** `STD-LIMEN-01-Framework.md` (process), `STD-LIMEN-02-Templates.md` (templates)

---

## 1. What changed from the v3 scorecard, and why

The v3 scorecard was the weakest part of that standard for its stated purpose. It
had five structural problems, each addressed here:

| v3 problem | Consequence | v4 fix |
| :--- | :--- | :--- |
| Scored **presence of sections**, not correctness | An agent optimizing the rubric produces a complete, confidently wrong document scoring 95 | **Presence caps at 40% of each category**; the rest is substance criteria with explicit anti-gaming tests (§3) |
| Uniform 10-pt weights across 10 categories | A CLI tool and a payments platform judged identically | **Tailoring profiles** with per-profile weight tables (§2) |
| Self-audit by the authoring agent | Near-worthless; the agent scores the reasoning it remembers, not the reasoning on the page | **Independent auditor protocol** with a clean context (§4) |
| Penalties mixed automatable and unmeasurable items | Broken links deducted 5 pts; "speculative features masquerading as existing code" deducted 10 and was uncheckable | **Hard gates** (binary, automated) separated from **scored substance** (§5, §6) |
| No category floors | 91/100 with 0/10 on security read "ARB Approved" | **Floors** per category, with elevated floors on quality, decisions, security (§7) |

One more correction: v3's top band read *"ARB Approved (Production Ready)."*
A document cannot make a system production-ready. The bands now describe the
document's fitness for review, which is the only thing a rubric can measure.

---

## 2. Tailoring profiles

Selected at L0.5 and recorded in front matter. Borrowed from the AWS
Well-Architected **lens** concept: the same framework, weighted for the workload.

| Profile | Use when | Typical |
| :--- | :--- | :--- |
| `P1-internal-tool` | Single team, internal users, low blast radius, no external contract | Admin tooling, internal batch jobs |
| `P2-product-service` | Multi-tenant service with external users — **default** | SaaS backend, API product |
| `P3-data-platform` | Data movement/storage dominates; correctness of state is the core risk | Pipelines, warehouses, streaming, CDC |
| `P4-regulated-critical` | Regulatory exposure or safety/financial consequence of failure | Payments, health, identity, critical infra |
| `P5-library-sdk` | No runtime operations; the contract *is* the product | SDKs, libraries, CLIs, protocol implementations |

### 2.1 Weight table (points per category; each column sums to 100)

| # | Category | P1 | P2 | P3 | P4 | P5 |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: |
| 1 | Intake, stakeholders & constraints | 8 | 8 | 7 | 8 | 8 |
| 2 | Problem, scope & non-goals | 10 | 7 | 6 | 6 | 10 |
| 3 | **Quality attributes & scenarios** | 10 | 12 | 10 | 10 | 10 |
| 4 | **Decisions & alternatives** | 12 | 12 | 10 | 10 | 14 |
| 5 | Topology & decomposition | 10 | 8 | 7 | 6 | 8 |
| 6 | Interfaces & contracts | 8 | 8 | 8 | 6 | **20** |
| 7 | Data, state & consistency | 10 | 10 | **16** | 9 | 8 |
| 8 | **Security & threat model** | 6 | 10 | 8 | **15** | 6 |
| 9 | Failure modes & resilience | 8 | 10 | 9 | 11 | 6 |
| 10 | Operations, SLO & fitness functions | 8 | 8 | 7 | 8 | 2 |
| 11 | Cost, governance & compliance | 2 | 3 | 7 | 8 | 0 |
| 12 | Evolution: migration, debt, roadmap | 8 | 4 | 5 | 3 | 8 |
| | **Total** | **100** | **100** | **100** | **100** | **100** |

A category weighted `0` is marked `N/A` and excluded from floors.

### 2.2 Profile overrides

A team may override one weight by ±4 points (redistributed) with a written
justification in front matter under `profile_override`. More than one override
means the wrong profile was selected.

### 2.3 Re-audit depth by profile

| Profile | Full audit | Re-audit on update |
| :--- | :--- | :--- |
| P1, P5 | At gate 3 | Hard gates only, unless L1.4 or a shaping ADR changed |
| P2, P3 | At gate 3 | Hard gates + categories touched by the update trigger |
| P4 | At every gate | Full re-audit |

---

## 3. Scoring method: presence vs substance

Each category's points split:

- **Presence criteria — ≤ 40% of category weight.** Binary: is the required
  artifact there, in the required shape, with the required columns?
- **Substance criteria — ≥ 60% of category weight.** Judged 0–3 and scaled:
  `0 = absent/vacuous · 1 = superficial · 2 = adequate · 3 = rigorous`.

This split is the core anti-gaming mechanism. A document can score every presence
point and still fail the audit, which is the correct outcome for a
well-formatted fabrication.

**Rule S-1 (vacuity test).** Any substance criterion scores `0` if its content
would remain true if the system were replaced by an arbitrary different system in
the same domain. Generic content is absence wearing a table.

**Rule S-2 (falsifiability test).** A substance criterion scores ≤ 1 if nothing in
it could be shown wrong by reading the code. Unfalsifiable prose is not
architecture description.

**Rule S-3 (uncertainty credit).** A correctly-tagged `[T0]` open question in
place of a fabricated claim **does not reduce** the score. An auditor who
penalizes honest gaps trains the next agent to fabricate; this rule is not
optional.

---

## 4. Auditor protocol

### 4.1 Independence requirements

| Requirement | Rationale |
| :--- | :--- |
| The auditor is a **different agent instance** from the author | An author scores the reasoning it remembers, not the reasoning on the page |
| The auditor receives **only**: the HLD files, the ADR directory, the repo at `repo.commit`, and these three standards | Any authoring context leaks unwritten justification into the score |
| The auditor **must not** be shown the authoring transcript, plan, or intermediate notes | Same |
| The auditor's findings are returned **verbatim** to the author, not summarized by the author | Prevents self-serving compression |
| For `P4`, at least one **human** reviewer signs the audit | Regulatory exposure is not delegable to a rubric |

If a single-agent workflow is unavoidable, the audit must run in a fresh session
with the document re-read from disk, and the result is marked
`independence: degraded` in the audit record. A degraded audit cannot award the
top band.

### 4.2 Mandatory auditor actions

The auditor does not read and opine. It verifies.

1. **Provenance sampling.** Resolve `max(10, 15%)` of all `[T1]` provenance
   pointers at `repo.commit`. For quoted literals, confirm the value. Report the
   resolution rate. Below 95% → gate G1 fails.
2. **Falsification attempt.** Pick the three highest-impact `[T2]` claims — the
   ones the rest of the document leans on — and actively try to disprove them from
   the repo. Report the attempt and its outcome, whether or not it succeeded.
3. **Silence audit.** Identify what the document does *not* say that a reader in
   each stakeholder role (`C-nn`) would need. Missing content is invisible to a
   checklist and is the auditor's highest-value contribution.
4. **Tier spot-check.** Sample 10 claims and verify tier assignment. A `[T2]`
   that introduces an unsourced fact is a Rule T-4 violation (`-01` §4).
5. **Budget arithmetic.** Recompute the timeout/retry budget (`-02` §14.2) and
   the sizing derivations (`-02` §10). Arithmetic errors are common and mechanical
   to catch.
6. **Diagram–prose consistency.** For each diagram, check that the prose
   companion's claims are actually depicted, and vice versa.

### 4.3 Finding severity

| Severity | Definition | Effect |
| :--- | :--- | :--- |
| **Blocker** | A hard gate failed, or a claim is demonstrably false | Document cannot pass |
| **Major** | A required substance criterion scores 0–1, or a floor is breached | Revision required before approval |
| **Minor** | Scored below rigorous but adequate | Noted, not blocking |
| **Note** | Improvement suggestion | Advisory |

---

## 5. Hard gates (binary — failure blocks approval at any score)

These replace v3's penalty deductions for everything that can be checked
mechanically. A gate failure is not worth "−5 points"; it means the document is
not yet auditable.

| ID | Gate | Automatable | Check |
| :--- | :--- | :--- | :--- |
| **G1** | **Provenance resolves** | ✅ full | ≥95% of `[T1]` pointers resolve at `repo.commit`; 100% of quoted literals match |
| **G2** | Diagrams render | ✅ full | Every Mermaid block parses; every Structurizr view renders |
| **G3** | Model name consistency | ✅ full | Element names identical across C4 levels and prose (`-01` V-1); no orphan components (V-2) |
| **G4** | Concern coverage | ✅ full | Every `C-nn` framed by ≥1 section; every section frames ≥1 `C-nn` or is explicitly marked `frames: —` |
| **G5** | Response measures | ✅ full | Every `QA-nn` has a quantified `response_measure` |
| **G6** | Tier tagging | ✅ partial | No untagged normative claim; every table has a `Tier` column where required |
| **G7** | Proposal hygiene | ✅ partial | Every `[T3]` has an owner and a trigger; no `[T3]` written in present tense (`-01` M-2) |
| **G8** | Open questions present | ✅ full | Register exists; every `[T0]` resolves to a `Q-nn`; every open `Q-nn` has an owner and a resolution path. **An L0 with zero open questions fails this gate** |
| **G9** | Front matter valid | ✅ full | Schema-valid; single `repo.commit`; `counts` match actual content; `dirty: false` or justified |
| **G10** | Block ownership respected | ✅ full | No `human:` block modified; no agent block with a mismatched hash overwritten (`-01` U-2, U-3) |
| **G11** | Mode discipline | ⚠️ partial | `brownfield-change`: no paragraph mixes as-is and to-be; L3.8 present. `greenfield`: no present-tense description of unbuilt behavior |
| **G12** | ADR externality | ✅ full | Every trade-off row cites an existing ADR file; no decision rationale exists only inside the HLD body |

**G1 is the gate that replaces v3's uncheckable −10 penalty** for "speculative
features masquerading as existing code." It only works because of the provenance
format in `-01` §5.

---

## 6. Validator (`limen`)

The automatable gates are worth nothing as prose. They need a binary.

**Implementation:** `tools/limen/` — all twelve gates are implemented. Most
checks are fully deterministic; four are necessarily heuristic and therefore warn
by default and fail under `--strict`: G3's fuzzy name band, G6's quantity-without-
tag scan, G7's tense check, and G11's tense check. Every gate's deterministic
checks always fail. See `tools/limen/README.md`.

### 6.1 Interface

```
limen [--docs docs/architecture] [--repo .] [--at HEAD]
         [--format json|text|sarif] [--gates G1,G2,...] [--strict]
```

| Flag | Behavior |
| :--- | :--- |
| `--at HEAD` | Re-resolve provenance at a commit other than `repo.commit` — this is the **drift check** (`-01` §7.2) |
| `--gates` | Run a subset; default is all automatable gates |
| `--strict` | Treat partial gates (G6, G7, G11) as failures rather than warnings |
| `--format sarif` | For code-scanning UIs |

Exit codes: `0` all gates pass · `1` gate failure · `2` validator error ·
`3` drift detected (with `--at` differing from baseline).

### 6.2 Checks

| Check | Gate | Implementation sketch |
| :--- | :--- | :--- |
| Parse front matter | G9 | YAML schema validation against `-02` §2 |
| Resolve provenance | G1 | For each `path@sha::symbol`: confirm blob exists at `sha`; locate symbol via language-appropriate parse (tree-sitter) or, fallback, exact-string search; for quoted literals compare values |
| Drift scan | — | Same as above at `--at`; report per-claim `resolved / moved / missing / value-changed` |
| Render diagrams | G2 | `mmdc` (mermaid-cli) per fenced block; Structurizr CLI for `.dsl` |
| Name consistency | G3 | Extract element names from all diagrams + prose backticks; cluster by normalized form; flag near-duplicates |
| Concern coverage | G4 | Join `concerns.yaml` against `<!-- frames: -->` comments |
| Response measures | G5 | `quality-scenarios.yaml`: assert `response_measure` non-empty and numeric-bearing |
| Tier tagging | G6 | Regex sweep for sentences/rows lacking a tier tag in normative sections |
| Proposal hygiene | G7 | For each `[T3]`: require owner + trigger nearby; flag present-tense verbs |
| Open questions | G8 | Cross-ref `[T0]` ↔ `open-questions.yaml`; assert count > 0 at L0 |
| Block ownership | G10 | Recompute SHA-256 of each `agent:` block; compare to recorded hash |
| ADR externality | G12 | Every `ADR-nnn` referenced resolves to a file with valid MADR front matter |
| Budget arithmetic | — (advisory) | Parse `-02` §14.2 table, assert `Σ downstream ≤ upstream` |

### 6.3 Output

```json
{
  "doc": "HLD-ingest-platform",
  "version": "4.1.0",
  "baseline": "a1b2c3d",
  "evaluated_at": "f4e5d6c",
  "gates": [
    { "id": "G1", "status": "fail", "detail": "Provenance resolution 88% (22/25)",
      "items": [
        { "claim": "L2.1 worker pool size 32",
          "pointer": "internal/worker/pool.go@a1b2c3d::NewPool",
          "result": "value-changed", "was": "32", "now": "64" }
      ]},
    { "id": "G2", "status": "pass" }
  ],
  "drift": { "resolved": 22, "moved": 1, "missing": 0, "value_changed": 2 },
  "summary": { "passed": 10, "failed": 2, "warned": 1 }
}
```

### 6.4 CI integration

```yaml
# .github/workflows/hld.yml
on:
  pull_request:
    paths: ['internal/**', 'db/migrations/**', 'deploy/**', 'docs/architecture/**']
jobs:
  hld:
    steps:
      - run: limen --docs docs/architecture --repo . --at ${{ github.sha }}
        continue-on-error: true       # advisory on code PRs
      - run: limen --docs docs/architecture --repo . --strict
        # blocking on PRs that touch docs/architecture/**
```

Recommended policy: **advisory on code PRs** (drift opens an issue / `Q-nn`),
**blocking on HLD PRs**. Blocking on every code PR turns the standard into a tax
and teams will route around it. This is fitness function `FF-07` in `-02` §15.

---

## 7. Scored categories

Each category below lists **P** presence criteria (≤40% of weight, binary) and
**S** substance criteria (≥60%, scored 0–3). Percentages are of the category's
profile weight.

### C1 — Intake, stakeholders & constraints

- **P** (30%): Mode declared with justification; baseline commit pinned; concern,
  constraint and open-question registers exist with IDs.
- **S1** (25%): Stakeholders cover ≥4 distinct *roles*, not 4 names of developers.
  Concerns are written from the stakeholder's viewpoint as questions they need
  answered — not as system features.
- **S2** (30%): Constraints are sourced and classified; each states the consequence
  of violation and whether it is negotiable. *Vacuity test: a constraint register
  containing only "must be scalable" scores 0.*
- **S3** (15%): Discovery report (brownfield) states coverage honestly, including
  what was sampled rather than inspected, and records source conflicts as `Q-nn`.

### C2 — Problem, scope & non-goals

- **P** (30%): Problem statement, scope matrix, glossary present.
- **S1** (35%): The problem names a **specific, measurable** bottleneck with
  evidence — not a mission statement. *"Uploads over 8 MiB time out at p99
  because the API buffers whole objects in memory (`[T1]` …)"* scores 3;
  *"improve reliability and scalability"* scores 0.
- **S2** (35%): **Non-goals are substantive.** A non-goal that nobody would have
  proposed ("we are not building a social network") scores 0. A non-goal that a
  reasonable reviewer might have argued for ("we are not supporting cross-region
  strong consistency in Phase 1") scores 3. Non-goals are where design docs earn
  their reputation, and this criterion is deliberately hard.

### C3 — Quality attributes & scenarios *(elevated floor: 70%)*

- **P** (25%): Quality tree present with `(importance, difficulty)` pairs;
  ≥5 six-part scenarios; conflict set present.
- **S1** (30%): Every H/H and H/M leaf has a scenario, and every scenario has a
  **quantified response measure** with units and conditions.
- **S2** (30%): The **conflict set is real.** Scenario pairs genuinely in tension,
  with a stated winner and rationale. A conflict set where every attribute wins is
  not a conflict set — score 0.
- **S3** (15%): Scenarios are traced downstream to SLOs (`-02` §16) and fitness
  functions (`-02` §15). Orphan scenarios and ancestor-less SLOs both lose points.

### C4 — Decisions & alternatives *(elevated floor: 70%)*

- **P** (25%): ADRs exist as separate files in MADR form with valid status
  lifecycle; trade-off index in the HLD points at them (G12).
- **S1** (30%): **Alternatives are real.** Each considered option has concrete
  pros *and* cons, and at least one rejected option is genuinely plausible — an
  option no competent engineer would choose is a straw man and scores 0. This is
  the single most-gamed criterion in the rubric; audit it hardest.
- **S2** (25%): Every decision names what it **sacrifices**, in `QA-nn` terms.
  A trade-off with an empty sacrifice column is a preference (`-02` §9).
- **S3** (20%): Consequences are stated, including negative ones, and each ADR has
  a **revisit trigger**. Decisions without expiry conditions become folklore.

### C5 — Topology & decomposition

- **P** (30%): C4 L1 and L2 present; trust boundaries drawn; every diagram has a
  legend and a prose companion.
- **S1** (35%): Decomposition reflects **actual deployment units** (IaC-derived),
  not code-package structure (`-01` D-3). For brownfield, containers map 1:1 to
  deployables and the mapping is provenance-backed.
- **S2** (20%): Diagrams respect the ≤15-element guidance and decompose rather
  than sprawl; no diagram is a boxes-and-arrows restatement of a short list.
- **S3** (15%): Prose companions state what the reader should conclude, and each
  is consistent with what is drawn.

### C6 — Interfaces & contracts

- **P** (30%): Contract catalogue with auth, idempotency, payload limits,
  consumers; versioning policy present.
- **S1** (35%): The catalogue is **complete** — the auditor finds no externally
  reachable route, event, or RPC absent from it. Sample the router and proto files.
- **S2** (20%): Breaking-change definition is explicit and operational, with a
  deprecation window and mechanism.
- **S3** (15%): Event/message schema evolution rules stated, including consumer
  obligations. Where any consumer is an autonomous agent, the contract declares
  schema discovery (and whether it is generated or hand-maintained), structured
  error payloads carrying `expected`/`actual`, and a correction budget. A
  prose-only error contract for an agent consumer scores 0 — it is not
  correctable, only readable.

### C7 — Data, state & consistency

- **P** (25%): ERD; consistency table; state ownership table.
- **S1** (35%): Consistency, delivery semantics, idempotency keys, and ordering
  guarantees are stated **per flow**, not globally. *An ERD with no consistency
  table scores 0 on this criterion regardless of ERD quality.*
- **S2** (25%): **Half-failure analysis** present for every non-atomic flow: what
  the system and the client see when step 1 succeeds and step 2 fails.
- **S3** (15%): Clock assumptions and skew tolerance stated where any logic depends
  on time; shared mutable state identified and recorded as a risk.

### C8 — Security & threat model *(elevated floor: 70%)*

- **P** (25%): Assets, adversaries, assumptions, per-boundary STRIDE tables,
  ≥2 abuse cases.
- **S1** (30%): STRIDE sweep covers **every** trust boundary from the L1.9
  diagram, with all six categories addressed per boundary — including explicit
  "not applicable because…" entries rather than blank cells.
- **S2** (25%): **Residual risk is honest.** Every control names what it does not
  cover, linked to `R-nn`. A threat model with no medium-or-above residual risk was
  not performed — score ≤1.
- **S3** (20%): Security **assumptions** are stated explicitly (what is trusted and
  therefore undefended). An inventory of auth mechanisms with no assumptions
  section scores 0 here — this is precisely the v3 failure mode.

### C9 — Failure modes & resilience

- **P** (30%): Dependency criticality table; timeout/retry budget; degradation
  matrix; blast radius.
- **S1** (30%): Dependencies classified hard vs soft with a stated fallback per
  soft dependency. Every "hard" is justified — an all-hard dependency list means
  no resilience design was attempted.
- **S2** (25%): The **budget arithmetic holds** (`Σ downstream ≤ upstream`) or
  violations are recorded as issues. Retry amplification factor stated.
- **S3** (15%): Degradation matrix has at least one non-trivial partial-availability
  row. An all-❌ matrix is permitted only with an explicit statement that no
  graceful degradation is designed.

### C10 — Operations, SLO & fitness functions

- **P** (25%): SLO table; alert→runbook matrix; fitness function table.
- **S1** (35%): **Fitness function coverage of H-priority attributes.** Scored on
  coverage, not count: every H attribute has a check, a threshold, a place it runs,
  and a consequence on failure.
- **S2** (25%): Every SLO traces to a `QA-nn`; error budgets and burn-rate alerting
  defined; every alert names a runbook and an owner.
- **S3** (15%): At least one fitness function is *holistic* (exercises the system,
  not a unit), and `FF-07` (HLD groundedness) or equivalent is present.

### C11 — Cost, governance & compliance

- **P** (30%): Cost model; data classification; retention; deletion cascade.
- **S1** (35%): Cost expressed as **unit economics** with a scaling projection and
  the identified dominant driver, not a monthly total.
- **S2** (35%): The **deletion cascade is complete** — it reaches backups, logs,
  caches, CDN, and downstream analytics, with latency per step. A cascade that
  stops at the primary database scores 0, because that is the one people believe
  and the one that is wrong.

### C12 — Evolution: migration, debt, roadmap

- **P** (30%): RAID log; technical debt register; roadmap; (migration plan if
  `brownfield-change`).
- **S1** (30%): Migration increments are **independently shippable and
  independently revertible**, with exit criteria and revert expiry dates.
- **S2** (25%): Technical debt records interest (ongoing cost) and principal (cost
  to fix), not just a description. Debt with no cost attached will never be paid.
- **S3** (15%): Roadmap phases have **trigger conditions**, not dates, and name
  their blockers. Dates in an architecture document are wrong within a quarter.

---

## 8. Floors

| Rule | Threshold |
| :--- | :--- |
| Every scored category (weight > 0) | ≥ **50%** of its weight |
| C3 Quality attributes, C4 Decisions, C8 Security | ≥ **70%** of weight |
| All hard gates | Pass |

A floor breach is a **Major** finding and caps the classification at
*Major Revision Required*, whatever the total. This is the fix for v3's
"91/100 with zero security" pathology.

---

## 9. Penalties

Only for things the gates cannot catch — judgment failures, not mechanical ones.

| Penalty | Deduction | Detection |
| :--- | :--- | :--- |
| Generic content: a section that would read identically for a different system in the same domain | −5 each, max −15 | Vacuity test (S-1) |
| Straw-man alternative in an ADR | −5 each, max −10 | Auditor judgment; C4 S1 |
| Contradiction between sections (or between a diagram and its prose) | −5 each | Auditor cross-read |
| Arithmetic error in sizing, budget, or cost | −3 each | Auditor recomputation |
| Produced ungated (`ungated: true`, all levels in one pass without explicit user request) | −10 | Front matter |
| Independence degraded (self-audit in a fresh session) | Top band unavailable | Audit record |

**No penalty is applied for `[T0]` open questions** (Rule S-3). An auditor that
penalizes disclosed uncertainty is training the next agent to fabricate, which is
a worse outcome than any gap it could catch.

---

## 10. Classification

| Score (after floors, gates, penalties) | Classification | Meaning |
| :--- | :--- | :--- |
| 90–100, all gates pass, no floor breach | **Ready for architecture review** | The document is fit to be reviewed by people who can judge the system |
| 75–89 | **Conditional — minor revisions** | Reviewable; named gaps to close during review |
| 50–74 | **Major revision required** | Substantive architectural gaps; review would be premature |
| < 50, or any gate failure, or any floor breach | **Not auditable** | Return to the author with findings |

Note the top band's wording. A rubric can certify that a *document* is reviewable.
It cannot certify that a *system* is production-ready, and a standard that claims
otherwise teaches its users to trust the wrong artifact.

---

## 11. Audit record

Emitted by the auditor as `docs/architecture/audits/<date>-<version>.yaml`.

```yaml
audit:
  doc: HLD-ingest-platform
  doc_version: 4.1.0
  baseline: a1b2c3d
  profile: P2-product-service
  date: 2026-09-15
  auditor: { kind: agent, model: <model-id>, independence: full }

gates:
  G1: { status: fail, detail: "88% resolution (22/25); 2 value-changed" }
  G2: { status: pass }
  # … G3–G12

provenance_sample:
  sampled: 25
  resolved: 22
  moved: 1
  value_changed: 2

falsification_attempts:
  - claim: "L2.4 — metadata and blob writes are not atomic"
    method: "Read internal/ingest/commit.go; traced tx boundary"
    outcome: confirmed
  - claim: "L2.1 — single worker pool of size 32"
    method: "grep NewPool; found second pool in cmd/gc"
    outcome: "REFUTED — second pool size 8 in ingest-gc, undocumented"

scores:
  C1: { weight: 8,  awarded: 7.0 }
  C3: { weight: 12, awarded: 9.5 }
  C8: { weight: 10, awarded: 5.5, floor: 7.0, breach: true }
  # …
  subtotal: 78.5

penalties:
  - { reason: "Straw-man alternative in ADR-014", points: -5 }

final: 73.5
classification: "Major revision required"
blocking_findings:
  - { severity: blocker, id: G1, summary: "Provenance below 95%" }
  - { severity: major, id: C8, summary: "Floor breach: no security assumptions section; TB-2 unswept" }
  - { severity: blocker, id: F2, summary: "Undocumented second worker pool in ingest-gc" }

silence_audit:
  - role: operates
    missing: "No runbook referenced for the pending-backlog alert"
  - role: audits
    missing: "Deletion cascade omits the analytics warehouse"
```

---

## 12. Quick reference

**Author, before presenting:**
`limen --strict` passes · every claim tagged · one baseline commit · every
`[T3]` has owner + trigger · every diagram renders and has prose · decisions are
in ADR files · open questions register is non-empty and honest.

**Auditor, before scoring:**
Fresh context · sample ≥10 provenance pointers · attempt to falsify the three
load-bearing `[T2]` claims · recompute the budgets · run the silence audit per
stakeholder role · never penalize a disclosed `[T0]`.

**Reviewer, reading the audit:**
Check gates before scores, floors before totals, and the falsification section
before anything else. A 92 with a refuted falsification attempt is worth less than
a 78 with three honest open questions.
