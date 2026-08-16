---
name: slice
version: 1.0.0
description: "Split an architecture into conflict-free parallel work slices. Assigns each slice exclusive file ownership, validates no two slices can collide, builds the dependency DAG, and writes one self-contained brief per slice plus slices.json. Stage 4 of 11 in the ladder (story -> arch -> contract? -> slice -> fleet -> before-pr -> review -> pentest? -> pr -> deploy? -> canary?)."
triggers:
  - slice
  - split this architecture
  - break into tasks
  - decompose the work
  - divide into sections
  - plan the worktrees
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

# /slice — architecture into conflict-free parallel work

Stage 4 of 11. `/arch` decided what to build. `/slice` decides **who can work in
parallel without stepping on each other**. `/fleet` executes it.

**Read `$ENG_BRAIN/CONVENTIONS.md` first.**

## When to invoke

After `/arch`, when the user wants the work divided: "slice it", "split this up",
"break into tasks", "divide into sections", "plan the worktrees".

If there is no `docs/arch/<slug>/ARCHITECTURE.md`, stop and run `/arch` first.
Slicing without an architecture produces tasks that contradict each other.

## Phase 0 — Preamble

Preamble from CONVENTIONS.md §7, then:

```bash
FEATURE_SLUG=<from the arch dir or the ask>
ARCH_DIR="$REPO_ROOT/docs/arch/$FEATURE_SLUG"
[ -f "$ARCH_DIR/ARCHITECTURE.md" ] || { echo "no architecture — run /arch first"; exit 1; }
mkdir -p "$ARCH_DIR/slices"
```

Read `ARCHITECTURE.md` in full, especially the **interfaces** section. Those interfaces
are the contract that lets slices be built blind to each other.

## Phase 0.5 — Learn how this user slices work

Before cutting anything, ask the brain how they have done it before. Slicing is a style
decision as much as a technical one, and the brain is where that style accumulates.

Cheap searches first. `gbrain think` is an uncached agentic loop and is the slowest call in
this skill; slice style is a lookup, not a reasoning problem, so it almost never earns one.

```bash
gbrain query "slice plan waves ownership" --no-expand
gbrain graph-query projects/<a-past-feature> --direction out --depth 2
```

Only if those come back empty *and* this is a large or unusual cut, escalate once:

```bash
gbrain think "What slice sizes and boundaries have worked for me, and which caused merge conflicts?"
```

Otherwise skip it. An empty brain does not get less empty by being searched harder.

Look specifically for:
- **Slice size** they settled on — 3 big or 6 small
- **Boundary style** — by layer, by bounded context, by entrypoint
- **Past collisions** — any timeline entry recording a merge conflict names a cut that
  failed. Do not repeat it.
- **Specialist assignments** that worked, feeding Phase 3.5

If the brain returns nothing, say so and proceed with the defaults below — then this run
becomes the first data point. Write the outcome back in Phase 5 so the next `/slice`
inherits it. That is the whole compounding mechanism; skipping the write-back breaks it.

## Phase 1 — Cut the slices

A good slice is:

- **Independently completable** — one agent, one worktree, no waiting on a sibling
  mid-flight. If it needs a sibling's output, that is a `depends_on`, not a parallel peer.
- **Exclusively owned** — it writes only files no other slice writes.
- **Verifiable alone** — it has its own tests that pass without the other slices.
- **One coherent change** — "add the sync table + its migration + its model" is a slice.
  "touch everything related to sync" is not.

Typical cuts that work: by layer (schema → API → UI), by bounded context, by
entrypoint. Cuts that fail: by file type, by "frontend/backend" when both edit shared
types, by developer preference.

Aim for **3–6 slices**. More than 6 and the coordination cost eats the parallelism;
fewer than 3 and you did not need a fleet.

Shared files (types, config, barrel exports, DI registration) are the usual collision
point. Handle them one of two ways, never by hoping:
1. Give one slice sole ownership and make the others depend on it, or
2. Pull the shared edit into a **slice 00** that runs alone first.

## Phase 2 — Ownership validation (the part that must not be skipped)

Every slice declares `owns`: glob patterns it may write. Two slices whose globs can
match the same file **will** produce a merge conflict in `/fleet`. Verify mechanically,
do not eyeball it:

```bash
python3 "$ENG_BRAIN/bin/owns.py" "$ARCH_DIR/slices.json" "$REPO_ROOT"
```

`owns.py` is the canonical, self-checked ownership gate (`owns.py --selfcheck`) — resolve
each slice's `owns` globs and prove no two slices' resolved sets intersect. It is the same
check `/fleet` re-runs before it creates a single worktree; use it here so a collision is
caught while it is still cheap to re-cut, not after four agents are already running.

On `FAIL`, re-cut the slices. Do not proceed with a known collision and do not
"just be careful in fleet" — parallel agents cannot be careful about each other.

This check only catches collisions among files that **already exist**. For new files,
compare the declared globs against each other by inspection too: two slices both
owning `src/api/**` collide even on an empty directory.

## Phase 3 — Dependency DAG

Set `depends_on` per slice. Then verify it is acyclic and compute the wave order:

```bash
python3 - "$ARCH_DIR/slices.json" <<'PY'
import json, sys
m = json.load(open(sys.argv[1]))
dep = {s["id"]: set(s.get("depends_on", [])) for s in m["slices"]}
unknown = {d for ds in dep.values() for d in ds} - set(dep)
if unknown:
    print("UNKNOWN DEP IDS:", unknown); sys.exit(1)
waves, done = [], set()
while len(done) < len(dep):
    ready = [i for i, d in dep.items() if i not in done and d <= done]
    if not ready:
        print("CYCLE among:", sorted(set(dep) - done)); sys.exit(1)
    waves.append(sorted(ready)); done |= set(ready)
for i, w in enumerate(waves, 1):
    print(f"wave {i}: {' '.join(w)}")
print("DAG: OK")
PY
```

Slices in the same wave run in parallel in `/fleet`. Keep wave 1 as wide as you can —
that is where the wall-clock win is. Two hard caps on that:

**Max 4 slices per wave.** The binding constraint is one human reading PRs, not agent
count. If a wave comes out wider, split it. Add to the DAG script:
`if len(wave) > 4: print(f"WAVE {i} TOO WIDE ({len(wave)}) — split it")`.

**A slice that touches the database gets its own wave, alone.** `/fleet` isolates slices
with git worktrees, and a worktree isolates *files*, not the database. Every parallel agent
runs its tests against the same live Postgres. If one slice migrates while a sibling tests,
the sibling is testing against a schema mutating underneath it, and the ownership gate
cannot see it because a migration's blast radius is not a file glob. Any slice owning
`supabase/migrations/**`, `*.sql`, or an ORM schema file is a wave of one.

## Phase 3.5 — Assign a specialist to each slice

Every slice gets three named agents: who **builds** it, who **reviews** it, who checks its
**tests**. `/fleet` dispatches exactly these. Picking a generalist when a specialist exists
is the most common waste in this pipeline — a `typescript-reviewer` catches things a
general reviewer does not.

**The default is eng-brain's own roster, which always ships with this plugin:**

| Role | Default agent (always available) |
|---|---|
| build | `eng-brain:slice-implementer` — owns-only, red-before-green, pastes runner output |
| review | `eng-brain:slice-reviewer` — fresh context, **no Write/Edit**, reports never fixes |
| test | `eng-brain:test-auditor` — judges whether tests assert on the brief's edge cases |

Upgrade any role to a language specialist **when that plugin is installed** — a specialist
catches what a generalist misses. Route on what the slice actually touches, not the
feature's topic; fall back to the eng-brain default whenever the specialist is absent:

| Slice touches | build (if installed) | review (if installed) |
|---|---|---|
| React / Next.js UI | `voltagent-lang:react-specialist` | `ecc:react-reviewer` |
| TypeScript / Node backend | `voltagent-lang:typescript-pro` | `ecc:typescript-reviewer` |
| Python | `voltagent-lang:python-pro` | `ecc:python-reviewer` |
| Go / Rust / Swift | `voltagent-lang:golang-pro` / `rust-engineer` / `swift-expert` | `ecc:go-reviewer` / `rust-reviewer` / `swift-reviewer` |
| DB schema, migrations, SQL | `ruflo-migrations:migration-engineer` | `ecc:database-reviewer` |
| API surface / contracts | `voltagent-core-dev:api-designer` | `ecc:typescript-reviewer` |
| Auth, crypto, user input, secrets | `voltagent-core-dev:backend-developer` | **`ecc:security-reviewer`** |
| Anything else | `eng-brain:slice-implementer` | `eng-brain:slice-reviewer` |

Test gate is `eng-brain:test-auditor` by default (or `ecc:tdd-guide` if you prefer it);
use `ecc:e2e-runner` for slices whose done-criteria are user-visible flows. Recording a
specialist that is not installed is not a hard failure — `/fleet` falls back to the
eng-brain default and notes the substitution — but prefer to record what will actually run.

Two overrides that matter more than the table:

- **Any slice touching auth, payments, PII, or user input gets `ecc:security-reviewer`**,
  regardless of language. Trust boundaries outrank idiom.
- **A slice that is fixing a bug, not building a feature**, routes build to
  `voltagent-qa-sec:debugger` (or the `investigate` skill for a gnarly one). Debugging and
  greenfield implementation are different jobs and the agents are tuned differently — do
  not send a `*-pro` implementer to chase a root cause.

Check Phase 0.5's brain results before finalizing: if a past assignment underperformed on
a similar slice, pick differently and note why.

## Phase 4 — Write the briefs

Each worktree agent sees **only its brief**. It cannot read the other slices, cannot
ask a sibling a question, and cannot see the conversation you are having now. If it is
not in the brief, it does not exist.

`$ARCH_DIR/slices/NN-<name>.md`:

```markdown
# Slice NN: <name>

## Goal
One paragraph. What is true when this is done.

## Owns (you may write ONLY these)
- `path/glob/**`

Touching anything outside this list is a bug. If you believe you must, stop and
report it instead — another slice owns that file and is editing it right now.

## Context
The relevant excerpt of ARCHITECTURE.md — inlined, not linked. Include the ADR
decisions that constrain this slice and the reason behind them.

## Interfaces you must honor
Exact signatures/schemas this slice must produce or consume. Copy them verbatim from
ARCHITECTURE.md. Other slices are being built against these right now; changing one
silently breaks them.

## Depends on
Slice IDs that land first, and what they give you.

## Done when
- [ ] <behavioral criterion, not "code written">
- [ ] tests pass, including the edge cases below
- [ ] docs updated

## Edge cases to test
Concrete list. Empty input, concurrent write, auth boundary, the failure the ADR
called out. This is what /fleet's test gate checks against.

Every row of the **Failure modes** table in ARCHITECTURE.md must land in exactly one
slice's list here, quoted with its guaranteed behaviour so the test has something to
assert. A row assigned to no slice is a mode nobody tests, because `/fleet`'s gate only
checks what the brief lists. If a row genuinely belongs to no slice, put it in that
slice's **Out of scope** with the reason.

Do not check this off from memory. After writing every brief, run:

```bash
python3 "$ENG_BRAIN/bin/"gate.py modes "$ARCH_DIR" || {
  echo "a failure mode reaches no brief — fix the briefs before the Phase 6 gate"; }
```

It parses the Failure-modes table and every brief's edge-case and out-of-scope sections,
and names any row that reaches neither. This is the same mechanical discipline as
`check_owns.py`, applied to the other thing that silently fails to propagate.

## Out of scope
Explicit. Prevents an agent from helpfully expanding into another slice's files.
```

Then write `$ARCH_DIR/slices.json`:

```json
{
  "feature": "<feature-slug>",
  "source_branch": "<the branch you were on — the PR target>",
  "created": "<YYYY-MM-DD>",
  "slices": [
    {
      "id": "01",
      "name": "sync-schema",
      "owns": ["db/migrations/**", "src/models/sync*.ts"],
      "depends_on": [],
      "covers": ["AC-1", "AC-4"],
      "brief": "slices/01-sync-schema.md",
      "status": "ready",
      "agents": {
        "build":  "ruflo-migrations:migration-engineer",
        "review": "ecc:database-reviewer",
        "test":   "ecc:tdd-guide"
      },
      "kind": "feature"
    }
  ]
}
```

`source_branch` must be the branch recorded in Phase 0 — every PR in `/fleet` targets it.

`covers` is the list of `AC-<n>` ids from `STORY.md` that this slice implements. It is not
optional bookkeeping: `coverage.py` reads it to prove every acceptance criterion reaches a
slice, and `/fleet` reads it so each slice's agent knows which criteria its tests must
prove. Rules that the gate enforces:

- **Every `AC-<n>` in the story must appear in some slice's `covers`.** A criterion no slice
  claims is a requirement nobody is building — run `coverage.py map` in Phase 6 and it fails.
- **A slice that implements no criterion writes `"covers": []`** — scaffolding, shared types,
  config. An absent `covers` key is `UNVERIFIED`, not a silent pass: it means "nobody
  answered", which is exactly the slice most likely to have dropped a requirement.
- A criterion may be split across slices; list it in each that contributes.

## Phase 5 — Brain write-back

Append the slice plan to the architecture page's timeline and tag it:

Record the plan **and the style choices behind it** — the style is what Phase 0.5 reads
next time. A timeline entry that only says "sliced into 4 tasks" teaches nothing.

```bash
gbrain timeline-add projects/$FEATURE_SLUG $(date +%F) \
  "Sliced into 4 tasks, cut by layer (schema/api/ui). Waves: 2 parallel, then 03, then 04. \
   Shared types pulled into slice 00 to avoid the collision that hit <past-feature>. \
   Agents: 01 migration-engineer+database-reviewer, 02 typescript-pro+security-reviewer (auth path)."
gbrain tag projects/$FEATURE_SLUG sliced
```

Write down, in the entry itself:
- **how you cut** (by layer / context / entrypoint) and why
- **slice count and wave shape**
- **which specialists** you assigned and to what
- **any collision you designed around**, naming the past feature it came from

Individual slices are ephemeral work orders — they do not get their own brain pages.
Their **outcomes** roll up into the architecture page's timeline in `/fleet`.

This entry is the only durable record of how you work. `/arch` reads it for decisions;
`/slice` Phase 0.5 reads it for style. Thin entries here are why `gbrain think` stays
thin — the graph compounds only as well as what you write into it.

## Phase 6 — Gate

Run every mechanical check, including the new coverage map — the cut is not done until all
pass:

```bash
python3 "$ENG_BRAIN/bin/owns.py"      "$ARCH_DIR/slices.json" "$REPO_ROOT"   # disjoint ownership
python3 "$ENG_BRAIN/bin/tractable.py" "$ARCH_DIR/slices.json" "$REPO_ROOT"   # no un-editable files
python3 "$ENG_BRAIN/bin/concepts.py"  "$ARCH_DIR/slices.json" "$REPO_ROOT"   # shared concepts owned
python3 "$ENG_BRAIN/bin/coverage.py"  map "$ARCH_DIR"                        # every AC reaches a slice
```

`coverage.py map` is the new gate: it fails if any `AC-<n>` in `STORY.md` is claimed by no
slice's `covers`, or if a slice claims a criterion the story does not define. A cut that
leaves a requirement unbuilt does not pass this phase — fix the `covers` map before `/fleet`.

Record the gate:

```bash
python3 "$ENG_BRAIN/bin/state.py" pass "$ARCH_DIR" --stage slice --artifact slices.json
```

Then present:

```
Sliced: <feature> → 4 slices
  wave 1 (parallel): 01-sync-schema, 02-conflict-resolver
  wave 2:            03-api-layer  (needs 01)
  wave 3:            04-ui         (needs 03)
  ownership: OK (no collisions)   DAG: OK   coverage: OK (AC-1..AC-6 all mapped)
  briefs: docs/arch/<slug>/slices/

Next: /fleet to run wave 1 in parallel worktrees.
```

Stop. The user reviews the cut before any worktree is created.

## Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| `OWNERSHIP: FAIL` | two slices share a file | Re-cut, or give one slice sole ownership + a `depends_on` |
| `CYCLE among:` | circular `depends_on` | Merge the cycle into one slice — it is not decomposable |
| Agent goes outside `owns` | brief lacked the constraint | "Out of scope" section must be explicit |
| Slices merge cleanly but the feature is broken | interfaces underspecified | Interfaces are the only cross-slice contract; make them exact |
