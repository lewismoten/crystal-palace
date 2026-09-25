#!/usr/bin/env python3
"""Create a standard 35-track CBM DOS D64 containing PRG files."""
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


def interleaved_sectors(track: int, count: int, interleave: int = 10) -> list[int]:
    """Return a rotationally interleaved sector order for one D64 track."""
    sectors = sectors_on_track(track)
    if not 0 <= count <= sectors or math.gcd(interleave, sectors) != 1:
        raise ValueError("invalid interleave or sector count")
    return [(index * interleave) % sectors for index in range(count)]


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
    build_d64_files({prg_path.name: prg_path}, output_path, disk_name)


def build_d64_files(files: dict[str, Path], output_path: Path, disk_name: str = "CP64 MODEL") -> None:
    """Write named PRGs to a D64, chaining directory sectors as required."""
    if not files:
        raise ValueError("D64 requires at least one file")
    if any(len(name) > 16 for name in files):
        raise ValueError("CBM DOS file names are limited to sixteen characters")
    directory_sectors = math.ceil(len(files) / 8)
    if directory_sectors >= sectors_on_track(DIRECTORY_TRACK):
        raise ValueError("too many files for this minimal D64 writer")

    image = bytearray(174_848)
    free = {(track, sector) for track in range(1, 36) for sector in range(sectors_on_track(track))}
    reserved = {(BAM_TRACK, BAM_SECTOR)} | {(DIRECTORY_TRACK, sector) for sector in range(DIRECTORY_SECTOR, DIRECTORY_SECTOR + directory_sectors)}
    free -= reserved
    payloads = [(name, path.read_bytes()) for name, path in files.items()]
    if any(len(payload) < 3 for _, payload in payloads):
        raise ValueError("every PRG must contain a two-byte load address and code")
    needed = sum(math.ceil(len(payload) / 254) for _, payload in payloads)
    def rotational_order(track: int) -> list[tuple[int, int]]:
        sectors = sectors_on_track(track)
        interleave = 10 if math.gcd(10, sectors) == 1 else 7
        return [(track, sector) for sector in interleaved_sectors(track, sectors, interleave) if (track, sector) in free]

    available = [address for track in range(1, 36) for address in rotational_order(track)]
    if needed > len(available):
        raise ValueError("files do not fit on a standard 35-track D64")

    chains: list[tuple[str, list[tuple[int, int]]]] = []
    cursor = 0
    for name, payload in payloads:
        block_count = math.ceil(len(payload) / 254)
        chain = available[cursor : cursor + block_count]
        cursor += block_count
        for index, (track, sector) in enumerate(chain):
            offset = sector_offset(track, sector)
            chunk = payload[index * 254 : (index + 1) * 254]
            image[offset : offset + 2] = bytes(chain[index + 1]) if index + 1 < len(chain) else bytes((0, len(chunk) + 1))
            image[offset + 2 : offset + 2 + len(chunk)] = chunk
            free.remove((track, sector))
        chains.append((name, chain))

    bam = sector_offset(BAM_TRACK, BAM_SECTOR)
    image[bam : bam + 4] = bytes((DIRECTORY_TRACK, DIRECTORY_SECTOR, 0x41, 0))
    for track in range(1, 36):
        bitmap = sum(1 << sector for sector in range(sectors_on_track(track)) if (track, sector) in free)
        entry = bam + 4 + (track - 1) * 4
        image[entry : entry + 4] = bytes((bitmap.bit_count(), bitmap & 0xff, (bitmap >> 8) & 0xff, (bitmap >> 16) & 0xff))
    image[bam + 0x90 : bam + 0xA0] = petscii_name(disk_name)
    image[bam + 0xA2 : bam + 0xA4] = b"2A"

    for directory_index in range(directory_sectors):
        directory = sector_offset(DIRECTORY_TRACK, DIRECTORY_SECTOR + directory_index)
        next_sector = DIRECTORY_SECTOR + directory_index + 1
        image[directory : directory + 2] = bytes((DIRECTORY_TRACK, next_sector)) if directory_index + 1 < directory_sectors else bytes((0, 0xff))
    for index, (name, chain) in enumerate(chains):
        directory = sector_offset(DIRECTORY_TRACK, DIRECTORY_SECTOR + index // 8)
        entry = directory + 2 + (index % 8) * 32
        image[entry : entry + 4] = bytes((0x82, chain[0][0], chain[0][1], 0))
        image[entry + 5 : entry + 21] = petscii_name(name)
        image[entry + 28 : entry + 30] = len(chain).to_bytes(2, "little")

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
