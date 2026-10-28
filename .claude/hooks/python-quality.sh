#!/usr/bin/env bash
# PostToolUse hook: after Claude edits a Python file, autofix it with ruff and report what is still wrong.
# Exit code 2 sends stderr back to Claude, so it fixes the problem in the same turn.
set -uo pipefail

file=$(python3 -c 'import json, sys; print(json.load(sys.stdin).get("tool_input", {}).get("file_path", ""))' 2>/dev/null)
[[ "$file" == *.py ]] || exit 0
[[ -f "$file" ]] || exit 0
cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0
case "$file" in
  */migrations/*) exit 0 ;;  # yoyo migrations are not linted
esac

uv run --quiet ruff check --fix --quiet "$file" >/dev/null 2>&1
uv run --quiet ruff format --quiet "$file" >/dev/null 2>&1

problems=""
out=$(uv run --quiet ruff check --no-fix --output-format concise "$file" 2>&1) || problems+="$out"$'\n'
out=$(uv run --quiet pyright "$file" 2>&1) || problems+=$(echo "$out" | grep -E "error|warning" | grep -v "new pyright version")$'\n'
if [[ "$file" == */src/* ]]; then
  out=$(uv run --quiet python -m tools.check_architecture 2>&1) || problems+="$out"$'\n'
fi

if [[ -n "${problems//[$'\n ']/}" ]]; then
  echo "Quality checks failed for $file (ruff autofix already applied):" >&2
  echo "$problems" >&2
  exit 2
fi
exit 0
