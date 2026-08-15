# eng-brain

**A software development lifecycle for AI coding agents — with gates that actually hold.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Claude Code](https://img.shields.io/badge/Claude%20Code-plugin-6b4fbb)](https://claude.com/claude-code)
[![Skills](https://img.shields.io/badge/skills-17-green.svg)](skills/)

One feature goes in at `/sdlc` and comes out as reviewed pull requests — through story,
architecture, contracts, slicing, parallel implementation, and gating. Every architectural
decision is written back to a knowledge brain, so the *next* feature inherits what the last
one learned instead of rediscovering it.

```
/story → /arch → /contract? → /slice → /fleet → /before-pr → /review → /pentest? → /pr → /deploy? → /canary?
```

---

## Quick start

```
/plugin marketplace add RamanaNani/eng-brain
/plugin install eng-brain@eng-brain
```

Then:

```
/sdlc build offline sync for the notes editor
```

That's enough to run the pipeline. To give it memory, add a brain — one command, no account
needed:

```bash
bun add github:garrytan/gbrain && gbrain init --pglite
```

Full walkthrough: **[docs/SETUP.md](docs/SETUP.md)**.

---

## Why this exists

Agent pipelines usually fail in one of two ways. Either every stage is a fresh start — the
agent re-derives the architecture it settled last week — or the stages exist but nothing
enforces them, so *"run the tests"* quietly becomes *"say the tests passed."*

eng-brain addresses both. The second half is the interesting one:

> **Gates are code, not prose.** A stage cannot be marked complete out of order, because
> `state.py` returns exit 2 and refuses. Tests cannot be declared green without runner
> output, because `gate.py` parses that output itself and treats `3 failed, 5 passed` as
> red.

That distinction is the whole design. Prose instructions to a model are advisory — they
compete with everything else in context and they lose under time pressure. A non-zero exit
code does not lose that argument. Reasoning: [ADR-101](docs/adr/ADR-101-ladder-as-data.md).

**Decisions persist.** Each stage reads the brain before deciding and writes back after, so
architecture becomes a queryable graph of decisions and the ADRs that settled them — rather
than a directory of markdown nobody opens again.

---

## What you get

**17 skills.** The eleven ladder stages, plus:

| Skill | What it's for |
|---|---|
| `/sdlc` | the spine — holds state, dispatches stages, enforces gates |
| `/impeccable` | review rubric: correctness, honesty of evidence, blast radius, reversibility |
| `/rollback` | incident runbook — stop the harm, then diagnose. Not a ladder rung; you invoke it when a deploy is causing damage. |
| `/grill-me` | adversarial interview to stress-test a design before you build it |
| `/brain-sync` | manual brain sync + health delta |
| `/change` | change requests against an existing system |

**Five tools** under `skills/_eng-brain/bin/`:

| Tool | What it does |
|---|---|
| `state.py` | the ladder and its gates — refuses out-of-order and unjustified skips |
| `gate.py` | failure-mode coverage + honest test-output parsing across 8 runners |
| `owns.py` | proves no two slices own the same file |
| `concepts.py`, `tractable.py` | scope and decomposability checks |

**A shared contract** — `skills/_eng-brain/CONVENTIONS.md` — covering brain page types, link
types, and the read/write protocol every stage follows.

---

## The ladder

`/sdlc` is the spine. It holds state, decides which stage runs next, and stops at the first
failing gate. Stage skills work standalone, but invoked directly they can't tell they're
being run out of order — which is the problem the spine exists to fix.

| Stage | Produces | Gate to advance |
|---|---|---|
| `story` | `STORY.md` | ≥1 acceptance criterion, ≥1 negative case, ≥1 non-goal |
| `arch` | `ARCHITECTURE.md`, `ADR-*.md` | ≥2 candidates weighed, ≥1 ADR, contradictions surfaced |
| `contract` *(opt)* | `contracts/` | required iff the feature spans ≥2 repos |
| `slice` | `slices.json` | ownership disjoint, DAG acyclic, failure modes routed |
| `fleet` | `FLEET.md` | every slice green, **runner output shown** |
| `before-pr` | `GATE.md` | `gate.py` passes on every slice |
| `review` | `REVIEW.md` | no scope drift either way, `/impeccable` rubric clean |
| `pentest` *(opt)* | `PENTEST.md` | no unresolved high/critical findings |
| `pr` | `PR.md` | PRs opened — **never merged** |
| `deploy` *(opt)* | `DEPLOY.md` | rollback path recorded **and dry-run** before release |
| `canary` *(opt)* | `CANARY.md` | baseline recorded, delta non-regressive |

`deploy` sits after `pr` because **a human merges in between**. It detects that merge; it
never performs it. Its gate is the rollback path: `/deploy` refuses to ship until a way back
has been written down *and* dry-run with `git revert --no-commit`, because the moment you
need a rollback plan is the moment you are least able to think one up.

The three gates before `pr` are separate on purpose, and ordered cheapest-first:

- **`before-pr`** is mechanical — it proves the code *works*. Fast, so it runs first;
  nobody should spend review attention on a branch whose suite is red.
- **`review`** is judgment — it asks whether the work is the work that was **asked for**.
  No test can tell you that.
- **`pentest`** is security — a Strix-style DAST run against a live target, gated behind an
  explicit `engagement.md` scope file. Optional, because a docs change has no attack surface.

> **Optional means "may be skipped", not "may be ignored".** An optional stage still blocks
> the ladder until it is explicitly recorded — `state.py` refuses `pr` while `pentest` is
> merely pending. Skipping requires a reason that goes on the record:
> ```bash
> state.py skip "$ARCH_DIR" --stage pentest --why "docs-only change, no attack surface"
> ```
> Silently dropping the security stage is precisely the outcome it exists to prevent.

State lives in the **target** repo at `docs/arch/<feature>/STATE.json`, so a feature's
position travels with its branch and survives a lost session.

```
$ /sdlc where is offline-sync

offline-sync  ·  slice → fleet
  ✓ story  ✓ arch  – contract (single repo)  ✓ slice  · fleet  · before-pr  · review  · pentest  · pr  · deploy  · canary
```

---

## The two rules

Everything else is negotiable. These aren't — and both are mechanised rather than trusted,
because they're the rules most likely to be rationalised away in the moment:

1. **Never merge.** `/pr` opens pull requests and stops. A human accepts. No `--auto-merge`,
   no "the gate passed so I merged it."
2. **Never claim a green suite without runner output.** `gate.py testout` understands
   pytest, jest, cargo, mocha, `node --test`, `go test`, TAP, and `unittest`. A missing
   output file is `NOT RUN`, and `NOT RUN` is a failure.

---

## Requirements

| | | |
|---|---|---|
| **Claude Code** | required | `npm i -g @anthropic-ai/claude-code` |
| **python3** ≥ 3.9 | required | the gate and ladder tools |
| **bun** | for the brain | [bun.sh](https://bun.sh) |
| **gbrain** | for memory | `bun add github:garrytan/gbrain` |
| **gh** | for `/pr` | `brew install gh && gh auth login` |

Runs without a brain — you lose the memory, not the pipeline.

---

## Installation

### Plugin (recommended)

```
/plugin marketplace add RamanaNani/eng-brain
/plugin install eng-brain@eng-brain
```

### Clone (if you'll modify the skills)

```bash
git clone https://github.com/RamanaNani/eng-brain.git
cd eng-brain
./skills/_eng-brain/setup.sh    # preflight — tells you exactly what's missing
./install.sh                    # projects skills into ~/.claude/skills/
```

> **Pick one, not both.** Installing the plugin *and* running `./install.sh` registers every
> skill twice and makes resolution ambiguous. Switching from clone to plugin? Remove the
> projected copies first:
> ```bash
> for s in sdlc story arch contract slice fleet before-pr review pentest pr deploy canary rollback \
>          impeccable grill-me brain-sync change _eng-brain; do
>   rm -rf ~/.claude/skills/$s
> done
> ```

---

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `GBRAIN_PREPARE` | — | **must be `true`.** The pooler rejects session-level prepared statements; without it queries return *empty results rather than an error*. |
| `GBRAIN_DISABLE_DIRECT_POOL` | `1` | avoids the IPv6-only direct Supabase host |
| `ENG_BRAIN_AUTO_SYNC` | `1` | clone mode: re-project skills automatically on drift |
| `ENG_BRAIN_NO_UPDATE_CHECK` | `0` | plugin mode: disable the daily version check |
| `CLAUDE_SKILLS_DIR` | `~/.claude/skills` | where `install.sh` projects to |

In `~/.claude/settings.json`:

```json
{ "env": { "GBRAIN_PREPARE": "true" } }
```

---

## Staying current

A `SessionStart` hook keeps installs from silently rotting, and behaves differently by mode
because the risk profiles differ:

| Mode | Behaviour |
|---|---|
| **clone** | Detects drift between repo and `~/.claude/skills/`, then **re-installs automatically**, printing one line. The projection is derived data — rebuilding it is safe and idempotent. |
| **plugin** | **Notifies only**, at most once a day, when `main` has a newer version. Fetching code from the network isn't a hook's call to make unasked. |

Silent when there's nothing to say. A hook that speaks every session gets ignored, and then
it isn't a hook, it's noise.

---

## Verifying

```bash
./skills/_eng-brain/setup.sh                     # full environment preflight
./install.sh --check                             # installed copy matches this repo
python3 skills/_eng-brain/bin/gate.py selfcheck  # must print OK
gbrain doctor                                    # brain health + skill reachability
```

`gate.py`'s selfcheck is load-bearing and worth explaining. The original `gate.py` was
partially lost; its test suite survived but its implementation didn't. The implementation
here was rebuilt to satisfy that suite, which pins exact behaviour *and* exact diagnostic
wording — several checks share an exit code, so only the message distinguishes "the file was
empty" from "the file was unparseable," and the operator needs to know which. Run it after
any edit to that file.

---

## Uninstall

```bash
# plugin
/plugin uninstall eng-brain@eng-brain
/plugin marketplace remove eng-brain

# clone
for s in sdlc story arch contract slice fleet before-pr review pentest pr deploy canary rollback \
         impeccable grill-me brain-sync change _eng-brain; do
  rm -rf ~/.claude/skills/$s
done
```

Neither touches your brain or your `docs/arch/` artifacts. To remove the brain too:
`rm -rf ~/.gbrain`.

---

## Documentation

| Doc | What's in it |
|---|---|
| [docs/SETUP.md](docs/SETUP.md) | install, all four brain engines, verification, troubleshooting |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | how it fits together, and what it deliberately doesn't do |
| [ADR-101](docs/adr/ADR-101-ladder-as-data.md) | why gates are code rather than prose |
| [ADR-100](docs/adr/ADR-100-claude-code-setup-recovery.md) | the recovery post-mortem this repo came out of |
| `skills/_eng-brain/CONVENTIONS.md` | the brain contract every stage follows |

---

## Layout

```
.claude-plugin/     marketplace.json + plugin.json — this repo IS a marketplace
hooks/              SessionStart wiring + sync.sh
skills/             everything here ships with the plugin
  sdlc/             the spine — start here
  story/ arch/ contract/ slice/ fleet/ before-pr/ pr/ canary/
  impeccable/ grill-me/ brain-sync/ change/
  _eng-brain/       shared library, not a skill (no SKILL.md)
    CONVENTIONS.md  GREENFIELD.md  BROWNFIELD.md  setup.sh
    bin/            state.py  gate.py  owns.py  concepts.py  tractable.py
docs/               SETUP, ARCHITECTURE, adr/
```

The shared library lives *under* `skills/` because a plugin ships only its `skills`
directory — anything outside it would be missing for plugin users.

---

## Status

Working and in use, with known rough edges — stated plainly rather than discovered later:

- `owns.py`, `concepts.py`, and `tractable.py` parse and are recovered, but have no
  selfcheck the way `gate.py` does. Treat their output as informative, not authoritative.
- `before-pr`, `canary`, and `impeccable` are newly written and haven't yet been run against
  a real feature end to end.
- No CI. `./install.sh --check` and `gate.py selfcheck` should gate every commit.

## Contributing

Edit this repo, then `./install.sh`. Never edit `~/.claude/skills/` directly — it's a
projection, and `./install.sh --check` exists to catch exactly that mistake.

Before opening a PR: preflight green, `gate.py selfcheck` passing. New skills need a
`triggers:` array in frontmatter, or gbrain's resolver can't route to them and
`gbrain doctor` reports `UNREACHABLE`.

## Provenance

These skills were lost on 2026-08-15 when `~/.claude/skills/` was wiped, and recovered
verbatim from gbrain transcript pages that happened to embed the original tool-call
payloads. That worked, and it should never have been the plan. This repo is the plan.

## Attribution

The `pentest` skill is derived from [usestrix/strix](https://github.com/usestrix/strix)
(Apache-2.0). Its methodology and playbooks are Strix's; the pipeline orchestration around
them is ours. Strix's playbooks are fetched at runtime by `sync-upstream.sh` rather than
vendored, so no Apache-2.0 code ships in this MIT repository.

## License

MIT — see [LICENSE](LICENSE).
