#!/usr/bin/env python3
"""Derive exact live bitmap-cell patches from Crystal Palace source planes."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
ASSETS = ROOT / "assets" / "crystal-palace-screen-states"
CELLS = ASSETS / "cells"
PATCH_BYTES_PER_CELL = 100


def bitmap_offsets(x_logical: int, y: int, width_logical: int, height: int) -> list[int]:
    """Return 100 source bitmap bytes: four chars wide × 25 raster lines.

    The supplied X shapes extend one raster line below their nominal 24-pixel
    crop at the top and middle board rows. A fixed 25-line source patch keeps
    that final diagonal byte with its owning cell while remaining inside the
    adjacent row's grid boundary.
    """
    first_char = (x_logical * 2) // 8
    char_count = ((width_logical * 2) + 7) // 8
    if char_count != 4:
        raise ValueError("expected four bitmap bytes per raster line")
    offsets: list[int] = []
    for scan_y in range(y, y + height + 1):
        char_y, scanline = divmod(scan_y, 8)
        for char_x in range(first_char, first_char + char_count):
            offsets.append((char_y * 40 + char_x) * 8 + scanline)
    if len(offsets) != PATCH_BYTES_PER_CELL:
        raise ValueError(f"expected {PATCH_BYTES_PER_CELL} offsets, got {len(offsets)}")
    return offsets


def main() -> None:
    coordinates = json.loads((ASSETS / "crystal-palace-board-coordinates.json").read_text())["cell_rectangles"]
    destinations: list[int] = []
    per_cell: list[list[int]] = []
    for cell in "abcdefghi":
        x, y, width, height = coordinates[cell]["logical_xywh"]
        offsets = bitmap_offsets(x, y, width, height)
        per_cell.append(offsets)
        destinations.extend(0x2000 + offset for offset in offsets)
    (CELLS / "bitmap-destination-addresses.bin").write_bytes(b"".join(address.to_bytes(2, "little") for address in destinations))
    for mark, source_name in (("x", "crystal-palace-game-all-x.bitmap.bin"), ("o", "crystal-palace-game-all-o.bitmap.bin")):
        source = (ASSETS / source_name).read_bytes()
        (CELLS / f"{mark}-cells.bitmap.bin").write_bytes(bytes(source[offset] for offsets in per_cell for offset in offsets))
    print(f"derived 9 × {PATCH_BYTES_PER_CELL}-byte exact bitmap patches")


if __name__ == "__main__":
    main()
