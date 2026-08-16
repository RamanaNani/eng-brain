# Contributing to eng-brain

Thanks for helping. eng-brain is a Claude Code plugin: a set of skills, a roster of agents,
and a handful of Python gate scripts. The bar for a change is simple — **the gates must stay
honest** — and everything below is in service of that.

## The one rule that shapes everything

Gates are code, not prose ([ADR-101](docs/adr/ADR-101-ladder-as-data.md)). A stage cannot be
marked complete out of order; a test suite cannot be called green without runner output. When
you change a gate, you are changing something the whole system trusts. So every gate carries
its own `selfcheck`, and **a gate change is not done until its selfcheck proves the new
behaviour** — including the exact diagnostic wording, because several checks share an exit code
and only the message tells them apart.

## Setup

```bash
git clone https://github.com/RamanaNani/eng-brain.git
cd eng-brain
./skills/_eng-brain/setup.sh     # preflight — tells you what's missing
./install.sh                     # project skills + agents into ~/.claude/
```

Edit **this repo**, never `~/.claude/skills/` or `~/.claude/agents/` — those are projections.
`./install.sh --check` exists to catch exactly the mistake of editing the projection.

> Install the plugin **or** run `./install.sh`, never both — two channels register every
> skill twice and resolution becomes ambiguous.

## Before you open a PR

Run what CI runs (it will fail the PR otherwise):

```bash
# every gate's selfcheck must pass
python3 skills/_eng-brain/bin/gate.py     selfcheck
python3 skills/_eng-brain/bin/coverage.py selfcheck
python3 skills/_eng-brain/bin/owns.py     --selfcheck
python3 skills/_eng-brain/bin/concepts.py --selfcheck
python3 skills/_eng-brain/bin/tractable.py --selfcheck

# projection matches the repo, manifests are valid
./install.sh --check
./skills/_eng-brain/setup.sh
```

CI ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) also checks that manifest versions
agree, every agent has valid frontmatter, every skill has a `triggers:` array, and every shell
script parses. Run them locally and there are no surprises.

## Changing each kind of thing

**A gate (`skills/_eng-brain/bin/*.py`).** Add or update its `selfcheck` first — pin the new
behaviour *and its message* — then make it pass. A gate change with no selfcheck change is
almost always wrong. Red-before-green applies to the gates themselves: see the check fail for
the reason you expect before you make it pass.

**A skill (`skills/<name>/SKILL.md`).** New skills need a `triggers:` array in frontmatter, or
gbrain's resolver cannot route to them and `gbrain doctor` reports `UNREACHABLE`. Keep the
`allowed-tools` honest — if the skill's body calls `Agent` or `Skill`, they must be listed, or
the call silently cannot run.

**An agent (`agents/<name>.md`).** Keep the provenance comment on line 1 (`eng-brain-managed`);
`install.sh` uses it to avoid overwriting a user's hand-written agent. The `name:` must match
the filename. Remember the roster's principle — **an agent's tools are its guardrail**; give a
reviewer `Write` and you have quietly turned it into an implementer
([ADR-103](docs/adr/ADR-103-agent-roster-tools-as-guardrails.md)).

**Docs.** Prose is fine to change freely, but if you change a gate's behaviour, update the doc
that describes it in the same PR.

## Versioning

eng-brain uses [semantic versioning](https://semver.org). One number, in three places that CI
checks agree: `VERSION`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`. Add a
`CHANGELOG.md` entry under `[Unreleased]` for anything user-facing.

## Style

Match the surrounding code and prose. The Python favours small, self-checked functions with
comments that record *the real failure someone had to debug*, not what the code obviously does.
The skills are written to be read by an agent under time pressure — direct, imperative, and
explicit about what must never happen.

## Reporting security issues

Do not open a public issue for a vulnerability. See [SECURITY.md](SECURITY.md).

## License

By contributing, you agree your contributions are licensed under the [MIT License](LICENSE).
