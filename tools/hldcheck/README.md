# hldcheck

Validator for the agent-authored HLD standard (`STD-ARCH-HLD-01/02/03`).

It turns the automatable hard gates in `STD-ARCH-HLD-03` §5 from prose into a
build step. Without it, "grounded in code" is an aspiration; with it, a claim
that no longer resolves fails CI.

**Status:** G1, G2, G9, G10 implemented. G3–G8, G11, G12 planned — `--gates`
accepts their names and reports them as not implemented rather than silently
passing.

## Install

No install. Python 3.9+ and `git`; `PyYAML` for front matter and registers.

```bash
python3 tools/hldcheck/hldcheck-cli --docs docs/architecture --repo .
```

Diagram rendering (G2) additionally needs mermaid-cli. It is discovered in this
order: `--mmdc`, `$MMDC`, `mmdc` on `PATH`, then `npx -p @mermaid-js/mermaid-cli mmdc`.
Without it G2 still runs its static lint and reports the render step as skipped.

## Gates

| Gate | Checks |
| :--- | :--- |
| **G1** Provenance resolves | Every `path@sha::symbol` pointer resolves at the declared baseline; quoted literals still match the code; one baseline per document version; no `file://` or absolute-path pointers |
| **G2** Diagrams render | Static lint of V-9…V-13, then an actual mermaid render per diagram |
| **G9** Front matter valid | Schema per `STD-ARCH-HLD-02` §2; baseline commit exists in the repo; declared `counts` match the content |
| **G10** Block ownership | `agent:` block hashes intact; no unhashed agent blocks; markers well-formed; ids unique |

### G1 symbol resolution

Layered, most precise first; every result records which layer answered, so
low-durability pointers are reported:

| Layer | Handles |
| :--- | :--- |
| `structured` | YAML/JSON path walk — `spec.template.spec.containers[0].resources` |
| `declaration` | Language-aware patterns for Go, Python, TS/JS, Rust, Java, SQL, proto, Terraform, shell |
| `identifier` | Bare identifier match — **warns**, because it is not a declaration |
| `line-range` | `#L10-L45` fallback — **warns**, because line numbers rot |

`--strict` promotes those warnings to failures. Tree-sitter would improve the
`declaration` layer; the current patterns are dependency-free and fail closed —
a miss is reported, never guessed.

## Usage

```bash
# full check
hldcheck-cli --docs docs/architecture --repo .

# drift scan: are the claims still true at HEAD?  (exit 3 if not)
hldcheck-cli --docs docs/architecture --repo . --at HEAD

# subset, machine-readable, CI-ready
hldcheck-cli --gates G1,G9 --format json
hldcheck-cli --format sarif > hld.sarif

# after authoring agent blocks, stamp their content hashes
hldcheck-cli --docs docs/architecture --stamp
```

| Exit | Meaning |
| ---: | :--- |
| 0 | All selected gates passed |
| 1 | A gate failed (or a warning, under `--strict`) |
| 2 | The validator could not run |
| 3 | Gates passed but drift was detected against `--at` |

### `--stamp` is an authoring step, not a fix

It recomputes `agent:begin` hashes in place. Run it immediately after writing an
agent block. **Never run it to clear a G10 mismatch** — a mismatch means a human
edited agent-owned content, and `STD-ARCH-HLD-01` U-2 says to promote that block
to `human:` ownership and raise a `Q-nn`. Stamping over it destroys exactly the
edit the gate exists to protect.

### Skipping a deliberate example

A document that shows intentionally invalid mermaid marks it:

```markdown
<!-- hldcheck:ignore-diagram -->
```

## CI

```yaml
on:
  pull_request:
    paths: ['internal/**', 'db/migrations/**', 'deploy/**', 'docs/architecture/**']
jobs:
  hld:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }        # baseline commit must be reachable
      - run: pip install pyyaml
      # advisory on code PRs: drift opens a Q-nn, it does not block the change
      - run: python3 tools/hldcheck/hldcheck-cli --at ${{ github.sha }}
        continue-on-error: true
      # blocking on PRs that touch the HLD itself
      - run: python3 tools/hldcheck/hldcheck-cli --strict
        if: contains(github.event.pull_request.changed_files, 'docs/architecture/')
```

Blocking on every code PR turns the standard into a tax and teams route around
it. This is fitness function `FF-07` in `STD-ARCH-HLD-02` §15.

`fetch-depth: 0` matters: a shallow clone will not contain the baseline commit
and G1 fails with "baseline commit unavailable" rather than a real result.

## Caching

Successful renders are cached by content hash in `.hldcheck-cache.json` beside
the docs. Add it to `.gitignore`. `--no-cache` forces a re-render; `--jobs N`
sets render parallelism (default 4).

## Tests

```bash
python3 tools/hldcheck/tests/run_tests.py          # 35 assertions
python3 tools/hldcheck/tests/run_tests.py -k drift --keep
```

The suite builds a throwaway git repo and two HLD document sets — one clean, one
seeded with every failure mode the four gates catch — then asserts on gate
status, stats and exit codes. It requires mermaid-cli for the G2 assertions.

## Layout

```
hldcheck-cli              entry point (no install needed)
hldcheck/
├── cli.py                argument parsing, gate orchestration, exit codes
├── docset.py             document discovery, front matter, pointer/diagram/block extraction
├── gitio.py              cached git plumbing (read-only, revision-addressed)
├── resolver.py           layered symbol resolution + literal verification
├── report.py             text / json / sarif renderers
├── model.py              GateResult, Item, status vocabulary
└── gates/
    ├── g1_provenance.py
    ├── g2_diagrams.py
    ├── g9_frontmatter.py
    └── g10_blocks.py
```

Adding a gate: implement `run(docs, ...) -> GateResult` in `gates/`, then move
its id from `PLANNED` to `IMPLEMENTED` in `cli.py` and wire the call.
