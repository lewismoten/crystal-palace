# CP64 D64 manifest

The release disk intentionally contains only the executable and the 48 immutable original Crystal-9 tensor packets. Title, INFO, game-room, charset, and cell-patch planes are embedded byte-for-byte in `CP64.PRG`; they are documented in [`assets/crystal-palace-screen-states/README.md`](../assets/crystal-palace-screen-states/README.md) and are not duplicated as unused disk files.

| Directory entry | Count | Purpose |
| --- | ---: | --- |
| `CP64.PRG` | 1 | Browser-facing presentation/game executable: title, INFO viewer, bitmap board, supplied visual planes, and narrowly bounded original-weight bridge code. It is deliberately the first directory entry and allocated nearest track 18. |
| `C9W00.PRG`–`C9W47.PRG` | 48 | Verbatim original packed Crystal-9 tensor packets. `C9W00.PRG` is the embedding packet; later numbered packets are router, expert, projection, normalization, and output tensors according to their immutable packet headers. They are never regenerated, distilled, or requantized by the C64 build. |

## Disk layout rules

- Standard 35-track 1541 D64: 174,848 bytes.
- Track 18 sector 0 is the BAM; only directory sectors that are actually linked are marked allocated.
- No file chain may use track 18.
- `CP64.PRG` stays first in the directory and begins on track 17, directly adjacent to the directory track.
- File allocation alternates outward from track 18 (`17`, `19`, `16`, `20`, …) with rotational sector interleaving. This avoids the old all-from-track-1 allocation order and distributes reads across both sides of the directory track.
- Release validation checks declared chains, duplicate sector references, track-18 misuse, DOS type `2A`, and BAM sectors marked used without a reachable BAM/directory/file claim.

`python3 scripts/build_disk.py` creates the numbered image. The image itself is ignored by Git; source, build scripts, tests, and this manifest are versioned.
