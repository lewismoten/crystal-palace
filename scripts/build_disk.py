#!/usr/bin/env python3
"""Assemble the CP64 pager and package it with its original Crystal-9 layers."""
from __future__ import annotations

import subprocess
from pathlib import Path

from make_d64 import build_d64_files

ROOT = Path(__file__).parents[1]
BUILD = ROOT / "build"


def main() -> None:
    assembler = ROOT / "tools" / "64tass" / "usr" / "bin" / "64tass"
    if not assembler.is_file():
        raise SystemExit("64tass is missing; run scripts/bootstrap_64tass.sh first")
    subprocess.run([str(assembler), "--cbm-prg", "-o", str(BUILD / "CP64.PRG"), str(ROOT / "src" / "cp64.asm")], check=True)
    files = {"CP64.PRG": BUILD / "CP64.PRG"}
    files.update({path.name: path for path in sorted((BUILD / "layers").glob("C9W*.PRG"))})
    if len(files) != 49:
        raise SystemExit(f"expected CP64 plus 48 original tensor files, found {len(files)}")
    build_d64_files(files, BUILD / "cp64.d64", disk_name="CP64 CRYSTAL9")
    print(BUILD / "cp64.d64")


if __name__ == "__main__":
    main()
