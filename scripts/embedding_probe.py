#!/usr/bin/env python3
"""Reference probe for CP64's first real packed-neural operation."""
from __future__ import annotations

from pathlib import Path


def unpack_int4(packed: bytes) -> list[int]:
    values = []
    for byte in packed:
        for code in (byte & 0x0F, byte >> 4):
            values.append(code - 16 if code >= 8 else code)
    return values


def weighted_checksum(values: list[int]) -> int:
    return sum((index + 1) * value for index, value in enumerate(values))


def embedding_row(path: Path, token: str) -> list[int]:
    if len(token) != 1 or token not in "abcdefghi":
        raise ValueError("token must be a-i")
    prg = path.read_bytes()
    packet = prg[2:]
    if packet[:4] != b"C9W1" or packet[4] != 0:
        raise ValueError("expected original Crystal-9 embedding packet C9W00")
    scale_size = int.from_bytes(packet[5:7], "little")
    packed_size = int.from_bytes(packet[7:9], "little")
    packed = packet[9 + scale_size : 9 + scale_size + packed_size]
    row = ord(token) - ord("a") + 4
    return unpack_int4(packed[row * 16 : (row + 1) * 16])


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("token", choices="abcdefghi")
    parser.add_argument("--packet", type=Path, default=Path("build/layers/C9W00.PRG"))
    args = parser.parse_args()
    values = embedding_row(args.packet, args.token)
    print(f"{args.token}: checksum=${weighted_checksum(values) & 0xffff:04X} codes={values}")
