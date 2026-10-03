#!/usr/bin/env python3
"""Assemble the CP64 pager and package it with its original Crystal-9 layers."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from make_d64 import build_d64_files

ROOT = Path(__file__).parents[1]
BUILD = ROOT / "build"
CURRENT_STAGE = 81
CURRENT_DESCRIPTION = "archive-and-title-composition"
PROGRAM_SOURCE = ROOT / "src" / "art_embedded_title.asm"
ART = ROOT / "assets" / "crystal-palace-screen-states"

# Descriptive 1541 directory names. The local source-packet names remain
# C9Wxx so the immutable transport ID and host-side parity fixtures stay
# obvious; only the user-facing disk entry changes.
DISK_TENSOR_FILENAMES = {
    "C9W00.PRG": "EMBEDTOK.PRG", "C9W01.PRG": "POSITN9.PRG",
    "C9W02.PRG": "ATTNQKVW.PRG", "C9W03.PRG": "ATTNQKVB.PRG",
    "C9W04.PRG": "ATTNOUTW.PRG", "C9W05.PRG": "ATTNOUTB.PRG",
    "C9W06.PRG": "NORMGAM.PRG", "C9W07.PRG": "NORMBET.PRG",
    "C9W08.PRG": "ROUTERW.PRG", "C9W09.PRG": "ROUTERB.PRG",
    "C9W46.PRG": "OUTHEADW.PRG", "C9W47.PRG": "OUTHEADB.PRG",
}
for expert in range(9):
    base = 10 + 4 * expert
    DISK_TENSOR_FILENAMES.update({
        f"C9W{base:02d}.PRG": f"EX{expert}L1W.PRG",
        f"C9W{base + 1:02d}.PRG": f"EX{expert}L1B.PRG",
        f"C9W{base + 2:02d}.PRG": f"EX{expert}L2W.PRG",
        f"C9W{base + 3:02d}.PRG": f"EX{expert}L2B.PRG",
    })

# These are immutable source planes wrapped only in standard two-byte PRG load
# addresses. They are staging buffers, never C9W packet/data-window addresses.
CRYSTAL_PALACE_ART = {"CPCHAR.PRG": ("crystal-palace-charset.bin", 0x3800)}
for variant in range(3):
    prefix = f"crystal-palace-title-player-{variant}"
    for plane, base, letter in (("screen", 0x0400, "S"), ("color", 0xD800, "C")):
        for page, offset in enumerate((0, 256, 512, 768)):
            CRYSTAL_PALACE_ART[f"CT{variant}{letter}{page}.PRG"] = (f"{prefix}.{plane}.bin", base + offset, offset, 1000 - offset if page == 3 else 256)
for plane, base, letter in (("screen", 0x0400, "S"), ("color", 0xD800, "C")):
    for page, offset in enumerate((0, 256, 512, 768)):
        CRYSTAL_PALACE_ART[f"CI{letter}{page}.PRG"] = (f"crystal-palace-info.{plane}.bin", base + offset, offset, 1000 - offset if page == 3 else 256)
for page in range(8):
    CRYSTAL_PALACE_ART[f"CGB{page}.PRG"] = ("crystal-palace-game-blank.bitmap.bin", 0x6000 + page * 1000, page * 1000, 1000)
for plane, base, letter in (("screen", 0x4000, "S"), ("color", 0xD800, "C")):
    for page, offset in enumerate((0, 256, 512, 768)):
        CRYSTAL_PALACE_ART[f"CG{letter}{page}.PRG"] = (f"crystal-palace-game-blank.{plane}.bin", base + offset, offset, 1000 - offset if page == 3 else 256)


def stage_image_path(number: int, description: str) -> Path:
    """Return the archived D64 name for a numbered CP64 proof gate."""
    if number < 1 or not description or "/" in description:
        raise ValueError("stage requires a positive number and filename-safe description")
    return BUILD / f"cs64-{number:03d}-{description}.d64"


def crystal_palace_art_prgs(destination: Path) -> dict[str, Path]:
    """Create reproducible PRG wrappers around verbatim supplied UI planes."""
    destination.mkdir(parents=True, exist_ok=True)
    result = {}
    for disk_name, spec in CRYSTAL_PALACE_ART.items():
        asset_name, load_address, *slice_spec = spec
        payload = (ART / asset_name).read_bytes()
        if slice_spec:
            offset, length = slice_spec
            payload = payload[offset : offset + length]
        path = destination / disk_name
        path.write_bytes(load_address.to_bytes(2, "little") + payload)
        result[disk_name] = path
    return result


def main() -> None:
    assembler = ROOT / "tools" / "64tass" / "usr" / "bin" / "64tass"
    if not assembler.is_file():
        raise SystemExit("64tass is missing; run scripts/bootstrap_64tass.sh first")
    subprocess.run([sys.executable, str(ROOT / "scripts" / "derive_cell_patches.py")], check=True)
    subprocess.run([sys.executable, str(ROOT / "scripts" / "compile_info_markdown.py")], check=True)
    subprocess.run([str(assembler), "--cbm-prg", "-o", str(BUILD / "CP64.PRG"), str(PROGRAM_SOURCE)], check=True)
    files = {"CP64.PRG": BUILD / "CP64.PRG"}
    packets = {path.name: path for path in sorted((BUILD / "layers").glob("C9W*.PRG"))}
    if set(packets) != set(DISK_TENSOR_FILENAMES):
        raise SystemExit("descriptive disk-name map does not cover exactly the 48 original tensor packets")
    files.update({DISK_TENSOR_FILENAMES[source_name]: path for source_name, path in packets.items()})
    if len(files) != 49:
        raise SystemExit(f"expected CP64 plus 48 original tensor files, found {len(files)}")
    # The current executable embeds the immutable title/info/game planes.
    # Keep raw asset wrappers reproducible via crystal_palace_art_prgs(), but
    # do not inflate the release disk with 49 unused staging PRGs.
    stage_image = stage_image_path(CURRENT_STAGE, CURRENT_DESCRIPTION)
    build_d64_files(files, stage_image, disk_name="CP64 CRYSTAL9")
    shutil.copyfile(stage_image, BUILD / "cp64.d64")
    print(stage_image)


if __name__ == "__main__":
    main()
