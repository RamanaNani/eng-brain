# ADR-103 — A typed agent roster, where tools are the guardrail

- **Date:** 2026-08-15
- **Status:** Accepted
- **Context:** The pipeline dispatched anonymous general agents and depended on external plugins (`ecc:*`, `voltagent:*`) for the specialists. It needed its own roster, and a principled answer to "when does a role deserve to be an agent?"

## Problem

`/fleet`, `/arch`, and `/slice` all spawned subagents, but the plugin defined none of its
own. Two costs followed:

1. **Not self-contained.** The reviewer, the security tester, the test auditor were all
   `ecc:*` or `voltagent:*` types. Install eng-brain alone and `/pentest`'s core SAST step
   silently could not run, because it referenced an agent from a plugin that was not there.

2. **No structural guarantees.** An anonymous "reviewer" agent has the same tools as an
   "implementer" — including `Write` and `Edit`. So "review, don't fix" was an *instruction*,
   competing for attention with everything else, and a reviewer that quietly rewrote the code
   it was reviewing violated nothing the system could see.

We also had no discipline about *which* roles deserve a definition. A job title alone is a
costume: a "PM agent" and a "CTO agent" that share tools and context are two prompts wearing
hats, not two different capabilities.

## Decision

Ship a roster of **six** typed agents under `agents/`, declared in `plugin.json`, and adopt
one rule for what earns a definition and one principle for how it is constrained.

**A role earns an agent only if it needs one of:**

1. **Different tools** — the guardrail (below).
2. **Guaranteed context isolation** — a reviewer that never saw the implementer's reasoning
   cannot inherit its blind spot.
3. **A different output contract** — findings with severity, not prose.

By that rule the roster is six, not fifteen:

| Agent | Tools | The guarantee its toolset makes |
|---|---|---|
| `slice-implementer` | Read, Write, Edit, Bash, Grep, Glob | builds — but no `Agent`, so it cannot spawn its own sub-fleet |
| `slice-reviewer` | Read, Grep, Glob, Bash | **no Write/Edit** — it physically cannot fix what it reviews |
| `test-auditor` | Read, Grep, Glob, Bash | read-only — it judges test adequacy, it does not add the missing test |
| `architect` | Read, Grep, Glob, Bash, WebFetch, WebSearch | **no Write/Edit** — a design candidate cannot smuggle in half an implementation |
| `security-tester` | Bash, Read, Grep, Glob, WebFetch | no repo `Write` — it proves exploitability read-only, never mutates the target |
| `devops-advisor` | Read, Grep, Glob, Bash | read-only — it plans a deploy and its rollback, it never triggers one |

**The principle: tools are the guardrail.** The most important column in that table is what
each agent *cannot* do. A reviewer with no `Write` turns "don't fix what you review" from a
sentence a model may forget into a capability it does not possess. This is [ADR-101](ADR-101-ladder-as-data.md)
applied to agents: don't trust the prompt to hold a line the toolset can hold for you.

## What deliberately did *not* become an agent

- **The gates.** `gate.py`, `owns.py`, `coverage.py` decide pass/fail deterministically. An
  agent judging "are the tests green?" is strictly worse than a script parsing the output.
  Agents produce and critique; scripts verify and record.
- **A "manager" / "orchestrator" agent.** `/sdlc` is a skill holding a data ladder, not an
  agent improvising a plan. Orchestration is deterministic control flow, not a persona.

## Dispatch and fallback

Skills reference the roster as `eng-brain:<name>`. `/slice` Phase 3.5 still *upgrades* any
role to an installed language specialist (`voltagent-lang:typescript-pro`, `ecc:react-reviewer`,
…) when its plugin is present — a specialist catches what a generalist misses — but the
**default is always the eng-brain roster**, so the pipeline is self-contained and degrades to
its own agents rather than failing when an optional plugin is absent.

For clone installs, `install.sh` projects `agents/*.md` into `~/.claude/agents/`, guarded by
a per-file `eng-brain-managed` marker so a user's hand-written agent of the same name is never
overwritten. For plugin installs, `plugin.json`'s `"agents": "./agents"` registers them.

## Consequences

- `/pentest` and every `/fleet` review now work with **only** eng-brain installed. External
  specialists become an upgrade, not a dependency.
- The "reviewer cannot fix" and "architect cannot implement" invariants are enforced by the
  runtime, not by hope.
- Adding a role is adding a file to `agents/` — the roster is data, like the ladder. No spine
  edit, no new dispatch code.

## Alternatives rejected

- **A society of persona agents talking to each other** (PM↔architect↔dev↔QA). Every system
  that actually ships code converged away from this: agent-to-agent chat is a telephone game;
  artifacts on disk with script gates are an assembly line. We kept the assembly line and gave
  it a typed crew.
- **One general agent for everything, differentiated only by prompt.** Loses the tool
  guardrail — the single most valuable property of the roster.
- **Keep depending on `ecc:*` / `voltagent:*`.** Fine as an upgrade, unacceptable as the
  floor: a plugin should stand up on its own.
