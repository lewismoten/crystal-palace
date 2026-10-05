#!/bin/sh
# Rebuild every derived asset, review preview, and release disk after bootstrap.
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
python="$root/.venv/bin/python"

if [ ! -x "$python" ]; then
  echo "CP64 dependencies are missing; run scripts/bootstrap.sh first." >&2
  exit 1
fi

"$python" "$root/scripts/compile_c64_assets.py"
"$python" "$root/scripts/render_screen_states.py"
"$python" "$root/scripts/build_disk.py"
"$python" "$root/scripts/render_screen_states.py" --check

if [ ! -s "$root/release/crystal-palace-9.d64" ]; then
  echo "release/crystal-palace-9.d64 was not produced." >&2
  exit 1
fi

printf '%s\n' "CP64 build complete: release/crystal-palace-9.d64"
