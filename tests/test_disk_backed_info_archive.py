"""Regression coverage for the disk-backed INFO archive payload."""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).parents[1]


def load_module(name: str, relative: str):
    scripts = ROOT / "scripts"
    if str(scripts) not in __import__("sys").path:
        __import__("sys").path.insert(0, str(scripts))
    path = ROOT / relative
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_archive_compiler_writes_a_versioned_runtime_prg_without_embedding_text():
    compiler = load_module("compile_info_markdown", "scripts/compile_info_markdown.py")

    payload = compiler.archive_payload()
    chars, colours, line_count = compiler.compile_data()

    assert payload[:2] == compiler.ARCHIVE_LOAD_ADDRESS.to_bytes(2, "little")
    assert payload[2 : 2 + compiler.ARCHIVE_HEADER_SIZE] == b"ARCV\x01" + line_count.to_bytes(2, "little") + bytes((compiler.WIDTH,))
    assert payload[2 + compiler.ARCHIVE_HEADER_SIZE :] == chars + colours
    assert "info_markdown_chars:" not in compiler.OUTPUT.read_text()


def test_info_runtime_loads_and_validates_only_the_archive_on_info_entry():
    source = (ROOT / "src" / "art_embedded_title.asm").read_text()
    show_info = source[source.index("show_info:") : source.index("show_game:")]
    loader = source[source.index("load_info_archive:") : source.index("show_game:")]
    game_input = source[source.index("process_game_key:") : source.index("materialize_selected_embedding:")]

    assert show_info.index("jsr load_info_archive") < show_info.index("jsr copy_screen")
    assert 'archive_filename: .text "ARCHIVE.PRG"' in loader
    assert "jsr LOAD" in loader
    assert "cmp #'A'" in loader and "cmp #'V'" in loader
    assert "ARCHIVE_COPY_FULL_PAGES" in loader and "ARCHIVE_COPY_TAIL" in loader
    assert "jsr LOAD" not in game_input


def test_d64_can_contain_a_readable_sequential_markdown_file(tmp_path):
    d64 = load_module("make_d64", "scripts/make_d64.py")
    markdown = b"# Archive\n\nReadable disk text.\n"
    payload = tmp_path / "ARCHIVE.MD"
    payload.write_bytes(markdown)
    image = tmp_path / "archive.d64"

    d64.build_d64_files({"ARCHIVE.MD": (payload, d64.SEQ_FILE_TYPE)}, image, disk_name="CP64 ARCHIVE")

    directory = d64.sector_offset(d64.DIRECTORY_TRACK, d64.DIRECTORY_SECTOR)
    assert image.read_bytes()[directory + 2] == d64.SEQ_FILE_TYPE
    assert d64.extract_d64_file(image, "ARCHIVE.MD") == markdown


def test_release_builder_packages_runtime_payload_and_readable_markdown():
    builder = load_module("build_disk", "scripts/build_disk.py")

    assert (builder.CURRENT_STAGE, builder.CURRENT_DESCRIPTION) == (85, "title-input-and-runtime-plane-recovery")
    assert builder.ARCHIVE_RUNTIME_FILENAME == "ARCHIVE.PRG"
    assert builder.ARCHIVE_MARKDOWN_FILENAME == "ARCHIVE.MD"
