---
name: fleet
version: 1.0.0
description: "Run sliced work across parallel git worktrees. One agent per slice, wave by wave, each gated on real tests and written docs, retried once on failure and never twice. Passing slices assemble onto an integration branch and it STOPS — no PR. /review reads the seam, then /pr publishes. Stage 4 of story -> arch -> slice -> fleet -> review -> pr."
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

Stage 3 of three. `/arch` decided. `/slice` divided. `/fleet` builds — in parallel,
in isolated worktrees, and **it never merges**.

**Read `~/.claude/skills/_eng-brain/CONVENTIONS.md` first.**

## The one inviolable rule

`/fleet` never touches `$TARGET` and never opens a pull request.

Passing slices merge onto `integration/<feature>`, which is a scratch branch — that merge
is bookkeeping, not a release, and it exists so the seam can be read in one place. Nothing
reaches the branch you actually care about without a human reading the assembled diff first,
and the PR is raised by `/review` as the record that the read happened.

If you are ever unsure whether you are allowed to touch `$TARGET` or run `gh pr create`:
you are not. That is `/review`'s job.

## When to invoke

After `/slice`, when the user says "fleet", "run the worktrees", "build the slices",
"execute the plan". There is no accept subcommand — `/review` is the next step.

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
python3 /tmp/check_owns.py "$MANIFEST" "$REPO_ROOT" || { echo "BLOCKED: slice ownership collision"; exit 1; }
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
    `6. Report every cross-slice signature you implemented, verbatim, one per line, in ` +
    `implemented_signatures. Siblings compile against these and cannot see your code.\n\n` +
    `Return JSON: {slice, files_written, tests_run, tests_passed, test_output, ` +
    `implemented_signatures, docs_updated, blocked, blocker}`,
    // agentType comes from /slice Phase 3.5 — the specialist matched to what this slice touches.
    { label: `build:${s.id}`, phase: 'Build', isolation: 'worktree',
      agentType: s.agents?.build || 'software-developer', schema: BUILD_SCHEMA }
  ),
  (r, s) => (r?.blocked || !r?.tests_passed) ? r : parallel([
    () => agent(`Read the brief at ${args.repoRoot}/docs/arch/${args.feature}/${s.brief} FIRST.\n` +
                `Then adversarially review the diff on branch ${s.branch} for slice ${s.id}. ` +
                `Find real defects: unhandled errors, missing validation at trust boundaries, ` +
                `swallowed exceptions, files written outside ${s.owns.join(', ')}. ` +
                `Report only defects you can point at a line for.`,
                { label: `review:${s.id}`, phase: 'Verify',
                  agentType: s.agents?.review || 'ecc:code-reviewer', schema: REVIEW_SCHEMA }),
    () => agent(`Read the brief at ${args.repoRoot}/docs/arch/${args.feature}/${s.brief} FIRST ` +
                `and extract its "Edge cases to test" list. You are checking against that list, ` +
                `not against your own idea of what should be tested.\n` +
                `Then verify slice ${s.id}'s tests actually exercise each one. Re-run the test ` +
                `command yourself in the worktree; do not trust the build agent's report. ` +
                `A test that asserts nothing, or only the happy path, is a FAIL. ` +
                `Return {adequate, gaps[], rerun_output}.`,
                { label: `tests:${s.id}`, phase: 'Verify',
                  agentType: s.agents?.test || 'ecc:tdd-guide', schema: TESTGATE_SCHEMA }),
  ]).then(([review, tests]) => ({ ...r, review, tests }))
)
return built.filter(Boolean)
```

Use `pipeline`, not `parallel` between stages — a slice that finishes building should
start its review immediately rather than waiting for its slowest sibling.

## Phase 2 — The gate

A slice may push **only** if all five hold. Every row has a command. An agent's assurance
that it did the thing is not evidence that it did the thing.

| Gate | Mechanical check |
|---|---|
| Tests really ran | `gate.py testout` on the pasted output, and the verify agent's independent re-run agrees |
| Edge cases | verify agent maps each brief edge case to a named test, and that name appears in the diff |
| Interfaces | `gate.py iface` — reported signatures match the brief's contract |
| Docs | `git diff --name-only` includes a doc file, and the diff is not a one-word touch |
| Ownership | `git diff --name-only $TARGET...HEAD` ⊆ the slice's `owns` globs |

```bash
GATE=~/.claude/skills/_eng-brain/bin/gate.py

# Tests: the runner actually printed counts. Prose claiming success fails here.
printf '%s' "$TEST_OUTPUT" | python3 "$GATE" testout - || FAILED="$FAILED tests"

# Interfaces: what the agent says it built vs what the brief said to build.
printf '%s\n' "$IMPLEMENTED_SIGNATURES" > /tmp/sig-$SLICE_ID.txt
python3 "$GATE" iface "$ARCH_DIR/$SLICE_BRIEF" /tmp/sig-$SLICE_ID.txt || FAILED="$FAILED interfaces"

# Ownership: catches the agent that helpfully wandered.
git -C "$WT" diff --name-only "$TARGET"...HEAD
```

The interface check is the one that would have caught Tier 0. Slices pass their own tests