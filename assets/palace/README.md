# Palace assets

`assets/palace/` contains editable, indexed C64-palette PNG sources. No C64
binary plane is committed. `scripts/compile_c64_assets.py` rebuilds the ignored
planes under `build/palace-assets/` and checks every result against
`manifest.json` (sizes and SHA-256 digests).

## Layout

- `charset/atlas.png` — 16×16 shared 8×8 glyph atlas; black/white bits.
- `title/{auto,one,two}/` — each title mode has `glyph-map.png` and
  `color-map.png` sources plus deterministic `preview.png`, `glyphs.png`, and
  `colors.png` review images.
- `info/` — the INFO frame has the same `glyph-map.png`, `color-map.png`,
  `preview.png`, `glyphs.png`, and `colors.png` structure.
- `game/board/` — the fixed blank board: explicit bitmap-selector and local
  colour-nibble PNG planes, plus final `preview.png`.
- `game/marks/x.png` and `game/marks/o.png` — the only editable mark art.
  They are 28×24 final physical-pixel images (black transparent background;
  light-red X or cyan O foreground). The compiler stamps each mark at A–I,
  preserves the grid, and derives transient per-cell patch bins.
- `game/reference/all-x.png` and `game/reference/all-o.png` — deterministic
  full-board verification renders, not editable input planes.
- `layout/board.json` — named board placement rectangles.
- `archive/archive.md` — disk-readable INFO text source.

## Why there is no `all-x.bitmap-selectors.png`

The prior all-X/all-O selector planes were an unnecessary intermediate source.
A C64 mark cannot be copied as one byte-identical patch at every A–I position:
the board positions cross different bitmap-byte and character-cell boundaries.
The compiler now takes the one X or O image, stamps it into the blank board at
each named rectangle, and remaps a grid cell's local selectors only where a
mark shares that cell. The generated all-X/all-O planes and live cell patches
remain byte-identical to the reviewed native reference digests.

## PNG contract

Every PNG is colour type 3 (indexed), 8-bit, non-interlaced, and uses the
16-entry Pepto C64 palette with index values equal to VIC-II colour IDs. The
final game review is 320×200 physical pixels. Its intentionally wide pixels
are native VIC-II multicolour bitmap pixels: a 160×200 logical grid with each
logical pixel two physical pixels wide.

```sh
python3 scripts/compile_c64_assets.py
python3 scripts/render_screen_states.py --check
.venv/bin/python scripts/build_disk.py
```
