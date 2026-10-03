#!/usr/bin/env python3
"""Render source-exact Crystal Palace VIC-II planes as indexed PNG reviews.

The binary planes remain authoritative. Every output pixel is an index in the
fixed C64/Pepto 16-colour palette; no RGB conversion, alpha, or quantization is
used. Combined previews show the normal VIC-II result. Mono and colour-plane
previews expose the raw character and colour planes independently.
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

# C64 Pepto palette, indexed by native VIC-II colour number 0..15.
C64_PALETTE = (
    (0x00, 0x00, 0x00), (0xFF, 0xFF, 0xFF), (0x68, 0x37, 0x2B), (0x70, 0xA4, 0xB2),
    (0x6F, 0x3D, 0x86), (0x58, 0x8D, 0x43), (0x35, 0x28, 0x79), (0xB8, 0xC7, 0x6F),
    (0x6F, 0x4F, 0x25), (0x43, 0x39, 0x00), (0x9A, 0x67, 0x59), (0x44, 0x44, 0x44),
    (0x6C, 0x6C, 0x6C), (0x9A, 0xD2, 0x84), (0x6C, 0x5E, 0xB5), (0x95, 0x95, 0x95),
)


class StateError(ValueError):
    pass


def read_exact(name: str, size: int) -> bytes:
    data = (ASSETS / name).read_bytes()
    if len(data) != size:
        raise StateError(f"{name}: expected {size} bytes, found {len(data)}")
    return data


def render_character_state(screen_name: str, color_name: str) -> bytes:
    """Render 40×25 standard-character mode with the supplied custom charset."""
    charset = read_exact("crystal-palace-charset.bin", 2048)
    screen = read_exact(screen_name, 1000)
    colour = read_exact(color_name, 1000)
    pixels = bytearray(WIDTH * HEIGHT)
    for cell_y in range(25):
        for cell_x in range(40):
            cell = cell_y * 40 + cell_x
            glyph = screen[cell] * 8
            foreground = colour[cell] & 0x0F
            for scanline in range(8):
                pattern = charset[glyph + scanline]
                row = (cell_y * 8 + scanline) * WIDTH + cell_x * 8
                for bit in range(8):
                    if pattern & (0x80 >> bit):
                        pixels[row + bit] = foreground
    return bytes(pixels)


def render_character_screen_mono(screen_name: str) -> bytes:
    """Render only screen-character glyph bits: white ink on black."""
    charset = read_exact("crystal-palace-charset.bin", 2048)
    screen = read_exact(screen_name, 1000)
    pixels = bytearray(WIDTH * HEIGHT)
    for cell_y in range(25):
        for cell_x in range(40):
            glyph = screen[cell_y * 40 + cell_x] * 8
            for scanline in range(8):
                pattern = charset[glyph + scanline]
                row = (cell_y * 8 + scanline) * WIDTH + cell_x * 8
                for bit in range(8):
                    if pattern & (0x80 >> bit):
                        pixels[row + bit] = 1
    return bytes(pixels)


def render_colour_plane(color_name: str) -> bytes:
    """Render raw colour-RAM nibbles as 40×25 coloured 8×8 tiles."""
    colour = read_exact(color_name, 1000)
    pixels = bytearray(WIDTH * HEIGHT)
    for cell_y in range(25):
        for cell_x in range(40):
            value = colour[cell_y * 40 + cell_x] & 0x0F
            for scanline in range(8):
                row = (cell_y * 8 + scanline) * WIDTH + cell_x * 8
                pixels[row : row + 8] = bytes((value,)) * 8
    return bytes(pixels)


def render_charset_charmap() -> bytes:
    """Render all 256 custom characters as a 16×16 black-and-white atlas."""
    charset = read_exact("crystal-palace-charset.bin", 2048)
    pixels = bytearray(128 * 128)
    for glyph_index in range(256):
        glyph_x = (glyph_index % 16) * 8
        glyph_y = (glyph_index // 16) * 8
        for scanline in range(8):
            pattern = charset[glyph_index * 8 + scanline]
            row = (glyph_y + scanline) * 128 + glyph_x
            for bit in range(8):
                if pattern & (0x80 >> bit):
                    pixels[row + bit] = 1
    return bytes(pixels)


def render_multicolor_bitmap(bitmap_name: str, screen_name: str, color_name: str) -> bytes:
    """Render VIC-II multicolour bitmap data to 320×200 physical pixels.

    Each 2-bit logical pixel is expanded horizontally. Values map as 00: global
    background ($d021), 01: screen high nibble, 10: screen low nibble, 11:
    colour RAM nibble. This is three local colours plus one shared background.
    """
    bitmap = read_exact(bitmap_name, 8000)
    screen = read_exact(screen_name, 1000)
    colour = read_exact(color_name, 1000)
    pixels = bytearray(WIDTH * HEIGHT)
    for char_y in range(25):
        for char_x in range(40):
            cell = char_y * 40 + char_x
            screen_byte = screen[cell]
            colours = (0, screen_byte >> 4, screen_byte & 0x0F, colour[cell] & 0x0F)
            for scanline in range(8):
                pattern = bitmap[cell * 8 + scanline]
                row = (char_y * 8 + scanline) * WIDTH + char_x * 8
                for pair in range(4):
                    native_colour = colours[(pattern >> (6 - pair * 2)) & 0x03]
                    pixels[row + pair * 2 : row + pair * 2 + 2] = bytes((native_colour,)) * 2
    return bytes(pixels)


def chunk(name: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", len(payload)) + name + payload + struct.pack(">I", zlib.crc32(name + payload) & 0xFFFFFFFF)


def indexed_png(pixels: bytes, width: int = WIDTH, height: int = HEIGHT) -> bytes:
    if len(pixels) != width * height:
        raise StateError(f"expected {width * height} indexed pixels, found {len(pixels)}")
    if any(pixel > 15 for pixel in pixels):
        raise StateError("render produced an index outside the C64 palette")
    rows = b"".join(b"\0" + pixels[row * width : (row + 1) * width] for row in range(height))
    palette = bytes(channel for rgb in C64_PALETTE for channel in rgb)
    return b"".join((
        b"\x89PNG\r\n\x1a\n",
        chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 3, 0, 0, 0)),
        chunk(b"PLTE", palette),
        chunk(b"IDAT", zlib.compress(rows, level=9)),
        chunk(b"IEND", b""),
    ))


STATES = {
    "crystal-palace-title-player-0.png": lambda: render_character_state("crystal-palace-title-player-0.screen.bin", "crystal-palace-title-player-0.color.bin"),
    "crystal-palace-title-player-1.png": lambda: render_character_state("crystal-palace-title-player-1.screen.bin", "crystal-palace-title-player-1.color.bin"),
    "crystal-palace-title-player-2.png": lambda: render_character_state("crystal-palace-title-player-2.screen.bin", "crystal-palace-title-player-2.color.bin"),
    "crystal-palace-info.png": lambda: render_character_state("crystal-palace-info.screen.bin", "crystal-palace-info.color.bin"),
    "crystal-palace-game-blank.png": lambda: render_multicolor_bitmap("crystal-palace-game-blank.bitmap.bin", "crystal-palace-game-blank.screen.bin", "crystal-palace-game-blank.color.bin"),
    "crystal-palace-game-all-x.png": lambda: render_multicolor_bitmap("crystal-palace-game-all-x.bitmap.bin", "crystal-palace-game-all-x.screen.bin", "crystal-palace-game-all-x.color.bin"),
    "crystal-palace-game-all-o.png": lambda: render_multicolor_bitmap("crystal-palace-game-all-o.bitmap.bin", "crystal-palace-game-all-o.screen.bin", "crystal-palace-game-all-o.color.bin"),
}

DERIVED_VIEWS = {
    "crystal-palace-charset-charmap.png": lambda: (render_charset_charmap(), 128, 128),
    "crystal-palace-title-player-0.screen-mono.png": lambda: (render_character_screen_mono("crystal-palace-title-player-0.screen.bin"), WIDTH, HEIGHT),
    "crystal-palace-title-player-0.color-plane.png": lambda: (render_colour_plane("crystal-palace-title-player-0.color.bin"), WIDTH, HEIGHT),
    "crystal-palace-title-player-1.screen-mono.png": lambda: (render_character_screen_mono("crystal-palace-title-player-1.screen.bin"), WIDTH, HEIGHT),
    "crystal-palace-title-player-1.color-plane.png": lambda: (render_colour_plane("crystal-palace-title-player-1.color.bin"), WIDTH, HEIGHT),
    "crystal-palace-title-player-2.screen-mono.png": lambda: (render_character_screen_mono("crystal-palace-title-player-2.screen.bin"), WIDTH, HEIGHT),
    "crystal-palace-title-player-2.color-plane.png": lambda: (render_colour_plane("crystal-palace-title-player-2.color.bin"), WIDTH, HEIGHT),
    "crystal-palace-info.screen-mono.png": lambda: (render_character_screen_mono("crystal-palace-info.screen.bin"), WIDTH, HEIGHT),
    "crystal-palace-info.color-plane.png": lambda: (render_colour_plane("crystal-palace-info.color.bin"), WIDTH, HEIGHT),
}


def expected_images() -> dict[Path, bytes]:
    images = {ASSETS / name: indexed_png(renderer()) for name, renderer in STATES.items()}
    images.update({ASSETS / name: indexed_png(*renderer()) for name, renderer in DERIVED_VIEWS.items()})
    return images


def write_previews() -> list[Path]:
    expected = expected_images()
    for path, content in expected.items():
        path.write_bytes(content)
    return list(expected)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if checked-in previews differ from a fresh render")
    args = parser.parse_args()
    expected = expected_images()
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
