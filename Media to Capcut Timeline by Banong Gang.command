#!/bin/bash
set -u

script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
if ! command -v python3 >/dev/null 2>&1; then
  printf 'ERROR: Python 3 is required.\n'
  read -r _
  exit 1
fi

python3 "$script_dir/MediaToCapcut.py" "$@"
status=$?
keep_open=0
for arg in "$@"; do
  if [[ "$arg" == "--keep-open" ]]; then
    keep_open=1
  fi
done
if [[ "$status" -eq 0 && "$keep_open" -eq 0 && "${TERM_PROGRAM:-}" == "Apple_Terminal" ]]; then
  /usr/bin/osascript -e 'tell application "Terminal" to close (front window)' >/dev/null 2>&1 || true
fi
exit "$status"
