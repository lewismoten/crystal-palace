# Crystal Palace PNG asset sources

This directory is PNG-first. The committed, editable sources are indexed PNGs
using the fixed 16-entry C64/Pepto palette. C64 `.bin` planes are **not** kept
in Git: `scripts/compile_c64_assets.py` regenerates them under
`build/generated-assets/` immediately before preview rendering, assembly, and
D64 packaging. `asset-manifest.json` records the original native plane sizes
and SHA-256 digests; compilation fails if an edit changes a C64 byte without
updating that reviewed manifest.

## Shared glyph system

`crystal-palace-charset-charmap.png` is the editable 16×16 atlas of all 256
8×8 custom glyphs. Black is a clear bit and white is a set bit. It compiles to
the 2,048-byte character set used by both title and INFO states.

Each title/INFO state is assembled from that same atlas:

- `crystal-palace-<state>.glyph-map.png` is 80×25 indexed pixels. Two C64
  palette indices encode each 8-bit glyph ID: high nibble, then low nibble.
- `crystal-palace-<state>.color-map.png` is 40×25 indexed pixels. Its index is
  the colour-RAM nibble for the corresponding glyph cell.
- The 320×200 `<state>.png`, `.screen-mono.png`, and `.color-plane.png` files
  are deterministic review renderings. They make the final result and its two
  native planes visible without introducing another source of truth.

Primary review files are `crystal-palace-title-player-1.png`,
`crystal-palace-title-player-1.screen-mono.png`,
`crystal-palace-title-player-1.color-plane.png`, `crystal-palace-info.png`,
`crystal-palace-info.screen-mono.png`, and
`crystal-palace-info.color-plane.png`.

## Final game screen and multicolour sources

`crystal-palace-game-{blank,all-x,all-o}.png` is the final 320×200 screen
review used to inspect the real playfield composition. It is intentionally
wide-looking at the pixel level: VIC-II multicolour bitmap mode has a 160×200
logical grid and each logical pixel occupies two physical horizontal pixels.
It is not a scaled substitute for the game screen.

The three final game reviews are `crystal-palace-game-blank.png`,
`crystal-palace-game-all-x.png`, and `crystal-palace-game-all-o.png`.

A final rendered game PNG cannot recover C64 bitmap planes uniquely: the same
visible colour can come from local selector `01`, `10`, or `11`. Therefore the
editable exact source is deliberately explicit for each game state:

| Source PNG | Dimensions | Meaning |
| --- | ---: | --- |
| `*.bitmap-selectors.png` | 160×200 | Literal bitmap selectors 0–3, packed four per output bitmap byte. |
| `*.screen-hi.png` | 40×25 | High nibble of each screen-RAM byte. |
| `*.screen-lo.png` | 40×25 | Low nibble of each screen-RAM byte. |
| `*.color-lo.png` | 40×25 | Colour-RAM low nibble; high nibble is fixed to zero. |

All four PNGs use the C64 palette; their palette index is the stored native
value. The compiler packs them to the 8,000-byte bitmap and two 1,000-byte
planes. The all-X/all-O states also derive transient per-cell X/O bitmap,
screen, colour, and destination-address planes used by the live game.

## C64 palette

Every source and review PNG is colour type 3 (indexed), 8 bits per index,
non-interlaced, with exactly this native-index palette:

| Index | Colour | RGB |
| ---: | --- | --- |
| 0 | Black | `#000000` |
| 1 | White | `#ffffff` |
| 2 | Red | `#68372b` |
| 3 | Cyan | `#70a4b2` |
| 4 | Purple | `#6f3d86` |
| 5 | Green | `#588d43` |
| 6 | Blue | `#352879` |
| 7 | Yellow | `#b8c76f` |
| 8 | Orange | `#6f4f25` |
| 9 | Brown | `#433900` |
| 10 | Light red | `#9a6759` |
| 11 | Dark grey | `#444444` |
| 12 | Medium grey | `#6c6c6c` |
| 13 | Light green | `#9ad284` |
| 14 | Light blue | `#6c5eb5` |
| 15 | Light grey | `#959595` |

## Build and verify

```sh
python3 scripts/compile_c64_assets.py
python3 scripts/render_screen_states.py --check
.venv/bin/python scripts/build_disk.py
```

The first command creates ignored `build/generated-assets/**/*.bin` outputs.
The renderer recompiles from PNGs and confirms every checked-in 320×200 review
image is byte-exact. The D64 build also runs the compiler before 64tass.
