#!/usr/bin/env python3
"""Render source-exact Crystal Palace VIC-II screen states as indexed PNGs.

The binary planes remain authoritative.  The PNGs are review transports: every
pixel is an index in the fixed C64/Pepto 16-colour palette below, with no RGB
conversion, filtering, alpha, or non-C64 palette entries.
"""
from __future__ import annotations

import argparse
import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).parents[1]
ASSETS = ROOT / "assets" / "crystal-palace-screen-states"
WIDTH = 320
HEIGHT = 200

# C64 Pepto palette, indexed by the native VIC-II colour number 0..15.
C64_PALETTE = (
    (0x00, 0x00, 0x00),  # 0 black
    (0xFF, 0xFF, 0xFF),  # 1 white
    (0x68, 0x37, 0x2B),  # 2 red
    (0x70, 0xA4, 0xB2),  # 3 cyan
    (0x6F, 0x3D, 0x86),  # 4 purple
    (0x58, 0x8D, 0x43),  # 5 green
    (0x35, 0x28, 0x79),  # 6 blue
    (0xB8, 0xC7, 0x6F),  # 7 yellow
    (0x6F, 0x4F, 0x25),  # 8 orange
    (0x43, 0x39, 0x00),  # 9 brown
    (0x9A, 0x67, 0x59),  # 10 light red
    (0x44, 0x44, 0x44),  # 11 dark grey
    (0x6C, 0x6C, 0x6C),  # 12 medium grey
    (0x9A, 0xD2, 0x84),  # 13 light green
    (0x6C, 0x5E, 0xB5),  # 14 light blue
    (0x95, 0x95, 0x95),  # 15 light grey
)


class StateError(ValueError):
    pass


def read_exact(name: str, size: int) -> bytes:
    data = (ASSETS / name).read_bytes()
    if len(data) != size:
        raise StateError(f"{name}: expected {size} bytes, found {len(data)}")
    return data


def render_character_state(screen_name: str, color_name: str) -> bytes:
    """Render 40x25 standard-character mode using the supplied 256-glyph set."""
    charset = read_exact("crystal-palace-charset.bin", 2048)
    screen = read_exact(screen_name, 1000)
    color = read_exact(color_name, 1000)
    pixels = bytearray(WIDTH * HEIGHT)  # native background: VIC-II colour 0
    for cell_y in range(25):
        for cell_x in range(40):
            cell = cell_y * 40 + cell_x
            glyph = screen[cell] * 8
            foreground = color[cell] & 0x0F
            for scanline in range(8):
                pattern = charset[glyph + scanline]
                row = (cell_y * 8 + scanline) * WIDTH + cell_x * 8
                for bit in range(8):
                    if pattern & (0x80 >> bit):
                        pixels[row + bit] = foreground
    return bytes(pixels)


def render_multicolor_bitmap(bitmap_name: str, screen_name: str, color_name: str) -> bytes:
    """Render VIC-II 160x200 multicolour bitmap data into 320x200 pixels.

    Two source bits become one logical multicolour pixel and are written twice
    horizontally, matching the C64's physical-pixel display aspect.
    """
    bitmap = read_exact(bitmap_name, 8000)
    screen = read_exact(screen_name, 1000)
    color = read_exact(color_name, 1000)
    pixels = bytearray(WIDTH * HEIGHT)
    for char_y in range(25):
        for char_x in range(40):
            cell = char_y * 40 + char_x
            screen_byte = screen[cell]
            colours = (0, screen_byte >> 4, screen_byte & 0x0F, color[cell] & 0x0F)
            bitmap_base = cell * 8
            for scanline in range(8):
                pattern = bitmap[bitmap_base + scanline]
                row = (char_y * 8 + scanline) * WIDTH + char_x * 8
                for pair in range(4):
                    native_colour = colours[(pattern >> (6 - pair * 2)) & 0x03]
                    pixels[row + pair * 2] = native_colour
                    pixels[row + pair * 2 + 1] = native_colour
    return bytes(pixels)


def chunk(name: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", len(payload)) + name + payload + struct.pack(">I", zlib.crc32(name + payload) & 0xFFFFFFFF)


def indexed_png(pixels: bytes) -> bytes:
    if len(pixels) != WIDTH * HEIGHT:
        raise StateError(f"expected {WIDTH * HEIGHT} indexed pixels, found {len(pixels)}")
    if any(pixel > 15 for pixel in pixels):
        raise StateError("render produced an index outside the C64 palette")
    rows = b"".join(b"\0" + pixels[row * WIDTH : (row + 1) * WIDTH] for row in range(HEIGHT))
    palette = bytes(channel for rgb in C64_PALETTE for channel in rgb)
    return b"".join((
        b"\x89PNG\r\n\x1a\n",
        chunk(b"IHDR", struct.pack(">IIBBBBB", WIDTH, HEIGHT, 8, 3, 0, 0, 0)),
        chunk(b"PLTE", palette),
        chunk(b"IDAT", zlib.compress(rows, level=9)),
        chunk(b"IEND", b""),
    ))


STATES = {
    "crystal-palace-title-player-0.png": lambda: render_character_state(
        "crystal-palace-title-player-0.screen.bin", "crystal-palace-title-player-0.color.bin"),
    "crystal-palace-title-player-1.png": lambda: render_character_state(
        "crystal-palace-title-player-1.screen.bin", "crystal-palace-title-player-1.color.bin"),
    "crystal-palace-title-player-2.png": lambda: render_character_state(
        "crystal-palace-title-player-2.screen.bin", "crystal-palace-title-player-2.color.bin"),
    "crystal-palace-info.png": lambda: render_character_state(
        "crystal-palace-info.screen.bin", "crystal-palace-info.color.bin"),
    "crystal-palace-game-blank.png": lambda: render_multicolor_bitmap(
        "crystal-palace-game-blank.bitmap.bin", "crystal-palace-game-blank.screen.bin", "crystal-palace-game-blank.color.bin"),
    "crystal-palace-game-all-x.png": lambda: render_multicolor_bitmap(
        "crystal-palace-game-all-x.bitmap.bin", "crystal-palace-game-all-x.screen.bin", "crystal-palace-game-all-x.color.bin"),
    "crystal-palace-game-all-o.png": lambda: render_multicolor_bitmap(
        "crystal-palace-game-all-o.bitmap.bin", "crystal-palace-game-all-o.screen.bin", "crystal-palace-game-all-o.color.bin"),
}


def write_previews() -> list[Path]:
    output = []
    for name, renderer in STATES.items():
        path = ASSETS / name
        path.write_bytes(indexed_png(renderer()))
        output.append(path)
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if checked-in previews differ from a fresh render")
    args = parser.parse_args()
    expected = {ASSETS / name: indexed_png(renderer()) for name, renderer in STATES.items()}
    if args.check:
        stale = [path.name for path, content in expected.items() if not path.is_file() or path.read_bytes() != content]
        if stale:
            raise SystemExit("stale screen-state preview(s): " + ", ".join(stale))
        print(f"verified {len(expected)} C64 indexed PNG previews")
    else:
        for path, content in expected.items():
            path.write_bytes(content)
            print(path.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
