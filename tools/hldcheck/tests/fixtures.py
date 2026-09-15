"""Fixture builders for the hldcheck test suite.

Two HLD document sets over one throwaway git repo:

  clean   satisfies all twelve gates
  broken  seeds at least one violation of every gate, so a regression that
          silences a check shows up as a test failure rather than a green run
"""
from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path

from hldcheck.docset import normalize_block

# --------------------------------------------------------------------------
# git repository
# --------------------------------------------------------------------------

LIMITS_GO_V1 = """package ingest

// MaxPartBytes is the protocol ceiling for one multipart chunk.
const MaxPartBytes = 25165824

const pollTimeoutSeconds = 30
"""

LIMITS_GO_V2 = LIMITS_GO_V1.replace("25165824", "33554432")

HANDLER_GO = """package ingest

type Handler struct{ repo Repo }

func (h *Handler) Upload(ctx context.Context, r *Request) error {
\treturn h.repo.Save(ctx, r)
}

func NewHandler(repo Repo) *Handler { return &Handler{repo: repo} }
"""

POOL_GO = """package worker

func NewPool(size int) *Pool {
\treturn &Pool{size: size}
}
"""

DEPLOY_YAML = """apiVersion: apps/v1
kind: Deployment
metadata:
  name: ingest-api
spec:
  template:
    spec:
      containers:
        - name: api
          resources:
            limits:
              memory: 512Mi
"""

MIGRATION_SQL = """CREATE TABLE uploads (
  id UUID PRIMARY KEY,
  tenant_id UUID NOT NULL
);
"""


def build_repo(root: Path) -> tuple[str, str]:
    """Create a git repo; return (baseline_sha, later_sha)."""
    for rel, body in {
        "internal/ingest/limits.go": LIMITS_GO_V1,
        "internal/ingest/handler.go": HANDLER_GO,
        "internal/worker/pool.go": POOL_GO,
        "deploy/k8s/ingest.yaml": DEPLOY_YAML,
        "db/migrations/0042_add_tenant_id.sql": MIGRATION_SQL,
    }.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body)

    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid"}

    def git(*args: str) -> str:
        return subprocess.run(["git", "-C", str(root), *args], check=True,
                              capture_output=True, env=env).stdout.decode().strip()

    git("init", "-q", "-b", "main")
    git("add", "-A")
    git("commit", "-qm", "baseline")
    baseline = git("rev-parse", "HEAD")

    (root / "internal/ingest/limits.go").write_text(LIMITS_GO_V2)
    (root / "internal/worker/pool.go").write_text("// header added\n\n" + POOL_GO)
    git("add", "-A")
    git("commit", "-qm", "raise part ceiling")
    return baseline, git("rev-parse", "HEAD")


# --------------------------------------------------------------------------
# diagrams and blocks
# --------------------------------------------------------------------------

L2_MERMAID = """graph TD
    A["ingest-api"] -->|"POST /v1/uploads (part)"| B["ingest-worker"]
    B --> C["object storage"]
"""

L3_MERMAID = """graph LR
    H["upload handler"] --> R["tenant repository"]
"""

INCONSISTENT_MERMAID = """graph TD
    A["Ingest API"] --> B["queue"]
"""

BAD_MERMAID = """graph TD
    A[POST /v1/uploads (part)] --> B[worker
"""


def agent_block(bid: str, body: str, tamper: bool = False, hashed: bool = True) -> str:
    digest = "sha256:" + hashlib.sha256(
        normalize_block("\n" + body + "\n").encode()).hexdigest()
    if tamper:
        digest = "sha256:" + "0" * 64
    attrs = f'id="{bid}"' + (f' hash="{digest}"' if hashed else "")
    return f'<!-- agent:begin {attrs} -->\n{body}\n<!-- agent:end id="{bid}" -->'


# --------------------------------------------------------------------------
# registers
# --------------------------------------------------------------------------

CLEAN_CONCERNS = """- id: C-01
  stakeholder: Platform SRE
  role: operates
  concern: Determine which component caused an incident within 5 minutes.
  priority: H
  framed_by: [L1.4]
- id: C-02
  stakeholder: Tenant admin
  role: uses
  concern: Confirm my tenant's data is isolated from other tenants.
  priority: H
  framed_by: [L1.4]
- id: C-03
  stakeholder: Security review
  role: audits
  concern: Know what crosses a trust boundary unauthenticated.
  priority: H
  framed_by: [L1.9, L2.5]
- id: C-04
  stakeholder: Finance
  role: funds
  concern: Know what a marginal tenant costs per month.
  priority: M
  framed_by: [L1.6]
- id: C-05
  stakeholder: New engineer
  role: builds
  concern: Find where to add a new ingest format.
  priority: M
  framed_by: [L2.1, L2.2]
"""

CLEAN_CONSTRAINTS = """- id: K-01
  class: legal
  constraint: EU tenant data must not leave eu-west-1.
  source: DPA section 7
  negotiable: false
- id: K-02
  class: technical
  constraint: Datastore must be Postgres (platform mandate).
  source: Platform RFC-88
  negotiable: false
- id: K-03
  class: organizational
  constraint: Four engineers, no dedicated SRE.
  source: Team charter
  negotiable: false
"""

CLEAN_SCENARIOS = """- id: QA-01
  attribute: availability
  priority: { importance: H, difficulty: H }
  source: Authenticated tenant client
  stimulus: Submits an upload during a single-AZ failure
  artifact: ingest-api write path
  environment: Peak load, one availability zone unreachable
  response: Upload is accepted and durably committed
  response_measure: { success_rate_min: 0.995, window_minutes: 10 }
  derived_slo: SLO-01
  fitness_function: FF-02
  traded_against: [QA-03]
- id: QA-02
  attribute: performance.latency
  priority: { importance: H, difficulty: M }
  source: Authenticated tenant client
  stimulus: Submits a 24 MiB multipart upload
  artifact: ingest-api write path
  environment: Peak load, normal operation
  response: Upload acknowledged and durably committed
  response_measure: { p95_ms: 250, p99_ms: 900 }
  derived_slo: SLO-02
  fitness_function: FF-03
- id: QA-03
  attribute: cost
  priority: { importance: M, difficulty: M }
  source: Finance
  stimulus: Tenant count doubles
  artifact: whole system
  environment: Steady state over one month
  response: Marginal cost per tenant stays sublinear
  response_measure: { cost_per_tenant_max_usd: 2.40 }
- id: QA-04
  attribute: modifiability
  priority: { importance: M, difficulty: L }
  source: Engineer
  stimulus: Adds a new ingest format
  artifact: format registry
  environment: Development
  response: No change to the transport layer
  response_measure: { files_touched_max: 3 }
- id: QA-05
  attribute: security.isolation
  priority: { importance: H, difficulty: H }
  source: Compromised tenant credential
  stimulus: Attempts to read another tenant's upload
  artifact: repository layer
  environment: Normal operation
  response: Request is denied and audited
  response_measure: { cross_tenant_reads_max: 0 }
  derived_slo: SLO-03
  fitness_function: FF-01
  traded_against: [QA-02]
"""

CLEAN_QUESTIONS = """- id: Q-01
  question: Is the 24 MiB part limit a protocol constraint or a tuned value?
  matters_because: Determines whether the sizing bounds can be relaxed.
  blocks: [L1.6]
  owner: "@ingest-lead"
  resolution_path: git blame internal/ingest/limits.go; ask the original author
  status: open
- id: Q-02
  question: Which cache is actually deployed, Redis or Memcached?
  matters_because: Affects the failure analysis for the read path.
  blocks: [L2.1]
  owner: "@platform"
  resolution_path: Inspect the running configuration in eu-west-1
  status: open
- id: Q-03
  question: Who owns pkg/legacy/replicator?
  matters_because: Decides whether it can be decommissioned.
  blocks: [L2.1]
  owner: "@ingest-lead"
  resolution_path: Check CODEOWNERS history
  status: open
"""

CLEAN_ADR = """---
id: ADR-011
title: Derive tenant data keys per request rather than per session
status: accepted
date: 2026-07-14
deciders: ["@ingest-lead", "@security"]
optimizes_for: [QA-05]
sacrifices: [QA-02]
affects_sections: [L2.5]
---

# ADR-011 - Derive tenant data keys per request

## Context and problem statement

Caching a derived key for a session reduces latency but widens the window in
which a process holds key material for multiple tenants.

## Considered options

### Option A - Per-request derivation (chosen)
- Pros: key lifetime bounded by the request; no cache to operate.
- Cons: adds latency; raises KMS request volume.

### Option B - Per-session cached key with TTL
- Pros: near-zero added latency.
- Cons: multi-tenant key material co-resident in process memory.

## Decision outcome

Chosen: Option A. A leaked cross-tenant key cannot be un-leaked.

## Consequences

- Negative: consumes part of the latency budget in QA-02.
- Revisit trigger: if KMS p99 exceeds 25 ms, re-open with envelope encryption.
"""


def front_matter(baseline: str, *, version: str = "4.1.0", mode: str = "brownfield-asis",
                 level: int = 2, counts: dict) -> str:
    rows = "\n".join(f"  {k}: {v}" for k, v in counts.items())
    return f"""---
doc: hld
id: HLD-ingest-platform
title: Ingest Platform High-Level Design
version: {version}
status: draft
mode: {mode}
level: {level}
profile: P2-product-service
ungated: false
adr_dir: adr
repo:
  url: https://example.invalid/acme/ingest
  commit: {baseline}
  short: {baseline[:7]}
  dirty: false
  inspected: full
authors:
  - {{ name: architecture-agent, kind: agent }}
owners:
  document: platform-team
  system: ingest-team
counts:
{rows}
changelog:
  - version: {version}
    date: 2026-09-15
    trigger: provenance-drift
    summary: Re-pinned baseline.
---
"""


def _write(root: Path, rel: str, body: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)


# --------------------------------------------------------------------------
# clean document set
# --------------------------------------------------------------------------

def build_clean_docs(root: Path, baseline: str) -> None:
    short = baseline[:7]
    root.mkdir(parents=True, exist_ok=True)

    _write(root, "registers/concerns.yaml", CLEAN_CONCERNS)
    _write(root, "registers/constraints.yaml", CLEAN_CONSTRAINTS)
    _write(root, "registers/quality-scenarios.yaml", CLEAN_SCENARIOS)
    _write(root, "registers/open-questions.yaml", CLEAN_QUESTIONS)
    _write(root, "adr/ADR-011-per-request-key-derivation.md", CLEAN_ADR)

    intake_body = f"""### L1.4 Quality scenarios
<!-- frames: C-01, C-02 -->

Scenarios `QA-01` through `QA-05` are registered, with the conflict set recorded
as `traded_against` entries. Constraints `K-01`, `K-02` and `K-03` apply.

- Max part size `[T1]` (`internal/ingest/limits.go@{short}::MaxPartBytes` = 25165824).
- Long-poll timeout `[T1]` (`internal/ingest/limits.go@{short}::pollTimeoutSeconds` = 30).
- Ownership of the legacy replicator is undetermined `[T0]`, tracked as `Q-03`.

### L1.6 Sizing bounds
<!-- frames: C-04 -->

- Worker pool size `[T1]` (`internal/worker/pool.go@{short}::NewPool`).
- Container resources `[T1]`
  (`deploy/k8s/ingest.yaml@{short}::spec.template.spec.containers[0].resources`).
- The part ceiling may be a tuned value rather than a protocol constraint `[T0]`,
  tracked as `Q-01`.

### L1.9 Container topology
<!-- frames: C-03 -->

The `ingest-api` container terminates tenant traffic and hands work to the
`ingest-worker` container, which writes to object storage `[T2]`.

<!-- c4: level=2 -->

```mermaid
{L2_MERMAID}```

### L1.10 Trade-off index
<!-- frames: C-03 -->

| Dimension | Chosen | Rejected | Sacrifices | ADR | Tier |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Key lifetime | Per-request derivation | Per-session cached key | `QA-02` | `ADR-011` | `[T1]` |
"""

    _write(root, "01-intake.md",
           front_matter(baseline, counts={"concerns": 5, "constraints": 3,
                                          "quality_scenarios": 5, "open_questions": 3})
           + "\n# Ingest Platform HLD\n\n"
           + agent_block("L1", intake_body)
           + '\n\n<!-- human:begin id="L1.note" -->\n'
             "Reviewer note: sizing re-checked 2026-09-01.\n"
             '<!-- human:end id="L1.note" -->\n')

    mechanics_body = f"""### L2.1 Components
<!-- frames: C-05 -->

Inside `ingest-api`, the `upload handler` delegates persistence to the
`tenant repository` `[T2]`.

- Upload entry point `[T1]` (`internal/ingest/handler.go@{short}::(*Handler).Upload`).
- Handler constructor `[T1]` (`internal/ingest/handler.go@{short}::NewHandler`).
- Which cache is deployed is unresolved `[T0]`, tracked as `Q-02`.

<!-- c4: level=3 parent="ingest-api" -->

```mermaid
{L3_MERMAID}```

### L2.2 Contracts
<!-- frames: C-05 -->

| ID | Contract | Auth | Provenance | Tier |
| :--- | :--- | :--- | :--- | :--- |
| `I-01` | `POST /v1/uploads` | OIDC | `internal/ingest/handler.go@{short}::(*Handler).Upload` | `[T1]` |

- Proposed: publish an OpenAPI document generated from the handlers `[T3]` —
  owner @ingest-lead, trigger: when the first external SDK consumer appears.

### L2.5 Threat model
<!-- frames: C-03 -->

Tenant isolation is enforced in the repository layer `[T2]`, and the schema
carries a tenant column `[T1]`
(`db/migrations/0042_add_tenant_id.sql@{short}::uploads`).

| ID | SLI | Target | Window | Derived from | Tier |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `SLO-01` | Upload success rate | 99.9% | 30 d | `QA-01` | `[T2]` |
| `SLO-02` | Upload-ack p95 | 250 ms | 30 d | `QA-02` | `[T2]` |
| `SLO-03` | Cross-tenant reads | 0 | 30 d | `QA-05` | `[T2]` |
"""

    _write(root, "02-mechanics.md",
           "# L2 Mechanics\n\n" + agent_block("L2", mechanics_body) + "\n")


# --------------------------------------------------------------------------
# broken document set
# --------------------------------------------------------------------------

BROKEN_CONCERNS = """- id: C-01
  stakeholder: Developer
  role: builds
  concern: Find where to add a format.
  priority: M
- id: C-02
  stakeholder: Another developer
  role: builds
  concern: Understand the worker pool.
  priority: M
- id: C-07
  stakeholder: Security review
  role: audits
  concern: Never framed by any section.
  priority: H
"""

BROKEN_SCENARIOS = """- id: QA-01
  attribute: performance
  priority: { importance: H, difficulty: M }
  source: Client
  stimulus: Uploads a file
  artifact: api
  environment: Peak
  response: Accepted quickly
  response_measure: fast
- id: QA-02
  attribute: availability
  priority: { importance: H, difficulty: H }
  source: Client
  stimulus: Uploads during an outage
  artifact: api
  environment: Degraded
  response: Accepted
"""

BROKEN_QUESTIONS = """- id: Q-01
  question: Is the part limit tuned?
  status: open
"""

BROKEN_ADR = """# ADR-020 - No front matter here

This decision record has no YAML front matter at all.
"""


def build_broken_docs(root: Path, baseline: str) -> None:
    short = baseline[:7]
    root.mkdir(parents=True, exist_ok=True)

    _write(root, "registers/concerns.yaml", BROKEN_CONCERNS)
    _write(root, "registers/quality-scenarios.yaml", BROKEN_SCENARIOS)
    _write(root, "registers/open-questions.yaml", BROKEN_QUESTIONS)
    _write(root, "adr/ADR-020-no-front-matter.md", BROKEN_ADR)

    # G9: non-semver version, counts that do not match the registers.
    fm = front_matter(baseline, version="4.1", mode="brownfield-change",
                      counts={"concerns": 99, "constraints": 2,
                              "quality_scenarios": 2, "open_questions": 1})

    body = f"""### L1.4 Quality scenarios
<!-- frames: C-01, C-99 -->

G1 failures:

- missing symbol `[T1]` (`internal/ingest/limits.go@{short}::NoSuchConstant`)
- missing path `[T1]` (`internal/nope/gone.go@{short}::Thing`)
- literal mismatch `[T1]` (`internal/ingest/limits.go@{short}::MaxPartBytes` = 999999)
- mixed baseline `[T1]` (`internal/ingest/handler.go@deadbee::NewHandler`)
- forbidden form: `file:///home/someone/repo/internal/ingest/limits.go#L4`

G6: this claim has a pointer and no tier tag
(`internal/worker/pool.go@{short}::NewPool`).

G7: add per-region garbage collection `[T3]`.

G8: the cache topology is undetermined `[T0]`.

| Component | Provenance |
| :--- | :--- |
| worker | `internal/worker/pool.go@{short}::NewPool` |

| Dimension | Chosen | Rejected |
| :--- | :--- | :--- |
| Key lifetime | Per-request | Per-session |

| Dimension | Chosen | Rejected | Sacrifices | ADR |
| :--- | :--- | :--- | :--- | :--- |
| Storage | Object store | Database blobs | | `ADR-999` |

```mermaid
{BAD_MERMAID}```

This diagram is a deliberate example and must be skipped:

<!-- hldcheck:ignore-diagram -->

```mermaid
{BAD_MERMAID}```

### L2.1 Components

This section declares no frames comment at all.

The system handles uploads and writes them to storage.

<!-- c4: level=2 -->

```mermaid
{L2_MERMAID}```

<!-- c4: level=3 parent="nonexistent-container" -->

```mermaid
{INCONSISTENT_MERMAID}```
"""

    _write(root, "01-intake.md",
           fm + "\n# Broken HLD\n\n"
           + agent_block("L1.4", body, tamper=True)
           + "\n\n"
           + agent_block("L2.1", "Unhashed agent block.", hashed=False)
           + "\n")
