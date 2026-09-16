"""limen CLI — STD-LIMEN-03 §6.

Exit codes:
  0  all selected gates passed
  1  a gate failed
  2  the validator could not run
  3  gates passed but drift was detected against --at
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__, docset, xrefs
from .gates import (
    g1_provenance, g2_diagrams, g3_consistency, g4_concerns, g5_scenarios,
    g6_tiers, g7_proposals, g8_questions, g9_frontmatter, g10_blocks,
    g11_mode, g12_adr,
)
from .gitio import Git
from .model import FAIL, SKIP, WARN, CheckError, GateResult
from .report import render_json, render_sarif, render_text

IMPLEMENTED = ["G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8", "G9", "G10",
               "G11", "G12"]
PLANNED: list[str] = []

EXIT_OK, EXIT_GATE_FAILURE, EXIT_ERROR, EXIT_DRIFT = 0, 1, 2, 3


SUBCOMMANDS = ("check", "stamp", "xrefs")
GLOBAL_FLAGS = ("-h", "--help", "--version")


def _add_check_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--docs", default="docs/architecture", type=Path,
                   help="HLD directory or single markdown file "
                        "(default: docs/architecture)")
    p.add_argument("--repo", default=".", type=Path,
                   help="git repository the provenance pointers refer to (default: .)")
    p.add_argument("--at", metavar="REV",
                   help="also resolve pointers at this revision and report drift")
    p.add_argument("--gates", metavar="LIST",
                   help=f"comma-separated subset, e.g. G1,G9 "
                        f"(default: {','.join(IMPLEMENTED)})")
    p.add_argument("--strict", action="store_true",
                   help="treat partial/advisory findings as failures")
    p.add_argument("--format", choices=("text", "json", "sarif"), default="text")
    p.add_argument("-v", "--verbose", action="store_true",
                   help="show passing checks in text output")
    p.add_argument("--min-resolution", type=float,
                   default=g1_provenance.DEFAULT_MIN_RESOLUTION,
                   help="G1 resolution threshold (default: 0.95)")
    p.add_argument("--mmdc", metavar="CMD",
                   help="mermaid-cli command override (also read from $MMDC)")
    p.add_argument("--no-cache", action="store_true",
                   help="ignore the diagram render cache")
    p.add_argument("--jobs", type=int, default=4,
                   help="parallel diagram renders (default: 4)")
    p.add_argument("--timeout", type=int, default=120,
                   help="per-diagram render timeout in seconds (default: 120)")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="limen",
        description="Validate an HLD document set against STD-LIMEN-03 hard gates.",
        epilog=f"Gates: {', '.join(IMPLEMENTED)}. "
               f"`limen` with no subcommand runs `limen check`.",
    )
    p.add_argument("--version", action="version", version=f"limen {__version__}")
    subs = p.add_subparsers(dest="command")

    check = subs.add_parser("check", help="run the hard gates against a document set")
    _add_check_args(check)

    stamp = subs.add_parser(
        "stamp",
        help="recompute agent:begin block hashes in place",
        description="Run this immediately after authoring agent blocks — never to "
                    "clear a G10 mismatch, which would destroy the human edit the "
                    "mismatch is reporting (STD-LIMEN-01 U-2).")
    stamp.add_argument("--docs", default="docs/architecture", type=Path,
                       help="HLD directory or single markdown file")

    xr = subs.add_parser("xrefs",
                         help="validate internal cross-references in the standards")
    xr.add_argument("--dir", default=".", type=Path,
                    help="directory holding the three STD-LIMEN documents")
    return p


def normalize_argv(argv: list[str]) -> list[str]:
    """Bare `limen --docs x` means `limen check --docs x`."""
    if not argv:
        return ["check"]
    if argv[0] in SUBCOMMANDS or argv[0] in GLOBAL_FLAGS:
        return list(argv)
    return ["check", *argv]


def select(requested: str | None) -> list[str]:
    if not requested:
        return list(IMPLEMENTED)
    wanted = [g.strip().upper() for g in requested.split(",") if g.strip()]
    unknown = [g for g in wanted if g not in IMPLEMENTED + PLANNED]
    if unknown:
        raise CheckError(f"unknown gate(s): {', '.join(unknown)}")
    not_yet = [g for g in wanted if g in PLANNED]
    if not_yet:
        print(f"note: {', '.join(not_yet)} not implemented yet; skipping",
              file=sys.stderr)
    return [g for g in wanted if g in IMPLEMENTED]


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
        changed = g10_blocks.stamp(docs)
        for line in changed:
            print(f"stamped {line}")
        print(f"{len(changed)} agent block hash(es) updated.")
        return EXIT_OK

    try:
        selected = select(args.gates)
    except CheckError as exc:
        print(f"limen: {exc}", file=sys.stderr)
        return EXIT_ERROR

    git: Git | None = None
    if {"G1", "G9"} & set(selected):
        try:
            git = Git(args.repo)
        except CheckError as exc:
            if "G1" in selected:
                print(f"limen: {exc}", file=sys.stderr)
                return EXIT_ERROR
            print(f"limen: {exc} (G9 repo checks reduced)", file=sys.stderr)

    gates: list[GateResult] = []
    drift = {"resolved": 0, "moved": 0, "missing": 0, "value_changed": 0}

    if "G9" in selected:
        gates.append(g9_frontmatter.run(docs, git, strict=args.strict))
    if "G1" in selected:
        if git is None:
            gates.append(GateResult("G1", "Provenance resolves").skip("no repository"))
        else:
            gate, drift = g1_provenance.run(
                docs, git, at=args.at, min_resolution=args.min_resolution,
                strict=args.strict)
            gates.append(gate)
    if "G2" in selected:
        gates.append(g2_diagrams.run(docs, mmdc=args.mmdc, strict=args.strict,
                                     use_cache=not args.no_cache, jobs=args.jobs,
                                     timeout=args.timeout))
    if "G3" in selected:
        gates.append(g3_consistency.run(docs, strict=args.strict))
    if "G4" in selected:
        gates.append(g4_concerns.run(docs, strict=args.strict))
    if "G5" in selected:
        gates.append(g5_scenarios.run(docs, strict=args.strict))
    if "G6" in selected:
        gates.append(g6_tiers.run(docs, strict=args.strict))
    if "G7" in selected:
        gates.append(g7_proposals.run(docs, strict=args.strict))
    if "G8" in selected:
        gates.append(g8_questions.run(docs, strict=args.strict))
    if "G10" in selected:
        gates.append(g10_blocks.run(docs, strict=args.strict))
    if "G11" in selected:
        gates.append(g11_mode.run(docs, strict=args.strict))
    if "G12" in selected:
        gates.append(g12_adr.run(docs, strict=args.strict))

    repo_front = docs.front.get("repo") or {}
    evaluated = None
    if args.at and git is not None:
        evaluated = git.rev_parse(args.at) or args.at

    payload = {
        "doc": docs.front.get("id", "(unknown)"),
        "version": docs.front.get("version", "0.0.0"),
        "baseline": str(repo_front.get("commit", "")) or "(none)",
        "evaluated_at": evaluated or str(repo_front.get("commit", "")) or "(none)",
        "profile": docs.front.get("profile"),
        "mode": docs.front.get("mode"),
        "gates": [g.to_dict(include_passing=args.verbose) for g in gates],
        "drift": drift,
        "skipped_gates": [g for g in PLANNED if not args.gates],
        "summary": {
            "passed": sum(1 for g in gates if g.status == "pass"),
            "failed": sum(1 for g in gates if g.status == FAIL),
            "warned": sum(1 for g in gates if g.status == WARN),
            "skipped": sum(1 for g in gates if g.status == SKIP),
        },
    }

    if args.format == "json":
        render_json(payload)
    elif args.format == "sarif":
        render_sarif(payload, gates)
    else:
        render_text(payload, gates, verbose=args.verbose)

    if any(g.status == FAIL for g in gates):
        return EXIT_GATE_FAILURE
    if args.strict and any(g.status == WARN for g in gates):
        return EXIT_GATE_FAILURE
    if any(drift[k] for k in ("moved", "missing", "value_changed")):
        return EXIT_DRIFT
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
