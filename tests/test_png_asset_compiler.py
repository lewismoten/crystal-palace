"""PNG-source C64 asset compiler coverage."""
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
ASSETS = ROOT / "assets" / "palace"


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
