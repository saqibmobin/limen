# Limen — Brand & Naming Specification

**Status:** Adopted 2026-09-16 — executed in full; see §9 for the decisions taken
**Scope:** The name, how it is written, the identifiers it governs, and the
identifiers it must not touch.

---

## 1. The name

**Limen.** Latin *limen, liminis* — the threshold, the doorsill; the stone you
cross to get in.

### 1.1 Why this name

The framework's whole job is deciding what has crossed a line: claims that are
verified versus guessed, gates passed versus failed, code that still matches its
description versus code that has moved. Five things the word already names:

| Sense | Maps to |
| :--- | :--- |
| Threshold as gate | Four alignment gates (0–3) and twelve hard gates (G1–G12). A gate failure is a threshold not crossed |
| Thresholds as numbers | `-03` is literally a rubric of thresholds: 95% provenance resolution, floors at 50%/70%, bands at 90/75/50, presence capped at 40% |
| **Difference limen** | Psychophysics: *the smallest difference between two stimuli that can be consistently detected*. That is exactly what `--at HEAD` computes between a claim and the code |
| Liminal | A `brownfield-change` document is mid-transition by definition; L3.8 migration increments are liminal states with revert expiry dates |
| Subliminal | Below the threshold of detection — the failure mode the framework exists to prevent: a claim that quietly stopped being true |

Two of those five are technical rather than poetic. That is the test a name
should pass.

### 1.2 Pronunciation

**LEE-men** (classical Latin), not LY-men. Stated because English psychophysics
convention says LY-men, which has an unfortunate near-homophone, and because a
name people say aloud in meetings needs one agreed pronunciation.

### 1.3 Positioning

The name does distinctiveness; the subtitle does legibility. Never expect the
word "Limen" to explain itself.

- **One line:** Limen — a standard for grounded, verifiable architecture documentation.
- **One paragraph:** Limen is a standard and validator for architecture documents
  written by agents. Every factual claim is anchored to a commit and
  re-resolvable, uncertainty has a first-class place to live, and drift between
  the document and the code is detected mechanically rather than noticed by
  accident.

Always pair the name with the descriptor on first use in any external context.

---

## 2. Disambiguation and attribution

### 2.1 Other Limens exist

The name is not unique on GitHub. At least four unrelated projects use it,
including an agent harness, an API abuse-defense engine, and a Rust reverse
proxy. None occupy this niche, but the collision is real and the mitigation is
to never ship the bare word without its descriptor or document ID.

- **Internal use:** "Limen" alone is fine.
- **External use:** "Limen (architecture documentation standard)" or the document
  ID, e.g. `STD-LIMEN-01`.
- **Never** claim the name is unique or register-quality distinctive.

### 2.2 arc42

`arc42®` is a registered trademark of Dr. Gernot Starke and Dr. Peter Hruschka.
Limen incorporates parts of the arc42 template (§2 Constraints, §8 cross-cutting
concepts, §10 quality tree, §11 risks) and credits it in `-01` §12.

Every external-facing surface carries this line verbatim:

> Limen is not affiliated with or endorsed by arc42.org. arc42® is a registered
> trademark of Dr. Gernot Starke and Dr. Peter Hruschka.

This is why `arc1` and `arcX` were rejected: a name that rhymes with a live
trademark implies an endorsement that does not exist.

---

## 3. Writing the name

| Context | Form | Example |
| :--- | :--- | :--- |
| Prose, the framework | `Limen`, capitalised | "Limen requires a pinned baseline." |
| Code, CLI, paths | `limen`, lowercase | `limen check`, `tools/limen/` |
| Document IDs | `LIMEN`, uppercase | `STD-LIMEN-01` |
| Possessive | "Limen's" | fine |
| Adjectival | avoid | write "a Limen document", not "a Limen-ified document" |

Never: `LiMen`, `limEn`, `Limen™`, `LIMEN` in prose, or any portmanteau.

---

## 4. Lexicon — sanctioned and banned

A clever name invites clever writing, and clever writing degrades a technical
standard. These rules exist to stop that.

### 4.1 Sanctioned

| Term | Means | Use where |
| :--- | :--- | :--- |
| above / below the limen | passed / failed a threshold | Gate results, floor breaches |
| the difference limen | the smallest detectable claim-vs-code difference | Drift detection, `--at` |
| liminal | mid-transition between as-is and to-be | `brownfield-change`, migration increments |

### 4.2 Banned

- `sublimenal`, `limenal`, `eLIMENate`, `Limenator`, or any coinage
- Punning on "preliminary" or "eliminate" — use both words normally or not at all
- Threshold metaphors stacked on each other ("crossing the limen of the gate")

### 4.3 The restraint rule

**The name may earn its keep in at most three places across the three
standards.** Everywhere else, use plain technical language: "gate failed", "claim
did not resolve", "drift detected". A standard is not a place to be pleased with
oneself.

---

## 5. Voice

Codified from the existing standards so future edits match:

- **Declarative, not hedged.** "A second writer is a finding, not a design."
- **Name the failure it prevents.** Every rule says what goes wrong without it.
- **Second person is rare.** Address the agent or the reader impersonally.
- **No exclamation marks, no rhetorical questions, no jokes in normative text.**
- **Short sentences carry the rules; long sentences carry the reasoning.**

---

## 6. Naming conventions (normative)

### 6.1 What Limen is, and is not

**Limen is the standard. HLD is the artifact.** Limen governs how a High-Level
Design is written and verified; it is not itself the document type. This line
decides several identifiers below — notably that `doc: hld` and `HLD-<slug>`
document IDs do **not** change.

### 6.2 Identifier scheme

| Kind | Convention | Example |
| :--- | :--- | :--- |
| Standard document ID | `STD-LIMEN-NN` | `STD-LIMEN-01` |
| Standard filename | `STD-LIMEN-NN-Title.md` | `STD-LIMEN-02-Templates.md` |
| Cross-reference shorthand | `-NN` | ``see `-03` §9`` |
| CLI binary | `limen` | `limen check` |
| CLI short alias | `lmn` | `lmn check` |
| Python package | `limen` | `from limen.gates import g1_provenance` |
| Tool directory | `tools/limen/` | |
| Cache file | `.limen-cache.json` | gitignored |
| Env overrides | `LIMEN_*` | `LIMEN_MMDC` (alias; `MMDC` still honoured) |
| Audit records | `audits/<date>-<version>.yaml` | unchanged |

### 6.3 CLI grammar

Verb-first subcommands, because `limen check` reads as a sentence and
`limen --stamp` does not:

```
limen check   [--docs DIR] [--repo DIR] [--at REV] [--gates LIST] [--strict]
limen stamp   [--docs DIR]
limen xrefs   [--dir DIR]          # absorbs tools/limen/bin/limen xrefs
```

`limen` with no subcommand runs `check`, so existing invocations keep working.

### 6.4 The `lmn` alias

`bin/lmn` is a symlink to `bin/limen`. It exists so the command is three
characters to type, and nothing more.

- **Terminals, shell history, ad-hoc invocation:** `lmn` is fine.
- **Every written surface — READMEs, standards, CI config, commit messages,
  runbooks, issue threads:** `limen` in full.

The reason is searchability. A reader grepping for `limen` must find every
invocation, and a reader who has never seen the alias must not have to guess.
An alias that leaks into documentation stops being a convenience and becomes a
second name to learn.

If `lmn` collides with an existing command on someone's PATH, they symlink a
different name. Nothing in the repo depends on the alias existing.

### 6.5 What must NOT change

Renaming the framework must not touch the vocabulary the standards are built
from. These are load-bearing and appear in the counts shown:

| Identifier | Count | Why it stays |
| :--- | ---: | :--- |
| Tier tags `[T0]`–`[T3]` | 191 | The evidence model, not the brand |
| Gate IDs `G1`–`G12` | 293 | Referenced by the validator, audit record, and CI |
| Rule IDs (`M-1`, `T-3`, `U-2`, `V-9`, `D-5`, …) | 46 | Cited across all three standards |
| Register prefixes (`C-`, `K-`, `QA-`, `Q-`, `R-`, `FF-`, `ADR-`) | 93+ | Document-level IDs, per §6.1 |
| Front matter `doc: hld`, `id: HLD-<slug>` | 6 | The artifact is still an HLD |
| Exit codes 0/1/2/3 | — | CI contracts |
| Section IDs `L0.1`–`L3.10` | — | The artifact's structure |

---

## 7. Migration map

| From | To | Occurrences |
| :--- | :--- | ---: |
| `STD-LIMEN` | `STD-LIMEN` | 74 |
| `STD-LIMEN-0N-*.md` | `STD-LIMEN-0N-*.md` | 3 files |
| `limen` (package, prose) | `limen` | 67 |
| `limen` | `limen` | 14 |
| `tools/limen/` | `tools/limen/` | 1 dir |
| `.limen-cache.json` | `.limen-cache.json` | 3 + `.gitignore` |
| `tools/limen/bin/limen xrefs` | `tools/limen/limen/xrefs.py` | 1 file |

Execution: mechanical `sed` plus `git mv`, then re-run the 75 assertions and the
cross-reference checker. Both must be green before the commit lands.

---

## 8. Visual identity

**Deferred, deliberately.** There is no surface that needs a logo — no docs site,
no README badge, no external distribution. Inventing a palette for an internal
standard is the kind of scope inflation this framework is otherwise built to
resist.

If a surface appears, the wordmark is the plain word `limen` in the repo's
monospace stack, lowercase, no glyph. Revisit then.

---

| # | Question | Default if you don't care |
| :--- | :--- | :--- |
| D-1 | CLI subcommands (`limen check`) or keep flat flags (`limen --stamp`)? | Subcommands, with bare `limen` defaulting to `check` |
| D-2 | Fold `check-xrefs.py` into the CLI as `limen xrefs`? | Yes |
| D-3 | Version bump for the three standards? Renaming a document ID is the most breaking change a reference can suffer, but nothing external references them yet | `5.0.0`, changelog entry "renamed to Limen; no content change" |
| D-4 | Keep an `limen` shim that warns and forwards? | No — no external consumers, so no deprecation surface is needed |
