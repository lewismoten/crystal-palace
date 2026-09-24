#!/usr/bin/env python3
"""Assemble the CP64 pager and package it with its original Crystal-9 layers."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from make_d64 import build_d64_files

ROOT = Path(__file__).parents[1]
BUILD = ROOT / "build"
CURRENT_STAGE = 26
CURRENT_DESCRIPTION = "attention-output-projection"


def stage_image_path(number: int, description: str) -> Path:
    """Return the archived D64 name for a numbered CP64 proof gate."""
    if number < 1 or not description or "/" in description:
        raise ValueError("stage requires a positive number and filename-safe description")
    return BUILD / f"cs64-{number:03d}-{description}.d64"


def main() -> None:
    assembler = ROOT / "tools" / "64tass" / "usr" / "bin" / "64tass"
    if not assembler.is_file():
        raise SystemExit("64tass is missing; run scripts/bootstrap_64tass.sh first")
    subprocess.run([str(assembler), "--cbm-prg", "-o", str(BUILD / "CP64.PRG"), str(ROOT / "src" / "cp64.asm")], check=True)
    files = {"CP64.PRG": BUILD / "CP64.PRG"}
    files.update({path.name: path for path in sorted((BUILD / "layers").glob("C9W*.PRG"))})
    if len(files) != 49:
        raise SystemExit(f"expected CP64 plus 48 original tensor files, found {len(files)}")
    stage_image = stage_image_path(CURRENT_STAGE, CURRENT_DESCRIPTION)
    build_d64_files(files, stage_image, disk_name="CP64 CRYSTAL9")
    shutil.copyfile(stage_image, BUILD / "cp64.d64")
    print(stage_image)


if __name__ == "__main__":
    main()
