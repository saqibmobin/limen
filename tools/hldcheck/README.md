# hldcheck

Validator for the agent-authored HLD standard (`STD-ARCH-HLD-01/02/03`).

It turns the automatable hard gates in `STD-ARCH-HLD-03` §5 from prose into a
build step. Without it, "grounded in code" is an aspiration; with it, a claim
that no longer resolves fails CI.

**Status:** all twelve hard gates implemented.

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
| **G3** Model name consistency | C4 containment via `<!-- c4: level=N parent="X" -->`; near-duplicate element names; elements absent from prose |
| **G4** Concern coverage | Every `C-nn` framed by a section; every `L<n>.<n>` section declares `<!-- frames: … -->`; ≥4 stakeholder roles |
| **G5** Response measures | Six-part scenarios with *quantified* measures; priority pairs; conflict set present; every SLO cites a `QA-nn` |
| **G6** Tier tagging | Pointer-bearing claims tagged; `[T1]` anchored to a pointer, ADR or standard; normative tables have a Tier column; T-4 anti-laundering |
| **G7** Proposal hygiene | Every `[T3]` has an owner and a trigger, and does not read as present tense |
| **G8** Open questions | Register exists and is **non-empty**; every `[T0]` resolves to a `Q-nn`; open questions have owner + resolution path |
| **G9** Front matter valid | Schema per `STD-ARCH-HLD-02` §2; baseline commit exists in the repo; declared `counts` match the content |
| **G10** Block ownership | `agent:` block hashes intact; no unhashed agent blocks; markers well-formed; ids unique |
| **G11** Mode discipline | greenfield: no present-tense unbuilt behavior. brownfield-change: no unit mixing `[AS-IS]`/`[TO-BE]`, migration section present |
| **G12** ADR externality | Every `ADR-nnn` resolves to a file with valid MADR front matter; trade-off rows cite an ADR and name what they sacrifice |

### Deterministic vs heuristic

Most checks are fully deterministic and always fail. Four are necessarily
heuristic — they **warn by default and fail under `--strict`**: G3's fuzzy
near-duplicate band, G6's quantity-without-tag scan, and the tense checks in G7
and G11. Every gate's deterministic checks fail regardless of `--strict`.

`G8` has an unusual polarity worth knowing: an **empty** open-questions register
fails, because zero open questions means the agent had nowhere it was willing to
admit uncertainty. Nothing in hldcheck penalizes a disclosed `[T0]`.

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
python3 tools/hldcheck/tests/run_tests.py          # 75 assertions
python3 tools/hldcheck/tests/run_tests.py -k drift --keep
```

The suite builds a throwaway git repo and two HLD document sets — one clean
(which must pass all twelve gates, including under `--strict`), one seeded with a
violation of every gate — then asserts on gate status, stats and exit codes.
Fixtures live in `tests/fixtures.py`. Requires mermaid-cli for the G2 assertions.

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
    ├── g1_provenance.py     g7_proposals.py
    ├── g2_diagrams.py       g8_questions.py
    ├── g3_consistency.py    g9_frontmatter.py
    ├── g4_concerns.py       g10_blocks.py
    ├── g5_scenarios.py      g11_mode.py
    └── g6_tiers.py          g12_adr.py
```

Adding a gate: implement `run(docs, ...) -> GateResult` in `gates/`, add its id
to `IMPLEMENTED` in `cli.py`, and wire the call. Gates read the shared primitives
on `DocSet` — `sections()`, `units()`, `tables()`, `pointers()`, `diagrams()`,
`diagram_elements()`, `blocks()`, `adr_refs()` — rather than re-parsing markdown.
