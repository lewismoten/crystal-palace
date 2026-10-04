# Assets

`assets/` is the editable visual source for Crystal Palace 9. Every PNG is an
8-bit indexed image using the native 16-color Pepto C64 palette. Generated
C64 planes are ignored under `build/assets/`; the compiler checks their sizes
and SHA-256 values against `manifest.json`.

```sh
python3 scripts/compile_c64_assets.py
python3 scripts/render_screen_states.py --check
.venv/bin/python scripts/build_disk.py
```

## Title and INFO screens

`charset/atlas.png` is the shared 16×16 custom-character atlas. Title and INFO
screens use it through explicit `glyph-map.png` and `color-map.png` files, so
the review images are reproducible from editable source data. Each character
screen also has generated `glyphs.png` and `colors.png` inspection views.

| Title screen | INFO screen after entry |
| --- | --- |
| ![Player-one title preview](title/one/preview.png) | ![INFO preview with runtime footer](info/preview.png) |

The INFO preview includes the entered runtime footer, `SCROLL: UP/DOWN  QUIT: Q`.
It does not preserve the obsolete `SPACE: CONTINUE` artwork from the supplied
frame.

## Game board and marks

`game/board/` contains the fixed blank-board source planes:

- `bitmap-selectors.png` — 2-bit multicolor bitmap selectors.
- `screen-hi.png` and `screen-lo.png` — the two screen-memory color nibbles.
- `color-lo.png` — the Color RAM nibble.
- `preview.png` — the final 320×200 VIC-II rendering.

| Fixed board | Mark review |
| --- | --- |
| ![Blank board preview](game/board/preview.png) | ![Alternating X and O mark preview](game/marks/preview.png) |

`game/marks/x.png` and `game/marks/o.png` are the only editable mark sources.
They are **14×24 logical multicolor pixels**. VIC-II expands each logical pixel
to two horizontal physical pixels, so the marks display at 28×24 on the C64.
They use the shared black background plus two mark colors while preserving the
grid's local color slot.

| Editable X source | Editable O source |
| --- | --- |
| ![Logical X source](game/marks/x.png) | ![Logical O source](game/marks/o.png) |

The compiler stamps these two images into the named A–I rectangles from
`layout/board.json`, then derives ignored bitmap, screen, Color RAM, and
per-cell runtime patch planes. A separate all-X or all-O editable source image
is not needed.

## Other sources

- `archive/archive.md` — readable source text packaged as `ARCHIVE.MD`.
- `layout/board.json` — game-cell placement geometry.
- `manifest.json` — generated-plane size and digest contract.

## PNG requirements

PNGs must use color type 3 (indexed), 8-bit depth, no interlacing, and the
exact 16-entry Pepto C64 palette. Palette index values are VIC-II color IDs.
The normal game review is 320×200 physical pixels, representing a 160×200
multicolor logical-pixel grid.
