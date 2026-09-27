"""Stage 059: native art must arrive as visible source-exact disk pages."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
ASSETS = ROOT / "assets" / "crystal-palace-screen-states"


def load_builder():
    scripts = ROOT / "scripts"
    sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location("build_disk", scripts / "build_disk.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_stage_070_declares_browser_lowercase_input_repair():
    builder = load_builder()
    assert (builder.CURRENT_STAGE, builder.CURRENT_DESCRIPTION) == (70, "browser-lowercase-input-repair")
    assert builder.PROGRAM_SOURCE.name == "art_embedded_title.asm"


def test_native_art_chunks_are_source_exact_final_address_prgs(tmp_path):
    """Every page is loaded straight to the final VIC plane address."""
    builder = load_builder()
    pages = builder.crystal_palace_art_prgs(tmp_path)
    title_screen = [pages[f"CT1S{index}.PRG"].read_bytes() for index in range(4)]
    title_color = [pages[f"CT1C{index}.PRG"].read_bytes() for index in range(4)]
    assert [int.from_bytes(page[:2], "little") for page in title_screen] == [0x0400, 0x0500, 0x0600, 0x0700]
    assert [int.from_bytes(page[:2], "little") for page in title_color] == [0xD800, 0xD900, 0xDA00, 0xDB00]
    assert b"".join(page[2:] for page in title_screen) == (ASSETS / "crystal-palace-title-player-1.screen.bin").read_bytes()
    assert b"".join(page[2:] for page in title_color) == (ASSETS / "crystal-palace-title-player-1.color.bin").read_bytes()
    game_bitmap = [pages[f"CGB{index}.PRG"].read_bytes() for index in range(8)]
    assert [int.from_bytes(page[:2], "little") for page in game_bitmap] == [0x6000 + 1000 * index for index in range(8)]
    assert b"".join(page[2:] for page in game_bitmap) == (ASSETS / "crystal-palace-game-blank.bitmap.bin").read_bytes()


def test_embedded_title_source_uses_no_disk_loader_or_screen_editor_output():
    source = (ROOT / "src" / "art_embedded_title.asm").read_text()
    assert "jsr LOAD" not in source and "SETNAM" not in source and "CHROUT" not in source
    assert '.binary "../assets/crystal-palace-screen-states/crystal-palace-charset.bin"' in source
    assert '.binary "../assets/crystal-palace-screen-states/crystal-palace-title-player-1.screen.bin"' in source
    assert '.binary "../assets/crystal-palace-screen-states/crystal-palace-title-player-1.color.bin"' in source


def test_embedded_title_uses_declared_vic_addresses_and_direct_plane_copies():
    source = (ROOT / "src" / "art_embedded_title.asm").read_text()
    assert "* = $3800" in source and "* = $4000" in source and "* = $4400" in source
    assert "lda #$1e" in source and "sta $d018" in source
    assert "show_title:" in source and "show_info:" in source and "show_game:" in source
    assert "ldx view_mode" in source
    assert "patch_title_hints:" in source


def test_assembled_embedded_title_copies_exact_planes_to_live_vic_memory(tmp_path):
    """Exercise the actual 6502 copies, not a host-language substitute."""
    import subprocess
    import pytest

    pytest.importorskip("py65")
    from py65.devices.mpu6502 import MPU

    sys.path.insert(0, str(ROOT / "tests"))
    from test_6502_embedding_gate import ASSEMBLER, call, labels

    prg = tmp_path / "CP64.PRG"
    labels_path = tmp_path / "embedded.lbl"
    source = ROOT / "src" / "art_embedded_title.asm"
    subprocess.run([str(ASSEMBLER), "--cbm-prg", f"--labels={labels_path}", "-o", str(prg), str(source)], check=True, capture_output=True, text=True)
    symbols = labels(labels_path)
    mpu = MPU()
    image = prg.read_bytes()
    load = int.from_bytes(image[:2], "little")
    mpu.memory[load : load + len(image) - 2] = image[2:]
    mpu.memory[symbols["title_mode"]] = 1
    call(mpu, symbols["show_title"])
    expected_screen = bytearray((ASSETS / "crystal-palace-title-player-1.screen.bin").read_bytes())
    expected_colour = bytearray((ASSETS / "crystal-palace-title-player-1.color.bin").read_bytes())
    expected_screen[882:888] = bytes((9, 0, 9, 14, 6, 15))
    expected_colour[882:888] = b"\x07" * 6
    expected_screen[922:928] = bytes((17, 0, 17, 21, 9, 20))
    expected_colour[922:928] = b"\x07" * 6
    for offset in (371, 451, 531): expected_colour[offset] = 7
    assert bytes(mpu.memory[0x0400 : 0x0400 + 1000]) == bytes(expected_screen)
    assert bytes(mpu.memory[0xD800 : 0xD800 + 1000]) == bytes(expected_colour)


def test_embedded_preview_has_correct_game_vic_layout_and_live_a_to_i_marks(tmp_path):
    """The browser-facing preview must use the supplied bitmap bank and accept A–I."""
    import subprocess
    import pytest

    pytest.importorskip("py65")
    from py65.devices.mpu6502 import MPU
    sys.path.insert(0, str(ROOT / "tests"))
    from test_6502_embedding_gate import ASSEMBLER, call, labels

    prg, labels_path = tmp_path / "CP64.PRG", tmp_path / "embedded.lbl"
    subprocess.run([str(ASSEMBLER), "--cbm-prg", f"--labels={labels_path}", "-o", str(prg), str(ROOT / "src" / "art_embedded_title.asm")], check=True, capture_output=True, text=True)
    symbols = labels(labels_path)
    assert {"show_game", "game_key", "draw_x", "draw_o", "game_bitmap_copy"} <= symbols.keys()
    image = prg.read_bytes(); mpu = MPU(); load = int.from_bytes(image[:2], "little")
    mpu.memory[load : load + len(image) - 2] = image[2:]
    call(mpu, symbols["show_game"])
    assert bytes(mpu.memory[0x2000 : 0x3F40]) == (ASSETS / "crystal-palace-game-blank.bitmap.bin").read_bytes()
    assert bytes(mpu.memory[0x0400 : 0x07E8]) == (ASSETS / "crystal-palace-game-blank.screen.bin").read_bytes()
    assert (mpu.memory[0xD011] & 0x20, mpu.memory[0xD016] & 0x10, mpu.memory[0xD018], mpu.memory[0xDD00] & 3) == (0x20, 0x10, 0x18, 3)

    mpu.memory[symbols["game_index"]] = 0; call(mpu, symbols["draw_x"])
    assert mpu.memory[symbols["board_state"]] == 1
    assert bytes(mpu.memory[0x2000 + 30 * 40 + 29 : 0x2000 + 30 * 40 + 37]) == (ROOT / "assets" / "crystal-palace-screen-states" / "cells" / "x-cells.bitmap.bin").read_bytes()[:8]
    assert (mpu.memory[0x0400 + 4 * 40 + 15] >> 4) == 10  # source-exact light-red X

    mpu.memory[symbols["game_index"]] = 1; call(mpu, symbols["draw_o"])
    assert mpu.memory[symbols["board_state"] + 1] == 2
    assert (mpu.memory[0x0400 + 4 * 40 + 19] >> 4) == 3  # source-exact cyan O


def test_embedded_title_selection_cycles_without_bouncing_to_player_one(tmp_path):
    import subprocess
    import pytest

    pytest.importorskip("py65")
    from py65.devices.mpu6502 import MPU
    sys.path.insert(0, str(ROOT / "tests"))
    from test_6502_embedding_gate import ASSEMBLER, call, labels

    prg, labels_path = tmp_path / "CP64.PRG", tmp_path / "embedded.lbl"
    subprocess.run([str(ASSEMBLER), "--cbm-prg", f"--labels={labels_path}", "-o", str(prg), str(ROOT / "src" / "art_embedded_title.asm")], check=True, capture_output=True, text=True)
    symbols = labels(labels_path); image = prg.read_bytes(); mpu = MPU(); load = int.from_bytes(image[:2], "little")
    mpu.memory[load : load + len(image) - 2] = image[2:]
    mpu.memory[symbols["title_mode"]] = 1
    call(mpu, symbols["select_title_down"]); assert mpu.memory[symbols["title_mode"]] == 2
    call(mpu, symbols["select_title_down"]); assert mpu.memory[symbols["title_mode"]] == 0
    call(mpu, symbols["select_title_down"]); assert mpu.memory[symbols["title_mode"]] == 1
    call(mpu, symbols["select_title_up"]); assert mpu.memory[symbols["title_mode"]] == 0


def test_title_actions_return_to_the_key_loop_without_falling_into_basic():
    """Display routines end in RTS, so title dispatch must enter them via JSR."""
    source = (ROOT / "src" / "art_embedded_title.asm").read_text()
    assert "title_number_game:\n    jsr show_game\n    jmp key_loop" in source
    assert "title_info:\n    jsr show_info\n    jmp key_loop" in source
    assert "title_down:\n    jsr select_title_down\n    jsr wait_key_release\n    jmp key_loop" in source
    assert "wait_key_release:\n    lda #0\n    sta $c6" in source


def test_game_dispatch_accepts_browser_lowercase_a_to_i():
    source = (ROOT / "src" / "art_embedded_title.asm").read_text()
    assert "cmp #'a'" in source
    assert "sbc #'a'" in source
