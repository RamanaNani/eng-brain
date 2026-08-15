---
name: story
version: 1.0.0
description: "Turn a request into a user story with acceptance criteria and a runnable definition of done, before any design exists. Names the user, the job, the observable outcome, and the command that proves it. Writes STORY.md. Stage 1 of 11 in the ladder (story -> arch -> contract? -> slice -> fleet -> before-pr -> review -> pentest? -> pr -> deploy? -> canary?)."
triggers:
  - story
  - user story
  - what are we building
  - scope this
  - acceptance criteria
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Grep
  - Glob
  - AskUserQuestion
---

# /story — the ask, before the design

Stage 1 of 11. `/story` decides *what* and *for whom*. `/arch` decides *how*.
Running `/arch` first is how you get an elegant design for the wrong problem.

**Read `$ENG_BRAIN/CONVENTIONS.md` first.**

## The one inviolable rule

`/story` does not design and does not write code. If you find yourself naming a
table, a module, or a library, you have left this stage. Stop and record it as an
open question for `/arch`.

## When to invoke

At the start, when the ask arrives as a sentence rather than a spec: "we want
feature flags", "coaches can't remember their clients", "make search better".
Skip it only when the ask is already a written ticket with acceptance criteria —
and then transcribe that ticket into STORY.md anyway.

Bug fixes skip this stage. A bug already has its acceptance criterion: it stops
happening.

## Phase 0 — Preamble and preflight

Preamble from CONVENTIONS.md §7, then:

```bash
FEATURE_SLUG=<kebab-case from the ask>
REPO_ROOT=$(git rev-parse --show-toplevel)
ARCH_DIR="$REPO_ROOT/docs/arch/$FEATURE_SLUG"
mkdir -p "$ARCH_DIR"
```

## Phase 1 — Ask the brain what it already knows

Before asking the user anything, ask gbrain. Half of "new" features are a
re-litigation of something already settled.

```
mcp__gbrain__recall              "<the ask, verbatim>"
mcp__gbrain__find_contradictions "<the ask>"
```

If the brain returns a prior decision that conflicts with the ask, record it in
STORY.md under **Prior decisions that constrain this** and say so out loud. Do
not silently design around it.

## Phase 2 — The four questions

Answer all four in writing. If the ask does not answer one, use AskUserQuestion —
do not guess. A guessed user is the most expensive error in this pipeline,
because every later stage inherits it.

1. **Who** is the user? Name a role, not "the user". A coach with 40 clients is a
   different person from a coach with 3.
2. **What job** are they trying to finish? State it as something they do, not as
   something the software has.
3. **What do they do today instead?** Every real feature replaces a workaround.
   If there is no workaround, question whether the need is real.
4. **What is observably different** when this works? Something a person could
   watch happen, or a number that moves.

## Phase 3 — Acceptance criteria, as checks

Each criterion is one row. A criterion with no check is a wish, and it is
rejected here rather than at `/qa`.

| # | Given / when / then | How it is proven |
|---|---|---|
| A1 | Given a coach with 40 clients, when they open one, then the last three sessions render | `pnpm test coach-context.spec.ts` |
| A2 | Given no prior sessions, when they open a client, then an empty state appears, not a spinner | `pnpm test coach-context.spec.ts -t empty` |

Rules:
- Every criterion names a command, a manual step, or a metric with a threshold.
- "It works" and "it's fast" are rejected. "p95 under 400ms, measured by X" passes.
- Include at least one **negative** criterion: what must NOT happen. Agents
  optimise the positive path and quietly break the negative one.

## Phase 4 — Out of scope, in writing

List what this feature is explicitly not doing. This section is what protects the
work from an agent — and from you — expanding it during `/fleet`.

## Phase 5 — Write STORY.md and gate

Write `$ARCH_DIR/STORY.md`:

```markdown
# <Feature> — story

## User and job
<role>, trying to <job>. Today they <workaround>.

## Observable outcome
<what is different, watchable or measurable>

## Acceptance criteria
| # | Given / when / then | How it is proven |

## Explicitly out of scope
- ...

## Prior decisions that constrain this
- [[analysis/adr-007-<topic>]] — <what it constrains> — or "none found"

## Open questions for /arch
- ...
```

**Gate — all must hold before `/arch` may run:**

- [ ] Every acceptance criterion has a proof command or a measured threshold
- [ ] At least one negative criterion exists
- [ ] The out-of-scope list is non-empty
- [ ] No table, module, library, or file name appears anywhere in STORY.md
- [ ] gbrain was queried and the result recorded, even if empty

Then **stop**. Print the story and the gate result, and hand back for review. Do
not chain into `/arch`.

## Phase 6 — Write back to the brain

Write it with the local CLI, from the file you just wrote:

```bash
python3 -c 'import json,sys; print(json.dumps({
  "slug": sys.argv[1], "type": "note", "title": sys.argv[2],
  "source": "default", "content": open(sys.argv[3]).read()}))' \
  "story-$FEATURE_SLUG" "<Feature> story" "$ARCH_DIR/STORY.md" \
| xargs -0 gbrain call put_page
```

Four things about that, none of them optional:

- **`source: "default"`.** The write falls back to matching the current directory against
  registered code sources before it reaches `default`, so running this inside a repo that
  is a registered gbrain source files the page into that *code* source — while every other
  command resolves slugs against `default`. Both halves then report success and the page
  is unreachable.
- **Not `mcp__gbrain__put_page`.** The MCP tool returns `auto_links: {"skipped":"remote"}`.
  Remote callers get no wikilink extraction, so a page written that way is an orphan
  whatever its body says.
- **`call put_page`, not `capture`.** Both extract wikilinks locally, but `capture` stamps
  `captured_at` and `captured_via` into the frontmatter and rewrites `source_uri` to a path
  that will not survive the session. `put_page` preserves what you wrote, and it is the only
  one that reports how many edges it made.
- **The `[[wikilinks]]` in the body are the edges.** This is why Phase 1's prior decisions
  get written as `[[analysis/adr-007-<topic>]]` rather than as prose. Those pages already
  exist, so each one becomes a real edge at no cost and with no second call that can fail
  on its own.

`/story` runs before anything else exists, so it must **not** wikilink forward to
`projects/<feature-slug>`. A wikilink only resolves against a page that exists at write
time; a forward reference is discarded silently, exit 0, and it does not even appear in
`unresolved` — the write reports `auto_links: {created: 0, removed: 0, errors: 0,
unresolved: []}` and nothing anywhere says a link was thrown away. Writing one is not a
harmless no-op, it is an edge you will believe you have. `/arch` closes the loop from its
side by wikilinking `[[story-<feature-slug>]]` in ARCHITECTURE.md, which resolves because
this page exists by then.

If Phase 1 found no priors, this page has no outgoing edges and that is honest — it is a
genuinely new ask. Say so in the gate rather than inventing a link.

Verify. Read `auto_links.created` off the write itself, then confirm from the other side —
in two commands, because `graph-query` on its own is fail-open. A typo'd slug, a page filed
into the wrong source, and a page that genuinely has no edges all print
`No edges found from <slug>.` and all exit 0. `gbrain get` is what tells them apart:

```bash
gbrain get "story-$FEATURE_SLUG" >/dev/null   # exit 1 + page_not_found = wrong slug or wrong source
gbrain graph-query "story-$FEATURE_SLUG" --direction out --depth 1
```

`get` exit 0 with `No edges found` means the page is really there and really has no edges —
which for a no-priors story is the correct result, not a failure.

## Failure modes

| Smell | What it means | Do this |
|---|---|---|
| "The user", no role | Nobody has thought about who | AskUserQuestion, do not proceed |
| All criteria positive | The agent will break the negative path | Add a must-not-happen row |
| Empty out-of-scope | Scope will expand during `/fleet` | Name three things you are not doing |
| A file name appears | You have started designing | Move it to open questions |
| No workaround exists today | The need may be imagined | Say so out loud before building |
