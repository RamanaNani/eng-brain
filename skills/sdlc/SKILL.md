---
name: sdlc
version: 2.0.0
description: "The spine. Carries one feature through the whole ladder — story, arch, contract, slice, fleet, before-pr, pr, canary — holding state in docs/arch/<feature>/STATE.json and refusing to advance past a gate that has not been shown to pass. Invoke this instead of the individual stage skills; it decides which stage runs next and stops when a gate fails."
triggers:
  - "build <feature>"
  - "ship <feature>"
  - "where is <feature>"
  - "continue <feature>"
  - "resume the pipeline"
  - "what's next for <feature>"
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - Skill
  - Task
---

# /sdlc — the spine

Stage skills (`/story`, `/arch`, `/contract`, `/slice`, `/fleet`, `/before-pr`, `/pr`,
`/canary`) each do one job well. Nothing sequenced them. That had three consequences worth
naming, because this skill exists to fix exactly them:

1. **"Where is this feature stuck?" was unanswerable** without reading the arch directory
   and inferring.
2. **Gates were advisory.** Invoking `/slice` directly skipped `/arch` silently — the
   stage had no way to know it was being run out of order.
3. **A lost session lost the thread.** Nothing on disk said which stages had passed.

`/sdlc` holds the ladder. It does not reimplement the stages; it dispatches to them.

Read `lib/CONVENTIONS.md` before any brain read or write. Everything there still applies —
this skill adds sequencing, not new brain rules.

## The ladder

| # | Stage | Artifact | Gate to advance |
|---|---|---|---|
| 0 | `story` | `STORY.md` | ≥1 acceptance criterion, ≥1 negative case, ≥1 non-goal |
| 1 | `arch` | `ARCHITECTURE.md` + `ADR-*.md` | ≥2 candidates weighed, 1 recommended, ≥1 ADR written, contradictions surfaced |
| 2 | `contract` *(optional)* | `contracts/` | required iff ≥2 slices share an interface |
| 3 | `slice` | `slices.json` + `slices/NN-*.md` | file ownership disjoint (`owns.py`), DAG acyclic, every failure mode lands in a slice or Out of scope (`gate.py`) |
| 4 | `fleet` | `FLEET.md` | every slice green, **runner output shown** |
| 5 | `before-pr` | `GATE.md` | `gate.py` passes on every slice |
| 6 | `pr` | `PR.md` | PRs opened. **Never merged.** |
| 7 | `canary` *(optional)* | `CANARY.md` | baseline recorded, delta non-regressive |

Optional stages must still be *recorded* — skipped with a reason, never left pending.
"Not applicable" is a decision; make it visible.

## Phase 0 — Preamble

Run the `lib/CONVENTIONS.md` §7 preamble first (`REPO_ROOT`, `SOURCE_BRANCH`, `SOURCE_ID`,
`GBRAIN_PREPARE=true`). Then:

```bash
FEATURE_SLUG="<kebab-case-from-the-ask>"     # /arch coins it; every later stage reuses it
ARCH_DIR="$REPO_ROOT/docs/arch/$FEATURE_SLUG"
STATE="$ENG_BRAIN/lib/bin/state.py"
```

`FEATURE_SLUG` unset is not harmless — `ARCH_DIR` collapses to `docs/arch/` and artifacts
land loose among other features. Fail closed.

## Phase 1 — Locate the feature

```bash
if [ -f "$ARCH_DIR/STATE.json" ]; then
  python3 "$STATE" show "$ARCH_DIR"
else
  python3 "$STATE" init "$ARCH_DIR" --feature "$FEATURE_SLUG" --branch "$SOURCE_BRANCH"
fi
NEXT=$(python3 "$STATE" next "$ARCH_DIR")
```

If the user asked "where is X" or "what's next", `show` is the whole answer. Print it and
stop — do not helpfully start running stages they did not ask for.

## Phase 2 — Run the next stage

Dispatch to the stage skill named by `$NEXT`. One stage per invocation, by default.

Announce the stage before running it and the gate result after. The user should never have
to guess which rung they are on.

**Do not batch the ladder without being asked.** Running story→pr in one sweep produces
seven artifacts the user has reviewed none of, and the review points are the value. If the
user explicitly asks to run through, do it — but stop at the first failing gate regardless.

## Phase 3 — Record the gate

The stage reports its own gate. Record it, and let the recording be the source of truth:

```bash
python3 "$STATE" pass "$ARCH_DIR" --stage "$NEXT" --artifact "<path>"
# or
python3 "$STATE" fail "$ARCH_DIR" --stage "$NEXT" --why "<what failed, concretely>"
# or, optional stages only
python3 "$STATE" skip "$ARCH_DIR" --stage "$NEXT" --why "<why it does not apply>"
```

`state.py` refuses out-of-order `pass` (exit 2) and refuses to skip a mandatory stage
(exit 1). Treat a refusal as correct and surface it — do not work around it by editing
`STATE.json` by hand. If the ladder is genuinely wrong for this feature, that is a
conversation to have, not a file to patch.

On `fail`: stop. Report what failed and what would unblock it. Do not advance, and do not
re-run the stage hoping for a different answer.

## Phase 4 — Write back

Per `CONVENTIONS.md` §5, after a stage passes: repo first, then brain, then **an edge in
the same run** (an orphan page is invisible to `think`), then a timeline entry.

```bash
gbrain capture --file "$ARCH_DIR/<artifact>" --slug projects/"$FEATURE_SLUG" \
  --type project --source "$SOURCE_ID" --quiet
gbrain link projects/"$FEATURE_SLUG" analysis/adr-NNN-<topic> --link-type decided_by
gbrain timeline-add projects/"$FEATURE_SLUG" "$(date +%F)" "<stage> passed"
gbrain tag projects/"$FEATURE_SLUG" eng-brain
```

## Never

- Never merge a PR. `/pr` opens and stops; a human accepts. No `--auto-merge`, no "the
  gate passed so I merged it".
- Never mark a gate `pass` without the evidence in hand. For `fleet` and `before-pr` that
  means actual runner output, not an assertion that tests pass.
- Never hand-edit `STATE.json` to get past a refusal.
- Never let two slices own the same file — `/slice` validates it; if the check fails,
  re-slice rather than "being careful".

## Reporting

End every invocation with the ladder, so position is never ambiguous:

```
offline-sync  ·  slice → fleet
  ✓ story  ✓ arch  – contract (single repo)  ✓ slice  · fleet  · before-pr  · pr  · canary
```
