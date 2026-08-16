# eng-brain — architecture

## The problem

The pipeline stages (`/story`, `/arch`, `/slice`, `/fleet`, `/pr`) were each well built and
independently useful. Three things were missing, and all three were structural rather than
matters of polish:

1. **Nothing sequenced them.** "Where is this feature stuck?" required reading the arch
   directory and inferring. There was no answer to ask for.
2. **Gates were advisory.** Invoking `/slice` directly skipped `/arch` silently — a stage
   had no way to know it was being run out of order, so the ladder was a convention rather
   than a constraint.
3. **The layer had no home.** It existed only in `~/.claude/skills/`, with no package, no
   repo, and no lockfile. When that directory was lost, the only surviving copy was inside
   gbrain transcript pages.

## The design

Three components, deliberately separated by what they know.

### 1. The ladder, as data — `skills/_eng-brain/bin/state.py`

`STATE.json` in the target repo's `docs/arch/<feature>/`. Not in this repo: state belongs
next to the artifacts it describes, so a feature's position survives a lost session and
travels with a branch.

`state.py` owns stage order and refuses to be talked out of it:

- `pass` on a stage with ANY earlier stage — mandatory or optional — not yet pass/skipped → **exit 2**
- `skip` on a mandatory stage → **exit 1**

Optional stages (`contract`, `pentest`, `deploy`, `canary`) must still be *recorded* as skipped with a reason.
"Not applicable" is a decision, and decisions are the thing this system exists to keep.

Putting the ladder in code rather than in the spine's prose is the central choice here.
Prose instructions are advisory to a model; a non-zero exit code is not.

### 2. The spine — `skills/sdlc/SKILL.md`

Reads state, dispatches to exactly one stage skill, records the gate, writes back to the
brain. It does not reimplement stages and holds no stage logic — adding a stage means
adding a rung to `LADDER` in `state.py` and a skill directory, and nothing else changes.

It defaults to one stage per invocation. Running the whole ladder unattended produces
artifacts nobody reviewed, and the review points are most of the value.

### 3. The gate — `skills/_eng-brain/bin/gate.py`

Two mechanical checks: failure-mode coverage, and honest test output.

The second is the load-bearing one. `gate.py testout` parses pytest, jest, cargo, mocha,
`node --test`, `go test`, TAP, and `unittest`, and treats `3 failed, 5 passed` as red. Its
regexes carry comments recording specific false results that had to be debugged — the
`node --test` prefix is `\S{0,2}` rather than `\W*` because Python's `\w` matches U+2139
INFORMATION SOURCE, so `[^\w]` skipped past nothing on the spec line.

`gate.py selfcheck` is inherited from the original and asserts on exact diagnostic wording,
not just exit codes. That distinction matters: several checks share an exit code, so only
the message distinguishes "the file was empty" from "the file was unparseable", and the
operator needs to know which.

## Layering

Three layers with different failure modes and different restore paths. Conflating them is
what made the 2026-08-15 recovery slow.

| Layer | Home | Restore | Fragility |
|---|---|---|---|
| gbrain bundle (53) | the npm package | reinstall + copy | low — hash-verified |
| **this repo (17)** | **git** | `./install.sh` | **low, now** |
| marketplace plugins (26) | marketplace repos | `claude plugin install` | low — recorded in `settings.json` |

Layer 2 was the fragile one and is what this repo fixes.

## Brain contract

Unchanged from `skills/_eng-brain/CONVENTIONS.md`, which remains authoritative. The spine adds no brain
rules; it only ensures each stage's write-back actually happens. The rules that bite most:

- `--source` is mandatory; omitting it silently files into `default`, which is the wrong
  repo and will not sync.
- Every written page needs an edge **in the same run**. Orphans are invisible to `think`,
  and the brain already carried 540 orphans out of 542.
- `GBRAIN_PREPARE=true` must be exported — the pooler rejects session-level prepared
  statements and the failure mode is an *empty result set rather than an error*.

## The doers: agents

The gates decide; the skills conduct; **agents do**. eng-brain ships six typed subagents
(`agents/`) whose tools are their guardrails — a `slice-reviewer` has no `Write`, so it
cannot fix what it reviews; an `architect` has no `Write`, so a design candidate cannot
smuggle in an implementation. This is the same "don't trust the prompt to hold a line the
runtime can hold" argument as the gates, applied to agents. See
[AGENTS.md](AGENTS.md) and [ADR-103](adr/ADR-103-agent-roster-tools-as-guardrails.md).

## Requirements traceability

A third mechanical gate joined the two above: `coverage.py` proves every acceptance
criterion in `STORY.md` (each with a stable `AC-<n>` id) reaches a slice's `covers`. It is
what makes "loop until the requirements are satisfied" a checkable exit rather than an
assertion — a criterion is done only when a slice claims it *and* that slice is green. See
[ADR-102](adr/ADR-102-requirements-traceability.md).

## What this does not do

- **It does not merge.** `/pr` opens PRs and stops; `/fleet` assembles onto integration and
  stops.
- **It does not decide whether a design is good.** `/arch` weighs candidates; a human
  accepts. The gates check that the work was *done and evidenced*, not that it was wise.
- **It does not run stages unattended by default.** Batching is available on request and
  still stops at the first failing gate.

## Open

- **All six gate tools are self-checked**, and CI (`.github/workflows/ci.yml`) runs every
  selfcheck on each push. The recovery-era gap of "recovered but unverified" tools is closed.
- `concepts.py` resolves a slice's owned files against the primary repo only; a slice whose
  files live in a *secondary* repo of a multi-repo feature is not yet fully checked.
- `gate.py modes` matches failure modes by substring, so use full-phrase mode names (the
  `/arch` sweep produces these).
- `canary`, `before-pr`, and `impeccable` have been exercised in pieces but not yet driven
  against a large multi-repo feature end to end.
