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


def test_stage_061_declares_silent_kernal_art_loader():
    builder = load_builder()
    assert (builder.CURRENT_STAGE, builder.CURRENT_DESCRIPTION) == (61, "silent-kernal-art-loader")
    assert builder.PROGRAM_SOURCE.name == "art_loader.asm"


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


def test_loader_source_has_splash_before_load_and_direct_page_progress_without_editor_output():
    source = (ROOT / "src" / "art_loader.asm").read_text()
    assert source.index("jsr preview_splash") < source.index("jsr preview_load_charset")
    assert "CRYSTAL PALACE 9" in source
    assert "LOADING NATIVE DISPLAY" in source
    assert "SETMSG = $ff90" in source
    assert source.index("jsr SETMSG") < source.index("jsr preview_load_charset")
    # Each real load advances an internal boundary, but after the charset becomes
    # active the source-exact screen/color pages are the visible progress.  No
    # CHROUT/cursor call may scroll or overwrite the direct $0400 dashboard.
    loader = source[source.index("preview_load_prg:") : source.index("preview_load_pages:")]
    assert "inc preview_progress_count" in loader
    assert "CHROUT" not in loader
    assert "preview_loading_label" not in source
    assert "name_t1s0" in source and "name_gbm7" in source and "name_ins3" in source


def test_loader_announces_each_native_page_pair_with_direct_screen_text():
    """Post-charset loads keep a real, ROM-readable page label without CHROUT."""
    source = (ROOT / "src" / "art_loader.asm").read_text()
    pages = source[source.index("preview_load_pages:") : source.index("preview_load_title:")]
    assert "jsr preview_page_label" in pages
    label = source[source.index("preview_page_label:") : source.index("preview_load_title:")]
    assert "TITLE SCREEN " in source
    assert "INFO SCREEN " in source
    assert "GAME BITMAP " in source
    assert "sta $d018" in label
    assert "sta (label_pointer),y" in label
    assert "sta (label_color_pointer),y" in label
    assert "CHROUT" not in label
