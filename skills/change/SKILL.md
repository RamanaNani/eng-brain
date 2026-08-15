---
name: change
version: 1.0.0
description: "Scope work on code that already exists — a behavior change, a refactor, a scalability or extensibility pass. Establishes blast radius, captures a baseline before anything moves, and writes the invariants that must survive. Writes CHANGE.md. Replaces /story when the code is already there."
triggers:
  - change
  - modify
  - refactor
  - make it faster
  - make it scale
  - extend
  - update the feature
  - rework
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Grep
  - Glob
  - AskUserQuestion
---

# /change — the ask, when the code already exists

`/story` asks what must become true. That is the whole job for a new feature, and
half the job for anything else.

On existing code the other half is **what must stay true**, and unlike the first
half it is not a matter of opinion — it is mechanically discoverable. Callers
exist. Tests exist. Numbers exist. A change that did not look them up is not
scoped; it is a guess with a diff attached.

**Read `~/.claude/skills/_eng-brain/CONVENTIONS.md` first.**

## The one inviolable rule

**No baseline, no change.** You may not proceed to `/arch` without a captured
before-state: the current behavior written down, and for any performance or scale
work, the current number with the command that produced it. "It's faster now" is
not a result. "p95 840ms → 190ms, same command, same dataset" is.

## When to invoke

| Shape of work | Entry point |
|---|---|
| New feature, nothing exists yet | `/story` |
| Bug, cause unknown | `/investigate` first, then `/change` only if the fix is broad |
| Bug, cause known, one or two files | Just fix it, then `/qa`. No pipeline. |
| Behavior must differ | `/change` |
| Behavior identical, structure better (refactor, extensibility) | `/change`, with an empty "must change" table |
| Must handle more load | `/change`, with a measured baseline |

The test for whether this skill is needed at all: if you cannot name every caller
from memory, you need it. If you can, fix the thing and move on.

## Phase 0 — Preamble and preflight

Preamble from CONVENTIONS.md §7, then:

```bash
FEATURE_SLUG=<kebab-case>
REPO_ROOT=$(git rev-parse --show-toplevel)
ARCH_DIR="$REPO_ROOT/docs/arch/$FEATURE_SLUG"
mkdir -p "$ARCH_DIR"
```

## Phase 1 — Blast radius, found mechanically

Never from memory, and never from the agent's summary of the code.

```bash
# Every caller of what you are about to change.
rg -n --glob '!**/node_modules/**' -w "<function_or_symbol>" "$REPO_ROOT"

# Every definition site of the shared types involved — the same gate /slice runs.
python3 ~/.claude/skills/_eng-brain/bin/concepts.py "$MANIFEST" "$REPO_ROOT" [<other_repo>...]

# Every test that currently covers it. If this returns nothing, that is the finding.
rg -l --glob '**/*{test,spec}*' -w "<function_or_symbol>" "$REPO_ROOT"
```

Record the counts in CHANGE.md. A change with 40 callers is a different design
problem from one with 2, and the count decides whether this is one slice or a
wave — before `/arch` gets an opinion about it.

If the symbol crosses a repo boundary, stop and run `/contract` before continuing.

## Phase 2 — Capture the baseline, before anything moves

Two kinds; use whichever applies, and often both.

**Behavioral baseline.** If tests already cover the current behavior, name them.
If they do not, write a **characterization test** now — one that asserts what the
code does today, including the parts that look wrong. Its job is not to be
correct; its job is to go red the moment the change alters something nobody meant
to alter. Commit it before touching anything.

```bash
git add <characterization test> && git commit -m "test: characterize <thing> before changing it"
```

**Numeric baseline.** For any scalability, latency, cost, or memory work, record
the number *and* how to reproduce it:

| Metric | Now | Command | Dataset |
|---|---|---|---|
| p95 search latency | 840 ms | `pnpm bench search` | 10k-doc fixture |
| tokens per request | 12,400 | `python bench/tokens.py` | 50-query sample |

A target with no baseline is a wish. A baseline with no reproducible command is a
number somebody remembers.

## Phase 3 — Invariants: what must not change

The list that protects everything the change is not about.

- Public API shape callers depend on
- On-the-wire formats, storage formats, anything already persisted
- Behavior the characterization tests pin
- Numbers that must not regress, with their tolerance

Each invariant names how it is enforced. An invariant with no enforcement is a
hope, and hopes are what agents quietly break while passing their own tests.

## Phase 4 — What must change

The same acceptance-criteria table `/story` uses: each row given/when/then, each
row with a proof command.

For a pure refactor this table is **empty**, and that is the correct answer. An
empty must-change table plus a full invariant list is exactly what a refactor is.
Writing it down is what stops the agent inventing improvements along the way.

## Phase 5 — Write CHANGE.md and gate

```markdown
# <Thing> — change

## Why now
<the pressure forcing this: a bug, a limit hit, a feature blocked by the shape>

## Changes what
- [[projects/<slug>]] — the feature being modified
- [[analysis/adr-007-<topic>]] — the decision being revisited, or "none"

Wikilink syntax, not prose. Phase 6 turns these into the page's edges.

## Blast radius
- callers: N (list, or the rg command and its count)
- definition sites: N — concepts.py output
- existing tests covering this: N (list, or "none — characterization test added at <sha>")
- crosses a repo boundary: yes/no → CONTRACTS.md at <path>

## Baseline
| Metric | Now | Command | Dataset |
Behavioral: <test names, or the characterization test sha>

## Invariants — must not change
| # | Invariant | Enforced by |

## Must change
| # | Given / when / then | How it is proven |

## Explicitly out of scope
- ...
```

**Gate — all must hold before `/arch` may run:**

- [ ] Caller count came from a command, not from memory
- [ ] `concepts.py` has been run for every shared type being touched
- [ ] Behavioral baseline exists: named existing tests, or a committed
      characterization test
- [ ] Every numeric target has a before-number and a reproducible command
- [ ] Every invariant names its enforcement
- [ ] For a refactor, the must-change table is empty and says so explicitly

Then **stop** and hand back for review. Do not chain into `/arch`.

## Phase 6 — Write back to the brain

`mcp__gbrain__recall "<the thing being changed>"` in Phase 1, before scoping. Reads
through MCP are fine; the write is not.

```bash
gbrain capture --file "$ARCH_DIR/CHANGE.md" \
  --slug "change-$FEATURE_SLUG" --type analysis --source default --quiet
```

Three things about that line, none of them optional:

- **`--source default`.** `capture` matches the current directory against registered code
  sources before falling back to `default`, so running this from inside a repo that is a
  registered gbrain source files the page into that *code* source — while every other
  command resolves slugs against `default`. Both halves report success and the page is
  unreachable.
- **Not `mcp__gbrain__put_page`.** The MCP tool returns `auto_links: {"skipped":"remote"}`;
  remote callers get no wikilink extraction, so the page lands orphaned regardless of body.
- **The `[[wikilinks]]` in CHANGE.md are the edges.** Write the pages this change touches
  as wikilinks rather than prose: the ADR whose decision is being revisited
  (`[[analysis/adr-007-<topic>]]`), the feature being modified
  (`[[projects/<slug>]]`), the investigation that led here. Those pages already exist —
  that is the whole reason `/change` applies rather than `/story` — so each one becomes a
  real edge at capture time with no second call that can fail on its own.

That last point is what makes `/change` the better-connected half of the pipeline. A
change is by definition attached to something already in the brain; a page that records
one and links to nothing has lost the only context that made it worth writing.

Record the baseline numbers specifically. Six months on, the only thing anyone
wants from this document is what it used to be.

Verify, because `capture --json` reports slug, status and hash and says nothing about how
many links it extracted — a page with six edges and a page with none look identical in its
output:

```bash
gbrain graph-query "change-$FEATURE_SLUG" --direction out --depth 1
```

No edges means the write-back failed. Say so and fix it; do not report the brain write as
done.

## Failure modes

| Smell | What it means | Do this |
|---|---|---|
| "It should be faster" | No baseline, so no result is provable | Measure first, then scope |
| Caller list from the agent's summary | It read some of the code | Run the command yourself, paste the count |
| Refactor with a non-empty must-change table | Not a refactor — a change wearing one | Split into two passes |
| No existing tests, none added | Every later gate is checking nothing | Characterization test before scoping |
| Invariant with no enforcement | It will be broken silently | Give it a test or delete the claim |
| "Make it extensible" | Nobody has named the second use case | Name it, or do not build the seam yet |
| Blast radius over ~20 callers | This is a wave, not a slice | Expect 3-4 slices at `/slice` |
