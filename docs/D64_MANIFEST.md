# CP64 D64 manifest

The release disk intentionally contains only the executable and the 48 immutable original Crystal-9 tensor packets. Title, INFO, game-room, charset, and cell-patch planes are embedded byte-for-byte in `CP64.PRG`; they are documented in [`assets/crystal-palace-screen-states/README.md`](../assets/crystal-palace-screen-states/README.md) and are not duplicated as unused disk files.

| Directory entry | Count | Purpose |
| --- | ---: | --- |
| `CP64.PRG` | 1 | Browser-facing presentation/game executable: title, INFO viewer, bitmap board, supplied visual planes, and narrowly bounded original-weight bridge code. It is deliberately the first directory entry and allocated nearest track 18. |
| `C9W00.PRG`–`C9W47.PRG` | 48 | Verbatim original packed Crystal-9 tensor packets. The exact directory ranges are listed below. They are never regenerated, distilled, or requantized by the C64 build. |

## Crystal-9 packet directory map

Every `C9Wxx.PRG` has the same small transport wrapper: PRG load address `$c000`; `C9W1` magic; packet ID; FP16-scale byte count; packed-INT4 byte count; then the **unchanged** source scale and packed-weight bytes. The C64 uses the numeric filename as the immutable packet ID; it is not a hand-assigned game lookup table.

| Directory range | Crystal-9 tensor(s) | What it does |
| --- | --- | --- |
| `C9W00.PRG` | `embedding.weight` — 13 × 32 | Token embedding table. It maps the model vocabulary tokens, including board-cell tokens, into 32 lanes. |
| `C9W01.PRG` | `position.weight` — 9 × 32 | Position embedding table. The nine rows correspond to positions in the bounded tic-tac-toe history. |
| `C9W02.PRG` | `attention.in_proj_weight` — 96 × 32 | Joined attention input projection. Rows 0–31 are **Query (Q)**, 32–63 are **Key (K)**, and 64–95 are **Value (V)**. |
| `C9W03.PRG` | `attention.in_proj_bias` — 96 | Biases in the same Q / K / V order: 0–31 Q, 32–63 K, 64–95 V. |
| `C9W04.PRG`–`C9W05.PRG` | `attention.out_proj.weight`, `attention.out_proj.bias` | Attention output projection: turns the merged attention result back into the 32-lane model stream. |
| `C9W06.PRG`–`C9W07.PRG` | `norm.weight`, `norm.bias` | LayerNorm affine parameters: gamma/weight and beta/bias for the 32-lane stream. |
| `C9W08.PRG`–`C9W09.PRG` | `router.weight`, `router.bias` — 9 outputs | MoE router. It produces one logit per expert, then the runtime selects the eligible top experts according to its declared bounded route. |
| `C9W10.PRG`–`C9W13.PRG` | `experts.0.{0,2}.{weight,bias}` | **Expert 0**: first affine weight/bias, then second affine weight/bias. |
| `C9W14.PRG`–`C9W17.PRG` | `experts.1.{0,2}.{weight,bias}` | **Expert 1**: same four-packet layout. |
| `C9W18.PRG`–`C9W21.PRG` | `experts.2.{0,2}.{weight,bias}` | **Expert 2**. |
| `C9W22.PRG`–`C9W25.PRG` | `experts.3.{0,2}.{weight,bias}` | **Expert 3**. |
| `C9W26.PRG`–`C9W29.PRG` | `experts.4.{0,2}.{weight,bias}` | **Expert 4**. |
| `C9W30.PRG`–`C9W33.PRG` | `experts.5.{0,2}.{weight,bias}` | **Expert 5**. |
| `C9W34.PRG`–`C9W37.PRG` | `experts.6.{0,2}.{weight,bias}` | **Expert 6**. |
| `C9W38.PRG`–`C9W41.PRG` | `experts.7.{0,2}.{weight,bias}` | **Expert 7**. |
| `C9W42.PRG`–`C9W45.PRG` | `experts.8.{0,2}.{weight,bias}` | **Expert 8**. There are nine experts total: 0 through 8. |
| `C9W46.PRG`–`C9W47.PRG` | `output.weight`, `output.bias` — 13 outputs | Final output head. It turns the final 32-lane state into one logit per 13-token vocabulary entry. A legal tic-tac-toe move still requires masking special/occupied tokens before choosing a cell. |

### Expert packet pattern

For every expert **N** from 0 through 8, the directory is regular:

| Packet | Tensor |
| --- | --- |
| `C9W(10 + 4N).PRG` | `experts.N.0.weight` |
| `C9W(11 + 4N).PRG` | `experts.N.0.bias` |
| `C9W(12 + 4N).PRG` | `experts.N.2.weight` |
| `C9W(13 + 4N).PRG` | `experts.N.2.bias` |

The `.0` and `.2` names are the original sequential-module parameter names. In plain language, each expert has a first 32×32 affine transform and bias, an activation between them, then a second 32×32 affine transform and bias. No packet name claims an invented expert role beyond that original structure.

## Disk layout rules

- Standard 35-track 1541 D64: 174,848 bytes.
- Track 18 sector 0 is the BAM; only directory sectors that are actually linked are marked allocated.
- No file chain may use track 18.
- `CP64.PRG` stays first in the directory and begins on track 17, directly adjacent to the directory track.
- File allocation alternates outward from track 18 (`17`, `19`, `16`, `20`, …) with rotational sector interleaving. This avoids the old all-from-track-1 allocation order and distributes reads across both sides of the directory track.
- Release validation checks declared chains, duplicate sector references, track-18 misuse, DOS type `2A`, and BAM sectors marked used without a reachable BAM/directory/file claim.

`python3 scripts/build_disk.py` creates the numbered image. The image itself is ignored by Git; source, build scripts, tests, and this manifest are versioned.
