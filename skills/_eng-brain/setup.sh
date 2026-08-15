#!/usr/bin/env bash
# eng-brain environment + preflight.
#
# Two ways to use it:
#   source lib/setup.sh     export the env every stage skill needs, quietly
#   ./lib/setup.sh          run the checks and print a report (exit 1 if broken)
#
# The three exports below are not cosmetic. Each one guards a failure that is
# hard to diagnose from its symptom:
#
#   PATH          gbrain lives in ~/.bun/bin, which a non-login agent shell does
#                 not have. Without this the CLI is simply "not found" and every
#                 health check reports a dead brain.
#   GBRAIN_PREPARE
#                 The engine is Postgres behind a PgBouncer transaction pooler,
#                 which does not support session-level prepared statements.
#                 Its absence yields an EMPTY RESULT SET RATHER THAN AN ERROR —
#                 so a thin `search` is a suspected connection fault, not proof
#                 the brain is thin. This is the nastiest bug in the system.
#   GBRAIN_DISABLE_DIRECT_POOL
#                 The direct (non-pooler) Supabase host is IPv6-only. On a v4
#                 network it fails with ECONNREFUSED, which reads like a wrong
#                 password rather than a wrong host.

case ":$PATH:" in
  *":$HOME/.bun/bin:"*) ;;
  *) PATH="$HOME/.bun/bin:$PATH" ;;
esac
export PATH
export GBRAIN_PREPARE="${GBRAIN_PREPARE:-true}"
export GBRAIN_DISABLE_DIRECT_POOL="${GBRAIN_DISABLE_DIRECT_POOL:-1}"

# Sourced? Set the env and stop. Only run checks when executed directly.
(return 0 2>/dev/null) && return 0

MISSING=0
ok()   { printf "  \033[32m✓\033[0m %s\n" "$1"; }
warn() { printf "  \033[33m!\033[0m %s\n" "$1"; }
bad()  { printf "  \033[31m✗\033[0m %s\n" "$1"; MISSING=$((MISSING + 1)); }

echo "eng-brain preflight"
echo

echo "Toolchain"
command -v bun     >/dev/null 2>&1 && ok "bun $(bun --version 2>/dev/null)"     || bad "bun not found — https://bun.sh"
command -v git     >/dev/null 2>&1 && ok "git $(git --version 2>/dev/null | awk '{print $3}')" || bad "git not found"
command -v python3 >/dev/null 2>&1 && ok "python3 $(python3 --version 2>&1 | awk '{print $2}')" || bad "python3 not found (lib/bin/*.py need it)"
command -v claude  >/dev/null 2>&1 && ok "claude CLI"                            || warn "claude CLI not found — skills can't be invoked without it"
command -v gh      >/dev/null 2>&1 && ok "gh CLI"                                || warn "gh not found — /pr needs it to open pull requests"
echo

echo "gbrain"
if command -v gbrain >/dev/null 2>&1; then
  ok "gbrain $(gbrain --version 2>/dev/null | head -1)"
  if [ -f "$HOME/.gbrain/config.json" ]; then
    ok "configured (~/.gbrain/config.json)"
    if gbrain doctor --fast >/dev/null 2>&1; then
      ok "doctor passes"
    else
      bad "gbrain doctor failed — run: gbrain doctor"
    fi
  else
    bad "not initialised — run: gbrain init --non-interactive --url '<postgres-uri>'"
  fi
else
  bad "gbrain not found — run: bun add github:garrytan/gbrain"
fi
echo

echo "Environment"
[ "$GBRAIN_PREPARE" = "true" ] && ok "GBRAIN_PREPARE=true" || bad "GBRAIN_PREPARE must be true"
case ":$PATH:" in *":$HOME/.bun/bin:"*) ok "~/.bun/bin on PATH" ;; *) bad "~/.bun/bin not on PATH" ;; esac
echo

echo "Skills"
T="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}"
if [ -d "$T" ]; then
  ok "$(find "$T" -name SKILL.md | wc -l | tr -d ' ') skills installed in $T"
  [ -f "$T/sdlc/SKILL.md" ] && ok "/sdlc present" || bad "/sdlc missing — run ./install.sh"
  [ -f "$T/_eng-brain/CONVENTIONS.md" ] && ok "_eng-brain library present" || bad "_eng-brain missing — run ./install.sh"
else
  bad "$T does not exist — run ./install.sh"
fi
echo

echo "Self-tests"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$HERE/bin/gate.py" selfcheck >/dev/null 2>&1 && ok "gate.py selfcheck" || bad "gate.py selfcheck FAILED — do not trust the gate"
python3 "$HERE/bin/state.py" --help   >/dev/null 2>&1 && ok "state.py runs"     || bad "state.py broken"
echo

if [ "$MISSING" -eq 0 ]; then
  echo "Ready."
else
  echo "$MISSING problem(s). See docs/SETUP.md."
fi
exit $([ "$MISSING" -eq 0 ] && echo 0 || echo 1)
