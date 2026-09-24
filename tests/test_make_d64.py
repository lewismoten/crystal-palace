import importlib.util
from pathlib import Path


def load_builder():
    path = Path(__file__).parents[1] / "scripts" / "make_d64.py"
    spec = importlib.util.spec_from_file_location("make_d64", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_d64_creates_standard_35_track_image_with_prg(tmp_path):
    builder = load_builder()
    prg = tmp_path / "CP64.PRG"
    prg.write_bytes(bytes((0x01, 0x08, 0x60)))  # BASIC load address + RTS
    image = tmp_path / "cp64.d64"

    builder.build_d64(prg, image, disk_name="CP64 MODEL")

    data = image.read_bytes()
    assert len(data) == 174_848
    assert data[0x16590:0x165a0].rstrip(b"\xa0") == b"CP64 MODEL"
    assert b"CP64" in data[0x16600:0x16800]
    assert data[0x16600:0x16602] == bytes((0, 0xff))
