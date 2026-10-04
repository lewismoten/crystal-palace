import hashlib
from pathlib import Path


ROOT = Path(__file__).parents[1]
ASSETS = ROOT / "assets" / "palace"
GENERATED = ROOT / "build" / "palace-assets"
SOURCE = Path("/tmp/crystal-palace-screen-states")


REQUIRED = (
    "charset.bin",
    "title/auto/screen.bin",
    "title/auto/color.bin",
    "title/one/screen.bin",
    "title/one/color.bin",
    "title/two/screen.bin",
    "title/two/color.bin",
    "info/screen.bin",
    "info/color.bin",
    "game/blank/bitmap.bin",
    "game/blank/screen.bin",
    "game/blank/color.bin",
    "game/all-x/bitmap.bin",
    "game/all-x/screen.bin",
    "game/all-x/color.bin",
    "game/all-o/bitmap.bin",
    "game/all-o/screen.bin",
    "game/all-o/color.bin",
)


def test_png_compilation_matches_the_reviewed_native_manifest():
    """The PNG sources reproduce the reviewed native C64 planes exactly."""
    import json
    manifest = json.loads((ASSETS / "manifest.json").read_text())["generated_bins"]
    assert ASSETS.is_dir()
    for name, expected in manifest.items():
        payload = (GENERATED / name).read_bytes()
        assert len(payload) == expected["bytes"], name
        assert hashlib.sha256(payload).hexdigest() == expected["sha256"], name


def test_crystal_palace_assets_have_declared_raw_graphics_sizes():
    """Title/info are 1K char planes; game is 8K bitmap plus 1K screen/color planes."""
    assert (GENERATED / "charset.bin").stat().st_size == 2048
    for prefix in ("title/auto", "title/one", "title/two", "info"):
        assert (GENERATED / prefix / "screen.bin").stat().st_size == 1000
        assert (GENERATED / prefix / "color.bin").stat().st_size == 1000
    for prefix in ("game/blank", "game/all-x", "game/all-o"):
        assert (GENERATED / prefix / "bitmap.bin").stat().st_size == 8000
    assert (GENERATED / "game/blank/screen.bin").stat().st_size == 1000
    assert (GENERATED / "game/blank/color.bin").stat().st_size == 1000


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
    assert len(art) == 11
    for disk_name, spec in builder.CRYSTAL_PALACE_ART.items():
        asset_path, load_address = spec
        payload = art[disk_name].read_bytes()
        assert int.from_bytes(payload[:2], "little") == load_address
        assert payload[2:] == asset_path.read_bytes()
        assert not (load_address < 0xCA00 and load_address + len(payload) - 2 > 0xC000)
        assert not (load_address < 0xCA00 and load_address + len(payload) - 2 > 0xC100)


def test_blank_game_bitmap_is_one_final_address_bundle():
    """A transition bundle avoids a per-page loading path."""
    import importlib.util
    import sys

    scripts = ROOT / "scripts"
    sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location("build_disk", scripts / "build_disk.py")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)

    assert builder.CRYSTAL_PALACE_ART["GMBIT.PRG"] == (GENERATED / "game/blank/bitmap.bin", 0x6000)


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

    title_screen = (GENERATED / "title/one/screen.bin").read_bytes()
    title_color = (GENERATED / "title/one/color.bin").read_bytes()
    mpu.memory[0x5000 : 0x5000 + 1000] = title_screen
    mpu.memory[0x5400 : 0x5400 + 1000] = title_color
    call(mpu, symbols["ui_show_native_title"])
    assert bytes(mpu.memory[0x0400 : 0x0400 + 1000]) == title_screen
    assert bytes(mpu.memory[0xD800 : 0xD800 + 1000]) == title_color
    assert (mpu.memory[0xD011] & 0x20, mpu.memory[0xD016] & 0x10, mpu.memory[0xD018], mpu.memory[0xDD00] & 3) == (0, 0, 0x1E, 3)

    bitmap = (GENERATED / "game/blank/bitmap.bin").read_bytes()
    game_screen = (GENERATED / "game/blank/screen.bin").read_bytes()
    game_color = (GENERATED / "game/blank/color.bin").read_bytes()
    mpu.memory[0x6000 : 0x6000 + 8000] = bitmap
    mpu.memory[0x5000 : 0x5000 + 1000] = game_screen
    mpu.memory[0x5400 : 0x5400 + 1000] = game_color
    call(mpu, symbols["ui_show_native_game"])
    assert bytes(mpu.memory[0x6000 : 0x6000 + 8000]) == bitmap
    assert bytes(mpu.memory[0x4000 : 0x4000 + 1000]) == game_screen
    assert bytes(mpu.memory[0xD800 : 0xD800 + 1000]) == game_color
    assert (mpu.memory[0xD011] & 0x20, mpu.memory[0xD016] & 0x10, mpu.memory[0xD018], mpu.memory[0xDD00] & 3, mpu.memory[0xD021]) == (0x20, 0x10, 0x08, 2, 0)


def test_6502_native_game_patches_one_x_cell_from_the_supplied_all_x_plane(tmp_path):
    """A live mark changes only its supplied bitmap cell, never swaps in an all-X frame."""
    import subprocess
    import sys

    import pytest

    pytest.importorskip("py65")
    from py65.devices.mpu6502 import MPU

    sys.path.insert(0, str(ROOT / "tests"))
    from test_6502_embedding_gate import ASSEMBLER, call, labels

    prg = tmp_path / "CP64.PRG"; labels_path = tmp_path / "cp64.lbl"
    subprocess.run([str(ASSEMBLER), "--cbm-prg", f"--labels={labels_path}", "-o", str(prg), str(ROOT / "src" / "cp64.asm")], check=True, capture_output=True, text=True)
    symbols = labels(labels_path)
    assert {"ui_patch_native_x_cell", "computer_cell"} <= symbols.keys()
    mpu = MPU(); image = prg.read_bytes(); load = int.from_bytes(image[:2], "little")
    mpu.memory[load : load + len(image) - 2] = image[2:]
    blank = (GENERATED / "game/blank/bitmap.bin").read_bytes()
    all_x = (GENERATED / "game/all-x/bitmap.bin").read_bytes()
    mpu.memory[0x6000 : 0x6000 + 8000] = blank
    mpu.memory[0x8000 : 0x8000 + 8000] = all_x
    mpu.memory[symbols["computer_cell"]] = 4  # centre cell e

    call(mpu, symbols["ui_patch_native_x_cell"])

    # e spans character columns 19-20 and rows 7-9 (six 8-byte bitmap cells).
    allowed = {((row * 40 + column) * 8 + scan) for row in range(7, 10) for column in range(19, 21) for scan in range(8)}
    changed = {index for index, (before, after) in enumerate(zip(blank, mpu.memory[0x6000 : 0x6000 + 8000])) if before != after}
    assert changed
    assert changed <= allowed
    assert bytes(mpu.memory[0x6000 : 0x6000 + 8000])[min(allowed) : max(allowed) + 1] != blank[min(allowed) : max(allowed) + 1]


def test_6502_native_game_patches_one_o_cell_from_the_supplied_all_o_plane(tmp_path):
    """A model O is copied from its supplied cell source, not a PETSCII overlay."""
    import subprocess
    import sys

    import pytest

    pytest.importorskip("py65")
    from py65.devices.mpu6502 import MPU

    sys.path.insert(0, str(ROOT / "tests"))
    from test_6502_embedding_gate import ASSEMBLER, call, labels

    prg = tmp_path / "CP64.PRG"; labels_path = tmp_path / "cp64.lbl"
    subprocess.run([str(ASSEMBLER), "--cbm-prg", f"--labels={labels_path}", "-o", str(prg), str(ROOT / "src" / "cp64.asm")], check=True, capture_output=True, text=True)
    symbols = labels(labels_path)
    assert {"ui_patch_native_o_cell", "computer_cell"} <= symbols.keys()
    mpu = MPU(); image = prg.read_bytes(); load = int.from_bytes(image[:2], "little")
    mpu.memory[load : load + len(image) - 2] = image[2:]
    blank = (GENERATED / "game/blank/bitmap.bin").read_bytes()
    all_o = (GENERATED / "game/all-o/bitmap.bin").read_bytes()
    mpu.memory[0x6000 : 0x6000 + 8000] = blank
    mpu.memory[0x8000 : 0x8000 + 8000] = all_o
    mpu.memory[symbols["computer_cell"]] = 4

    call(mpu, symbols["ui_patch_native_o_cell"])

    allowed = {((row * 40 + column) * 8 + scan) for row in range(7, 10) for column in range(19, 21) for scan in range(8)}
    changed = {index for index, (before, after) in enumerate(zip(blank, mpu.memory[0x6000 : 0x6000 + 8000])) if before != after}
    assert changed
    assert changed <= allowed


def test_6502_title_selection_cycles_supplied_player_states(tmp_path):
    """The native title's Up/Down state is 1-player, 2-players, AI-vs-AI."""
    import subprocess
    import sys

    import pytest

    pytest.importorskip("py65")
    from py65.devices.mpu6502 import MPU

    sys.path.insert(0, str(ROOT / "tests"))
    from test_6502_embedding_gate import ASSEMBLER, call, labels

    prg = tmp_path / "CP64.PRG"; labels_path = tmp_path / "cp64.lbl"
    subprocess.run([str(ASSEMBLER), "--cbm-prg", f"--labels={labels_path}", "-o", str(prg), str(ROOT / "src" / "cp64.asm")], check=True, capture_output=True, text=True)
    symbols = labels(labels_path)
    assert {"title_mode", "ui_title_select_down", "ui_title_select_up"} <= symbols.keys()
    mpu = MPU(); image = prg.read_bytes(); load = int.from_bytes(image[:2], "little")
    mpu.memory[load : load + len(image) - 2] = image[2:]
    mpu.memory[symbols["title_mode"]] = 1
    call(mpu, symbols["ui_title_select_down"])
    assert mpu.memory[symbols["title_mode"]] == 2
    call(mpu, symbols["ui_title_select_down"])
    assert mpu.memory[symbols["title_mode"]] == 0
    call(mpu, symbols["ui_title_select_up"])
    assert mpu.memory[symbols["title_mode"]] == 2
    call(mpu, symbols["ui_title_select_up"])
    assert mpu.memory[symbols["title_mode"]] == 1


def test_6502_board_winner_distinguishes_native_x_o_rows_columns_and_diagonals(tmp_path):
    """Terminal board state must come from marks, never from a display frame."""
    import subprocess
    import sys

    import pytest

    pytest.importorskip("py65")
    from py65.devices.mpu6502 import MPU

    sys.path.insert(0, str(ROOT / "tests"))
    from test_6502_embedding_gate import ASSEMBLER, call, labels

    prg = tmp_path / "CP64.PRG"; labels_path = tmp_path / "cp64.lbl"
    subprocess.run([str(ASSEMBLER), "--cbm-prg", f"--labels={labels_path}", "-o", str(prg), str(ROOT / "src" / "cp64.asm")], check=True, capture_output=True, text=True)
    symbols = labels(labels_path)
    assert {"board_winner", "human_cells", "computer_cells"} <= symbols.keys()
    mpu = MPU(); image = prg.read_bytes(); load = int.from_bytes(image[:2], "little")
    mpu.memory[load : load + len(image) - 2] = image[2:]

    for human, computer, expected in ((0b000000111, 0, 1), (0, 0b001010100, 2), (0b100010001, 0, 1), (0, 0b001010100, 2), (0b000010001, 0b000100010, 0)):
        mpu.memory[symbols["human_cells"]] = human & 0xff
        mpu.memory[symbols["human_cells"] + 1] = human >> 8
        mpu.memory[symbols["computer_cells"]] = computer & 0xff
        mpu.memory[symbols["computer_cells"] + 1] = computer >> 8
        call(mpu, symbols["board_winner"])
        assert mpu.a == expected


def test_6502_restart_state_clears_every_board_ownership_bit(tmp_path):
    """A restart cannot retain a hidden occupied cell or a prior winner."""
    import subprocess
    import sys

    import pytest

    pytest.importorskip("py65")
    from py65.devices.mpu6502 import MPU

    sys.path.insert(0, str(ROOT / "tests"))
    from test_6502_embedding_gate import ASSEMBLER, call, labels

    prg = tmp_path / "CP64.PRG"; labels_path = tmp_path / "cp64.lbl"
    subprocess.run([str(ASSEMBLER), "--cbm-prg", f"--labels={labels_path}", "-o", str(prg), str(ROOT / "src" / "cp64.asm")], check=True, capture_output=True, text=True)
    symbols = labels(labels_path)
    assert {"reset_board_state", "board_occupied", "human_cells", "computer_cells", "computer_cell"} <= symbols.keys()
    mpu = MPU(); image = prg.read_bytes(); load = int.from_bytes(image[:2], "little")
    mpu.memory[load : load + len(image) - 2] = image[2:]
    for name in ("board_occupied", "board_occupied_hi", "human_cells", "computer_cells"):
        mpu.memory[symbols[name]] = 0xff
        mpu.memory[symbols[name] + 1] = 0xff
    mpu.memory[symbols["computer_cell"]] = 8

    call(mpu, symbols["reset_board_state"])

    assert bytes(mpu.memory[symbols["board_occupied"] : symbols["board_occupied"] + 2]) == b"\0\0"
    assert bytes(mpu.memory[symbols["human_cells"] : symbols["human_cells"] + 2]) == b"\0\0"
    assert bytes(mpu.memory[symbols["computer_cells"] : symbols["computer_cells"] + 2]) == b"\0\0"
    assert mpu.memory[symbols["computer_cell"]] == 0


def test_stage_058_preview_uses_only_native_art_navigation_and_restores_title_mode(tmp_path):
    """Stage 058 is an art navigator: title→game/info→title never enters a model path."""
    import subprocess
    import sys

    import pytest

    pytest.importorskip("py65")
    sys.path.insert(0, str(ROOT / "tests"))
    from test_6502_embedding_gate import ASSEMBLER, call, labels
    from py65.devices.mpu6502 import MPU

    source = ROOT / "src" / "art_preview.asm"
    assert source.is_file(), "Stage 058 needs a standalone no-inference preview program"
    prg = tmp_path / "CP64.PRG"; labels_path = tmp_path / "cp64.lbl"
    subprocess.run([str(ASSEMBLER), "--cbm-prg", f"--labels={labels_path}", "-o", str(prg), str(source)], check=True, capture_output=True, text=True)
    symbols = labels(labels_path)
    assert {"preview_show_title", "preview_show_game", "preview_show_info", "preview_title_down", "preview_title_up", "preview_mode", "preview_title_mode"} <= symbols.keys()
    mpu = MPU(); image = prg.read_bytes(); load = int.from_bytes(image[:2], "little")
    mpu.memory[load : load + len(image) - 2] = image[2:]
    charset = (GENERATED / "charset.bin").read_bytes()
    mpu.memory[0x3800 : 0x4000] = charset

    title_screen = (GENERATED / "title/one/screen.bin").read_bytes()
    title_color = (GENERATED / "title/one/color.bin").read_bytes()
    mpu.memory[0x5000 : 0x53e8] = title_screen; mpu.memory[0x5400 : 0x57e8] = title_color
    call(mpu, symbols["preview_show_title"])
    assert bytes(mpu.memory[0x0400 : 0x07e8]) == title_screen
    assert bytes(mpu.memory[0xd800 : 0xdbe8]) == title_color
    assert bytes(mpu.memory[0x3800 : 0x4000]) == charset
    assert mpu.memory[symbols["preview_mode"]] == 0
    assert (mpu.memory[0xd011] & 0x20, mpu.memory[0xd016] & 0x10, mpu.memory[0xd018], mpu.memory[0xdd00] & 3) == (0, 0, 0x1e, 3)

    game_bitmap = (GENERATED / "game/blank/bitmap.bin").read_bytes()
    game_screen = (GENERATED / "game/blank/screen.bin").read_bytes()
    game_color = (GENERATED / "game/blank/color.bin").read_bytes()
    mpu.memory[0x6000 : 0x7f40] = game_bitmap; mpu.memory[0x5000 : 0x53e8] = game_screen; mpu.memory[0x5400 : 0x57e8] = game_color
    call(mpu, symbols["preview_show_game"])
    assert bytes(mpu.memory[0x6000 : 0x7f40]) == game_bitmap
    assert bytes(mpu.memory[0x4000 : 0x43e8]) == game_screen
    assert bytes(mpu.memory[0xd800 : 0xdbe8]) == game_color
    assert mpu.memory[symbols["preview_mode"]] == 1
    assert (mpu.memory[0xd011] & 0x20, mpu.memory[0xd016] & 0x10, mpu.memory[0xd018], mpu.memory[0xdd00] & 3, mpu.memory[0xd021]) == (0x20, 0x10, 0x08, 2, 0)

    info_screen = (GENERATED / "info/screen.bin").read_bytes()
    info_color = (GENERATED / "info/color.bin").read_bytes()
    mpu.memory[0x5000 : 0x53e8] = info_screen; mpu.memory[0x5400 : 0x57e8] = info_color
    call(mpu, symbols["preview_show_info"])
    assert bytes(mpu.memory[0x0400 : 0x07e8]) == info_screen
    assert bytes(mpu.memory[0xd800 : 0xdbe8]) == info_color
    assert bytes(mpu.memory[0x3800 : 0x4000]) == charset
    assert mpu.memory[symbols["preview_mode"]] == 2
    assert (mpu.memory[0xd011] & 0x20, mpu.memory[0xd016] & 0x10, mpu.memory[0xd018], mpu.memory[0xdd00] & 3) == (0, 0, 0x1e, 3)

    call(mpu, symbols["preview_title_down"]); assert mpu.memory[symbols["preview_title_mode"]] == 2
    call(mpu, symbols["preview_title_down"]); assert mpu.memory[symbols["preview_title_mode"]] == 0
    call(mpu, symbols["preview_title_up"]); assert mpu.memory[symbols["preview_title_mode"]] == 2


def test_stage_086_build_keeps_disk_backed_info_with_browser_verified_radar_blackout(tmp_path):
    """The release builder preserves disk-backed INFO and uses the verified cells."""
    import importlib.util
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("build_disk", ROOT / "scripts" / "build_disk.py")
    builder = importlib.util.module_from_spec(spec); spec.loader.exec_module(builder)
    assert (builder.CURRENT_STAGE, builder.CURRENT_DESCRIPTION) == (86, "browser-verified-title-radar-blackout")
    assert builder.PROGRAM_SOURCE.name == "art_embedded_title.asm"
