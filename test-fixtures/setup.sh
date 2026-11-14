#!/usr/bin/env bash
# Builds a throwaway git repo for a test scenario.
#
#   ./setup.sh <scenario> [target-dir] [--force]
#   ./setup.sh --all [--force]
#   ./setup.sh --list
#
# Steps for a scenario:
#   1. copy projects/<base>/ into the target
#   2. run scenarios/<id>/prepare.py <target>   (optional, inflates the base before commit)
#   3. git init on branch "develop", commit everything as the base state
#   4. if scenarios/<id>/committed/ exists: create branch feature/<id>, copy it over, commit
#   5. leave the review subject UNCOMMITTED:
#        - delete paths listed in scenarios/<id>/delete.txt
#        - copy scenarios/<id>/changes/ over the tree (new files stay untracked)
#        - run scenarios/<id>/generate.py <target>  (optional, mechanical bulk edits)
#        - git add paths listed in scenarios/<id>/staged.txt (optional, partial staging)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
SANDBOX="$ROOT/sandbox"

die() { echo "error: $*" >&2; exit 1; }

list_scenarios() { find "$ROOT/scenarios" -mindepth 1 -maxdepth 1 -type d -exec basename {} \; | sort; }

read_list() { # prints non-empty, non-comment lines of a file
  [ -f "$1" ] || return 0
  grep -v '^[[:space:]]*#' "$1" | grep -v '^[[:space:]]*$' || true
}

setup_one() {
  local id="$1" target="$2" force="$3"
  local sdir="$ROOT/scenarios/$id"
  [ -d "$sdir" ] || die "unknown scenario '$id' (see --list)"
  [ -f "$sdir/base" ] || die "$sdir/base missing (must contain the base project name)"
  local base; base="$(tr -d '[:space:]' < "$sdir/base")"
  [ -d "$ROOT/projects/$base" ] || die "base project '$base' not found in projects/"

  if [ -e "$target" ]; then
    [ "$force" = 1 ] || die "$target exists (use --force to recreate)"
    rm -rf "$target"
  fi
  mkdir -p "$target"
  cp -R "$ROOT/projects/$base/." "$target/"

  [ -f "$sdir/prepare.py" ] && python3 -I "$sdir/prepare.py" "$target"

  (
    cd "$target"
    export GIT_AUTHOR_NAME="fixture" GIT_AUTHOR_EMAIL="fixture@example.invalid"
    export GIT_COMMITTER_NAME="fixture" GIT_COMMITTER_EMAIL="fixture@example.invalid"
    git init -q
    git checkout -q -b develop
    git add -A
    git commit -qm "Base state: $base"

    if [ -d "$sdir/committed" ]; then
      git checkout -q -b "feature/$id"
      cp -R "$sdir/committed/." .
      git add -A
      git commit -qm "WIP: $id (already committed part)"
    fi

    while IFS= read -r p; do rm -rf -- "$p"; done < <(read_list "$sdir/delete.txt")
    [ -d "$sdir/changes" ] && cp -R "$sdir/changes/." .
    [ -f "$sdir/generate.py" ] && python3 -I "$sdir/generate.py" "$target"
    while IFS= read -r p; do git add -- "$p"; done < <(read_list "$sdir/staged.txt")

    local tracked untracked
    tracked="$(git diff HEAD --name-only | wc -l | tr -d ' ')"
    untracked="$(git ls-files --others --exclude-standard | wc -l | tr -d ' ')"
    printf '%-28s %4s modified/deleted, %4s untracked  -> %s\n' "$id" "$tracked" "$untracked" "$target"
  )
}

force=0; args=()
for a in "$@"; do
  case "$a" in
    --force) force=1 ;;
    *) args+=("$a") ;;
  esac
done

[ "${#args[@]}" -ge 1 ] || { sed -n '2,8p' "$0"; exit 1; }

case "${args[0]}" in
  --list) list_scenarios ;;
  --all)
    for id in $(list_scenarios); do setup_one "$id" "$SANDBOX/$id" "$force"; done ;;
  *)
    setup_one "${args[0]}" "${args[1]:-$SANDBOX/${args[0]}}" "$force" ;;
esac
