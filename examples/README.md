# Examples

## `limen-hld/`

A complete High-Level Design that passes all twelve hard gates under `--strict`.

Its subject is `limen` itself, in `brownfield-asis` mode, so every `[T1]` claim
points at real code at a real commit. That makes it a worked example and a
regression test at once: `tools/limen/tests/run_tests.py` runs the validator over
it on every test run, because a conforming document that `limen` rejects is a bug
in `limen`.

```bash
limen check --docs examples/limen-hld --repo . --strict
```

### What to look at

| If you want to see | Read |
| :--- | :--- |
| Front matter, registers, counts | `01-intake.md` and `registers/` |
| A conflict set that actually picks winners | `01-intake.md`, L1.4 |
| C4 level annotations that let G3 check containment | `01-intake.md` L1.9, `02-mechanics.md` L2.1 |
| Provenance pointers with a quoted literal | `02-mechanics.md`, L2.1 |
| Tier discipline, including why a classification is `[T2]` and not `[T1]` | `02-mechanics.md`, L2.6 |
| `[T3]` proposals carrying an owner and a trigger | `03-operations.md`, L3.2 and L3.10 |
| `[T0]` open questions linked to the register | `02-mechanics.md` L2.6, `03-operations.md` L3.10 |
| Agent and human ownership blocks | All three documents |
| A full MADR decision record with real rejected options | `adr/ADR-001-*.md` |

### It is deliberately small

The profile is `P5-library-sdk`, so operations and cost carry little weight and
the document is about 250 lines. It shows every mechanism the gates enforce
without pretending a CLI needs a disaster recovery plan. Right-sizing is the
point, not completeness: see the root README, §8.

### The baseline will drift

`repo.commit` pins the example to the commit its claims were written against.
As `tools/limen/` changes, some pointers will move. That is the mechanism working,
and it is what `--at` reports:

```bash
limen check --docs examples/limen-hld --repo . --at HEAD
```

Exit code 3 means the gates pass but claims have drifted. Repair is described in
`STD-LIMEN-01` §7.3: re-pin the baseline, fix only what moved, and never silently
rewrite a claim that can no longer be verified.
