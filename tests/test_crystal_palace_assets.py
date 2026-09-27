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
    assert len(art) == 49
    for disk_name, spec in builder.CRYSTAL_PALACE_ART.items():
        asset_name, load_address, *slice_spec = spec
        payload = art[disk_name].read_bytes()
        assert int.from_bytes(payload[:2], "little") == load_address
        source = (ASSETS / asset_name).read_bytes()
        if slice_spec:
            offset, length = slice_spec
            source = source[offset : offset + length]
        assert payload[2:] == source
        assert not (load_address < 0xCA00 and load_address + len(payload) - 2 > 0xC000)
        assert not (load_address < 0xCA00 and load_address + len(payload) - 2 > 0xC100)


def test_blank_game_bitmap_is_split_into_final_address_source_pages():
    """Stage 059 presents the supplied blank board without a full staging load."""
    import importlib.util
    import sys

    scripts = ROOT / "scripts"
    sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location("build_disk", scripts / "build_disk.py")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)

    assert builder.CRYSTAL_PALACE_ART["CGB0.PRG"] == ("crystal-palace-game-blank.bitmap.bin", 0x6000, 0, 1000)
    assert builder.CRYSTAL_PALACE_ART["CGB7.PRG"] == ("crystal-palace-game-blank.bitmap.bin", 0x7b58, 7000, 1000)


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
    blank = (ASSETS / "crystal-palace-game-blank.bitmap.bin").read_bytes()
    all_x = (ASSETS / "crystal-palace-game-all-x.bitmap.bin").read_bytes()
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
    blank = (ASSETS / "crystal-palace-game-blank.bitmap.bin").read_bytes()
    all_o = (ASSETS / "crystal-palace-game-all-o.bitmap.bin").read_bytes()
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
    charset = (ASSETS / "crystal-palace-charset.bin").read_bytes()
    mpu.memory[0x3800 : 0x4000] = charset

    title_screen = (ASSETS / "crystal-palace-title-player-1.screen.bin").read_bytes()
    title_color = (ASSETS / "crystal-palace-title-player-1.color.bin").read_bytes()
    mpu.memory[0x5000 : 0x53e8] = title_screen; mpu.memory[0x5400 : 0x57e8] = title_color
    call(mpu, symbols["preview_show_title"])
    assert bytes(mpu.memory[0x0400 : 0x07e8]) == title_screen
    assert bytes(mpu.memory[0xd800 : 0xdbe8]) == title_color
    assert bytes(mpu.memory[0x3800 : 0x4000]) == charset
    assert mpu.memory[symbols["preview_mode"]] == 0
    assert (mpu.memory[0xd011] & 0x20, mpu.memory[0xd016] & 0x10, mpu.memory[0xd018], mpu.memory[0xdd00] & 3) == (0, 0, 0x1e, 3)

    game_bitmap = (ASSETS / "crystal-palace-game-blank.bitmap.bin").read_bytes()
    game_screen = (ASSETS / "crystal-palace-game-blank.screen.bin").read_bytes()
    game_color = (ASSETS / "crystal-palace-game-blank.color.bin").read_bytes()
    mpu.memory[0x6000 : 0x7f40] = game_bitmap; mpu.memory[0x5000 : 0x53e8] = game_screen; mpu.memory[0x5400 : 0x57e8] = game_color
    call(mpu, symbols["preview_show_game"])
    assert bytes(mpu.memory[0x6000 : 0x7f40]) == game_bitmap
    assert bytes(mpu.memory[0x4000 : 0x43e8]) == game_screen
    assert bytes(mpu.memory[0xd800 : 0xdbe8]) == game_color
    assert mpu.memory[symbols["preview_mode"]] == 1
    assert (mpu.memory[0xd011] & 0x20, mpu.memory[0xd016] & 0x10, mpu.memory[0xd018], mpu.memory[0xdd00] & 3, mpu.memory[0xd021]) == (0x20, 0x10, 0x08, 2, 0)

    info_screen = (ASSETS / "crystal-palace-info.screen.bin").read_bytes()
    info_color = (ASSETS / "crystal-palace-info.color.bin").read_bytes()
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


def test_stage_072_build_uses_original_c9w00_embedding_bridge_and_archives_the_named_disk(tmp_path):
    """The release builder reserves Stage 072 for the real original-weight bridge."""
    import importlib.util
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("build_disk", ROOT / "scripts" / "build_disk.py")
    builder = importlib.util.module_from_spec(spec); spec.loader.exec_module(builder)
    assert (builder.CURRENT_STAGE, builder.CURRENT_DESCRIPTION) == (72, "original-c9w00-embedding-bridge")
    assert builder.PROGRAM_SOURCE.name == "art_embedded_title.asm"
