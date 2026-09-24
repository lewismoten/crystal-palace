# CP64

CP64 is a Commodore 64 feasibility project for **the original Crystal-9 packed INT4 neural network**. It does not use a move table, a hand-coded tic-tac-toe policy, or distilled replacement weights.

## Current executable milestone

`build/cp64.d64` is a runnable C64 disk with an **original attention query, key, and value proof gate**. It loads the original `embedding.weight` packet (`C9W00.PRG`) into `$c000`; for a selected `a`–`i` token it materializes 32 signed Q8.8 values at `$c100`. It then pages the original `position.weight` packet (`C9W01.PRG`), adds the matching position row, retains that 32-value input, and pages the original first-attention input-projection packet (`C9W02.PRG`). The 6502 materializes C9W02's original query rows at `$c740`, key rows at `$c780`, and value rows at `$c800`. All packets retain their original FP16 scale bytes and packed INT4 payloads.

This is not yet a model move. The next gate is the causal-attention path. It must not be represented as a tic-tac-toe-playing model until the 6502 evaluator is implemented and compared with Crystal-9's reference outputs.

## Model provenance

- Source: `~/crystal-9/releases/huggingface-int4-v1/artifacts/crystal-9-int4-group2-packed-fp16-scales-v1.pt`
- Source SHA-256: `63eee663a143ee478308144da406873c72c05b6d5226dbb2f5e329dacb1392eb`
- Source format: `crystal-9-packed-int4-fp16-scales-v1`
- Export: 48 packets, 13,938 bytes of original FP16 scale bytes plus packed INT4 bytes
- Packet format: `C9W1`, tensor ID, little-endian scale length, little-endian packed length, verbatim scales, verbatim INT4 payload

Each packet is a PRG whose two-byte load address is `$c000`; therefore the C64 KERNAL loader pages one original tensor into a fixed RAM window without reserving all model data in RAM.

## Build

```sh
cd ~/cp64
scripts/bootstrap_64tass.sh
~/crystal-9/.venv/bin/python scripts/export_c64_layers.py --output build/layers
python3 scripts/build_disk.py
python3 -m pytest tests -q
```

The result is `build/cp64.d64`. Each proof gate is also preserved under a sequentially numbered filename:

```text
build/cs64-008-test-position-embedding.d64
build/cs64-009-test-original-attention-query.d64
build/cs64-010-test-original-attention-key.d64
build/cs64-011-test-original-attention-value.d64
```

`cp64.d64` is a compatibility copy of the current numbered gate. A number is reserved only after its gate builds and passes its reference tests.

### Stage 011 acceptance

Assembled-6502 Py65 regression tests compare all nine materialized position rows, all nine token-plus-position vectors, and all 32 query, key, and value projection values for every mapped playable input against independent fixed-point reference calculations over verbatim `C9W00`, `C9W01`, and `C9W02` packet bytes. A separate weighted query checksum is retained by the 6502 for every input.

To run it in VICE, attach/autostart `cs64-011-test-original-attention-value.d64` with a C64 ROM set supplied by your emulator installation. Enter `A` through `I` after the ready prompt; the selected token is paired with position `0` through `8` respectively. This gate computes the corresponding original query, key, and value vectors; the Py65 suite is its exact parity oracle.

### Browser test target

The manual acceptance target is [C64 Online Emulator](https://c64online.com/c64-online-emulator/). Use its **Load Program** control to select the numbered `.d64` artifact; it accepts D64 files directly. This project treats a user-reported matching result from that emulator as a separate browser-emulator confirmation in addition to the assembled-6502 regression suite.

## Next proof gates

1. Implement causal score, masking, softmax, and attention output from the original query, key, and value vectors.
2. Implement LayerNorm, router top-2 selection, only the selected expert tensors, and output logits.
3. Feed legal move histories from the C64 game loop and compare every C64 prediction against the packed Python reference runtime.
4. Run exhaustive legal-history parity before claiming the C64 can play tic-tac-toe with Crystal-9.

The direct original packed tensor payload is small enough for the disk and for a single `$c000` layer window. The open engineering question is 6502 inference time and numerical parity, not whether the original packed weights can be stored and paged.

## Repository layout

- `src/cp64.asm` — C64 pager and direct VRAM status code
- `scripts/export_c64_layers.py` — lossless original-tensor exporter
- `scripts/make_d64.py` — tested multi-file D64 writer
- `scripts/build_disk.py` — assemble and package the disk
- `tests/` — D64 and packet-format tests
