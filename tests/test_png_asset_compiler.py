"""PNG-source C64 asset compiler coverage."""
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
ASSETS = ROOT / "assets"


def load_compiler():
    spec = importlib.util.spec_from_file_location("compile_c64_assets", ROOT / "scripts" / "compile_c64_assets.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_png_sources_compile_to_the_declared_c64_plane_digests(tmp_path: Path):
    compiler = load_compiler()
    compiler.compile_assets(ASSETS, tmp_path)

    manifest = json.loads((ASSETS / "manifest.json").read_text())
    for relative_path, expected in manifest["generated_bins"].items():
        payload = (tmp_path / relative_path).read_bytes()
        assert len(payload) == expected["bytes"], relative_path
        assert hashlib.sha256(payload).hexdigest() == expected["sha256"], relative_path


def test_png_sources_are_indexed_c64_palette_assets():
    compiler = load_compiler()
    for source in compiler.SOURCE_PNGS:
        image = compiler.read_indexed_png(ASSETS / source)
        assert image.palette == compiler.C64_PALETTE


def test_mark_sources_use_logical_multicolor_pixels_and_allow_two_ink_colors():
    compiler = load_compiler()
    for mark in ("x", "o"):
        image = compiler.read_indexed_png(ASSETS / "game" / "marks" / f"{mark}.png")
        assert (image.width, image.height) == (14, 24)
        assert 1 < len({value for value in image.pixels if value}) <= 2


def test_title_uses_one_editable_base_and_small_selection_deltas(tmp_path: Path):
    compiler = load_compiler()
    compiler.compile_assets(ASSETS, tmp_path)
    assert {"title/glyph-map.png", "title/color-map.png"} <= set(compiler.SOURCE_PNGS)
    assert not any(path.startswith("title/one/") or path.startswith("title/two/") or path.startswith("title/auto/") for path in compiler.SOURCE_PNGS)
    selection = json.loads((ASSETS / "title" / "selection.json").read_text())
    assert selection["base"] == "one"
    assert {state: (len(data["screen"]), len(data["color"])) for state, data in selection["states"].items()} == {
        "one": (0, 0), "two": (2, 30), "auto": (2, 22)
    }


def test_info_source_maps_contain_entered_footer_and_initial_scrollbar(tmp_path: Path):
    compiler = load_compiler()
    compiler.compile_assets(ASSETS, tmp_path)
    screen = (tmp_path / "info/screen.bin").read_bytes()
    color = (tmp_path / "info/color.bin").read_bytes()
    footer = 23 * 40 + 4
    assert screen[footer : footer + 35] == bytes((0, 0, 0, 0, 0, 0, 19, 3, 18, 15, 12, 12, 38, 0, 21, 16, 41, 4, 15, 23, 14, 0, 17, 21, 9, 20, 38, 0, 17, 0, 0, 0, 0, 0, 0))
    assert color[footer : footer + 35] == bytes((0, 0, 0, 0, 0, 0, 12, 12, 12, 12, 12, 12, 12, 12, 1, 1, 1, 1, 1, 1, 1, 0, 12, 12, 12, 12, 12, 12, 1, 0, 0, 0, 0, 0, 0))
    scrollbar = [row * 40 + 34 for row in range(4, 22)]
    assert [screen[cell] for cell in scrollbar] == [42] + [46] * 17
    assert [color[cell] for cell in scrollbar] == [7] + [11] * 17
