# CP64

CP64 is a Commodore 64 feasibility project for **the original Crystal-9 packed INT4 neural network**. It does not use a move table, a hand-coded tic-tac-toe policy, or distilled replacement weights.

## Current executable milestone

`build/cp64.d64` is a runnable C64 disk with a bounded **two-token attention, LayerNorm-affine, and router top-2 gate**. For `A`→`B`, it materializes all eight original C9W02 attention heads under the fixed-point two-key causal-softmax contract, applies original C9W04/C9W05 output projection and bias, adds the retained input residual, completes the fixed-point LayerNorm contract, pages C9W08/C9W09 to calculate all nine original router logits, and retains the greatest two logits with their original expert indices. All packets retain their original FP16 scale bytes and packed INT4 payloads.

This is not yet a model move. Router normalization, selected expert execution, residuals, and output logits remain. It must not be represented as a tic-tac-toe-playing model until the 6502 evaluator is implemented and compared with Crystal-9's reference outputs.

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
build/cs64-015-fix-token-packet-reload.d64
build/cs64-016-fix-selected-token-after-load.d64
build/cs64-017-show-inference-progress.d64
build/cs64-018-show-attention-query-checksum.d64
build/cs64-020-show-single-token-attention-output.d64
build/cs64-021-test-two-key-softmax.d64
build/cs64-022-test-two-key-second-attention-head.d64
build/cs64-023-split-inference-progress-stages.d64
build/cs64-024-combine-two-attention-heads.d64
build/cs64-025-combine-all-attention-heads.d64
build/cs64-026-attention-output-projection.d64
build/cs64-027-attention-output-bias.d64
build/cs64-028-attention-residual.d64
build/cs64-029-norm-weight-paging.d64
build/cs64-030-norm-bias-paging.d64
build/cs64-031-layer-norm-centering.d64
build/cs64-032-layer-norm-variance.d64
build/cs64-033-layer-norm-affine.d64
build/cs64-034-router-projection.d64
build/cs64-035-router-bias.d64
build/cs64-036-router-top2.d64
build/cs64-037-router-normalization.d64
```

`cp64.d64` is a compatibility copy of the current numbered gate. A number is reserved only after its gate builds and passes its reference tests.

### Stage 014 acceptance

Assembled-6502 Py65 regression tests compare all nine materialized position rows, all nine token-plus-position vectors, all 32 query, key, and value projection values, and all eight scaled Q·K self-attention scores for every mapped playable input against independent fixed-point reference calculations over verbatim `C9W00`, `C9W01`, and `C9W02` packet bytes. The stage-014 regression independently generates token `a` at position 0, `b` at position 1, and `c` at position 2 from those same packet bytes, retains all three key vectors, and verifies that the middle query row contains all eight original `b`→`a` and `b`→`b` scores while all eight `b`→`c` entries are the fixed `$8000` causal-mask marker.

To exercise the stage-014 parity gate, run `./.venv/bin/pytest tests/test_6502_embedding_gate.py::test_6502_three_token_causal_score_row_keeps_prior_original_keys -q`. To load the disk in VICE, attach/autostart `cs64-014-test-three-token-causal-attention-mask.d64` with a C64 ROM set supplied by your emulator installation; enter `A` through `I` for the preceding single-token materialization gate. The Py65 regression is the exact three-token causal-mask oracle.

### Stage 018 browser-emulator acceptance

`cs64-018-show-attention-query-checksum.d64` reloads the original token packet for each request, preserves the selected token across KERNAL disk loads, and provides immediate six-step status output for the token, position, Q, K, V, and attention-score work. It reports an input-dependent attention-Q checksum after the work completes. On C64 Online Emulator, the user verified all A–I checksums against the independent packed-byte reference values: `0035`, `F758`, `03F3`, `E529`, `3E4C`, `2CBF`, `DD6C`, `E627`, and `E84F`.

### Stage 020 browser-emulator acceptance

`cs64-020-show-single-token-attention-output.d64` performs the exact degenerate causal-softmax case: one visible key has probability 1, so the attended vector is an exact copy of the original projected V vector. It displays a checksum over the retained attended Q8.8 vector. On C64 Online Emulator, the expected attended-output checksum matched.

### Stage 021 two-key softmax proof

`cs64-021-test-two-key-softmax.d64` retains original Q/K/V vectors for the bounded sequence `A` at position 0 followed by `B` at position 1. For head 0 it materializes the two visible causal scores, derives normalized Q0.15 weights from their Q8.8 delta, and applies them to four original projected V lanes. Enter `A`, wait for completion, then enter `B`. The expected final attended-output checksum is `5979`; the user confirmed that C64 Online Emulator displayed `$5979`. The independent 6502 reference also verifies scores `[3, 28]`, weights `[15585, 17183]`, and output `[1791, 2985, 1336, 2784]`. This is an explicitly bounded CP64 fixed-point contract, not a claim of source-FP32 bit parity.

### Stage 022 second-head two-key softmax proof

`cs64-022-test-two-key-second-attention-head.d64` repeats the accepted `A`, then `B` sequence but evaluates head 3 rather than head 0. It retains the original projected vectors, derives weights from head-3 causal scores `[-84, -58]`, and applies them to that head’s four original V lanes. The expected final attended-output checksum is `AA36`; the user confirmed that C64 Online Emulator displayed `$AA36`. The assembled-6502 reference gives output `[1113, -2072, 191, -643]` with Q0.15 weights `[15553, 17215]`.

### Stage 023 split inference progress

`cs64-023-split-inference-progress-stages.d64` keeps the accepted head-3 computation but replaces the misleading six-step display with eight real boundaries: token embedding, position embedding, Q, K, V, K/V-history retention, self-attention-score materialization, and causal softmax plus attended-V output.

### Stage 024 combined two-head attention output

`cs64-024-combine-two-attention-heads.d64` retains the same original `A`→`B` two-key sequence and combines both previously proved attention slices into one attended vector: head 0 occupies lanes 0–3 and head 3 occupies lanes 12–15; all other lanes remain zero in this bounded gate. The expected final checksum is `03AF`; browser-emulator parity was confirmed. Its nine progress messages separately identify the two actual head-output computations.

### Stage 025 all-head attention output

`cs64-025-combine-all-attention-heads.d64` uses the same original `A`→`B` two-key sequence but now emits the 32-lane attended vector from all eight original attention heads. The bounded Q0.15 two-key softmax remains an explicitly fixed-point proof approximation; the projected Q/K/V vectors and packed tensors remain original source data. The expected final checksum is `FFA0`; browser-emulator parity was confirmed with all sixteen displayed work stages.

### Stage 026 attention output projection

`cs64-026-attention-output-projection.d64` pages original `C9W04` after the all-head two-key attention vector is materialized, then applies its 32 original packed INT4 output-projection rows. This gate intentionally excludes the separate original `C9W05` output bias, which is the next mathematical component. For `A`→`B`, expected projected-output checksum is `CE3E`; browser-emulator parity was confirmed with all eighteen displayed work stages.

### Stage 027 attention output bias

`cs64-027-attention-output-bias.d64` preserves stage 026's all-head `A`→`B` output-projection result, then pages original `C9W05`. Its one FP16 scale and 32 packed INT4 bias codes are materialized as signed Q8.8 and added lane-wise to the projected output. The assembled-6502 regression compares all 32 final lanes with an independent calculation over the verbatim C9W05 packet. The expected final checksum is `BEEE`; browser-emulator parity was confirmed. This remains a bounded attention-block proof, not full model inference or a policy move.

### Stage 028 attention residual

`cs64-028-attention-residual.d64` preserves the original token-plus-position hidden state before paging C9W04, then adds that retained state lane-wise after the C9W04 projection and C9W05 bias. For the live `A`→`B` sequence, the expected residual-output checksum is `FF9E`. The two added messages distinguish residual retention from its later addition; no new tensor is introduced at this gate.

### Stage 029 norm-weight paging

`cs64-029-norm-weight-paging.d64` pages original `C9W06` and materializes its 32 norm-affine weights from 16 original FP16 scales and 16 packed INT4 bytes, with one scale assigned to each original pair of lanes. This is a source-byte and 6502-vector gate for the next LayerNorm tensor; it does **not** claim to execute LayerNorm yet. Its fixed Q8.8 norm-weight checksum is `E4D4`; browser-emulator parity was confirmed.

### Stage 030 norm-bias paging

`cs64-030-norm-bias-paging.d64` retains Stage 029's C9W06 norm-weight proof, then pages original `C9W07` and materializes its one-FP16-scale, 32-value packed-INT4 norm-bias vector. The fixed Q8.8 norm-weight and norm-bias checksums are `E4D4` and `051C` for both `A` and `B`; browser-emulator parity was confirmed. The attended-output checksum is input-sequence-specific: the live `A`→`B` value is `FF9E`, and it is not an expected value for the initial `A`. This completes paging and decoding the two original LayerNorm affine tensors; centering, variance, reciprocal-square-root, and affine application remain the next gate.

### Stage 031 LayerNorm centering

`cs64-031-layer-norm-centering.d64` introduced signed 32-bit mean accumulation and symmetric mean rounding, then retains `x - mean` for all 32 lanes. Its documented `6AAA` checksum belongs to the isolated arithmetic fixture retained in the regression suite; it is not a live A→B browser-sequence oracle.

### Stage 032 LayerNorm variance bundle

`cs64-032-layer-norm-variance.d64` adds unsigned 32-bit Q16.16 sum-of-squares and nearest division by 32. It preserves the original C9W06/C9W07 paging proofs but does not yet apply the affine transform.

### Stage 033 LayerNorm affine bundle

`cs64-033-layer-norm-affine.d64` completes this bounded fixed-point LayerNorm contract for the live `A`→`B` sequence: 32-bit centering and variance, epsilon `$00000001` Q16.16, nearest integer square root, symmetric Q8.8 normalization, and original packed C9W06 gamma/C9W07 beta affine application. Its assembled-6502 live-path regression asserts residual `$FF9E`, mean `-711`, variance `$06C97ECE`, stddev `$29AF`, normalized checksum `$DF93`, static original gamma/beta checksums `$E4D4`/`$051C`, and final affine checksum `$FCBF`. Browser-emulator parity is confirmed for `$29AF`, `$DF93`, and `$FCBF`. This is LayerNorm only; routing and expert execution remain unimplemented.

### Stage 034 router-weight projection

`cs64-034-router-projection.d64` retains the Stage 033 `A`→`B` LayerNorm-affine output, pages original C9W08, and projects all nine original packed-INT4 router-weight rows. The assembled-6502 regression compares each Q8.8 logit with an independent calculation over verbatim C9W08 bytes: `[-839, 1559, 9, -228, 1324, -381, -613, -1574, 878]` (weighted checksum `$F34B`). This gate excludes C9W09 router bias and does not select an expert.

### Stage 035 router bias

`cs64-035-router-bias.d64` retains Stage 034's nine C9W08 projections, pages original C9W09, materializes exactly its nine tensor-scale packed-INT4 bias lanes, and adds them to the retained Q8.8 router logits. The assembled-6502 regression compares every final lane against an independent reference over the verbatim C9W08 and C9W09 packet bytes. This completes raw router-logit construction only; it does not select or execute an expert.

### Stage 036 router top-2

`cs64-036-router-top2.d64` retains Stage 035's nine original router logits and selects the largest two signed Q8.8 values, retaining each value and its source expert index. The assembled-6502 regression derives the Stage 035 logits from verbatim C9W09 bias bytes and asserts the selected indices and values. This is selection only: router normalization and selected-expert execution remain out of scope.

### Stage 037 router normalization

`cs64-037-router-normalization.d64` normalizes Stage 036's two selected original C9W08/C9W09 router logits for the bounded live `A`→`B` path. It subtracts the lower selected Q8.8 logit from the higher, then looks up `round(sigmoid(delta / 256) * 32768)` in a checked Q0.15 table covering deltas 0 through 8.0 (larger deltas saturate at the 8.0 endpoint); the complementary Q0.15 weight is exactly `32768 - top1`. The assembled-6502 regression pages and decodes verbatim C9W09 bytes, produces the two selected logits, and independently checks the resulting weights against `exp`. The C64 display visibly runs 32/37 through 37/37 and reports `ROUTER TOP-1 EXPERT E1 WEIGHT Q0.15 $630F` and `ROUTER TOP-2 EXPERT E4 WEIGHT Q0.15 $1CF1`. These are bounded CP64 router weights—not original packed-runtime routing parity—and no expert tensor is yet paged or executed.

### Stage 043 raw bounded next-token argmax

`cs64-043-raw-bounded-next-token-argmax.d64` continues the live bounded `A`→`B` route through selected original E1/E4 affine tensors, the declared Q8.8 SiLU and Q0.15 merge contracts, a post-MoE residual, then original C9W46 (13-by-32 output head) and C9W47 (13-lane bias). It displays real steps 38/43 through 43/43 and a lower-index-first signed-Q8.8 raw argmax token index. Browser-emulator parity is confirmed: the live route reports `$08`, which is vocabulary token `e`. This is a bounded CP64 fixed-point output, not original packed-runtime or playable-policy parity.

### Stage 044 predicted-token embedding feedback

`cs64-044-predicted-token-embedding-feedback.d64` preserves Stage 043's bounded live `A`→`B` raw argmax, then genuinely reloads verbatim original C9W00 after the output packets have replaced the disk window. It uses the raw output index directly as the original embedding row, decodes its FP16 row scale and all 32 original packed INT4 codes, and displays the input-dependent predicted-token embedding checksum. For `A`→`B`, the raw index remains `$08` (the established `e` vocabulary row) and C9W00 row 8 materializes to checksum `$889C`. This proves disk/RAM feedback materialization only—not a third live forward pass, original-runtime parity, or a playable policy.

### Stage 045 A→B output boundary

`cs64-045-a-then-b-output-boundary.d64` corrects Stage 044's interactive boundary. The proof is specifically the live `A`→`B` route: after `A`, CP64 retains original K/V history, reports `A RETAINED. TYPE B TO RUN THE A->B PROOF.`, and returns to input without emitting an output token. Only then does `B` run the two-key bounded route through the existing output argmax and predicted-token feedback gates. Browser-emulator acceptance confirmed that `A` stops at the retention boundary and `B` produces the expected result. This prevents a misleading one-key result from being presented beside the accepted A→B output.

### Stage 046 three-token legal-history boundary

`cs64-046-three-token-legal-history.d64` is the earliest bounded browser sequence beyond the accepted A→B route. Enter `A`, then `B`, then `C`, waiting for each real tensor-page/projection pass. The program retains each projected original C9W02 K/V page in a contiguous explicit history buffer, reports the required next input after A and B, then displays `A,B,C RETAINED. THREE-KEY K/V HISTORY READY.` after C. The assembled-6502 parity test compares all 192 retained key bytes and all 192 retained value bytes across the live three-call state machine, while the wider suite keeps independent original packed-byte references for token, position, and attention materialization. This is a three-token pageable-history proof only: it deliberately does not claim a three-key softmax, forward pass, argmax, or prediction.

### Stage 047 graphical three-token history

`cs64-047-graphical-three-token-history.d64` keeps Stage 046's source-bound A→B→C history boundary and normal character-mode operation. It adds a direct-screen PETSCII 3×3 board; only accepted legal A, B, and C history inputs mark their cells. Its seven-cell progress segment advances immediately before each actual embedding page, position page, Q projection, K projection, V projection, K/V retention, and self-score computation—not on simulated timer ticks. After C it reports only measured state: history length `$03`, plus 16-bit byte sums over the 192 retained key bytes and 192 retained value bytes. It neither calculates nor claims a tic-tac-toe policy or a model prediction.

### Stage 048 fixed dashboard history

`cs64-048-fixed-dashboard-history.d64` fixes the Stage 047 browser scrolling regression. Once the board activates, accepted-token status, real work-stage text, and retained-history diagnostics are written directly to fixed screen and color-RAM panel slots; no interactive status or diagnostic path streams through KERNAL `CHROUT`. The board, seven real-work progress cells, status row, and diagnostic row retain explicit light-green color writes. Enter `A`, then `B`, then `C`: the fixed panel ends with `A,B,C RETAINED: HISTORY READY` and `LENGTH $03 KEY SUM $47A0 VALUE $` followed by the measured value sum. This remains a pageable three-token K/V-history proof, not a model prediction or playable policy.

### Stage 049 full-progress dashboard history

`cs64-049-full-progress-dashboard-history.d64` corrects the Stage 048 meter scale. The fixed 28-cell graphical meter assigns four cells to each of the seven real page/compute boundaries, so it reaches 100% at every A, B, and C retained-history boundary. It preserves Stage 048's direct screen/color-RAM dashboard: no scrolling status stream, no color inheritance, and end diagnostics remain fixed. This is still only a pageable three-token K/V-history proof, not a model prediction or playable policy.

### Stage 050 clean centered dashboard history

`cs64-050-clean-centered-dashboard-history.d64` clears the KERNAL loading/title screen and its color RAM before activating the direct-screen dashboard, then redraws the title, prompt, grid, progress meter, status, and diagnostics only in fixed panel slots. It also centers the first-column move markers within their cells. No pre-load text remains behind the grid.

### Browser test target

The manual acceptance target is [C64 Online Emulator](https://c64online.com/c64-online-emulator/). Use its **Load Program** control to select the numbered `.d64` artifact; it accepts D64 files directly. This project treats a user-reported matching result from that emulator as a separate browser-emulator confirmation in addition to the assembled-6502 regression suite.

## Next proof gates

1. Page and execute only the two selected original expert tensors before output logits.
2. Feed legal move histories from the C64 game loop and compare every C64 prediction against the packed Python reference runtime.
3. Run exhaustive legal-history parity before claiming the C64 can play tic-tac-toe with Crystal-9.

The direct original packed tensor payload is small enough for the disk and for a single `$c000` layer window. The open engineering question is 6502 inference time and numerical parity, not whether the original packed weights can be stored and paged.

## Repository layout

- `src/cp64.asm` — C64 pager and direct VRAM status code
- `scripts/export_c64_layers.py` — lossless original-tensor exporter
- `scripts/make_d64.py` — tested multi-file D64 writer
- `scripts/build_disk.py` — assemble and package the disk
- `tests/` — D64 and packet-format tests
