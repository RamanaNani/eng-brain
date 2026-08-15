#!/usr/bin/env bash
# Project this repo's skills into ~/.claude/skills.
#
# Only needed for a local clone. If you installed via the plugin marketplace,
# Claude Code manages the copy and you never run this.
#
#   ./install.sh            install
#   ./install.sh --check    verify installed copies match this repo, change nothing
#   ./install.sh --lock     regenerate skills.lock.json from the repo
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}"
LOCK="$REPO/skills.lock.json"
MODE="${1:-install}"

# _recovered/ holds partially-recovered originals kept for provenance. They are
# not runnable and must never be projected.
files() { find "$REPO/skills" -type f ! -path '*/_recovered/*' ! -name '*.pyc' | sort; }
hash_file() { shasum -a 256 "$1" | awk '{print $1}'; }

case "$MODE" in
  --lock)
    {
      echo '{'
      echo "  \"schema\": \"eng-brain.skills.lock/v1\","
      echo "  \"version\": \"$(cat "$REPO/VERSION")\","
      echo '  "files": {'
      first=1
      while IFS= read -r f; do
        [ $first -eq 1 ] || echo ','
        first=0
        printf '    "%s": "%s"' "${f#$REPO/}" "$(hash_file "$f")"
      done < <(files)
      echo
      echo '  }'
      echo '}'
    } > "$LOCK"
    echo "wrote $LOCK ($(files | wc -l | tr -d ' ') files)"
    ;;

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
    done < <(files)
    [ $fail -eq 0 ] && echo "in sync with $TARGET"
    exit $fail
    ;;

  install)
    # Refuse to run alongside a plugin install — both channels register every
    # skill, and you get whichever the loader reaches first.
    if [ -d "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/plugins/cache/eng-brain" ]; then
      echo "eng-brain is already installed as a plugin. Running both registers every" >&2
      echo "skill twice from two versions. Uninstall one first:" >&2
      echo "  claude plugin uninstall eng-brain@eng-brain" >&2
      exit 1
    fi

    mkdir -p "$TARGET"
    n=0 skipped=0
    for d in "$REPO"/skills/*/; do
      name="$(basename "$d")"
      dest="$TARGET/$name"
      # These names are generic — arch, review, deploy, pr. Never delete a
      # directory we did not put there; a third party's hand-written
      # ~/.claude/skills/review is not ours to remove.
      if [ -d "$dest" ] && [ ! -f "$dest/.eng-brain" ]; then
        echo "SKIP $name — exists and is not eng-brain-managed (no .eng-brain marker)" >&2
        skipped=$((skipped + 1))
        continue
      fi
      # Stage beside the target, then swap. A hook killed mid-copy must never
      # leave the skill deleted-and-not-replaced.
      staging="$TARGET/.$name.incoming.$$"
      rm -rf "$staging"
      cp -R "$d" "$staging"
      : > "$staging/.eng-brain"
      rm -rf "$staging/bin/_recovered"
      find "$staging" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
      find "$staging" -name '*.py' -path '*/bin/*' -exec chmod +x {} + 2>/dev/null || true
      find "$staging" -name '*.sh' -exec chmod +x {} + 2>/dev/null || true
      rm -rf "$dest"
      mv "$staging" "$dest"
      n=$((n + 1))
    done
    echo "installed $n skills -> $TARGET"
    [ "$skipped" -gt 0 ] && echo "$skipped skipped (unmanaged) — see above" >&2
    echo "verify with: ./install.sh --check"
    ;;

  *) echo "usage: install.sh [install|--check|--lock]" >&2; exit 1 ;;
esac
