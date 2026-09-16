#!/usr/bin/env python3
"""End-to-end tests for limen.

Builds a throwaway git repo and two HLD document sets (one clean, one seeded
with a violation of every gate), runs the CLI in-process, and asserts on gate
status, stats and exit codes.

Run:  python3 tests/run_tests.py [-k pattern] [--keep]
"""
from __future__ import annotations

import argparse
import io
import json
import shutil
import sys
import tempfile
import textwrap
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fixtures import build_broken_docs, build_clean_docs, build_repo  # noqa: E402
from limen.cli import IMPLEMENTED, main  # noqa: E402

FAILURES: list[str] = []
PASSES = 0

ALL_GATES = ["G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8", "G9", "G10", "G11", "G12"]


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

def test_registration(work: Path, repo: Path, baseline: str) -> None:
    check("registry: all twelve gates are implemented",
          IMPLEMENTED == ALL_GATES, str(IMPLEMENTED))
    docs = work / "docs-clean"
    build_clean_docs(docs, baseline)
    code, payload = run_cli(["--docs", str(docs), "--repo", str(repo)])
    ran = [g["id"] for g in payload["gates"]]
    check("registry: a default run executes all twelve",
          sorted(ran, key=lambda g: int(g[1:])) == ALL_GATES, str(ran))
    # G9 parses front matter, which G1 needs for its baseline commit.
    check("registry: G9 runs before G1", ran.index("G9") < ran.index("G1"), str(ran))


def test_clean(work: Path, repo: Path, baseline: str) -> None:
    docs = work / "docs-clean"
    build_clean_docs(docs, baseline)
    code, payload = run_cli(["--docs", str(docs), "--repo", str(repo)])

    for gid in ALL_GATES:
        g = gate(payload, gid)
        check(f"clean: {gid} passes", g["status"] == "pass",
              f"status={g['status']} :: {summaries(g)}")
    check("clean: exit code 0", code == 0, f"got {code}")

    stats = gate(payload, "G1").get("stats", {})
    check("clean: G1 resolved every pointer",
          stats.get("resolved") == stats.get("total") and stats.get("total", 0) >= 7,
          json.dumps(stats))
    check("clean: G3 tolerates an element name split across a line break",
          gate(payload, "G3").get("stats", {}).get("absent_from_prose") == 0,
          summaries(gate(payload, "G3")))
    check("clean: G3 checked C4 containment",
          gate(payload, "G3").get("stats", {}).get("containment_checked") is True,
          json.dumps(gate(payload, "G3").get("stats")))
    check("clean: G4 framed every concern",
          gate(payload, "G4").get("stats", {}).get("unframed") == 0,
          json.dumps(gate(payload, "G4").get("stats")))
    check("clean: G5 saw 5 complete scenarios",
          gate(payload, "G5").get("stats", {}).get("scenarios") == 5
          and gate(payload, "G5").get("stats", {}).get("unquantified") == 0,
          json.dumps(gate(payload, "G5").get("stats")))
    check("clean: G8 has a non-empty question register",
          gate(payload, "G8").get("stats", {}).get("open") == 3,
          json.dumps(gate(payload, "G8").get("stats")))
    check("clean: G12 found the ADRs and the trade-off row",
          gate(payload, "G12").get("stats", {}).get("rows_without_adr") == 0
          and gate(payload, "G12").get("stats", {}).get("adr_files") == 2,
          json.dumps(gate(payload, "G12").get("stats")))
    # ADR-012 is a pointer record whose owning file never says "option". It must
    # pass on `owned_by` plus optimizes_for/sacrifices, or the gate is measuring
    # vocabulary rather than whether a trade-off was recorded.
    check("clean: G12 accepts a pointer record with a resolvable owner",
          not any("ADR-012" in str(i) for i in gate(payload, "G12").get("items", [])),
          json.dumps(gate(payload, "G12").get("items", [])))


def test_clean_strict(work: Path, repo: Path, baseline: str) -> None:
    docs = work / "docs-clean"
    code, payload = run_cli(["--docs", str(docs), "--repo", str(repo), "--strict"])
    noisy = [f"{g['id']}={g['status']}" for g in payload["gates"] if g["status"] != "pass"]
    check("clean: survives --strict with no warnings promoted to failures",
          code == 0 and not noisy,
          f"exit {code}; " + " ".join(noisy) + " :: " +
          " || ".join(summaries(g) for g in payload["gates"] if g["status"] != "pass"))


def test_broken(work: Path, repo: Path, baseline: str) -> None:
    docs = work / "docs-broken"
    build_broken_docs(docs, baseline)
    code, payload = run_cli(["--docs", str(docs), "--repo", str(repo)])

    check("broken: exit code 1", code == 1, f"got {code}")
    for gid in ALL_GATES:
        g = gate(payload, gid)
        check(f"broken: {gid} fails", g["status"] == "fail",
              f"status={g['status']} :: {summaries(g)}")

    t = {gid: summaries(gate(payload, gid)) for gid in ALL_GATES}

    check("broken: G1 flags missing symbol", "NoSuchConstant" in t["G1"], t["G1"])
    check("broken: G1 flags literal mismatch", "literal mismatch" in t["G1"], t["G1"])
    check("broken: G1 flags mixed baseline", "deadbee" in t["G1"], t["G1"])
    check("broken: G1 flags file:// pointer", "forbidden pointer form" in t["G1"], t["G1"])

    check("broken: G2 honoured limen:ignore-diagram",
          gate(payload, "G2").get("stats", {}).get("diagrams") == 3,
          json.dumps(gate(payload, "G2").get("stats")))
    check("broken: G2 reports one render failure",
          sum(1 for i in gate(payload, "G2").get("items", [])
              if "render failed" in i["summary"]) == 1, t["G2"])

    check("broken: G3 flags the orphan level-3 parent", "nonexistent" in t["G3"], t["G3"])
    check("broken: G3 flags the renamed element",
          "named two ways" in t["G3"], t["G3"])

    check("broken: G4 flags the undeclared section", "does not declare" in t["G4"], t["G4"])
    check("broken: G4 flags the dangling concern ref", "C-99" in t["G4"], t["G4"])
    check("broken: G4 flags the unframed concern", "C-07" in t["G4"], t["G4"])

    check("broken: G5 flags the vague response measure",
          "vague adjective" in t["G5"] or "not quantified" in t["G5"], t["G5"])
    check("broken: G5 flags the incomplete scenario",
          "six-part" in t["G5"], t["G5"])

    check("broken: G6 flags the untagged pointer claim",
          "no tier tag" in t["G6"], t["G6"])
    check("broken: G6 flags the table with no Tier column",
          "no Tier column" in t["G6"], t["G6"])
    # One bare mention in prose, one tag whose closing backtick landed after the
    # prefix. Both counted as tags before T-3 was enforced; the second one hid a
    # proposal from G7 once it stopped counting.
    check("broken: G6 flags the bare mention and the misplaced backtick",
          gate(payload, "G6").get("stats", {}).get("stray_tier_tokens") == 2,
          json.dumps(gate(payload, "G6").get("stats")))

    check("broken: G7 flags the ownerless proposal", "no owner" in t["G7"], t["G7"])
    check("broken: G7 flags the triggerless proposal", "no trigger" in t["G7"], t["G7"])

    check("broken: G8 flags the orphan [T0]", "does not reference a Q-nn" in t["G8"], t["G8"])
    check("broken: G8 flags the register entry missing an owner",
          "missing `owner`" in t["G8"], t["G8"])

    check("broken: G9 flags non-semver version", "not semver" in t["G9"], t["G9"])
    check("broken: G9 flags counts mismatch", "counts.concerns" in t["G9"], t["G9"])

    check("broken: G10 detects the human-edited agent block",
          "edited by a human" in t["G10"], t["G10"])
    check("broken: G10 detects the unhashed agent block",
          "no `hash` attribute" in t["G10"], t["G10"])

    check("broken: G11 flags the missing migration section",
          "L3.8" in t["G11"], t["G11"])
    check("broken: G11 flags the missing as-is/to-be markers",
          "AS-IS" in t["G11"], t["G11"])

    check("broken: G12 flags the dangling ADR reference", "ADR-999" in t["G12"], t["G12"])
    check("broken: G12 flags the trade-off table with no ADR column",
          "no ADR column" in t["G12"], t["G12"])
    check("broken: G12 flags the ADR with no front matter",
          "no YAML front matter" in t["G12"], t["G12"])


def test_drift(work: Path, repo: Path, baseline: str, later: str) -> None:
    docs = work / "docs-clean"
    code, payload = run_cli(["--docs", str(docs), "--repo", str(repo),
                             "--at", later, "--gates", "G1"])
    drift = payload.get("drift", {})
    check("drift: exit code 3", code == 3, f"got {code}, drift={drift}")
    check("drift: literal change detected", drift.get("value_changed", 0) >= 1,
          json.dumps(drift))
    check("drift: moved symbol detected", drift.get("moved", 0) >= 1, json.dumps(drift))
    check("drift: findings are warnings, not baseline failures",
          gate(payload, "G1")["status"] == "warn"
          and "DRIFT" in summaries(gate(payload, "G1")),
          summaries(gate(payload, "G1")))


def test_stamp(work: Path, repo: Path, baseline: str) -> None:
    docs = work / "docs-stamp"
    build_broken_docs(docs, baseline)

    _, payload = run_cli(["--docs", str(docs), "--repo", str(repo), "--gates", "G10"])
    before = gate(payload, "G10").get("stats", {})
    check("stamp: pre-stamp mismatch present",
          before.get("mismatched") == 1 and before.get("unhashed") == 1,
          json.dumps(before))

    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main(["stamp", "--docs", str(docs)])
    check("stamp: exits 0", rc == 0, buf.getvalue())

    _, payload = run_cli(["--docs", str(docs), "--repo", str(repo), "--gates", "G10"])
    after = gate(payload, "G10").get("stats", {})
    check("stamp: hashes reconciled afterwards",
          after.get("mismatched") == 0 and after.get("unhashed") == 0,
          json.dumps(after))


def test_subcommands(work: Path, repo: Path) -> None:
    docs = work / "docs-clean"
    bare = run_cli(["--docs", str(docs), "--repo", str(repo), "--gates", "G9"])
    named = run_cli(["check", "--docs", str(docs), "--repo", str(repo), "--gates", "G9"])
    check("subcommands: bare invocation defaults to `check`",
          bare[0] == named[0] and bare[1]["gates"] == named[1]["gates"],
          f"{bare[0]} vs {named[0]}")

    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main(["xrefs", "--dir", str(Path(__file__).resolve().parents[3])])
    check("subcommands: `limen xrefs` runs and finds no broken references",
          rc == 0 and "0 broken reference" in buf.getvalue(), buf.getvalue()[-200:])

    # The lmn alias must resolve the package through a symlink, including one
    # made from outside the repo (~/.local/bin/lmn -> bin/limen).
    import os
    import subprocess
    import tempfile
    entry = Path(__file__).resolve().parents[1] / "bin" / "limen"
    alias = Path(__file__).resolve().parents[1] / "bin" / "lmn"
    check("alias: bin/lmn is a symlink to bin/limen",
          alias.is_symlink() and alias.resolve() == entry.resolve(),
          f"{alias} -> {alias.resolve() if alias.exists() else 'missing'}")
    with tempfile.TemporaryDirectory(prefix="limen-alias-") as tmp:
        far = Path(tmp) / "lmn"
        os.symlink(entry, far)
        proc = subprocess.run([sys.executable, str(far), "--version"],
                              capture_output=True, text=True)
        check("alias: resolves through an out-of-tree symlink",
              proc.returncode == 0 and "limen" in proc.stdout,
              (proc.stdout + proc.stderr)[-200:])


def test_example(work: Path, repo: Path) -> None:
    """The shipped worked example must pass all twelve gates under --strict.

    A conforming document that limen rejects is a bug in limen, and without an
    exemplar in CI that bug gets found by an author instead of the maintainer.
    """
    root = Path(__file__).resolve().parents[3]
    docs = root / "examples" / "limen-hld"
    if not docs.is_dir():
        check("example: examples/limen-hld exists", False, str(docs))
        return
    code, payload = run_cli(["check", "--docs", str(docs), "--repo", str(root),
                             "--strict"])

    # A dirty working tree is a property of the checkout, not of the document,
    # and --strict promotes it to a failure. CI checks out clean so it never
    # fires there; tolerating it here keeps the test usable mid-edit.
    def environmental(gate: dict) -> bool:
        items = gate.get("items", [])
        return bool(items) and all("working tree has uncommitted changes"
                                   in i["summary"] for i in items)

    failing = [g for g in payload["gates"]
               if g["status"] != "pass" and not (g["status"] == "warn"
                                                 and environmental(g))]
    check("example: passes all twelve gates under --strict",
          not failing,
          f"exit {code}; " +
          " ".join(f"{g['id']}={g['status']}" for g in failing) + " :: " +
          " || ".join(summaries(g) for g in failing))


def test_selection(work: Path, repo: Path) -> None:
    docs = work / "docs-clean"
    _, payload = run_cli(["--docs", str(docs), "--repo", str(repo), "--gates", "G4,G5"])
    ran = [g["id"] for g in payload["gates"]]
    check("selection: --gates runs only the requested gates", ran == ["G4", "G5"], str(ran))

    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main(["--docs", str(docs), "--repo", str(repo), "--gates", "G42"])
    check("selection: an unknown gate exits 2", rc == 2, buf.getvalue())


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
    check("formats: sarif is well-formed with an error result", ok, str(sarif)[:200])

    buf = io.StringIO()
    with redirect_stdout(buf):
        main(["--docs", str(docs), "--repo", str(repo), "--gates", "G10"])
    check("formats: text output names the gate", "G10" in buf.getvalue(), buf.getvalue())


# --------------------------------------------------------------------------

def test_resolver_structured() -> None:
    """A dotted path that left the document is missing, not weakly found.

    Regression: `jobs.e2e.if` against a workflow whose `if:` key was deleted
    used to fall through to the identifier layer and match the `if` of a shell
    script inside a `run:` block, reporting a deleted key as merely moved.
    """
    from limen.resolver import resolve

    before = textwrap.dedent("""\
        jobs:
          e2e:
            if: github.event_name == 'push'
            steps:
              - run: npm run test:e2e
        """)
    after = textwrap.dedent("""\
        jobs:
          e2e:
            steps:
              - run: |
                  if [ -z "$VERSION" ]; then exit 1; fi
                  npm run test:e2e
        """)
    path = ".github/workflows/test.yml"

    res = resolve(path, before, "jobs.e2e.if")
    check("resolver: dotted path resolves structurally while it exists",
          res.found and res.method == "structured", f"{res.found} {res.method}")

    res = resolve(path, after, "jobs.e2e.if")
    check("resolver: a deleted dotted path is missing, not identifier-matched",
          not res.found and res.method == "structured",
          f"found={res.found} method={res.method} line={res.line}")

    res = resolve(path, after, "jobs.e2e")
    check("resolver: a surviving dotted path still resolves",
          res.found and res.method == "structured", f"{res.found} {res.method}")

    res = resolve(path, after, "npm")
    check("resolver: a bare symbol still falls through to a textual match",
          res.found and res.method == "identifier", f"{res.found} {res.method}")

    # A literal deep inside a structured node is anchored, not "weakly anchored":
    # the node owns every line indented under it, however many that is.
    from limen.resolver import find_literal

    res = resolve(path, before, "jobs")
    matched, where = find_literal(before, res, "e2e")
    check("resolver: a literal inside a structured node is firmly anchored",
          matched and "outside symbol" not in (where or ""), f"{matched} {where}")

    matched, where = find_literal(before, res, "lint-and-build")
    check("resolver: a literal absent from the node does not match",
          not matched, f"{matched} {where}")

    # A generic class method is still a declaration: `request<T = unknown>(`
    # must not fall through to the identifier layer, which --strict rejects.
    ts = textwrap.dedent("""\
        export class ApiClient {
          protected async request<T = unknown>(
            url: string,
            opts: { timeoutMs?: number } = {}
          ): Promise<T> {
            const { timeoutMs = 30000 } = opts;
          }
        }
        """)
    res = resolve("src/services/api-client.ts", ts, "request")
    check("resolver: a generic TS class method resolves as a declaration",
          res.found and res.method == "declaration", f"{res.found} {res.method}")


def main_tests() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-k", dest="pattern", default="")
    ap.add_argument("--keep", action="store_true")
    args = ap.parse_args()

    work = Path(tempfile.mkdtemp(prefix="limen-tests-"))
    repo = work / "repo"
    repo.mkdir()
    baseline, later = build_repo(repo)
    print(f"workspace: {work}\nbaseline:  {baseline[:12]}\nlater:     {later[:12]}\n")

    cases = [
        ("registration", lambda: test_registration(work, repo, baseline)),
        ("clean", lambda: test_clean(work, repo, baseline)),
        ("clean-strict", lambda: test_clean_strict(work, repo, baseline)),
        ("broken", lambda: test_broken(work, repo, baseline)),
        ("drift", lambda: test_drift(work, repo, baseline, later)),
        ("resolver", lambda: test_resolver_structured()),
        ("stamp", lambda: test_stamp(work, repo, baseline)),
        ("subcommands", lambda: test_subcommands(work, repo)),
        ("example", lambda: test_example(work, repo)),
        ("selection", lambda: test_selection(work, repo)),
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
    if args.keep:
        print(f"\nworkspace kept at {work}")
    else:
        shutil.rmtree(work, ignore_errors=True)
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main_tests())
