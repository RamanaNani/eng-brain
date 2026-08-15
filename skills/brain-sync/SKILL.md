---
name: brain-sync
version: 1.0.0
description: "Manually push everything into gbrain: ingest Claude session transcripts, sync registered code sources, embed what is stale, and report the health delta. The on-demand counterpart to the SessionEnd auto-ingest hook."
triggers:
  - update the gbrain
  - update gbrain
  - brain sync
  - push to brain
  - sync my brain
  - push everything to the db
allowed-tools:
  - Bash
  - Read
---

# /brain-sync — push everything into the brain, now

Automatic ingest already runs on `SessionEnd`. Use this when you do not want to wait:
mid-session, after a big work block, or when you suspect the brain is behind.

## Phase 0 — Baseline

Capture the before-state so the report shows a real delta, not a vibe.

```bash
gbrain health --json 2>/dev/null | python3 -c "
import sys,json; d=json.load(sys.stdin)
print(json.dumps({k:d.get(k) for k in ['page_count','brain_score','embed_coverage','link_count','orphan_pages']}))" > /tmp/brain-before.json
cat /tmp/brain-before.json
```

## Phase 1 — Ingest session transcripts

The bridge walks `~/.claude/projects/**/*.jsonl` and files the salient parts as brain
pages. `--incremental` only takes what is new since the last run.

```bash
bun ~/.claude/skills/gstack/bin/gstack-memory-ingest.ts --incremental --scan-secrets
```

**Always keep `--scan-secrets`.** Session transcripts routinely contain API keys, tokens,
and connection strings; this brain lives in Supabase, so an unscanned ingest publishes
them to a hosted database. Never drop that flag to make a run faster.

Modes, and when each is right:

| Flag | Use when |
|---|---|
| `--incremental` | **default** — new transcripts since last run |
| `--probe` | dry run, writes nothing. Use first if it has been a long time |
| `--bulk` | full backfill. ~8,600 candidates / 1.15GB here — hours. Only deliberately |
| `--limit N` | cap a run while testing |
| `--no-write` | smoke test the pipeline |

If the user says "update gbrain" with no qualifier, that means `--incremental`.
Never launch `--bulk` without saying what it costs and getting a yes.

## Phase 2 — Sync code sources

Transcripts are what you *said*; sources are what the code *is*. Both matter.

```bash
gbrain sync --all --missing-path skip
```

`--missing-path skip` classifies sources whose `local_path` is absent on this machine as
skipped rather than failed, so one unmounted repo does not fail the whole run.

## Phase 3 — Embed

New pages arrive unembedded, which makes them invisible to the vector half of hybrid
search. Close that immediately.

```bash
gbrain embed --stale
```

This is local ollama (`nomic-embed-text`), so it costs nothing but wall time.
Roughly 400 pages ≈ a few minutes.

## Phase 4 — Report the delta

```bash
gbrain health --json 2>/dev/null | python3 -c "
import sys,json
before=json.load(open('/tmp/brain-before.json')); after=json.load(sys.stdin)
for k in ['page_count','brain_score','embed_coverage','link_count','orphan_pages']:
    b,a=before.get(k),after.get(k)
    if isinstance(b,float): b,a=round(b,3),round(a,3)
    print(f'{k:18} {b} -> {a}' + ('   (unchanged)' if b==a else ''))"
```

Report honestly:

```
Brain sync complete
  pages          542 -> 561   (+19 from 3 sessions)
  embed_coverage 1.0 -> 1.0
  brain_score     45 -> 45
  link_count       0 -> 0     (unchanged — see below)
```

## What this does NOT fix

Say this plainly rather than implying a clean bill of health:

- **`link_count` will stay 0.** Ingested transcripts carry no wikilink syntax, so no edges
  are created. The graph is built forward only by `/arch` and `/fleet` write-back, never
  by ingest. Do not suggest `gbrain extract` — it is verified to yield 0 links and 0
  timeline entries on this corpus.
- **`brain_score` will barely move.** It is dominated by link and timeline coverage, both
  at 0. More pages without edges can even lower it by adding orphans.
- **`takes` stay empty** until gbrain has an LLM provider key (`ANTHROPIC_API_KEY`,
  `OPENAI_API_KEY`, or an ollama chat model). Ingest does not populate decision memory.

More pages is not the same as a better brain. The graph is what makes `gbrain think` work.

## Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Ingest hangs for hours | ran `--bulk` on 1.15GB | Ctrl-C; use `--incremental` |
| `sync` fails on one source | repo not on this machine | `--missing-path skip` |
| New pages not in search | not embedded | `gbrain embed --stale` |
| Secrets in a brain page | `--scan-secrets` omitted | `gbrain delete <slug>`, rotate the credential, re-run with the flag |
