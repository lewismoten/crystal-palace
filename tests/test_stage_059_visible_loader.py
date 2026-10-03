"""Stage 059: native art must arrive as visible source-exact disk pages."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
ASSETS = ROOT / "assets" / "crystal-palace-screen-states"


def load_builder():
    scripts = ROOT / "scripts"
    sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location("build_disk", scripts / "build_disk.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_stage_076_declares_validated_d64_and_plane_previews():
    builder = load_builder()
    assert (builder.CURRENT_STAGE, builder.CURRENT_DESCRIPTION) == (76, "validated-d64-and-plane-previews")
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


def test_embedded_title_source_uses_no_screen_editor_output():
    source = (ROOT / "src" / "art_embedded_title.asm").read_text()
    assert "CHROUT" not in source
    assert '.binary "../assets/crystal-palace-screen-states/crystal-palace-charset.bin"' in source
    assert '.binary "../assets/crystal-palace-screen-states/crystal-palace-title-player-1.screen.bin"' in source
    assert '.binary "../assets/crystal-palace-screen-states/crystal-palace-title-player-1.color.bin"' in source


@pytest.mark.parametrize("game_index", range(9))
def test_assembled_embedded_c9w00_bridge_materializes_each_original_row_without_being_in_the_browser_input_path(tmp_path, game_index):
    """Keep the original-data bridge testable, but isolate it from unstable browser input."""
    import subprocess
    import pytest

    pytest.importorskip("py65")
    from py65.devices.mpu6502 import MPU

    sys.path.insert(0, str(ROOT / "tests"))
    from test_6502_embedding_gate import ASSEMBLER, call, labels, q8_8_vector_from_original_packet, signed_vector

    prg, labels_path = tmp_path / "CP64.PRG", tmp_path / "embedded.lbl"
    source_path = ROOT / "src" / "art_embedded_title.asm"
    subprocess.run([str(ASSEMBLER), "--cbm-prg", f"--labels={labels_path}", "-o", str(prg), str(source_path)], check=True, capture_output=True, text=True)
    symbols = labels(labels_path)
    assert {"load_c9w00", "materialize_selected_embedding", "EMBEDDING_VECTOR", "embedding_sumlo", "embedding_sumhi"} <= symbols.keys()

    image = prg.read_bytes(); mpu = MPU(); load = int.from_bytes(image[:2], "little")
    mpu.memory[load : load + len(image) - 2] = image[2:]
    # KERNAL calls return in Py65; the original packet is already in its real $c000 window.
    for address in (0xFFBA, 0xFFBD, 0xFFD5): mpu.memory[address] = 0x60
    packet = (ROOT / "build" / "layers" / "C9W00.PRG").read_bytes()
    mpu.memory[0xC000 : 0xC000 + len(packet) - 2] = packet[2:]
    mpu.memory[symbols["game_index"]] = game_index
    mpu.p &= ~mpu.CARRY

    call(mpu, symbols["materialize_selected_embedding"])

    expected = q8_8_vector_from_original_packet(ROOT / "build" / "layers" / "C9W00.PRG", game_index + 4)
    assert signed_vector(mpu, symbols["EMBEDDING_VECTOR"]) == expected
    assert mpu.memory[symbols["embedding_sumlo"]] | (mpu.memory[symbols["embedding_sumhi"]] << 8) == (
        sum((index + 1) * value for index, value in enumerate(expected)) & 0xFFFF
    )
    browser_input = source_path.read_text()[source_path.read_text().index("game_draw_x:") : source_path.read_text().index("game_key_done:")]
    assert "jsr draw_x" in browser_input
    assert "materialize_selected_embedding" not in browser_input
    assert "draw_o" not in browser_input and "turn_mark" not in browser_input


def test_assembled_embedded_c9w00_loader_rejects_wrong_packet_header(tmp_path):
    """A resident lookalike cannot be materialized as the original C9W00 tensor."""
    import subprocess

    pytest.importorskip("py65")
    from py65.devices.mpu6502 import MPU

    sys.path.insert(0, str(ROOT / "tests"))
    from test_6502_embedding_gate import ASSEMBLER, call, labels

    prg, labels_path = tmp_path / "CP64.PRG", tmp_path / "embedded.lbl"
    subprocess.run([str(ASSEMBLER), "--cbm-prg", f"--labels={labels_path}", "-o", str(prg), str(ROOT / "src" / "art_embedded_title.asm")], check=True, capture_output=True, text=True)
    symbols = labels(labels_path); image = prg.read_bytes(); mpu = MPU(); load = int.from_bytes(image[:2], "little")
    mpu.memory[load : load + len(image) - 2] = image[2:]
    for address in (0xFFBA, 0xFFBD, 0xFFD5): mpu.memory[address] = 0x60
    packet = bytearray((ROOT / "build" / "layers" / "C9W00.PRG").read_bytes()[2:])
    packet[4] = 1  # C9W01 must not pass a C9W00 bridge.
    mpu.memory[0xC000 : 0xC000 + len(packet)] = packet
    mpu.p &= ~mpu.CARRY

    call(mpu, symbols["load_c9w00"])

    assert mpu.p & mpu.CARRY


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
    assert {"show_game", "game_key", "draw_x", "draw_o", "game_bitmap_copy", "progress_reset"} <= symbols.keys()
    image = prg.read_bytes(); mpu = MPU(); load = int.from_bytes(image[:2], "little")
    mpu.memory[load : load + len(image) - 2] = image[2:]
    call(mpu, symbols["show_game"])
    expected_bitmap = bytearray((ASSETS / "crystal-palace-game-blank.bitmap.bin").read_bytes())
    for segment in range(12):
        expected_bitmap[0x11F4 + segment * 8 : 0x11F8 + segment * 8] = b"\0" * 4
    assert bytes(mpu.memory[0x2000 : 0x3F40]) == bytes(expected_bitmap)
    expected_screen = bytearray((ASSETS / "crystal-palace-game-blank.screen.bin").read_bytes())
    for segment in range(12):
        expected_screen[574 + segment] &= 0x0F
    assert bytes(mpu.memory[0x0400 : 0x07E8]) == bytes(expected_screen)
    assert (mpu.memory[0xD011] & 0x20, mpu.memory[0xD016] & 0x10, mpu.memory[0xD018], mpu.memory[0xDD00] & 3) == (0x20, 0x10, 0x18, 3)

    mpu.memory[symbols["game_index"]] = 0; call(mpu, symbols["draw_x"])
    assert mpu.memory[symbols["board_state"]] == 1
    patch = (ROOT / "assets" / "crystal-palace-screen-states" / "cells" / "x-cells.bitmap.bin").read_bytes()
    destinations = (ROOT / "assets" / "crystal-palace-screen-states" / "cells" / "bitmap-destination-addresses.bin").read_bytes()
    for offset, value in enumerate(patch[:192]):
        address = int.from_bytes(destinations[offset * 2 : offset * 2 + 2], "little")
        assert mpu.memory[address] == value
    assert (mpu.memory[0x0400 + 4 * 40 + 15] >> 4) == 10  # source-exact light-red X

    mpu.memory[symbols["game_index"]] = 1; call(mpu, symbols["draw_o"])
    assert mpu.memory[symbols["board_state"] + 1] == 2
    assert (mpu.memory[0x0400 + 4 * 40 + 19] >> 4) == 3  # source-exact cyan O
    # The line sits below the grid in bitmap RAM; it must visibly finish after
    # the real X bitmap/screen/colour patch boundaries, not leave a screen-code
    # meter hidden in multicolour metadata.
    for index in range(12):
        assert bytes(mpu.memory[0x31F4 + index * 8 : 0x31F8 + index * 8]) == b"\x55" * 4
    assert [mpu.memory[0x063E + index] >> 4 for index in range(12)] == [9] * 4 + [8] * 4 + [10] * 3 + [7]


def test_title_and_info_restore_after_live_board_patches(tmp_path):
    """Q/I must restore their full supplied planes after a move changed the board."""
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
    call(mpu, symbols["show_game"])
    call(mpu, symbols["draw_x"])
    mpu.memory[0x3800 : 0x4000] = b"\x00" * 2048
    mpu.memory[symbols["title_mode"]] = 1
    call(mpu, symbols["show_title"])
    assert bytes(mpu.memory[0x3800 : 0x4000]) == (ASSETS / "crystal-palace-charset.bin").read_bytes()
    title = bytearray((ASSETS / "crystal-palace-title-player-1.screen.bin").read_bytes())
    title[882:888] = bytes((9, 0, 9, 14, 6, 15))
    title[922:928] = bytes((17, 0, 17, 21, 9, 20))
    assert bytes(mpu.memory[0x0400 : 0x07E8]) == bytes(title)
    call(mpu, symbols["show_info"])
    assert bytes(mpu.memory[0x0400 : 0x07E8]) == (ASSETS / "crystal-palace-info.screen.bin").read_bytes()


def test_sequential_a_to_i_x_patches_stay_in_the_game_planes_and_leave_title_info_restorable(tmp_path):
    """The exact reported A..I path must never invoke a disk load or scramble other planes."""
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
    call(mpu, symbols["show_game"])
    for game_index in range(9):
        mpu.memory[symbols["game_index"]] = game_index
        call(mpu, symbols["draw_x"])
    assert bytes(mpu.memory[symbols["board_state"] : symbols["board_state"] + 9]) == b"\x01" * 9
    assert bytes(mpu.memory[0x2000 : 0x3F40]) != (ASSETS / "crystal-palace-game-blank.bitmap.bin").read_bytes()
    mpu.memory[symbols["title_mode"]] = 1
    call(mpu, symbols["show_title"])
    assert bytes(mpu.memory[0x3800 : 0x4000]) == (ASSETS / "crystal-palace-charset.bin").read_bytes()
    call(mpu, symbols["show_info"])
    assert bytes(mpu.memory[0x0400 : 0x07E8]) == (ASSETS / "crystal-palace-info.screen.bin").read_bytes()


def test_charset_restore_reads_the_ram_copy_hidden_under_basic_rom_on_real_c64s():
    """Py65 lacks C64 ROM banking, so guard the hardware-only $b000 failure statically."""
    source = (ROOT / "src" / "art_embedded_title.asm").read_text()
    restore = source[source.index("restore_title_charset:") : source.index("ambient_console_lights:")]
    assert "lda $01" in restore
    assert "and #$fe" in restore
    assert "sta $01" in restore
    assert "title_charset_memory_config" in restore


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
    assert "cmp #$c1" in source
    assert "sbc #$c1" in source
