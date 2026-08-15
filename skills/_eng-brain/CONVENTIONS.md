# Engineering Brain Conventions

Shared contract for `/arch`, `/slice`, `/fleet`. Read this before any brain read or write.

Everything here is verified against gbrain 0.42.74 on the postgres/Supabase engine.
Do not invent verbs. If a command is not listed here, run `gbrain <cmd> --help` first.

## 1. The loop

```
capture ──► /arch ──► /slice ──► /fleet ──► PR ──► you accept ──► write-back
   ▲                                                                   │
   └───────────────── brain carries decisions forward ─────────────────┘
```

Each stage reads the brain before deciding and writes to the brain after deciding.
A stage that does neither is a bug.

## 2. Page types

The active pack is `gbrain-base-v2` (15 types). It has **no** `decision` or
`architecture` type, and we are **not** forking it yet — upstream guidance is that
under ~20 pages should not be pack-codified. Map onto existing types instead:

| What | Type | Slug | Extractable |
|---|---|---|---|
| Architecture for a feature | `project` | `projects/<feature-slug>` | no |
| One architectural decision (ADR) | `analysis` | `analysis/adr-<nnn>-<topic>` | **yes** |
| Shipped-slice outcome | timeline entry on the `project` page | — | — |

ADRs are `analysis` deliberately: that type is `extractable: true`, so `dream`'s
`extract_facts` mines them into facts and, downstream, into takes. `project` is not
extractable, which is fine — the architecture page is an index, the ADRs carry the claims.

**When you cross ~100 ADRs**, fork the pack and promote `decision` to a first-class type:
`gbrain schema fork my-eng-pack && gbrain schema add-type decision --extractable`.
Not before. Type proliferation is the failure mode the v2 pack exists to fix.

Tag every page this system writes: `gbrain tag <slug> eng-brain` plus one of
`architecture` / `adr` / `slice-outcome`. Tags are add-only on reconcile as of v0.41.37,
so enrichment tags survive a re-chunk.

## 3. Link types

Arbitrary `--link-type` values are accepted (verified: a custom `supersedes` edge
persisted and traversed via `graph-query`). Use exactly these six, no synonyms —
consistency is what makes the graph queryable:

| Edge | Meaning |
|---|---|
| `decided_by` | architecture → ADR that settled a question in it |
| `supersedes` | new ADR → the ADR it replaces |
| `constrains` | ADR → architecture it limits (often cross-project) |
| `implements` | slice/PR → the architecture it builds |
| `depends_on` | slice → slice it must follow |
| `informed_by` | architecture → prior page that shaped it |

Direction matters. `A --supersedes-> B` means A is the new one. Always write the edge
from the new page to the old page, never the reverse.

## 4. Read protocol — priors before design

Never design without querying priors first. This is the whole point of the system.

```bash
# 1. Multi-hop synthesis across pages + takes + graph, with conflict + gap analysis.
#    This is the primary recall verb — not `search`, not `query`.
gbrain think "<the design question>. What have I decided about this before, and why?"

# 2. Hybrid retrieval (vector + tsvector + RRF) for the raw supporting pages.
gbrain query "<feature area> architecture decisions" --no-expand

# 3. What the code actually is today (only if the repo is synced as a code source).
gbrain code-def <Symbol>
gbrain code-refs <Symbol>
gbrain code-callers <Symbol>

# 4. Prior ADRs as a graph, not a list.
gbrain graph-query projects/<related-feature> --direction out --depth 2
```

Also call the MCP tools `takes_search` and `find_contradictions` — they have no thin CLI
equivalent. `takes` are your graded past opinions; `find_contradictions` surfaces where a
new decision fights an old one. **Surface contradictions to the user explicitly. Never
silently overwrite a prior decision.**

If `gbrain think` returns a gap ("the brain doesn't know X"), say so out loud rather than
filling the gap with a confident guess. Gap analysis is a feature; suppressing it is not.

## 5. Write protocol

Write to the repo first (the agent-readable artifact), then the brain (the memory).

```bash
# 1. Repo — this is what /slice and worktree agents actually read.
docs/arch/<feature-slug>/ARCHITECTURE.md
docs/arch/<feature-slug>/ADR-001-<topic>.md
docs/arch/<feature-slug>/slices/NN-<name>.md
docs/arch/<feature-slug>/slices.json

# 2. Brain — this is what the NEXT /arch inherits.
#    NOTE: no --source. Eng-brain pages go to the DEFAULT source deliberately (see below).
gbrain capture --file docs/arch/<slug>/ARCHITECTURE.md \
  --slug projects/<slug> --type project --quiet
gbrain capture --file docs/arch/<slug>/ADR-001-<topic>.md \
  --slug analysis/adr-001-<topic> --type analysis --quiet

# 3. Edges — a page with no edges is an orphan, and orphans are invisible to `think`.
gbrain link projects/<slug> analysis/adr-001-<topic> --link-type decided_by
gbrain link analysis/adr-001-<topic> analysis/adr-<old> --link-type supersedes

# 4. Timeline — this is what makes trajectory and drift work.
gbrain timeline-add projects/<slug> $(date +%F) "Architecture accepted; N slices planned"

# 5. Tags
gbrain tag projects/<slug> eng-brain && gbrain tag projects/<slug> architecture
```

### Why the default source, not the repo's source

**Verified constraint (gbrain 0.42.74):** `capture` and `timeline-add` accept `--source`,
but **`tag` and `link` do not** — they resolve slugs against the default source only.
Capturing to `notes9` and then tagging produces
`page "projects/x" (source=default) not found`, and you end up with an untagged,
unlinked orphan.

So eng-brain pages go to the **default source**, and that is the right call anyway:
architecture decisions are cross-project knowledge. An ADR you wrote building Notes9
should surface when you design something unrelated eighteen months later. Keeping one
decision corpus is what makes `gbrain think` compound across projects instead of
siloing per repo.

The split is therefore:

| Lives in | What | Why |
|---|---|---|
| The repo (`docs/arch/**`) | ARCHITECTURE.md, ADRs, slice briefs | Worktree agents read these; they version with the code |
| Brain `default` source | `projects/<slug>`, `analysis/adr-*` | Cross-project decision memory |

`SOURCE_ID` from §7 is still worth resolving — use it for `gbrain sync` and for code
queries (`code-def`, `code-refs`) scoped to this repo. Just do not pass it to `capture`
for eng-brain pages.

**Every written page must get at least one edge in the same run.** The brain currently
has 540 orphan pages out of 542 and `link_count: 0` — that is precisely why recall is
weak today. Do not add to that pile.

## 6. Never

- Never merge a PR. `/pr` opens PRs and stops. A human accepts. No exceptions,
  no `--auto-merge`, no "the gate passed so I merged it".
- Never let two slices own the same file. `/slice` validates this; if the check fails,
  re-slice — do not "just be careful".
- Never write a brain page without an edge (§5).
- Never `gbrain sources remove` or `sources purge` from inside these skills.
- Never claim tests pass without showing the runner output.

## 7. Run preamble

Every skill runs this first and reuses the values:

```bash
set -o pipefail
REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null) || { echo "not a git repo"; exit 1; }
SOURCE_BRANCH=$(git branch --show-current)          # the PR target. Record it.

# FEATURE_SLUG is supplied by the CALLING SKILL, never by this block. `/arch` coins it
# kebab-case from the ask (`FEATURE_SLUG=offline-sync`); `/slice`, `/fleet` and `/pr` reuse
# the one already on the arch dir they found. Unset is not harmless: `ARCH_DIR` collapses to
# "$REPO_ROOT/docs/arch/" and every §5 file lands loose in that directory, mixed in with
# other features' arch dirs. Fail closed rather than write to the wrong path.
[ -n "${FEATURE_SLUG:-}" ] || { echo "FEATURE_SLUG unset — the calling skill sets it before this block"; exit 1; }
ARCH_DIR="$REPO_ROOT/docs/arch/$FEATURE_SLUG"

# gbrain env — MUST come before the first gbrain call of the run.
# PATH: gbrain lives in ~/.bun/bin, which is not on a non-login agent shell's PATH. Without
#   this the CLI is simply "not found" and every check below reports a dead brain.
# GBRAIN_PREPARE: the engine is Postgres behind a PgBouncer transaction pooler, which does
#   not support session-level prepared statements. This is set in ~/.claude/settings.json
#   for a reason; export it here too, because a subshell or a differently-launched agent
#   may not inherit it. The failure mode it guards against is the dangerous kind — an
#   empty result set rather than an error — so treat an unexpectedly empty `search` as a
#   possible connection problem, not as proof the brain is thin. Verify with setup.sh,
#   which checks that a known-good query actually returns rows.
# GBRAIN_SOURCE: THE source pin for the whole run. Export it here, once, before the first
#   gbrain call — do not pin it inline on individual commands. Source resolution falls back
#   to matching the working directory against a registered code source's `local_path`, and
#   CLAUDE.md mandates running this pipeline from the repo root, which for this user IS a
#   registered code source (`~/code/acme-app`). So every unpinned gbrain call in the
#   session silently resolves against the code source instead of `default`, where eng-brain
#   pages live. Pinning only the write helper is not enough: the write lands correctly and
#   then every *verification* command reads the wrong source and reports clean.
#   Verified from inside ~/code/acme-app on 0.42.74.0, on a page with a real edge:
#     unset  → gbrain call get_links '{"slug":"test-round3/conv-proj"}'  → []   rc=0
#     export → same command                                             → 2 rows, rc=0
#   The read verbs fail SILENTLY like that. The mutating ones fail loudly and name the
#   source they resolved, which is how this was finally caught:
#     addTag failed: page "test-round3/conv-proj" (source=acme-app-code-1a2b3c4d) not found
export PATH="$HOME/.bun/bin:$PATH"
export GBRAIN_PREPARE=true
export GBRAIN_SOURCE=default

# ENG_BRAIN — where the gate scripts live. Every stage skill invokes
#   "$ENG_BRAIN/bin/state.py". Nothing else sets it, and an unset variable
#   expands to "" — so the command silently becomes "python3 /bin/state.py",
#   the gate DOES NOT RUN, and the stage reports success. That is the exact
#   failure class this pipeline exists to prevent, so it fails closed below.
#   Two install channels, two locations: plugin installs live under
#   $CLAUDE_PLUGIN_ROOT, clone installs under ~/.claude/skills.
if [ -z "${ENG_BRAIN:-}" ]; then
  if [ -n "${CLAUDE_PLUGIN_ROOT:-}" ] && [ -d "$CLAUDE_PLUGIN_ROOT/skills/_eng-brain" ]; then
    ENG_BRAIN="$CLAUDE_PLUGIN_ROOT/skills/_eng-brain"
  else
    ENG_BRAIN="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}/_eng-brain"
  fi
fi
export ENG_BRAIN
if [ ! -f "$ENG_BRAIN/bin/state.py" ]; then
  echo "eng-brain: gate scripts unreachable at $ENG_BRAIN — refusing to continue" >&2
  exit 1
fi

# Is gbrain reachable AT ALL? This must be answered before anything else, because a dead
# CLI and an empty brain produce identical output downstream, and §8 below trains you to
# read emptiness as normal. Never let those two states look the same to the user.
if ! GBRAIN_ERR=$(gbrain whoami 2>&1 >/dev/null); then
  echo "BRAIN DOWN — gbrain is not reachable. This is NOT 'thin recall'."
  echo "$GBRAIN_ERR"
  echo "Every prior-decision lookup and every write-back below will be skipped."
  echo "Fix it or proceed explicitly without the brain. Do not report a 'gap'."
  BRAIN_UP=0
else
  BRAIN_UP=1
fi

# Which gbrain source is this repo? Match on local_path.
SOURCE_ID=$([ "$BRAIN_UP" = 1 ] && gbrain sources list --json 2>/dev/null | python3 -c "
import sys,json,os
r=json.load(sys.stdin); s=r.get('sources',r) if isinstance(r,dict) else r
p=os.path.realpath('$REPO_ROOT')
print(next((x['id'] for x in s if x.get('local_path') and os.path.realpath(x['local_path'])==p),''))
" 2>/dev/null)
# `if`, NOT `[ -z "$SOURCE_ID" ] && echo …`. A trailing `test && cmd` is the last statement
# in this block, so when the repo IS registered the test is false and the whole preamble
# returns 1 — non-zero exactly when everything succeeded. Measured on the old form from
# ~/code/acme-app (registered) and from a throwaway git repo (not registered):
#   registered    -> rc=1, and silent, because the WARN branch never fired
#   NOT registered-> rc=0, with the warning printed
# Precisely inverted. An `if` whose condition is false returns 0, which is why this form is
# correct in both states.
if [ -z "$SOURCE_ID" ]; then
  echo "WARN: repo not registered as a gbrain source. Register with: gbrain sources add <id> --path $REPO_ROOT"
fi
```

**This block exits 0 in both states, deliberately.** An unregistered repo is a warning, not
a failure: eng-brain pages go to `default` either way (§5), and only `code-def` / `code-refs`
go blind. So never branch a skill on this block's exit status to decide whether the repo is
registered — read `$SOURCE_ID` itself. The exit status only distinguishes "the preamble ran"
from "it bailed on `not a git repo` or an unset `FEATURE_SLUG`".

If `SOURCE_ID` is empty, tell the user and offer `gbrain sources add` — do not silently
write into `default`.

### What the `GBRAIN_SOURCE=default` export does and does not change

Measured from `~/code/acme-app`, with and without the export:

| Verb | Effect of the export | Note |
|---|---|---|
| `call put_page`, `call get_links`, `call get_backlinks`, `backlinks`, `get`, `graph-query`, `tag`, `link`, `timeline-add` | **Fixes them** — they resolve against `default` instead of the repo's code source | This is the point |
| `code-def`, `code-refs`, `code-callers` | **No effect** — `code-def createClient` returned `count=2` unpinned, exported, and with an explicit `--source` | The code index is searched across sources; the export is safe here |
| `sources list`, `whoami` | No effect | |
| `query` | **Narrows it** — 2076 bytes of hits unpinned vs 631 exported, because code-source hits drop out | Intended for §4 step 2 (decisions live in `default`), but know that it happens |
| `think` | No meaningful change (1691 vs 1580 bytes, both real cited syntheses) | Generative; byte counts differ run to run anyway |

So the export is correct for the decision corpus and harmless to code lookups. If you
deliberately want `query` to span code pages too, run that one call in a subshell with
`env -u GBRAIN_SOURCE gbrain query …` rather than unsetting it for the rest of the run.

## 8. Known state of this brain (2026-08-13)

Read this before trusting recall. Verified by running the calls, not assumed:

```
Pages: 4220   Chunks: 23312   Embedded: 13480
Links: 63     Tags: 51        Timeline: 12
By type: transcript 3086, code 1053, note 57, analysis 15, project 6, concept 3
health: embed coverage 57.8%, missing embeddings 9832, stale pages 4164,
        orphan pages 4197, link coverage 0.0%, timeline coverage 0.0%, health score 4/10
```

Those figures are **one example brain at one moment** — the author's, dominated by
transcript capture. Yours will look nothing like them, and that is fine; what generalises
is the table below, not the numbers.

**Re-measure rather than trust this block.** It is a snapshot, and it goes stale fast:
`page_count` moved 4075 → 4190 → 4220 across three sessions, because transcript capture
runs continuously. A previous version of §8 quoted `542 pages / link_count 0` long after
those were wrong, and skills kept reciting it. One command refreshes everything above:

```bash
gbrain health && gbrain stats
```

**`gbrain stats --json` does not return JSON.** The flag is accepted and ignored; you get
the same plain-text table, so anything piping it into a parser gets an exception or, worse,
a silent empty parse. Verified — the first bytes are `Pages:     4220\nChunks: …`, and
`json.loads` on it raises. Parse the text or use `gbrain call get_stats '{}'`.

Quote a number to the user only if you just ran that. Otherwise describe the shape
("mostly transcripts, very few edges"), which stays true, instead of a figure that does not.

**Which of these are expected to move, and which mean something is broken:**

| Figure | Reading |
|---|---|
| `link_count`, `timeline_entry_count`, `tag_count` | **Expected to climb** — every `/arch` adds edges via §5. Flat across a run that wrote pages = §5 is not working. That is the defect this protocol exists to prevent. |
| `page_count`, `transcript` count | **Expected to climb on its own**, continuously, from session capture. Not a health signal. It drifts within a single day — these numbers were already stale hours after being taken. |
| `orphan_pages` | **Expected to climb in absolute terms** while transcript capture runs, since transcripts arrive unlinked. Judge the *pipeline* by whether `projects/*` and `analysis/*` pages are orphans, never by this total. |
| `embed coverage` / `missing_embeddings` | **A backlog, not a defect** — embeddings are produced by a local Ollama model. Falling coverage while page count climbs is normal. Zero movement over days means the embedding worker is stuck. |
| `link coverage 0.0%` / `timeline coverage 0.0%` | **A defect indicator.** These are ratios over entity pages. They stay pinned at 0 while the handful of real edges is swamped by ~3000 unlinked transcripts, so treat them as unreliable at this corpus ratio and check specific slugs with `gbrain call get_links '{"slug":"…"}'` instead. |
| `dead_links` / `no_dead_links_score` | **Fail-open after any page deletion — do not trust a 0.** It does not count links whose endpoint has been soft-deleted. Verified: with a live edge `conv-proj → conv-adr`, deleting `conv-adr` left `gbrain get` on it at rc=1 while `get_health` still reported `dead_links: 0`, `no_dead_links_score: 10`. `gbrain delete` is a soft delete (`recoverable_until: now + 72h via restore_page`), so *every* deletion produces exactly this blind spot. A perfect dead-link score means "no hard-deleted endpoints", never "every edge resolves". To actually check, read the edges and resolve each `to_slug` with `gbrain get`. |
| `health score 4/10` | Dominated by the transcript bulk. Not a useful pipeline signal; do not chase it. |

- `gbrain extract all --source db --dry-run` is effectively a no-op over the transcript
  bulk: that corpus has no wikilink syntax, so there is nothing to extract. **Do not run it
  to find out** — it does not return within 45s on this corpus (verified: killed at the
  timeout, no output), so a skill that shells out to it will hang rather than report. The
  graph must be *built forward* by the write protocol in §5. This is why §5 puts wikilinks
  in the body at write time — it is the only moment the syntax exists.
- The `default` source (the bulk of the brain) has `local_path: null`. Because gbrain has no on-disk
  checkout for it, `dream` skips its filesystem phases (`lint`, `backlinks`, `sync`,
  `synthesize`, `extract`, `patterns`).
- **No LLM API key is configured, but generation still works.** `~/.gbrain/config.json`
  sets only `embedding_model: ollama:nomic-embed-text` — no generation key, verified by
  reading the config for key *names* only. Generation nonetheless runs: `gbrain think`
  returns a real cited synthesis, and announces its route on stderr as
  `tier.subagent resolved to "claude-cli:claude-sonnet-4-6" via "models.default"`. gbrain
  falls back to the **local Claude Code CLI** as its provider. An earlier version of this
  section said `think` was dark; it is not. Do not tell the user recall is unavailable —
  run it.
- **`takes` is nevertheless empty** (`gbrain call takes_list '{}'` → `[]`, verified), and
  `calibration_profile` needs ≥5 resolved takes. So takes-based recall returns nothing
  today while `think` itself works. Report those two separately: an empty `takes_list` is
  not evidence that the brain is unreachable or that generation is unconfigured.
  Everything in §5 is independent of all of this — wikilink extraction is plain markdown
  parsing and costs nothing.

Consequence: **`gbrain think` is weak today and gets stronger with every `/arch` you run.**
Say this plainly to the user rather than presenting thin recall as complete recall.

**Distinguish empty from broken before applying any of the above.** Everything in this
section describes a brain that is reachable and genuinely sparse. A `gbrain` call that is
unreachable, errors, or times out must NEVER be reported as a gap, a thin brain, or
"nothing found" — this section would otherwise train you to narrate a total outage as
normal, which is the easiest way for the whole pipeline to look healthy while remembering
nothing. Capture stderr and branch on the exit code instead of discarding it:

```bash
OUT=$(gbrain think "<question>" 2>/tmp/gbrain.err); rc=$?
if [ $rc -ne 0 ]; then
  echo "BRAIN CALL FAILED (rc=$rc) — this is NOT a gap:"; cat /tmp/gbrain.err
elif [ -z "$OUT" ]; then
  echo "Brain reachable, nothing recorded on this yet."   # a real gap
fi
```

The same rule governs writes. A failed `capture`, `link`, `timeline-add` or `tag` must be
surfaced, never swallowed: a silently failed write-back means the next `/arch` inherits
nothing and nobody ever finds out.
The two unblockers are an on-disk brain source and an API key for gbrain; see
`_eng-brain/setup.sh`.
