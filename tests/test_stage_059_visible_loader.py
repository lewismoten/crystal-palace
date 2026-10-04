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


def prepare_info_archive_load(mpu) -> None:
    """Supply the disk payload and KERNAL stubs for the flat-memory Py65 harness."""
    payload = (ROOT / "build" / "ARCHIVE.PRG").read_bytes()
    mpu.memory[0xFFBA] = 0x60  # SETLFS RTS
    mpu.memory[0xFFBD] = 0x60  # SETNAM RTS
    mpu.memory[0xFFD5] = 0x60  # LOAD RTS after the preloaded disk payload
    mpu.memory[0xC000 : 0xC000 + len(payload) - 2] = payload[2:]


def test_stage_084_declares_disk_backed_info_archive():
    builder = load_builder()
    assert (builder.CURRENT_STAGE, builder.CURRENT_DESCRIPTION) == (84, "disk-backed-info-archive")
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
    assert "materialize_selected_embedding" not in browser_input


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
    assert "* = $3800" in source and "* = $4000" in source and "* = $4c00" in source
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
    expected_screen[882:886] = bytes((9, 14, 6, 15))
    expected_colour[882:886] = bytes((1, 12, 12, 12))
    expected_screen[922:926] = bytes((17, 21, 9, 20))
    expected_colour[922:926] = bytes((1, 12, 12, 12))
    for offset in (242, 282, 321, 322):
        expected_screen[offset] = 0
        expected_colour[offset] = 0
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
    assert {"show_game", "game_key", "process_game_key", "draw_x", "draw_o", "game_bitmap_copy"} <= symbols.keys()
    image = prg.read_bytes(); mpu = MPU(); load = int.from_bytes(image[:2], "little")
    mpu.memory[load : load + len(image) - 2] = image[2:]
    call(mpu, symbols["show_game"])
    expected_bitmap = bytearray((ASSETS / "crystal-palace-game-blank.bitmap.bin").read_bytes())
    label_glyphs = (
        b"\x00\x14\x41\x55\x41\x41\x41\x00", b"\x00\x54\x41\x54\x41\x41\x54\x00",
        b"\x00\x15\x40\x40\x40\x40\x15\x00", b"\x00\x54\x41\x41\x41\x41\x54\x00",
        b"\x00\x55\x40\x54\x40\x40\x55\x00", b"\x00\x55\x40\x54\x40\x40\x40\x00",
        b"\x00\x15\x40\x45\x41\x41\x15\x00", b"\x00\x41\x41\x55\x41\x41\x41\x00",
        b"\x00\x55\x14\x14\x14\x14\x55\x00",
    )
    for index, glyph in enumerate(label_glyphs):
        address = int.from_bytes(mpu.memory[symbols["label_bitmap_destinations"] + index * 2 : symbols["label_bitmap_destinations"] + index * 2 + 2], "little")
        expected_bitmap[address - 0x2000 : address - 0x2000 + 8] = glyph
    expected_bitmap[0x3218 - 0x2000 : 0x3220 - 0x2000] = b"\x00\x41\x41\x14\x14\x41\x41\x00"
    assert bytes(mpu.memory[0x2000 : 0x3F40]) == bytes(expected_bitmap)
    expected_screen = bytearray((ASSETS / "crystal-palace-game-blank.screen.bin").read_bytes())
    for index in range(9):
        address = int.from_bytes(mpu.memory[symbols["label_screen_destinations"] + index * 2 : symbols["label_screen_destinations"] + index * 2 + 2], "little")
        offset = address - 0x0400
        expected_screen[offset] = (expected_screen[offset] & 0x0F) | 0xB0
    expected_screen[0x0643 - 0x0400] = (expected_screen[0x0643 - 0x0400] & 0x0F) | 0xA0
    assert bytes(mpu.memory[0x0400 : 0x07E8]) == bytes(expected_screen)
    assert (mpu.memory[0xD011] & 0x20, mpu.memory[0xD016] & 0x10, mpu.memory[0xD018], mpu.memory[0xDD00] & 3) == (0x20, 0x10, 0x18, 3)

    mpu.memory[symbols["game_index"]] = 0; call(mpu, symbols["draw_x"])
    assert mpu.memory[symbols["board_state"]] == 1
    patch = (ROOT / "assets" / "crystal-palace-screen-states" / "cells" / "x-cells.bitmap.bin").read_bytes()
    destinations = (ROOT / "assets" / "crystal-palace-screen-states" / "cells" / "bitmap-destination-addresses.bin").read_bytes()
    for offset, value in enumerate(patch[:100]):
        address = int.from_bytes(destinations[offset * 2 : offset * 2 + 2], "little")
        assert mpu.memory[address] == value
    assert (mpu.memory[0x0400 + 4 * 40 + 15] >> 4) == 10  # source-exact light-red X

    mpu.memory[symbols["game_index"]] = 1; call(mpu, symbols["draw_o"])
    assert mpu.memory[symbols["board_state"] + 1] == 2
    assert (mpu.memory[0x0400 + 4 * 40 + 19] >> 4) == 3  # source-exact cyan O
    # Human paint is immediate visual acknowledgement, not model inference;
    # the supplied baseline beneath the board remains unchanged.
    for index in range(12):
        start = 0x11F4 + index * 8
        assert bytes(mpu.memory[0x31F4 + index * 8 : 0x31F8 + index * 8]) == expected_bitmap[start : start + 4]


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
    title[882:886] = bytes((9, 14, 6, 15))
    title[922:926] = bytes((17, 21, 9, 20))
    for offset in (242, 282, 321, 322): title[offset] = 0
    assert bytes(mpu.memory[0x0400 : 0x07E8]) == bytes(title)
    prepare_info_archive_load(mpu)
    call(mpu, symbols["show_info"])
    source_info = bytearray((ASSETS / "crystal-palace-info.screen.bin").read_bytes())
    source_info[23 * 40 + 4 : 24 * 40 - 1] = bytes((0, 0, 0, 0, 0, 0, 19, 3, 18, 15, 12, 12, 38, 0, 21, 16, 41, 4, 15, 23, 14, 0, 17, 21, 9, 20, 38, 0, 17, 0, 0, 0, 0, 0, 0))
    assert bytes(mpu.memory[0x0400 : 0x04A5]) == source_info[:165]
    assert bytes(mpu.memory[0x076B : 0x07E8]) == bytes(source_info[875:])


def test_middle_mark_does_not_repaint_the_top_mark_shared_attribute_row(tmp_path):
    """Rows d-f begin one raster line into the preceding character row.

    That row belongs to a-c's final diagonal byte. Its screen/color attributes
    must not be copied from d-f's empty leading source row, or a later O changes
    the earlier X's border/colour definition.
    """
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

    mpu.memory[symbols["game_index"]] = 0  # a: last mark scanline is character row 6
    call(mpu, symbols["draw_x"])
    shared_screen = bytes(mpu.memory[0x0400 + 6 * 40 + 14 : 0x0400 + 6 * 40 + 18])
    shared_colour = bytes(mpu.memory[0xD800 + 6 * 40 + 14 : 0xD800 + 6 * 40 + 18])

    mpu.memory[symbols["game_index"]] = 3  # d: first source attribute row is empty
    call(mpu, symbols["draw_o"])

    assert bytes(mpu.memory[0x0400 + 6 * 40 + 14 : 0x0400 + 6 * 40 + 18]) == shared_screen
    assert bytes(mpu.memory[0xD800 + 6 * 40 + 14 : 0xD800 + 6 * 40 + 18]) == shared_colour


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
    prepare_info_archive_load(mpu)
    call(mpu, symbols["show_info"])
    source_info = bytearray((ASSETS / "crystal-palace-info.screen.bin").read_bytes())
    source_info[23 * 40 + 4 : 24 * 40 - 1] = bytes((0, 0, 0, 0, 0, 0, 19, 3, 18, 15, 12, 12, 38, 0, 21, 16, 41, 4, 15, 23, 14, 0, 17, 21, 9, 20, 38, 0, 17, 0, 0, 0, 0, 0, 0))
    assert bytes(mpu.memory[0x0400 : 0x04A5]) == source_info[:165]
    assert bytes(mpu.memory[0x076B : 0x07E8]) == bytes(source_info[875:])


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


def test_title_reloads_its_charset_even_when_already_in_title_mode(tmp_path):
    """A damaged title charset must not turn the known-black header into residue."""
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
    mpu.memory[symbols["view_mode"]] = 0
    mpu.memory[0x3800 : 0x4000] = b"\xff" * 2048

    call(mpu, symbols["show_title"])

    assert bytes(mpu.memory[0x3800 : 0x4000]) == (ASSETS / "crystal-palace-charset.bin").read_bytes()


def test_title_selection_changes_only_selector_cells_without_blanking_display(tmp_path):
    """A title navigation tap must not black out and repaint the full title."""
    import subprocess
    import pytest

    pytest.importorskip("py65")
    from py65.devices.mpu6502 import MPU
    sys.path.insert(0, str(ROOT / "tests"))
    from test_6502_embedding_gate import ASSEMBLER, call, labels

    class WriteTrace(list):
        def __init__(self, values):
            super().__init__(values)
            self.events = []

        def __setitem__(self, address, value):
            if isinstance(address, int) and (address == 0xD011 or 0x0400 <= address < 0x07E8):
                self.events.append((address, value, bool(self[0xD011] & 0x10)))
            super().__setitem__(address, value)

    prg, labels_path = tmp_path / "CP64.PRG", tmp_path / "embedded.lbl"
    subprocess.run([str(ASSEMBLER), "--cbm-prg", f"--labels={labels_path}", "-o", str(prg), str(ROOT / "src" / "art_embedded_title.asm")], check=True, capture_output=True, text=True)
    symbols = labels(labels_path); image = prg.read_bytes(); mpu = MPU(); load = int.from_bytes(image[:2], "little")
    mpu.memory[load : load + len(image) - 2] = image[2:]
    mpu.memory[symbols["title_mode"]] = 0
    mpu.memory[0xD011] = 0  # establish the selected state without displaying setup writes
    call(mpu, symbols["show_title"])
    mpu.memory[0xD011] = 0x10  # a visible character-mode title, as on the C64
    trace = WriteTrace(mpu.memory); mpu.memory = trace

    call(mpu, symbols["select_title_up"])

    assert mpu.memory[symbols["title_mode"]] == 2
    assert not [event for event in trace.events if event[0] == 0xD011 and not event[2]]
    assert not [event for event in trace.events if 0x0400 <= event[0] < 0x0570]
    assert not [event for event in trace.events if 0x0572 <= event[0] < 0x05C1]
    assert (0x05C1, 44, True) in trace.events


def test_title_blanks_only_the_four_unwanted_radar_glyph_cells(tmp_path):
    """The requested black title cells remove glyph noise without altering its art."""
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

    call(mpu, symbols["show_title"])

    for offset in (242, 282, 321, 322):
        assert mpu.memory[0x0400 + offset] == 0
        assert mpu.memory[0xD800 + offset] == 0


def test_title_actions_return_to_the_key_loop_without_falling_into_basic():
    """Display routines end in RTS, so title dispatch must enter them via JSR."""
    source = (ROOT / "src" / "art_embedded_title.asm").read_text()
    assert "title_number_game:\n    jsr show_game\n    jmp key_loop" in source
    assert "title_info:\n    jsr show_info\n    jmp key_loop" in source
    assert "title_down:\n    jsr select_title_down\n    jsr wait_title_down_release\n    jmp key_loop" in source
    assert "cmp #13                  ; RETURN/Enter" in source
    assert "wait_key_release:\n    lda #0\n    sta $c6" in source


def test_game_dispatch_accepts_browser_lowercase_a_to_i():
    source = (ROOT / "src" / "art_embedded_title.asm").read_text()
    assert "cmp #'a'" in source
    assert "sbc #'a'" in source
    assert "cmp #$c1" in source
    assert "sbc #$c1" in source


def test_archive_compiler_uses_the_supplied_charset_alphabet_and_blank_slot():
    """The supplied charset has a blank at 0 and A–Z in slots 1–26."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("compile_info_markdown", ROOT / "scripts" / "compile_info_markdown.py")
    compiler = importlib.util.module_from_spec(spec); spec.loader.exec_module(compiler)
    assert compiler.screen_code("A") == 1
    assert compiler.screen_code("Z") == 26
    assert compiler.screen_code(" ") == 0
    chars, _, _ = compiler.compile_data()
    assert chars[:7] == bytes((3, 18, 25, 19, 20, 1, 12))  # CRYSTAL


def test_archive_compiler_uses_verified_charset_punctuation_zero_padding_and_wraps_urls():
    """The supplied charset—not PETSCII—defines the archive's punctuation slots."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("compile_info_markdown", ROOT / "scripts" / "compile_info_markdown.py")
    compiler = importlib.util.module_from_spec(spec); spec.loader.exec_module(compiler)
    charset = (ASSETS / "crystal-palace-charset.bin").read_bytes()

    assert charset[0 * 8 : 1 * 8] == b"\x00" * 8
    assert charset[39 * 8 : 40 * 8] == bytes((0, 0, 0, 0, 0, 16, 16, 0))  # period
    assert charset[42 * 8 : 43 * 8] == bytes((0, 0, 0, 124, 0, 0, 0, 0))  # hyphen
    assert compiler.screen_code(".") == 39
    assert compiler.screen_code(",") == 40
    assert compiler.screen_code("/") == 41
    assert compiler.screen_code("-") == 42
    assert compiler.screen_code("|") == 55
    assert compiler.screen_code("0") == 27
    assert compiler.screen_code("9") == 36
    # The charset has no semicolon or curly-quote glyph; readable fallbacks
    # must use the available comma and straight quote instead.
    assert compiler.screen_code(";") == 40
    assert compiler.screen_code('"') == 47

    chars, _, _ = compiler.compile_data()
    # Digit glyph 5 occupies slot 32, so padding is proved at the known short
    # final row instead of forbidding that valid character code.
    assert chars[-20:] == bytes(20)
    text_lines = ["".join(character for character, _ in line) for line in compiler.parse_markdown(compiler.SOURCE.read_text())]
    assert text_lines[-2:] == ["- github.com/lewismoten/cryst", "al-palace"]


def test_archive_lists_and_quotes_use_only_readable_supplied_glyphs():
    """Green lists use hyphens and purple quotes omit unsupported curl marks."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("compile_info_markdown", ROOT / "scripts" / "compile_info_markdown.py")
    compiler = importlib.util.module_from_spec(spec); spec.loader.exec_module(compiler)
    text_lines = ["".join(character for character, _ in line) for line in compiler.parse_markdown(compiler.SOURCE.read_text())]

    assert text_lines[6] == "- X moves first."
    assert text_lines[11] == "A strange game. The only"
    assert text_lines[-2:] == ["- github.com/lewismoten/cryst", "al-palace"]


def test_archive_table_wraps_cells_without_clipping_columns():
    """A 29-cell table must retain every cell string, including its continuations."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("compile_info_markdown", ROOT / "scripts" / "compile_info_markdown.py")
    compiler = importlib.util.module_from_spec(spec); spec.loader.exec_module(compiler)

    lines = compiler.parse_markdown("""| Project | Role |
| --- | --- |
| Crystal Palace | The combined game and C64 experiment |
""")
    assert ["".join(character for character, _ in line) for line in lines] == [
        f"{'Project':<14} | {'Role':<12}",
        f"{'-' * 14} | {'-' * 12}",
        f"{'Crystal Palace':<14} | {'The combined':<12}",
        f"{'':<14} | {'game and C64':<12}",
        f"{'':<14} | {'experiment':<12}",
    ]

    hyphenated = compiler.table_rows(["Palace-9", "Strategic-fiction"], [14, 12])
    assert ["".join(character for character, _ in line) for line in hyphenated] == [
        f"{'Palace-9':<14} | {'Strategic-':<12}",
        f"{'':<14} | {'fiction':<12}",
    ]

    compound = compiler.table_rows(["Crystal-9", "Condensed mixture-of-experts neural model"], [14, 12])
    assert ["".join(character for character, _ in line) for line in compound] == [
        f"{'Crystal-9':<14} | {'Condensed':<12}",
        f"{'':<14} | {'mixture-of-':<12}",
        f"{'':<14} | {'experts':<12}",
        f"{'':<14} | {'neural model':<12}",
    ]


def test_archive_footer_centers_scroll_and_quit_commands(tmp_path):
    """The fixed footer clears stale continuation text and centers its commands."""
    import subprocess
    import pytest

    pytest.importorskip("py65")
    from py65.devices.mpu6502 import MPU
    sys.path.insert(0, str(ROOT / "tests"))
    from test_6502_embedding_gate import ASSEMBLER, call, labels

    subprocess.run([sys.executable, str(ROOT / "scripts" / "compile_info_markdown.py")], check=True)
    prg, labels_path = tmp_path / "CP64.PRG", tmp_path / "embedded.lbl"
    subprocess.run([str(ASSEMBLER), "--cbm-prg", f"--labels={labels_path}", "-o", str(prg), str(ROOT / "src" / "art_embedded_title.asm")], check=True, capture_output=True, text=True)
    symbols = labels(labels_path); image = prg.read_bytes(); mpu = MPU(); load = int.from_bytes(image[:2], "little")
    mpu.memory[load : load + len(image) - 2] = image[2:]

    prepare_info_archive_load(mpu)
    call(mpu, symbols["show_info"])

    footer = 23 * 40 + 4
    screen = bytes(mpu.memory[0x0400 + footer : 0x0400 + footer + 35])
    colours = bytes(mpu.memory[0xD800 + footer : 0xD800 + footer + 35])
    scroll = bytes((19, 3, 18, 15, 12, 12, 38, 0, 21, 16, 41, 4, 15, 23, 14))
    quit_command = bytes((17, 21, 9, 20, 38, 0, 17))

    assert screen == bytes(6) + scroll + b"\0" + quit_command + bytes(6)
    assert colours == bytes(6) + bytes((12,)) * 8 + bytes((1,)) * 7 + b"\0" + bytes((12,)) * 6 + b"\x01" + bytes(6)


def test_archive_renderer_banks_in_ram_for_the_a600_compiled_text():
    """$a600 is under BASIC ROM on C64 hardware; Py65 flat RAM cannot expose this."""
    source = (ROOT / "src" / "art_embedded_title.asm").read_text()
    render = source[source.index("render_info_markdown:") : source.index("game_key:")]
    assert "info_markdown_memory_config" in render
    assert "and #$fe" in render
    assert "sta $01" in render
    assert render.rfind("sta $01") > render.index("render_info_scrollbar:")


def test_info_colour_plane_is_relocated_beyond_the_title_charset_backup():
    """49 archive rows no longer fit below $b000 beside the title charset."""
    generated = (ROOT / "src" / "info_markdown.inc").read_text()
    assert "info_markdown_chars = $a600" in generated
    assert "info_markdown_colours = $b800" in generated


def test_info_cursor_down_is_checked_before_ambiguous_screen_code_q():
    """$11 is Cursor Down in GETIN and must scroll, not be consumed as Q."""
    source = (ROOT / "src" / "art_embedded_title.asm").read_text()
    info_key = source[source.index("info_key:") : source.index("key_not_game:")]
    assert info_key.index("cmp #$11") < info_key.index("cmp #17")


def test_title_hints_keep_the_shortcut_brighter_without_runtime_radar_mutation():
    source = (ROOT / "src" / "art_embedded_title.asm").read_text()
    shown = source[source.index("show_title:") : source.index("patch_title_variant:")]
    assert "jsr cleanup_title_radar_labels" in shown
    hints = source[source.index("patch_title_hints:") : source.index("set_title_vic:")]
    assert "lda #12" in hints  # descriptive INFO/QUIT text is dimmer light grey
    assert "lda #1                   ; bright white direct key" in hints


def test_two_player_input_alternates_x_and_o_and_terminal_wins_lock_the_board(tmp_path):
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
    mpu.memory[symbols["title_mode"]] = 2
    call(mpu, symbols["show_game"])
    for key in b"abcdefg":
        mpu.a = key
        call(mpu, symbols["process_game_key"])
    assert bytes(mpu.memory[symbols["board_state"] : symbols["board_state"] + 7]) == bytes((1, 2, 1, 2, 1, 2, 1))
    assert mpu.memory[symbols["game_winner"]] == 1
    before = bytes(mpu.memory[symbols["board_state"] : symbols["board_state"] + 9])
    mpu.a = ord("h"); call(mpu, symbols["process_game_key"])
    assert bytes(mpu.memory[symbols["board_state"] : symbols["board_state"] + 9]) == before


def test_title_variants_are_exact_deltas_over_the_single_player_base(tmp_path):
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
    for mode in (0, 2):
        mpu.memory[symbols["title_mode"]] = mode
        call(mpu, symbols["show_title"])
        expected_screen = bytearray((ASSETS / f"crystal-palace-title-player-{mode}.screen.bin").read_bytes())
        expected_colour = bytearray((ASSETS / f"crystal-palace-title-player-{mode}.color.bin").read_bytes())
        expected_screen[882:886] = bytes((9, 14, 6, 15)); expected_colour[882:886] = bytes((1, 12, 12, 12))
        expected_screen[922:926] = bytes((17, 21, 9, 20)); expected_colour[922:926] = bytes((1, 12, 12, 12))
        for offset in (242, 282, 321, 322):
            expected_screen[offset] = 0; expected_colour[offset] = 0
        for offset in (371, 451, 531): expected_colour[offset] = 7
        assert bytes(mpu.memory[0x0400 : 0x07E8]) == bytes(expected_screen)
        assert bytes(mpu.memory[0xD800 : 0xDBE8]) == bytes(expected_colour)


def test_lowercase_g_runs_the_actual_game_input_subroutine_without_disk_load(tmp_path):
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
    mpu.a = ord("g")
    call(mpu, symbols["process_game_key"])
    assert mpu.memory[symbols["board_state"] + 6] == 1
    assert "materialize_selected_embedding" not in (ROOT / "src" / "art_embedded_title.asm").read_text().split("process_game_key:", 1)[1].split("materialize_selected_embedding:", 1)[0]


def test_player_vs_ai_accepts_one_screen_code_x_then_locks_input_for_a_real_model_turn(tmp_path):
    """The browser's normal GETIN path delivers A–I as screen codes 1–9."""
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
    for screen_code in range(1, 10):
        mpu.a = screen_code
        call(mpu, symbols["process_game_key"])
    assert bytes(mpu.memory[symbols["board_state"] : symbols["board_state"] + 9]) == b"\x01" + b"\x00" * 8
    assert mpu.memory[symbols["game_ai_pending"]] == 1
    assert mpu.memory[symbols["turn_mark"]] == 2
    assert bytes(mpu.memory[0x3218 : 0x3220]) == b"\x00\x14\x41\x41\x41\x41\x14\x00"
    assert mpu.memory[0x0643] >> 4 == 3


def test_archive_markdown_is_compiled_and_scrolls_a_fixed_panel(tmp_path):
    import subprocess
    import pytest

    pytest.importorskip("py65")
    from py65.devices.mpu6502 import MPU
    sys.path.insert(0, str(ROOT / "tests"))
    from test_6502_embedding_gate import ASSEMBLER, call, labels
    subprocess.run([sys.executable, str(ROOT / "scripts" / "compile_info_markdown.py")], check=True)
    prg, labels_path = tmp_path / "CP64.PRG", tmp_path / "embedded.lbl"
    subprocess.run([str(ASSEMBLER), "--cbm-prg", f"--labels={labels_path}", "-o", str(prg), str(ROOT / "src" / "art_embedded_title.asm")], check=True, capture_output=True, text=True)
    symbols = labels(labels_path); image = prg.read_bytes(); mpu = MPU(); load = int.from_bytes(image[:2], "little")
    mpu.memory[load : load + len(image) - 2] = image[2:]
    prepare_info_archive_load(mpu)
    call(mpu, symbols["show_info"])
    first = bytes(mpu.memory[0x04A5 : 0x04A5 + 29])
    colours = bytes(mpu.memory[0xD8A5 : 0xD8A5 + 29])
    assert first[:7] == bytes((3, 18, 25, 19, 20, 1, 12))  # CRYSTAL custom charset codes
    assert colours[:7] == b"\x07" * 7
    assert mpu.memory[0x04C2] != 0
    call(mpu, symbols["archive_scroll_down"])
    assert mpu.memory[symbols["info_scroll"]] == 1
    assert bytes(mpu.memory[0x04A5 : 0x04A5 + 29]) != first
    for _ in range(80): call(mpu, symbols["archive_scroll_down"])
    assert mpu.memory[symbols["info_scroll"]] == 31
    # The final wrapped URL reaches the last content row; no blank viewport rows
    # or clipped tail remain at the absolute end of the archive.
    last_row = 0x04A5 + 17 * 40
    assert bytes(mpu.memory[last_row : last_row + 9]) == bytes((1, 12, 42, 16, 1, 12, 1, 3, 5))  # AL-PALACE
    assert bytes(mpu.memory[last_row + 9 : last_row + 29]) == b"\0" * 20


def test_game_presentation_labels_empty_cells_shows_turns_and_reports_terminal_states(tmp_path):
    """The safe local two-player preview must explain board state without AI moves."""
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

    mpu.memory[symbols["title_mode"]] = 2
    call(mpu, symbols["show_game"])
    assert {"draw_empty_labels", "draw_turn_indicator", "game_terminal_tick", "game_winning_line", "game_terminal_ticks"} <= symbols.keys()
    label_bitmap = bytes(mpu.memory[symbols["label_bitmap_destinations"] : symbols["label_bitmap_destinations"] + 18])
    label_screen = bytes(mpu.memory[symbols["label_screen_destinations"] : symbols["label_screen_destinations"] + 18])
    expected_labels = (
        b"\x00\x14\x41\x55\x41\x41\x41\x00", b"\x00\x54\x41\x54\x41\x41\x54\x00",
        b"\x00\x15\x40\x40\x40\x40\x15\x00", b"\x00\x54\x41\x41\x41\x41\x54\x00",
        b"\x00\x55\x40\x54\x40\x40\x55\x00", b"\x00\x55\x40\x54\x40\x40\x40\x00",
        b"\x00\x15\x40\x45\x41\x41\x15\x00", b"\x00\x41\x41\x55\x41\x41\x41\x00",
        b"\x00\x55\x14\x14\x14\x14\x55\x00",
    )
    for index, glyph in enumerate(expected_labels):
        bitmap_address = int.from_bytes(label_bitmap[index * 2 : index * 2 + 2], "little")
        screen_address = int.from_bytes(label_screen[index * 2 : index * 2 + 2], "little")
        assert bytes(mpu.memory[bitmap_address : bitmap_address + 8]) == glyph
        assert mpu.memory[screen_address] >> 4 == 11  # dim-grey A-I labels

    # The one-cell turn status is centered on the board's midpoint below its
    # bottom grid edge: character row 14, column 19 (bitmap $3218/screen $0643).
    status_bitmap, status_screen = 0x3218, 0x0643
    assert bytes(mpu.memory[status_bitmap : status_bitmap + 8]) == b"\x00\x41\x41\x14\x14\x41\x41\x00"
    assert mpu.memory[status_screen] >> 4 == 10

    mpu.a = ord("a"); call(mpu, symbols["process_game_key"])
    assert mpu.memory[symbols["board_state"]] == 1
    assert mpu.memory[int.from_bytes(label_screen[:2], "little")] >> 4 == 10  # X replaces A in light red
    assert mpu.memory[symbols["turn_mark"]] == 2
    assert bytes(mpu.memory[status_bitmap : status_bitmap + 8]) == b"\x00\x14\x41\x41\x41\x41\x14\x00"
    assert mpu.memory[status_screen] >> 4 == 3  # next player is cyan O

    mpu.a = ord("b"); call(mpu, symbols["process_game_key"])
    assert mpu.memory[symbols["board_state"] + 1] == 2
    assert mpu.memory[int.from_bytes(label_screen[2:4], "little")] >> 4 == 3  # O replaces B in cyan
    for key in b"cdefg":
        mpu.a = key; call(mpu, symbols["process_game_key"])
    assert mpu.memory[symbols["game_winner"]] == 1
    assert mpu.memory[symbols["game_winning_line"]] == 21  # C-E-G diagonal
    assert mpu.memory[symbols["game_terminal_ticks"]] > 0
    winning_labels = [int.from_bytes(label_screen[index * 2 : index * 2 + 2], "little") for index in (2, 4, 6)]
    assert [mpu.memory[address] >> 4 for address in winning_labels] == [7, 7, 7]
    call(mpu, symbols["game_terminal_tick"])
    assert [mpu.memory[address] >> 4 for address in winning_labels] == [10, 10, 10]
    while mpu.memory[symbols["game_terminal_ticks"]]:
        call(mpu, symbols["game_terminal_tick"])
    assert mpu.memory[symbols["view_mode"]] == 0  # short terminal sequence returns to title


def test_two_player_draw_reports_draw_and_locks_the_board_without_an_ai_fallback(tmp_path):
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
    mpu.memory[symbols["title_mode"]] = 2
    call(mpu, symbols["show_game"])
    for key in b"abcedfhgi":
        mpu.a = key; call(mpu, symbols["process_game_key"])
    assert mpu.memory[symbols["game_winner"]] == 3
    assert mpu.memory[symbols["game_terminal_ticks"]] > 0
    assert mpu.memory[symbols["turn_indicator_colour"]] == 7
    before = bytes(mpu.memory[symbols["board_state"] : symbols["board_state"] + 9])
    mpu.a = ord("a"); call(mpu, symbols["process_game_key"])
    assert bytes(mpu.memory[symbols["board_state"] : symbols["board_state"] + 9]) == before


def test_archive_source_plane_harness_uses_every_blank_frame_row_and_keeps_scrollbar_visible(tmp_path):
    """The assembled INFO viewer must occupy the supplied frame's full 18-row cavity."""
    import importlib.util
    import subprocess
    import pytest

    pytest.importorskip("py65")
    from py65.devices.mpu6502 import MPU
    sys.path.insert(0, str(ROOT / "tests"))
    from test_6502_embedding_gate import ASSEMBLER, call, labels

    asset_screen = (ASSETS / "crystal-palace-info.screen.bin").read_bytes()
    asset_colour = (ASSETS / "crystal-palace-info.color.bin").read_bytes()
    panel_rows = [
        row for row in range(25)
        if asset_screen[row * 40 + 5 : row * 40 + 35] == bytes(30)
        and asset_screen[row * 40 + 4] != 0
        and asset_screen[row * 40 + 35] != 0
    ]
    assert panel_rows == list(range(4, 22))

    spec = importlib.util.spec_from_file_location("compile_info_markdown", ROOT / "scripts" / "compile_info_markdown.py")
    compiler = importlib.util.module_from_spec(spec); spec.loader.exec_module(compiler)
    chars, colours, line_count = compiler.compile_data()
    text_columns, scrollbar_column = 29, 34

    subprocess.run([sys.executable, str(ROOT / "scripts" / "compile_info_markdown.py")], check=True)
    prg, labels_path = tmp_path / "CP64.PRG", tmp_path / "embedded.lbl"
    subprocess.run([str(ASSEMBLER), "--cbm-prg", f"--labels={labels_path}", "-o", str(prg), str(ROOT / "src" / "art_embedded_title.asm")], check=True, capture_output=True, text=True)
    symbols = labels(labels_path); image = prg.read_bytes(); mpu = MPU(); load = int.from_bytes(image[:2], "little")
    mpu.memory[load : load + len(image) - 2] = image[2:]

    prepare_info_archive_load(mpu)
    call(mpu, symbols["show_info"])
    for viewport_row, source_row in enumerate(range(len(panel_rows))):
        offset = panel_rows[viewport_row] * 40
        expected = slice(source_row * text_columns, (source_row + 1) * text_columns)
        assert bytes(mpu.memory[0x0400 + offset + 5 : 0x0400 + offset + 34]) == chars[expected]
        assert bytes(mpu.memory[0xD800 + offset + 5 : 0xD800 + offset + 34]) == colours[expected]
        assert mpu.memory[0x0400 + offset + 35] == asset_screen[offset + 35]
        assert mpu.memory[0xD800 + offset + 35] == asset_colour[offset + 35]
    assert [mpu.memory[0x0400 + row * 40 + scrollbar_column] for row in panel_rows].count(42) == 1

    for _ in range(line_count + 1):
        call(mpu, symbols["archive_scroll_down"])
    maximum_scroll = line_count - len(panel_rows)
    assert mpu.memory[symbols["info_scroll"]] == maximum_scroll
    for viewport_row, row in enumerate(panel_rows):
        offset = row * 40
        source_row = maximum_scroll + viewport_row
        expected = slice(source_row * text_columns, (source_row + 1) * text_columns)
        assert bytes(mpu.memory[0x0400 + offset + 5 : 0x0400 + offset + 34]) == chars[expected]
        assert bytes(mpu.memory[0xD800 + offset + 5 : 0xD800 + offset + 34]) == colours[expected]
    scrollbar = [mpu.memory[0x0400 + row * 40 + scrollbar_column] for row in panel_rows]
    assert scrollbar.count(42) == 1
    assert scrollbar[-1] == 42
