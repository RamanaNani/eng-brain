---
name: deploy
version: 2.0.0
description: "Stage 10, optional. Releases a merged change, with a rollback path recorded and verified BEFORE anything ships. Detects that a human merged the PR — it never merges anything itself. Refuses to release without a rollback path that has actually been checked."
triggers:
  - "deploy"
  - "ship it"
  - "release this"
  - "roll out"
  - "push to production"
allowed-tools:
  - Bash
  - Read
  - Write
  - Grep
  - Glob
---

# /deploy — release, with a way back

Stage 10 of the ladder (see `skills/sdlc/SKILL.md`), optional but **recorded**.
Position: `pr → *(a human merges)* → **deploy** → canary`.

Read `skills/_eng-brain/CONVENTIONS.md` first.

## This stage does not merge

`/pr` opens pull requests and stops. A human accepts. That rule is absolute and this stage
does not soften it — `/deploy` **detects** that a merge happened and picks up afterwards.

If the PR is not merged, this stage stops and says so. It does not offer to merge, and it
does not wait in a loop. Go get a human.

## Phase 0 — Preamble

`CONVENTIONS.md` §7, then confirm the merge is real:

```bash
gh pr view "$PR_NUMBER" --json state,mergedAt,mergeCommit \
  --jq '{state,mergedAt,sha:.mergeCommit.oid}'
```

`state` must be `MERGED`. A `CLOSED` PR is not a merged one — that distinction has shipped
nothing while looking like it shipped something.

```bash
MERGE_SHA=$(gh pr view "$PR_NUMBER" --json mergeCommit --jq .mergeCommit.oid)
```

Everything below references `$MERGE_SHA`, not `HEAD`. Local `HEAD` may have moved on.

## Phase 1 — The rollback path, before anything ships

**Write this down before you deploy, not after.** After is too late: the moment you need it
is the moment you are least able to think it through.

Determine and record:

| Question | Why it decides the plan |
|---|---|
| Is `git revert $MERGE_SHA` sufficient? | If yes, the plan is short. If no, say why. |
| Did it run a migration? | Migrations rarely revert cleanly — you need a down path or a forward fix. |
| Did it write state? | Published pages, external calls, deleted rows. A revert leaves these behind. |
| Is it behind a flag? | A flag is a faster and safer rollback than a redeploy. |
| What is the revert blast radius? | Reverting may break things merged *after* it. |

Then **verify the path is real**, not asserted:

```bash
git revert --no-commit --no-edit "$MERGE_SHA" && echo "revert applies cleanly" \
  || echo "REVERT CONFLICTS — the rollback plan needs more than git revert"
git revert --abort 2>/dev/null || git reset --hard
```

A rollback plan that has never been executed even in dry-run is a hope, not a plan. If the
revert conflicts, that is a finding — record the real procedure before shipping.

**Irreversible changes raise the bar rather than meeting it.** If there is no rollback path
at all, say so explicitly and get a human decision. Do not proceed on the assumption that it
will be fine.

## Phase 2 — Deploy

Use the project's own release mechanism — this skill does not invent one. Look for it, in
this order: `Makefile` release targets, `package.json` scripts, `.github/workflows/`, a
`deploy/` directory, or the project's runbook.

If you cannot find one, stop and ask. Guessing at a deploy command is the single most
expensive mistake available in this pipeline.

Capture the output. As everywhere else in this system, "it deployed" is a claim that needs
evidence:

```bash
<project deploy command> 2>&1 | tee "$ARCH_DIR/runs/deploy.log"
```

## Phase 3 — Verify it actually landed

Deploying and being live are different things. Check the deployed artifact reports the
version you expect — not that the command exited 0:

```bash
curl -fsS "$HEALTH_URL" | head -20
```

A green exit code with a stale version means the deploy silently no-opped. That failure is
common and quiet, which is exactly the combination this pipeline treats as dangerous.

## Phase 4 — Write DEPLOY.md

```markdown
# Deploy — <feature-slug>
- **Date:** <YYYY-MM-DD>
- **Merge SHA:** <sha>       **Deployed version:** <version>
- **Environment:** <prod | staging>
- **Verdict:** DEPLOYED | FAILED | ROLLED BACK

## Rollback path
- **Mechanism:** git revert | feature flag | forward fix | <other>
- **Dry-run result:** applies cleanly | conflicts (see below)
- **Migrations:** none | <name>, down path: <how>
- **State written:** none | <what, and how to undo it>
- **Command:** `<the exact command to run>`

## Deploy output
<verbatim tail of the deploy log>

## Verification
<what you checked, and what it returned>
```

## Phase 5 — Record

```bash
python3 "$ENG_BRAIN/bin/state.py" pass "$ARCH_DIR" --stage deploy --artifact DEPLOY.md
# or
python3 "$ENG_BRAIN/bin/state.py" fail "$ARCH_DIR" --stage deploy --why "<what happened>"
# or, when there is genuinely nothing to deploy
python3 "$ENG_BRAIN/bin/state.py" skip "$ARCH_DIR" --stage deploy --why "library change, no deployment"
```

Then capture to the brain per `CONVENTIONS.md` §5 with an edge, and add a timeline entry —
deploy dates are what make trajectory and drift analysis work later:

```bash
gbrain timeline-add projects/"$FEATURE_SLUG" "$(date +%F)" "Deployed <version> to <env>"
```

## Never

- Never merge. Detect the merge; a human performs it.
- Never deploy before the rollback path is recorded **and** dry-run.
- Never guess a deploy command. Find the project's, or ask.
- Never report success on exit code alone — verify the deployed version.
- Never skip this stage silently. `--why` goes on the record.

## When it goes wrong

`/rollback`. Do not improvise under pressure — that skill exists precisely because
judgment degrades during an incident.
