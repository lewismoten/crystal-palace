# Building CP64

This guide builds the local development disk image. The output is always:

```text
release/crystal-palace-9.d64
```

The `release/` output is generated and Git-ignored. A numbered archival image is also written under `build/`.

## One-command setup

- Python 3 (`python3`)
- Git
- Internet access for the first setup

Run this once from the repository root:

```sh
scripts/bootstrap.sh
```

It creates `.venv`, installs `py65` and PyTorch from `requirements-dev.txt`,
installs a repository-local 64tass, downloads the exact Crystal-9 model artifact,
verifies it, and exports the 48 original tensor packets under `build/layers/`.

The model source is the [official Crystal-9 v1.0.0 INT4 group-2 artifact with FP16 scales](https://github.com/lewismoten/crystal-9/releases/download/v1.0.0/crystal-9-int4-group2-packed-fp16-scales-v1.pt):

```text
SHA-256: 63eee663a143ee478308144da406873c72c05b6d5226dbb2f5e329dacb1392eb
```

## Assembler bootstrap details

On Debian/Ubuntu, `bootstrap.sh` uses `apt` and `dpkg-deb`. On macOS, it uses
Homebrew's `tass64` formula. Neither route installs CP64's assembler globally.

```sh
scripts/bootstrap_64tass.sh
```

## Model packet source

`scripts/build_disk.py` works without model packets and produces a presentation
preview D64. A fresh checkout does not contain `build/layers/`, because model
packets are generated artifacts and are Git-ignored.

`bootstrap.sh` performs the following model step. It is shown only for a manual
retry or inspection:

```sh
mkdir -p build/model
curl -L --fail \
  --output build/model/crystal-9-int4-group2-packed-fp16-scales-v1.pt \
  https://github.com/lewismoten/crystal-9/releases/download/v1.0.0/crystal-9-int4-group2-packed-fp16-scales-v1.pt

.venv/bin/python -m pip install torch
.venv/bin/python scripts/export_c64_layers.py \
  --artifact build/model/crystal-9-int4-group2-packed-fp16-scales-v1.pt \
  --output build/layers
```

Use this cross-platform check before exporting:

```sh
.venv/bin/python -c "import hashlib, pathlib; p=pathlib.Path('build/model/crystal-9-int4-group2-packed-fp16-scales-v1.pt'); assert hashlib.sha256(p.read_bytes()).hexdigest() == '63eee663a143ee478308144da406873c72c05b6d5226dbb2f5e329dacb1392eb'; print('verified')"
```

The exporter accepts this artifact because its embedded contract is
`crystal-9-packed-int4-fp16-scales-v1` with `scale_storage: float16`. It does
not distill, regenerate, or requantize tensors.

The similarly named `crystal-9-int4-group2-packed-v1.pt` lacks that FP16-scale
contract and is not interchangeable. The GitHub `crystal-9-int3-packed-v1.pt`
artifact is INT3, regardless of an older directory name that includes `int4`.

After export, the same build command packages all 48 original-model packet
files from `build/layers/`. A partial packet directory is rejected rather than
producing a misleading disk.

Do not point `scripts/export_c64_layers.py` at an arbitrary `.pt`,
`model.safetensors`, or GGUF file. Its input must be the verified artifact
above.

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

The D64 always contains the executable and archive runtime/text files. It contains the 48 original model packet files only when the complete verified `build/layers/` set was supplied. See [`D64_MANIFEST.md`](D64_MANIFEST.md) for the disk layout and [`STAGE_HISTORY.md`](STAGE_HISTORY.md) for proof boundaries and historical stage notes.
