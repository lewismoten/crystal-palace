# Crystal Palace screen states

This directory contains the source-exact VIC-II planes used by the CP64 embedded-art presentation, plus reproducible indexed PNG previews for review. **The `.bin` planes are authoritative.** The PNGs are derived documentation artifacts and are never loaded by the C64 program.

## Preview gallery

### Title states — standard character mode

| One player | Two players | AI vs AI |
| --- | --- | --- |
| ![One-player title](crystal-palace-title-player-1.png) | ![Two-player title](crystal-palace-title-player-2.png) | ![AI-vs-AI title](crystal-palace-title-player-0.png) |

All title variants use the shared [`crystal-palace-charset.bin`](crystal-palace-charset.bin), one 1,000-byte screen plane, and one 1,000-byte colour plane. The highlighted row differs by selection state.

### Archive / information — standard character mode

![Crystal Palace archive screen](crystal-palace-info.png)

`crystal-palace-info.screen.bin` and `crystal-palace-info.color.bin` share the title charset. They must be restored with that charset after leaving bitmap mode.

### Playfield states — multicolour bitmap mode

| Blank board | Source all-X reference | Source all-O reference |
| --- | --- | --- |
| ![Blank playfield](crystal-palace-game-blank.png) | ![All X playfield](crystal-palace-game-all-x.png) | ![All O playfield](crystal-palace-game-all-o.png) |

The all-X and all-O planes are source references for extracting exact live-cell patches. They are not whole-frame replacements during normal play.

## Raw plane contract

| State type | Files | VIC-II mode / address expectation |
| --- | --- | --- |
| Title variants | `title-player-{0,1,2}.{screen,color}.bin` | Standard character mode; screen `$0400`, colour RAM `$d800`, charset `$3800`. |
| Archive/info | `info.{screen,color}.bin` | Standard character mode; same screen, colour, and charset locations. |
| Game states | `game-{blank,all-x,all-o}.{bitmap,screen,color}.bin` | Multicolour bitmap mode; 8,000-byte bitmap, 1,000-byte screen plane, 1,000-byte colour plane; background `$d021 = 0` (black). |
| Live patches | `cells/{x,o}-cells.{bitmap,screen,color}.bin` plus `cells/bitmap-destination-addresses.bin` | Exact per-cell deltas in real VIC bitmap-address order, not a linear raster-byte order. |

Every title/info screen or colour plane is 1,000 bytes. Each game bitmap plane is 8,000 bytes; each accompanying screen/colour plane is 1,000 bytes. `crystal-palace-board-coordinates.json` defines the board-cell locations used to derive the live patch artifacts.

## Indexed PNG contract

The seven `*.png` review images are exactly **320×200**, PNG colour type **3** (indexed), 8 bits per palette index, with a 16-entry C64 palette. No alpha channel, RGB conversion, or palette quantization is used.

Palette indices equal native VIC-II colour codes. The renderer uses the Pepto C64 RGB presentation palette:

| Index | VIC-II colour | RGB |
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

For multicolour bitmap previews, each 2-bit logical VIC pixel is doubled horizontally. The resulting 320×200 image retains the C64’s physical display pixel grid while representing a 160×200 multicolour logical grid.

## Rebuild and verify previews

The renderer uses Python’s standard library only:

```sh
python3 scripts/render_screen_states.py
python3 scripts/render_screen_states.py --check
```

`--check` regenerates every preview in memory and fails when any checked-in PNG differs. This makes the documentation previews reproducible from the raw source planes and guards against a silent palette, layout, or format change.
