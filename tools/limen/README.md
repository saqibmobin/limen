# limen

**What it is.** A command-line validator for architecture documents written
against the Limen standard (`STD-LIMEN-01/02/03`).

**What it does.** It reads a High-Level Design and checks twelve things a
reviewer cannot check by eye: that every claim about the code still resolves at
the commit it was written against, that quoted limits still match the source,
that diagrams render and name the same things the prose does, that every
stakeholder concern is addressed somewhere, that proposals are labelled as
proposals, and that nobody has quietly overwritten a human's edits. It exits
non-zero when any of that is untrue.

**Why it exists.** An agent asked to write an HLD produces something complete,
confident, well-formatted and substantially untrue. It infers components from
imports, asserts trade-offs it never evaluated, and describes planned behaviour
in the present tense. Prose review does not catch this reliably, and the
document decays further every time the code moves underneath it. `limen` makes
those failures mechanical: a claim that no longer resolves fails CI, the same
way a broken test does.

**Status:** all twelve hard gates implemented.

## Install

No install. Python 3.9+ and `git`; `PyYAML` for front matter and registers.

```bash
python3 tools/limen/bin/limen check --docs docs/architecture --repo .
```

### Putting `limen` on PATH

`bin/` ships two names for the same entry point: `limen` and the short alias
`lmn`. Either works, from anywhere:

```bash
# option A: add bin/ to PATH (gets you both names)
export PATH="$PWD/tools/limen/bin:$PATH"

# option B: symlink one name into a directory already on PATH
ln -s "$PWD/tools/limen/bin/limen" ~/.local/bin/lmn

limen check --docs docs/architecture --repo .
lmn check --docs docs/architecture --repo .      # identical
```

The entry script resolves its package through `realpath`, so a symlink from
anywhere works. `lmn` is a typing convenience only. **Written surfaces use
`limen` in full**, so that grepping for `limen` finds every invocation. If `lmn`
collides with something already on your PATH, symlink a different name; nothing
depends on it.

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
| **G6** Tier tagging | Pointer-bearing claims tagged; every `[Tn]` token is a well-formed tag, not a bare mention; `[T1]` anchored to a pointer, ADR or standard; normative tables have a Tier column; T-4 anti-laundering |
| **G7** Proposal hygiene | Every `[T3]` has an owner and a trigger, and does not read as present tense |
| **G8** Open questions | Register exists and is **non-empty**; every `[T0]` resolves to a `Q-nn`; open questions have owner + resolution path |
| **G9** Front matter valid | Schema per `STD-LIMEN-02` §2; baseline commit exists in the repo; declared `counts` match the content |
| **G10** Block ownership | `agent:` block hashes intact; no unhashed agent blocks; markers well-formed; ids unique |
| **G11** Mode discipline | greenfield: no present-tense unbuilt behavior. brownfield-change: no unit mixing `[AS-IS]`/`[TO-BE]`, migration section present |
| **G12** ADR externality | Every `ADR-nnn` resolves to a file with valid MADR front matter; trade-off rows cite an ADR and name what they sacrifice. A `record_type: pointer` ADR is judged on `owned_by` resolving plus its declared trade-off, not on restating prose it deliberately does not hold |

### Mode-aware checks

Two gates read `mode` from front matter and judge accordingly, so the same
command is correct for a system that does not exist yet and one that does:

- **G1** does not demand provenance pointers in `greenfield`; it reports "no
  pointers (greenfield)" and passes. In either brownfield mode, a document with
  no pointers fails.
- **G11** enforces tense in `greenfield` (no present-tense description of
  unbuilt behaviour), and in `brownfield-change` enforces that no unit mixes
  `[AS-IS]` with `[TO-BE]` and that a migration section exists.

### Deterministic vs heuristic

Most checks are fully deterministic and always fail. Four are necessarily
heuristic, and they **warn by default and fail under `--strict`**: G3's fuzzy
near-duplicate band, G6's quantity-without-tag scan, and the tense checks in G7
and G11. Every gate's deterministic checks fail regardless of `--strict`.

`G8` has an unusual polarity worth knowing: an **empty** open-questions register
fails, because zero open questions means the agent had nowhere it was willing to
admit uncertainty. Nothing in limen penalizes a disclosed `[T0]`.

### G1 symbol resolution

Layered, most precise first; every result records which layer answered, so
low-durability pointers are reported:

| Layer | Handles |
| :--- | :--- |
| `structured` | YAML/JSON path walk, e.g. `spec.template.spec.containers[0].resources` |
| `declaration` | Language-aware patterns for Go, Python, TS/JS, Rust, Java, SQL, proto, Terraform, shell |
| `identifier` | Bare identifier match. **Warns**, because it is not a declaration |
| `line-range` | `#L10-L45` fallback. **Warns**, because line numbers rot |

A dotted or indexed symbol is an assertion about structure, so if the document
parses and the path is not in it the pointer is **missing** rather than falling
through to a textual match. Without that rule a deleted YAML key resolves to
whatever else shares its last segment: `jobs.e2e.if` against a workflow that
dropped its `if:` matched the `if` of a shell script in a `run:` block, which
turns a deleted key into a merely moved one.

`--strict` promotes those warnings to failures. Tree-sitter would improve the
`declaration` layer; the current patterns are dependency-free and fail closed,
so a miss is reported, never guessed.

## Usage

```bash
# full check
limen check --docs docs/architecture --repo .

# drift scan: are the claims still true at HEAD?  (exit 3 if not)
limen check --docs docs/architecture --repo . --at HEAD

# subset, machine-readable, CI-ready
limen check --gates G1,G9 --format json
limen check --format sarif > hld.sarif

# after authoring agent blocks, stamp their content hashes
limen stamp --docs docs/architecture
```

| Exit | Meaning |
| ---: | :--- |
| 0 | All selected gates passed |
| 1 | A gate failed (or a warning, under `--strict`) |
| 2 | The validator could not run |
| 3 | Gates passed but drift was detected against `--at` |

### `--stamp` is an authoring step, not a fix

It recomputes `agent:begin` hashes in place. Run it immediately after writing an
agent block. **Never run it to clear a G10 mismatch.** A mismatch means a human
edited agent-owned content, and `STD-LIMEN-01` U-2 says to promote that block
to `human:` ownership and raise a `Q-nn`. Stamping over it destroys exactly the
edit the gate exists to protect.

### Skipping a deliberate example

A document that shows intentionally invalid mermaid marks it:

```markdown
<!-- limen:ignore-diagram -->
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
      - run: python3 tools/limen/bin/limen --at ${{ github.sha }}
        continue-on-error: true
      # blocking on PRs that touch the HLD itself
      - run: python3 tools/limen/bin/limen --strict
        if: contains(github.event.pull_request.changed_files, 'docs/architecture/')
```

Blocking on every code PR turns the standard into a tax and teams route around
it. This is fitness function `FF-07` in `STD-LIMEN-02` §17.

`fetch-depth: 0` matters: a shallow clone will not contain the baseline commit
and G1 fails with "baseline commit unavailable" rather than a real result.

## Caching

Successful renders are cached by content hash in `.limen-cache.json` beside
the docs. Add it to `.gitignore`. `--no-cache` forces a re-render; `--jobs N`
sets render parallelism (default 4).

## Cross-reference checking

`limen xrefs` validates every internal `§` and rule citation in the three
standards against the headings and rule definitions that actually exist.
Section renumbering breaks these silently, and a wrong pointer in a standard
about grounding claims is a bad look.

```bash
limen xrefs     # exit 1 on a broken reference
```

## Conventions for maintainers

**Limen is the standard; HLD is the artifact it governs.** That is why the
front-matter `doc: hld` key and `HLD-<slug>` document ids did not change when
the project was renamed. The document type is still a High-Level Design.

**Capitalisation carries meaning:** `limen` is the command and the Python
package, `Limen` is the standard in prose, `LIMEN` appears only inside document
ids such as `STD-LIMEN-01`.

**Do not rename these.** They are the standard's vocabulary, not the tool's
branding, and they are referenced across the documents, the validator, the audit
record format and CI:

| Identifier | Occurrences | Referenced by |
| :--- | ---: | :--- |
| Tier tags `[T0]`–`[T3]` | 191 | G6, G7, G8, G11; the evidence model |
| Gate ids `G1`–`G12` | 293 | CLI `--gates`, audit records, CI |
| Rule ids (`M-1`, `T-3`, `U-2`, `V-9`, `D-5`, …) | 46 | Cited across all three standards |
| Register prefixes `C-` `K-` `QA-` `Q-` `R-` `FF-` `ADR-` | 93+ | G4, G5, G8, G12 |
| Front matter `doc: hld`, `id: HLD-<slug>` | 6 | G9 |
| Exit codes 0/1/2/3 | n/a | CI contracts |
| Section ids `L0.1`–`L3.10` | n/a | G4 concern framing |

A blanket rename across this repo will silently break the gates that depend on
them. The 12 gates are the enforcement; these ids are what they enforce against.

## Tests

```bash
python3 tools/limen/tests/run_tests.py          # 88 assertions
python3 tools/limen/tests/run_tests.py -k drift --keep
```

The suite builds a throwaway git repo and two HLD document sets: one clean
(which must pass all twelve gates, including under `--strict`), one seeded with a
violation of every gate. It then asserts on gate status, stats and exit codes.
Fixtures live in `tests/fixtures.py`. Requires mermaid-cli for the G2 assertions.

The suite also runs the validator over the shipped worked example at
`examples/limen-hld/`, which must pass all twelve gates under `--strict`. A
conforming document that `limen` rejects is a bug in `limen`, and the exemplar is
what makes that show up here rather than in an author's terminal.

## Layout

```
bin/limen          entry point (no install needed)
limen/
├── cli.py                argument parsing, gate orchestration, exit codes
├── docset.py             document discovery, front matter, pointer/diagram/block extraction
├── gitio.py              cached git plumbing (read-only, revision-addressed)
├── resolver.py           layered symbol resolution + literal verification
├── report.py             text / json / sarif renderers
├── xrefs.py              `limen xrefs`, standards cross-ref checker
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
on `DocSet` (`sections()`, `units()`, `tables()`, `pointers()`, `diagrams()`,
`diagram_elements()`, `blocks()`, `adr_refs()`) rather than re-parsing markdown.
