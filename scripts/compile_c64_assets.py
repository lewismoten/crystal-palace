#!/usr/bin/env python3
"""Compile editable indexed PNG sources into transient C64 binary planes.

PNG sources, the common 16×16 glyph atlas, and a digest manifest are committed.
All C64 .bin planes are generated beneath build/generated-assets immediately
before rendering, assembly, or disk packaging; no binary plane is authoritative.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).parents[1]
ASSETS = ROOT / "assets" / "crystal-palace-screen-states"

# C64 Pepto palette, indexed by native VIC-II colour number 0..15.
C64_PALETTE = (
    (0x00, 0x00, 0x00), (0xFF, 0xFF, 0xFF), (0x68, 0x37, 0x2B), (0x70, 0xA4, 0xB2),
    (0x6F, 0x3D, 0x86), (0x58, 0x8D, 0x43), (0x35, 0x28, 0x79), (0xB8, 0xC7, 0x6F),
    (0x6F, 0x4F, 0x25), (0x43, 0x39, 0x00), (0x9A, 0x67, 0x59), (0x44, 0x44, 0x44),
    (0x6C, 0x6C, 0x6C), (0x9A, 0xD2, 0x84), (0x6C, 0x5E, 0xB5), (0x95, 0x95, 0x95),
)
CHARACTER_STATES = ("title-player-0", "title-player-1", "title-player-2", "info")
GAME_STATES = ("blank", "all-x", "all-o")
SOURCE_PNGS = (
    "crystal-palace-charset-charmap.png",
    *(f"crystal-palace-{name}.{plane}.png" for name in CHARACTER_STATES for plane in ("glyph-map", "color-map")),
    *(f"crystal-palace-game-{state}.{plane}.png" for state in GAME_STATES for plane in ("bitmap-selectors", "screen-hi", "screen-lo", "color-lo")),
)


class IndexedPNG:
    def __init__(self, width: int, height: int, palette: tuple[tuple[int, int, int], ...], pixels: bytes):
        self.width = width
        self.height = height
        self.palette = palette
        self.pixels = pixels


def paeth(a: int, b: int, c: int) -> int:
    estimate = a + b - c
    left_distance = abs(estimate - a)
    above_distance = abs(estimate - b)
    corner_distance = abs(estimate - c)
    return a if left_distance <= above_distance and left_distance <= corner_distance else b if above_distance <= corner_distance else c


def read_indexed_png(path: Path) -> IndexedPNG:
    payload = path.read_bytes()
    if payload[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"{path}: not a PNG")
    width = height = None
    bit_depth = colour_type = interlace = None
    palette: tuple[tuple[int, int, int], ...] | None = None
    compressed = bytearray()
    cursor = 8
    while cursor < len(payload):
        length = struct.unpack(">I", payload[cursor:cursor + 4])[0]
        kind = payload[cursor + 4:cursor + 8]
        chunk = payload[cursor + 8:cursor + 8 + length]
        cursor += length + 12
        if kind == b"IHDR":
            width, height, bit_depth, colour_type, compression, filtering, interlace = struct.unpack(">IIBBBBB", chunk)
            if compression != 0 or filtering != 0:
                raise ValueError(f"{path}: unsupported PNG compression/filter method")
        elif kind == b"PLTE":
            if len(chunk) != 16 * 3:
                raise ValueError(f"{path}: palette must have 16 C64 entries")
            palette = tuple((chunk[index], chunk[index + 1], chunk[index + 2]) for index in range(0, len(chunk), 3))
        elif kind == b"IDAT":
            compressed.extend(chunk)
        elif kind == b"IEND":
            break
    if width is None or height is None or bit_depth != 8 or colour_type != 3 or interlace != 0 or palette is None:
        raise ValueError(f"{path}: expected a non-interlaced 8-bit indexed PNG")
    if palette != C64_PALETTE:
        raise ValueError(f"{path}: palette must be the project C64 palette")
    raw = zlib.decompress(compressed)
    stride = width
    if len(raw) != (stride + 1) * height:
        raise ValueError(f"{path}: unexpected decompressed size")
    decoded = bytearray(width * height)
    previous = bytearray(stride)
    cursor = 0
    for y in range(height):
        kind = raw[cursor]
        cursor += 1
        encoded = raw[cursor:cursor + stride]
        cursor += stride
        row = bytearray(stride)
        for x, value in enumerate(encoded):
            left = row[x - 1] if x else 0
            above = previous[x]
            upper_left = previous[x - 1] if x else 0
            if kind == 0:
                row[x] = value
            elif kind == 1:
                row[x] = (value + left) & 0xff
            elif kind == 2:
                row[x] = (value + above) & 0xff
            elif kind == 3:
                row[x] = (value + ((left + above) // 2)) & 0xff
            elif kind == 4:
                row[x] = (value + paeth(left, above, upper_left)) & 0xff
            else:
                raise ValueError(f"{path}: unsupported PNG row filter {kind}")
        decoded[y * width:(y + 1) * width] = row
        previous = row
    return IndexedPNG(width, height, palette, bytes(decoded))


def require_pixels(source: Path, relative: str, width: int, height: int) -> bytes:
    image = read_indexed_png(source / relative)
    if (image.width, image.height) != (width, height):
        raise ValueError(f"{relative}: expected {width}×{height}, got {image.width}×{image.height}")
    return image.pixels


def write_plane(output: Path, relative: str, payload: bytes) -> None:
    target = output / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)


def compile_charset(source: Path, output: Path) -> None:
    pixels = require_pixels(source, "crystal-palace-charset-charmap.png", 128, 128)
    if any(index not in (0, 1) for index in pixels):
        raise ValueError("crystal-palace-charset-charmap.png: glyph atlas is black/white only")
    charset = bytearray(2048)
    for glyph in range(256):
        origin_x = (glyph % 16) * 8
        origin_y = (glyph // 16) * 8
        for scanline in range(8):
            pattern = 0
            for bit in range(8):
                if pixels[(origin_y + scanline) * 128 + origin_x + bit]:
                    pattern |= 0x80 >> bit
            charset[glyph * 8 + scanline] = pattern
    write_plane(output, "crystal-palace-charset.bin", bytes(charset))


def compile_character_state(source: Path, output: Path, name: str) -> None:
    glyphs = require_pixels(source, f"crystal-palace-{name}.glyph-map.png", 80, 25)
    colours = require_pixels(source, f"crystal-palace-{name}.color-map.png", 40, 25)
    screen = bytes((glyphs[cell * 2] << 4) | glyphs[cell * 2 + 1] for cell in range(1000))
    # Colour RAM exposes only the low nibble; source contract fixes upper bits to zero.
    write_plane(output, f"crystal-palace-{name}.screen.bin", screen)
    write_plane(output, f"crystal-palace-{name}.color.bin", bytes(colours))


def compile_game_state(source: Path, output: Path, state: str) -> None:
    prefix = f"crystal-palace-game-{state}"
    selectors = require_pixels(source, f"{prefix}.bitmap-selectors.png", 160, 200)
    high = require_pixels(source, f"{prefix}.screen-hi.png", 40, 25)
    low = require_pixels(source, f"{prefix}.screen-lo.png", 40, 25)
    colour = require_pixels(source, f"{prefix}.color-lo.png", 40, 25)
    if any(index > 3 for index in selectors):
        raise ValueError(f"{prefix}: selector source permits only palette indices 0..3")
    bitmap = bytearray(8000)
    for y in range(200):
        for x in range(160):
            cell = (y // 8) * 40 + (x // 4)
            address = cell * 8 + y % 8
            bitmap[address] |= selectors[y * 160 + x] << (6 - 2 * (x % 4))
    write_plane(output, f"{prefix}.bitmap.bin", bytes(bitmap))
    write_plane(output, f"{prefix}.screen.bin", bytes((left << 4) | right for left, right in zip(high, low)))
    write_plane(output, f"{prefix}.color.bin", bytes(colour))


def bitmap_offsets(x_logical: int, y: int, width_logical: int, height: int) -> list[int]:
    first_char = (x_logical * 2) // 8
    char_count = ((width_logical * 2) + 7) // 8
    if char_count != 4:
        raise ValueError("board source must remain four bitmap bytes wide")
    offsets = []
    for scan_y in range(y, y + height + 1):
        char_y, scanline = divmod(scan_y, 8)
        offsets.extend((char_y * 40 + char_x) * 8 + scanline for char_x in range(first_char, first_char + char_count))
    if len(offsets) != 100:
        raise ValueError("board source must remain 100 bitmap bytes per cell")
    return offsets


def compile_cells(source: Path, output: Path) -> None:
    coordinates = json.loads((source / "crystal-palace-board-coordinates.json").read_text())["cell_rectangles"]
    bitmap_per_cell: list[list[int]] = []
    screen_per_cell: list[list[int]] = []
    destinations: list[int] = []
    for cell in "abcdefghi":
        x, y, width, height = coordinates[cell]["logical_xywh"]
        bitmap_addresses = bitmap_offsets(x, y, width, height)
        bitmap_per_cell.append(bitmap_addresses)
        destinations.extend(0x2000 + address for address in bitmap_addresses)
        first_char, first_row = (x * 2) // 8, y // 8
        screen_per_cell.append([row * 40 + column for row in range(first_row, first_row + 4) for column in range(first_char, first_char + 4)])
    write_plane(output, "cells/bitmap-destination-addresses.bin", b"".join(address.to_bytes(2, "little") for address in destinations))
    for mark, state in (("x", "all-x"), ("o", "all-o")):
        bitmap = (output / f"crystal-palace-game-{state}.bitmap.bin").read_bytes()
        screen = (output / f"crystal-palace-game-{state}.screen.bin").read_bytes()
        colour = (output / f"crystal-palace-game-{state}.color.bin").read_bytes()
        write_plane(output, f"cells/{mark}-cells.bitmap.bin", bytes(bitmap[address] for group in bitmap_per_cell for address in group))
        write_plane(output, f"cells/{mark}-cells.screen.bin", bytes(screen[address] for group in screen_per_cell for address in group))
        write_plane(output, f"cells/{mark}-cells.color.bin", bytes(colour[address] for group in screen_per_cell for address in group))


def validate_manifest(source: Path, output: Path) -> None:
    manifest = json.loads((source / "asset-manifest.json").read_text())
    for relative, expected in manifest["generated_bins"].items():
        payload = (output / relative).read_bytes()
        if len(payload) != expected["bytes"] or hashlib.sha256(payload).hexdigest() != expected["sha256"]:
            raise ValueError(f"{relative}: PNG compilation changed the recorded C64 source-exact plane")


def compile_assets(source: Path = ASSETS, output: Path = ROOT / "build" / "generated-assets") -> Path:
    for relative in SOURCE_PNGS:
        read_indexed_png(source / relative)
    compile_charset(source, output)
    for name in CHARACTER_STATES:
        compile_character_state(source, output, name)
    for state in GAME_STATES:
        compile_game_state(source, output, state)
    for suffix in ("screen", "color"):
        write_plane(output, f"runtime/crystal-palace-title-player-1.{suffix}.bin", (output / f"crystal-palace-title-player-1.{suffix}.bin").read_bytes())
    compile_cells(source, output)
    validate_manifest(source, output)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ASSETS)
    parser.add_argument("--output", type=Path, default=ROOT / "build" / "generated-assets")
    args = parser.parse_args()
    compile_assets(args.source, args.output)
    print(f"compiled {len(SOURCE_PNGS)} indexed PNG sources to {args.output}")


if __name__ == "__main__":
    main()
