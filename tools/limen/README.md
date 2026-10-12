# limen

**What it is.** A command-line validator for architecture documents written to
the Limen standard ([`LIMEN.md`](../../LIMEN.md)).

**What it does.** It reads an HLD and checks five things a reviewer cannot check
by eye: that every claim about code still points at real code at the commit it was
written against, that quoted values still match the source, that diagrams render,
that nobody overwrote a person's edits, and that unknowns and proposals are
honest about being unknown or proposed. It exits non-zero when any of that is
untrue.

**What it does not do.** Decide whether a claim is true, whether alternatives were
real, or whether anything is missing. A passing run says the document can be
audited, not that it is right. That is the audit's job (LIMEN.md §10).

**Status:** 6.0.0. The 5.x validator, with twelve gates, remains at the git tag
`v5-final`.

## Install

No install. Python 3.9+, `git`, and `PyYAML`.

```bash
python3 tools/limen/bin/limen check --docs docs/architecture --repo .
```

`bin/` ships two names for the same entry point, `limen` and the short alias
`lmn`. Add `bin/` to your `PATH`, or symlink either name anywhere; the entry
script resolves its package through `realpath`. Written surfaces use `limen` in
full, so that grepping for `limen` finds every invocation.

The `diagrams` check needs mermaid-cli. It is found in this order: `--mmdc`,
`$MMDC`, `mmdc` on `PATH`, then `npx -p @mermaid-js/mermaid-cli mmdc`, first
offline and then online. **That last step downloads an unpinned package when npm
is reachable**, which is a known issue (`R-05` in the example HLD). Install
mermaid-cli yourself, at a pinned version, anywhere that matters. Without it, the
check lints diagram source and reports the render as skipped.

## Checks

| Check | Fails when |
| :--- | :--- |
| `pointers` | A `path@sha::symbol` pointer does not resolve at the baseline, a quoted literal no longer matches, a pointer uses another commit, a `[verified]` claim carries no pointer, ADR, standard or link, the mode is unknown, or a brownfield document has no baseline. A whole-file or name-only pointer warns |
| `diagrams` | A Mermaid diagram does not render. Habits that break other renderers (unquoted punctuation, raw HTML, LaTeX, Unicode arrows, no direction) warn |
| `ownership` | A section recorded in `.limen-lock.yaml` as agent-written has changed since it was stamped, and the change has not been attributed |
| `uncertainty` | A tag is malformed (bare in prose, inside a longer code span, or a 5.x `[Tn]`), an `[unknown]` names no open question, a `Q-nn` is cited but never defined, or a `[proposed]` lacks an owner or a trigger |
| `decisions` | A cited `ADR-nnn` has no file. Citing no ADRs at all warns |

Warnings fail only under `--strict`.

### Pointer resolution

Layered, most precise first. Every result records which layer answered, so a weak
match is reported rather than silently accepted.

| Layer | Handles |
| :--- | :--- |
| `structured` | YAML and JSON paths, such as `spec.template.spec.containers[0].resources` |
| `declaration` | Language-aware patterns for Go, Python, TS/JS, Rust, Java, SQL, proto, Terraform and shell |
| `identifier` | A bare identifier match. **Warns**, because it is not a declaration |
| `line-range` | The `#L10-L45` fallback. **Warns**, because line numbers rot |
| `file` | No symbol. **Warns**, because drift inside the file is invisible |

A dotted or indexed symbol is an assertion about structure, so if the document
parses and the path is not in it, the pointer is **missing** rather than falling
through to a textual match. Without that rule, a deleted YAML key resolves to
whatever else shares its last segment.

## Usage

```bash
limen check --docs docs/architecture --repo .              # all five checks
limen check --docs docs/architecture --repo . --at HEAD    # drift: exit 3 if found
limen check --checks pointers,uncertainty --format json
limen check --format sarif > hld.sarif
limen check --legacy                                       # read a 5.x document

limen stamp --all                    # record a newly written document as the agent's
limen stamp --mine "6. Invariants"   # a section the agent edited in this run
limen stamp --human "Reviewer notes" # a section a person owns

limen migrate --dry-run              # convert a 5.x document set, in place
limen xrefs                          # check § and rule references in the standard
```

`limen` with no subcommand runs `limen check`.

| Exit | Meaning |
| ---: | :--- |
| 0 | Every selected check passed |
| 1 | A check failed, or warned under `--strict` |
| 2 | limen could not run |
| 3 | The checks passed, but drift was found against `--at` |

### Stamping

`.limen-lock.yaml` maps each `##` heading to the hash of what an agent last wrote
there, or to `human`. A section with no entry was written by a person
(LIMEN.md §8.3). `stamp` writes the lock atomically and drops entries for
sections that no longer exist.

**Never `--mine` a section to make `ownership` pass.** A failure means the section
changed after it was stamped. If you did not change it, a person did, and the
right command is `--human`. `--mine` refuses a section already recorded as a
person's; a person hands one back by deleting its line from the lock.

### Migrating from 5.x

`limen migrate` rewrites `[T0]`–`[T3]` as `[unknown]`, `[verified]`, `[inferred]`
and `[proposed]`; both brownfield modes as `brownfield`; `repo.commit` as
`baseline`. It drops retired front matter and `frames:` and `c4:` comments, and
moves ownership markers into the lock. A 5.x agent block whose hash no longer
matched was edited by a person, so its sections are recorded as theirs. It
leaves `[AS-IS]`/`[TO-BE]` markers, YAML registers and the prose alone.

`limen check --legacy` performs the same conversion in memory and writes nothing.
`--gates G1,G10` still works for one minor version: 5.x gate ids map to the
checks that replaced them, and retired gates are reported as retired.

## CI

Blocking on PRs that change the HLD:

```yaml
# .github/workflows/hld.yml
on:
  pull_request:
    paths: ['docs/architecture/**', 'docs/adr/**']
jobs:
  hld:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }        # the baseline commit must be reachable
      - run: pip install pyyaml && npm i -g @mermaid-js/mermaid-cli@11
      - run: python3 tools/limen/bin/limen check --strict
```

Advisory on code PRs: drift opens a ticket, it does not block the change.

```yaml
# .github/workflows/hld-drift.yml
on:
  pull_request:
    paths: ['src/**', 'internal/**', 'deploy/**', 'db/**']
jobs:
  drift:
    runs-on: ubuntu-latest
    continue-on-error: true
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - run: pip install pyyaml
      - run: python3 tools/limen/bin/limen check --checks pointers --at ${{ github.sha }}
```

Blocking every code PR turns the standard into a tax, and teams route around it.
A shallow clone does not contain the baseline commit, and `pointers` fails with
"not in this repository" rather than passing.

## Caching

Successful renders are cached by content hash in `.limen-cache.json` beside the
docs; add it to `.gitignore`. `--no-cache` forces a re-render, `--jobs N` sets
render parallelism (default 4), and `--timeout` cuts off one render (default
120 s).

## Conventions for maintainers

**Do not rename these.** They are the standard's vocabulary, referenced across the
documents, the checks, the lock and CI:

| Identifier | Used by |
| :--- | :--- |
| Tags `[verified]`, `[inferred]`, `[proposed]`, `[unknown]` | `pointers`, `uncertainty`, `migrate` |
| Check names `pointers`, `diagrams`, `ownership`, `uncertainty`, `decisions` | `--checks`, JSON and SARIF output, CI |
| Register prefixes `C-` `K-` `QA-` `Q-` `R-` `FF-` `ADR-` | `uncertainty`, `decisions` |
| `.limen-lock.yaml` and the value `human` | `stamp`, `ownership`, `migrate` |
| Exit codes 0, 1, 2, 3 | CI |

`limen` is the command and the Python package, `Limen` is the standard in prose.

## Tests

```bash
python3 tools/limen/tests/run_tests.py          # 89 assertions
python3 tools/limen/tests/run_tests.py -k stamp --keep
```

The suite builds a throwaway git repository and three document sets: a clean 6.0
document that must pass every check under `--strict`, a broken one seeded with at
least one violation of every check, and a 5.x document for `migrate` and
`--legacy`. It also runs the shipped example under `--strict`: a conforming
document that `limen` rejects is a bug in `limen`. The `diagrams` assertions need
mermaid-cli.

## Layout

```
bin/limen            entry point (no install needed); bin/lmn is an alias
limen/
├── cli.py           argument parsing, check orchestration, exit codes
├── docset.py        document discovery, front matter, pointers, tags, sections
├── lock.py          .limen-lock.yaml: section hashes and `stamp`
├── migrate.py       5.x conversion, on disk and in memory (--legacy)
├── gitio.py         cached, read-only, revision-addressed git
├── resolver.py      layered symbol resolution and literal matching
├── report.py        text, JSON and SARIF output
├── xrefs.py         `limen xrefs`
├── model.py         CheckResult, Item, status vocabulary
└── checks/          pointers, diagrams, ownership, uncertainty, decisions
```

Adding a check: implement `run(docs, ...) -> CheckResult` in `checks/`, add its
name to `CHECKS` in `cli.py`, and wire the call. Checks read the shared
primitives on `DocSet` (`units()`, `pointers()`, `diagrams()`, `sections()`,
`adr_refs()`, `question_ids()`) rather than re-parsing markdown. Before adding
one, ask whether it checks something true of the system or only the shape of the
document; 6.0 retired seven gates that did the second.
