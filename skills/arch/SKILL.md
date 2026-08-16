---
name: arch
version: 1.0.0
description: "Brain-grounded architecture for a new feature. Queries gbrain for your prior decisions and contradictions, traces the real code flow, proposes 1-3 options with a recommendation, writes ARCHITECTURE.md + ADRs to the repo and to the brain. Stage 2 of 11 in the ladder (story -> arch -> contract? -> slice -> fleet -> before-pr -> review -> pentest? -> pr -> deploy? -> canary?)."
triggers:
  - arch
  - design this feature
  - architect this
  - build the architecture
  - how should I build
  - new feature design
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Grep
  - Glob
  - Agent
  - AskUserQuestion
---

# /arch — brain-grounded architecture

Stage 2 of 11. `/arch` decides *what to build and why*. `/slice` splits it.
`/fleet` builds it.

**Read `$ENG_BRAIN/CONVENTIONS.md` before doing anything else.**
It defines the page types, link types, read/write protocol, and the current known
state of the brain. Everything below assumes it.

**Then read the playbook that matches the job** — they carry the actual method; the
phases below are the scaffolding around it:

| Situation | Read |
|---|---|
| Feature into an existing codebase | `_eng-brain/BROWNFIELD.md` |
| New project, no code yet | `_eng-brain/GREENFIELD.md` |

Brownfield's hard problem is *fitting*; greenfield's is *restraint*. They need different
research, different defaults, and different failure modes — do not run one method on the
other's problem. Both apply the ponytail ladder **after** research, never instead of it.

## When to invoke

The user is starting a feature and wants the full engineering picture before code:
"design this", "how should I build X", "architect the Y system", "arch".

Do **not** invoke for a one-file bug fix. The ladder applies to architecture too —
if the answer is "add a guard in the shared function", say that and stop.

## Phase 0 — Preamble

Run the preamble from CONVENTIONS.md §7. Then:

```bash
FEATURE_SLUG=<kebab-case-from-the-ask>     # e.g. offline-sync
ARCH_DIR="$REPO_ROOT/docs/arch/$FEATURE_SLUG"
mkdir -p "$ARCH_DIR"
echo "source=$SOURCE_ID branch=$SOURCE_BRANCH dir=$ARCH_DIR"
```

Record `SOURCE_BRANCH`. It becomes the PR target three stages later, and it must be
captured *now*, before any branch switching.

## Phase 1 — Priors (run in parallel with Phase 2)

This is the phase that makes the system worth having. Never skip it.

**Cheap calls first, and only escalate if they find something.** `gbrain think` is an
agentic loop on a provider with no prompt caching, so it runs hot and it is by far the
slowest thing in this skill. Everything else here is a search. Running a deep reasoning
loop over a brain that returns nothing is the single biggest waste in the pipeline.

Start with the searches, which are cheap and can all go in one call:

```bash
gbrain query "<feature area> architecture decision tradeoff" --no-expand
```

Plus the MCP tools that have no CLI equivalent (dispatch these together, not one by one):
- `takes_search` — your graded past opinions on this area
- `find_contradictions` — where this design would fight an earlier decision
- `find_trajectory` — how your thinking on this area has moved over time

**Then decide whether `think` is worth it.** Run it only if the searches above returned
at least one prior worth reasoning over, or the design question genuinely turns on a past
decision you cannot resolve from what came back:

```bash
gbrain think "<the design question>. What have I decided about this before, and why?"
```

If the searches came back empty, skip `think`, say "brain has nothing here yet" and move
on. You are not losing recall you had; you are declining to pay for a deep search of an
empty index. Ask it one narrow question when you ask it at all — a vague prompt is what
makes the loop long.

For each prior decision found, capture: **what you decided, why, and whether it still
holds.** A prior decision that no longer holds becomes a `supersedes` edge in Phase 5.

Report priors to the user in this shape — never bury them:

```
Priors found:
  ADR-004 (2026-03) chose Postgres RLS over app-layer authz — still holds
  ADR-007 (2026-05) chose optimistic UI — CONFLICTS with offline-first here
  Gap: brain has nothing on conflict resolution strategy
```

If `gbrain think` reports a gap, print the gap. The brain is at `brain_score 22/100`
with an empty link graph, so thin recall is expected right now — say so rather than
implying you did a thorough historical review when you did not.

## Phase 2 — Ground truth (run in parallel with Phase 1)

Priors tell you what you decided. This tells you what actually exists.

"In parallel with Phase 1" is a real instruction, not a note. Issue the `ecc:code-explorer`
dispatch below **in the same message** as Phase 1's search calls, so the code trace runs
while the brain lookups are in flight. Done sequentially this phase doubles `/arch`'s
wall clock for no reason: the two phases share no inputs.

Dispatch `ecc:code-explorer` to trace the real execution path end to end, and if the
repo is registered as a gbrain code source:

```bash
gbrain code-def <EntryPointSymbol>
gbrain code-callers <EntryPointSymbol>
gbrain code-refs <SharedType>
```

The output you need is: entry points, the data model as it is today, the trust
boundaries, and every caller that a change here would touch. Per the root-cause rule,
find where all callers route through — that is where the change belongs.

## Phase 3 — Options and recommendation

Produce **1–3 options**, never more. For each: the approach in two sentences, what it
costs, and its failure mode. Then **one recommendation with the reason**.

An option set where two options are obviously bad is a fake choice — cut it to one and
say "this is the only sensible shape, here's why."

For a feature with a genuinely wide solution space, generate the candidates **independently
and in parallel** rather than writing option 2 as a variation on option 1 — a lone author
anchors on the first idea and the rest drift toward it. Dispatch the `architect` agent
several times, each from a different angle, in one message:

```
Agent(subagent_type: "eng-brain:architect")  angle: "minimise blast radius"
Agent(subagent_type: "eng-brain:architect")  angle: "least new infrastructure"
Agent(subagent_type: "eng-brain:architect")  angle: "optimise the common read path"
```

Each returns an approach, its cost, its one-way doors, and its own failure mode, blind to
the others. You then synthesise: recommend the strongest, and graft the best idea from each
runner-up. The `architect` agent is **read-only** — it cannot write code, so a "candidate"
can never quietly become half an implementation you are then reluctant to discard. For a
small or obvious feature, skip the fan-out and write the options directly; the ladder
applies to `/arch` too.

Call out explicitly:
- what this makes hard to change later (the one-way doors)
- where it contradicts a prior decision from Phase 1

### The failure-mode sweep (required, not optional)

Walk every line. An LLM only explores the direction it was pointed at, so the sweep is
what forces the other directions. For each, state the behaviour the design guarantees:

- **Volume** — 10x traffic, 10x rows, 10x concurrent writers on the same record
- **Size** — the largest realistic input (long document, huge upload, 10k-row file) and
  what happens one byte past the limit
- **Shape** — malformed, unknown, mixed, or missing data types at every trust boundary
- **Cost and latency** — the slowest and most expensive path, what a timeout mid-flight
  leaves behind, and what an expensive model call costs at real usage
- **Partial failure** — one dependency down, one of two writes committed, a retry
  arriving twice, a job dying halfway
- **Boundaries** — empty, zero, null, unauthorized, and another tenant's data
- **Version skew** — the previously deployed client calling the new backend, and the new
  code reading rows written before the migration. Every other axis inspects the new state;
  this is the only one that inspects the transition into it.

Each line becomes a row in the **Failure modes** table of ARCHITECTURE.md: the mode, the
guaranteed behaviour, and which component owns it. `/slice` turns every row into a brief's
edge case, and `/fleet`'s test gate checks that a test actually asserts on it.

A failure mode you do not write here will never be tested, at any later stage. This is the
single highest-leverage part of `/arch`.

Use `AskUserQuestion` only if the options differ in a way you genuinely cannot resolve
from the code and the priors. Otherwise recommend and move.

## Phase 4 — ADRs

One ADR per **non-obvious** decision. If the decision is "use the framework's router",
that is not an ADR. If it is "we accept eventual consistency between device and server",
that is.

`$ARCH_DIR/ADR-<nnn>-<topic>.md`:

```markdown
# ADR-001: <decision in imperative form>

- Status: accepted
- Date: <YYYY-MM-DD>
- Supersedes: <analysis/adr-xxx or none>

## Context
What forces this decision. Include the prior decision from Phase 1 if relevant.

## Decision
What we are doing. One paragraph, no hedging.

## Consequences
What this buys, what it costs, and what it forecloses.

## Alternatives rejected
Each with the reason it lost.
```

Number ADRs continuing from what already exists across the repo, not from 001 each time:
`ls docs/arch/*/ADR-*.md 2>/dev/null | wc -l`.

## Phase 5 — Write repo, then brain

Write `$ARCH_DIR/ARCHITECTURE.md`: the recommended design, the component boundaries,
the data flow, the interfaces other slices must honor, the **Failure modes** table from
Phase 3, and links to each ADR.

`## Failure modes` is a table of `| Mode | Guaranteed behaviour | Owned by |`, one row per
line of the Phase 3 sweep. It is the input to every test written downstream, so a mode
missing here is a test nobody writes.

`## Rollout` is required whenever this feature touches schema, an API shape, or anything
already deployed. Five lines, no prose:

- **Migration order** — what must be applied before what, and whether the code deploys
  before or after the migration
- **Backward-compat window** — how long old clients and pre-migration rows must keep
  working, and what makes them work
- **Flag** — the flag this ships behind, or "none" with the reason
- **Rollback** — the actual primitive. `git revert` is correct for code and *unsafe* for
  schema: reverting a merge that carried a migration un-deploys the reader and leaves the
  mutated table. If this feature migrates, name the down path explicitly.
- **The one signal that says it broke** — the metric, log line or query you would check
  first at 3am

Every stage after this one inspects the new state. Rollout is the only place the
*transition* gets designed, so if it is missing here nothing downstream will test it.

The **interfaces** section matters more than it looks — in `/fleet`, parallel worktree
agents cannot see each other's code. That section is the only contract keeping them
compatible. Make every cross-slice interface explicit and complete there.

Then write to the brain. Run these commands — do not paraphrase them, do not defer to
another document, do not skip because "the repo docs exist". A repo file the brain never
sees teaches the next `/arch` nothing.

```bash
# Architecture page (no --source: eng-brain pages go to the default source, see CONVENTIONS §5)
gbrain capture --file "$ARCH_DIR/ARCHITECTURE.md" \
  --slug "projects/$FEATURE_SLUG" --type project --quiet

# One capture per ADR
gbrain capture --file "$ARCH_DIR/ADR-012-<topic>.md" \
  --slug "analysis/adr-012-<topic>" --type analysis --quiet

# Edges — the architecture points at each ADR that settled a question in it
gbrain link "projects/$FEATURE_SLUG" "analysis/adr-012-<topic>" --link-type decided_by

# Supersede any prior decision Phase 1 found to be obsolete (new page -> old page)
gbrain link "analysis/adr-012-<topic>" "analysis/adr-007-<old>" --link-type supersedes

# Priors that shaped this without being replaced
gbrain link "projects/$FEATURE_SLUG" "<prior-slug>" --link-type informed_by

# Timeline + tags
gbrain timeline-add "projects/$FEATURE_SLUG" "$(date +%F)" "Architecture accepted: <one line>. N ADRs."
gbrain tag "projects/$FEATURE_SLUG" eng-brain
gbrain tag "projects/$FEATURE_SLUG" architecture
```

Note: `/story` and `/contract` write their pages with `gbrain call put_page` (it reports the
edge count, which `capture` does not). `capture` is the newer single entrypoint and handles
slug/type/disk routing in one call — prefer it here in `/arch`, but both write real pages.

Verify the edges landed rather than assuming:

```bash
gbrain graph-query projects/$FEATURE_SLUG --direction out --depth 1
```

If that prints no edges, the write-back failed — fix it before moving on. A page with
no edges is invisible to `gbrain think`, which means the next `/arch` will not find it.

## Phase 6 — Gate

Record the gate so `/sdlc` can advance and a resumed session knows this stage is done:

```bash
python3 "$ENG_BRAIN/bin/state.py" pass "$ARCH_DIR" --stage arch --artifact ARCHITECTURE.md
```

If that reports no `STATE.json`, the ladder was never started — run `/story` (or `/sdlc`)
first. Then stop and present:

```
Architecture: <feature>
  Recommended: <one line>
  ADRs: 3 written (ADR-012, ADR-013, ADR-014)
  Conflicts with priors: ADR-007 (superseded, edge written)
  Brain: projects/<slug> + 3 edges + timeline entry
  Repo: docs/arch/<slug>/

Next: /slice to split this into parallel worktree tasks.
```

Do not run `/slice` automatically. The user reviews the architecture first — that is
the whole point of writing it down.

## Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| `gbrain think` returns nothing useful | brain has 540 orphans, no link graph | Expected today. Report the gap; the graph builds as you use this. |
| `capture` writes to the wrong repo | `--source` omitted | Resolve `SOURCE_ID` in the preamble; never omit it |
| `graph-query` shows no edges | linked before both pages existed | `capture` both pages first, then `link` |
| Architecture too vague for `/slice` | interfaces section thin | Every cross-slice contract must be explicit; re-run Phase 5 |
