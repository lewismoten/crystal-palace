import hashlib
from pathlib import Path


ROOT = Path(__file__).parents[1]
ASSETS = ROOT / "assets" / "crystal-palace-screen-states"
SOURCE = Path("/tmp/crystal-palace-screen-states")


REQUIRED = (
    "crystal-palace-charset.bin",
    "crystal-palace-title-player-0.screen.bin",
    "crystal-palace-title-player-0.color.bin",
    "crystal-palace-title-player-1.screen.bin",
    "crystal-palace-title-player-1.color.bin",
    "crystal-palace-title-player-2.screen.bin",
    "crystal-palace-title-player-2.color.bin",
    "crystal-palace-info.screen.bin",
    "crystal-palace-info.color.bin",
    "crystal-palace-game-blank.bitmap.bin",
    "crystal-palace-game-blank.screen.bin",
    "crystal-palace-game-blank.color.bin",
    "crystal-palace-game-all-x.bitmap.bin",
    "crystal-palace-game-all-x.screen.bin",
    "crystal-palace-game-all-x.color.bin",
    "crystal-palace-game-all-o.bitmap.bin",
    "crystal-palace-game-all-o.screen.bin",
    "crystal-palace-game-all-o.color.bin",
    "crystal-palace-board-coordinates.json",
    "README.txt",
)


def test_immutable_crystal_palace_source_assets_are_exact_copies():
    """The native UI bytes are versioned copies, never regenerated approximations."""
    assert ASSETS.is_dir(), "copy the supplied native Crystal Palace assets into the repository"
    for name in REQUIRED:
        copied = ASSETS / name
        supplied = SOURCE / name
        assert copied.is_file(), name
        assert hashlib.sha256(copied.read_bytes()).digest() == hashlib.sha256(supplied.read_bytes()).digest(), name


def test_crystal_palace_assets_have_declared_raw_graphics_sizes():
    """Title/info are 1K char planes; game is 8K bitmap plus 1K screen/color planes."""
    assert (ASSETS / "crystal-palace-charset.bin").stat().st_size == 2048
    for prefix in ("crystal-palace-title-player-0", "crystal-palace-title-player-1", "crystal-palace-title-player-2", "crystal-palace-info"):
        assert (ASSETS / f"{prefix}.screen.bin").stat().st_size == 1000
        assert (ASSETS / f"{prefix}.color.bin").stat().st_size == 1000
    for prefix in ("crystal-palace-game-blank", "crystal-palace-game-all-x", "crystal-palace-game-all-o"):
        assert (ASSETS / f"{prefix}.bitmap.bin").stat().st_size == 8000
    assert (ASSETS / "crystal-palace-game-blank.screen.bin").stat().st_size == 1000
    assert (ASSETS / "crystal-palace-game-blank.color.bin").stat().st_size == 1000


def test_build_packages_native_art_as_fixed_address_prgs_without_model_window_overlap(tmp_path):
    """Raw supplied planes travel unchanged behind only a two-byte PRG load address."""
    import importlib.util
    import sys

    scripts = ROOT / "scripts"
    sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location("build_disk", scripts / "build_disk.py")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    art = builder.crystal_palace_art_prgs(tmp_path)
    assert len(art) == 18
    for disk_name, (asset_name, load_address) in builder.CRYSTAL_PALACE_ART.items():
        payload = art[disk_name].read_bytes()
        assert int.from_bytes(payload[:2], "little") == load_address
        assert payload[2:] == (ASSETS / asset_name).read_bytes()
        assert not (load_address < 0xCA00 and load_address + len(payload) - 2 > 0xC000)
        assert not (load_address < 0xCA00 and load_address + len(payload) - 2 > 0xC100)
