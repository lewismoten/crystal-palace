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


def test_6502_native_title_and_game_art_activate_at_declared_vic_locations(tmp_path):
    """The supplied planes, not a recreated dashboard, drive each VIC-II mode."""
    import subprocess
    import sys

    import pytest

    pytest.importorskip("py65")
    from py65.devices.mpu6502 import MPU

    sys.path.insert(0, str(ROOT / "tests"))
    from test_6502_embedding_gate import ASSEMBLER, call, labels

    prg = tmp_path / "CP64.PRG"
    labels_path = tmp_path / "cp64.lbl"
    subprocess.run([str(ASSEMBLER), "--cbm-prg", f"--labels={labels_path}", "-o", str(prg), str(ROOT / "src" / "cp64.asm")], check=True, capture_output=True, text=True)
    symbols = labels(labels_path)
    assert {"ui_show_native_title", "ui_show_native_game", "ui_copy_1000"} <= symbols.keys()
    mpu = MPU()
    image = prg.read_bytes()
    load_address = int.from_bytes(image[:2], "little")
    mpu.memory[load_address : load_address + len(image) - 2] = image[2:]

    title_screen = (ASSETS / "crystal-palace-title-player-1.screen.bin").read_bytes()
    title_color = (ASSETS / "crystal-palace-title-player-1.color.bin").read_bytes()
    mpu.memory[0x5000 : 0x5000 + 1000] = title_screen
    mpu.memory[0x5400 : 0x5400 + 1000] = title_color
    call(mpu, symbols["ui_show_native_title"])
    assert bytes(mpu.memory[0x0400 : 0x0400 + 1000]) == title_screen
    assert bytes(mpu.memory[0xD800 : 0xD800 + 1000]) == title_color
    assert (mpu.memory[0xD011] & 0x20, mpu.memory[0xD016] & 0x10, mpu.memory[0xD018], mpu.memory[0xDD00] & 3) == (0, 0, 0x1E, 3)

    bitmap = (ASSETS / "crystal-palace-game-blank.bitmap.bin").read_bytes()
    game_screen = (ASSETS / "crystal-palace-game-blank.screen.bin").read_bytes()
    game_color = (ASSETS / "crystal-palace-game-blank.color.bin").read_bytes()
    mpu.memory[0x6000 : 0x6000 + 8000] = bitmap
    mpu.memory[0x5000 : 0x5000 + 1000] = game_screen
    mpu.memory[0x5400 : 0x5400 + 1000] = game_color
    call(mpu, symbols["ui_show_native_game"])
    assert bytes(mpu.memory[0x6000 : 0x6000 + 8000]) == bitmap
    assert bytes(mpu.memory[0x4000 : 0x4000 + 1000]) == game_screen
    assert bytes(mpu.memory[0xD800 : 0xD800 + 1000]) == game_color
    assert (mpu.memory[0xD011] & 0x20, mpu.memory[0xD016] & 0x10, mpu.memory[0xD018], mpu.memory[0xDD00] & 3, mpu.memory[0xD021]) == (0x20, 0x10, 0x08, 2, 0)
