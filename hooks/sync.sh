#!/usr/bin/env bash
# SessionStart hook — keep the installed skills in step with the source.
#
# Two install modes, two different staleness problems:
#
#   local clone   You edit the repo; ~/.claude/skills/ is a projection that goes
#                 stale the moment you do. That projection is DERIVED data, so
#                 re-syncing it is safe and idempotent — this hook does it, and
#                 says so. Losing an edit to the projection is the failure this
#                 whole repo exists to prevent.
#
#   plugin        Claude Code owns the copy under ~/.claude/plugins/. Updating
#                 means fetching code from the network, which is not something a
#                 hook should do without being asked. This only NOTIFIES, at most
#                 once a day, and tells you the command to run.
#
# Silent when there is nothing to say — a hook that speaks every session gets
# ignored, and then it is not a hook, it is noise.
#
# Opt out:  ENG_BRAIN_AUTO_SYNC=0   (drift is reported but not applied)
#           ENG_BRAIN_NO_UPDATE_CHECK=1
set -uo pipefail

ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
TARGET="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}"
STAMP="${TMPDIR:-/tmp}/.eng-brain-update-check"
AUTO_SYNC="${ENG_BRAIN_AUTO_SYNC:-1}"

# Plugin install? Then $ROOT lives under the plugins cache and is not a git repo
# we own. Anything else we treat as a working clone.
case "$ROOT" in
  *"/.claude/plugins/"*) MODE="plugin" ;;
  *) MODE=$([ -d "$ROOT/.git" ] && echo "clone" || echo "plugin") ;;
esac

# ---------------------------------------------------------------- local clone
if [ "$MODE" = "clone" ]; then
  [ -x "$ROOT/install.sh" ] || exit 0

  if "$ROOT/install.sh" --check >/dev/null 2>&1; then
    exit 0                                  # in sync, say nothing
  fi

  drift=$("$ROOT/install.sh" --check 2>/dev/null | grep -cE '^(MISSING|DIFFERS)' || true)

  if [ "$AUTO_SYNC" = "1" ]; then
    if "$ROOT/install.sh" >/dev/null 2>&1; then
      echo "eng-brain: re-installed skills from $ROOT ($drift file(s) were out of date)."
    else
      echo "eng-brain: skills are out of date and the re-install FAILED. Run: $ROOT/install.sh"
    fi
  else
    echo "eng-brain: $drift file(s) in $TARGET differ from $ROOT. Run: $ROOT/install.sh"
  fi
  exit 0
fi

# -------------------------------------------------------------------- plugin
[ "${ENG_BRAIN_NO_UPDATE_CHECK:-0}" = "1" ] && exit 0

# At most one check per day. A network call on every session start is rude.
if [ -f "$STAMP" ]; then
  now=$(date +%s)
  then_=$(cat "$STAMP" 2>/dev/null || echo 0)
  [ $((now - then_)) -lt 86400 ] && exit 0
fi
date +%s > "$STAMP" 2>/dev/null || true

local_ver=$(sed -n 's/.*"version"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' \
            "$ROOT/.claude-plugin/plugin.json" 2>/dev/null | head -1)
[ -z "$local_ver" ] && exit 0

remote_ver=$(curl -fsS --max-time 6 \
  "https://raw.githubusercontent.com/RamanaNani/eng-brain/main/.claude-plugin/plugin.json" 2>/dev/null \
  | sed -n 's/.*"version"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1)
[ -z "$remote_ver" ] && exit 0

if [ "$local_ver" != "$remote_ver" ]; then
  # Only speak if remote is genuinely newer; sort -V keeps this from firing when
  # a local build is ahead of main.
  newest=$(printf '%s\n%s\n' "$local_ver" "$remote_ver" | sort -V | tail -1)
  if [ "$newest" = "$remote_ver" ]; then
    echo "eng-brain: $remote_ver available (you have $local_ver). Update with:"
    echo "  claude plugin marketplace update eng-brain && claude plugin install eng-brain@eng-brain"
  fi
fi
exit 0
