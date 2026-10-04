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
- A verified `build/layers/` packet set for a model-enabled D64

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

## Model packet source

`scripts/build_disk.py` packages 48 prebuilt original-model packet files from
`build/layers/`. A fresh checkout does not contain them, because model packets
are generated artifacts and are Git-ignored.

Do not point `scripts/export_c64_layers.py` at an arbitrary `.pt`,
`model.safetensors`, or GGUF file. Its input is a specific historical
`crystal-9-packed-int4-fp16-scales-v1` PyTorch manifest with verbatim FP16
scales and packed INT4 tensors. The current public Palace-9 download formats
are not a drop-in replacement for that input contract.

Until a verified CP64-compatible source/download workflow is published, obtain
the checked packet set or the exact compatible source artifact from the project
maintainer. Then place the resulting 48 `C9Wxx.PRG` files and `manifest.json`
under:

```text
build/layers/
```

The historical compatible source artifact, when supplied, must match:

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
