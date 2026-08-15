---
name: before-pr
version: 2.0.0
description: "Stage 5. The last gate before PRs exist. Runs gate.py over every slice — failure-mode coverage and honest test output — and writes GATE.md. Refuses to pass on asserted test results; it wants runner output. Invoked by /sdlc after /fleet, or directly before /pr."
triggers:
  - "gate the slices"
  - "ready for PR"
  - "before pr"
  - "check before opening PRs"
allowed-tools:
  - Bash
  - Read
  - Write
  - Glob
  - Grep
---

# /before-pr — the last honest moment

Stage 5 of the ladder (see `skills/sdlc/SKILL.md`). Position: `fleet → **before-pr** → pr`.

Everything upstream of here is recoverable. Once `/pr` runs, work is visible to other
people and a bad slice costs someone else's attention. This is the last stage where being
wrong is free, so it is deliberately the least forgiving one.

Read `lib/CONVENTIONS.md` first.

## What it checks

Two things, both mechanical, both via `lib/bin/gate.py`:

1. **Failure-mode coverage** — every row in `ARCHITECTURE.md`'s `## Failure modes` table
   reaches some slice brief's `## Edge cases to test` or `## Out of scope`. A failure mode
   that reaches neither was designed and then quietly dropped.
2. **Honest test output** — the runner actually ran and was green. `gate.py testout` knows
   pytest, jest, cargo, mocha, `node --test`, `go test`, TAP, and `unittest`, and treats
   `3 failed, 5 passed` as red rather than as "5 passed".

An ADR is not a slice brief. `gate.py` reads `slices/*.md` and root-level briefs, and
deliberately does not count `ADR-*.md` — covering a failure mode in the ADR that *created*
it is circular.

## Phase 0 — Preamble

`lib/CONVENTIONS.md` §7, then:

```bash
GATE="$ENG_BRAIN/lib/bin/gate.py"
python3 "$GATE" selfcheck || { echo "gate.py is broken; fix it before trusting it"; exit 1; }
```

Self-checking first is not ceremony. `gate.py` was once recovered in a corrupted state that
still imported cleanly — a gate that is silently wrong is worse than no gate.

## Phase 1 — Failure-mode coverage

```bash
python3 "$GATE" modes "$ARCH_DIR"
```

On failure it names the exact mode and where to put it. Do not "cover" a mode by pasting
its text into a brief — either the slice genuinely tests it, or it is genuinely out of
scope with a reason. Pasting to satisfy a grep is how the gate stops meaning anything.

## Phase 2 — Test output, per slice

Every slice must have produced real runner output. Collect it, do not assert it:

```bash
for d in "$ARCH_DIR"/slices/*.md; do
  slug=$(basename "$d" .md)
  out="$ARCH_DIR/runs/$slug/test_output.txt"
  python3 "$GATE" testout "$out" || FAILED="$FAILED $slug"
done
```

If a slice has no output file, that is `NOT RUN`, and `NOT RUN` is a failure. A slice whose
agent said "tests pass" without capturing output has not been verified — re-run it.

## Phase 3 — Write GATE.md

```markdown
# Gate report — <feature-slug>
- **Date:** <YYYY-MM-DD>
- **Verdict:** PASS | FAIL

## Failure-mode coverage
<gate.py modes output, verbatim>

## Test output
| Slice | Runner | Result |
|---|---|---|
| 01-pooler | pytest | 12 passed |

## Unresolved
<anything a human must decide before /pr>
```

Verbatim means verbatim. A summary of runner output is an assertion again.

## Phase 4 — Record

```bash
python3 "$ENG_BRAIN/lib/bin/state.py" pass "$ARCH_DIR" --stage before-pr --artifact GATE.md
# or
python3 "$ENG_BRAIN/lib/bin/state.py" fail "$ARCH_DIR" --stage before-pr --why "<what failed>"
```

Then capture `GATE.md` to the brain per `CONVENTIONS.md` §5, with an edge in the same run.

## Never

- Never pass a slice on an assertion that tests pass. Show the output or mark it NOT RUN.
- Never edit a brief purely to make `modes` green.
- Never continue to `/pr` on a FAIL verdict. Report and stop.
