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


def call(mpu: MPU, address: int, steps: int = 1_000_000) -> None:
    mpu.sp = 0xFF
    mpu.stPushWord(0x01FF)  # RTS returns to $0200.
    mpu.pc = address
    for _ in range(steps):
        mpu.step()
        if mpu.pc == 0x0200:
            return
    raise AssertionError(f"6502 routine did not return; PC=${mpu.pc:04X}")


def q8_8_vector_from_original_packet(packet_path: Path, row: int) -> list[int]:
    """Independent fixed-point reference over verbatim C9W scale and INT4 bytes."""
    packet = packet_path.read_bytes()[2:]
    scale_bytes = int.from_bytes(packet[5:7], "little")
    raw_scale = int.from_bytes(packet[9 + row * 2 : 11 + row * 2], "little")
    exponent = (raw_scale >> 10) & 0x1F
    fraction = raw_scale & 0x03FF
    mantissa = fraction if exponent == 0 else 1024 + fraction
    shift = exponent - 17 if exponent else -16
    scale = mantissa << shift if shift >= 0 else (mantissa + (1 << -shift) // 2) // (1 << -shift)
    packed = packet[9 + scale_bytes + row * 16 : 9 + scale_bytes + (row + 1) * 16]
    codes = [nibble - 16 if nibble >= 8 else nibble for byte in packed for nibble in (byte & 0x0F, byte >> 4)]
    return [(code * scale + 3) // 7 if code >= 0 else -((-code * scale + 3) // 7) for code in codes]


def signed_vector(mpu: MPU, address: int) -> list[int]:
    values = []
    for index in range(32):
        value = mpu.memory[address + index * 2] | (mpu.memory[address + index * 2 + 1] << 8)
        values.append(value - 0x10000 if value & 0x8000 else value)
    return values


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


@pytest.mark.parametrize(
    ("token_row", "expected_checksum"),
    [(4, 0x20AD), (5, 0xD419), (6, 0xCCBC), (7, 0xA0DE), (8, 0x889C),
     (9, 0xF8A2), (10, 0x4119), (11, 0x479C), (12, 0x3C6C)],
)
def test_6502_embedding_checksum_matches_reference_for_every_token(tmp_path, token_row, expected_checksum):
    prg = tmp_path / "CP64.PRG"
    labels_path = tmp_path / "cp64.lbl"
    subprocess.run(
        [str(ASSEMBLER), "--cbm-prg", f"--labels={labels_path}", "-o", str(prg), str(ROOT / "src" / "cp64.asm")],
        check=True, capture_output=True, text=True,
    )
    symbols = labels(labels_path)
    mpu = MPU()
    image = prg.read_bytes()
    load_address = int.from_bytes(image[:2], "little")
    mpu.memory[load_address : load_address + len(image) - 2] = image[2:]
    packet = (ROOT / "build" / "layers" / "C9W00.PRG").read_bytes()[2:]
    mpu.memory[0xC000 : 0xC000 + len(packet)] = packet
    mpu.memory[symbols["row"]] = token_row

    call(mpu, symbols["decode_scale"])
    call(mpu, symbols["materialize_embedding"])

    checksum = mpu.memory[symbols["sumlo"]] | (mpu.memory[symbols["sumhi"]] << 8)
    assert checksum == expected_checksum


@pytest.mark.parametrize(
    ("position_row", "expected_checksum"),
    [(0, 0x20E2), (1, 0x1913), (2, 0x1CA9), (3, 0x061A), (4, 0x2F56),
     (5, 0x2937), (6, 0xFDC0), (7, 0x18BA), (8, 0x14EB)],
)
def test_6502_materializes_original_position_embedding(tmp_path, position_row, expected_checksum):
    prg = tmp_path / "CP64.PRG"
    labels_path = tmp_path / "cp64.lbl"
    subprocess.run(
        [str(ASSEMBLER), "--cbm-prg", f"--labels={labels_path}", "-o", str(prg), str(ROOT / "src" / "cp64.asm")],
        check=True, capture_output=True, text=True,
    )
    symbols = labels(labels_path)
    mpu = MPU()
    image = prg.read_bytes()
    load_address = int.from_bytes(image[:2], "little")
    mpu.memory[load_address : load_address + len(image) - 2] = image[2:]
    packet = (ROOT / "build" / "layers" / "C9W01.PRG").read_bytes()[2:]
    mpu.memory[0xC000 : 0xC000 + len(packet)] = packet
    mpu.memory[symbols["position_row"]] = position_row

    call(mpu, symbols["decode_position_scale"])
    call(mpu, symbols["materialize_position"])

    assert signed_vector(mpu, symbols["POSITION_VECTOR"]) == q8_8_vector_from_original_packet(
        ROOT / "build" / "layers" / "C9W01.PRG", position_row
    )
    checksum = mpu.memory[symbols["position_sumlo"]] | (mpu.memory[symbols["position_sumhi"]] << 8)
    assert checksum == expected_checksum


@pytest.mark.parametrize("position_row", range(9))
def test_6502_adds_original_position_to_retained_token_vector(tmp_path, position_row):
    prg = tmp_path / "CP64.PRG"
    labels_path = tmp_path / "cp64.lbl"
    subprocess.run(
        [str(ASSEMBLER), "--cbm-prg", f"--labels={labels_path}", "-o", str(prg), str(ROOT / "src" / "cp64.asm")],
        check=True, capture_output=True, text=True,
    )
    symbols = labels(labels_path)
    mpu = MPU()
    image = prg.read_bytes()
    load_address = int.from_bytes(image[:2], "little")
    mpu.memory[load_address : load_address + len(image) - 2] = image[2:]
    token_packet = (ROOT / "build" / "layers" / "C9W00.PRG").read_bytes()[2:]
    mpu.memory[0xC000 : 0xC000 + len(token_packet)] = token_packet
    mpu.memory[symbols["row"]] = 4 + position_row
    call(mpu, symbols["decode_scale"])
    call(mpu, symbols["materialize_embedding"])
    position_packet = (ROOT / "build" / "layers" / "C9W01.PRG").read_bytes()[2:]
    mpu.memory[0xC000 : 0xC000 + len(position_packet)] = position_packet
    mpu.memory[symbols["position_row"]] = position_row

    call(mpu, symbols["decode_position_scale"])
    call(mpu, symbols["materialize_position"])
    call(mpu, symbols["add_position_to_vector"])

    expected_token = q8_8_vector_from_original_packet(ROOT / "build" / "layers" / "C9W00.PRG", 4 + position_row)
    expected_position = q8_8_vector_from_original_packet(ROOT / "build" / "layers" / "C9W01.PRG", position_row)
    expected = [token + position for token, position in zip(expected_token, expected_position)]
    assert signed_vector(mpu, symbols["VECTOR"]) == expected
    assert mpu.memory[symbols["sumlo"]] | (mpu.memory[symbols["sumhi"]] << 8) == sum(
        (index + 1) * value for index, value in enumerate(expected)
    ) & 0xFFFF


def q8_8_attention_row_from_original_packet(packet_path: Path, row: int) -> list[int]:
    """Independently decode one original INT4 attention-matrix row to Q8.8."""
    return q8_8_vector_from_original_packet(packet_path, row)


def q8_8_dot(left: list[int], right: list[int]) -> int:
    """Symmetrically round a Q16.16 dot product back to Q8.8."""
    total = sum(a * b for a, b in zip(left, right))
    return (total + 128) // 256 if total >= 0 else -((-total + 128) // 256)


@pytest.mark.parametrize("position_row", range(9))
def test_6502_projects_original_attention_query_for_every_playable_input(tmp_path, position_row):
    prg = tmp_path / "CP64.PRG"
    labels_path = tmp_path / "cp64.lbl"
    subprocess.run(
        [str(ASSEMBLER), "--cbm-prg", f"--labels={labels_path}", "-o", str(prg), str(ROOT / "src" / "cp64.asm")],
        check=True, capture_output=True, text=True,
    )
    symbols = labels(labels_path)
    assert "project_query" in symbols
    mpu = MPU()
    image = prg.read_bytes()
    load_address = int.from_bytes(image[:2], "little")
    mpu.memory[load_address : load_address + len(image) - 2] = image[2:]
    token_packet = ROOT / "build" / "layers" / "C9W00.PRG"
    position_packet = ROOT / "build" / "layers" / "C9W01.PRG"
    attention_packet = ROOT / "build" / "layers" / "C9W02.PRG"
    mpu.memory[0xC000 : 0xC000 + len(token_packet.read_bytes()) - 2] = token_packet.read_bytes()[2:]
    mpu.memory[symbols["row"]] = 4 + position_row
    call(mpu, symbols["decode_scale"])
    call(mpu, symbols["materialize_embedding"])
    mpu.memory[0xC000 : 0xC000 + len(position_packet.read_bytes()) - 2] = position_packet.read_bytes()[2:]
    mpu.memory[symbols["position_row"]] = position_row
    call(mpu, symbols["decode_position_scale"])
    call(mpu, symbols["materialize_position"])
    call(mpu, symbols["add_position_to_vector"])
    call(mpu, symbols["retain_hidden_vector"])
    mpu.memory[0xC000 : 0xC000 + len(attention_packet.read_bytes()) - 2] = attention_packet.read_bytes()[2:]

    call(mpu, symbols["project_query"], steps=20_000_000)

    hidden = q8_8_vector_from_original_packet(token_packet, 4 + position_row)
    position = q8_8_vector_from_original_packet(position_packet, position_row)
    expected = [q8_8_dot([a + b for a, b in zip(hidden, position)], q8_8_attention_row_from_original_packet(attention_packet, row)) for row in range(32)]
    assert signed_vector(mpu, symbols["QUERY_VECTOR"]) == expected


@pytest.mark.parametrize("position_row", range(9))
def test_6502_records_original_attention_query_checksum_for_every_playable_input(tmp_path, position_row):
    prg = tmp_path / "CP64.PRG"
    labels_path = tmp_path / "cp64.lbl"
    subprocess.run(
        [str(ASSEMBLER), "--cbm-prg", f"--labels={labels_path}", "-o", str(prg), str(ROOT / "src" / "cp64.asm")],
        check=True, capture_output=True, text=True,
    )
    symbols = labels(labels_path)
    assert "query_sumlo" in symbols
    assert "query_sumhi" in symbols
    mpu = MPU()
    image = prg.read_bytes()
    load_address = int.from_bytes(image[:2], "little")
    mpu.memory[load_address : load_address + len(image) - 2] = image[2:]
    token_packet = ROOT / "build" / "layers" / "C9W00.PRG"
    position_packet = ROOT / "build" / "layers" / "C9W01.PRG"
    attention_packet = ROOT / "build" / "layers" / "C9W02.PRG"
    mpu.memory[0xC000 : 0xC000 + len(token_packet.read_bytes()) - 2] = token_packet.read_bytes()[2:]
    mpu.memory[symbols["row"]] = 4 + position_row
    call(mpu, symbols["decode_scale"])
    call(mpu, symbols["materialize_embedding"])
    mpu.memory[0xC000 : 0xC000 + len(position_packet.read_bytes()) - 2] = position_packet.read_bytes()[2:]
    mpu.memory[symbols["position_row"]] = position_row
    call(mpu, symbols["decode_position_scale"])
    call(mpu, symbols["materialize_position"])
    call(mpu, symbols["add_position_to_vector"])
    call(mpu, symbols["retain_hidden_vector"])
    mpu.memory[0xC000 : 0xC000 + len(attention_packet.read_bytes()) - 2] = attention_packet.read_bytes()[2:]

    call(mpu, symbols["project_query"], steps=20_000_000)

    hidden = q8_8_vector_from_original_packet(token_packet, 4 + position_row)
    position = q8_8_vector_from_original_packet(position_packet, position_row)
    expected = [q8_8_dot([a + b for a, b in zip(hidden, position)], q8_8_attention_row_from_original_packet(attention_packet, row)) for row in range(32)]
    expected_checksum = sum((index + 1) * value for index, value in enumerate(expected)) & 0xFFFF
    actual_checksum = mpu.memory[symbols["query_sumlo"]] | (mpu.memory[symbols["query_sumhi"]] << 8)
    assert actual_checksum == expected_checksum
