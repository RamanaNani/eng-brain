# The pipeline, end to end

This is the full lifecycle eng-brain runs, from an idea to a monitored release, and the loop
model that keeps a feature moving until it is genuinely done. For install and setup, see
[SETUP.md](SETUP.md); for the agents, [AGENTS.md](AGENTS.md); for why gates are code, see
[ADR-101](adr/ADR-101-ladder-as-data.md).

Read this if you want to understand *how a feature travels*, not just how to install the
thing.

---

## The eleven rungs

One feature enters at `/sdlc` and climbs a ladder. Each rung produces an artifact and is
gated: `/sdlc` will not advance past a gate that has not been shown to pass, and a resumed
session reads its position off `docs/arch/<feature>/STATE.json` in your repo.

```
 1  story       STORY.md          the requirement, as testable acceptance criteria (AC-1, AC-2, …)
 2  arch        ARCHITECTURE.md   the design: candidates weighed, ADRs written, failure modes enumerated
 3  contract?   CONTRACTS.md      the seam between repos, with a conformance test on each side
 4  slice       slices.json       disjoint file ownership, an acyclic DAG, every AC mapped to a slice
 5  fleet       FLEET.md          parallel worktrees build + cross-review each slice, gated on real tests
 6  before-pr   GATE.md           mechanical gate: tests green, failure modes covered, requirements covered
 7  review      REVIEW.md         human-facing: scope drift both ways, the /impeccable rubric
 8  pentest?    PENTEST.md        source-aware security assessment, authorized targets only
 9  pr          PR.md             the pull request opens — a human merges
10  deploy?     DEPLOY.md         release, with a dry-run rollback path recorded first
11  canary?     CANARY.md         measured regression check against a pre-change baseline
```

`?` marks stages that are *optional but recorded* — they may be skipped, with a reason on the
record, but never silently ignored. `state.py` refuses `/pr` while `/pentest` is merely
pending.

---

## Mapping the vision onto the rungs

The lifecycle people describe informally — *understand the ask, design it, break it into
services, build bottom-up, test the edges, review, security-test, deploy, monitor* — maps onto
the ladder like this:

| What you want | Where it lives | How it is made real |
|---|---|---|
| Capture data & understand requirements | **story** | acceptance criteria get ids; gbrain is queried for prior art before the interview |
| Create the architecture | **arch** | parallel `architect` agents propose independent candidates; you synthesise |
| Slice into services, build bottom-up | **contract + slice + fleet** | multi-repo features write contracts first; each slice is a unit; waves build dependencies before dependents |
| Implement with edge & test cases | **story + slice + fleet** | every failure mode from `/arch` becomes a slice edge case; `coverage.py` proves every AC reaches a slice |
| Agents reviewing each other | **fleet (per slice) + review (whole)** | each green slice gets a `slice-reviewer` and `test-auditor`; the assembled diff gets a human-facing read |
| Penetration / security testing | **pentest** | `security-tester` runs SAST + DAST; touching auth/network/input makes it mandatory for that feature |
| Deployment & DevOps guidance | **deploy** | `devops-advisor` reads the repo's real machinery and writes a runbook + rollback + environment matrix |
| Monitoring the system | **canary** | a pre-change baseline vs the post-change delta turns "it works" into a measured claim |

Nothing here is a new persona chatting with another persona. Each rung is an artifact on disk
and a script that decides whether it passed. That is the whole reliability argument.

---

## The loop model

A straight climb is the happy path. Real work loops — and every loop here has a **script**
deciding when it exits, never an agent's sense that it is finished. That is what keeps loops
from thrashing.

| Loop | What iterates | Exit decided by | Bound |
|---|---|---|---|
| **L0 — fix** | a red or blocked slice → feed the verbatim gate output back → fix → re-gate | `gate.py` | 3 attempts, then the slice is marked blocked and re-cut or re-briefed |
| **L1 — review** | reviewer/auditor findings → fix → re-gate + re-check findings | findings ledger empty (or waived with a reason) | bounded rounds, then a human decides |
| **L2 — requirements** | is every acceptance criterion built *and* green? | `coverage.py` + `gate.py` together | loop until every AC maps to a green slice |
| **L3 — release** | a canary breach → rollback → `/change` → new story | the canary's regression verdict | per release |
| **L4 — knowledge** | decisions & incidents written back to gbrain, read by the next feature's `/story` and `/arch` | — | across features, forever |

**L2 is the one that makes "loop until the requirements are satisfied" real.** Before it, "all
requirements met" was the agent's assertion. Now the exit condition is a fact: every `AC-<n>`
in `STORY.md` maps to a slice (`coverage.py`), and that slice's tests ran and passed
(`gate.py`). A green coverage map over red slices is not done; red coverage over green slices
is not done. Only both, together, is done — see [ADR-102](adr/ADR-102-requirements-traceability.md).

**L4 is what makes the second feature cheaper than the first.** Every stage reads the brain
before deciding and writes back after, so architecture becomes a queryable graph of decisions
and the ADRs that settled them. The next `/arch` inherits what the last one learned.

---

## The two invariants that never bend

Everything above is negotiable per feature. These two are mechanised, because they are the
rules most likely to be rationalised away under pressure:

1. **Never merge.** `/pr` opens a pull request and stops. `/fleet` assembles onto an
   integration branch and stops. There is no `--auto-merge`, no `--accept`, no "the gate
   passed so I merged it". A human merges; only then does `/deploy` detect that merge and pick
   up. The flag that could merge was removed, because a flag that can merge is exactly the
   affordance the rule exists to remove.

2. **Never claim a green suite without runner output.** `gate.py testout` parses the actual
   output of pytest, jest, cargo, mocha, `node --test`, `go test`, TAP, and `unittest`. A
   missing output file is `NOT RUN`, and `NOT RUN` is a failure. "Should pass" is not a
   result.

---

## What one feature looks like

```
/sdlc build offline draft sync
  → story      3 acceptance criteria (AC-1..AC-3), 1 negative case, gbrain queried
  → arch       3 architect candidates → 1 recommended, 2 ADRs, 6 failure modes enumerated
  → contract   skipped (single repo — recorded, not ignored)
  → slice      4 slices, disjoint ownership, coverage.py: AC-1..AC-3 all mapped
  → fleet      wave 1: 2 slices build + review + test-audit in parallel worktrees
               wave 2: 1 slice (needs wave 1's interfaces)
               1 slice went red twice, fixed on attempt 3 → assembled onto integration/offline-draft-sync
  → before-pr  gate.py green on every slice, coverage.py green, failure modes covered
  → review     no scope drift, /impeccable clean, every AC located in the code
  → pentest    touches sync auth → mandatory → security-tester: 0 unresolved high/critical
  → pr         PR opened against the source branch. You merge.
  → deploy     devops-advisor runbook, rollback dry-run applied cleanly → shipped
  → canary     p95 +2.7% (within noise), error rate flat → NON-REGRESSIVE
```

Every arrow is a gate. None of them trust the previous one's word for it.
