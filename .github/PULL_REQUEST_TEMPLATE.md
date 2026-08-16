<!--
Thanks for contributing! eng-brain dogfoods its own rule: a change is not done until the
gate proves it. Fill this in, and let the checks below be true before you request review.
-->

## What this changes

<!-- One or two sentences. Link the issue it closes, if any. -->

Closes #

## Why

<!-- The problem this solves. -->

## Kind of change

- [ ] Gate script (`skills/_eng-brain/bin/*.py`)
- [ ] Stage skill (`skills/<name>/SKILL.md`)
- [ ] Agent (`agents/<name>.md`)
- [ ] Docs
- [ ] Infra / CI / install

## Checklist

<!-- Everything here is also enforced by CI — running it locally means no surprises. -->

- [ ] If I changed a gate, I updated its `selfcheck` **first** to pin the new behaviour and its message, and it passes.
- [ ] All five gate selfchecks pass (`gate.py`, `coverage.py`, `owns.py`, `concepts.py`, `tractable.py`).
- [ ] `./install.sh --check` is clean, and `./skills/_eng-brain/setup.sh` is green.
- [ ] If I bumped the version, it agrees across `VERSION`, `plugin.json`, and `marketplace.json`.
- [ ] If I added a skill, it has a `triggers:` array; if I added an agent, its `name:` matches the filename and its tools are the minimum it needs.
- [ ] I added a `CHANGELOG.md` entry under `[Unreleased]` for anything user-facing.
- [ ] I did not weaken either invariant: **never merge**, **never claim green without runner output**.

## Notes for the reviewer

<!-- Anything that would help someone read this diff — where the tricky part is, what you're unsure about. -->
