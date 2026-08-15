# the caller's shell. Checks branch explicitly and accumulate into MISSING instead.

# --- 1. Env, before any gbrain call -----------------------------------------------------
# gbrain lives in ~/.bun/bin, which is not on a non-login agent shell's PATH. Guard against
# re-adding on repeated sourcing.
case ":$PATH:" in
  *":$HOME/.bun/bin:"*) ;;
  *) export PATH="$HOME/.bun/bin:$PATH" ;;
esac

# Postgres behind a PgBouncer transaction pooler: no session-level prepared statements.
export GBRAIN_PREPARE=true
export GBRAIN_DISABLE_DIRECT_POOL="${GBRAIN_DISABLE_DIRECT_POOL:-1}"

MISSING=0
note() { printf '  %s\n' "$1"; }
ok()   { printf 'OK    %s\n' "$1"; }
warn() { printf 'WARN  %s\n' "$1"; MISSING=$((MISSING+1)); }