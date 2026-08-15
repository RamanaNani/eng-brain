---
name: impeccable
version: 2.0.0
description: "The quality standard the pipeline enforces, not a pipeline stage. A rubric for reviewing work produced by /fleet or by hand — correctness, honesty of evidence, blast radius, and reversibility. Invoke to grade a diff, a slice, or an artifact against a fixed bar rather than against taste."
triggers:
  - "is this impeccable"
  - "grade this"
  - "review against the bar"
  - "hold this to the standard"
allowed-tools:
  - Bash
  - Read
  - Glob
  - Grep
---

# /impeccable — the bar

Not a rung on the ladder. `/sdlc` never dispatches to this. It is the standard that
`/before-pr` mechanises and that a human applies where mechanisation runs out.

Read `$ENG_BRAIN/CONVENTIONS.md` first.

## Why a rubric and not taste

Review quality drifts with fatigue and with who is asking. A fixed rubric makes the bar
the same on a Friday as on a Monday, and makes a rejection explainable — the author can
see which axis failed rather than hearing "this doesn't feel right".

## The four axes

Grade each **pass / weak / fail**. Any `fail` is a `fail` overall; axes do not average out.

### 1. Correctness — does it do what it claims?

- Does the change do what its STORY acceptance criteria say, including the negative cases?
- Are the failure modes from `ARCHITECTURE.md` actually handled, or only mentioned?
- Is there a test that would fail if the change were reverted? A test that passes both
  ways is documentation, not verification.

### 2. Honesty of evidence — is the claim backed?

- Is "tests pass" backed by runner output, or asserted?
- Are numbers reproducible — is the method recorded alongside the value?
- Are the limits of what was checked stated? Unstated scope reads as full coverage.
- If something was skipped, is the skip visible, with a reason?

This axis fails more real work than correctness does, and it is the one most worth being
strict about: a wrong claim that looks verified costs more than an obvious gap.

### 3. Blast radius — what else can this reach?

- Which files does it touch that no slice claimed? (`$ENG_BRAIN/bin/owns.py`)
- Does it change a shared interface without a `contract` entry?
- Does it widen permissions, add a network call, or touch auth, migrations, or deletion
  paths? Any of those raise the bar rather than meet it.
- Could it fail *silently*? Prefer a loud failure over a quiet wrong answer — the
  `GBRAIN_PREPARE` bug is the canonical example: it returned empty results rather than
  erroring, so it read as "the brain is thin" for weeks.

### 4. Reversibility — how expensive is being wrong?

- Can this be reverted with `git revert`, or has it written state that a revert leaves
  behind — a migration, a published page, a deleted row, an external side effect?
- Is it behind a flag? Should it be?
- If it is irreversible, does the evidence justify irreversibility? The bar scales with
  the cost of being wrong; a one-way door needs more than a two-way door.

## Output

```markdown
# Impeccable review — <what was reviewed>

| Axis | Grade | Why |
|---|---|---|
| Correctness | pass | … |
| Honesty of evidence | weak | p95 quoted with no method |
| Blast radius | pass | … |
| Reversibility | fail | migration with no down path |

**Verdict:** FAIL — reversibility.
**To clear:** <the specific, smallest change that would flip the failing axis>
```

"To clear" is required on any non-pass. A rejection without a route forward is a
complaint, not a review.

## Never

- Never grade an axis you did not check. Mark it `unchecked` and say so.
- Never let a strong axis compensate for a failing one.
- Never soften a `fail` because the work was effortful, or because the deadline is close.
  The bar exists precisely for the moments when it is inconvenient.
