# Crystal Palace 64 (CP64)

![Crystal Palace 9](./docs/social-preview.jpg)

A Commodore 64 feasibility project for evaluating **the original Crystal-9 packed INT4 neural-network weights** from a 1541 disk. CP64 does not replace the network with a move table, a hand-authored tic-tac-toe policy, distilled weights, or requantized weights.

The executable is an engineering preview, not a claim of finished playable model parity. It combines source-exact Crystal Palace screen art with bounded, source-byte-backed Crystal-9 proof gates.

## Current milestone — Stage 086

`cs64-086-browser-verified-title-radar-blackout.d64` is the current locally built image. Opening **INFO** performs the only presentation-side KERNAL load: it reads `ARCHIVE.PRG` into the volatile `$c000` window, validates its `ARCV` header/version/line geometry, then copies its character and colour planes into the fixed INFO RAM ranges. A failed or mismatched archive returns safely to the title instead of rendering stale RAM. Normal A–I board input does not load from disk. The exact eight radar-label cells visibly rendered by C64 Online as Y/4/4/7 are made black in derived runtime title planes before the first screen copy; the supplied source planes remain unchanged.

The D64 also includes `ARCHIVE.MD` as a sequential (`SEQ`) file. It is the authored, disk-readable Markdown source for the compiled viewer payload; edit it, then rebuild. The runtime reads `ARCHIVE.PRG`, not Markdown text, because the 6502 viewer needs bounded custom-charset character and colour planes.

The local board preview renders player marks and terminal states, but it does not claim a model-driven AI turn. Full legal-history model gameplay remains unestablished.

## Required resources

### Repository tools

The documented commands assume a Debian/Ubuntu-like host with:

- `python3` (3.11 or newer recommended), `python3-venv`, and `pip`
- `apt` and `dpkg-deb` for the reproducible local 64tass bootstrap
- Internet access the first time `scripts/bootstrap_64tass.sh` downloads the Debian `64tass` package

Create the development test environment:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
scripts/bootstrap_64tass.sh
```

`requirements-dev.txt` pins `py65` for assembled-6502 regression tests. The bootstrap script extracts 64tass beneath `tools/64tass/`; it does not install a system-wide assembler.

### Crystal-9 model artifact

Building a full D64 requires the original Crystal-9 artifact and a Python environment that can import `torch`. Obtain the artifact from the Crystal-9 release resource and retain its original bytes at:

```text
~/crystal-9/releases/huggingface-int4-v1/artifacts/crystal-9-int4-group2-packed-fp16-scales-v1.pt
```

Expected source SHA-256:

```text
63eee663a143ee478308144da406873c72c05b6d5226dbb2f5e329dacb1392eb
```

The exporter accepts another location with `--artifact`; it reads the artifact with `torch.load(..., weights_only=True)` and emits 48 `C9Wxx.PRG` files without changing the source FP16-scale or packed-INT4 bytes.

```sh
~/crystal-9/.venv/bin/python scripts/export_c64_layers.py \
  --artifact /absolute/path/to/crystal-9-int4-group2-packed-fp16-scales-v1.pt \
  --output build/layers
```

The `torch` installation belongs to the Crystal-9 environment, not CP64's small test environment. Do not substitute a different model, quantization, or regenerated packet set.

## Build and verify

From a checkout with the source art already present under `assets/crystal-palace-screen-states/`:

```sh
cd ~/cp64
scripts/bootstrap_64tass.sh
~/crystal-9/.venv/bin/python scripts/export_c64_layers.py \
  --artifact ~/crystal-9/releases/huggingface-int4-v1/artifacts/crystal-9-int4-group2-packed-fp16-scales-v1.pt \
  --output build/layers
.venv/bin/python scripts/render_screen_states.py --check
.venv/bin/python scripts/build_disk.py
.venv/bin/python -m pytest -q
```

`scripts/build_disk.py` regenerates `src/info_markdown.inc` and `build/ARCHIVE.PRG` from `assets/crystal-palace-screen-states/ARCHIVE.md`, assembles `CP64.PRG`, packages the D64, validates its DOS chains, and writes both the numbered Stage 085 image and `build/cp64.d64`.

Generated `.d64`, PRG, layer, and virtual-environment outputs are intentionally ignored by Git.

## Disk and model provenance

- Source format: `crystal-9-packed-int4-fp16-scales-v1`
- Model transport: 48 `C9Wxx.PRG` packets, each loaded at `$c000` with a small `C9W1` transport header followed by unchanged source FP16 scales and packed INT4 bytes
- Archive transport: `ARCHIVE.PRG`, loaded only when INFO opens; `ARCHIVE.MD` is its readable SEQ source document
- A KERNAL load replaces the `$c000` load window. CP64 pages one artifact at a time and does not claim full-model RAM residency.

See [`docs/D64_MANIFEST.md`](docs/D64_MANIFEST.md) for the exact 51-file disk layout and allocation rules.

## Screen-state source art

The raw VIC-II planes and matching C64-indexed PNG review images live in [`assets/crystal-palace-screen-states/`](assets/crystal-palace-screen-states/README.md). The binary planes are authoritative; PNGs are reproducible 320×200 indexed-palette renders for review and documentation.

| Preview | State |
| --- | --- |
| ![One-player Crystal Palace title](assets/crystal-palace-screen-states/crystal-palace-title-player-1.png) | One-player title selection |
| ![Crystal Palace blank game room](assets/crystal-palace-screen-states/crystal-palace-game-blank.png) | Native blank multicolour playfield |

## Documentation

- [Stage history and proof boundaries](docs/STAGE_HISTORY.md)
- [D64 file manifest and allocation rules](docs/D64_MANIFEST.md)
- [Crystal Palace screen-state files, previews, palette, and VIC-II layout](assets/crystal-palace-screen-states/README.md)
- [Browser acceptance target: C64 Online Emulator](https://c64online.com/c64-online-emulator/)

## Repository layout

- `src/` — 6502 assembly and generated INFO-viewer constants.
- `scripts/build_disk.py` — assembler/D64 packaging entry point.
- `scripts/compile_info_markdown.py` — Markdown-to-runtime-payload compiler.
- `scripts/export_c64_layers.py` — original Crystal-9 packet exporter (requires `torch`).
- `scripts/render_screen_states.py` — dependency-free indexed PNG renderer.
- `assets/crystal-palace-screen-states/` — source-exact native art planes and `ARCHIVE.md`.
- `tests/` — packet, disk, assembly, VIC-layout, renderer, and archive regressions.
