# Building CP64

This guide builds the local development disk image. The output is always:

```text
release/crystal-palace-9.d64
```

The `release/` output is generated and Git-ignored. A numbered archival image is also written under `build/`.

## Prerequisites

- Python 3 (`python3`)
- Git
- Internet access on the first assembler bootstrap
- The original Crystal-9 packed INT4/FP16-scale model artifact and an environment that can import `torch`

Create CP64's small development environment once:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
```

## Linux (Debian/Ubuntu)

The local assembler bootstrap uses `apt` and `dpkg-deb`; it does not install 64tass system-wide.

```sh
scripts/bootstrap_64tass.sh
```

## macOS

Install Homebrew first if it is not already installed. The same bootstrap command uses the `tass64` Homebrew formula when `64tass` is absent, then creates the repository-local assembler path expected by the build.

```sh
scripts/bootstrap_64tass.sh
```

If an older checkout still has the Debian-only bootstrap script, use this one-time workaround before building:

```sh
brew install tass64
mkdir -p tools/64tass/usr/bin
ln -sf "$(command -v 64tass)" tools/64tass/usr/bin/64tass
```

## Original model artifact

CP64 does not generate substitute model data. You do **not** need a separate
`~/crystal-9` checkout. Obtain the original packed artifact, choose any local
path for it, then install `torch` into this repository's `.venv` and export the
48 D64 packet files from here:

```sh
.venv/bin/python -m pip install torch
.venv/bin/python scripts/export_c64_layers.py \
  --artifact /path/to/crystal-9-int4-group2-packed-fp16-scales-v1.pt \
  --output build/layers
```

The expected source artifact SHA-256 is:

```text
63eee663a143ee478308144da406873c72c05b6d5226dbb2f5e329dacb1392eb
```

## Build and verify

From the repository root:

```sh
.venv/bin/python scripts/render_screen_states.py --check
.venv/bin/python scripts/build_disk.py
.venv/bin/python -m pytest -q
```

`build_disk.py` regenerates the INFO runtime archive, assembles `CP64.PRG`, packages and validates the D64, writes the numbered build image, and copies the reviewable output to:

```text
release/crystal-palace-9.d64
```

The D64 contains the executable, archive runtime/text files, and 48 original model packet files. See [`D64_MANIFEST.md`](D64_MANIFEST.md) for the disk layout and [`STAGE_HISTORY.md`](STAGE_HISTORY.md) for proof boundaries and historical stage notes.
