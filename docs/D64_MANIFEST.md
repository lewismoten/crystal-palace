# CP64 D64 manifest

The release disk intentionally contains only the executable and the 48 immutable original Crystal-9 tensor packets. Title, INFO, game-room, charset, and cell-patch planes are embedded byte-for-byte in `CP64.PRG`; they are documented in [`assets/crystal-palace-screen-states/README.md`](../assets/crystal-palace-screen-states/README.md) and are not duplicated as unused disk files.

| Directory entry | Count | Purpose |
| --- | ---: | --- |
| `CP64.PRG` | 1 | Browser-facing presentation/game executable: title, INFO viewer, bitmap board, supplied visual planes, and narrowly bounded original-weight bridge code. It is deliberately the first directory entry and allocated nearest track 18. |
| Descriptive model packets | 48 | Verbatim original packed Crystal-9 tensor packets with readable 1541 directory names. The exact directory ranges are listed below. They are never regenerated, distilled, or requantized by the C64 build. |

## Crystal-9 packet directory map

Every model packet has the same small transport wrapper: PRG load address `$c000`; `C9W1` magic; immutable packet ID; FP16-scale byte count; packed-INT4 byte count; then the **unchanged** source scale and packed-weight bytes. The readable disk filename is only a directory label; packet identity remains inside the packet.

| Directory range | Crystal-9 tensor(s) | What it does |
| --- | --- | --- |
| `EMBEDTOK.PRG` | `embedding.weight` — 13 × 32 | Token embedding table. It maps the model vocabulary tokens, including board-cell tokens, into 32 lanes. |
| `POSITN9.PRG` | `position.weight` — 9 × 32 | Position embedding table. The nine rows correspond to positions in the bounded tic-tac-toe history. |
| `ATTNQKVW.PRG` | `attention.in_proj_weight` — 96 × 32 | Joined attention input projection. Rows 0–31 are **Query (Q)**, 32–63 are **Key (K)**, and 64–95 are **Value (V)**. |
| `ATTNQKVB.PRG` | `attention.in_proj_bias` — 96 | Biases in the same Q / K / V order: 0–31 Q, 32–63 K, 64–95 V. |
| `ATTNOUTW.PRG` / `ATTNOUTB.PRG` | `attention.out_proj.weight`, `attention.out_proj.bias` | Attention output projection. |
| `NORMGAM.PRG` / `NORMBET.PRG` | `norm.weight`, `norm.bias` | LayerNorm gamma/weight and beta/bias. |
| `ROUTERW.PRG` / `ROUTERB.PRG` | `router.weight`, `router.bias` — 9 outputs | MoE router: one logit per expert. |
| `EX0L1W.PRG`–`EX8L2B.PRG` | `experts.0` through `experts.8` | Nine experts; each has L1 weight/bias and L2 weight/bias. The exact four-file pattern is below. |
| `OUTHEADW.PRG` / `OUTHEADB.PRG` | `output.weight`, `output.bias` — 13 outputs | Final output head; legal selection must still mask special/occupied tokens. |

### Expert packet pattern

For every expert **N** from 0 through 8, the directory is regular:

| Packet | Tensor |
| --- | --- |
| `EXNL1W.PRG` | `experts.N.0.weight` |
| `EXNL1B.PRG` | `experts.N.0.bias` |
| `EXNL2W.PRG` | `experts.N.2.weight` |
| `EXNL2B.PRG` | `experts.N.2.bias` |

The `.0` and `.2` names are the original sequential-module parameter names. In plain language, each expert has a first 32×32 affine transform and bias, an activation between them, then a second 32×32 affine transform and bias. No packet name claims an invented expert role beyond that original structure.

### Source-packet provenance IDs

The original short IDs are retained here only for byte-level provenance and developer cross-reference; they do **not** appear beside the readable directory range above.

| Source packet IDs | Disk directory names |
| --- | --- |
| `C9W00–01` | `EMBEDTOK.PRG`, `POSITN9.PRG` |
| `C9W02–03` | `ATTNQKVW.PRG`, `ATTNQKVB.PRG` |
| `C9W04–05` | `ATTNOUTW.PRG`, `ATTNOUTB.PRG` |
| `C9W06–07` | `NORMGAM.PRG`, `NORMBET.PRG` |
| `C9W08–09` | `ROUTERW.PRG`, `ROUTERB.PRG` |
| `C9W10–45` | `EX0L1W.PRG` through `EX8L2B.PRG` |
| `C9W46–47` | `OUTHEADW.PRG`, `OUTHEADB.PRG` |

## Disk layout rules

- Standard 35-track 1541 D64: 174,848 bytes.
- Track 18 sector 0 is the BAM; only directory sectors that are actually linked are marked allocated.
- No file chain may use track 18.
- `CP64.PRG` stays first in the directory and begins on track 17, directly adjacent to the directory track.
- File allocation alternates outward from track 18 (`17`, `19`, `16`, `20`, …) with rotational sector interleaving. This avoids the old all-from-track-1 allocation order and distributes reads across both sides of the directory track.
- Release validation checks declared chains, duplicate sector references, track-18 misuse, DOS type `2A`, and BAM sectors marked used without a reachable BAM/directory/file claim.

`python3 scripts/build_disk.py` creates the numbered image. The image itself is ignored by Git; source, build scripts, tests, and this manifest are versioned.
