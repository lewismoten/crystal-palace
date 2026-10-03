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


def test_stage_080_declares_archive_layout_and_board_planes():
    builder = load_builder()
    assert (builder.CURRENT_STAGE, builder.CURRENT_DESCRIPTION) == (80, "archive-layout-and-board-planes")
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
    expected_bitmap = (ASSETS / "crystal-palace-game-blank.bitmap.bin").read_bytes()
    assert bytes(mpu.memory[0x2000 : 0x3F40]) == expected_bitmap
    expected_screen = (ASSETS / "crystal-palace-game-blank.screen.bin").read_bytes()
    assert bytes(mpu.memory[0x0400 : 0x07E8]) == expected_screen
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
    assert bytes(mpu.memory[0x0400 : 0x07E8]) == bytes(title)
    call(mpu, symbols["show_info"])
    source_info = bytearray((ASSETS / "crystal-palace-info.screen.bin").read_bytes())
    source_info[23 * 40 + 24 : 23 * 40 + 39] = bytes((17, 38, 0, 17, 21, 9, 20, 0, 0, 0, 0, 0, 0, 0, 0))
    assert bytes(mpu.memory[0x0400 : 0x047D]) == source_info[:125]
    assert bytes(mpu.memory[0x0725 : 0x07E8]) == bytes(source_info[805:])


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
    call(mpu, symbols["show_info"])
    source_info = bytearray((ASSETS / "crystal-palace-info.screen.bin").read_bytes())
    source_info[23 * 40 + 24 : 23 * 40 + 39] = bytes((17, 38, 0, 17, 21, 9, 20, 0, 0, 0, 0, 0, 0, 0, 0))
    assert bytes(mpu.memory[0x0400 : 0x047D]) == source_info[:125]
    assert bytes(mpu.memory[0x0725 : 0x07E8]) == bytes(source_info[805:])


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
    assert compiler.screen_code("-") == 42
    assert compiler.screen_code(":") == 38
    assert compiler.screen_code("/") == 41

    chars, _, _ = compiler.compile_data()
    assert 32 not in chars  # padding must be the verified blank glyph 0, never glyph 32
    text_lines = ["".join(character for character, _ in line) for line in compiler.parse_markdown(compiler.SOURCE.read_text())]
    assert text_lines[-2:] == [". github.com/lewismoten/cryst", "al-palace"]


def test_archive_footer_is_q_quit_at_the_absolute_bottom(tmp_path):
    """The quit affordance belongs in the fixed footer, outside the scroll region."""
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

    call(mpu, symbols["show_info"])

    footer = 23 * 40 + 24
    assert bytes(mpu.memory[0x0400 + footer : 0x0400 + footer + 7]) == bytes((17, 38, 0, 17, 21, 9, 20))
    assert bytes(mpu.memory[0xD800 + footer : 0xD800 + footer + 7]) == bytes((1, 12, 12, 12, 12, 12, 12))
    assert bytes(mpu.memory[0x0400 + footer + 7 : 0x0400 + footer + 15]) == b"\0" * 8


def test_archive_renderer_banks_in_ram_for_the_a600_compiled_text():
    """$a600 is under BASIC ROM on C64 hardware; Py65 flat RAM cannot expose this."""
    source = (ROOT / "src" / "art_embedded_title.asm").read_text()
    render = source[source.index("render_info_markdown:") : source.index("game_key:")]
    assert "info_markdown_memory_config" in render
    assert "and #$fe" in render
    assert "sta $01" in render
    assert render.rfind("sta $01") > render.index("render_info_scrollbar:")


def test_info_cursor_down_is_checked_before_ambiguous_screen_code_q():
    """$11 is Cursor Down in GETIN and must scroll, not be consumed as Q."""
    source = (ROOT / "src" / "art_embedded_title.asm").read_text()
    info_key = source[source.index("info_key:") : source.index("key_not_game:")]
    assert info_key.index("cmp #$11") < info_key.index("cmp #17")


def test_title_hints_keep_the_shortcut_brighter_without_runtime_radar_mutation():
    source = (ROOT / "src" / "art_embedded_title.asm").read_text()
    shown = source[source.index("show_title:") : source.index("patch_title_variant:")]
    assert "cleanup_title_radar_labels" not in shown
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
    call(mpu, symbols["show_info"])
    first = bytes(mpu.memory[0x047D : 0x047D + 29])
    colours = bytes(mpu.memory[0xD87D : 0xD87D + 29])
    assert first[:7] == bytes((3, 18, 25, 19, 20, 1, 12))  # CRYSTAL custom charset codes
    assert colours[:7] == b"\x07" * 7
    assert mpu.memory[0x049A] != 0
    call(mpu, symbols["archive_scroll_down"])
    assert mpu.memory[symbols["info_scroll"]] == 1
    assert bytes(mpu.memory[0x047D : 0x047D + 29]) != first
    for _ in range(80): call(mpu, symbols["archive_scroll_down"])
    assert mpu.memory[symbols["info_scroll"]] == 24
    # The final wrapped URL reaches the last content row; no blank viewport rows
    # or clipped tail remain at the absolute end of the archive.
    last_row = 0x047D + 16 * 40
    assert bytes(mpu.memory[last_row : last_row + 9]) == bytes((1, 12, 42, 16, 1, 12, 1, 3, 5))  # AL-PALACE
    assert bytes(mpu.memory[last_row + 9 : last_row + 29]) == b"\0" * 20
