#!/usr/bin/env python3
"""Compile editable Palace PNG sources into transient C64 binary planes."""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).parents[1]
ASSETS = ROOT / "assets"
OUTPUT = ROOT / "build" / "assets"

# C64 Pepto palette; every source PNG is indexed directly by VIC-II color ID.
C64_PALETTE = (
    (0x00, 0x00, 0x00), (0xFF, 0xFF, 0xFF), (0x68, 0x37, 0x2B), (0x70, 0xA4, 0xB2),
    (0x6F, 0x3D, 0x86), (0x58, 0x8D, 0x43), (0x35, 0x28, 0x79), (0xB8, 0xC7, 0x6F),
    (0x6F, 0x4F, 0x25), (0x43, 0x39, 0x00), (0x9A, 0x67, 0x59), (0x44, 0x44, 0x44),
    (0x6C, 0x6C, 0x6C), (0x9A, 0xD2, 0x84), (0x6C, 0x5E, 0xB5), (0x95, 0x95, 0x95),
)
TITLE_STATES = ("auto", "one", "two")
SOURCE_PNGS = (
    "charset/atlas.png",
    "title/glyph-map.png", "title/color-map.png",
    "info/glyph-map.png", "info/color-map.png",
    "game/board/bitmap-selectors.png", "game/board/screen-hi.png", "game/board/screen-lo.png", "game/board/color-lo.png",
    "game/marks/x.png", "game/marks/o.png",
)


class IndexedPNG:
    def __init__(self, width: int, height: int, palette: tuple[tuple[int, int, int], ...], pixels: bytes):
        self.width, self.height, self.palette, self.pixels = width, height, palette, pixels


def paeth(a: int, b: int, c: int) -> int:
    estimate = a + b - c
    da, db, dc = abs(estimate - a), abs(estimate - b), abs(estimate - c)
    return a if da <= db and da <= dc else b if db <= dc else c


def read_indexed_png(path: Path) -> IndexedPNG:
    payload = path.read_bytes()
    if payload[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"{path}: not a PNG")
    width = height = bit_depth = color_type = interlace = None
    palette = None
    compressed = bytearray()
    cursor = 8
    while cursor < len(payload):
        length = struct.unpack(">I", payload[cursor:cursor + 4])[0]
        kind = payload[cursor + 4:cursor + 8]
        chunk = payload[cursor + 8:cursor + 8 + length]
        cursor += length + 12
        if kind == b"IHDR":
            width, height, bit_depth, color_type, compression, filtering, interlace = struct.unpack(">IIBBBBB", chunk)
            if compression or filtering:
                raise ValueError(f"{path}: unsupported PNG compression/filter method")
        elif kind == b"PLTE":
            if len(chunk) != 48:
                raise ValueError(f"{path}: palette must have exactly 16 C64 entries")
            palette = tuple((chunk[index], chunk[index + 1], chunk[index + 2]) for index in range(0, 48, 3))
        elif kind == b"IDAT":
            compressed.extend(chunk)
        elif kind == b"IEND":
            break
    if None in (width, height) or bit_depth != 8 or color_type != 3 or interlace != 0 or palette is None:
        raise ValueError(f"{path}: expected a non-interlaced 8-bit indexed PNG")
    if palette != C64_PALETTE:
        raise ValueError(f"{path}: palette must be the project C64 palette")
    raw = zlib.decompress(compressed)
    if len(raw) != (width + 1) * height:
        raise ValueError(f"{path}: unexpected decompressed size")
    decoded = bytearray(width * height)
    previous = bytearray(width)
    cursor = 0
    for y in range(height):
        filter_kind = raw[cursor]; cursor += 1
        encoded = raw[cursor:cursor + width]; cursor += width
        row = bytearray(width)
        for x, value in enumerate(encoded):
            left, above, upper_left = (row[x - 1] if x else 0), previous[x], (previous[x - 1] if x else 0)
            if filter_kind == 0: row[x] = value
            elif filter_kind == 1: row[x] = (value + left) & 0xff
            elif filter_kind == 2: row[x] = (value + above) & 0xff
            elif filter_kind == 3: row[x] = (value + ((left + above) // 2)) & 0xff
            elif filter_kind == 4: row[x] = (value + paeth(left, above, upper_left)) & 0xff
            else: raise ValueError(f"{path}: unsupported PNG row filter {filter_kind}")
        decoded[y * width:(y + 1) * width] = row
        previous = row
    return IndexedPNG(width, height, palette, bytes(decoded))


def require_pixels(source: Path, relative: str, width: int, height: int) -> bytes:
    image = read_indexed_png(source / relative)
    if (image.width, image.height) != (width, height):
        raise ValueError(f"{relative}: expected {width}×{height}, got {image.width}×{image.height}")
    return image.pixels


def write_plane(output: Path, relative: str, payload: bytes) -> None:
    path = output / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def compile_charset(source: Path, output: Path) -> None:
    pixels = require_pixels(source, "charset/atlas.png", 128, 128)
    if any(index not in (0, 1) for index in pixels):
        raise ValueError("charset/atlas.png: glyph atlas must be black/white")
    charset = bytearray(2048)
    for glyph in range(256):
        origin_x, origin_y = glyph % 16 * 8, glyph // 16 * 8
        for scanline in range(8):
            charset[glyph * 8 + scanline] = sum((0x80 >> bit) for bit in range(8) if pixels[(origin_y + scanline) * 128 + origin_x + bit])
    write_plane(output, "charset.bin", bytes(charset))


def compile_character_state(source: Path, output: Path, relative: str) -> None:
    glyphs = require_pixels(source, f"{relative}/glyph-map.png", 80, 25)
    colors = require_pixels(source, f"{relative}/color-map.png", 40, 25)
    write_plane(output, f"{relative}/screen.bin", bytes((glyphs[cell * 2] << 4) | glyphs[cell * 2 + 1] for cell in range(1000)))
    write_plane(output, f"{relative}/color.bin", bytes(colors))


def compile_title_states(source: Path, output: Path) -> None:
    """Build title variants from one base map and small selector/color deltas."""
    glyphs = require_pixels(source, "title/glyph-map.png", 80, 25)
    base_screen = bytes((glyphs[cell * 2] << 4) | glyphs[cell * 2 + 1] for cell in range(1000))
    base_color = require_pixels(source, "title/color-map.png", 40, 25)
    selections = json.loads((source / "title/selection.json").read_text())
    if selections.get("base") != "one" or set(selections.get("states", {})) != set(TITLE_STATES):
        raise ValueError("title/selection.json: expected one base and auto/one/two states")
    for state in TITLE_STATES:
        screen, color = bytearray(base_screen), bytearray(base_color)
        for plane, destination in (("screen", screen), ("color", color)):
            for offset, value in selections["states"][state][plane]:
                if not 0 <= offset < 1000 or not 0 <= value < 256:
                    raise ValueError(f"title/selection.json: invalid {state} {plane} delta")
                destination[offset] = value
        write_plane(output, f"title/{state}/screen.bin", bytes(screen))
        write_plane(output, f"title/{state}/color.bin", bytes(color))


def compile_blank_board(source: Path, output: Path) -> None:
    selectors = require_pixels(source, "game/board/bitmap-selectors.png", 160, 200)
    high = require_pixels(source, "game/board/screen-hi.png", 40, 25)
    low = require_pixels(source, "game/board/screen-lo.png", 40, 25)
    color = require_pixels(source, "game/board/color-lo.png", 40, 25)
    if any(index > 3 for index in selectors):
        raise ValueError("game/board/bitmap-selectors.png: selectors must be 0..3")
    bitmap = bytearray(8000)
    for y in range(200):
        for x in range(160):
            cell = (y // 8) * 40 + x // 4
            bitmap[cell * 8 + y % 8] |= selectors[y * 160 + x] << (6 - 2 * (x % 4))
    write_plane(output, "game/blank/bitmap.bin", bytes(bitmap))
    write_plane(output, "game/blank/screen.bin", bytes((left << 4) | right for left, right in zip(high, low)))
    write_plane(output, "game/blank/color.bin", bytes(color))


def set_selector(bitmap: bytearray, x: int, y: int, selector: int) -> None:
    cell = (y // 8) * 40 + x // 4
    address = cell * 8 + y % 8
    shift = 6 - 2 * (x % 4)
    bitmap[address] = (bitmap[address] & ~(3 << shift)) | (selector << shift)


def exchange_local_selectors(bitmap: bytearray, screen_cell: int) -> None:
    """Swap selectors 01/10 in one bitmap cell without changing its pixels."""
    for scanline in range(8):
        address = screen_cell * 8 + scanline
        pattern = bitmap[address]
        swapped = 0
        for pair in range(4):
            selector = (pattern >> (6 - pair * 2)) & 3
            if selector == 1:
                selector = 2
            elif selector == 2:
                selector = 1
            swapped |= selector << (6 - pair * 2)
        bitmap[address] = swapped


def compile_mark_board(source: Path, output: Path, mark: str, cells: str = "abcdefghi", output_name: str | None = None, base_name: str = "game/blank") -> None:
    pixels = require_pixels(source, f"game/marks/{mark}.png", 14, 24)
    colors = {value for value in pixels if value}
    if not 1 <= len(colors) <= 2:
        raise ValueError(f"game/marks/{mark}.png: black background plus one or two C64 mark colors required")
    primary = 10 if mark == "x" else 3
    if primary not in colors:
        raise ValueError(f"game/marks/{mark}.png: primary color must be palette index {primary}")
    accent = next(iter(colors - {primary}), 0)
    bitmap = bytearray((output / f"{base_name}/bitmap.bin").read_bytes())
    blank_screen = (output / f"{base_name}/screen.bin").read_bytes()
    screen = bytearray(blank_screen)
    color_ram = bytearray((output / f"{base_name}/color.bin").read_bytes())
    coordinates = json.loads((source / "game/board/layout.json").read_text())["cell_rectangles"]
    remapped_cells: set[int] = set()
    for cell in cells:
        physical_x, physical_y, width, height = coordinates[cell]["preview_xywh"]
        if (width, height) != (28, 24):
            raise ValueError("board cell preview rectangles must stay 28×24")
        for y in range(24):
            for x in range(14):
                pixel = pixels[y * 14 + x]
                if pixel == 0:
                    continue
                logical_x = physical_x // 2 + x
                logical_y = physical_y + y
                screen_cell = (logical_y // 8) * 40 + logical_x // 4
                original = blank_screen[screen_cell]
                if screen_cell not in remapped_cells and original >> 4 and not (original & 0x0f):
                    # A grid line already owns selector 01. Move it to 10 so
                    # the mark can use 01 and keep the supplied pixels intact.
                    exchange_local_selectors(bitmap, screen_cell)
                    screen[screen_cell] = (primary << 4) | (original >> 4)
                    remapped_cells.add(screen_cell)
                elif screen_cell not in remapped_cells:
                    screen[screen_cell] = (primary << 4) | (original & 0x0f)
                    remapped_cells.add(screen_cell)
                if pixel == accent and accent:
                    color_ram[screen_cell] = accent
                    set_selector(bitmap, logical_x, logical_y, 3)
                else:
                    set_selector(bitmap, logical_x, logical_y, 1)
    relative = output_name or f"game/all-{mark}"
    write_plane(output, f"{relative}/bitmap.bin", bytes(bitmap))
    write_plane(output, f"{relative}/screen.bin", bytes(screen))
    write_plane(output, f"{relative}/color.bin", bytes(color_ram))


def bitmap_offsets(x_logical: int, y: int, width_logical: int, height: int) -> list[int]:
    first_char = (x_logical * 2) // 8
    if ((width_logical * 2) + 7) // 8 != 4:
        raise ValueError("board source must remain four bitmap bytes wide")
    offsets = []
    for scan_y in range(y, y + height + 1):
        char_y, scanline = divmod(scan_y, 8)
        offsets.extend((char_y * 40 + char_x) * 8 + scanline for char_x in range(first_char, first_char + 4))
    if len(offsets) != 100:
        raise ValueError("board source must remain 100 bitmap bytes per cell")
    return offsets


def compile_cells(source: Path, output: Path) -> None:
    coordinates = json.loads((source / "game/board/layout.json").read_text())["cell_rectangles"]
    bitmap_per_cell, screen_per_cell, destinations = [], [], []
    for cell in "abcdefghi":
        x, y, width, height = coordinates[cell]["logical_xywh"]
        addresses = bitmap_offsets(x, y, width, height)
        bitmap_per_cell.append(addresses)
        destinations.extend(0x2000 + address for address in addresses)
        first_char, first_row = (x * 2) // 8, y // 8
        screen_per_cell.append([row * 40 + column for row in range(first_row, first_row + 4) for column in range(first_char, first_char + 4)])
    write_plane(output, "game/cells/destinations.bin", b"".join(address.to_bytes(2, "little") for address in destinations))
    for mark in ("x", "o"):
        root = output / f"game/all-{mark}"
        bitmap, screen, color = (root / "bitmap.bin").read_bytes(), (root / "screen.bin").read_bytes(), (root / "color.bin").read_bytes()
        write_plane(output, f"game/cells/{mark}.bitmap.bin", bytes(bitmap[address] for group in bitmap_per_cell for address in group))
        write_plane(output, f"game/cells/{mark}.screen.bin", bytes(screen[address] for group in screen_per_cell for address in group))
        write_plane(output, f"game/cells/{mark}.color.bin", bytes(color[address] for group in screen_per_cell for address in group))


def validate_manifest(source: Path, output: Path) -> None:
    manifest = json.loads((source / "manifest.json").read_text())
    for relative, expected in manifest["generated_bins"].items():
        payload = (output / relative).read_bytes()
        if len(payload) != expected["bytes"] or hashlib.sha256(payload).hexdigest() != expected["sha256"]:
            raise ValueError(f"{relative}: PNG compilation changed the recorded C64 source-exact plane")


def compile_assets(source: Path = ASSETS, output: Path = OUTPUT) -> Path:
    for relative in SOURCE_PNGS:
        read_indexed_png(source / relative)
    compile_charset(source, output)
    compile_title_states(source, output)
    compile_character_state(source, output, "info")
    compile_blank_board(source, output)
    compile_mark_board(source, output, "x")
    compile_mark_board(source, output, "o")
    compile_mark_board(source, output, "x", "acegi", "game/marks-preview")
    compile_mark_board(source, output, "o", "bdfh", "game/marks-preview", "game/marks-preview")
    for suffix in ("screen", "color"):
        write_plane(output, f"runtime/title-one.{suffix}.bin", (output / f"title/one/{suffix}.bin").read_bytes())
    compile_cells(source, output)
    validate_manifest(source, output)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ASSETS)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    compile_assets(args.source, args.output)
    print(f"compiled {len(SOURCE_PNGS)} indexed PNG sources to {args.output}")


if __name__ == "__main__":
    main()
