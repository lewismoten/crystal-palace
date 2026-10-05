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


def test_character_screens_are_derived_from_image_sources_with_one_shared_charset(tmp_path: Path):
    compiler = load_compiler()
    compiler.compile_assets(ASSETS, tmp_path)
    assert {"title/image.png", "info/image.png"} <= set(compiler.SOURCE_PNGS)
    assert not any("glyph-map.png" in path or "color-map.png" in path or "charset/atlas.png" in path for path in compiler.SOURCE_PNGS)
    assert not (ASSETS / "charset" / "atlas.png").exists()
    assert not (ASSETS / "title" / "glyph-map.png").exists()
    assert not (ASSETS / "info" / "glyph-map.png").exists()
    assert compiler.shared_glyph_count(ASSETS) <= 256
    selection = json.loads((ASSETS / "title" / "selection.json").read_text())
    assert selection["base"] == "one"
    assert selection["marker"]["source_cell"] == [9, 9]
    assert selection["highlight"] == {"active_color": 7, "inactive_color": 13}
    assert selection["states"] == {
        "one": {"row": 9, "hotkey_column": 11, "text_start_column": 13, "text_width": 12},
        "two": {"row": 11, "hotkey_column": 11, "text_start_column": 13, "text_width": 16},
        "auto": {"row": 13, "hotkey_column": 11, "text_start_column": 13, "text_width": 8},
    }



def test_character_screens_preserve_the_checked_in_charset_id_order(tmp_path):
    compiler = load_compiler()
    output = tmp_path / "generated"
    compiler.compile_assets(ASSETS, output)
    order = json.loads((ASSETS / "charset" / "id-order.json").read_text())
    assert (output / "charset.bin").read_bytes() == b"".join(bytes.fromhex(mask) for mask in order["glyph_masks_hex"])



def test_stable_charset_order_assigns_a_duplicate_slot_to_a_new_glyph():
    compiler = load_compiler()
    order = compiler.charset_id_order(ASSETS)
    mask = next(bytes((value,) * 8) for value in range(1, 256) if bytes((value,) * 8) not in order)
    pixels = bytearray(320 * 200)
    for y, pattern in enumerate(mask):
        for x in range(8):
            if pattern & (0x80 >> x):
                pixels[y * 320 + x] = 1
    image = compiler.IndexedPNG(320, 200, compiler.C64_PALETTE, bytes(pixels))
    charset, screens, _ = compiler.compile_character_images({"new": image}, order)
    glyph = screens["new"][0]
    assert glyph in [index for index, value in enumerate(order) if order.index(value) != index]
    assert charset[glyph * 8:glyph * 8 + 8] == mask


def test_info_image_source_contains_entered_footer_and_initial_scrollbar(tmp_path: Path):
    compiler = load_compiler()
    compiler.compile_assets(ASSETS, tmp_path)
    screen = (tmp_path / "info/screen.bin").read_bytes()
    color = (tmp_path / "info/color.bin").read_bytes()
    source = compiler.read_indexed_png(ASSETS / "info" / "image.png")
    charset = (tmp_path / "charset.bin").read_bytes()
    rendered = bytearray(320 * 200)
    for cell in range(1000):
        row, column = divmod(cell, 40)
        for y in range(8):
            pattern = charset[screen[cell] * 8 + y]
            for x in range(8):
                if pattern & (0x80 >> x):
                    rendered[(row * 8 + y) * 320 + column * 8 + x] = color[cell]
    assert bytes(rendered) == source.pixels
    footer = 23 * 40 + 4
    assert screen[footer + 6] and screen[footer + 14] and screen[footer + 22]
    assert color[footer + 6] == 12 and color[footer + 14] == 1 and color[footer + 22] == 12
    scrollbar = [row * 40 + 34 for row in range(4, 22)]
    assert screen[scrollbar[0]] and all(screen[cell] for cell in scrollbar[1:])
    assert [color[cell] for cell in scrollbar] == [7] + [11] * 17


def test_character_image_overflow_reports_the_shared_charset_group(tmp_path: Path):
    compiler = load_compiler()
    image = compiler.read_indexed_png(ASSETS / "info" / "image.png")
    payload = bytearray(image.pixels)
    for cell in range(257):
        row, column = divmod(cell, 40)
        for y in range(8):
            for x in range(8):
                payload[(row * 8 + y) * 320 + column * 8 + x] = 1 if (cell >> (x + y * 8)) & 1 else 0
    synthetic = compiler.IndexedPNG(image.width, image.height, image.palette, bytes(payload))
    try:
        compiler.compile_character_images({"overflow": synthetic})
    except ValueError as error:
        assert "shared charset group" in str(error)
        assert "reduce" in str(error)
    else:
        raise AssertionError("expected a shared-charset overflow")
