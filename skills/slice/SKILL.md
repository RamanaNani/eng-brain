---
name: slice
version: 1.0.0
description: "Split an architecture into conflict-free parallel work slices. Assigns each slice exclusive file ownership, validates no two slices can collide, builds the dependency DAG, and writes one self-contained brief per slice plus slices.json. Stage 4 of 11 in the ladder (story -> arch -> contract? -> slice -> fleet -> before-pr -> review -> pentest? -> pr -> deploy? -> canary?)."
triggers:
  - slice
  - split this architecture
  - break into tasks
  - decompose the work
  - divide into sections
  - plan the worktrees
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Grep
  - Glob
  - Agent
  - AskUserQuestion
---

# /slice — architecture into conflict-free parallel work

Stage 4 of 11. `/arch` decided what to build. `/slice` decides **who can work in
parallel without stepping on each other**. `/fleet` executes it.

**Read `~/.claude/skills/_eng-brain/CONVENTIONS.md` first.**

## When to invoke

After `/arch`, when the user wants the work divided: "slice it", "split this up",
"break into tasks", "divide into sections", "plan the worktrees".

If there is no `docs/arch/<slug>/ARCHITECTURE.md`, stop and run `/arch` first.
Slicing without an architecture produces tasks that contradict each other.

## Phase 0 — Preamble

Preamble from CONVENTIONS.md §7, then:

```bash
FEATURE_SLUG=<from the arch dir or the ask>
ARCH_DIR="$REPO_ROOT/docs/arch/$FEATURE_SLUG"
[ -f "$ARCH_DIR/ARCHITECTURE.md" ] || { echo "no architecture — run /arch first"; exit 1; }
mkdir -p "$ARCH_DIR/slices"
```

Read `ARCHITECTURE.md` in full, especially the **interfaces** section. Those interfaces
are the contract that lets slices be built blind to each other.

## Phase 0.5 — Learn how this user slices work

Before cutting anything, ask the brain how they have done it before. Slicing is a style
decision as much as a technical one, and the brain is where that style accumulates.

Cheap searches first. `gbrain think` is an uncached agentic loop and is the slowest call in
this skill; slice style is a lookup, not a reasoning problem, so it almost never earns one.

```bash
gbrain query "slice plan waves ownership" --no-expand
gbrain graph-query projects/<a-past-feature> --direction out --depth 2
```

Only if those come back empty *and* this is a large or unusual cut, escalate once:

```bash
gbrain think "What slice sizes and boundaries have worked for me, and which caused merge conflicts?"
```

Otherwise skip it. An empty brain does not get less empty by being searched harder.

Look specifically for:
- **Slice size** they settled on — 3 big or 6 small
- **Boundary style** — by layer, by bounded context, by entrypoint
- **Past collisions** — any timeline entry recording a merge conflict names a cut that
  failed. Do not repeat it.
- **Specialist assignments** that worked, feeding Phase 3.5

If the brain returns nothing, say so and proceed with the defaults below — then this run
becomes the first data point. Write the outcome back in Phase 5 so the next `/slice`
inherits it. That is the whole compounding mechanism; skipping the write-back breaks it.

## Phase 1 — Cut the slices

A good slice is:

- **Independently completable** — one agent, one worktree, no waiting on a sibling
  mid-flight. If it needs a sibling's output, that is a `depends_on`, not a parallel peer.
- **Exclusively owned** — it writes only files no other slice writes.
- **Verifiable alone** — it has its own tests that pass without the other slices.
- **One coherent change** — "add the sync table + its migration + its model" is a slice.
  "touch everything related to sync" is not.

Typical cuts that work: by layer (schema → API → UI), by bounded context, by
entrypoint. Cuts that fail: by file type, by "frontend/backend" when both edit shared
types, by developer preference.

Aim for **3–6 slices**. More than 6 and the coordination cost eats the parallelism;
fewer than 3 and you did not need a fleet.

Shared files (types, config, barrel exports, DI registration) are the usual collision
point. Handle them one of two ways, never by hoping:
1. Give one slice sole ownership and make the others depend on it, or
2. Pull the shared edit into a **slice 00** that runs alone first.

## Phase 1.5 — Tractability, and the cross-repo precondition

A slice can be perfectly cut and still be un-buildable, because the file it owns is
too large for an agent to edit safely. Not hypothetical: a 5,339-line component burned
two agent attempts on `data-analysis-ai-seam/N02` before the file, rather than the
agent, was identified as the problem. Find that here, for free, instead of there, twice.

```bash
python3 ~/.claude/skills/_eng-brain/bin/tractable.py "$MANIFEST" "$REPO_ROOT"
```

Any file at or over 1500 lines fails the gate. Two legitimate ways forward:

1. **Split the file first**, as its own slice 00 that runs alone.
2. **Declare `"edit_strategy": "surgical"`** on the slice, and make the brief name the
   exact functions, symbols, or line regions the agent may touch. Surgical means the
   agent reads the whole file and edits three named places — never "refactor this
   component". Pair it with serena for symbol-level edits.

Files between 800 and 1500 lines warn. A warning is not a blocker, but the brief must
name the regions to touch.

**Cross-repo precondition.** If the feature spans more than one repo,
`docs/arch/<slug>/CONTRACTS.md` must already exist from `/contract`, and `slices.json`