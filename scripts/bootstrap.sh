#!/bin/sh
# Set up the local tools and exact original Crystal-9 C64 packet files.
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
python_bin=${PYTHON:-python3}
venv_python="$root/.venv/bin/python"
artifact_dir="$root/build/model"
artifact="$artifact_dir/crystal-9-int4-group2-packed-fp16-scales-v1.pt"
layers="$root/build/layers"
# Pin CP64 to the immutable official GitHub Release asset, not a moving branch.
artifact_url="https://github.com/lewismoten/crystal-9/releases/download/v1.0.0/crystal-9-int4-group2-packed-fp16-scales-v1.pt"
artifact_sha256="63eee663a143ee478308144da406873c72c05b6d5226dbb2f5e329dacb1392eb"

if ! command -v "$python_bin" >/dev/null 2>&1; then
  echo "Python 3 is required (set PYTHON=/path/to/python3 if needed)." >&2
  exit 1
fi

if [ ! -x "$venv_python" ]; then
  "$python_bin" -m venv "$root/.venv"
fi

"$venv_python" -m pip install -r "$root/requirements-dev.txt"
"$root/scripts/bootstrap_64tass.sh"

if [ ! -f "$artifact" ]; then
  if ! command -v curl >/dev/null 2>&1; then
    echo "curl is required to download the verified Crystal-9 artifact." >&2
    exit 1
  fi
  mkdir -p "$artifact_dir"
  curl -L --fail --output "$artifact" "$artifact_url"
fi

"$venv_python" -c "import hashlib, pathlib, sys; p = pathlib.Path(sys.argv[1]); actual = hashlib.sha256(p.read_bytes()).hexdigest(); expected = sys.argv[2]; sys.exit('Crystal-9 artifact SHA-256 mismatch: ' + actual if actual != expected else 0)" "$artifact" "$artifact_sha256"
"$venv_python" "$root/scripts/export_c64_layers.py" --artifact "$artifact" --output "$layers"
printf '%s\n' "CP64 setup complete: original Crystal-9 packets are in build/layers/."
