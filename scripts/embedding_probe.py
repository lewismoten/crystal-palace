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


def fp16le_to_q8_8(raw: bytes) -> int:
    """Decode a finite IEEE-754 binary16 value to signed Q8.8 with rounding."""
    if len(raw) != 2:
        raise ValueError("binary16 requires exactly two bytes")
    bits = int.from_bytes(raw, "little")
    sign = -1 if bits & 0x8000 else 1
    exponent = (bits >> 10) & 0x1F
    fraction = bits & 0x03FF
    if exponent == 0x1F:
        raise ValueError("infinite and NaN scales are invalid")
    mantissa = fraction if exponent == 0 else 1024 + fraction
    shift = exponent - 17 if exponent else -16
    if shift >= 0:
        magnitude = mantissa << shift
    else:
        divisor = 1 << -shift
        magnitude = (mantissa + divisor // 2) // divisor
    return sign * magnitude


def scale_int4_code_q8_8(code: int, scale_q8_8: int) -> int:
    """Materialize code * scale / 7 using symmetric nearest-integer rounding."""
    if not -8 <= code <= 7:
        raise ValueError("INT4 code is outside [-8, 7]")
    product = code * scale_q8_8
    return (product + 3) // 7 if product >= 0 else -((-product + 3) // 7)


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
