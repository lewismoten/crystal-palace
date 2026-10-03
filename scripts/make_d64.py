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


def estimate_next_sector_window(previous: tuple[int, int], target_track: int) -> int:
    """Model the 1541's expected next-sector arrival window.

    The constants match storage-d64's timing model: about nine sectors for a
    same-track read, four sectors for a one-track seek, otherwise two plus two
    sectors per track step.  The target track's sector count owns the modulo.
    """
    previous_track, previous_sector = previous
    seek = abs(target_track - previous_track)
    advance = 9 if seek == 0 else 4 if seek == 1 else 2 + seek * 2
    return (previous_sector + min(advance, sectors_on_track(target_track))) % sectors_on_track(target_track)


def rotational_distance(expected_sector: int, actual_sector: int, track: int) -> int:
    return (actual_sector - expected_sector) % sectors_on_track(track)


def link_score(previous: tuple[int, int], current: tuple[int, int]) -> float:
    expected = estimate_next_sector_window(previous, current[0])
    delay = rotational_distance(expected, current[1], current[0])
    return 100.0 * (1.0 - delay / (sectors_on_track(current[0]) - 1))


def directory_sector_order(count: int) -> list[int]:
    """Allocate the linked track-18 directory sectors at interleave three."""
    if count >= sectors_on_track(DIRECTORY_TRACK):
        raise ValueError("too many directory sectors")
    result: list[int] = []
    sector = DIRECTORY_SECTOR
    while len(result) < count:
        if sector != BAM_SECTOR and sector not in result:
            result.append(sector)
        sector = (sector + 3) % sectors_on_track(DIRECTORY_TRACK)
    return result


def next_directory_sector(sector: int) -> int:
    """Advance directory interleave three without ever targeting BAM sector 0."""
    candidate = (sector + 3) % sectors_on_track(DIRECTORY_TRACK)
    while candidate == BAM_SECTOR:
        candidate = (candidate + 3) % sectors_on_track(DIRECTORY_TRACK)
    return candidate


def centre_out_tracks() -> list[int]:
    return [track for distance in range(1, 18) for track in (DIRECTORY_TRACK - distance, DIRECTORY_TRACK + distance) if 1 <= track <= 35]


def first_free_sector(free: set[tuple[int, int]]) -> tuple[int, int]:
    for track in centre_out_tracks():
        candidates = [address for address in free if address[0] == track]
        if candidates:
            return min(candidates, key=lambda address: address[1])
    raise ValueError("D64 is full")


def file_start_order() -> list[tuple[int, int]]:
    """Spread independent file starts across rotational slots near track 18."""
    order: list[tuple[int, int]] = []
    for track in centre_out_tracks():
        sectors = sectors_on_track(track)
        interleave = 10 if math.gcd(10, sectors) == 1 else 7
        order.extend((track, sector) for sector in interleaved_sectors(track, sectors, interleave))
    return order


def smart_next_sector(free: set[tuple[int, int]], previous: tuple[int, int]) -> tuple[int, int]:
    """Choose a free block by seek cost first, rotational latency second."""
    def cost(address: tuple[int, int]) -> tuple[int, int, int, int]:
        track, sector = address
        seek = abs(track - previous[0])
        rotation = rotational_distance(estimate_next_sector_window(previous, track), sector, track)
        # Moving across track 18 switches physical sides on a 1541 layout.
        side_switch = int((track < DIRECTORY_TRACK) != (previous[0] < DIRECTORY_TRACK))
        return seek * 100 + rotation * 3 + side_switch * 180 + abs(track - DIRECTORY_TRACK) * 2, seek, rotation, sector
    candidates = (address for address in free if address[0] != DIRECTORY_TRACK)
    return min(candidates, key=cost)


def score_d64_layout(image_path: Path) -> dict[str, float]:
    """Return storage-d64-compatible rotational link scores for a finished D64."""
    image = image_path.read_bytes()
    directory_scores: list[float] = []
    data_scores: list[float] = []
    track, sector = DIRECTORY_TRACK, DIRECTORY_SECTOR
    seen_directories: set[tuple[int, int]] = set()
    while track:
        address = (track, sector)
        if address in seen_directories:
            raise ValueError("looped directory chain")
        seen_directories.add(address)
        directory = sector_offset(*address)
        next_track, next_sector = image[directory], image[directory + 1]
        if next_track:
            # Directory traversal is a fixed +3 sector interleave, distinct
            # from the data-sector head/rotation timing model.
            expected = next_directory_sector(sector)
            delay = rotational_distance(expected, next_sector, DIRECTORY_TRACK)
            directory_scores.append(100.0 * (1.0 - delay / (sectors_on_track(DIRECTORY_TRACK) - 1)))
        for index in range(8):
            entry = directory + 2 + index * 32
            if not image[entry]:
                continue
            blocks = int.from_bytes(image[entry + 28 : entry + 30], "little")
            file_track, file_sector = image[entry + 1], image[entry + 2]
            for block in range(blocks - 1):
                offset = sector_offset(file_track, file_sector)
                following = (image[offset], image[offset + 1])
                data_scores.append(link_score((file_track, file_sector), following))
                file_track, file_sector = following
        track, sector = next_track, next_sector
    scores = [*directory_scores, *data_scores]
    return {
        "average": sum(scores) / len(scores) if scores else 100.0,
        "minimum": min(scores, default=100.0),
        "directory_minimum": min(directory_scores, default=100.0),
        "data_minimum": min(data_scores, default=100.0),
        "directory_links": float(len(directory_scores)),
        "data_links": float(len(data_scores)),
    }


def build_d64(prg_path: Path, output_path: Path, disk_name: str = "CP64 MODEL") -> None:
    build_d64_files({prg_path.name: prg_path}, output_path, disk_name)


def extract_d64_file(image_path: Path, filename: str) -> bytes:
    """Read one PRG back through its DOS directory and sector chain."""
    image = image_path.read_bytes()
    expected = petscii_name(filename)
    track, sector = DIRECTORY_TRACK, DIRECTORY_SECTOR
    visited_directories: set[tuple[int, int]] = set()
    while track:
        if (track, sector) in visited_directories:
            raise ValueError("looped D64 directory chain")
        visited_directories.add((track, sector))
        directory = sector_offset(track, sector)
        for index in range(8):
            entry = directory + 2 + index * 32
            if image[entry] and image[entry + 3 : entry + 19] == expected:
                blocks = int.from_bytes(image[entry + 28 : entry + 30], "little")
                file_track, file_sector = image[entry + 1], image[entry + 2]
                payload = bytearray()
                for block in range(blocks):
                    if not file_track:
                        raise ValueError("short D64 file chain")
                    offset = sector_offset(file_track, file_sector)
                    next_track, next_sector = image[offset], image[offset + 1]
                    byte_count = 254 if block + 1 < blocks else next_sector - 1
                    payload.extend(image[offset + 2 : offset + 2 + byte_count])
                    file_track, file_sector = next_track, next_sector
                return bytes(payload)
        track, sector = image[directory], image[directory + 1]
    raise FileNotFoundError(filename)


def validate_d64(image_path: Path) -> dict[str, object]:
    """Inspect DOS directory/file chains and report structural D64 invariants."""
    image = image_path.read_bytes()
    if len(image) != 174_848:
        raise ValueError("not a standard 35-track D64 image")
    bam = sector_offset(BAM_TRACK, BAM_SECTOR)
    directory_track = {(DIRECTORY_TRACK, sector) for sector in range(sectors_on_track(DIRECTORY_TRACK))}
    directory_sectors: set[tuple[int, int]] = set()
    file_sectors: dict[tuple[int, int], list[str]] = {}
    file_sectors_on_directory_track: list[tuple[str, tuple[int, int]]] = []
    malformed_entries: list[str] = []
    active_files = 0
    track, sector = DIRECTORY_TRACK, DIRECTORY_SECTOR
    visited_directories: set[tuple[int, int]] = set()
    while track:
        if track != DIRECTORY_TRACK or not 0 <= sector < sectors_on_track(track) or (track, sector) in visited_directories:
            malformed_entries.append("invalid directory chain")
            break
        visited_directories.add((track, sector))
        directory_sectors.add((track, sector))
        directory = sector_offset(track, sector)
        for index in range(8):
            entry = directory + 2 + index * 32
            file_type = image[entry]
            if not file_type:
                continue
            active_files += 1
            name = image[entry + 3 : entry + 19].rstrip(b"\xa0").decode("ascii", "replace")
            blocks = int.from_bytes(image[entry + 28 : entry + 30], "little")
            file_track, file_sector = image[entry + 1], image[entry + 2]
            if not name or blocks == 0 or not file_track:
                malformed_entries.append(name or "(unnamed)")
                continue
            visited_file: set[tuple[int, int]] = set()
            for block in range(blocks):
                if not 1 <= file_track <= 35 or not 0 <= file_sector < sectors_on_track(file_track):
                    malformed_entries.append(name)
                    break
                address = (file_track, file_sector)
                if address in visited_file:
                    malformed_entries.append(name)
                    break
                visited_file.add(address)
                file_sectors.setdefault(address, []).append(name)
                if address in directory_track:
                    file_sectors_on_directory_track.append((name, address))
                offset = sector_offset(*address)
                next_track, next_sector = image[offset], image[offset + 1]
                if block + 1 == blocks:
                    if next_track != 0:
                        malformed_entries.append(name)
                elif not next_track:
                    malformed_entries.append(name)
                    break
                file_track, file_sector = next_track, next_sector
        track, sector = image[directory], image[directory + 1]
    multiply_referenced = sorted(address for address, names in file_sectors.items() if len(names) > 1)
    bam_claimed = {(BAM_TRACK, BAM_SECTOR), *directory_sectors, *file_sectors}
    bam_unclaimed_used: list[tuple[int, int]] = []
    for candidate_track in range(1, 36):
        entry = bam + 4 + (candidate_track - 1) * 4
        bitmap = image[entry + 1] | image[entry + 2] << 8 | image[entry + 3] << 16
        for candidate_sector in range(sectors_on_track(candidate_track)):
            is_free = bool(bitmap & (1 << candidate_sector))
            address = (candidate_track, candidate_sector)
            if not is_free and address not in bam_claimed:
                bam_unclaimed_used.append(address)
    return {
        "active_files": active_files,
        "directory_sectors": sorted(directory_sectors),
        "file_sectors_on_directory_track": file_sectors_on_directory_track,
        "multiply_referenced_file_sectors": multiply_referenced,
        "malformed_entries": malformed_entries,
        "bam_unclaimed_used_sectors": bam_unclaimed_used,
        "header_dos_type": image[bam + 0xA5 : bam + 0xA7],
    }


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
    # A directory sector becomes allocated only when it is actually linked.
    # Spare track-18 sectors remain BAM-free but are excluded from file chains:
    # this is both DOS-correct and avoids Doctor's unreachable-used-sector alarm.
    free.remove((BAM_TRACK, BAM_SECTOR))
    allocated_directory_sectors = directory_sector_order(directory_sectors)
    free -= {(DIRECTORY_TRACK, sector) for sector in allocated_directory_sectors}
    payloads = [(name, path.read_bytes()) for name, path in files.items()]
    if any(len(payload) < 3 for _, payload in payloads):
        raise ValueError("every PRG must contain a two-byte load address and code")
    needed = sum(math.ceil(len(payload) / 254) for _, payload in payloads)
    if needed > len(free):
        raise ValueError("files do not fit on a standard 35-track D64")

    chains: list[tuple[str, list[tuple[int, int]]]] = []
    starts = file_start_order()
    start_cursor = 0
    for name, payload in payloads:
        block_count = math.ceil(len(payload) / 254)
        while starts[start_cursor] not in free:
            start_cursor += 1
        chain = [starts[start_cursor]]
        start_cursor += 1
        free.remove(chain[0])
        while len(chain) < block_count:
            next_address = smart_next_sector(free, chain[-1])
            chain.append(next_address)
            free.remove(next_address)
        for index, (track, sector) in enumerate(chain):
            offset = sector_offset(track, sector)
            chunk = payload[index * 254 : (index + 1) * 254]
            image[offset : offset + 2] = bytes(chain[index + 1]) if index + 1 < len(chain) else bytes((0, len(chunk) + 1))
            image[offset + 2 : offset + 2 + len(chunk)] = chunk
        chains.append((name, chain))

    bam = sector_offset(BAM_TRACK, BAM_SECTOR)
    image[bam : bam + 4] = bytes((DIRECTORY_TRACK, allocated_directory_sectors[0], 0x41, 0))
    for track in range(1, 36):
        bitmap = sum(1 << sector for sector in range(sectors_on_track(track)) if (track, sector) in free)
        entry = bam + 4 + (track - 1) * 4
        image[entry : entry + 4] = bytes((bitmap.bit_count(), bitmap & 0xff, (bitmap >> 8) & 0xff, (bitmap >> 16) & 0xff))
    image[bam + 0x90 : bam + 0xA0] = petscii_name(disk_name)
    image[bam + 0xA2 : bam + 0xA4] = b"00"  # disk ID
    image[bam + 0xA5 : bam + 0xA7] = b"2A"  # standard 1541 DOS type

    for directory_index in range(directory_sectors):
        directory_sector = allocated_directory_sectors[directory_index]
        directory = sector_offset(DIRECTORY_TRACK, directory_sector)
        next_sector = allocated_directory_sectors[directory_index + 1] if directory_index + 1 < directory_sectors else 0xff
        image[directory : directory + 2] = bytes((DIRECTORY_TRACK, next_sector)) if directory_index + 1 < directory_sectors else bytes((0, 0xff))
    for index, (name, chain) in enumerate(chains):
        directory = sector_offset(DIRECTORY_TRACK, allocated_directory_sectors[index // 8])
        entry = directory + 2 + (index % 8) * 32
        image[entry : entry + 3] = bytes((0x82, chain[0][0], chain[0][1]))
        image[entry + 3 : entry + 19] = petscii_name(name)
        image[entry + 28 : entry + 30] = len(chain).to_bytes(2, "little")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(image)
    report = validate_d64(output_path)
    if report["file_sectors_on_directory_track"] or report["multiply_referenced_file_sectors"] or report["malformed_entries"] or report["bam_unclaimed_used_sectors"] or report["header_dos_type"] != b"2A":
        raise ValueError(f"D64 validation failed: {report}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prg", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--disk-name", default="CP64 MODEL")
    args = parser.parse_args()
    build_d64(args.prg, args.output, args.disk_name)
