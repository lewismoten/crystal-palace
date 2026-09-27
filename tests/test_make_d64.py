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


def test_build_d64_chains_directory_sectors_for_more_than_eight_files(tmp_path):
    builder = load_builder()
    files = {}
    for number in range(9):
        path = tmp_path / f"L{number}.PRG"
        path.write_bytes(bytes((0x00, 0xc0, number)))
        files[path.name] = path
    image = tmp_path / "layers.d64"

    builder.build_d64_files(files, image, disk_name="CP64 WEIGHTS")

    data = image.read_bytes()
    first = 0x16600
    second = first + 256
    assert data[first:first + 2] == bytes((18, 2))
    assert data[second:second + 2] == bytes((0, 0xff))
    assert b"L0" in data[first:first + 256]
    assert b"L8" in data[second:second + 256]


def test_build_d64_directory_entry_preserves_start_track_sector_and_filename(tmp_path):
    """A CBM directory entry must keep its start pointer outside the PETSCII name."""
    builder = load_builder()
    prg = tmp_path / "CP64.PRG"
    prg.write_bytes(bytes((0x01, 0x08, 0x60)))
    image = tmp_path / "cp64.d64"

    builder.build_d64_files({"CP64.PRG": prg}, image, disk_name="CP64 MODEL")

    data = image.read_bytes()
    entry = 0x16600 + 2
    start_track, start_sector = data[entry + 1], data[entry + 2]
    assert start_track == 1
    assert start_sector == 0
    # CBM DOS stores a filename immediately after the two-byte start pointer.
    # This must be a conventional directory entry that DOS can open by name.
    assert data[entry + 3 : entry + 19].rstrip(b"\xa0") == b"CP64.PRG"


def test_extract_d64_file_recovers_the_exact_chained_prg_payload(tmp_path):
    """Release inspection must read back bytes from the D64 rather than trust inputs."""
    builder = load_builder()
    prg = tmp_path / "ART.PRG"
    payload = bytes((0x00, 0x60)) + bytes(range(256)) * 3
    prg.write_bytes(payload)
    image = tmp_path / "preview.d64"

    builder.build_d64_files({"ART.PRG": prg}, image, disk_name="CP64 PREVIEW")

    assert builder.extract_d64_file(image, "ART.PRG") == payload
