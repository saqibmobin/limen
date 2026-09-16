# L3 Operations and evolution

<!-- agent:begin id="L3" hash="sha256:a3cb1e6b18f2022fcc051c3bb861131bd0cb34eb5da6821709f6a527ecaee614" -->
## L3.1 Service levels
<!-- frames: C-01, C-03 -->

There is no running service, so these are properties of a run rather than of an
uptime window. Each traces to the scenario it came from.

| ID | SLI | Target | Window | Derived from | Tier |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `SLO-01` | Drifted claims detected | 100% of moved, missing or changed pointers | Per run | `QA-01` | `[T2]` |
| `SLO-02` | Full check wall clock, warm cache | 60 s or less | Per run | `QA-02` | `[T2]` |
| `SLO-03` | False findings on a conforming document | 0 | Per run | `QA-05` | `[T2]` |

`SLO-02` is met by caching renders rather than by checking less, which is the
consequence of the `QA-01` versus `QA-02` decision in L1.4 `[T2]`.

## L3.2 Fitness functions
<!-- frames: C-03 -->

| ID | Characteristic | QA | Check | Where | Threshold | On failure | Tier |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `FF-01` | Groundedness | `QA-01` | The suite moves a symbol and asserts the drift is reported (`tools/limen/tests/run_tests.py@9a5b391::test_drift`) | Test suite, on demand | 0 missed | Suite fails | `[T1]` |
| `FF-02` | Speed | `QA-02` | Time a full run over this example | CI, nightly | 60 s | Ticket | `[T3]` Proposed, owner @maintainer, trigger: when a second example exists |
| `FF-03` | No false findings | `QA-05` | This document must pass all twelve gates under `--strict` (`tools/limen/tests/run_tests.py@9a5b391::main_tests`) | Test suite, on demand | 0 findings | Suite fails | `[T1]` |
| `FF-04` | Enforcement | `QA-05` | Run the suite on every pull request | Not yet wired | 0 findings | Block merge | `[T3]` Proposed, owner @maintainer, trigger: when the repository gains a remote |

`FF-03` is why this example exists. A conforming document that the validator
rejects is a bug in the validator, and without an exemplar under test that bug is
found by an author rather than by the maintainer.

Note what the `Where` column says, and what it does not. These checks are
implemented and they pass, so each check is a Tier 1 claim carrying a pointer.
Nothing invokes them automatically, so the enforcement is `FF-04`, a separate
Tier 3 proposal with an owner and a trigger. Collapsing the two into one row
reading "CI, per PR / Block merge" would have been the more impressive claim and
the false one: a fitness function nothing runs is documentation of an intention.

This distinction is not one a gate can make for you. G1 proves that `test_drift`
exists; it cannot prove that anything calls it. Every `Where` cell in this table
is an unverifiable claim, which is exactly the kind of statement the tier model
exists to mark.

## L3.9 Risks and technical debt
<!-- frames: C-05 -->

| ID | Type | Description | Impact | Owner | Mitigation | Tier |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `R-01` | Risk | Declaration patterns miss unusual formatting, presenting as a false unresolved claim | M | @maintainer | Layer records match method; `--strict` rejects weak matches. See `ADR-001` | `[T1]` |
| `R-02` | Risk | Heuristic bands tuned on fixtures, not real documents | M | @maintainer | Heuristics warn rather than fail by default. Tracked as `Q-02` | `[T2]` |
| `R-03` | Issue | `limen xrefs` covers the three standards only, so any other document can rot unnoticed (`tools/limen/limen/xrefs.py@9a5b391::DOCS`) | M | @maintainer | Extend coverage, or keep no other normative documents | `[T1]` |
| `R-04` | Risk | No continuous integration exists, so every fitness function depends on a person remembering to run the suite | H | @maintainer | Wire `FF-04` when a remote exists; until then the risk is accepted, not mitigated | `[T2]` |
| `A-01` | Assumption | Authors run the validator before presenting, rather than discovering failures after the fact | H if wrong | @maintainer | Documented in the standard's operating rules | `[T2]` |

`R-03` is not hypothetical: a previous brand document sat outside the checked set
and contradicted itself within one commit `[T2]`.

## L3.10 Roadmap
<!-- frames: C-04 -->

Phases carry trigger conditions rather than dates, because dates in an
architecture document are wrong within a quarter.

| Phase | Scope | Trigger to start | Exit criterion | Tier |
| :--- | :--- | :--- | :--- | :--- |
| 1 | Extend `limen xrefs` to every normative document in the repository | `R-03` recurs once | No document outside the checked set | `[T3]` Proposed, owner @maintainer, trigger: next unchecked document appears |
| 2 | Tree-sitter declaration layer | Measured miss rate above 5% on a real repository | `Q-01` closed; `ADR-001` superseded | `[T3]` Proposed, owner @maintainer, trigger: `Q-01` resolved against real data |
| 3 | Scored audit categories, not just hard gates | A second document set exists to compare | Rubric reproducible between two reviewers | `[T3]` Proposed, owner @maintainer, trigger: when a second HLD is written |

Whether audit records belong beside each document or in one place is undetermined
`[T0]`, tracked as `Q-03`.
<!-- agent:end id="L3" -->

<!-- human:begin id="L3.note" -->
Reviewer note: `R-03` was raised by a human after a brand document rotted outside
the checked set. Kept here as the record of why phase 1 exists.
<!-- human:end id="L3.note" -->
