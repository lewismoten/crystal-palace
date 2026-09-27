#!/usr/bin/env python3
"""Assemble the CP64 pager and package it with its original Crystal-9 layers."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from make_d64 import build_d64_files

ROOT = Path(__file__).parents[1]
BUILD = ROOT / "build"
CURRENT_STAGE = 57
CURRENT_DESCRIPTION = "masked-legal-model-argmax"
ART = ROOT / "assets" / "crystal-palace-screen-states"

# These are immutable source planes wrapped only in standard two-byte PRG load
# addresses. They are staging buffers, never C9W packet/data-window addresses.
CRYSTAL_PALACE_ART = {
    "CPCHAR.PRG": ("crystal-palace-charset.bin", 0x3800),
    "CPT0S.PRG": ("crystal-palace-title-player-0.screen.bin", 0x5000),
    "CPT0C.PRG": ("crystal-palace-title-player-0.color.bin", 0x5400),
    "CPT1S.PRG": ("crystal-palace-title-player-1.screen.bin", 0x5000),
    "CPT1C.PRG": ("crystal-palace-title-player-1.color.bin", 0x5400),
    "CPT2S.PRG": ("crystal-palace-title-player-2.screen.bin", 0x5000),
    "CPT2C.PRG": ("crystal-palace-title-player-2.color.bin", 0x5400),
    "CPINS.PRG": ("crystal-palace-info.screen.bin", 0x5000),
    "CPINC.PRG": ("crystal-palace-info.color.bin", 0x5400),
    "CPGBM.PRG": ("crystal-palace-game-blank.bitmap.bin", 0x6000),
    "CPGSC.PRG": ("crystal-palace-game-blank.screen.bin", 0x5000),
    "CPGCO.PRG": ("crystal-palace-game-blank.color.bin", 0x5400),
    "CPGXB.PRG": ("crystal-palace-game-all-x.bitmap.bin", 0x6000),
    "CPGXS.PRG": ("crystal-palace-game-all-x.screen.bin", 0x5000),
    "CPGXC.PRG": ("crystal-palace-game-all-x.color.bin", 0x5400),
    "CPGOB.PRG": ("crystal-palace-game-all-o.bitmap.bin", 0x6000),
    "CPGOS.PRG": ("crystal-palace-game-all-o.screen.bin", 0x5000),
    "CPGOC.PRG": ("crystal-palace-game-all-o.color.bin", 0x5400),
}


def stage_image_path(number: int, description: str) -> Path:
    """Return the archived D64 name for a numbered CP64 proof gate."""
    if number < 1 or not description or "/" in description:
        raise ValueError("stage requires a positive number and filename-safe description")
    return BUILD / f"cs64-{number:03d}-{description}.d64"


def crystal_palace_art_prgs(destination: Path) -> dict[str, Path]:
    """Create reproducible PRG wrappers around verbatim supplied UI planes."""
    destination.mkdir(parents=True, exist_ok=True)
    result = {}
    for disk_name, (asset_name, load_address) in CRYSTAL_PALACE_ART.items():
        payload = (ART / asset_name).read_bytes()
        path = destination / disk_name
        path.write_bytes(load_address.to_bytes(2, "little") + payload)
        result[disk_name] = path
    return result


def main() -> None:
    assembler = ROOT / "tools" / "64tass" / "usr" / "bin" / "64tass"
    if not assembler.is_file():
        raise SystemExit("64tass is missing; run scripts/bootstrap_64tass.sh first")
    subprocess.run([str(assembler), "--cbm-prg", "-o", str(BUILD / "CP64.PRG"), str(ROOT / "src" / "cp64.asm")], check=True)
    files = {"CP64.PRG": BUILD / "CP64.PRG"}
    files.update({path.name: path for path in sorted((BUILD / "layers").glob("C9W*.PRG"))})
    if len(files) != 49:
        raise SystemExit(f"expected CP64 plus 48 original tensor files, found {len(files)}")
    files.update(crystal_palace_art_prgs(BUILD / "art-prgs"))
    stage_image = stage_image_path(CURRENT_STAGE, CURRENT_DESCRIPTION)
    build_d64_files(files, stage_image, disk_name="CP64 CRYSTAL9")
    shutil.copyfile(stage_image, BUILD / "cp64.d64")
    print(stage_image)


if __name__ == "__main__":
    main()
