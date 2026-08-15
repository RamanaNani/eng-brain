# ADR-101 — The ladder is data, not prose

- **Date:** 2026-08-15
- **Status:** Accepted
- **Context:** `/sdlc` needs to enforce stage order and gates across `/story` … `/canary`.

## Problem

The pipeline stages already existed and were individually good, but nothing sequenced
them. Gate enforcement had to live *somewhere*, and there were two candidates:

1. In the spine's `SKILL.md` — describe the ladder and the gates in prose, and instruct
   the model to follow it.
2. In code — a state machine that returns a non-zero exit code when the order is violated.

## Decision

**Code.** `skills/_eng-brain/bin/state.py` owns the ladder. The spine's `SKILL.md` describes *intent*
and dispatches; it does not adjudicate order.

Concretely:

- `state.py pass --stage slice` with `arch` still pending → **exit 2**, with a message
  naming the blocking stage and the exact `skip` command if it genuinely does not apply.
- `state.py skip --stage arch` → **exit 1**; mandatory stages cannot be skipped.
- Optional stages (`contract`, `pentest`, `deploy`, `canary`) may be skipped but must carry a `--why`.

## Why

Prose instructions to a model are advisory. They compete with everything else in context,
they degrade as the conversation grows, and under pressure — a long session, a user in a
hurry, a plausible-looking shortcut — "the ladder is ordered" loses to "the user wants the
PR". A non-zero exit code does not lose that argument.

This is the same reasoning that put honest test-output parsing in `gate.py` rather than
trusting a reported "tests pass". The system's two hardest rules — *never merge* and
*never claim a green suite without runner output* — are exactly the rules most likely to
be rationalised away in the moment, so both are mechanised.

The secondary benefit is answerability. `state.py show` makes "where is this feature
stuck" a command rather than an inference, which is what makes a lost session survivable.

## Consequences

- Adding a stage means adding a rung to `LADDER` in `state.py` plus a skill directory.
  The spine does not change. This is the property that keeps the spine from accumulating
  stage logic.
- `STATE.json` lives in the **target** repo at `docs/arch/<feature>/`, not in eng-brain —
  state belongs beside the artifacts it describes, and travels with the branch.
- Hand-editing `STATE.json` defeats the mechanism. The spine is explicitly instructed to
  surface a refusal rather than route around it; if the ladder is wrong for a feature,
  that is a conversation, not a file edit.
- The refusal messages are part of the contract, not decoration — a refusal that does not
  say what would unblock it just gets worked around.

## Alternatives rejected

- **Prose-only enforcement.** Cheapest, and what the pipeline effectively had. It is why
  `/slice` could run before `/arch` without anything noticing.
- **Git hooks.** Enforces at commit time, far too late — by then the slices are written.
- **A gbrain page as the state store.** Attractive, since the brain is already the memory.
  Rejected: it makes the pipeline unusable offline or with a cold brain, and couples stage
  progress to network availability. The brain records *decisions*; the repo records
  *position*.
