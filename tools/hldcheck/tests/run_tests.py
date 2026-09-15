#!/usr/bin/env python3
"""End-to-end tests for hldcheck.

Builds a throwaway git repo and two HLD document sets (one clean, one seeded
with every failure mode the four implemented gates are meant to catch), runs the
CLI in-process, and asserts on gate status, item counts and exit codes.

Run:  python3 tests/run_tests.py [-k pattern] [--keep]
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hldcheck.cli import main  # noqa: E402
from hldcheck.docset import normalize_block  # noqa: E402

FAILURES: list[str] = []
PASSES = 0


# --------------------------------------------------------------------------
# assertions
# --------------------------------------------------------------------------

def check(label: str, condition: bool, detail: str = "") -> None:
    global PASSES
    if condition:
        PASSES += 1
        print(f"  ok   {label}")
    else:
        FAILURES.append(label)
        print(f"  FAIL {label}" + (f"\n         {detail}" if detail else ""))


def gate(payload: dict, gate_id: str) -> dict:
    for g in payload["gates"]:
        if g["id"] == gate_id:
            return g
    return {"id": gate_id, "status": "(absent)", "items": []}


def summaries(g: dict) -> str:
    return " | ".join(i["summary"] for i in g.get("items", []))


def run_cli(argv: list[str]) -> tuple[int, dict]:
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = main([*argv, "--format", "json"])
    raw = buf.getvalue()
    try:
        return code, json.loads(raw)
    except json.JSONDecodeError:
        return code, {"gates": [], "summary": {}, "_raw": raw}


# --------------------------------------------------------------------------
# fixture: git repository
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
    files = {
        "internal/ingest/limits.go": LIMITS_GO_V1,
        "internal/ingest/handler.go": HANDLER_GO,
        "internal/worker/pool.go": POOL_GO,
        "deploy/k8s/ingest.yaml": DEPLOY_YAML,
        "db/migrations/0042_add_tenant_id.sql": MIGRATION_SQL,
    }
    for rel, body in files.items():
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

    # A later commit that changes a quoted literal and moves a symbol.
    (root / "internal/ingest/limits.go").write_text(LIMITS_GO_V2)
    (root / "internal/worker/pool.go").write_text("// header added\n\n" + POOL_GO)
    git("add", "-A")
    git("commit", "-qm", "raise part ceiling")
    later = git("rev-parse", "HEAD")
    return baseline, later


# --------------------------------------------------------------------------
# fixture: HLD document sets
# --------------------------------------------------------------------------

GOOD_MERMAID = """graph TD
    A["ingest-api"] -->|"POST /v1/uploads (part)"| B["ingest-worker"]
    B --> C["object storage"]
"""

SECOND_MERMAID = """sequenceDiagram
    autonumber
    actor Client
    participant API as "ingest-api"
    Client->>API: "POST /v1/uploads"
    API-->>Client: "202 Accepted"
"""

BAD_MERMAID = """graph TD
    A[POST /v1/uploads (part)] --> B[worker
"""


def agent_block(bid: str, body: str, tamper: bool = False, hashed: bool = True) -> str:
    digest = "sha256:" + hashlib.sha256(normalize_block("\n" + body + "\n").encode()).hexdigest()
    if tamper:
        digest = "sha256:" + "0" * 64
    attrs = f'id="{bid}"' + (f' hash="{digest}"' if hashed else "")
    return f"<!-- agent:begin {attrs} -->\n{body}\n<!-- agent:end id=\"{bid}\" -->"


def front_matter(baseline: str, *, version: str = "4.1.0", counts: dict) -> str:
    return f"""---
doc: hld
id: HLD-ingest-platform
title: Ingest Platform High-Level Design
version: {version}
status: draft
mode: brownfield-asis
level: 2
profile: P2-product-service
ungated: false
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
  concerns: {counts['concerns']}
  constraints: {counts['constraints']}
  quality_scenarios: {counts['quality_scenarios']}
  open_questions: {counts['open_questions']}
changelog:
  - version: {version}
    date: 2026-09-15
    trigger: provenance-drift
    summary: Re-pinned baseline.
---
"""


def build_clean_docs(root: Path, baseline: str) -> None:
    short = baseline[:7]
    root.mkdir(parents=True, exist_ok=True)

    body = f"""### L1.4 Quality scenarios
<!-- frames: C-01, C-02 -->

`QA-01` availability, `QA-02` latency. Constraints `K-01`, `K-02`.
Open questions: `Q-01`, `Q-02`. Concern `C-03` is framed at L2.5.

Max part size is 24 MiB `[T1]` (`internal/ingest/limits.go@{short}::MaxPartBytes` = 25165824).
Long-poll timeout is 30 s `[T1]` (`internal/ingest/limits.go@{short}::pollTimeoutSeconds` = 30).

```mermaid
{GOOD_MERMAID}```
"""

    (root / "01-intake.md").write_text(
        front_matter(baseline, counts={"concerns": 3, "constraints": 2,
                                       "quality_scenarios": 2, "open_questions": 2})
        + "\n# Ingest Platform HLD\n\n"
        + agent_block("L1.4", body)
        + "\n\n<!-- human:begin id=\"L1.4.note\" -->\nReviewer note: sizing re-checked 2026-09-01.\n<!-- human:end id=\"L1.4.note\" -->\n"
    )

    (root / "02-mechanics.md").write_text(f"""# L2 Mechanics

### L2.1 Components
<!-- frames: C-01 -->

The upload handler is `internal/ingest/handler.go@{short}::(*Handler).Upload` `[T1]`.
The worker pool constructor is `internal/worker/pool.go@{short}::NewPool` `[T1]`.
Container resources: `deploy/k8s/ingest.yaml@{short}::spec.template.spec.containers[0].resources` `[T1]`.
Schema: `db/migrations/0042_add_tenant_id.sql@{short}::uploads` `[T1]`.
Migrations directory: `db/migrations/@{short}` `[T1]`.

```mermaid
{SECOND_MERMAID}```
""")


def build_broken_docs(root: Path, baseline: str) -> None:
    short = baseline[:7]
    root.mkdir(parents=True, exist_ok=True)

    # G9: non-semver version, counts that do not match content.
    fm = front_matter(baseline, version="4.1",
                      counts={"concerns": 99, "constraints": 2,
                              "quality_scenarios": 2, "open_questions": 1})

    body = f"""### L1.4 Quality scenarios

`QA-01`, `QA-02`, `K-01`, `K-02`, `C-01`, `Q-01`.

G1 failures below:
- missing symbol: `internal/ingest/limits.go@{short}::NoSuchConstant` `[T1]`
- missing path: `internal/nope/gone.go@{short}::Thing` `[T1]`
- literal mismatch: `internal/ingest/limits.go@{short}::MaxPartBytes` = 999999 `[T1]`
- mixed baseline: `internal/ingest/handler.go@deadbee::NewHandler` `[T1]`
- forbidden form: `file:///home/someone/repo/internal/ingest/limits.go#L4`

```mermaid
{BAD_MERMAID}```

This one is a deliberate example and must be skipped:

<!-- hldcheck:ignore-diagram -->

```mermaid
{BAD_MERMAID}```
"""

    (root / "01-intake.md").write_text(
        fm + "\n# Broken HLD\n\n"
        + agent_block("L1.4", body, tamper=True)
        + "\n\n"
        + agent_block("L2.1", "Unhashed agent block.", hashed=False)
        + "\n"
    )


# --------------------------------------------------------------------------
# test cases
# --------------------------------------------------------------------------

def test_clean(work: Path, repo: Path, baseline: str) -> None:
    docs = work / "docs-clean"
    build_clean_docs(docs, baseline)
    code, payload = run_cli(["--docs", str(docs), "--repo", str(repo)])

    check("clean: exit code 0", code == 0, f"got {code}")
    for gid in ("G1", "G2", "G9", "G10"):
        g = gate(payload, gid)
        check(f"clean: {gid} passes", g["status"] == "pass", summaries(g))

    g1 = gate(payload, "G1")
    stats = g1.get("stats", {})
    check("clean: G1 resolved every pointer",
          stats.get("resolved") == stats.get("total") and stats.get("total", 0) >= 7,
          json.dumps(stats))
    check("clean: G1 found no value-changed literals",
          stats.get("value_changed") == 0, json.dumps(stats))

    g2 = gate(payload, "G2")
    check("clean: G2 rendered 2 diagrams",
          g2.get("stats", {}).get("diagrams") == 2, json.dumps(g2.get("stats")))

    g10 = gate(payload, "G10")
    st = g10.get("stats", {})
    check("clean: G10 saw 1 agent + 1 human block",
          st.get("agent") == 1 and st.get("human") == 1 and st.get("mismatched") == 0,
          json.dumps(st))


def test_broken(work: Path, repo: Path, baseline: str) -> None:
    docs = work / "docs-broken"
    build_broken_docs(docs, baseline)
    code, payload = run_cli(["--docs", str(docs), "--repo", str(repo)])

    check("broken: exit code 1", code == 1, f"got {code}")

    g9 = gate(payload, "G9")
    text = summaries(g9)
    check("broken: G9 fails", g9["status"] == "fail", text)
    check("broken: G9 flags non-semver version", "not semver" in text, text)
    check("broken: G9 flags counts mismatch", "counts.concerns" in text, text)

    g1 = gate(payload, "G1")
    text = summaries(g1)
    check("broken: G1 fails", g1["status"] == "fail", text)
    check("broken: G1 flags missing symbol", "NoSuchConstant" in text, text)
    check("broken: G1 flags missing path", "gone.go" in text or "path not found" in text, text)
    check("broken: G1 flags literal mismatch", "literal mismatch" in text, text)
    check("broken: G1 flags mixed baseline", "deadbee" in text, text)
    check("broken: G1 flags file:// pointer", "forbidden pointer form" in text, text)

    g2 = gate(payload, "G2")
    text = summaries(g2)
    check("broken: G2 fails", g2["status"] == "fail", text)
    check("broken: G2 reports exactly one render failure",
          sum(1 for i in g2.get("items", []) if "render failed" in i["summary"]) == 1,
          text)
    check("broken: G2 honoured hldcheck:ignore-diagram",
          g2.get("stats", {}).get("diagrams") == 1, json.dumps(g2.get("stats")))
    check("broken: G2 static lint caught the unquoted label",
          "[V-9]" in text, text)

    g10 = gate(payload, "G10")
    text = summaries(g10)
    check("broken: G10 fails", g10["status"] == "fail", text)
    check("broken: G10 detects the human-edited agent block",
          "edited by a human" in text, text)
    check("broken: G10 detects the unhashed agent block",
          "no `hash` attribute" in text, text)


def test_drift(work: Path, repo: Path, baseline: str, later: str) -> None:
    docs = work / "docs-clean"
    code, payload = run_cli(["--docs", str(docs), "--repo", str(repo),
                             "--at", later, "--gates", "G1"])

    drift = payload.get("drift", {})
    check("drift: exit code 3", code == 3, f"got {code}, drift={drift}")
    check("drift: literal change detected", drift.get("value_changed", 0) >= 1,
          json.dumps(drift))
    check("drift: moved symbol detected", drift.get("moved", 0) >= 1, json.dumps(drift))
    text = summaries(gate(payload, "G1"))
    check("drift: findings are warnings, not baseline failures",
          gate(payload, "G1")["status"] == "warn" and "DRIFT" in text, text)


def test_stamp(work: Path, repo: Path, baseline: str) -> None:
    docs = work / "docs-stamp"
    build_broken_docs(docs, baseline)

    code, payload = run_cli(["--docs", str(docs), "--repo", str(repo), "--gates", "G10"])
    before = gate(payload, "G10").get("stats", {})
    check("stamp: pre-stamp mismatch present",
          before.get("mismatched") == 1 and before.get("unhashed") == 1,
          json.dumps(before))

    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main(["--docs", str(docs), "--stamp"])
    check("stamp: exits 0", rc == 0, buf.getvalue())

    code, payload = run_cli(["--docs", str(docs), "--repo", str(repo), "--gates", "G10"])
    after = gate(payload, "G10").get("stats", {})
    check("stamp: hashes reconciled afterwards",
          after.get("mismatched") == 0 and after.get("unhashed") == 0,
          json.dumps(after) + " | " + summaries(gate(payload, "G10")))


def test_output_formats(work: Path, repo: Path) -> None:
    docs = work / "docs-broken"
    buf = io.StringIO()
    with redirect_stdout(buf):
        main(["--docs", str(docs), "--repo", str(repo), "--gates", "G10",
              "--format", "sarif"])
    try:
        sarif = json.loads(buf.getvalue())
        ok = sarif["runs"][0]["results"][0]["level"] == "error"
    except Exception as exc:  # noqa: BLE001
        ok, sarif = False, str(exc)
    check("formats: sarif output is well-formed with an error result", ok, str(sarif)[:200])

    buf = io.StringIO()
    with redirect_stdout(buf):
        main(["--docs", str(docs), "--repo", str(repo), "--gates", "G10"])
    check("formats: text output names the gate", "G10" in buf.getvalue(), buf.getvalue())


# --------------------------------------------------------------------------

def main_tests() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-k", dest="pattern", default="")
    ap.add_argument("--keep", action="store_true", help="keep the temp workspace")
    args = ap.parse_args()

    work = Path(tempfile.mkdtemp(prefix="hldcheck-tests-"))
    repo = work / "repo"
    repo.mkdir()
    baseline, later = build_repo(repo)
    print(f"workspace: {work}\nbaseline:  {baseline[:12]}\nlater:     {later[:12]}\n")

    cases = [
        ("clean", lambda: test_clean(work, repo, baseline)),
        ("broken", lambda: test_broken(work, repo, baseline)),
        ("drift", lambda: test_drift(work, repo, baseline, later)),
        ("stamp", lambda: test_stamp(work, repo, baseline)),
        ("formats", lambda: test_output_formats(work, repo)),
    ]
    for name, fn in cases:
        if args.pattern and args.pattern not in name:
            continue
        print(f"{name}:")
        fn()
        print()

    print(f"{PASSES} passed, {len(FAILURES)} failed")
    for f in FAILURES:
        print(f"  - {f}")
    if not args.keep:
        shutil.rmtree(work, ignore_errors=True)
    else:
        print(f"\nworkspace kept at {work}")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main_tests())
