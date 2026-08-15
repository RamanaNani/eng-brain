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

- `pass` on a stage with an earlier mandatory stage unmet → **exit 2**
- `skip` on a mandatory stage → **exit 1**

Optional stages (`contract`, `canary`) must still be *recorded* as skipped with a reason.
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
| **this repo (13)** | **git** | `./install.sh` | **low, now** |
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

## What this does not do

- **It does not merge.** `/pr` opens PRs and stops.
- **It does not decide whether a design is good.** `/arch` weighs candidates; a human
  accepts. The gates check that the work was *done and evidenced*, not that it was wise.
- **It does not run stages unattended by default.** Batching is available on request and
  still stops at the first failing gate.

## Open

- `owns.py`, `concepts.py`, and `tractable.py` were recovered and parse, but are not yet
  exercised by a selfcheck the way `gate.py` is. Until they are, treat their output as
  informative rather than authoritative.
- `canary`, `before-pr`, and `impeccable` are newly written to fill recovered gaps. They
  have not yet been run against a real feature.
- No CI. `./install.sh --check` and `gate.py selfcheck` should run on every commit.
