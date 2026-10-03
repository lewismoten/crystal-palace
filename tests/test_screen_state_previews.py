import importlib.util
import struct
from pathlib import Path


ROOT = Path(__file__).parents[1]
ASSETS = ROOT / "assets" / "crystal-palace-screen-states"
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
    assert len(module.STATES) == 7
    expected_palette = bytes(component for rgb in module.C64_PALETTE for component in rgb)

    for name, render in module.STATES.items():
        content = (ASSETS / name).read_bytes()
        chunks = dict(png_chunks(content))
        assert chunks[b"IHDR"] == struct.pack(">IIBBBBB", 320, 200, 8, 3, 0, 0, 0)
        assert chunks[b"PLTE"] == expected_palette
        assert content == module.indexed_png(render())


def test_screen_state_markdown_documents_every_preview_and_raw_contract():
    readme = (ASSETS / "README.md").read_text()
    assert "The `.bin` planes are authoritative." in readme
    assert "PNG colour type **3** (indexed)" in readme
    for name in renderer().STATES:
        assert name in readme
