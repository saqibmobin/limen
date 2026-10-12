"""limen CLI (LIMEN.md §9).

Exit codes:
  0  every selected check passed
  1  a check failed (or warned, under --strict)
  2  the validator could not run
  3  checks passed but drift was detected against --at
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__, docset, lock, migrate, xrefs
from .checks import decisions, diagrams, ownership, pointers, uncertainty
from .gitio import Git
from .model import FAIL, SKIP, WARN, CheckError, CheckResult
from .report import render_json, render_sarif, render_text

CHECKS = ["pointers", "diagrams", "ownership", "uncertainty", "decisions"]

# 5.x gate ids, so existing CI invocations keep working for one minor version.
GATE_ALIASES = {"G1": "pointers", "G2": "diagrams", "G6": "uncertainty",
                "G7": "uncertainty", "G8": "uncertainty", "G9": "pointers",
                "G10": "ownership", "G12": "decisions"}
RETIRED_GATES = {"G3", "G4", "G5", "G11"}

EXIT_OK, EXIT_FAILURE, EXIT_ERROR, EXIT_DRIFT = 0, 1, 2, 3

SUBCOMMANDS = ("check", "stamp", "migrate", "xrefs")
GLOBAL_FLAGS = ("-h", "--help", "--version")


def _add_docs_arg(p: argparse.ArgumentParser) -> None:
    p.add_argument("--docs", default="docs/architecture", type=Path,
                   help="HLD directory or single markdown file "
                        "(default: docs/architecture)")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="limen",
        description="Check an HLD written to the Limen standard (LIMEN.md).",
        epilog=f"Checks: {', '.join(CHECKS)}. "
               "`limen` with no subcommand runs `limen check`.",
    )
    p.add_argument("--version", action="version", version=f"limen {__version__}")
    subs = p.add_subparsers(dest="command")

    check = subs.add_parser("check", help="run the checks against a document set")
    _add_docs_arg(check)
    check.add_argument("--repo", default=".", type=Path,
                       help="git repository the pointers refer to (default: .)")
    check.add_argument("--at", metavar="REV",
                       help="also resolve pointers at this revision and report drift")
    check.add_argument("--checks", metavar="LIST",
                       help=f"comma-separated subset (default: {','.join(CHECKS)})")
    check.add_argument("--gates", metavar="LIST", help=argparse.SUPPRESS)
    check.add_argument("--strict", action="store_true",
                       help="treat warnings as failures")
    check.add_argument("--legacy", action="store_true",
                       help="read a 5.x document: old tags, modes, front matter and "
                            "ownership markers")
    check.add_argument("--format", choices=("text", "json", "sarif"), default="text")
    check.add_argument("-v", "--verbose", action="store_true",
                       help="show passing items in text output")
    check.add_argument("--mmdc", metavar="CMD",
                       help="mermaid-cli command override (also read from $MMDC)")
    check.add_argument("--no-cache", action="store_true",
                       help="ignore the diagram render cache")
    check.add_argument("--jobs", type=int, default=4,
                       help="parallel diagram renders (default: 4)")
    check.add_argument("--timeout", type=int, default=120,
                       help="per-diagram render timeout in seconds (default: 120)")

    stamp = subs.add_parser(
        "stamp", help="record who wrote which sections, in .limen-lock.yaml",
        description="Attribute sections in .limen-lock.yaml. Claim only sections "
                    "you wrote in this run: a section a person changed is theirs "
                    "(LIMEN.md §8.3). Headings are given exactly as written, as "
                    "'Heading' or 'file.md#Heading'.")
    _add_docs_arg(stamp)
    stamp.add_argument("--all", dest="new", action="store_true",
                       help="record every section of a newly written document as "
                            "the agent's")
    stamp.add_argument("--mine", action="append", default=[], metavar="HEADING",
                       help="a section the agent wrote or edited in this run")
    stamp.add_argument("--human", action="append", default=[], metavar="HEADING",
                       help="a section a person owns; agents stop editing it")

    mig = subs.add_parser("migrate", help="convert a 5.x document set to 6.0, in place")
    _add_docs_arg(mig)
    mig.add_argument("--dry-run", action="store_true",
                     help="report what would change without writing")

    xr = subs.add_parser("xrefs", help="validate section references in the standard")
    xr.add_argument("--dir", default=".", type=Path,
                    help="directory holding LIMEN.md (default: .)")
    return p


def normalize_argv(argv: list[str]) -> list[str]:
    """Bare `limen --docs x` means `limen check --docs x`."""
    if not argv:
        return ["check"]
    if argv[0] in SUBCOMMANDS or argv[0] in GLOBAL_FLAGS:
        return list(argv)
    return ["check", *argv]


def select(checks: str | None, gates: str | None) -> list[str]:
    if not checks and not gates:
        return list(CHECKS)
    wanted: list[str] = []
    for raw in (checks or "").split(","):
        if name := raw.strip().lower():
            if name not in CHECKS:
                raise CheckError(f"unknown check '{name}'; expected one of "
                                 f"{', '.join(CHECKS)}")
            wanted.append(name)
    retired: list[str] = []
    for raw in (gates or "").split(","):
        if gid := raw.strip().upper():
            if gid in RETIRED_GATES:
                retired.append(gid)
            elif gid in GATE_ALIASES:
                wanted.append(GATE_ALIASES[gid])
            else:
                raise CheckError(f"unknown gate '{gid}'")
    if retired:
        print(f"limen: {', '.join(retired)} retired in 6.0; nothing runs in "
              "their place", file=sys.stderr)
    selected = [c for c in CHECKS if c in wanted]
    if not selected:
        raise CheckError("nothing to run")
    return selected


def main(argv: list[str] | None = None) -> int:
    argv = normalize_argv(list(sys.argv[1:] if argv is None else argv))
    args = build_parser().parse_args(argv)

    if args.command == "xrefs":
        return xrefs.run(args.dir)

    try:
        docs = docset.load(args.docs)
    except CheckError as exc:
        print(f"limen: {exc}", file=sys.stderr)
        return EXIT_ERROR

    if args.command == "stamp":
        return _stamp(docs, args)
    if args.command == "migrate":
        return _migrate(docs, args)
    return _check(docs, args)


def _stamp(docs: docset.DocSet, args) -> int:
    if not (args.new or args.mine or args.human):
        print("limen stamp: say whose sections these are: --all for a document you "
              "just wrote, --mine HEADING for sections you edited in this run, "
              "--human HEADING for a person's", file=sys.stderr)
        return EXIT_ERROR
    try:
        changes = lock.stamp(docs, mine=args.mine, human=args.human, new=args.new)
    except lock.StampError as exc:
        print(f"limen stamp: {exc}", file=sys.stderr)
        return EXIT_FAILURE
    for line in changes:
        print(line)
    return EXIT_OK


def _migrate(docs: docset.DocSet, args) -> int:
    notes = migrate.migrate(docs, write=not args.dry_run)
    if not notes:
        print("nothing to migrate: no 5.x forms found")
        return EXIT_OK
    for line in notes:
        print(("would: " if args.dry_run and line.startswith(("rewrote", "wrote"))
               else "") + line)
    if not args.dry_run:
        print("\nnext: run `limen check` and fix what it reports")
    return EXIT_OK


def _check(docs: docset.DocSet, args) -> int:
    try:
        selected = select(args.checks, args.gates)
    except CheckError as exc:
        print(f"limen: {exc}", file=sys.stderr)
        return EXIT_ERROR

    notes: list[str] = []
    if args.legacy:
        notes = migrate.legacy_view(docs)

    git: Git | None = None
    if "pointers" in selected:
        try:
            git = Git(args.repo)
        except CheckError as exc:
            print(f"limen: {exc}", file=sys.stderr)
            return EXIT_ERROR

    results: list[CheckResult] = []
    drift = {"resolved": 0, "moved": 0, "missing": 0, "value_changed": 0}
    try:
        for name in selected:
            if name == "pointers":
                result, drift = pointers.run(docs, git, at=args.at, strict=args.strict)
            elif name == "diagrams":
                result = diagrams.run(docs, mmdc=args.mmdc, strict=args.strict,
                                      use_cache=not args.no_cache, jobs=args.jobs,
                                      timeout=args.timeout)
            elif name == "ownership":
                result = ownership.run(docs, strict=args.strict)
            elif name == "uncertainty":
                result = uncertainty.run(docs, strict=args.strict)
            else:
                result = decisions.run(docs, strict=args.strict)
            results.append(result)
    except CheckError as exc:
        print(f"limen: {exc}", file=sys.stderr)
        return EXIT_ERROR

    evaluated = None
    if args.at and git is not None:
        evaluated = git.rev_parse(args.at) or args.at

    payload = {
        "doc": str(docs.front.get("title") or docs.front.get("id") or "(untitled)"),
        "version": str(docs.front.get("version") or "0.0.0"),
        "mode": docs.mode or None,
        "baseline": docs.baseline or "(none)",
        "evaluated_at": evaluated or docs.baseline or "(none)",
        "legacy": args.legacy,
        "notes": notes,
        "checks": [r.to_dict(include_passing=args.verbose) for r in results],
        "drift": drift,
        "summary": {
            "passed": sum(1 for r in results if r.status == "pass"),
            "failed": sum(1 for r in results if r.status == FAIL),
            "warned": sum(1 for r in results if r.status == WARN),
            "skipped": sum(1 for r in results if r.status == SKIP),
        },
    }

    if args.format == "json":
        render_json(payload)
    elif args.format == "sarif":
        render_sarif(payload, results)
    else:
        render_text(payload, results, verbose=args.verbose)

    if any(r.status == FAIL for r in results):
        return EXIT_FAILURE
    if args.strict and any(r.status == WARN for r in results):
        return EXIT_FAILURE
    if any(drift[k] for k in ("moved", "missing", "value_changed")):
        return EXIT_DRIFT
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
