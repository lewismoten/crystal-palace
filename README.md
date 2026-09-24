# CP64

CP64 is a Commodore 64 feasibility project for **the original Crystal-9 packed INT4 neural network**. It does not use a move table, a hand-coded tic-tac-toe policy, or distilled replacement weights.

## Current executable milestone

`build/cp64.d64` is a runnable C64 disk with the first **real packed-neural computation gate**. It loads the original `embedding.weight` packet (`C9W00.PRG`) into `$c000`. When the user types `a`–`i`, the 6502 code selects that source embedding row, unpacks all 32 signed INT4 values, and computes the 16-bit checksum `Σ(position × INT4_code)`. The matching Python reference is `scripts/embedding_probe.py`.

This is not yet a model move. The next gate is applying each row's original FP16 scale, then retaining the fixed-point embedding vector for the causal-attention path. It must not be represented as a tic-tac-toe-playing model until the 6502 evaluator is implemented and compared with Crystal-9's reference outputs.

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

The result is `build/cp64.d64`.

To run it in VICE, attach/autostart the disk with a C64 ROM set supplied by your emulator installation. The program displays `48 PACKED TENSORS READ FROM DISK` after its paging pass.

## Next proof gates

1. Implement 6502 fixed-point decoding of the original FP16 scales and packed signed INT4 codes.
2. Implement the actual Crystal-9 forward path: embeddings, causal attention, LayerNorm, router top-2 selection, only the selected expert tensors, and output logits.
3. Feed legal move histories from the C64 game loop and compare every C64 prediction against the packed Python reference runtime.
4. Run exhaustive legal-history parity before claiming the C64 can play tic-tac-toe with Crystal-9.

The direct original packed tensor payload is small enough for the disk and for a single `$c000` layer window. The open engineering question is 6502 inference time and numerical parity, not whether the original packed weights can be stored and paged.

## Repository layout

- `src/cp64.asm` — C64 pager and direct VRAM status code
- `scripts/export_c64_layers.py` — lossless original-tensor exporter
- `scripts/make_d64.py` — tested multi-file D64 writer
- `scripts/build_disk.py` — assemble and package the disk
- `tests/` — D64 and packet-format tests
