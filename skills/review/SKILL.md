---
name: review
version: 2.0.0
description: "Stage 7. Substantive review of what the fleet actually built — scope drift in both directions, plus the /impeccable rubric applied to the real diff. Runs after /before-pr (mechanical gate) and before /pr, because nobody should spend review attention on code whose tests are red."
triggers:
  - "review the slices"
  - "review the diff"
  - "did we build the right thing"
  - "check for scope drift"
allowed-tools:
  - Bash
  - Read
  - Grep
  - Glob
  - Write
  - Skill
---

# /review — did we build the right thing

Stage 7 of the ladder (see `skills/sdlc/SKILL.md`).
Position: `before-pr → **review** → pentest?`.

`/before-pr` proves the code *works*: tests are green and every failure mode reached a
slice. It cannot tell you whether the work is the work that was asked for. A slice can pass
every mechanical check and still have quietly built something else.

That gap is what this stage is for, and it is why review sits *after* the mechanical gate
rather than before it — mechanical checks are cheap and review attention is not. Spending a
careful read on a branch with a red suite wastes the expensive resource to find what the
cheap one would have caught.

Read `skills/_eng-brain/CONVENTIONS.md` first.

## Phase 0 — Preamble

`CONVENTIONS.md` §7, then establish the diff base. Every later phase reads from it, and
getting it wrong silently reviews the wrong commits:

```bash
DIFF_BASE=$(git merge-base origin/"$SOURCE_BRANCH" HEAD)
git diff --stat "$DIFF_BASE"..HEAD
git log "$DIFF_BASE"..HEAD --oneline
```

Use `merge-base`, not `origin/<base>..HEAD` directly. If the base branch moved since the
worktree was cut, the plain range includes other people's commits and you will review work
that is not yours.

## Phase 1 — Scope drift, both directions

This is the phase that earns the stage. Read `STORY.md` and the slice briefs, then compare
against the diff. Drift runs two ways and both matter:

**Built but not asked for.** Every changed file must trace to a slice brief. A file that
belongs to no slice is either scope creep or a missed `contract` — both are findings.

```bash
python3 "$ENG_BRAIN/bin/owns.py" "$ARCH_DIR" --diff-base "$DIFF_BASE"
```

**Asked for but not built.** Walk `STORY.md`'s acceptance criteria one at a time and locate
the code that satisfies each. A criterion with no implementation is the failure mode that
mechanical gates structurally cannot catch: the tests that exist all pass, and the test that
should exist was never written.

Report both as a table, with the specific file or criterion — never as a summary:

```markdown
| Direction | Item | Evidence |
|---|---|---|
| unasked | `src/telemetry.ts` | changed, owned by no slice |
| missing | AC-3 "offline edits queue" | no implementation found |
```

## Phase 2 — Apply the rubric

Run `/impeccable` against the diff: correctness, honesty of evidence, blast radius,
reversibility. Do not restate its output — record the grades and the "to clear" line for
any non-pass.

Pay particular attention to blast radius here. `/slice` proved ownership was disjoint *as
planned*; this is the first point where you see what was actually touched.

## Phase 3 — Write REVIEW.md

```markdown
# Review — <feature-slug>
- **Date:** <YYYY-MM-DD>
- **Diff base:** <sha>
- **Verdict:** PASS | CHANGES REQUESTED

## Scope drift
| Direction | Item | Evidence |
|---|---|---|

## Rubric
| Axis | Grade | Why |
|---|---|---|

## Must fix before PR
<numbered, specific, each naming the file>

## Noted, not blocking
<things worth saying that should not hold up the PR>
```

Separating blocking from non-blocking is not politeness. A review that mixes them makes the
author guess which comments are gates, and the usual guess is "none of them."

## Phase 4 — Record

```bash
python3 "$ENG_BRAIN/bin/state.py" pass "$ARCH_DIR" --stage review --artifact REVIEW.md
# or
python3 "$ENG_BRAIN/bin/state.py" fail "$ARCH_DIR" --stage review --why "<what must change>"
```

On `CHANGES REQUESTED`, stop. Do not open PRs. The fix loop goes back to `/fleet` for the
affected slice, not forward.

Then capture `REVIEW.md` to the brain per `CONVENTIONS.md` §5, with an edge in the same run.
Scope drift is worth remembering — a slice that drifted once tends to drift again, and
`gbrain think` can surface that on the next `/arch`.

## Never

- Never review against the diff alone. Without `STORY.md` you can only see what changed, not
  what was supposed to change, and the missing half is invisible.
- Never pass a criterion you could not locate in the code. Mark it missing.
- Never let "the tests pass" substitute for this stage — that is `/before-pr`, and it has
  already run.
- Never open a PR on `CHANGES REQUESTED`.
