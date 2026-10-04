# C64 Asset Studio

The root [`index.html`](../index.html) is a static editor that works on GitHub
Pages and can also write to a local checkout in browsers that support the File
System Access API.

## Open it

For GitHub Pages, publish the repository root and visit `/index.html`.

For local work:

```sh
python3 scripts/serve_asset_studio.py start --port 8042
```

Then open `http://127.0.0.1:8042/`. The launcher binds only to loopback and
sends `Cache-Control: no-store, max-age=0` for the page and ES modules.

## Local files and downloads

- **Repository files** is read-only browser mode. Changes remain in memory
  until **Download active file** saves the current PNG, JSON, or Markdown file.
- **Open local project** lets Chromium-family browsers choose a local checkout.
  Subsequent **Download active file** actions write the active changed source
  file back into that selected directory instead of downloading it.
- A static GitHub Pages site cannot commit directly to Git. Review downloaded
  files, then commit them normally.

The editor writes indexed PNGs with the manifest palette and unfiltered rows.
Run the normal project validation after an edit:

```sh
.venv/bin/python scripts/compile_c64_assets.py
.venv/bin/python scripts/render_screen_states.py --check
.venv/bin/python -m pytest -q
```

## Generic manifest

`asset-studio.json` is the site contract. It declares:

- the native C64 palette;
- shared glyph atlases and their dimensions;
- PETSCII glyph/color maps and optional selection deltas;
- multicolor bitmap selector/color planes and logical size;
- reusable marks;
- Markdown sources and viewport dimensions; and
- JSON layout sources and editor overlays.

A different project can reuse the editor by placing equivalent indexed PNG/JSON
sources in its published tree and replacing paths, sizes, and editor entries in
the manifest. No project-specific build server or JavaScript framework is
required.

## Editors

| Editor | Source it changes | Immediate review |
| --- | --- | --- |
| Glyph atlas | `charset/atlas.png` | Glyph usage count across the declared character screens; every shared glyph redraws in those screens. |
| PETSCII screen | glyph and color maps | 40×25 custom-charset screen. Click sets a glyph; Shift-click sets a cell color. |
| Multicolor bitmap | selector, screen-high, screen-low, Color RAM planes | 160×200 logical-pixel board; click changes a 2-bit selector or a 4×8 cell’s local color. |
| X / O marks | mark PNG | 14×24 logical-pixel color grid. |
| INFO Markdown | `archive.md` | A 29×18 INFO viewport preview with scroll position. The Python compiler remains the final runtime authority. |
| Layout | board layout JSON or manifest layouts | Board A–I rectangles, INFO text viewport, and title selection rows. |

The editor does not run the C64 emulator yet. Its manifest and layout paths are
intended to make an emulator panel an additive future page rather than a second
asset definition.
