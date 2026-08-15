# eng-brain

A brain-grounded SDLC pipeline for Claude Code. One feature goes in at `/sdlc`, and comes
out as reviewed PRs — with every architectural decision written back to gbrain so the next
feature inherits it.

## Why this repo exists

These skills lived only in `~/.claude/skills/` and were lost on 2026-08-15 when a restart
wiped the directory. They were recovered from gbrain transcript pages, which happened to
embed the original tool-call payloads. That worked, but it should never be the plan.

This repo is the plan. `install.sh` projects it into `~/.claude/skills/`; `--check`
verifies the installed copy still matches.

See `docs/ARCHITECTURE.md` for the design and `../docs/analysis/ADR-100-*.md` for the
recovery post-mortem.

## Install

```bash
./install.sh          # project skills into ~/.claude/skills
./install.sh --check  # verify installed copies match this repo
./install.sh --lock   # regenerate skills.lock.json
```

Requires `gbrain` on `PATH` (`~/.bun/bin`) and `GBRAIN_PREPARE=true` exported — see
`lib/CONVENTIONS.md` §7.

## The ladder

```
/story → /arch → /contract? → /slice → /fleet → /before-pr → /pr → /canary?
```

Drive it with **`/sdlc`**, which holds the state and the gates. The stage skills still work
standalone, but invoked directly they cannot tell they are being run out of order.

| Stage | Produces | Gate to advance |
|---|---|---|
| `story` | `STORY.md` | ≥1 acceptance criterion, ≥1 negative case, ≥1 non-goal |
| `arch` | `ARCHITECTURE.md`, `ADR-*.md` | ≥2 candidates weighed, ≥1 ADR, contradictions surfaced |
| `contract` *(opt)* | `contracts/` | required iff ≥2 slices share an interface |
| `slice` | `slices.json` | ownership disjoint, DAG acyclic, failure modes routed |
| `fleet` | `FLEET.md` | every slice green, runner output shown |
| `before-pr` | `GATE.md` | `gate.py` passes on every slice |
| `pr` | `PR.md` | PRs opened — **never merged** |
| `canary` *(opt)* | `CANARY.md` | baseline recorded, delta non-regressive |

State lives in `docs/arch/<feature>/STATE.json` in the *target* repo, so it travels with
the artifacts and survives a lost session.

## Layout

```
skills/          one directory per skill, each with SKILL.md
  sdlc/          the spine — start here
lib/
  CONVENTIONS.md the shared contract: page types, link types, read/write protocol
  GREENFIELD.md  / BROWNFIELD.md
  bin/
    state.py     the ladder + gates (has --help)
    gate.py      failure-mode coverage + honest test output (has selfcheck)
    owns.py      slice file-ownership disjointness
    concepts.py  / tractable.py
    _recovered/  partially-recovered originals, kept for provenance
docs/
  ARCHITECTURE.md
  adr/
```

## Standards

`/impeccable` is the review rubric — correctness, honesty of evidence, blast radius,
reversibility. It is not a ladder stage; `/before-pr` mechanises the parts that can be
mechanised and `/impeccable` covers the rest.

Two rules the whole system rests on:

- **Never merge a PR.** `/pr` opens and stops. A human accepts.
- **Never claim tests pass without runner output.** `gate.py testout` treats
  `3 failed, 5 passed` as red, and treats a missing output file as NOT RUN.

## Verifying the tools

```bash
python3 lib/bin/gate.py selfcheck   # must print OK
python3 lib/bin/state.py --help
```

`gate.py`'s selfcheck is inherited from the original implementation and pins exact
behaviour *and* exact diagnostic wording. It is the reason the rebuilt implementation can
be trusted — run it after any edit.
