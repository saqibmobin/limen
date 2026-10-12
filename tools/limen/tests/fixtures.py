"""Fixture builders for the limen test suite.

Three document sets over one throwaway git repo:

  clean   a 6.0 document that passes every check, including under --strict
  broken  seeds at least one violation of every check, so a regression that
          silences one shows up as a test failure rather than a green run
  v5      a 5.x document, for `limen migrate` and `limen check --legacy`
"""
from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path

from limen import docset, lock

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
# shared pieces
# --------------------------------------------------------------------------

L2_MERMAID = """graph TD
    A["ingest-api"] -->|"POST /v1/uploads (part)"| B["ingest-worker"]
    B --> C["object storage"]
"""

BAD_MERMAID = """graph TD
    A[POST /v1/uploads (part)] --> B[worker
"""

ADR_011 = """---
id: ADR-011
title: Derive tenant data keys per request rather than per session
status: accepted
---

# ADR-011 - Derive tenant data keys per request

## Considered options

- Per-request derivation (chosen): key lifetime bounded by the request.
- Per-session cached key: near-zero added latency, but key material for many
  tenants co-resident in one process.

## Consequences

Consumes part of the latency budget in `QA-01`. Revisit if KMS p99 exceeds 25 ms.
"""

# A decision record in a form limen does not inspect at all.
ADR_012 = """# ADR-012: Keep both wasm variants

Deferred; see the spike notes.
"""


def _write(root: Path, rel: str, body: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)


def front_matter(baseline: str | None, mode: str = "brownfield",
                 title: str = "Ingest Platform HLD") -> str:
    base = f"baseline: {baseline}\n" if baseline else ""
    return (f"---\ntitle: {title}\nmode: {mode}\n{base}version: 2.0.0\n"
            "status: draft\nadr_dir: adr\n---\n")


def stamp_all(root: Path, human: list[str] = ()) -> None:
    lock.stamp(docset.load(root), new=True)
    if human:
        lock.stamp(docset.load(root), human=list(human))


# --------------------------------------------------------------------------
# clean document set
# --------------------------------------------------------------------------

def clean_body(short: str) -> str:
    return f"""
# Ingest Platform HLD

## Summary

The ingest platform accepts tenant uploads and stores them durably. Its one
shaping decision derives keys per request and pays for it in latency (`ADR-011`).

## Quality priorities

| ID | Attribute | Scenario | Measure | Tier |
| :--- | :--- | :--- | :--- | :--- |
| `QA-01` | Latency | A tenant uploads a 24 MiB part at peak | p95 at most 250 ms | `[inferred]` |

## Context and containers

The `ingest-api` container hands work to the `ingest-worker` container, which
writes to object storage `[inferred]`.

```mermaid
{L2_MERMAID}```

## Invariants

| Invariant | Tier | Basis | Checked | Status |
| :--- | :--- | :--- | :--- | :--- |
| A part is at most 24 MiB | `[verified]` | `internal/ingest/limits.go@{short}::MaxPartBytes` = 25165824 | Read the constant | `untested` |

- The long-poll timeout is 30 s `[verified]`
  (`internal/ingest/limits.go@{short}::pollTimeoutSeconds` = 30).
- Workers come from one pool `[verified]` (`internal/worker/pool.go@{short}::NewPool`).
- Container resources are capped `[verified]`
  (`deploy/k8s/ingest.yaml@{short}::spec.template.spec.containers[0].resources`).
- Uploads enter through one handler `[verified]`
  (`internal/ingest/handler.go@{short}::(*Handler).Upload`), built by
  `internal/ingest/handler.go@{short}::NewHandler`.
- Every upload row carries a tenant `[verified]`
  (`db/migrations/0042_add_tenant_id.sql@{short}::uploads`).
- Keys are derived per request `[verified]`, as decided in `ADR-011`.
- Tokens are JWTs per RFC 7519 `[verified]`.

## Key decisions

| Decision | Chosen | Sacrifices | ADR | Tier |
| :--- | :--- | :--- | :--- | :--- |
| Key lifetime | Per-request derivation | `QA-01` latency | `ADR-011` | `[verified]` |
| Wasm variants | Keep both | Deploy size | `ADR-012` | `[verified]` |

## Risks and open questions

- Publish an OpenAPI document generated from the handlers `[proposed]`, owner
  @ingest-lead, trigger: the first external SDK consumer appears.
- Whether the part ceiling is a protocol limit is undetermined `[unknown]`,
  tracked as `Q-01`.
- Which cache is deployed is undetermined `[unknown]`, see `Q-02`.

| ID | Question | Owner | Resolution path |
| :--- | :--- | :--- | :--- |
| `Q-01` | Is the 24 MiB limit a protocol constraint or a tuned value? | @ingest-lead | git blame the constant |
| `Q-02` | Is Redis or Memcached deployed? | @platform | Read the running config |

This diagram is a deliberate example of what not to write, so it is skipped:

<!-- limen:ignore-diagram -->

```mermaid
{BAD_MERMAID}```

## Reviewer notes

Sizing re-checked by hand on 2026-09-01.
"""


def build_clean_docs(root: Path, baseline: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    _write(root, "hld.md", front_matter(baseline) + clean_body(baseline[:7]))
    _write(root, "adr/ADR-011-per-request-key-derivation.md", ADR_011)
    _write(root, "adr/ADR-012-keep-both-variants.md", ADR_012)
    stamp_all(root, human=["Reviewer notes"])


# --------------------------------------------------------------------------
# broken document set
# --------------------------------------------------------------------------

def build_broken_docs(root: Path, baseline: str) -> None:
    short = baseline[:7]
    root.mkdir(parents=True, exist_ok=True)
    _write(root, "adr/ADR-011-per-request-key-derivation.md", ADR_011)

    body = f"""
# Broken HLD

## Claims

- missing symbol `[verified]` (`internal/ingest/limits.go@{short}::NoSuchConstant`)
- missing path `[verified]` (`internal/nope/gone.go@{short}::Thing`)
- literal mismatch `[verified]` (`internal/ingest/limits.go@{short}::MaxPartBytes` = 999999)
- mixed baseline `[verified]` (`internal/ingest/handler.go@deadbee::NewHandler`)
- forbidden form: `file:///home/someone/repo/internal/ingest/limits.go#L4`
- whole file `[verified]` (`internal/ingest/limits.go@{short}`)
- a verified claim with nothing behind it `[verified]`.

## Honesty

- the cache topology is undetermined `[unknown]`.
- the shard count is undetermined `[unknown]`, tracked as `Q-07`.
- add per-region garbage collection `[proposed]`.
- shard the queue `[proposed]`, owner @platform, when needed.
- a [verified] claim mentioned bare in prose.
- **`[proposed] Proposed:`** a misplaced backtick, owner @platform, trigger: backlog over 1 h.
- an old tag `[T1]` (`internal/worker/pool.go@{short}::NewPool`).

## Decisions

Storage follows `ADR-011`, and sharding follows `ADR-999`.

```mermaid
{BAD_MERMAID}```

This one is a deliberate example and must be skipped:

<!-- limen:ignore-diagram -->

```mermaid
{BAD_MERMAID}```

## Edited later

Original content.
"""
    _write(root, "hld.md", front_matter(baseline, title="Broken HLD") + body)
    stamp_all(root)
    hld = root / "hld.md"
    hld.write_text(hld.read_text().replace("Original content.",
                                           "Content a person rewrote after stamping."))


# --------------------------------------------------------------------------
# 5.x document set
# --------------------------------------------------------------------------

def agent_block(bid: str, body: str, tamper: bool = False) -> str:
    """A 5.x agent block, hashed the way 5.x hashed it."""
    digest = "sha256:" + hashlib.sha256(body.encode()).hexdigest()
    if tamper:
        digest = "sha256:" + "0" * 64
    return f'<!-- agent:begin id="{bid}" hash="{digest}" -->\n{body}\n<!-- agent:end id="{bid}" -->'


V5_QUESTIONS = """- id: Q-01
  question: Who owns pkg/legacy/replicator?
  owner: "@ingest-lead"
  resolution_path: Check CODEOWNERS history
  status: open
"""


def build_v5_docs(root: Path, baseline: str) -> None:
    short = baseline[:7]
    root.mkdir(parents=True, exist_ok=True)
    _write(root, "registers/open-questions.yaml", V5_QUESTIONS)
    _write(root, "adr/ADR-011-per-request-key-derivation.md", ADR_011)

    l1 = f"""## L1.4 Quality scenarios
<!-- frames: C-01 -->

- Max part size `[T1]` (`internal/ingest/limits.go@{short}::MaxPartBytes` = 25165824).
- Ownership of the legacy replicator is undetermined `[T0]`, tracked as `Q-01`.
- Proposed: publish an OpenAPI document `[T3]`, owner @ingest-lead, trigger: the
  first external consumer appears.
- Tenancy is enforced in the repository layer `[T2]`.

<!-- c4: level=2 -->

```mermaid
{L2_MERMAID}```"""

    l2 = f"""## L2.1 Components
<!-- frames: C-02 -->

- Upload entry point `[T1]` (`internal/ingest/handler.go@{short}::(*Handler).Upload`),
  per `ADR-011`."""

    front = f"""---
doc: hld
id: HLD-ingest
title: Ingest HLD
version: 4.1.0
status: draft
mode: brownfield-change
level: 2
profile: P2-product-service
adr_dir: adr
repo:
  url: https://example.invalid/acme/ingest
  commit: {baseline}
  short: {short}
counts:
  open_questions: 1
---
"""
    _write(root, "01-intake.md",
           front + "\n# Ingest HLD\n\n"
           + agent_block("L1", l1) + "\n\n"
           + agent_block("L2", l2, tamper=True) + "\n\n"
           + '<!-- human:begin id="L2.note" -->\n## Reviewer notes\n\n'
             "Sizing re-checked by hand.\n"
             '<!-- human:end id="L2.note" -->\n')
