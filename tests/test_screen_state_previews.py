import importlib.util
import struct
from pathlib import Path


ROOT = Path(__file__).parents[1]
ASSETS = ROOT / "assets"
SCRIPT = ROOT / "scripts" / "render_screen_states.py"


def renderer():
    spec = importlib.util.spec_from_file_location("render_screen_states", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def png_chunks(data: bytes):
    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    offset = 8
    while offset < len(data):
        size = struct.unpack(">I", data[offset : offset + 4])[0]
        name = data[offset + 4 : offset + 8]
        payload = data[offset + 8 : offset + 8 + size]
        yield name, payload
        offset += 12 + size


def test_screen_state_previews_are_reproducible_indexed_c64_pngs():
    module = renderer()
    assert len(module.STATES) == 6
    assert len(module.DERIVED_VIEWS) == 9
    expected_palette = bytes(component for rgb in module.C64_PALETTE for component in rgb)

    for path, expected in module.expected_images().items():
        content = path.read_bytes()
        chunks = dict(png_chunks(content))
        width, height, depth, color_type, compression, filtering, interlace = struct.unpack(">IIBBBBB", chunks[b"IHDR"])
        assert (width, height, depth, color_type, compression, filtering, interlace) in {
            (320, 200, 8, 3, 0, 0, 0),
            (128, 128, 8, 3, 0, 0, 0),
        }
        assert chunks[b"PLTE"] == expected_palette
        assert content == expected


def test_screen_state_markdown_documents_png_sources_and_reviewed_final_screens():
    readme = (ASSETS / "README.md").read_text()
    assert "`assets/` is the editable visual source" in readme
    assert "Generated\nC64 planes are ignored" in readme
    assert "color type 3 (indexed)" in readme
    assert "glyph-map.png" in readme
    assert "bitmap-selectors.png" in readme
    assert "320×200 physical pixels" in readme
    documented = {"atlas.png", "preview.png", "glyphs.png", "colors.png"}

    assert documented <= {path.name for path in renderer().expected_images()}
    for name in documented:
        assert name in readme


def test_authored_repository_writing_uses_us_english():
    forbidden = tuple(word + suffix for word in ("colo", "Colo", "COLO") for suffix in ("ur", "urs")) + tuple(word + suffix for word in ("gre", "Gre", "GRE", "cent", "Cent", "CENT") for suffix in ("y", "re"))
    roots = (ROOT / "assets", ROOT / "docs", ROOT / "scripts", ROOT / "src", ROOT / "tests")
    text_files = [ROOT / "README.md"]
    for root in roots:
        text_files.extend(path for path in root.rglob("*") if path.suffix in {".asm", ".inc", ".json", ".md", ".py", ".sh", ".txt"})
    for path in text_files:
        assert not any(word in path.read_text() for word in forbidden), path
