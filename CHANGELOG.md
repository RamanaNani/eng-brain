# Changelog

All notable changes to eng-brain are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

_Nothing yet. Add user-facing changes here as you make them._

## [3.0.0] — 2026-08-15

The pipeline gains a typed agent roster and a requirements-traceability gate, and the
lifecycle is documented end to end. Major because the slice manifest and story format both
gain required fields (`covers`, `AC-<n>` ids), and the plugin now ships agents.

### Added
- **Agent roster** (`agents/`) — six typed subagents whose tools are their guardrails:
  `slice-implementer`, `slice-reviewer`, `test-auditor`, `architect`, `security-tester`,
  `devops-advisor`. A reviewer with no `Write` tool cannot fix what it reviews; an architect
  with no `Write` tool cannot smuggle in an implementation. Declared in `plugin.json`, projected
  by `install.sh` for clone installs. See [ADR-103](docs/adr/ADR-103-agent-roster-tools-as-guardrails.md).
- **`coverage.py`** — a new gate proving every acceptance criterion reaches a slice. `STORY.md`
  criteria get stable `AC-<n>` ids; each slice declares the ids it `covers`; the gate fails on
  any uncovered criterion or dangling reference. Runs in `/slice` and `/before-pr`. Self-checked
  like every other gate. See [ADR-102](docs/adr/ADR-102-requirements-traceability.md).
- **Bounded fix loop in `/fleet`** — a red or blocked slice is retried up to 3 times with the
  verbatim failure fed back, then marked blocked for a re-cut. The loop's exit is the gate,
  never the agent's sense of doneness.
- **CI** (`.github/workflows/ci.yml`) — every push and PR runs all five gate selfchecks, checks
  manifest validity and version agreement, validates agent frontmatter and skill triggers, and
  parses every shell script. This closes the "no CI" gap.
- **Documentation** — [`docs/PIPELINE.md`](docs/PIPELINE.md) (the full lifecycle + the loop
  model), [`docs/AGENTS.md`](docs/AGENTS.md) (the roster reference), and ADR-102 / ADR-103.
- Open-source community health: `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`,
  `CHANGELOG.md`, GitHub issue/PR templates.

### Changed
- **`/story`** now assigns stable `AC-<n>` ids to acceptance criteria and self-records its gate,
  bootstrapping the ladder (`state.py init`) when run standalone.
- **`/slice`** manifest gains a required `covers` field per slice; Phase 3.5 defaults agent roles
  to the eng-brain roster (specialists are an upgrade when installed, not a dependency); Phase 6
  runs `coverage.py map`.
- **`/fleet`** assembles passing slices onto an integration branch and stops — it no longer opens
  pull requests (that is `/pr`, stage 9). The title, phases, and report were contradicting the
  skill's own never-merge rule; they now agree.
- **`/arch`** can generate design candidates via parallel `architect` agents.
- **`/pentest`** gains `Agent` and `Skill` in `allowed-tools` (it referenced both and could not
  call them) and dispatches the internal `security-tester`, so the stage is self-contained.
- **`/arch`, `/contract`, `/slice`, `/pr`** now self-record their gate with `state.py`, matching
  the stages that already did — so `/sdlc` can advance and a resumed session knows they are done.
- `/sdlc` `allowed-tools` normalized from the legacy `Task` to `Agent`.

### Fixed
- **`state.py`** writes `STATE.json` atomically (temp + `os.replace`) so an interrupted write can
  never corrupt the one file the system relies on to survive a lost session; a malformed
  `STATE.json` now reports a friendly error instead of a raw traceback.
- **`owns.py`** refuses duplicate slice ids, which previously let one slice's file set overwrite
  another's in an id-keyed map and hid real collisions (a false green).
- **`/slice`** no longer writes a duplicate of `owns.py` to `/tmp` — it calls the canonical,
  self-checked gate.
- **`check-upstream.sh`** resolves its directory relative to the script (works from both install
  channels) instead of a hardcoded clone path, and is documented as on-demand rather than a
  SessionStart hook that was never registered.
- Removed references to skills that do not exist (`/investigate`, `/qa`, `/retro`) and the stale
  `fleet accept` trigger / `--accept` failure-mode row.

## [2.4.0] — 2026-08-15

Initial public release: the eleven-stage ladder (`/sdlc`), the gate scripts (`state.py`,
`gate.py`, `owns.py`, `concepts.py`, `tractable.py`), gbrain write-back, the Strix-derived
`/pentest` stage, and the recovery post-mortem ([ADR-100](docs/adr/ADR-100-claude-code-setup-recovery.md)).

[3.0.0]: https://github.com/RamanaNani/eng-brain/releases/tag/v3.0.0
[2.4.0]: https://github.com/RamanaNani/eng-brain/releases/tag/v2.4.0
