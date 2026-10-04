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
    assert any(editor["id"] == "info" and editor["glyph_map"] == "assets/info/glyph-map.png" for editor in manifest["editors"])
    assert any(editor["id"] == "board" and editor["layout"] == "assets/game/board/layout.json" for editor in manifest["editors"])


def test_root_page_loads_the_generic_asset_studio():
    page = (ROOT / "index.html").read_text()
    assert '<script type="module" src="web/studio.js"></script>' in page
    assert 'asset-studio.json' in page
    assert 'Glyph atlas' in page
    assert 'Multicolor bitmap' in page


def test_asset_studio_launcher_disables_browser_asset_caching():
    launcher = (ROOT / "scripts" / "serve_asset_studio.py").read_text()
    assert 'Cache-Control' in launcher
    assert 'no-store, max-age=0' in launcher
    assert 'choices=("start", "stop", "status")' in launcher
    assert 'PID_FILE' in launcher
