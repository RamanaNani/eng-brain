# eng-brain

**A software development lifecycle for AI coding agents, with gates that actually hold.**

One feature goes in at `/sdlc` and comes out as reviewed pull requests — through story,
architecture, contracts, slicing, parallel implementation, and gating. Every architectural
decision is written back to a knowledge brain, so the *next* feature inherits what the
last one learned instead of rediscovering it.

Built for [Claude Code](https://claude.com/claude-code). 13 skills, ~2500 lines.

```
/story → /arch → /contract? → /slice → /fleet → /before-pr → /pr → /canary?
```

---

## The idea

Agent pipelines usually fail in one of two ways. Either every stage is a fresh start —
the agent re-derives the architecture it settled last week — or the stages exist but
nothing enforces them, so "run the tests" quietly becomes "say the tests passed."

eng-brain addresses both, and the second one is the interesting half:

**Gates are code, not prose.** A stage cannot be marked complete out of order, because
`state.py` returns exit 2 and refuses. Tests cannot be declared green without runner
output, because `gate.py` parses the output itself and treats `3 failed, 5 passed` as red.

That distinction is the whole design. Prose instructions to a model are advisory — they
compete with everything else in context and they lose to time pressure. A non-zero exit
code does not lose that argument. See
[ADR-101](docs/adr/ADR-101-ladder-as-data.md) for the reasoning.

**Decisions persist.** Each stage reads the brain before deciding and writes back after.
Architecture becomes a queryable graph of decisions and the ADRs that settled them, rather
than a directory of markdown nobody opens again.

---

## Install

**As a plugin** — recommended, and what you want if you just intend to use it:

```
/plugin marketplace add RamanaNani/eng-brain
/plugin install eng-brain@eng-brain
```

Claude Code manages the copy and a bundled hook tells you when a new version ships.

**As a clone** — if you intend to modify the skills:

```bash
git clone https://github.com/RamanaNani/eng-brain.git
cd eng-brain
./skills/_eng-brain/setup.sh    # preflight: tells you exactly what's missing
./install.sh                    # projects skills into ~/.claude/skills/
```

In clone mode the same hook keeps `~/.claude/skills/` in step with the repo automatically —
edit here, and the next session picks it up.

Then, in Claude Code:

```
/sdlc build offline sync for the notes editor
```

Full instructions, including provisioning the brain, are in **[docs/SETUP.md](docs/SETUP.md)**.
Requires `bun`, `python3`, and a Postgres database (Supabase free tier is plenty). It runs
without a brain too — you just lose the memory, not the pipeline.

---

## The ladder

`/sdlc` is the spine. It holds the state, decides which stage runs next, and stops at the
first failing gate. The stage skills work standalone, but invoked directly they cannot
tell they're being run out of order — which is exactly the problem the spine exists to fix.

| Stage | Produces | Gate to advance |
|---|---|---|
| `story` | `STORY.md` | ≥1 acceptance criterion, ≥1 negative case, ≥1 non-goal |
| `arch` | `ARCHITECTURE.md`, `ADR-*.md` | ≥2 candidates weighed, ≥1 ADR, contradictions surfaced |
| `contract` *(optional)* | `contracts/` | required iff ≥2 slices share an interface |
| `slice` | `slices.json` | file ownership disjoint, DAG acyclic, failure modes routed |
| `fleet` | `FLEET.md` | every slice green, **runner output shown** |
| `before-pr` | `GATE.md` | `gate.py` passes on every slice |
| `pr` | `PR.md` | PRs opened — **never merged** |
| `canary` *(optional)* | `CANARY.md` | baseline recorded, delta non-regressive |

Optional stages must still be *recorded* as skipped, with a reason. "Not applicable" is a
decision, and decisions are the thing this system exists to keep.

State lives in the **target** repo at `docs/arch/<feature>/STATE.json`, so a feature's
position travels with its branch and survives a lost session.

```
$ /sdlc where is offline-sync

offline-sync  ·  slice → fleet
  ✓ story  ✓ arch  – contract (single repo)  ✓ slice  · fleet  · before-pr  · pr  · canary
```

---

## The two rules

Everything else is negotiable. These are not, and both are mechanised rather than trusted:

**Never merge.** `/fleet` opens pull requests and stops. A human accepts. There is no
`--auto-merge` and no "the gate passed so I merged it."

**Never claim a green suite without runner output.** `gate.py testout` understands pytest,
jest, cargo, mocha, `node --test`, `go test`, TAP, and `unittest`. A missing output file is
`NOT RUN`, and `NOT RUN` is a failure.

Both rules exist because they're the ones most likely to be rationalised away in the
moment — which is precisely why they can't live in prose.

---

## Layout

```
.claude-plugin/
  marketplace.json  this repo IS a Claude Code marketplace
  plugin.json       the plugin manifest
hooks/
  hooks.json        SessionStart wiring
  sync.sh           keeps installs current (see "Staying current")
skills/             everything here ships with the plugin
  sdlc/             the spine — start here
  story/ arch/ contract/ slice/ fleet/ before-pr/ pr/ canary/
  impeccable/       review rubric (not a stage)
  grill-me/         adversarial design interview
  brain-sync/ change/
  _eng-brain/       shared library, not a skill (no SKILL.md)
    CONVENTIONS.md  the contract — page types, link types, read/write protocol
    GREENFIELD.md   starting fresh
    BROWNFIELD.md   working in an existing codebase
    setup.sh        env + preflight (source it, or run it)
    bin/
      state.py      the ladder and its gates
      gate.py       failure-mode coverage + honest test output
      owns.py       slice file-ownership disjointness
      concepts.py  tractable.py
docs/
  SETUP.md          start here to install
  ARCHITECTURE.md   how it fits together, and what it deliberately doesn't do
  adr/
```

The shared library lives *under* `skills/` rather than beside it because a plugin only
ships its `skills` directory — anything outside it would be missing for plugin users.

`/impeccable` is the review rubric — correctness, honesty of evidence, blast radius,
reversibility. Not a ladder stage: `/before-pr` mechanises what can be mechanised, and
`/impeccable` covers the rest, where a human still has to look.

---

## Staying current

A `SessionStart` hook keeps installs from silently rotting, and behaves differently by
install mode because the two have different risk profiles:

| Mode | Behaviour |
|---|---|
| **clone** | Detects that `~/.claude/skills/` drifted from the repo and **re-installs automatically**, printing one line saying so. The projection is derived data, so rebuilding it is safe and idempotent. |
| **plugin** | **Notifies only**, at most once a day, when a newer version is on `main`. Fetching code from the network is not something a hook should do unasked. |

It is silent when there is nothing to say — a hook that speaks every session gets ignored,
and then it isn't a hook, it's noise.

```bash
ENG_BRAIN_AUTO_SYNC=0        # report drift but don't apply it
ENG_BRAIN_NO_UPDATE_CHECK=1  # disable the version check entirely
```

## Verifying

```bash
./skills/_eng-brain/setup.sh                     # full environment preflight
./install.sh --check                             # installed copy matches this repo
python3 skills/_eng-brain/bin/gate.py selfcheck  # must print OK
```

`gate.py`'s selfcheck is worth explaining, because it's load-bearing. The original
`gate.py` was partially lost; its test suite survived but its implementation did not. The
implementation here was rebuilt to satisfy that suite, which pins exact behaviour *and*
exact diagnostic wording — several checks share an exit code, so only the message
distinguishes "the file was empty" from "the file was unparseable," and the operator needs
to know which. Run it after any edit to that file.

---

## Status

Working and in use, with known rough edges — stated plainly rather than discovered later:

- `owns.py`, `concepts.py`, and `tractable.py` are recovered and parse, but have no
  selfcheck the way `gate.py` does. Treat their output as informative, not authoritative.
- `before-pr`, `canary`, and `impeccable` are newly written and have not yet been run
  against a real feature end to end.
- No CI. `./install.sh --check` and `gate.py selfcheck` should gate every commit.

## Contributing

Edit this repo, then `./install.sh`. Never edit `~/.claude/skills/` directly — it's a
projection, and `./install.sh --check` exists to catch exactly that mistake.

Before opening a PR: `./skills/_eng-brain/setup.sh` green, `gate.py selfcheck` passing. New skills need
a `triggers:` array in frontmatter or gbrain's resolver cannot route to them and
`gbrain doctor` will report `UNREACHABLE`.

## Provenance

These skills were lost on 2026-08-15 when `~/.claude/skills/` was wiped, and recovered
verbatim from gbrain transcript pages that happened to embed the original tool-call
payloads. That worked, and it should never have been the plan. This repo is the plan.

The recovery post-mortem — including the chunk-overlap trap that corrupts naive
reassembly — is written up in `ADR-100`.
