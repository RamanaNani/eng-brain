---
name: rollback
version: 2.0.0
description: "Incident runbook. Not a ladder stage — invoke it when a deploy is causing harm. Stops the bleeding first, diagnoses second, and records the incident so the next /arch inherits what broke. Deliberately prescriptive, because judgment degrades under pressure."
triggers:
  - "rollback"
  - "roll it back"
  - "revert the deploy"
  - "production is broken"
  - "incident"
  - "something is on fire"
allowed-tools:
  - Bash
  - Read
  - Write
  - Grep
  - Glob
---

# /rollback — stop the bleeding

**Not a ladder rung.** `/sdlc` never dispatches to this. You invoke it when a deploy is
causing harm, and it is written to be followed literally rather than adapted — the whole
premise is that the moment you need it is the moment you are worst equipped to improvise.

Read `$ENG_BRAIN/CONVENTIONS.md` §7 preamble only. Skip the rest of the brain
protocol until Phase 4; recall is not the priority while something is broken.

## Order of operations

**Stop the harm first. Understand it second.** This ordering is the point of the runbook.
The instinct under pressure is to diagnose before acting, because acting feels irreversible
— but every minute spent understanding is a minute the damage continues, and the rollback
path was already worked out and dry-run during `/deploy`.

Diagnosis is not urgent. Restoration is.

## Phase 1 — Assess, in 60 seconds

Three questions, not more:

| Question | Why |
|---|---|
| What is the observable harm? | errors, data loss, downtime, wrong results — be specific |
| Is it getting worse? | a growing blast radius changes the calculus |
| Is data being corrupted? | **if yes, restoring service is secondary to stopping the writes** |

Data corruption is the one case where you do not simply revert and move on. Reverting the
code stops new corruption; it does not undo what already landed. Say so out loud and get a
human before touching anything.

## Phase 2 — Read the plan you already wrote

```bash
cat "$ARCH_DIR/DEPLOY.md"          # the Rollback path section
```

`/deploy` recorded the mechanism and dry-ran it. Use it. This is why that stage refuses to
ship without one.

Pick by cost, fastest first:

| Mechanism | When | Speed |
|---|---|---|
| **Feature flag off** | change is flagged | seconds — always prefer this |
| **Redeploy previous version** | release system supports it | minutes |
| **`git revert` + deploy** | revert applies cleanly | minutes |
| **Forward fix** | revert conflicts, or a migration blocks it | slow — last resort |

Forward fix under incident pressure is how a small outage becomes a long one. Choose it only
when reverting genuinely cannot work, and say why in the record.

## Phase 3 — Execute

```bash
# flag (preferred)
<project flag-disable command>

# or revert the merge commit recorded in DEPLOY.md
git revert --no-edit "$MERGE_SHA"
git push origin "$SOURCE_BRANCH"
<project deploy command> 2>&1 | tee "$ARCH_DIR/runs/rollback.log"
```

Then **verify the harm actually stopped** — the same discipline as everywhere else. A
rollback that exits 0 while errors continue has not worked:

```bash
curl -fsS "$HEALTH_URL" | head -20
```

If the harm continues, the diagnosis was wrong. Go back to Phase 1 rather than repeating
Phase 3.

## Phase 4 — Record the incident

Only now, with the bleeding stopped.

```markdown
# Incident — <feature-slug>
- **Date:** <YYYY-MM-DD>   **Detected:** <time>   **Mitigated:** <time>
- **Deployed SHA:** <sha>   **Mechanism used:** flag | revert | redeploy | forward fix

## Harm
<what users actually experienced, not what the logs said>

## Why the gates missed it
<the honest answer — this is the most valuable line in the document>

## Timeline
| Time | Event |
|---|---|

## Follow-ups
<numbered, each with an owner>
```

**"Why the gates missed it" is the point of writing this at all.** Every incident that
reaches production passed `/before-pr`, `/review`, and possibly `/pentest`. Something got
through. Naming it is how those stages get better — a vague answer here means the same
class of bug ships again.

Then capture it, and link it to the feature so the next `/arch` on this area inherits it:

```bash
gbrain capture --file "$ARCH_DIR/INCIDENT.md" \
  --slug analysis/incident-<slug>-<date> --type analysis --source "$SOURCE_ID" --quiet
gbrain link projects/"$FEATURE_SLUG" analysis/incident-<slug>-<date> --link-type informed_by
gbrain timeline-add projects/"$FEATURE_SLUG" "$(date +%F)" "Incident: <one line>; rolled back via <mechanism>"
gbrain tag analysis/incident-<slug>-<date> eng-brain && gbrain tag analysis/incident-<slug>-<date> incident
```

`analysis` is extractable, so `dream` mines incidents into facts and, later, into takes.
That is the mechanism by which this system stops repeating a mistake — an incident recorded
as a `project` page would be inert.

## Phase 5 — Reset the ladder

The feature is no longer deployed, and the state should say so rather than claiming success:

```bash
python3 "$ENG_BRAIN/bin/state.py" fail "$ARCH_DIR" --stage deploy \
  --why "rolled back <date>: <one-line reason>"
```

The fix re-enters at `/fleet` for the affected slice — not at `/pr`. Whatever broke got
through the gates once; it needs to pass them again, not route around them.

## Never

- Never diagnose before stopping the harm, unless data is being corrupted.
- Never improvise a rollback when `DEPLOY.md` records a dry-run one.
- Never forward-fix under pressure because reverting feels like defeat.
- Never mark the incident closed without answering why the gates missed it.
- Never re-enter the ladder at `/pr` after a rollback.
