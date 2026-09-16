# L3 Operations and evolution

<!-- agent:begin id="L3" hash="sha256:7adb7e9eac40b45debd36a8486cf86c006f1a05a08f031425e2d6ba0382b2462" -->
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
| `FF-01` | Groundedness | `QA-01` | The suite moves a symbol and asserts the drift is reported (`tools/limen/tests/run_tests.py@9a5b391::test_drift`) | CI, per PR | 0 missed | Block merge | `[T1]` |
| `FF-02` | Speed | `QA-02` | Time a full run over this example | CI, nightly | 60 s | Ticket | `[T3]` Proposed, owner @maintainer, trigger: when a second example exists |
| `FF-03` | No false findings | `QA-05` | This document must pass all twelve gates under `--strict` (`tools/limen/tests/run_tests.py@9a5b391::main_tests`) | CI, per PR | 0 findings | Block merge | `[T1]` |

`FF-03` is why this example exists. A conforming document that the validator
rejects is a bug in the validator, and without an exemplar in CI that bug is
found by an author rather than by the maintainer.

## L3.9 Risks and technical debt
<!-- frames: C-05 -->

| ID | Type | Description | Impact | Owner | Mitigation | Tier |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `R-01` | Risk | Declaration patterns miss unusual formatting, presenting as a false unresolved claim | M | @maintainer | Layer records match method; `--strict` rejects weak matches. See `ADR-001` | `[T1]` |
| `R-02` | Risk | Heuristic bands tuned on fixtures, not real documents | M | @maintainer | Heuristics warn rather than fail by default. Tracked as `Q-02` | `[T2]` |
| `R-03` | Issue | `limen xrefs` covers the three standards only, so any other document can rot unnoticed (`tools/limen/limen/xrefs.py@9a5b391::DOCS`) | M | @maintainer | Extend coverage, or keep no other normative documents | `[T1]` |
| `A-01` | Assumption | Authors run the validator before presenting, rather than discovering failures in CI | H if wrong | @maintainer | Documented in the standard's operating rules | `[T2]` |

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
