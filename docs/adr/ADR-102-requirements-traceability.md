# ADR-102 — Requirements are traced, not trusted

- **Date:** 2026-08-15
- **Status:** Accepted
- **Context:** The pipeline could prove tests were green and files were disjoint, but not that the thing the story asked for was actually built.

## Problem

Two gates already held the line on quality: `gate.py testout` proved a slice's tests ran
and passed, and `owns.py` proved no two slices wrote the same file. Neither could answer the
question that matters most to the person who asked for the feature: **did we build what was
asked?**

That gap is structural, not accidental. A requirement nobody implemented has no failing
test — because the test that *would* have caught it was never written. The suite of tests
that *do* exist passes. Every mechanical gate is green. And a whole acceptance criterion has
silently fallen on the floor.

Until this ADR, "all requirements satisfied" was an assertion the agent made, competing with
everything else in context — exactly the kind of prose promise [ADR-101](ADR-101-ladder-as-data.md)
argues you cannot trust. It needed to become a fact a script checks.

## Decision

Make the story→slice mapping **explicit and machine-checked**, in three parts:

1. **Every acceptance criterion gets a stable id** in `STORY.md` — `AC-1`, `AC-2`, …
   `/story` writes them; they never get renumbered, because a slice may already point at one.

2. **Every slice declares which criteria it covers** in `slices.json`:

   ```json
   { "id": "01-sync", "owns": ["..."], "covers": ["AC-1", "AC-3"] }
   ```

3. **`coverage.py map` fails the gate** if any criterion is covered by no slice (a
   requirement nobody built), or if a slice claims a criterion the story does not define (a
   typo, or a criterion deleted from the story but not the slice). It runs in `/slice` (as
   the cut is planned) and again in `/before-pr` (before review attention is spent).

A slice that implements no criterion writes `"covers": []` — a real answer. A slice with no
`covers` key at all is `UNVERIFIED` (exit 3), never a silent pass, following the same
silence-is-not-a-pass rule as `concepts.py`: the slice nobody annotated is the one most
likely to have dropped a requirement.

## Why this shape

- **Coverage is separate from green-ness, on purpose.** `coverage.py` proves a criterion is
  *claimed* by a slice; `gate.py` proves that slice is *green*. A criterion is satisfied only
  when both hold. Keeping them as two gates is what lets `/sdlc` **loop a feature until every
  requirement is both built and proven** — the loop's exit condition is "every AC maps to a
  green slice", which is checkable, rather than "the work feels done", which is not.

- **Mechanical before human.** `/before-pr` runs `coverage.py` before `/review`. The
  cheap check finds a skipped requirement so the expensive human read never has to.
  `/review` still walks each criterion by hand — but for a different bug: *claimed-but-not-
  honoured*, a slice that maps a criterion and then implements a stub. A map cannot catch
  that; a person can.

- **EARS-adjacent, deliberately.** Acceptance criteria are written given/when/then so each
  is a single checkable behaviour with a proof. An id on a paragraph of hand-waving traces
  to nothing useful.

## Consequences

- `STORY.md` and `slices.json` gain a small, stable vocabulary (`AC-<n>`, `covers`). The
  cost is a few tokens per slice; the return is that "we shipped everything" stops being a
  claim and becomes a gate.
- A feature can no longer reach `/pr` with an unbuilt acceptance criterion. That is the whole
  point, and it is the failure this system most wanted to make impossible.
- `coverage.py` is self-checked (`coverage.py selfcheck`), so the gate that guards the
  requirements is itself guarded — like every other gate in `bin/`.

## Alternatives rejected

- **Infer coverage from test names or file paths.** Fragile and dishonest — a heuristic that
  is right most of the time trains you to trust it the time it is wrong. Explicit `covers` is
  a declaration the author is accountable for.
- **One combined "done" gate.** Merging coverage and green-ness into a single check would
  lose the loop: you could no longer ask "which requirements are mapped but still red?",
  which is the exact state a fix-loop iterates on.
- **Leave it to review.** Human review is where *claimed-but-not-honoured* is caught, but
  making it also responsible for *never-claimed* wastes the expensive resource on what a
  script does perfectly.
