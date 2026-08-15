---
name: fleet
version: 1.0.0
description: "Run sliced work across parallel git worktrees. One agent per slice, wave by wave, each gated on real tests and written docs before it may push. Opens a PR per slice against your source branch and STOPS — you accept, then /fleet --accept merges and writes outcomes back to gbrain. Stage 5 of 11 in the ladder (story -> arch -> contract? -> slice -> fleet -> before-pr -> review -> pentest? -> pr -> deploy? -> canary?)."
triggers:
  - fleet
  - run the worktrees
  - build the slices
  - execute the plan
  - run the fleet
  - fleet accept
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Grep
  - Glob
  - Agent
  - Workflow
  - AskUserQuestion
---

# /fleet — parallel worktrees, gated, PR-only

Stage 5 of 11. `/arch` decided. `/slice` divided. `/fleet` builds — in parallel,
in isolated worktrees, and **it never merges**.

**Read `$ENG_BRAIN/CONVENTIONS.md` first.**

## The one inviolable rule

`/fleet` opens pull requests and stops. It does not merge. It does not enable
auto-merge. It does not merge "because the gate passed". The user accepts, explicitly,
and only then does `/fleet --accept` merge.

If you are ever unsure whether you are allowed to merge: you are not.

## When to invoke

After `/slice`, when the user says "fleet", "run the worktrees", "build the slices",
"execute the plan". Use `/fleet --accept` after they have reviewed the PRs.

## Phase 0 — Preamble and preflight

Preamble from CONVENTIONS.md §7, then:

```bash
FEATURE_SLUG=<from the ask or the most recent arch dir>
ARCH_DIR="$REPO_ROOT/docs/arch/$FEATURE_SLUG"
MANIFEST="$ARCH_DIR/slices.json"
[ -f "$MANIFEST" ] || { echo "no slices.json — run /slice first"; exit 1; }

# The PR target is what /slice recorded, NOT whatever branch you happen to be on now.
TARGET=$(python3 -c "import json;print(json.load(open('$MANIFEST'))['source_branch'])")

# Preflight — every one of these must pass before a single worktree is created.
git diff --quiet && git diff --cached --quiet || { echo "BLOCKED: uncommitted changes"; exit 1; }
git rev-parse --verify "$TARGET" >/dev/null 2>&1 || { echo "BLOCKED: target branch $TARGET missing"; exit 1; }
gh auth status >/dev/null 2>&1 || { echo "BLOCKED: gh not authenticated"; exit 1; }
python3 "$ENG_BRAIN/bin/owns.py" "$MANIFEST" "$REPO_ROOT" || { echo "BLOCKED: slice ownership collision"; exit 1; }
echo "preflight OK — target=$TARGET"
```

Re-running the ownership check here is deliberate. The tree may have changed since
`/slice` ran, and a collision discovered mid-fleet costs far more than one caught now.

## Phase 1 — Wave execution

Compute waves from `depends_on` (same algorithm as `/slice` Phase 3). Run **one wave at
a time**; within a wave, all slices run in parallel. A wave is a genuine barrier — wave
2 slices consume wave 1's merged interfaces.

Drive it with the `Workflow` tool using `isolation: 'worktree'`, which gives each agent
its own git worktree so parallel edits cannot collide:

```javascript
export const meta = {
  name: 'fleet-wave',
  description: 'Build one wave of slices in isolated worktrees, gated on tests + docs',
  phases: [{ title: 'Build' }, { title: 'Verify' }],
}

// args: { feature, repoRoot, target, slices: [{id, name, brief, owns, branch}] }
const built = await pipeline(
  args.slices,
  s => agent(
    `You are building ONE slice in an isolated git worktree.\n\n` +
    `Read the brief at ${args.repoRoot}/docs/arch/${args.feature}/${s.brief} and implement it.\n\n` +
    `HARD RULES:\n` +
    `1. Write ONLY files matching: ${s.owns.join(', ')}. Another agent owns everything else RIGHT NOW.\n` +
    `2. Write real tests covering every edge case the brief lists. Run them. Paste the runner output.\n` +
    `3. Update docs for what you changed and WHY.\n` +
    `4. Commit on branch ${s.branch}. Do NOT merge. Do NOT open a PR.\n` +
    `5. If the brief is wrong or you must touch a file you do not own, STOP and report it.\n\n` +
    `Return JSON: {slice, files_written, tests_run, tests_passed, test_output, docs_updated, blocked, blocker}`,
    // agentType comes from /slice Phase 3.5 — the specialist matched to what this slice touches.
    { label: `build:${s.id}`, phase: 'Build', isolation: 'worktree',
      agentType: s.agents?.build || 'software-developer', schema: BUILD_SCHEMA }
  ),
  (r, s) => (r?.blocked || !r?.tests_passed) ? r : parallel([
    () => agent(`Adversarially review the diff on branch ${s.branch} for slice ${s.id}. ` +
                `Find real defects: unhandled errors, missing validation at trust boundaries, ` +
                `swallowed exceptions, files written outside ${s.owns.join(', ')}. ` +
                `Report only defects you can point at a line for.`,
                { label: `review:${s.id}`, phase: 'Verify',
                  agentType: s.agents?.review || 'ecc:code-reviewer', schema: REVIEW_SCHEMA }),
    () => agent(`Verify slice ${s.id}'s tests actually exercise the brief's edge cases. ` +
                `A test that asserts nothing, or only the happy path, is a FAIL. Return {adequate, gaps[]}.`,
                { label: `tests:${s.id}`, phase: 'Verify',
                  agentType: s.agents?.test || 'ecc:tdd-guide', schema: TESTGATE_SCHEMA }),
  ]).then(([review, tests]) => ({ ...r, review, tests }))
)
return built.filter(Boolean)
```

Use `pipeline`, not `parallel` between stages — a slice that finishes building should
start its review immediately rather than waiting for its slowest sibling.

## Phase 2 — The gate

A slice may push **only** if all four hold:

| Gate | Pass condition |
|---|---|
| Tests | tests ran and passed, with runner output shown — never "should pass" |
| Edge cases | every edge case in the brief has a test that actually asserts on it |
| Docs | what changed and why, updated in the repo |
| Ownership | `git diff --name-only $TARGET...HEAD` ⊆ the slice's `owns` globs |

Verify ownership mechanically per slice — this is the check that catches an agent that
helpfully wandered:

```bash
git -C "$WT" diff --name-only "$TARGET"...HEAD
```

Any file outside `owns` fails the gate. Do not merge it in manually and do not wave it
through; report it and let the user decide.

A slice that fails any gate does **not** push. Report it as failed with the reason, and
keep going with the rest of the wave — one bad slice must not block three good ones.

## Phase 3 — Push and open PRs

For each slice that passed all four gates:

```bash
git -C "$WT" push -u origin "$BRANCH"
gh pr create \
  --base "$TARGET" \
  --head "$BRANCH" \
  --title "$FEATURE_SLUG/$SLICE_ID: $SLICE_NAME" \
  --body "$(cat <<EOF
Implements slice $SLICE_ID of \`docs/arch/$FEATURE_SLUG/ARCHITECTURE.md\`.

## What changed
<from the agent's report>

## Tests
\`\`\`
<actual runner output>
\`\`\`

## Edge cases covered
<from the brief, each with its test>

## Files (all within slice ownership)
<git diff --name-only>

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Then set `status: "pr_open"` on that slice in `slices.json` and commit the manifest.

**Stop here.** Do not merge.

## Phase 4 — Report and hand back

```
Fleet: <feature> wave 1 of 3

  ✓ 01-sync-schema       PR #241 → dev   12 tests, 4 edge cases   docs ✓
  ✓ 02-conflict-resolver PR #242 → dev    9 tests, 6 edge cases   docs ✓
  ✗ 03-api-layer         BLOCKED — needed src/types.ts (owned by 01)

2 PRs open against dev. Nothing merged.

Review them, then: /fleet --accept    (merges accepted PRs, runs wave 2)
Slice 03 needs a re-cut — its brief assumed ownership it does not have.
```

## Phase 5 — `/fleet --accept`

Only runs when the user explicitly asks. For each PR the user accepted:

```bash
gh pr merge "$PR" --squash --delete-branch      # only for user-accepted PRs
git -C "$REPO_ROOT" worktree remove "$WT"
```

Then write outcomes back to the brain — this is what makes the next `/arch` smarter:

```bash
gbrain timeline-add projects/$FEATURE_SLUG $(date +%F) \
  "Slice 01 sync-schema merged (PR #241): <what shipped, in one line>"
gbrain link projects/$FEATURE_SLUG analysis/adr-012-<topic> --link-type implements
```

If implementation contradicted an ADR — you discovered the decision was wrong once you
built it — that is the **most valuable thing** to record. Write a new ADR with a
`supersedes` edge to the old one and say what reality taught you. A brain that only
records decisions that worked teaches you nothing.

Then advance to the next wave, or report the fleet complete.

## Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Merge conflict between slices | ownership collision `/slice` missed | Re-run `owns.py`; re-cut. Never hand-resolve into another slice's files. |
| Agent reports tests pass, no output | it did not run them | Gate requires pasted runner output. Fail it. |
| PR targets the wrong branch | read the current branch instead of the manifest | `TARGET` comes from `slices.json.source_branch`, always |
| Wave 2 built against stale interfaces | wave 1 PRs not merged before wave 2 started | Waves are barriers; wave 2 starts only after wave 1 is accepted |
| Worktree left behind | `--accept` interrupted | `git worktree list` then `git worktree remove <path>` |
