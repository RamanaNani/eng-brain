# ADR-100 — Claude Code setup: layers, recovery, and the traps

- **Date:** 2026-08-15
- **Status:** Accepted
- **Context:** `~/.claude/skills/` was lost during a restart after an API error. It was
  rebuilt the same day. This records how, so the next loss is a ten-minute job.

## Decision

Treat the Claude Code environment as **three independent layers**, not one directory.
Which layer a skill belongs to determines how it is restored, and conflating them is what
made the first recovery attempt slow.

| Layer | Lives in | Restore by | Count |
|---|---|---|---|
| gbrain bundle | `~/.bun/install/global/node_modules/gbrain/skills/` | copy into `~/.claude/skills/` | 53 |
| Hand-authored pipeline | **nowhere on disk** — only in brain transcripts | mine tool-call payloads (below) | 13 |
| Marketplace plugins | `~/.claude/plugins/cache/` | `claude plugin marketplace add` + `install` | 26 |

### Layer 1 — gbrain bundle

Hash-verified against `skills.lock.json`; `gbrain doctor` reports
`skills_manifest_integrity` over 128 bundled files. **There is no gbrain command that
projects these into `~/.claude/skills/`** — the original copy was manual, so re-copy on
every reinstall. `gbrain integrations install` is unrelated (it manages Gmail/Calendar/X
data sources) and is the wrong verb to reach for.

### Layer 2 — hand-authored pipeline

`story`, `change`, `arch`, `contract`, `slice`, `fleet`, `pr`, `brain-sync`, `_eng-brain`
(shared lib: `bin/{gate,owns,concepts,tractable}.py`, `setup.sh`, `CONVENTIONS.md`,
`GREENFIELD.md`, `BROWNFIELD.md`), `gstack` (`qa`, `review`, `gstack-upgrade`),
`pentest`, `grill-me`, `update-superbase`.

These exist in no package and no backup. They are recoverable **verbatim** only because
gbrain syncs transcripts into the brain and those pages embed complete Write/Edit
tool-call payloads. See "Recovery procedure".

### Layer 3 — marketplace plugins

| Marketplace | Source repo |
|---|---|
| `ecc` | `affaan-m/ECC` |
| `ruflo` | `ruvnet/ruflo` |
| `voltagent-subagents` | `VoltAgent/awesome-claude-code-subagents` |
| `agent-router` | `RamanaNani/agent-router` |
| `thedotmack` | `thedotmack/claude-mem` |
| `claude-code-workflows` | `wshobson/agents` |
| `claude-plugins-official` | `anthropics/claude-plugins-official` |

`pentest` tracks a separate upstream: `usestrix/strix`.

**These are recorded in `~/.claude/settings.json` under `extraKnownMarketplaces` and
`enabledPlugins`.** Check there first — it is the cheap path, and it survived the loss.

## Traps

1. **`ecc`, `gstack`, and `voltagent` are marketplace names, not npm packages.** The npm
   packages under those names are unrelated projects — `ecc` is an elliptic-curve crypto
   library (`siddMahen/ecc.js`), `gstack` is "Global Stack Package". Installing them is a
   supply-chain mistake dressed as a restore. `ruflo` is the sole exception: the npm CLI
   is genuine and `ELN/.claude/proven-config.json` pins `ruflo >=3.24.0`.

2. **`GBRAIN_PREPARE=true` must be exported.** The engine is Postgres behind a PgBouncer
   transaction pooler, which rejects session-level prepared statements. Its absence
   produces an *empty result set rather than an error* — so an unexpectedly thin `search`
   is a suspected connection fault, not proof the brain is thin. Restored to
   `~/.claude/settings.json` under `env`.

3. **The brain is not reachable from the Supabase MCP.** It lives in project
   `duatdzhcnybzcbldcgrt`; the connected MCP only exposes `notes9`
   (`rutcjpugsrfoobsrufnn`) and `practice`. Query it with Bun's native client using
   `database_url` from `~/.gbrain/config.json`.

4. **`pages` has no `content` column.** Body text is in `content_chunks.chunk_text`,
   joined on `content_chunks.page_id = pages.id`. `gbrain list` also caps near 50 rows
   regardless of `-n`; paginate or go straight to SQL.

## Recovery procedure (layer 2)

```sql
select distinct page_id from content_chunks
where chunk_text like '%skills/%'
  and (chunk_text like '%file_path%' or chunk_text like '%filePath%');
```

Reassemble each page from its chunks in `chunk_index` order, then scan for JSON objects
carrying `file_path` + `content` with a string-aware brace matcher, retrying at each
unescape depth. Three failure modes, in descending order of nastiness:

1. **`content_chunks` OVERLAP — strip the seam.** Chunking is a sliding window;
   consecutive chunks share **180–500 bytes**. Naive concatenation duplicates that
   region, which splices a payload into itself and silently produces a file that is
   plausible but does not parse. Measured on this brain: 3877 seams, **1.3 MB** of
   duplicated bytes. At each join, find the longest suffix of the accumulated text that
   is a prefix of the next chunk and drop it:

   ```ts
   let ov = 0;
   for (let k = Math.min(out.length, cur.length, 6000); k > 16; k--) {
     if (out.endsWith(cur.slice(0, k))) { ov = k; break; }
   }
   out += cur.slice(ov);
   ```

2. **Rejoin with `""`, never `"\n"`.** A newline inside a JSON string literal invalidates
   it and every parse fails.

3. **When peeling escape layers, unescape only `\"` and `\\` — never `\n`.** Converting
   `\n` to a real newline breaks the inner literals the same way.

**Select one coherent version per path — never merge bytes across write events.** A
longest-wins merge across two extraction passes produced files that spliced two versions
together: all four `lib/bin/*.py` scripts failed `ast.parse`, with `gate.py` carrying a
duplicated `_PASS_COUNTS` block and a comment truncated mid-sentence. Correct approach:
keep every candidate payload intact, rank newest-then-longest, and take the first that
passes a structural check for its type (`ast.parse` for `.py`, `json.loads` for `.json`,
frontmatter + balanced fences for `SKILL.md`).

With overlap stripping and per-version selection, 29 of 31 files recover clean and all
four Python scripts parse. The 2 that don't are `gstack/{qa,review}/SKILL.md`, which
genuinely have no frontmatter — a false positive from the check, not damage.

## Consequences

- Layer 2 is the fragile one and the only layer with no second copy. Its durability is
  entirely a function of transcript sync staying on.
- Recovery is bounded by what was captured. Skills authored before sync was enabled are
  unrecoverable — confirmed for `canary`, `before-pr`, and `impeccable`, which are
  discussed in the brain but have no Write payload.
- Two of the original nine marketplaces remain unidentified: `ponytail`, and one whose
  name began "marketi…".

## Open

- Give layer 2 a real home (a git repo) so it stops depending on transcript archaeology.
- gbrain upgrade 0.42.74.0 → 0.45.18.0 is pending, deliberately deferred during recovery.
- `~/.gbrain/config.json` stores the Postgres password in plaintext.
