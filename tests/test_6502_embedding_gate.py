import subprocess
from pathlib import Path

import pytest

py65 = pytest.importorskip("py65")
from py65.devices.mpu6502 import MPU


ROOT = Path(__file__).parents[1]
ASSEMBLER = ROOT / "tools" / "64tass" / "usr" / "bin" / "64tass"


def labels(path: Path) -> dict[str, int]:
    result = {}
    for line in path.read_text().splitlines():
        if "= $" in line:
            name, value = line.split("= $")
            result[name.strip()] = int(value, 16)
    return result


def call(mpu: MPU, address: int) -> None:
    mpu.sp = 0xFF
    mpu.stPushWord(0x01FF)  # RTS returns to $0200.
    mpu.pc = address
    for _ in range(1_000_000):
        mpu.step()
        if mpu.pc == 0x0200:
            return
    raise AssertionError(f"6502 routine did not return; PC=${mpu.pc:04X}")


def test_6502_materializes_original_token_a_embedding(tmp_path):
    prg = tmp_path / "CP64.PRG"
    labels_path = tmp_path / "cp64.lbl"
    subprocess.run(
        [str(ASSEMBLER), "--cbm-prg", f"--labels={labels_path}", "-o", str(prg), str(ROOT / "src" / "cp64.asm")],
        check=True,
        capture_output=True,
        text=True,
    )
    symbols = labels(labels_path)
    mpu = MPU()
    image = prg.read_bytes()
    load_address = int.from_bytes(image[:2], "little")
    mpu.memory[load_address : load_address + len(image) - 2] = image[2:]
    packet = (ROOT / "build" / "layers" / "C9W00.PRG").read_bytes()[2:]
    mpu.memory[0xC000 : 0xC000 + len(packet)] = packet
    mpu.memory[symbols["row"]] = 4  # Crystal-9 token a.

    call(mpu, symbols["decode_scale"])
    call(mpu, symbols["materialize_embedding"])

    vector = []
    for index in range(32):
        low = mpu.memory[symbols["VECTOR"] + index * 2]
        high = mpu.memory[symbols["VECTOR"] + index * 2 + 1]
        value = low | (high << 8)
        vector.append(value - 0x10000 if value & 0x8000 else value)
    assert vector == [
        71, -71, -285, -71, 71, 0, 71, 428,
        0, 0, -71, -499, 71, -214, 0, -285,
        -143, -71, -285, 71, 0, -71, 428, -71,
        143, 0, -71, 0, -214, 214, 285, 285,
    ]
    assert mpu.memory[symbols["sumlo"]] | (mpu.memory[symbols["sumhi"]] << 8) == 0x20AD
