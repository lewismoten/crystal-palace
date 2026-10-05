"""Static GitHub Pages asset-editor contract."""
import json
from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_asset_studio_manifest_declares_editable_c64_sources():
    manifest = json.loads((ROOT / "asset-studio.json").read_text())
    assert manifest["version"] == 1
    assert manifest["palette"]["colors"][0] == "#000000"
    assert {editor["kind"] for editor in manifest["editors"]} == {
        "glyph-atlas", "petscii-screen", "multicolor-bitmap", "mark", "markdown", "layout"
    }
    assert any(editor["id"] == "info" and editor["image"] == "assets/info/image.png" for editor in manifest["editors"])
    assert manifest["charsets"][0]["sources"] == ["assets/title/image.png", "assets/info/image.png"]
    assert manifest["charsets"][0]["id_order"] == "assets/charset/id-order.json"


def test_root_page_loads_the_generic_asset_studio():
    page = (ROOT / "index.html").read_text()
    assert '<script type="module" src="web/studio.js"></script>' in page
    assert '<link rel="icon" href="favicon.ico" sizes="any">' in page
    assert 'asset-studio.json' in page
    assert 'Glyph atlas' in page
    assert 'IMAGE SOURCES → DERIVED CHARSET / MAPS · 256-GLYPH GUARD' in page
    assert 'Multicolor bitmap' in page



def test_asset_studio_png_decoder_compares_the_binary_signature_without_utf8_decoding():
    script = (ROOT / "web" / "studio.js").read_text()
    assert "data[0] !== 137" in script
    assert "decode.decode(data.slice(0, 8))" not in script


def test_asset_studio_screen_editor_uses_a_selected_cell_with_glyph_and_color_inspection():
    script = (ROOT / "web" / "studio.js").read_text()
    assert "let selectedCell = 0" in script
    assert "Selected glyph" in script
    assert "Click a glyph to apply it to the selected screen cell." in script
    assert "applyTile(image, selectedCell, current.mask, state.color)" in script
    assert "drawScreen(canvas, model, map, 2)" in script


def test_asset_studio_board_paint_uses_scaled_y_coordinate_and_mutates_a_visible_pixel():
    script = (ROOT / "web" / "studio.js").read_text()
    assert "let mode = 'paint', slot = 3" in script
    assert "y = Math.floor(py / 2)" in script
    assert "selectors.pixels[y * 160 + x] = slot" in script
    assert "[null, high, low, ram][slot].pixels[cell] = state.color" in script


def test_asset_studio_styles_keep_character_screens_at_gameplay_scale():
    stylesheet = (ROOT / "web" / "studio.css").read_text()
    assert ".screen-canvas { width: 640px; }" in stylesheet


def test_asset_studio_launcher_disables_browser_asset_caching():
    launcher = (ROOT / "scripts" / "serve_asset_studio.py").read_text()
    assert 'Cache-Control' in launcher
    assert 'no-store, max-age=0' in launcher
    assert 'choices=("start", "stop", "status")' in launcher
    assert 'PID_FILE' in launcher
