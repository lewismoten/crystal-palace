#!/usr/bin/env python3
"""Create a minimal standard 35-track CBM DOS D64 containing one PRG."""
from __future__ import annotations

import math
from pathlib import Path

SECTOR_SIZE = 256
DIRECTORY_TRACK = 18
DIRECTORY_SECTOR = 1
BAM_TRACK = 18
BAM_SECTOR = 0


def sectors_on_track(track: int) -> int:
    if 1 <= track <= 17:
        return 21
    if 18 <= track <= 24:
        return 19
    if 25 <= track <= 30:
        return 18
    if 31 <= track <= 35:
        return 17
    raise ValueError(f"invalid track: {track}")


def sector_offset(track: int, sector: int) -> int:
    if not 1 <= track <= 35 or not 0 <= sector < sectors_on_track(track):
        raise ValueError(f"invalid sector address {track}/{sector}")
    return sum(sectors_on_track(number) for number in range(1, track)) * SECTOR_SIZE + sector * SECTOR_SIZE


def petscii_name(text: str, width: int = 16) -> bytes:
    encoded = text.upper().encode("ascii")[:width]
    if any(value < 0x20 or value > 0x5F for value in encoded):
        raise ValueError("disk and file names must be printable ASCII")
    return encoded.ljust(width, b"\xa0")


def build_d64(prg_path: Path, output_path: Path, disk_name: str = "CP64 MODEL") -> None:
    payload = prg_path.read_bytes()
    if len(payload) < 3:
        raise ValueError("PRG must contain a two-byte load address and code")

    image = bytearray(174_848)
    free = {(track, sector) for track in range(1, 36) for sector in range(sectors_on_track(track))}
    free.remove((BAM_TRACK, BAM_SECTOR))
    free.remove((DIRECTORY_TRACK, DIRECTORY_SECTOR))
    blocks = math.ceil(len(payload) / 254)
    available = [(track, sector) for track in range(1, 36) for sector in range(sectors_on_track(track)) if (track, sector) in free]
    if blocks > len(available):
        raise ValueError("PRG does not fit on a standard 35-track D64")
    chain = available[:blocks]

    for index, (track, sector) in enumerate(chain):
        offset = sector_offset(track, sector)
        chunk = payload[index * 254 : (index + 1) * 254]
        if index + 1 < len(chain):
            image[offset : offset + 2] = bytes(chain[index + 1])
        else:
            image[offset : offset + 2] = bytes((0, len(chunk) + 1))
        image[offset + 2 : offset + 2 + len(chunk)] = chunk
        free.remove((track, sector))

    bam = sector_offset(BAM_TRACK, BAM_SECTOR)
    image[bam : bam + 4] = bytes((DIRECTORY_TRACK, DIRECTORY_SECTOR, 0x41, 0))
    for track in range(1, 36):
        bitmap = 0
        count = 0
        for sector in range(sectors_on_track(track)):
            if (track, sector) in free:
                count += 1
                bitmap |= 1 << sector
        entry = bam + 4 + (track - 1) * 4
        image[entry : entry + 4] = bytes((count, bitmap & 0xff, (bitmap >> 8) & 0xff, (bitmap >> 16) & 0xff))
    image[bam + 0x90 : bam + 0xA0] = petscii_name(disk_name)
    image[bam + 0xA2 : bam + 0xA4] = b"2A"

    directory = sector_offset(DIRECTORY_TRACK, DIRECTORY_SECTOR)
    image[directory : directory + 2] = bytes((0, 0xFF))
    entry = directory + 2
    image[entry : entry + 4] = bytes((0x82, chain[0][0], chain[0][1], 0))
    image[entry + 3 : entry + 19] = petscii_name(prg_path.stem)
    image[entry + 28 : entry + 30] = blocks.to_bytes(2, "little")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(image)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prg", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--disk-name", default="CP64 MODEL")
    args = parser.parse_args()
    build_d64(args.prg, args.output, args.disk_name)
