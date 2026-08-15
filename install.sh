#!/usr/bin/env bash
# Project this repo's skills into ~/.claude/skills.
#
# gbrain ships its own 53 skills inside its npm package and has no projector of
# its own; these are a separate layer that lived only in ~/.claude/skills and was
# lost once. This script is that layer's installer, so it never depends on
# transcript archaeology again.
#
#   ./install.sh            install
#   ./install.sh --check    verify installed copies match this repo, change nothing
#   ./install.sh --lock     regenerate skills.lock.json from the repo
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}"
LOCK="$REPO/skills.lock.json"
MODE="${1:-install}"

hash_file() { shasum -a 256 "$1" | awk '{print $1}'; }

gen_lock() {
  {
    echo '{'
    echo "  \"schema\": \"eng-brain.skills.lock/v1\","
    echo "  \"version\": \"$(cat "$REPO/VERSION")\","
    echo '  "files": {'
    first=1
    while IFS= read -r f; do
      rel="${f#$REPO/}"
      [ $first -eq 1 ] || echo ','
      first=0
      printf '    "%s": "%s"' "$rel" "$(hash_file "$f")"
    done < <(find "$REPO/skills" "$REPO/lib" -type f \
               ! -path '*/_recovered/*' ! -name '*.pyc' | sort)
    echo
    echo '  }'
    echo '}'
  } > "$LOCK"
  echo "wrote $LOCK ($(grep -c '": "' "$LOCK") files)"
}

case "$MODE" in
  --lock) gen_lock; exit 0 ;;

  --check)
    fail=0
    while IFS= read -r f; do
      rel="${f#$REPO/skills/}"
      dest="$TARGET/$rel"
      if [ ! -f "$dest" ]; then
        echo "MISSING  $rel"; fail=1
      elif [ "$(hash_file "$f")" != "$(hash_file "$dest")" ]; then
        echo "DIFFERS  $rel"; fail=1
      fi
    done < <(find "$REPO/skills" -type f ! -name '*.pyc' | sort)
    # the shared library is projected as the _eng-brain skill
    while IFS= read -r f; do
      rel="${f#$REPO/lib/}"
      dest="$TARGET/_eng-brain/$rel"
      if [ ! -f "$dest" ]; then
        echo "MISSING  _eng-brain/$rel"; fail=1
      elif [ "$(hash_file "$f")" != "$(hash_file "$dest")" ]; then
        echo "DIFFERS  _eng-brain/$rel"; fail=1
      fi
    done < <(find "$REPO/lib" -type f ! -path '*/_recovered/*' ! -name '*.pyc' | sort)
    [ $fail -eq 0 ] && echo "in sync with $TARGET"
    exit $fail
    ;;

  install)
    mkdir -p "$TARGET"
    n=0
    for d in "$REPO"/skills/*/; do
      name="$(basename "$d")"
      rm -rf "${TARGET:?}/$name"
      cp -R "$d" "$TARGET/$name"
      n=$((n + 1))
    done
    # shared library projects as _eng-brain so CONVENTIONS.md resolves for every stage
    rm -rf "${TARGET:?}/_eng-brain"
    mkdir -p "$TARGET/_eng-brain"
    cp -R "$REPO/lib/." "$TARGET/_eng-brain/"
    rm -rf "$TARGET/_eng-brain/_recovered"
    find "$TARGET" -name '*.py' -path '*/bin/*' -exec chmod +x {} \; 2>/dev/null || true
    find "$TARGET" -name '*.sh' -exec chmod +x {} \; 2>/dev/null || true
    echo "installed $n skills + shared library -> $TARGET"
    echo "run './install.sh --check' to verify"
    ;;

  *) echo "usage: install.sh [install|--check|--lock]" >&2; exit 1 ;;
esac
