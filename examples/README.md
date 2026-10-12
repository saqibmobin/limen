# Examples

## `limen-hld/`

An HLD of `limen` itself, written to [`LIMEN.md`](../LIMEN.md) 6.0, that passes
every check under `--strict`. Its mode is `brownfield`, so every verified claim
points at real code at a real commit. That makes it a worked example and a
regression test at once: `tools/limen/tests/run_tests.py` checks it on every run,
because a conforming document that `limen` rejects is a bug in `limen`.

```bash
limen check --docs examples/limen-hld --repo . --strict
```

### What to look at

| If you want to see | Read |
| :--- | :--- |
| A summary a reader can stop at | `hld.md`, section 0 |
| Non-goals a reviewer might have argued for | `hld.md`, section 1 |
| Ranked priorities and a conflict list that picks winners | `hld.md`, section 3 |
| Invariants with "Checked" lines, including one found `violated` | `hld.md`, section 6 |
| A half-failure traced through the code | `hld.md`, section 7 |
| An `[unknown]` linked to an open question | `hld.md`, section 9 |
| `[proposed]` items with an owner and a trigger | `hld.md`, section 10 |
| A triggered section | `hld.md`, section 11, the contract catalogue |
| ADRs whose rejected options were genuinely tempting | `adr/` |
| Section ownership | `.limen-lock.yaml` |

The most useful line is the violated invariant. The 5.x version of this document
claimed limen never reached the network; trying to break that claim (rule 5)
found the `npx --yes` fallback in the diagram check. The example records it as a
finding rather than fixing it quietly, because that is what a finding looks like.

### It is deliberately small

Most sections are a paragraph, because limen is a CLI with no service to operate.
Right-sizing is the point (LIMEN.md §12).

### The baseline will drift

`baseline` pins the example to the commit its claims were written against. As
`tools/limen/` changes, pointers will move, which is the mechanism working:

```bash
limen check --docs examples/limen-hld --repo . --at HEAD
```

Exit 3 means the checks pass but claims have drifted. Repair is in LIMEN.md §8.2:
re-pin the baseline, fix only what moved, and never silently rewrite a claim that
can no longer be verified.
