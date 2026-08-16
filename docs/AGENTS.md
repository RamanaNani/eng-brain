# The agent roster

eng-brain ships six subagents under [`agents/`](../agents/). They are the *doers* of the
pipeline — skills conduct, agents do, scripts decide. This page is the reference: who they
are, what they can and cannot touch, and how the pipeline dispatches them.

The design decision behind the roster — **tools are the guardrail** — is recorded in
[ADR-103](adr/ADR-103-agent-roster-tools-as-guardrails.md). The short version: the most
important thing about each agent is what it *cannot* do. A reviewer with no `Write` tool
cannot quietly fix the code it is reviewing; that stops being a rule it might forget and
becomes a capability it does not have.

---

## The six

| Agent | Dispatched by | Can | Cannot | Why the "cannot" matters |
|---|---|---|---|---|
| **`slice-implementer`** | `/fleet` | Read, Write, Edit, Bash, Grep, Glob | spawn agents | one slice, one worktree — it builds, it does not fan out into its own fleet |
| **`slice-reviewer`** | `/fleet` | Read, Grep, Glob, Bash | Write, Edit | it reports defects; a review that rewrites the code is just a second implementer |
| **`test-auditor`** | `/fleet` | Read, Grep, Glob, Bash | Write, Edit | it judges whether tests assert on the brief; it does not add the missing test, so the gap stays on the record |
| **`architect`** | `/arch` | Read, Grep, Glob, Bash, WebFetch, WebSearch | Write, Edit | a design candidate cannot smuggle in half an implementation you are then reluctant to discard |
| **`security-tester`** | `/pentest` | Bash, Read, Grep, Glob, WebFetch | mutate the repo | it proves exploitability read-only, and reads `engagement.md` scope before touching anything |
| **`devops-advisor`** | `/deploy` | Read, Grep, Glob, Bash | trigger a deploy | it plans the release and its rollback; planning a rollback is worthless if planning it can ship something |

Each agent's full brief — its method and its exact return contract — is in its own file under
[`agents/`](../agents/). Read the file, not just this table, before relying on one.

---

## How they are dispatched

Skills reference agents as `eng-brain:<name>`, e.g.:

```
Agent(subagent_type: "eng-brain:architect")
Agent(subagent_type: "eng-brain:slice-reviewer")
```

**The eng-brain roster is always the default.** The pipeline never *requires* an external
plugin. But when a language specialist is installed, `/slice` Phase 3.5 upgrades the relevant
role for that slice — a `typescript-reviewer` catches things a general reviewer does not:

| Slice touches | Upgraded build (if installed) | Upgraded review (if installed) |
|---|---|---|
| React / Next.js | `voltagent-lang:react-specialist` | `ecc:react-reviewer` |
| TypeScript / Node | `voltagent-lang:typescript-pro` | `ecc:typescript-reviewer` |
| Python | `voltagent-lang:python-pro` | `ecc:python-reviewer` |
| DB / migrations | `ruflo-migrations:migration-engineer` | `ecc:database-reviewer` |
| Auth / crypto / input | `voltagent-core-dev:backend-developer` | `ecc:security-reviewer` |
| **anything, no plugin** | **`eng-brain:slice-implementer`** | **`eng-brain:slice-reviewer`** |

If a recorded specialist is not installed, `/fleet` falls back to the eng-brain default and
notes the substitution rather than failing.

---

## Where the cross-review happens

The "agents review each other's work" property lives **inside `/fleet`**, not in a separate
stage. Every green slice, in the same wave, is handed to a `slice-reviewer` (fresh context,
no edit tools, prompted to refute) and a `test-auditor` (does the suite actually assert on
the brief's edge cases?). A slice pushes onto the integration branch only if it survives
both. The stage-7 `/review` is a *different* review — the whole assembled diff, read once by
a human-facing pass for scope drift and claimed-but-not-honoured requirements.

So there are two review layers, and they catch different things:

- **In-fleet, per slice, by agents** — local defects, weak tests, ownership violations.
- **Stage 7, whole feature, human-facing** — did we build the right thing, end to end.

---

## Installing / updating the roster

- **Plugin install:** `plugin.json` declares `"agents": "./agents"`; Claude Code registers
  them automatically.
- **Clone install:** `./install.sh` projects `agents/*.md` into `~/.claude/agents/`, guarded
  by an `eng-brain-managed` marker so it never overwrites an agent you wrote by hand.
- **Verify:** `./install.sh --check` reports any agent that is missing or out of date.

To change an agent, edit its file under `agents/` in this repo and re-run `./install.sh` —
never edit `~/.claude/agents/` directly, exactly as with skills.
