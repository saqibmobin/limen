# Limen: Start Here

Limen is a standard for architecture documents (HLDs) that agents write from
requirements or extract from running systems, plus a validator that checks what
can be checked mechanically. Claims that others build on say how they are known,
claims about code point at the code, uncertainty has a legal place to live, and
someone other than the author tries to break the result.

*Limen* is Latin for threshold: verified claim or guess, code that still matches
its description or code that has moved.

| Artifact | What it is | Who loads it |
| :--- | :--- | :--- |
| [`LIMEN.md`](LIMEN.md) | **The standard**, about 400 lines: modes, tiers, pointers, the ten rules, the skeleton, the loop, updating, checks, the audit | The authoring agent and the auditor, every run |
| [`LIMEN-reference.md`](LIMEN-reference.md) | **Templates**, one per section | The authoring agent, one section at a time |
| [`tools/limen/`](tools/limen/README.md) | **The validator**: five checks plus drift detection | CI, and the agent before presenting |
| [`examples/limen-hld/`](examples/README.md) | **An exemplar**: an HLD of limen itself that passes every check under `--strict` | Read once before authoring |
| [`rfcs/`](rfcs/RFC-limen-core.md) | **Why it is this way**: the proposal behind 6.0, and the one it replaced | Anyone changing the standard |

Limen 6.0 replaced the three 5.x standards (2,373 lines, 44 rules, 12 gates) with
the single file above. The 5.x documents and validator remain at the git tag
`v5-final`. See [`RFC-LIMEN-002`](rfcs/RFC-limen-core.md) for what changed and
why.

---

## Quick start

```bash
pip install pyyaml
npm i -g @mermaid-js/mermaid-cli          # diagrams; see tools/limen/README.md

# check a document set against the repository it describes
python3 tools/limen/bin/limen check --docs docs/architecture --repo .

# what has drifted since the baseline commit?   (exit 3 if anything has)
python3 tools/limen/bin/limen check --docs docs/architecture --repo . --at HEAD
```

## The loop

1. **Frame.** Pick the mode, pin the baseline commit, and write the problem,
   stakeholders and constraints, quality priorities and open questions. Stop: a
   person confirms them (LIMEN.md §6.1).
2. **Design.** Write the remaining sections and the ADRs, trying to break every
   load-bearing claim as you go (rule 5), and the summary last. Run
   `limen stamp --all`, then `limen check`, and fix what it reports.
3. **Audit.** A separate agent, in a clean context, tries to disprove the
   document (LIMEN.md §10).
4. **Review.** A person reads the document and its audit together.

Updating is not a re-run: repair only what drifted (LIMEN.md §8).

## Wiring it into an agent harness

Paste into the repository's `CLAUDE.md`, or the equivalent for your agent:

```markdown
## Architecture documentation

HLDs in this repo follow `docs/standards/LIMEN.md`.

When asked to create or update an HLD:
1. Read LIMEN.md in full. Load a template from LIMEN-reference.md only when
   writing that section.
2. Never write everything at once. Present the framing (LIMEN.md §6.1) and wait.
3. Before editing an existing HLD, run `limen check`. If `ownership` reports a
   section you did not change, a person changed it: `limen stamp --human` and
   leave it alone.
4. After writing, `limen stamp --mine` each section you wrote (or `--all` for a
   new document), then run:
   `python3 tools/limen/bin/limen check --docs docs/architecture --repo . --strict`
   Fix every failure. A failing check means it is not ready to present.
5. Never audit your own document. The audit is a separate session (LIMEN.md §10).
```

## First run in a repository

- [ ] `pip install pyyaml`, and install mermaid-cli
- [ ] Copy `LIMEN.md` and `LIMEN-reference.md` into `docs/standards/`
- [ ] Create `docs/architecture/` and `docs/adr/`
- [ ] Add `.limen-cache.json` to `.gitignore`; commit `.limen-lock.yaml`
- [ ] Add the `CLAUDE.md` block above
- [ ] Add the CI workflows from [`tools/limen/README.md`](tools/limen/README.md#ci),
      with `fetch-depth: 0`, or the baseline commit is not reachable
- [ ] Read [`examples/limen-hld/`](examples/README.md) once
- [ ] Write the framing and read its open questions before anything else

## Migrating a 5.x document

```bash
python3 tools/limen/bin/limen check --docs docs/architecture --legacy   # read as-is
python3 tools/limen/bin/limen migrate --docs docs/architecture --dry-run
python3 tools/limen/bin/limen migrate --docs docs/architecture
```

`migrate` rewrites the tags and modes, moves ownership into `.limen-lock.yaml`,
and prints anything left to do by hand (LIMEN.md §13).

---

## Sources

Limen borrows from ISO/IEC/IEEE 42010 (stakeholders and concerns), arc42
(constraints, quality trees, risks), SEI quality-attribute scenarios and ATAM,
MADR and Nygard's ADRs, the C4 model, *Building Evolutionary Architectures*
(fitness functions), Microsoft's STRIDE, *Release It!* (timeout budgets and
degradation), and Google's design-doc practice (non-goals, alternatives).

> Limen is not affiliated with or endorsed by arc42.org. arc42® is a
> registered trademark of Dr. Gernot Starke and Dr. Peter Hruschka.
