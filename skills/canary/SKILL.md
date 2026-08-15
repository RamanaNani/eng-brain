---
name: canary
version: 2.0.0
description: "Stage 11, optional. Records a pre-change baseline and compares the post-change delta, so 'it works' becomes a measured claim. Run --baseline BEFORE the change lands and again after to get the delta. Refuses to report a delta with no baseline."
triggers:
  - "canary"
  - "baseline"
  - "did it regress"
  - "measure the change"
allowed-tools:
  - Bash
  - Read
  - Write
  - Glob
  - Grep
---

# /canary — measured, not asserted

Stage 11 of the ladder (see `skills/sdlc/SKILL.md`), optional but recorded. Position:
`deploy → **canary**`.

Optional means "may be skipped with a reason", not "may be ignored". If a feature has no
production traffic to canary, skip it explicitly:

```bash
python3 "$ENG_BRAIN/lib/bin/state.py" skip "$ARCH_DIR" --stage canary --why "no prod traffic yet"
```

Read `lib/CONVENTIONS.md` first.

## The ordering problem

A baseline taken *after* the change is not a baseline. This is the single failure mode
this skill exists to prevent, and it is easy to hit because the natural time to think
about measurement is after shipping.

```
/canary --baseline      # BEFORE the change is live. Writes CANARY.baseline.json
   … change lands …
/canary                 # AFTER. Reads the baseline, writes CANARY.md with the delta
```

Running `/canary` with no `CANARY.baseline.json` is an error, not a prompt to invent one.
Say so and stop — a fabricated baseline makes every later number meaningless.

## Phase 0 — Preamble

`lib/CONVENTIONS.md` §7, then confirm what "regression" means for this feature. Pull it
from `STORY.md`'s acceptance criteria rather than choosing metrics here; metrics chosen
after the fact tend to be the ones that look good.

## Phase 1 — `--baseline`

Record, with provenance for each number:

```json
{
  "schema": "eng-brain.canary/v1",
  "feature": "<slug>",
  "taken_at": "<iso8601>",
  "git_sha": "<sha at time of measurement>",
  "metrics": {
    "p95_latency_ms": {"value": 244.6, "how": "gbrain doctor --fast, 3 runs, median"},
    "error_rate":     {"value": 0.0,   "how": "logs, 1h window"}
  }
}
```

`how` is mandatory. A number without its method cannot be reproduced, and an
irreproducible baseline is not evidence.

## Phase 2 — delta

Re-measure **the same way** — same command, same window, same run count. Then:

```markdown
# Canary — <feature-slug>

| Metric | Baseline | Now | Delta | Verdict |
|---|---|---|---|---|
| p95_latency_ms | 244.6 | 251.2 | +2.7% | within noise |
| error_rate | 0.0 | 0.0 | — | ok |

- **Baseline sha:** <sha>   **Current sha:** <sha>
- **Verdict:** NON-REGRESSIVE | REGRESSION | INCONCLUSIVE
```

`INCONCLUSIVE` is a real and often correct verdict. Three runs cannot separate a 2% change
from noise; say so rather than picking a direction. Declaring "no regression" from
underpowered measurement is the failure this stage is meant to catch, not commit.

## Phase 3 — Record

```bash
python3 "$ENG_BRAIN/lib/bin/state.py" pass "$ARCH_DIR" --stage canary --artifact CANARY.md
```

Capture to the brain per `CONVENTIONS.md` §5 and add a timeline entry — canary results are
exactly the kind of thing the next `/arch` should inherit:

```bash
gbrain timeline-add projects/"$FEATURE_SLUG" "$(date +%F)" "Canary: <verdict>, p95 <n>ms"
```

## Never

- Never take the baseline after the change.
- Never compare measurements taken by different methods.
- Never report NON-REGRESSIVE when the measurement cannot support it — use INCONCLUSIVE.
