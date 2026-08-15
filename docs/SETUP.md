# Setup

From nothing to a working pipeline. Roughly 15 minutes, most of it waiting on Supabase.

If you only want to read the skills and not run them, you can stop after Step 4 — the
pipeline degrades to "well-structured prompts" without a brain, which is still useful.
Steps 5–7 are what make it remember.

---

## 0. Prerequisites

| Tool | Why | Install |
|---|---|---|
| **bun** | runs gbrain | `curl -fsSL https://bun.sh/install \| bash` |
| **python3** ≥ 3.9 | `skills/_eng-brain/bin/*.py` | preinstalled on macOS; else python.org |
| **git** | everything | preinstalled |
| **Claude Code** | invokes the skills | `npm i -g @anthropic-ai/claude-code` |
| **gh** *(optional)* | `/pr` opens PRs | `brew install gh && gh auth login` |

A Postgres database is needed for the brain. Supabase's free tier is enough; Step 2
covers a local alternative if you'd rather not use a hosted DB.

---

## 1. Clone and look around

```bash
git clone https://github.com/RamanaNani/eng-brain.git
cd eng-brain
./skills/_eng-brain/setup.sh          # preflight — expect failures until you finish Step 6
```

`skills/_eng-brain/setup.sh` is the source of truth for whether your environment is right. Run it
whenever something behaves oddly; it checks the toolchain, the brain, the env vars, the
installed skills, and the self-tests, and it tells you which step to go back to.

---

## 2. Provision a brain

The brain is a Postgres database with pgvector. Two options.

### Option A — Supabase (recommended)

1. Create a project at [supabase.com](https://supabase.com). Any region; free tier is fine.
2. **Project Settings → Database → Connection string →** pick the **Transaction pooler**
   (port **6543**). Copy it.
3. Substitute your database password for `[YOUR-PASSWORD]`.

You want a URI shaped like:

```
postgresql://postgres.[ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres
```

> **Take the pooler, not the direct connection.** The direct host
> (`db.[ref].supabase.co:5432`) is IPv6-only. On an IPv4 network it fails with
> `ECONNREFUSED`, which reads like a wrong password and sends you off checking
> credentials that were fine. This is the single most common setup failure.

### Option B — PGLite (local, no account)

```bash
gbrain init --engine pglite
```

Everything works except cross-machine sync. Fine for trying the pipeline out; migrate to
Postgres later with `gbrain migrate`.

---

## 3. Install and initialise gbrain

```bash
bun add github:garrytan/gbrain

gbrain init --non-interactive \
  --url "postgresql://postgres.[ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres"

gbrain doctor
```

`doctor` should reach a health score and print `[OK] connection`. If it fails here, the
problem is the URI — re-read the pooler warning above.

Config lands in `~/.gbrain/config.json`.

> **Security:** that file stores your database password in plaintext. If that matters for
> your setup, put the URI in an environment variable and reference it rather than letting
> `init` write it, and keep `~/.gbrain/` out of any backup that leaves your machine.

---

## 4. Install the skills

### Option A — plugin (recommended)

Nothing to clone, and updates are handled for you:

```
/plugin marketplace add RamanaNani/eng-brain
/plugin install eng-brain@eng-brain
```

This repo doubles as a Claude Code marketplace — `.claude-plugin/marketplace.json` at the
root is what makes that work. Skip to Step 5.

### Option B — clone (if you'll modify the skills)

```bash
./install.sh            # projects into ~/.claude/skills/
./install.sh --check    # verify the installed copy matches this repo
```

This installs 13 skills plus the shared `_eng-brain` library. If you installed via the plugin marketplace instead, skip this step entirely — Claude Code manages the copy.

**Edit this repo, never `~/.claude/skills/` directly.** The installed copy is a
projection; `--check` exists to catch the case where someone edited the projection and is
about to lose it on the next install.

Set `CLAUDE_SKILLS_DIR` if your skills live somewhere non-standard.

---

## 5. Configure the environment

Two variables matter. Put them where your shell and Claude Code both see them.

In `~/.claude/settings.json`:

```json
{
  "env": {
    "GBRAIN_PREPARE": "true"
  }
}
```

And in your shell profile (`~/.zshrc`, `~/.bashrc`):

```bash
export PATH="$HOME/.bun/bin:$PATH"
export GBRAIN_PREPARE=true
export GBRAIN_DISABLE_DIRECT_POOL=1
```

**`GBRAIN_PREPARE=true` is not optional.** The pooler rejects session-level prepared
statements, and without this the failure mode is *an empty result set rather than an
error*. Every search comes back thin and everything looks like a sparse brain rather than
a broken connection. It is the worst kind of bug — silent and plausible — which is why it
appears in three places in this repo.

---

## 6. Register your repo as a source

gbrain needs to know which repo a page belongs to.

```bash
cd /path/to/your/project
gbrain sources add my-project --path "$(pwd)"
gbrain sources list
```

`--source` is mandatory on every `capture`. Omitting it files the page into `default`,
which is the wrong repo and will not sync — silently.

---

## 7. Verify

```bash
cd /path/to/eng-brain
./skills/_eng-brain/setup.sh
```

Every line should be green. Then:

```bash
python3 skills/_eng-brain/bin/gate.py selfcheck    # must print OK
gbrain doctor                        # resolver_health should report all skills reachable
```

In Claude Code, `/sdlc` should now appear. Ask it where a feature stands:

```
/sdlc where is my-feature
```

---

## Claude Code setup for a new machine

The skills are one of three independent layers. If you're setting up from scratch, or
recovering, they restore differently:

| Layer | Lives in | Restore |
|---|---|---|
| gbrain's own skills (53) | the gbrain npm package | reinstall gbrain, copy `node_modules/gbrain/skills/*` into `~/.claude/skills/` |
| **eng-brain (13)** | **this repo** | `./install.sh` |
| Marketplace plugins | marketplace repos | `claude plugin marketplace add <repo>` then `claude plugin install <plugin>@<market>` |

Your installed plugins and their marketplaces are recorded in `~/.claude/settings.json`
under `enabledPlugins` and `extraKnownMarketplaces` — check there first when rebuilding;
it is much cheaper than reconstructing the list by hand.

gbrain ships no projector for its own bundled skills. They were copied in manually, so
re-copy them after every gbrain upgrade or they silently go stale.

---

## Troubleshooting

**`gbrain: command not found`**
`~/.bun/bin` is not on PATH. Non-login shells (including the one Claude Code's agents run
in) do not pick up your profile. `source skills/_eng-brain/setup.sh` fixes it for the current shell.

**Searches return nothing and the brain "looks empty"**
Almost always `GBRAIN_PREPARE`. Check `echo $GBRAIN_PREPARE` — it must be `true`. Treat an
unexpectedly thin result as a suspected connection fault, not as evidence about the brain.

**`ECONNREFUSED` on init**
You used the direct connection string instead of the transaction pooler. Port **6543**,
host `...pooler.supabase.com`.

**`gbrain doctor` reports `UNREACHABLE` / `MECE_GAP` for a skill**
That skill's frontmatter has no `triggers:` array, so the resolver cannot route to it. Add
one and re-run `./install.sh`.

**`./install.sh --check` says `DIFFERS`**
Someone edited `~/.claude/skills/` directly. Copy the change back into this repo, or
discard it by re-running `./install.sh`.

**`gate.py selfcheck` fails**
Stop and fix it before trusting any gate result. That selfcheck is inherited from the
original implementation and asserts on exact diagnostic wording as well as exit codes —
a gate that is silently wrong is worse than no gate at all.

**`addLink failed: page ... not found`**
Links cannot span gbrain sources. Both pages must be captured under the same `--source`.
