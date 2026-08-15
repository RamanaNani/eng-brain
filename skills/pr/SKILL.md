---
name: pr
version: 1.0.0
description: "Raise the pull request after a review has passed. Composes the body from the slice manifest, refuses if the review did not happen, and records the PR number back to the manifest and gbrain. The first step in the pipeline that leaves your machine. Stage 9 of 11 in the ladder (story -> arch -> contract? -> slice -> fleet -> before-pr -> review -> pentest? -> pr -> deploy? -> canary?)."
triggers:
  - pr
  - raise pr
  - open the pr
  - raise the pull request
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Grep
  - Glob
---

# /pr — publish, once someone has actually looked

`/fleet` assembles and stops. `/review` reads the assembled diff and can fail. `/pr` is the
separate act of publishing, and it is its own command for one reason: **a review has to be
able to end in "no".** If reviewing and publishing were one command, a review that found
problems would have to abort halfway through something named after shipping.

This is also the first step in the pipeline that leaves the machine. Normal mode, prompts on.

**Read `$ENG_BRAIN/CONVENTIONS.md` first.**

## The one inviolable rule

`/pr` opens a pull request. It does not merge it, does not enable auto-merge, and does not
push to the target branch. Landing is a human act.

## When to invoke

After `/review` has passed on `integration/<feature>`. Also usable without a fleet manifest,
on any ordinary feature branch — it degrades to composing the body from the diff while
enforcing the same preconditions.

Do not use it to "get a PR up for discussion". An unreviewed PR trains whoever opens it to
assume someone else already looked.

## Phase 0 — Preflight, and these are refusals

Preamble from CONVENTIONS.md §7, then every check below must hold. Print each check and its
result; do not continue past a failure.

```bash
REPO_ROOT=$(git rev-parse --show-toplevel)
BRANCH=$(git rev-parse --abbrev-ref HEAD)
MANIFEST=$(ls "$REPO_ROOT"/docs/arch/*/slices.json 2>/dev/null | head -1)

# The target comes from the manifest, never from whatever branch you happen to be on.
TARGET=$(python3 -c "import json;print(json.load(open('$MANIFEST'))['source_branch'])" 2>/dev/null || echo "")
[ -n "$TARGET" ] || { echo "BLOCKED: no source_branch found. Pass the target explicitly."; exit 1; }

git diff --quiet && git diff --cached --quiet \
  || { echo "BLOCKED: uncommitted changes — commit or stash before publishing"; exit 1; }

[ "$BRANCH" != "$TARGET" ] \
  || { echo "BLOCKED: you are ON the target branch; there is nothing to open a PR from"; exit 1; }

gh auth status >/dev/null 2>&1 || { echo "BLOCKED: gh not authenticated"; exit 1; }

git push -u origin "$BRANCH" || { echo "BLOCKED: push failed"; exit 1; }
```

**The review check.** `/pr` must not be the first time anyone looks at this diff. Confirm a
review happened, by any of: a `review:` entry in the manifest, review notes committed under
`docs/arch/<slug>/`, or the user saying so in this session. If none exist, stop:

```
BLOCKED: no review recorded for integration/<feature>.
  Run /review first. If you reviewed it outside this session, say so and I will proceed.
```

**The CI check.** Report the state; never silently ignore it.

```bash
gh run list --branch "$BRANCH" --limit 1 --json conclusion,status,workflowName
```

Red CI is not an automatic refusal — sometimes a PR is how you get eyes on a failure — but
it goes in the first line of the body, rather than being discovered by the reviewer.

## Phase 1 — Compose the body from the manifest, not from memory

Read `slices.json` and build from recorded fact. Never summarize the diff from the agent's
own report of what it did.

```markdown
## What this assembles
<feature> — N slices, assembled on `integration/<feature>`.

| Slice | What it does | Tests | Attempts |
|---|---|---|---|
| N01  | spec-author bounds     | 12 pass | 1 |
| N02a | mention kind widening  |  9 pass | 2 ← retried once |
| N02b | mention rail           |  7 pass | 1 (built by hand) |

## Seam review
Reviewed at <sha>. Findings: <what the review actually said, or "none">.

## Interfaces touched
<the Interfaces rows from ARCHITECTURE.md this wave changed>

## Cross-repo
Contract: `docs/arch/<slug>/CONTRACTS.md`. **Deploy order: <which repo first>.**
Conformance tests: <both sides, and whether each was observed to fail>

## Not done here
<the out-of-scope list from STORY.md or CHANGE.md, plus any slice that failed>

## CI
<state, with the run URL>
```

Two rules for the body:

- **A retried slice says so.** The attempt count is signal, not shame — it tells a reviewer
  where the code was hard, which is where they should look first.
- **A slice that failed twice and was cut is named under "Not done here."** A PR that
  silently omits the piece that didn't work is the most expensive kind of incomplete.

```bash
gh pr create --base "$TARGET" --head "$BRANCH" \
  --title "<feature>: <one line>" --body "$BODY"
```

## Phase 2 — Record it, then stop

```bash
PR_URL=$(gh pr view --json url -q .url)
```

Write the PR number into `slices.json` at the top level (`"pr": 251`), commit the manifest,
and write to the brain:

```
mcp__gbrain__put_page  slug: "pr-<feature-slug>"  type: "note"
```

Print the URL and **stop**. Do not merge. Do not watch CI and merge on green.

## Phase 3 — Cleanup, only after the human lands it

```bash
git worktree list                       # every wt/<slice> from /fleet
git worktree remove <path>              # for each
git branch -d slice/<feature>-<id>      # local slice branches, now merged
```

Leave `integration/<feature>` until the PR is merged — it is what the PR points at.

## Failure modes

| Smell | What it means | Do this |
|---|---|---|
| PR opened with no review | `/pr` was used to start a conversation | Close it, review, reopen. An unreviewed PR reads as reviewed. |
| Body written from the agent's summary | Nobody checked it against the diff | Compose from `slices.json` and `git diff --stat` only |
| Retry count omitted | The reviewer can't tell where the code was hard | Put attempts in the table, always |
| A failed slice not mentioned | The PR looks complete and isn't | Name it under "Not done here" |
| Target taken from `HEAD` | You will open a PR against the wrong base | Always read `source_branch` from the manifest |
| Auto-merge enabled | The human step was skipped | Turn it off. `/pr` opens; a person lands. |
| Cross-repo PR with no deploy order | Someone ships them backwards | State which side goes first, in the body |
