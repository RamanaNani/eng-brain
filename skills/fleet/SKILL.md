---
name: fleet
version: 1.0.0
description: "Run sliced work across parallel git worktrees. One agent per slice, wave by wave, each gated on real test output before the next wave starts. Assembles passing slices onto an integration branch and STOPS — it never opens PRs and never merges. /before-pr gates, /review reads the seam, /pr publishes, a human merges."
triggers:
  - fleet
  - run the worktrees
  - build the slices
  - execute the plan
  - run the fleet
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

# /fleet — parallel worktrees, gated, integration-only

Stage 5 of 11. `/arch` decided. `/slice` divided. `/fleet` builds — in parallel,
in isolated worktrees, and **it never merges and never opens a PR**.

**Read `$ENG_BRAIN/CONVENTIONS.md` first.**

## The one inviolable rule

`/fleet` assembles passing slices onto an integration branch and stops. It does not open
pull requests — that is `/pr`, stage 9, after `/before-pr` and `/review` have both passed.
It does not merge, it does not enable auto-merge, and it does not merge "because the gate
passed". A human merges, and only then does `/deploy` pick up.

There is no `--accept` subcommand. An earlier design had one; the ladder replaced it, and
the merge decision now sits with a person rather than a flag.

If you are ever unsure whether you are allowed to merge: you are not.

## When to invoke

After `/slice`, when the user says "fleet", "run the worktrees", "build the slices",
"execute the plan". The next stage is `/before-pr`; a human merges later, after `/pr`.

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
# Worktree isolation derives from the SESSION cwd, not from $REPO_ROOT. If they differ,
# every agent in the wave silently builds against the wrong repo. Assert, do not assume.
CWD_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
[ "$CWD_ROOT" = "$REPO_ROOT" ] || { echo "BLOCKED: session cwd repo ($CWD_ROOT) != REPO_ROOT ($REPO_ROOT) — cd \"$REPO_ROOT\" and re-run"; exit 1; }
git diff --quiet && git diff --cached --quiet || { echo "BLOCKED: uncommitted changes"; exit 1; }
git rev-parse --verify "$TARGET" >/dev/null 2>&1 || { echo "BLOCKED: target branch $TARGET missing"; exit 1; }
python3 "$ENG_BRAIN/bin/owns.py" "$MANIFEST" "$REPO_ROOT" || { echo "BLOCKED: slice ownership collision"; exit 1; }
# gh is not needed here — /fleet assembles locally and pushes nothing. It is only a
# warning, so a local build is not blocked; /pr enforces gh auth as a hard gate later.
gh auth status >/dev/null 2>&1 || echo "note: gh not authenticated — fine for /fleet, but /pr will need it"
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
    `0. FIRST command, before reading anything: \`git rev-parse --path-format=absolute --git-common-dir\`.\n` +
    `   It MUST be ${args.repoRoot}/.git — your worktree path differs, its git dir must not.\n` +
    `   Anything else means you are bound to the WRONG REPO: change nothing, return blocked with that path.\n` +
    `1. Write ONLY files matching: ${s.owns.join(', ')}. Another agent owns everything else RIGHT NOW.\n` +
    `2. Write real tests covering every edge case the brief lists. Run them. Paste the runner output.\n` +
    `3. Update docs for what you changed and WHY.\n` +
    `4. Commit on branch ${s.branch}. Do NOT merge. Do NOT open a PR.\n` +
    `5. If the brief is wrong or you must touch a file you do not own, STOP and report it.\n` +
    `6. NEVER run \`git stash\`. Worktrees have separate working dirs but share refs/stash —\n` +
    `   your stash would clobber a sibling agent's. Commit to ${s.branch} instead.\n\n` +
    `Return JSON: {slice, files_written, tests_run, tests_passed, test_output, docs_updated, blocked, blocker}`,
    // agentType comes from /slice Phase 3.5 — the specialist matched to what this slice
    // touches, defaulting to eng-brain's own roster when no specialist plugin is installed.
    { label: `build:${s.id}`, phase: 'Build', isolation: 'worktree',
      agentType: s.agents?.build || 'eng-brain:slice-implementer', schema: BUILD_SCHEMA }
  ),
  (r, s) => (r?.blocked || !r?.tests_passed) ? r : parallel([
    () => agent(`Adversarially review the diff on branch ${s.branch} for slice ${s.id}. ` +
                `Find real defects: unhandled errors, missing validation at trust boundaries, ` +
                `swallowed exceptions, files written outside ${s.owns.join(', ')}. ` +
                `Report only defects you can point at a line for.`,
                { label: `review:${s.id}`, phase: 'Verify',
                  agentType: s.agents?.review || 'eng-brain:slice-reviewer', schema: REVIEW_SCHEMA }),
    () => agent(`Verify slice ${s.id}'s tests actually exercise the brief's edge cases ` +
                `and the acceptance criteria it covers (${(s.covers || []).join(', ') || 'none'}). ` +
                `A test that asserts nothing, or only the happy path, is a FAIL. Return {adequate, gaps[]}.`,
                { label: `tests:${s.id}`, phase: 'Verify',
                  agentType: s.agents?.test || 'eng-brain:test-auditor', schema: TESTGATE_SCHEMA }),
  ]).then(([review, tests]) => ({ ...r, review, tests }))
)
return built.filter(Boolean)
```

Use `pipeline`, not `parallel` between stages — a slice that finishes building should
start its review immediately rather than waiting for its slowest sibling.

### The bounded fix loop

A slice that comes back red or blocked is not the end of the wave — it is one turn of a
loop with a hard stop. Feed the failure **verbatim** (the runner output, the reviewer's
findings, the blocker) back to a fresh `slice-implementer` for that slice and re-run its
gate. Cap it: **at most 3 build attempts per slice.** After the third, stop looping and
mark the slice `blocked` with the last failure recorded — a slice that will not go green in
three tries has a wrong brief or a wrong cut, and the fix is to re-slice or re-brief, not to
spend a fourth agent. Never lift the cap to "just get it green": an unbounded fix loop is
how a pipeline burns a day thrashing on one slice. The loop's exit is the *gate*, never the
agent's own sense that it is done.

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

## Phase 3 — Assemble onto the integration branch

`/fleet` does **not** open pull requests — that is `/pr`, stage 9, after `/before-pr` and
`/review` have passed. What it does here is assemble every passing slice onto a single
integration branch, so the next stages have one coherent diff to gate and review.

```bash
INTEGRATION="integration/$FEATURE_SLUG"
git rev-parse --verify "$INTEGRATION" >/dev/null 2>&1 || git branch "$INTEGRATION" "$TARGET"

# For each slice that passed all four gates, fast-forward its work onto integration.
for BRANCH in "${PASSED_BRANCHES[@]}"; do
  git -C "$REPO_ROOT" checkout "$INTEGRATION"
  git -C "$REPO_ROOT" merge --no-ff "$BRANCH" -m "assemble $BRANCH into $INTEGRATION" \
    || { echo "ASSEMBLY CONFLICT on $BRANCH — ownership gate missed a collision; re-cut"; exit 1; }
done
```

A merge conflict here is not something to hand-resolve into another slice's files — it means
the ownership gate missed a collision, and the answer is to re-cut, per rule #1's spirit.
Then set `status: "assembled"` on each passing slice in `slices.json` and commit the
manifest.

`integration/<feature>` stays local until `/pr`. Nothing is pushed and no PR is opened here.

### Then remove the worktrees

The harness auto-removes a worktree only if the agent left it *unchanged* — and a slice that
built anything committed, so every worktree that did real work survives the wave. Once a
slice is assembled its worktree holds nothing the refs don't: the commits are on `$BRANCH`
and on `integration/$FEATURE_SLUG`. Remove it here, not at `/pr` — `/pr` runs only after a
human merges, and never runs at all when the pipeline stops early, which is most of the time.

```bash
# Only worktrees whose slice assembled. A blocked slice keeps its worktree for inspection.
for BRANCH in "${PASSED_BRANCHES[@]}"; do
  WT=$(git -C "$REPO_ROOT" worktree list --porcelain \
       | awk -v b="branch refs/heads/$BRANCH" '/^worktree /{p=substr($0,10)} $0==b{print p}')
  [ -n "$WT" ] || continue
  git -C "$REPO_ROOT" worktree remove "$WT" 2>/dev/null \
    || echo "note: $WT has uncommitted changes — left in place; inspect before 'worktree remove --force'"
done
git -C "$REPO_ROOT" worktree prune     # drop admin entries whose dirs are already gone
git -C "$REPO_ROOT" worktree list      # what remains; blocked slices are expected here
```

Never `--force` inside that loop. A worktree that refuses to go has uncommitted work in it,
and that is a finding — a slice that wrote more than it committed — not an obstacle to clear.

**Stop here.** Do not merge, do not push, do not open a PR.

## Phase 4 — Report and hand back

```
Fleet: <feature> wave 1 of 3

  ✓ 01-sync-schema       assembled → integration/<feature>   12 tests, 4 edge cases, AC-1 AC-4   docs ✓
  ✓ 02-conflict-resolver assembled → integration/<feature>    9 tests, 6 edge cases, AC-2 AC-3   docs ✓
  ✗ 03-api-layer         BLOCKED (3 attempts) — needed src/types.ts (owned by 01)

2 slices assembled onto integration/<feature>. Nothing pushed, no PR, nothing merged.

Next: /before-pr    (gate), then /review, then /pr opens the PR — a human merges.
Slice 03 needs a re-cut — its brief assumed ownership it does not have.
```

## Phase 5 — hand off

`/fleet` stops here. Passing slices are assembled onto the integration branch; nothing is
published and nothing is merged.

The next rung is `/before-pr` (stage 6), then `/review` (7), optionally `/pentest` (8), and
only then `/pr` (9) opens the pull requests. A human merges. `/deploy` (10) detects that
merge and picks up.

An earlier design gave this skill an `--accept` subcommand that merged accepted PRs and
started the next wave. It is gone. Merging was moved out of the pipeline entirely, because
a flag that merges is exactly the affordance the never-merge rule exists to remove.

```bash
python3 "$ENG_BRAIN/bin/state.py" pass "$ARCH_DIR" --stage fleet --artifact FLEET.md
```

## Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Merge conflict between slices | ownership collision `/slice` missed | Re-run `owns.py`; re-cut. Never hand-resolve into another slice's files. |
| Agent reports tests pass, no output | it did not run them | Gate requires pasted runner output. Fail it. |
| Integration built against the wrong base | read the current branch instead of the manifest | `TARGET` comes from `slices.json.source_branch`, always |
| Wave 2 built against stale interfaces | wave 1 not assembled onto integration before wave 2 started | Waves are barriers; wave 2 starts only after wave 1 is assembled and green |
| Slice thrashes without going green | wrong brief or wrong cut, not a fixable slice | The fix loop caps at 3 attempts; then re-slice or re-brief — do not lift the cap |
| Worktree left behind | a wave interrupted mid-run | `git worktree list` then `git worktree remove <path>` |
