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
  until **Save active file** downloads the current PNG, JSON, or Markdown file.
- **Open local project** lets Chromium-family browsers choose a local checkout.
  Edits then auto-save to the corresponding file in that selected directory;
  **Save active file** remains available as an explicit retry. The status line
  reports `Saved path` or a concrete write error.
- A static GitHub Pages site cannot commit directly to Git. Review downloaded
  files, then commit them normally.

The editor writes indexed PNGs with the manifest palette and unfiltered rows.
After `scripts/bootstrap.sh`, regenerate every derived asset and release image:

```sh
scripts/build_all.sh
```

Run the regression suite separately when changing code or build logic:

```sh
.venv/bin/python -m pytest -q
```

## Generic manifest

`asset-studio.json` is the site contract. It declares:

- the native C64 palette;
- shared character-screen image sources and their dimensions;
- PETSCII source images and optional semantic selection metadata;
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
| Glyph atlas | title and INFO `image.png` files | The atlas is derived from the editable title and INFO images. Editing a glyph updates every matching 8×8 source-image cell; usage is counted across the declared shared group. |
| PETSCII screen | character-screen `image.png` | 40×25 custom-charset screen. Click a cell to inspect it, toggle its visible outline, choose a glyph/color, or use arrow keys in the glyph map to preview candidates before Enter commits one. The compiler rebuilds glyph/color maps. |
| Multicolor bitmap | selector, screen-high, screen-low, Color RAM planes | 160×200 logical-pixel board; click changes a 2-bit selector or a 4×8 cell’s local color. |
| X / O marks | mark PNG | 14×24 logical-pixel color grid. |
| INFO Markdown | `archive.md` | A 29×18 INFO viewport preview with scroll position. The Python compiler remains the final runtime authority. |
| Layout | board layout JSON or manifest layouts | Board A–I rectangles, INFO text viewport, and title selection rows. |

The shared character-screen group is limited to **256 unique glyphs**. The
Asset Studio reports an error when an edit would exceed that limit; reduce
unique masks or split screens into separate charset groups. `id_order` can
optionally preserve legacy C64 code positions without retaining visual atlas
art. The atlas and screen maps remain derived build artifacts, so the
repository intentionally does not contain `charset/atlas.png` or
`glyph-map.png` source files.

The editor does not run the C64 emulator yet. Its manifest and layout paths are
intended to make an emulator panel an additive future page rather than a second
asset definition.
