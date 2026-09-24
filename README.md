# CP64

CP64 is a Commodore 64 feasibility project for **the original Crystal-9 packed INT4 neural network**. It does not use a move table, a hand-coded tic-tac-toe policy, or distilled replacement weights.

## Current executable milestone

`build/cp64.d64` is a runnable C64 disk with a **three-token causal-attention mask proof gate**. It retains three original C9W02 key vectors at `$c880`, materializes the middle query's eight four-wide Q·K / sqrt(4) scores for each key at `$c940`, and writes signed Q8.8 `$8000` for all eight future-key entries. Its query and key vectors are materialized from the original `embedding.weight` (`C9W00.PRG`), `position.weight` (`C9W01.PRG`), and first-attention input-projection (`C9W02.PRG`) packets. All packets retain their original FP16 scale bytes and packed INT4 payloads.

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
build/cs64-012-test-original-self-attention-score.d64
build/cs64-013-test-two-token-causal-attention-mask.d64
build/cs64-014-test-three-token-causal-attention-mask.d64
```

`cp64.d64` is a compatibility copy of the current numbered gate. A number is reserved only after its gate builds and passes its reference tests.

### Stage 014 acceptance

Assembled-6502 Py65 regression tests compare all nine materialized position rows, all nine token-plus-position vectors, all 32 query, key, and value projection values, and all eight scaled Q·K self-attention scores for every mapped playable input against independent fixed-point reference calculations over verbatim `C9W00`, `C9W01`, and `C9W02` packet bytes. The stage-014 regression independently generates token `a` at position 0, `b` at position 1, and `c` at position 2 from those same packet bytes, retains all three key vectors, and verifies that the middle query row contains all eight original `b`→`a` and `b`→`b` scores while all eight `b`→`c` entries are the fixed `$8000` causal-mask marker.

To exercise the stage-014 parity gate, run `./.venv/bin/pytest tests/test_6502_embedding_gate.py::test_6502_three_token_causal_score_row_keeps_prior_original_keys -q`. To load the disk in VICE, attach/autostart `cs64-014-test-three-token-causal-attention-mask.d64` with a C64 ROM set supplied by your emulator installation; enter `A` through `I` for the preceding single-token materialization gate. The Py65 regression is the exact three-token causal-mask oracle.

### Browser test target

The manual acceptance target is [C64 Online Emulator](https://c64online.com/c64-online-emulator/). Use its **Load Program** control to select the numbered `.d64` artifact; it accepts D64 files directly. This project treats a user-reported matching result from that emulator as a separate browser-emulator confirmation in addition to the assembled-6502 regression suite.

## Next proof gates

1. Extend causal score materialization from the three-token mask gate, then implement fixed-point softmax and attention output from the original query, key, and value vectors.
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
