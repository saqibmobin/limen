# Engineering Standard: Agent-Authored HLD — Templates & Schemas

**Document Reference:** `STD-LIMEN-02`
**Version:** 5.0.0
**Status:** Canonical
**Supersedes:** `STD-ARCH-HLD-02` v4.0.0 (identical content; renamed to Limen)
**Companions:** `STD-LIMEN-01-Framework.md` (process), `STD-LIMEN-03-Audit.md` (audit)

Every template below is normative in **shape** (columns, required fields, IDs) and
illustrative in **content**. Example rows are marked `<!-- example -->` and must be
deleted from real documents.

Legend for column headers used throughout: `Tier` is the evidence tag from `-01` §4;
`Evidence` is a provenance pointer per `-01` §5.

---

## 1. Mode declaration (L0.1)

```markdown
## L0.1 Mode
<!-- frames: — -->

**Mode:** `brownfield-change`

**Justification:** The system exists at `github.com/acme/ingest@a1b2c3d`; this HLD
covers the addition of multi-region write support. As-is content is confined to
sections marked `[AS-IS]`; to-be content to sections marked `[TO-BE]`.

**Consequences of this mode:**
- L3.8 Migration & decommission is mandatory.
- No paragraph may mix as-is and to-be (`-01` Rule M-1).
- ≥70% of L2 as-is claims must carry resolvable provenance.
```

---

## 2. Front matter schema (L0.2)

Emitted as YAML at the top of the document (or as `00-front-matter.yaml`).
The validator parses this first; an invalid front matter fails gate G9.

```yaml
---
doc: hld
id: HLD-ingest-platform
title: Ingest Platform High-Level Design
version: 4.1.0                    # semver; see -01 §7.3 step 6 for bump rules
status: draft                     # draft | gate-0 | gate-1 | gate-2 | audited | superseded
mode: brownfield-change           # greenfield | brownfield-asis | brownfield-change
level: 2                          # highest level currently written
profile: P2-product-service       # tailoring profile, see -03 §2
ungated: false                    # true if all levels produced in one pass (-03 §9)

repo:
  url: https://github.com/acme/ingest
  commit: a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0   # THE baseline for all [T1]
  short: a1b2c3d
  dirty: false                    # true = working tree had uncommitted changes
  inspected: full                 # full | sampled
  sampling_note: null             # required when inspected: sampled

authors:
  - { name: architecture-agent, kind: agent, model: <model-id> }
  - { name: <human>, kind: human, role: reviewer }

owners:
  document: <team-or-person>
  system: <team>

supersedes:
  version: 4.0.0
  commit: 0f9e8d7

registers:
  concerns: registers/concerns.yaml
  constraints: registers/constraints.yaml
  quality_scenarios: registers/quality-scenarios.yaml
  open_questions: registers/open-questions.yaml
  risks: registers/risks.yaml
  fitness_functions: registers/fitness-functions.yaml

adr_dir: ../adr/

counts:                           # validator cross-checks these against content
  concerns: 9
  constraints: 7
  quality_scenarios: 11
  open_questions: 6
  t3_items: 14

changelog:
  - version: 4.1.0
    date: 2026-09-15
    trigger: provenance-drift
    summary: Re-pinned baseline to a1b2c3d; repaired 12 drifted claims in L2.1, L2.4.
---
```

---

## 3. Stakeholder & concern register (L0.3)

The completeness backbone (ISO/IEC/IEEE 42010). Every `C-nn` must be framed by at
least one section (hard gate G4).

| ID | Stakeholder | Role | Concern | Priority | Framed by |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `C-01` | Platform SRE | Operates | Can I tell which component caused an incident within 5 min? | H | L2.6, L3.3 |
| `C-02` | Tenant admin | Uses | Is my tenant's data isolated from other tenants? | H | L1.7, L2.4, L2.5 |
| `C-03` | Security review | Audits | What crosses a trust boundary unauthenticated? | H | L1.9, L2.5 |
| `C-04` | Finance | Funds | What does a marginal tenant cost per month? | M | L3.4 |
| `C-05` | New engineer | Builds | Where do I add a new ingest format? | M | L2.1, L2.2 |
<!-- example rows — delete -->

YAML form (`registers/concerns.yaml`):

```yaml
- id: C-01
  stakeholder: Platform SRE
  role: operates          # uses | operates | builds | audits | funds | governs
  concern: >
    Determine which component caused an incident within 5 minutes.
  priority: H             # H | M | L
  framed_by: [L2.6, L3.3]
```

**Rule.** Minimum four distinct stakeholder *roles*. A register listing only
"developers" has not been done.

---

## 4. Constraints register (L0.4)

The section v3 omitted entirely. Constraints are what make an architecture
non-obvious.

| ID | Class | Constraint | Source | Tier | Negotiable? | Consequence if violated |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `K-01` | Legal | EU tenant data must not leave eu-west-1 | DPA §7 | `[T1]` | No | Regulatory exposure |
| `K-02` | Technical | Datastore must be Postgres (platform mandate) | Platform RFC-88 | `[T1]` | Hard | Unsupported in prod |
| `K-03` | Organizational | 4 engineers, no dedicated SRE | Team charter | `[T1]` | No | Operability ceiling; see `QA-07` |
| `K-04` | Temporal | Must ship before the Q3 change freeze (2026-09-30) | Program plan | `[T1]` | Soft | Slips to Q1 |
| `K-05` | Commercial | Existing 3-yr Datadog commitment | Procurement | `[T1]` | Soft | Dual-vendor cost |
<!-- example rows — delete -->

Classes: `legal`, `regulatory`, `technical`, `organizational`, `commercial`,
`temporal`, `operational`.

**Rule.** A constraint that cannot be sourced is a `Q-nn`, not a constraint.
Inventing constraints is as damaging as ignoring them.

---

## 5. Open questions register (L0.6, maintained throughout)

Every `[T0]` in the document points here.

| ID | Question | Why it matters | Blocks | Owner | Resolution path | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `Q-01` | Is the 24 MiB part limit a protocol constraint or a tuned value? | Determines whether L1.6 sizing can be relaxed | L1.6, L2.2 | @ingest-lead | Ask original author / check git blame | open |
| `Q-02` | README says Redis, IaC provisions Memcached — which is live? | Affects L2.6 failure analysis | L2.1, L2.6 | @platform | Inspect running config | open |
<!-- example rows — delete -->

```yaml
- id: Q-01
  question: Is the 24 MiB part limit a protocol constraint or a tuned value?
  matters_because: Determines whether L1.6 sizing bounds can be relaxed.
  blocks: [L1.6, L2.2]
  owner: "@ingest-lead"
  resolution_path: git blame internal/ingest/limits.go; ask original author
  status: open           # open | answered | wont-resolve
  answer: null
  answered_at: null
```

**Rule.** An L0 with zero open questions is a signal the agent is guessing
(`-03` G8). Healthy range: 5–20 at L0, declining across gates.

---

## 6. Discovery report (L0.7, brownfield only)

```markdown
## L0.7 Discovery Report
<!-- frames: — -->

**Baseline:** `a1b2c3d` · **Coverage:** sampled (see below)

| # | Source | What was found | Provenance | Tier |
| :--- | :--- | :--- | :--- | :--- |
| 1 | Build manifests | Go 1.23; 41 direct deps; Postgres via pgx, S3 via aws-sdk-go-v2; **no Redis client** despite README | `go.mod@a1b2c3d` | `[T1]` |
| 2 | IaC / CI | 3 deployables: `ingest-api`, `ingest-worker`, `ingest-gc`. Single region eu-west-1. | `deploy/terraform/main.tf@a1b2c3d` | `[T1]` |
| 3 | Config schema | 24 env vars; 6 are cross-service endpoints → coupling surface | `internal/config/config.go@a1b2c3d::Config` | `[T1]` |
| 4 | Data layer | 42 migrations; 11 tables; `tenant_id` on 9 of 11 | `db/migrations/@a1b2c3d` | `[T1]` |
| 5 | Entrypoints | `cmd/api/main.go`, `cmd/worker/main.go`, `cmd/gc/main.go` | `cmd/@a1b2c3d` | `[T1]` |
| 6 | Async work | 1 worker pool (size 32), 1 cron (GC, hourly) | `internal/worker/pool.go@a1b2c3d::NewPool` | `[T1]` |
| 7 | AuthN/Z | OIDC at edge; internal calls unauthenticated → see `C-03` | `internal/auth/oidc.go@a1b2c3d` | `[T1]` |
| 8 | git log hot spots | `internal/ingest/` = 38% of commits in 90d → design under stress | `git log --since=90.days` | `[T1]` |
| 9 | CODEOWNERS | 2 teams: `@ingest`, `@platform` | `CODEOWNERS@a1b2c3d` | `[T1]` |
| 10 | Existing docs | 3 ADRs found; ADR-002 (single-region) directly relevant | `docs/adr/@a1b2c3d` | `[T1]` |

**Coverage statement:** All of `cmd/`, `internal/`, `db/`, `deploy/` inspected.
`pkg/legacy/` (14k LOC, no inbound references found) sampled only — see `Q-05`.

**Conflicts raised:** `Q-02` (Redis vs Memcached, sources 1 vs 10).
```

---

## 7. Quality tree & QA scenarios (L1.4)

### 7.1 Quality tree

Attributes → refinements, each with an ATAM priority pair
`(business importance, architectural difficulty)`.

```markdown
- **Availability**
  - Ingest accepts writes during a single-AZ failure — (H, H) → `QA-01`
  - Read path survives object-store degradation — (H, M) → `QA-02`
- **Performance**
  - p95 upload-ack latency under peak — (H, M) → `QA-03`
  - GC does not contend with the write path — (M, M) → `QA-04`
- **Security**
  - Tenant isolation under a compromised tenant credential — (H, H) → `QA-05`
- **Operability**
  - MTTI (mean time to identify) with 4 engineers and no SRE — (H, H) → `QA-07`
- **Modifiability**
  - New ingest format added without touching the transport layer — (M, L) → `QA-08`
- **Cost-efficiency**
  - Marginal cost per tenant stays sublinear — (M, M) → `QA-09`
```

Scenarios are required for every `(H, H)` and `(H, M)` leaf.

### 7.2 Six-part scenario (SEI)

| Field | `QA-03` |
| :--- | :--- |
| **ID** | `QA-03` |
| **Attribute** | Performance / latency |
| **Priority** | (H, M) |
| **Source of stimulus** | Authenticated tenant client |
| **Stimulus** | Submits a 24 MiB multipart upload |
| **Artifact** | `ingest-api` write path |
| **Environment** | Peak load (2× median), normal operation, single region |
| **Response** | Upload acknowledged and durably committed to object storage |
| **Response measure** | **p95 ≤ 250 ms, p99 ≤ 900 ms, error rate < 0.1%** |
| **Derived SLO** | `SLO-02` (L3.1) |
| **Fitness function** | `FF-03` (L3.2) |
| **Traded against** | `QA-09` (cost) — see `ADR-011` |
| Tier | `[T2]` derived from `QA` workshop + `[T1]` current p95 = 310 ms (`internal/metrics/…`) |
<!-- example — delete -->

```yaml
- id: QA-03
  attribute: performance.latency
  priority: { importance: H, difficulty: M }
  source: Authenticated tenant client
  stimulus: Submits a 24 MiB multipart upload
  artifact: ingest-api write path
  environment: Peak load (2x median), normal operation, single region
  response: Upload acknowledged and durably committed to object storage
  response_measure:
    p95_ms: 250
    p99_ms: 900
    error_rate_max: 0.001
  derived_slo: SLO-02
  fitness_function: FF-03
  traded_against: [QA-09]
  adr: ADR-011
```

**Rule.** No `response_measure` → hard gate G5 fails. "Fast" and "highly
available" are not response measures.

### 7.3 Conflict set (mandatory)

The input to every trade-off in the document.

| Pair | Tension | Winner | Rationale | ADR |
| :--- | :--- | :--- | :--- | :--- |
| `QA-01` vs `QA-09` | Multi-AZ write quorum raises cost ~40% | `QA-01` | `K-01` regulatory availability floor | `ADR-009` |
| `QA-03` vs `QA-05` | Per-request tenant key derivation adds ~18 ms | `QA-05` | Isolation is non-negotiable; latency budget absorbs it | `ADR-011` |
| `QA-07` vs `QA-08` | Plugin extensibility increases operational surface for a 4-person team | `QA-07` | `K-03` | `ADR-014` |
<!-- example — delete -->

---

## 8. Architecture Decision Record (MADR)

One decision per file: `docs/adr/ADR-011-per-request-key-derivation.md`.
ADRs are **append-only**; a reversal is a new ADR, not an edit.

```markdown
---
id: ADR-011
title: Derive tenant data keys per request rather than per session
status: accepted          # proposed | accepted | rejected | deprecated | superseded
date: 2026-07-14
deciders: [@ingest-lead, @security]
consulted: [@platform]
informed: [@sre]
supersedes: null
superseded_by: null
optimizes_for: [QA-05]
sacrifices: [QA-03]
constraints: [K-01]
affects_sections: [L2.4, L2.5]
---

# ADR-011 — Derive tenant data keys per request rather than per session

## Context and problem statement

Tenant payloads are encrypted with per-tenant DEKs. Caching a derived DEK for the
lifetime of a session reduces latency but widens the window in which a compromised
process holds plaintext key material for multiple tenants. `QA-05` requires
isolation to hold under a compromised tenant credential.

## Decision drivers

- `QA-05` tenant isolation under credential compromise — (H, H)
- `QA-03` p95 upload-ack ≤ 250 ms
- `K-01` EU data residency; KMS calls must stay in-region
- Operability: 4-person team, `K-03` — no bespoke key cache to run

## Considered options

### Option A — Per-request derivation (chosen)
- **Pros:** Key material lifetime ≈ request lifetime; no cross-tenant key
  residency in process memory; no cache to invalidate or operate.
- **Cons:** +18 ms p95 (measured, `bench/key_test.go@a1b2c3d::BenchmarkDerive`);
  KMS request volume ×~40; +$310/mo at current volume.

### Option B — Per-session cached DEK with TTL
- **Pros:** Near-zero added latency; low KMS cost.
- **Cons:** Multi-tenant key material co-resident in process memory; TTL tuning is
  a security/latency knob nobody will revisit; cache invalidation on tenant
  offboarding is a correctness burden on a 4-person team.

### Option C — Envelope encryption with per-request KEK, cached DEK
- **Pros:** Middle ground; bounded exposure.
- **Cons:** Two key hierarchies to reason about; the complexity is real and the
  exposure reduction over A is marginal.

## Decision outcome

Chosen: **Option A**. `QA-05` is a (H, H) attribute and the only one whose failure
is unrecoverable — a leaked cross-tenant key cannot be un-leaked, whereas 18 ms of
p95 can be recovered elsewhere (see `ADR-013`, connection pooling). `K-03` weighs
against options that add operational surface.

## Consequences

- **Positive:** Key material lifetime bounded by request; offboarding needs no
  cache invalidation; audit story is a single sentence.
- **Negative:** p95 budget in `QA-03` consumes 18 ms of its 250 ms; KMS becomes a
  hard dependency on the write path — recorded as `R-07` and reflected in the
  dependency criticality table (L2.6).
- **Revisit trigger:** if KMS p99 exceeds 25 ms, or write QPS exceeds 4k
  (KMS account limit), re-open with Option C.
```

### 8.3 Y-statement (compressed form, minor decisions)

> In the context of **the GC worker**, facing **unbounded delete fan-out on large
> tenants**, we decided for **batched deletes with a 5k-row ceiling per tick** and
> against **single-transaction cascade**, to achieve **bounded lock duration
> (`QA-04`)**, accepting **eventual consistency of the deletion cascade up to
> 30 min (`R-11`, disclosed in L3.5)**.

---

## 9. Trade-off index (L1.10)

The HLD does not restate decisions; it indexes them (`-01` Rule A-1).

| Dimension | Chosen | Rejected | Optimizes | Sacrifices | ADR | Tier |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Key lifetime | Per-request derivation | Per-session cache; envelope+cache | `QA-05` | `QA-03` (−18 ms) | `ADR-011` | `[T1]` |
| Write durability | Multi-AZ quorum | Single-AZ + async replica | `QA-01` | `QA-09` (+40% cost) | `ADR-009` | `[T1]` |
| Extensibility | Compiled-in format registry | Plugin runtime | `QA-07` | `QA-08` | `ADR-014` | `[T1]` |
<!-- example — delete -->

**Rule.** Every row names at least one sacrificed `QA-nn`. A row with an empty
`Sacrifices` column describes a preference, not a trade-off, and the audit
penalizes it (`-03` C4).

---

## 10. Sizing and capacity (L1.6)

Show the arithmetic. A result without a derivation cannot be reviewed or
recomputed when an input changes.

```markdown
### L1.6 Back-of-envelope sizing

**Inputs** (state tier and source for each):
- Tenants: 1,200 today, 3,000 at 18-month plan `[T2]` (product plan)
- Uploads/tenant/day: 140 median, 2,400 p99 `[T1]` (`analytics: uploads_daily`)
- Median object: 3.1 MiB; p99: 24 MiB (protocol ceiling) `[T1]`
  (`internal/ingest/limits.go@a1b2c3d::MaxPartBytes` = 25165824)

**Derivations:**

Writes/day   = 1,200 × 140                      ≈ 168,000/day
Mean QPS     = 168,000 / 86,400                 ≈ 1.9 QPS
Peak QPS     = mean × 12 (diurnal, measured)    ≈ 23 QPS  [T1]
Ingest bytes = 168,000 × 3.1 MiB                ≈ 521 GiB/day
Peak bandwidth = 23 × 3.1 MiB                   ≈ 71 MiB/s ≈ 570 Mbps
Storage/yr (no lifecycle) = 521 GiB × 365       ≈ 186 TiB/yr
Storage/yr (90-day lifecycle to IA)             ≈ 46 TiB hot + 140 TiB IA

**Bounds established:**
| Bound | Value | Basis | Tier |
| :--- | :--- | :--- | :--- |
| Peak write QPS (design to) | 50 QPS (2× headroom) | derivation above | `[T2]` |
| Max object size | 24 MiB | protocol ceiling | `[T1]` |
| Worker pool size | 32 | `internal/worker/pool.go@a1b2c3d::NewPool` | `[T1]` |
| Connection pool | 25/instance × 3 = 75 vs Postgres `max_connections` 200 | `deploy/terraform/rds.tf@a1b2c3d` | `[T1]` |
| Long-poll timeout | 30 s | `internal/api/poll.go@a1b2c3d::pollTimeout` | `[T1]` |

**Headroom check:** 75 of 200 connections at 3 instances → ceiling at 8
instances. Records as `R-04`.
```

---

## 11. Interface & contract catalogue (L2.2)

| ID | Contract | Kind | Consumers | Auth | Idempotent | Payload limit | Provenance | Tier |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `I-01` | `POST /v1/uploads` | REST | tenant SDK, web | OIDC | Yes (`Idempotency-Key`) | 24 MiB/part | `internal/api/upload.go@a1b2c3d::handleUpload` | `[T1]` |
| `I-02` | `GET /v1/uploads/{id}` | REST | tenant SDK | OIDC | n/a | — | `internal/api/get.go@a1b2c3d::handleGet` | `[T1]` |
| `I-03` | `ingest.completed` | Event (SNS) | billing, search | IAM | At-least-once | 256 KiB | `internal/events/publish.go@a1b2c3d::Publish` | `[T1]` |
| `I-04` | `ingest.Worker/Claim` | gRPC (internal) | ingest-worker | **none** → `C-03` | Yes | — | `proto/worker.proto@a1b2c3d` | `[T1]` |
<!-- example — delete -->

### 11.1 Compatibility & versioning policy (L2.3)

| Aspect | Policy | Tier |
| :--- | :--- | :--- |
| REST versioning | URI major version (`/v1/`); additive changes only within a major | `[T1]` |
| Breaking change definition | Removing a field, narrowing a type, adding a required request field, changing an error code class | `[T2]` |
| Deprecation window | 2 majors or 180 days, whichever is longer; `Deprecation` + `Sunset` headers | `[T3]` Proposed — owner @ingest-lead, trigger: first external SDK consumer |
| Event schema evolution | Backward-compatible only; consumers must ignore unknown fields; schema registry with compatibility mode `BACKWARD` | `[T1]` |
| Internal gRPC | No compatibility guarantee; deployed lockstep | `[T1]` |

### 11.2 Agent-facing contracts (L2.2)

Required whenever a contract's consumer is an autonomous agent rather than a
human-written client. Three properties become load-bearing, because an agent
cannot read your documentation at 3 a.m. and cannot infer intent from a bare 400:

| ID | Contract | Consumer class | Schema discovery | Error payload | Correction budget | Tier |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `I-01` | `POST /v1/uploads` | both | OpenAPI at `/v1/openapi.json`, **generated from handlers** | structured (below) | 3 attempts, then fail closed | `[T1]` |
| `I-04` | `ingest.Worker/Claim` | agent | protobuf reflection → JSON Schema, **generated** | structured | 1 | `[T1]` |
| `I-05` | `ingest` tool set | agent | MCP tool listing, **hand-maintained** → drifts, `R-14` | prose only → `R-15` | none declared | `[T1]` |
<!-- example — delete -->

**1. Schema discovery.** How the consumer obtains the contract at runtime, and
whether it is *generated from the implementation* (cannot drift) or
*hand-maintained* (will drift). Record which. A hand-maintained schema for an
agent consumer is a `R-nn`, not a footnote.

**2. Structured error payloads.** Errors must be machine-actionable. Prose-only
errors force the agent to guess, and it will guess wrong repeatedly:

```json
{
  "code": "PART_TOO_LARGE",
  "path": "parts[2].bytes",
  "reason": "part exceeds the protocol ceiling",
  "expected": "<= 25165824",
  "actual": 41943040,
  "retryable": false,
  "retry_after_ms": null
}
```

Minimum fields: `code` (stable, enumerable), `path` (which input), `reason`,
`expected`, `actual`, `retryable`. `expected`/`actual` are what make the error
correctable rather than merely informative.

**3. Correction budget.** How many correction attempts the contract expects
before the consumer should stop, and whether failed attempts are idempotent. An
agent looping on an uncorrectable error is a denial-of-service you built
yourself — cross-reference the retry-amplification analysis in §14.2.

**Headless credential acquisition.** Agent and CLI consumers cannot complete a
browser redirect. State how they obtain credentials — RFC 8628 device
authorization flow, workload identity federation, or issued service credentials —
and carry the choice into the `TB-n` STRIDE sweep in §13.2, since a long-lived
agent credential has a different compromise profile (`A-6`) than a user session.

**Rule.** A contract with an autonomous-agent consumer whose errors are
prose-only, or whose schema is hand-maintained with no drift control, is a
finding in C6 (`STD-LIMEN-03` §7). Record it as a risk rather than omitting it.

---

## 12. Data, state and consistency (L2.4)

### 12.1 ERD

Standard Mermaid `erDiagram` with PKs, FKs, cardinalities. Rules `-01` §9 apply.

### 12.2 Consistency semantics (the part an ERD cannot express)

| Flow | Consistency | Window | Transaction boundary | Delivery | Idempotency key | Ordering | Tier |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Upload → metadata row | Strong (single tx) | — | row + part rows commit atomically | — | `Idempotency-Key` header | — | `[T1]` |
| Metadata → object store | **Eventual** | ≤ 30 s | **Not atomic** — row commits before blob | — | object key = `{tenant}/{upload_id}` | — | `[T1]` |
| Upload → `ingest.completed` | Eventual | ≤ 5 s | outbox table, polled | At-least-once | `upload_id` | Per-tenant only | `[T1]` |
| Delete → blob GC | Eventual | ≤ 30 min | — | At-least-once | `upload_id` | None | `[T1]` |
<!-- example — delete -->

**Half-failure analysis (mandatory for every non-atomic row above):**

> Metadata row commits, blob write fails: the row is marked `pending` and the GC
> sweep reclaims rows in `pending` older than 1 h `[T1]`
> (`internal/gc/sweep.go@a1b2c3d::sweepPending`). A client polling `GET /v1/uploads/{id}`
> during the window sees `status: pending`, never a 404 and never a dangling
> `complete` `[T1]`.

### 12.3 Clock assumptions

| Assumption | Where it matters | Skew tolerance | Failure if violated | Tier |
| :--- | :--- | :--- | :--- | :--- |
| Node clocks within 500 ms (NTP) | `pending` TTL sweep | 1 h TTL ≫ skew, safe | — | `[T1]` |
| Token `exp` evaluated against node clock | OIDC validation | 60 s leeway configured | Early/late rejection | `[T1]` |
<!-- example — delete -->

### 12.4 State ownership

| State | Owning component | Other readers | Other writers |
| :--- | :--- | :--- | :--- |
| `uploads` table | `ingest-api` | `ingest-worker`, `ingest-gc` | **`ingest-gc`** → shared mutable state, `R-09` |

**Rule.** Exactly one component owns each piece of state. A second writer is a
finding, not a design — record it as a risk.

---

## 13. Threat model (L2.5)

### 13.1 Assets, adversaries, assumptions

```markdown
**Assets:** tenant payload bytes (Restricted/PII), tenant DEKs, OIDC client
secret, object-store credentials, ingest availability.

**Adversaries:**
| ID | Adversary | Capability | In scope |
| :--- | :--- | :--- | :--- |
| `A-1` | External unauthenticated | Network reach to edge only | Yes |
| `A-2` | Authenticated tenant | Valid credential, arbitrary payloads | Yes |
| `A-3` | Compromised tenant credential | As `A-2` plus intent | Yes |
| `A-4` | Malicious insider (eng) | Prod read access | Partial — see `Q-06` |
| `A-5` | Compromised dependency | Code execution in-process | Yes |
| `A-6` | Compromised CI / agent credential | Deploy capability | Yes |

**Security assumptions (trusted, therefore undefended):**
- Cloud KMS is trusted; its compromise is out of scope. `[T2]`
- The container base image supply chain is verified by platform. `[T2]` — see `Q-07`
- Physical and hypervisor security is the provider's. `[T2]`
```

**Rule.** Unstated assumptions are the ones that fail. A threat model with no
assumptions section is incomplete.

### 13.2 STRIDE sweep per trust boundary

One table per trust boundary drawn on L1.9.

**Boundary `TB-1`: Internet → edge (ingest-api)**

| STRIDE | Threat | Existing control | Provenance | Residual | Risk |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **S**poofing | Forged tenant identity | OIDC, JWKS rotation, `aud` + `iss` checked | `internal/auth/oidc.go@a1b2c3d::Verify` | Low | — |
| **T**ampering | Payload mutated in transit | TLS 1.3 terminate at ALB; part checksums | `deploy/terraform/alb.tf@a1b2c3d` | Low | — |
| **R**epudiation | Tenant denies an upload | Structured audit log with `sub`, `upload_id`; 400-day retention | `internal/audit/log.go@a1b2c3d` | Low | — |
| **I**nfo disclosure | Cross-tenant read via ID guess | `tenant_id` predicate enforced in repo layer + RLS | `internal/repo/upload.go@a1b2c3d::scopeTenant` | **Medium** — RLS not on 2 of 11 tables | `R-03` |
| **D**oS | Large-payload flood | 24 MiB part cap; per-tenant rate limit 50 rps | `internal/api/ratelimit.go@a1b2c3d` | Medium — **no global cap** | `R-05` |
| **E**oP | Tenant → admin scope | Scopes checked per handler | `internal/auth/scope.go@a1b2c3d` | Low | — |
<!-- example — delete -->

**Boundary `TB-2`: edge → internal gRPC** — *(gate: `I-04` is unauthenticated,
`C-03`, `R-01`)* … one table per boundary.

### 13.3 Abuse cases

≥2 narrative misuse flows, diagrammed as sequence diagrams with the adversary as
an actor. Example headings: *"A-3 replays a captured idempotency key to overwrite
another tenant's upload"*, *"A-5 exfiltrates DEKs via a dependency post-install hook"*.

---

## 14. Failure domains & degradation (L2.6)

### 14.1 Dependency criticality

| Dependency | Class | On failure | Timeout | Retry | Fallback | Tier |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Postgres (primary) | **Hard** | Writes fail, reads fail | 3 s | 2, exp backoff + jitter | None — fail fast 503 | `[T1]` |
| Object store | **Hard** (write path) | Uploads fail after metadata commit | 10 s | 3, backoff | Row stays `pending`, GC reclaims | `[T1]` |
| KMS | **Hard** (write path) | All writes fail | 2 s | 1 | None | `[T1]` `ADR-011` |
| SNS | Soft | Events lost | 2 s | 3 | Outbox retains, drains on recovery | `[T1]` |
| Datadog | Soft | Blind, not down | 1 s | 0 | Local buffer, 5 min | `[T1]` |
<!-- example — delete -->

### 14.2 Timeout & retry budget

**Rule.** `Σ(downstream timeout × (retries+1)) < upstream timeout`. Violations are
a finding — they guarantee that the caller gives up while the callee is still
working, converting a slow dependency into a retry storm.

| Hop | Timeout | Retries | Worst case | Running total | Budget |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Client → ALB | 60 s | 0 | 60 s | — | — |
| ALB → api | 30 s | 0 | 30 s | 30 s | ✅ < 60 s |
| api → KMS | 2 s | 1 | 4 s | 4 s | |
| api → Postgres | 3 s | 2 | 9 s | 13 s | |
| api → object store | 10 s | 3 | 40 s | **53 s** | ❌ **> 30 s ALB timeout** → `R-06` |

Include **retry amplification**: 3 retries at each of 3 layers = up to 64× load
on the deepest dependency. State the amplification factor explicitly.

### 14.3 Degradation matrix

Columns are capabilities; rows are failure conditions. This is what operators read
at 3 a.m.

| Failure | Upload | Read | Events | Delete | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Object store down | ❌ | ⚠️ cached only | ✅ | ⚠️ queued | `pending` rows accumulate |
| Postgres primary down | ❌ | ❌ | ⚠️ outbox stalls | ❌ | Full outage |
| Postgres replica down | ✅ | ⚠️ falls to primary | ✅ | ✅ | Primary load +40% |
| KMS down | ❌ | ✅ (cached plaintext? **no**) | ✅ | ✅ | `ADR-011` consequence |
| SNS down | ✅ | ✅ | ⚠️ delayed | ✅ | Outbox drains on recovery |
| Worker pool saturated | ⚠️ queued | ✅ | ⚠️ delayed | ⚠️ delayed | Backpressure at 32 |
<!-- example — delete -->

**Rule.** A system with no documented degraded mode has exactly one mode: down.
An all-❌ column means no graceful degradation was designed — say so explicitly
rather than leaving it implicit.

### 14.4 Blast radius

| Failure domain | Scope | Tenants affected | Recovery |
| :--- | :--- | :--- | :--- |
| Single api instance | 1/3 of capacity | 0 (LB drains) | Auto, < 60 s |
| AZ | Full write path (single-AZ RDS) | **All** | Manual failover, ~8 min → `R-02` |
| Region | Everything | All | None — `ADR-009` accepts this |

---

## 15. Fitness functions (L3.2)

| ID | Characteristic | `QA` | Check | Where | Threshold | On failure | Kind |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `FF-01` | Tenant isolation | `QA-05` | Integration test: tenant A token cannot read tenant B row across all 11 tables | CI (per PR) | 0 leaks | Block merge | triggered, atomic |
| `FF-02` | Availability | `QA-01` | Chaos: kill AZ in staging, assert write success | Nightly | ≥ 99.5% during 10 min | Page + block release | triggered, holistic |
| `FF-03` | Latency | `QA-03` | Load test at 50 QPS with 24 MiB objects | CI (nightly) | p95 ≤ 250 ms | Block release | triggered, holistic |
| `FF-04` | Modifiability | `QA-08` | Dependency rule: `internal/format/**` must not import `internal/transport/**` | CI (per PR) | 0 violations | Block merge | triggered, atomic |
| `FF-05` | Operability | `QA-07` | Every alert rule has a `runbook_url` label | CI | 100% | Block merge | triggered, atomic |
| `FF-06` | Cost | `QA-09` | Cost-per-tenant from billing export | Monthly | ≤ $2.40 | Ticket + review | continual, holistic |
| `FF-07` | Groundedness | — | HLD provenance re-resolution at HEAD | CI (per PR touching `internal/`) | 0 unresolvable | Warn + open `Q` | continual, atomic |
<!-- example — delete -->

```yaml
- id: FF-01
  characteristic: security.tenant-isolation
  quality_scenario: QA-05
  check: Integration test — tenant A token must not read tenant B rows (all tables)
  where: ci-pr
  threshold: "0 cross-tenant reads"
  on_failure: block-merge
  kind: { cadence: triggered, scope: atomic }
  implemented_at: test/isolation_test.go@a1b2c3d::TestCrossTenantDenied
```

**Rule F-1 (from `-01`).** An H-priority quality attribute with no fitness
function and no stated reason for the absence is unenforced. Coverage of
H-priority attributes is what L3.2 is scored on — not the number of functions.

`FF-07` is recommended for every project: it is the framework validating itself.

---

## 16. SLO / SLI (L3.1)

| ID | SLI | Target | Window | Error budget | Derived from | Alert | Runbook |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `SLO-01` | Upload success rate | 99.9% | 30 d rolling | 43 min | `QA-01` | burn-rate 14.4×/1h | `RB-01` |
| `SLO-02` | Upload-ack p95 | ≤ 250 ms | 30 d rolling | — | `QA-03` | p95 > 250 ms for 10 min | `RB-02` |
<!-- example — delete -->

**Rule.** Every SLO cites the `QA-nn` it derives from (`-01` Rule Q-2). An SLO
invented at L3 with no L1 ancestor is measuring something nobody prioritized.

---

## 17. Alert → runbook matrix (L3.3)

| Alert | Condition | Severity | Owner | Runbook | First action | Auto-remediation |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `SLO-01` fast burn | 14.4× for 1 h | P1 page | `@ingest` | `RB-01` | Check object-store health dashboard | None |
| `pending` backlog | > 500 rows > 1 h | P2 ticket | `@ingest` | `RB-04` | Run `gc sweep --force` | Hourly sweep |
<!-- example — delete -->

**Rule.** Every alert names a runbook and an owner (`FF-05` enforces this).
An alert with no runbook is a notification, and it will be muted within a quarter.

---

## 18. Cost model (L3.4)

Report **unit economics**, not only monthly totals — a total tells you nothing
about whether growth is affordable.

| Component | Driver | Unit | Rate | Monthly @ 1,200 tenants | @ 3,000 | Tier |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| RDS (Multi-AZ) | provisioned | instance | $0.68/h | $992 | $1,984 (scale step) | `[T1]` pricing, `[T2]` projection |
| Object storage | GiB-month | GiB | $0.023 | $1,070 | $2,675 | `[T2]` |
| Egress | GiB | GiB | $0.09 | $430 | $1,075 | `[T2]` |
| KMS | requests | 10k req | $0.03 | $310 | $775 | `[T1]` `ADR-011` consequence |
| **Total** | | | | **$2,802** | **$6,509** | |
| **Cost per tenant** | | | | **$2.34** | **$2.17** | sublinear ✅ `QA-09` |

Include: the dominant cost driver, the term at which it changes (scale steps), and
the optimization levers not yet pulled (lifecycle policy, compression, cache
headers) with their estimated savings — as `[T3]` with owners.

---

## 19. Data governance (L3.5)

### 19.1 Classification

| Data | Class | Residency | Retention | Encryption | Tier |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Payload bytes | Restricted (may contain PII) | eu-west-1 only (`K-01`) | 90 d hot, 400 d IA | AES-256-GCM, per-tenant DEK | `[T1]` |
| Upload metadata | Confidential | eu-west-1 | 400 d | At rest (RDS) | `[T1]` |
| Audit log | Confidential | eu-west-1 | 400 d (immutable) | At rest | `[T1]` |
| Telemetry | Internal | us-east-1 ⚠️ | 15 d | Vendor-managed | `[T1]` — **residency conflict with `K-01`** → `R-08` |

### 19.2 Deletion cascade

The section most often stated and least often traced. Every store must appear.

| Step | Store | Mechanism | Latency | Verified by | Tier |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | `uploads` row | soft-delete `deleted_at` | immediate | `FF-08` | `[T1]` |
| 2 | Child `parts` rows | FK cascade | immediate | migration `0031` | `[T1]` |
| 3 | Object storage blobs | GC sweep | ≤ 30 min | `FF-08` | `[T1]` |
| 4 | CDN / edge cache | purge API call | ≤ 5 min | — | `[T3]` **Proposed — not implemented**, owner @platform, `R-12` |
| 5 | Search index | tombstone event | ≤ 5 min | consumer contract | `[T1]` |
| 6 | **Backups** | expire with snapshot rotation | **≤ 35 d** | — | `[T1]` — disclose to DPO |
| 7 | **Application logs** | log retention expiry | ≤ 15 d | — | `[T1]` |
| 8 | **Analytics warehouse** | scheduled purge job | ≤ 24 h | — | `[T2]` → `Q-09` |

**Rule.** Backups, logs, caches, and downstream analytics are part of the cascade.
A deletion story that stops at the primary database is not a deletion story.

---

## 20. Migration & decommission (L3.8, `brownfield-change` only)

### 20.1 Delta table

| As-is | To-be | Class | Sections affected | Revertible |
| :--- | :--- | :--- | :--- | :--- |
| `ingest-api` (single region) | `ingest-api` (2 regions, active/active) | modified | L1.9, L2.1, L2.4 | Yes, per-increment |
| — | `region-router` | **new** | L1.9, L2.2 | Yes |
| `ingest-gc` (hourly cron) | `ingest-gc` (per-region) | modified | L2.1 | Yes |
| `pkg/legacy/replicator` | — | **removed** | L2.1 | No, after step 6 |

### 20.2 Increment sequencing (strangler fig)

| # | Increment | Ships independently | Revert path | Revert expires | Exit criterion |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | Add `region` column, nullable, backfill `eu-west-1` | Yes | Drop column | 30 d | 100% rows populated |
| 2 | Deploy `region-router` in shadow mode | Yes | Disable flag | 14 d | Shadow diff < 0.01% |
| 3 | Dual-write to eu-central-1 | Yes | Disable flag | 14 d | Reconciliation clean 7 d |
| 4 | Read from nearest region (5% → 100%) | Yes | Ramp to 0% | 7 d | `SLO-02` held at each step |
| 5 | Promote eu-central-1 to accept writes | Yes | Route all to eu-west | 7 d | `FF-02` passes both regions |
| 6 | Decommission `pkg/legacy/replicator` | — | **None** | — | Zero traffic 30 d |

### 20.3 Data migration

State the dual-write window, backfill strategy and throughput, the reconciliation
check (what query proves both sides agree), cutover criteria, and what happens to
in-flight writes during cutover.

---

## 21. RAID log (L3.9)

Decisions deliberately excluded — they live in ADRs (`-01` Rule A-1).

| ID | Type | Description | Likelihood | Impact | Owner | Mitigation | Trigger to escalate | Tier |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `R-01` | Risk | Internal gRPC unauthenticated (`I-04`); lateral movement from any pod | M | H | @security | mTLS via mesh | Any new workload in namespace | `[T1]` |
| `R-02` | Risk | Single-AZ RDS; ~8 min manual failover | M | H | @platform | Multi-AZ (`ADR-009`) | First AZ event | `[T1]` |
| `R-06` | Issue | Object-store worst-case 53 s exceeds ALB 30 s timeout | H | M | @ingest | Reduce retries to 1 | Now — open | `[T1]` |
| `A-01` | Assumption | Peak is 12× mean (measured over 90 d) | — | H if wrong | @ingest | Re-measure quarterly | Traffic mix change | `[T2]` |
| `D-01` | Dependency | Platform mesh rollout Q4 blocks `R-01` mitigation | — | H | @platform | Track | Slip past Q4 | `[T1]` |

Types: `R` Risk, `I` Issue, `A` Assumption, `D` Dependency.

### 21.1 Technical debt register

| ID | Debt | Incurred by | Interest (ongoing cost) | Principal (cost to fix) | Pay-down trigger |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `TD-01` | RLS missing on 2 of 11 tables | Schema predates RLS policy | Manual review on every PR touching repo layer | ~3 d | Before next tenant tier |

---

## 22. Roadmap (L3.10)

Phases with **trigger conditions**, not dates. Dates in an architecture document
are wrong within a quarter; triggers stay true.

| Phase | Scope | Trigger to start | Exit criterion | Blocked by |
| :--- | :--- | :--- | :--- | :--- |
| 1 | Multi-AZ write path | Now | `FF-02` passes | — |
| 2 | Multi-region active/active | Tenant count > 2,000 **or** first EU-central contract | `FF-02` both regions | Phase 1, `D-01` |
| 3 | Plugin format registry | ≥ 3 requested formats/quarter | `FF-04` holds | `K-03` (team size) |

---

## 23. Section header convention

Every section carries its ID, concern framing, and (where relevant) mode marker:

```markdown
### L2.5 Threat Model
<!-- frames: C-02, C-03 -->
<!-- agent:begin id="L2.5" hash="sha256:…" -->

[AS-IS] …

<!-- agent:end id="L2.5" -->

<!-- human:begin id="L2.5.notes" -->
Reviewer note: the TB-2 gap was accepted for Q3 only. — @security, 2026-08-02
<!-- human:end id="L2.5.notes" -->
```

Staleness marker (`-01` Rule U-4):

```markdown
> [!WARNING]
> **STALE** as of `f4e5d6c` — claims below last verified at `a1b2c3d`.
> 4 provenance pointers unresolvable. See `Q-17`.
```
