#!/usr/bin/env python3
"""End-to-end tests for limen.

Builds a throwaway git repo and document sets over it (clean, broken, and 5.x),
runs the CLI in-process, and asserts on check status, stats and exit codes.

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
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fixtures import (build_broken_docs, build_clean_docs, build_repo,  # noqa: E402
                      build_v5_docs, front_matter)
from limen.cli import CHECKS, main  # noqa: E402

FAILURES: list[str] = []
PASSES = 0
ROOT = Path(__file__).resolve().parents[3]


def check(label: str, condition: bool, detail: str = "") -> None:
    global PASSES
    if condition:
        PASSES += 1
        print(f"  ok   {label}")
    else:
        FAILURES.append(label)
        print(f"  FAIL {label}" + (f"\n         {detail}" if detail else ""))


def result(payload: dict, check_id: str) -> dict:
    for c in payload["checks"]:
        if c["id"] == check_id:
            return c
    return {"id": check_id, "status": "(absent)", "items": []}


def summaries(c: dict) -> str:
    return " | ".join(i["summary"] for i in c.get("items", []))


def run_cli(argv: list[str]) -> tuple[int, dict]:
    buf = io.StringIO()
    with redirect_stdout(buf), redirect_stderr(io.StringIO()):
        code = main([*argv, "--format", "json"])
    try:
        return code, json.loads(buf.getvalue())
    except json.JSONDecodeError:
        return code, {"checks": [], "summary": {}, "_raw": buf.getvalue()}


def run_raw(argv: list[str]) -> tuple[int, str]:
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue() + err.getvalue()


# --------------------------------------------------------------------------

def test_registration(work: Path, repo: Path, baseline: str) -> None:
    check("registry: the five checks, in order",
          CHECKS == ["pointers", "diagrams", "ownership", "uncertainty", "decisions"],
          str(CHECKS))
    docs = work / "docs-clean"
    _, payload = run_cli(["--docs", str(docs), "--repo", str(repo)])
    ran = [c["id"] for c in payload["checks"]]
    check("registry: a default run executes all five", ran == CHECKS, str(ran))


def test_clean(work: Path, repo: Path, baseline: str) -> None:
    docs = work / "docs-clean"
    code, payload = run_cli(["--docs", str(docs), "--repo", str(repo)])
    for cid in CHECKS:
        c = result(payload, cid)
        check(f"clean: {cid} passes", c["status"] == "pass",
              f"status={c['status']} :: {summaries(c)}")
    check("clean: exit code 0", code == 0, f"got {code}")

    stats = result(payload, "pointers").get("stats", {})
    check("clean: every pointer resolved",
          stats.get("resolved") == stats.get("total") == 7,
          json.dumps(stats))
    stats = result(payload, "ownership").get("stats", {})
    check("clean: the lock records agent sections and one person's section",
          stats.get("agent", 0) >= 6 and stats.get("human") == 1
          and stats.get("changed") == 0, json.dumps(stats))
    stats = result(payload, "uncertainty").get("stats", {})
    check("clean: unknowns, proposals and questions counted",
          stats.get("unknown") == 2 and stats.get("proposed") == 1
          and stats.get("questions") == 2, json.dumps(stats))
    stats = result(payload, "decisions").get("stats", {})
    check("clean: both ADRs resolve, whatever their format",
          stats.get("cited") == 2 and stats.get("dangling") == 0, json.dumps(stats))
    stats = result(payload, "diagrams").get("stats", {})
    check("clean: the ignored diagram is not rendered",
          stats.get("diagrams") == 1, json.dumps(stats))


def test_clean_strict(work: Path, repo: Path, baseline: str) -> None:
    docs = work / "docs-clean"
    code, payload = run_cli(["--docs", str(docs), "--repo", str(repo), "--strict"])
    noisy = [c for c in payload["checks"] if c["status"] != "pass"]
    check("clean: survives --strict", code == 0 and not noisy,
          f"exit {code}; " + " || ".join(f"{c['id']}: {summaries(c)}" for c in noisy))


def test_broken(work: Path, repo: Path, baseline: str) -> None:
    docs = work / "docs-broken"
    code, payload = run_cli(["--docs", str(docs), "--repo", str(repo)])
    check("broken: exit code 1", code == 1, f"got {code}")
    for cid in CHECKS:
        c = result(payload, cid)
        check(f"broken: {cid} fails", c["status"] == "fail",
              f"status={c['status']} :: {summaries(c)}")

    t = {cid: summaries(result(payload, cid)) for cid in CHECKS}
    check("broken: pointers flags a missing symbol", "NoSuchConstant" in t["pointers"],
          t["pointers"])
    check("broken: pointers flags a literal mismatch", "literal mismatch" in t["pointers"],
          t["pointers"])
    check("broken: pointers flags a mixed baseline", "deadbee" in t["pointers"],
          t["pointers"])
    check("broken: pointers flags a file:// pointer", "file:// URI" in t["pointers"],
          t["pointers"])
    check("broken: pointers warns on a whole-file pointer",
          "whole-file pointer" in t["pointers"], t["pointers"])
    stats = result(payload, "pointers").get("stats", {})
    check("broken: pointers flags a verified claim with nothing behind it",
          stats.get("verified_without_basis") == 1, json.dumps(stats))

    stats = result(payload, "diagrams").get("stats", {})
    check("broken: diagrams honours limen:ignore-diagram", stats.get("diagrams") == 1,
          json.dumps(stats))
    check("broken: diagrams reports the render failure", "render failed" in t["diagrams"],
          t["diagrams"])

    check("broken: ownership names the section a person changed",
          "'Edited later' changed after it was stamped" in t["ownership"],
          t["ownership"])

    stats = result(payload, "uncertainty").get("stats", {})
    # A bare mention, a misplaced backtick, and a 5.x tag.
    check("broken: uncertainty flags three malformed tags",
          stats.get("stray_tags") == 3, json.dumps(stats))
    check("broken: uncertainty names the 5.x tag", "5.x tag `[T1]`" in t["uncertainty"],
          t["uncertainty"])
    check("broken: uncertainty flags the unknown with no question",
          stats.get("unknown_without_question") == 1, json.dumps(stats))
    check("broken: uncertainty flags the undefined question",
          "Q-07 is referenced" in t["uncertainty"], t["uncertainty"])
    check("broken: uncertainty flags the ownerless proposal",
          stats.get("proposed_without_owner") == 1, json.dumps(stats))
    check("broken: uncertainty flags both triggerless proposals, including 'when needed'",
          stats.get("proposed_without_trigger") == 2, json.dumps(stats))

    check("broken: decisions flags the missing ADR", "ADR-999" in t["decisions"],
          t["decisions"])
    check("broken: decisions accepts the ADR that exists", "ADR-011" not in t["decisions"],
          t["decisions"])


def test_drift(work: Path, repo: Path, baseline: str, later: str) -> None:
    docs = work / "docs-clean"
    code, payload = run_cli(["--docs", str(docs), "--repo", str(repo),
                             "--at", later, "--checks", "pointers"])
    drift = payload.get("drift", {})
    check("drift: exit code 3", code == 3, f"got {code}, drift={drift}")
    check("drift: literal change detected", drift.get("value_changed", 0) >= 1,
          json.dumps(drift))
    check("drift: moved symbol detected", drift.get("moved", 0) >= 1, json.dumps(drift))
    c = result(payload, "pointers")
    check("drift: findings are warnings, not baseline failures",
          c["status"] == "warn" and "DRIFT" in summaries(c), summaries(c))


def test_greenfield(work: Path, repo: Path) -> None:
    docs = work / "docs-greenfield"
    docs.mkdir()
    (docs / "hld.md").write_text(
        front_matter(None, mode="greenfield")
        + "\n# New thing\n\n## Plan\n\nThe service will accept uploads `[proposed]`, "
          "owner @lead, trigger: funding approved.\n")
    _, payload = run_cli(["--docs", str(docs), "--repo", str(repo),
                          "--checks", "pointers,uncertainty"])
    c = result(payload, "pointers")
    check("greenfield: no pointers and no baseline is fine",
          c["status"] == "pass" and "greenfield" in c.get("detail", ""), json.dumps(c))

    (docs / "hld.md").write_text(front_matter(None) + "\n# Old thing\n")
    _, payload = run_cli(["--docs", str(docs), "--repo", str(repo), "--checks", "pointers"])
    check("greenfield: a brownfield document without a baseline fails",
          "needs a `baseline`" in summaries(result(payload, "pointers")),
          summaries(result(payload, "pointers")))

    # A shallow CI clone lacks the baseline commit. That must fail, because a
    # pass would be indistinguishable from a real one to whoever reads the badge.
    absent = "0123456789abcdef0123456789abcdef01234567"
    (docs / "hld.md").write_text(
        front_matter(absent) + "\n# Old thing\n\n## Limits\n\n- Parts are capped "
        f"`[verified]` (`internal/ingest/limits.go@{absent[:7]}::MaxPartBytes`).\n")
    _, payload = run_cli(["--docs", str(docs), "--repo", str(repo), "--checks", "pointers"])
    check("greenfield: a baseline missing from the repository fails, not passes",
          result(payload, "pointers")["status"] == "fail"
          and "not in this repository" in summaries(result(payload, "pointers")),
          json.dumps(result(payload, "pointers")))


def test_stamp(work: Path, repo: Path, baseline: str) -> None:
    docs = work / "docs-stamp"
    build_clean_docs(docs, baseline)
    (docs / ".limen-lock.yaml").unlink()

    _, payload = run_cli(["--docs", str(docs), "--repo", str(repo),
                          "--checks", "ownership"])
    check("stamp: no lock is a warning", result(payload, "ownership")["status"] == "warn",
          summaries(result(payload, "ownership")))

    code, out = run_raw(["stamp", "--docs", str(docs)])
    check("stamp: no flags is a usage error", code == 2, out)

    code, out = run_raw(["stamp", "--docs", str(docs), "--all"])
    check("stamp: --all records a new document", code == 0 and "recorded" in out, out)
    code, out = run_raw(["stamp", "--docs", str(docs), "--all"])
    check("stamp: --all refuses a document that already has a lock", code == 1, out)

    hld = docs / "hld.md"
    hld.write_text(hld.read_text().replace("Sizing re-checked", "Sizing re-checked twice"))
    _, payload = run_cli(["--docs", str(docs), "--repo", str(repo),
                          "--checks", "ownership"])
    check("stamp: an edit after stamping fails ownership",
          result(payload, "ownership")["status"] == "fail",
          summaries(result(payload, "ownership")))

    code, out = run_raw(["stamp", "--docs", str(docs), "--human", "Reviewer notes"])
    check("stamp: --human records a person's section", code == 0, out)
    _, payload = run_cli(["--docs", str(docs), "--repo", str(repo),
                          "--checks", "ownership"])
    check("stamp: a person's section may change freely",
          result(payload, "ownership")["status"] == "pass",
          summaries(result(payload, "ownership")))

    code, out = run_raw(["stamp", "--docs", str(docs), "--mine", "Reviewer notes"])
    check("stamp: --mine refuses a person's section",
          code == 1 and "recorded as a person's" in out, out)

    hld.write_text(hld.read_text().replace("tracked as `Q-01`.", "tracked as `Q-01`, "
                                                                 "and blocks sizing."))
    code, out = run_raw(["stamp", "--docs", str(docs), "--mine", "hld.md#Risks and open questions"])
    _, payload = run_cli(["--docs", str(docs), "--repo", str(repo),
                          "--checks", "ownership"])
    check("stamp: --mine with file#heading accepts the agent's own edit",
          code == 0 and result(payload, "ownership")["status"] == "pass",
          out + summaries(result(payload, "ownership")))

    code, out = run_raw(["stamp", "--docs", str(docs), "--mine", "No such heading"])
    check("stamp: an unknown heading is refused", code == 1 and "no section" in out, out)

    (docs / "more.md").write_text("# More\n\n## Summary\n\nA second summary.\n")
    code, out = run_raw(["stamp", "--docs", str(docs), "--mine", "Summary"])
    check("stamp: an ambiguous heading asks for file#heading",
          code == 1 and "more than one section" in out, out)


def test_migrate(work: Path, repo: Path, baseline: str) -> None:
    docs = work / "docs-v5-migrate"
    build_v5_docs(docs, baseline)
    before = (docs / "01-intake.md").read_text()

    code, out = run_raw(["migrate", "--docs", str(docs), "--dry-run"])
    check("migrate: --dry-run writes nothing",
          code == 0 and (docs / "01-intake.md").read_text() == before
          and not (docs / ".limen-lock.yaml").exists(), out)

    code, out = run_raw(["migrate", "--docs", str(docs)])
    text = (docs / "01-intake.md").read_text()
    check("migrate: exits 0", code == 0, out)
    check("migrate: tags rewritten",
          "`[verified]`" in text and "`[unknown]`" in text and "`[proposed]`" in text
          and "`[inferred]`" in text and "[T1]" not in text, text[:400])
    check("migrate: ownership markers and retired comments removed",
          "agent:begin" not in text and "human:begin" not in text
          and "frames:" not in text and "c4:" not in text, text)
    check("migrate: front matter rewritten",
          "mode: brownfield\n" in text and f"baseline: {baseline}" in text
          and "counts:" not in text and "profile:" not in text and "repo:" not in text,
          text[:400])
    check("migrate: says what brownfield-change leaves to do", "Proposed change" in out, out)

    lock_text = (docs / ".limen-lock.yaml").read_text()
    check("migrate: an intact agent block becomes an agent section",
          "L1.4 Quality scenarios: sha256:" in lock_text, lock_text)
    check("migrate: a block a person edited becomes theirs",
          "L2.1 Components: human" in lock_text, lock_text)
    check("migrate: a human block stays a person's",
          "Reviewer notes: human" in lock_text, lock_text)

    code, payload = run_cli(["--docs", str(docs), "--repo", str(repo)])
    failing = [c for c in payload["checks"] if c["status"] == "fail"]
    check("migrate: the migrated document passes every check",
          code == 0 and not failing,
          f"exit {code}; " + " || ".join(f"{c['id']}: {summaries(c)}" for c in failing))

    code, out = run_raw(["migrate", "--docs", str(docs)])
    check("migrate: a second run has nothing to do", "nothing to migrate" in out, out)


def test_legacy(work: Path, repo: Path, baseline: str) -> None:
    docs = work / "docs-v5-legacy"
    build_v5_docs(docs, baseline)
    plain = ["--docs", str(docs), "--repo", str(repo),
             "--checks", "pointers,uncertainty,ownership,decisions"]

    _, payload = run_cli(plain)
    check("legacy: without --legacy a 5.x mode fails pointers",
          "5.x mode" in summaries(result(payload, "pointers")),
          summaries(result(payload, "pointers")))
    check("legacy: without --legacy 5.x tags fail uncertainty",
          "5.x tag" in summaries(result(payload, "uncertainty")),
          summaries(result(payload, "uncertainty")))

    _, payload = run_cli([*plain, "--legacy"])
    check("legacy: --legacy reads the 5.x tags and front matter",
          result(payload, "pointers")["status"] == "pass"
          and result(payload, "uncertainty")["status"] == "pass",
          summaries(result(payload, "pointers")) + summaries(result(payload, "uncertainty")))
    check("legacy: --legacy still reports the block a person edited",
          "'L2.1 Components' changed" in summaries(result(payload, "ownership")),
          summaries(result(payload, "ownership")))
    check("legacy: --legacy writes nothing", not (docs / ".limen-lock.yaml").exists()
          and "[T1]" in (docs / "01-intake.md").read_text())


def test_selection(work: Path, repo: Path) -> None:
    docs = work / "docs-clean"
    _, payload = run_cli(["--docs", str(docs), "--repo", str(repo),
                          "--checks", "uncertainty,pointers"])
    ran = [c["id"] for c in payload["checks"]]
    check("selection: --checks runs the named checks in standard order",
          ran == ["pointers", "uncertainty"], str(ran))

    _, payload = run_cli(["--docs", str(docs), "--repo", str(repo), "--gates", "G1,G4"])
    ran = [c["id"] for c in payload["checks"]]
    check("selection: a 5.x gate id maps to its check; a retired one is skipped",
          ran == ["pointers"], str(ran))

    code, out = run_raw(["--docs", str(docs), "--repo", str(repo), "--gates", "G4"])
    check("selection: only retired gates is an error, not a vacuous pass",
          code == 2 and "retired" in out, out)
    code, out = run_raw(["--docs", str(docs), "--repo", str(repo), "--checks", "bogus"])
    check("selection: an unknown check exits 2", code == 2, out)


def test_formats(work: Path, repo: Path) -> None:
    docs = work / "docs-broken"
    code, out = run_raw(["--docs", str(docs), "--repo", str(repo),
                         "--checks", "ownership", "--format", "sarif"])
    try:
        sarif = json.loads(out)
        ok = sarif["runs"][0]["results"][0]["level"] == "error"
    except Exception as exc:  # noqa: BLE001
        ok, sarif = False, str(exc)
    check("formats: sarif is well-formed with an error result", ok, str(sarif)[:200])

    code, out = run_raw(["--docs", str(docs), "--repo", str(repo),
                         "--checks", "ownership"])
    check("formats: text output names the check", "ownership" in out, out)


def test_resolver() -> None:
    """A dotted path that left the document is missing, not weakly found.

    Regression: `jobs.e2e.if` against a workflow whose `if:` key was deleted
    used to fall through to the identifier layer and match the `if` of a shell
    script inside a `run:` block, reporting a deleted key as merely moved.
    """
    from limen.resolver import find_literal, resolve

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


def test_subcommands(work: Path, repo: Path) -> None:
    docs = work / "docs-clean"
    bare = run_cli(["--docs", str(docs), "--repo", str(repo), "--checks", "decisions"])
    named = run_cli(["check", "--docs", str(docs), "--repo", str(repo),
                     "--checks", "decisions"])
    check("subcommands: bare invocation defaults to `check`",
          bare[0] == named[0] and bare[1]["checks"] == named[1]["checks"],
          f"{bare[0]} vs {named[0]}")

    code, out = run_raw(["xrefs", "--dir", str(ROOT)])
    check("subcommands: `limen xrefs` finds no broken references in the standard",
          code == 0 and "0 broken reference" in out, out[-400:])

    # The lmn alias must resolve the package through a symlink, including one
    # made from outside the repo (~/.local/bin/lmn -> bin/limen).
    import os
    import subprocess
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
    """The shipped example must pass every check under --strict.

    A conforming document that limen rejects is a bug in limen, and without an
    exemplar under test that bug is found by an author instead of the maintainer.
    """
    docs = ROOT / "examples" / "limen-hld"
    if not docs.is_dir():
        check("example: examples/limen-hld exists", False, str(docs))
        return
    code, payload = run_cli(["check", "--docs", str(docs), "--repo", str(ROOT),
                             "--strict"])
    failing = [c for c in payload["checks"] if c["status"] != "pass"]
    check("example: passes every check under --strict", code == 0 and not failing,
          f"exit {code}; " + " || ".join(f"{c['id']}: {summaries(c)}" for c in failing)
          + payload.get("_raw", ""))


def main_tests() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-k", dest="pattern", default="")
    ap.add_argument("--keep", action="store_true")
    args = ap.parse_args()

    work = Path(tempfile.mkdtemp(prefix="limen-tests-"))
    repo = work / "repo"
    repo.mkdir()
    baseline, later = build_repo(repo)
    build_clean_docs(work / "docs-clean", baseline)
    build_broken_docs(work / "docs-broken", baseline)
    print(f"workspace: {work}\nbaseline:  {baseline[:12]}\nlater:     {later[:12]}\n")

    cases = [
        ("registration", lambda: test_registration(work, repo, baseline)),
        ("clean", lambda: test_clean(work, repo, baseline)),
        ("clean-strict", lambda: test_clean_strict(work, repo, baseline)),
        ("broken", lambda: test_broken(work, repo, baseline)),
        ("drift", lambda: test_drift(work, repo, baseline, later)),
        ("greenfield", lambda: test_greenfield(work, repo)),
        ("stamp", lambda: test_stamp(work, repo, baseline)),
        ("migrate", lambda: test_migrate(work, repo, baseline)),
        ("legacy", lambda: test_legacy(work, repo, baseline)),
        ("selection", lambda: test_selection(work, repo)),
        ("formats", lambda: test_formats(work, repo)),
        ("resolver", test_resolver),
        ("subcommands", lambda: test_subcommands(work, repo)),
        ("example", lambda: test_example(work, repo)),
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
