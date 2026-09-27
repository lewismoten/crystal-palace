import json
import subprocess
from math import exp
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


def q8_8_group2_vector_from_original_packet(packet_path: Path) -> list[int]:
    """Independent C9W06 group-of-two FP16/INT4 decode reference."""
    packet = packet_path.read_bytes()[2:]
    scale_bytes = int.from_bytes(packet[5:7], "little")
    packed = packet[9 + scale_bytes :]
    values = []
    for group, byte in enumerate(packed):
        raw = int.from_bytes(packet[9 + group * 2 : 11 + group * 2], "little")
        exponent, fraction = (raw >> 10) & 0x1F, raw & 0x03FF
        mantissa = fraction if exponent == 0 else 1024 + fraction
        shift = exponent - 17 if exponent else -16
        scale = mantissa << shift if shift >= 0 else (mantissa + (1 << -shift) // 2) // (1 << -shift)
        for nibble in (byte & 0x0F, byte >> 4):
            code = nibble - 16 if nibble >= 8 else nibble
            values.append((code * scale + 3) // 7 if code >= 0 else -((-code * scale + 3) // 7))
    return values


def signed_vector(mpu: MPU, address: int) -> list[int]:
    values = []
    for index in range(32):
        value = mpu.memory[address + index * 2] | (mpu.memory[address + index * 2 + 1] << 8)
        values.append(value - 0x10000 if value & 0x8000 else value)
    return values


def test_6502_materializes_original_group2_norm_weight(tmp_path):
    prg = tmp_path / "CP64.PRG"
    labels_path = tmp_path / "cp64.lbl"
    subprocess.run([str(ASSEMBLER), "--cbm-prg", f"--labels={labels_path}", "-o", str(prg), str(ROOT / "src" / "cp64.asm")], check=True, capture_output=True, text=True)
    symbols = labels(labels_path)
    mpu = MPU()
    image = prg.read_bytes(); load_address = int.from_bytes(image[:2], "little")
    mpu.memory[load_address : load_address + len(image) - 2] = image[2:]
    packet = ROOT / "build" / "layers" / "C9W06.PRG"; payload = packet.read_bytes()
    mpu.memory[0xC000 : 0xC000 + len(payload) - 2] = payload[2:]
    call(mpu, symbols["materialize_norm_weight"])
    expected = q8_8_group2_vector_from_original_packet(packet)
    assert signed_vector(mpu, symbols["PROJECTION_SCRATCH"]) == expected
    checksum = sum((index + 1) * value for index, value in enumerate(expected)) & 0xFFFF
    assert mpu.memory[symbols["norm_sumlo"]] | (mpu.memory[symbols["norm_sumhi"]] << 8) == checksum == 0xE4D4


def test_6502_materializes_original_norm_bias(tmp_path):
    prg = tmp_path / "CP64.PRG"; labels_path = tmp_path / "cp64.lbl"
    subprocess.run([str(ASSEMBLER), "--cbm-prg", f"--labels={labels_path}", "-o", str(prg), str(ROOT / "src" / "cp64.asm")], check=True, capture_output=True, text=True)
    symbols = labels(labels_path); mpu = MPU(); image = prg.read_bytes(); load_address = int.from_bytes(image[:2], "little")
    mpu.memory[load_address : load_address + len(image) - 2] = image[2:]
    packet = ROOT / "build" / "layers" / "C9W07.PRG"; payload = packet.read_bytes(); mpu.memory[0xC000 : 0xC000 + len(payload) - 2] = payload[2:]
    call(mpu, symbols["materialize_norm_bias"])
    expected = q8_8_vector_from_original_packet(packet, 0)
    assert signed_vector(mpu, symbols["POSITION_VECTOR"]) == expected
    checksum = sum((index + 1) * value for index, value in enumerate(expected)) & 0xFFFF
    assert mpu.memory[symbols["norm_bias_sumlo"]] | (mpu.memory[symbols["norm_bias_sumhi"]] << 8) == checksum == 0x051C


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


def test_interactive_request_reloads_token_packet_before_decoding_selected_row():
    """C9W01 overwrites $C000, so every next key request needs C9W00 again."""
    source = (ROOT / "src" / "cp64.asm").read_text()
    request = source[source.index("accepted_key:") : source.index("scale_ready:")]
    assert request.index("jsr load_embedding") < request.index("jsr decode_scale")


def test_interactive_request_restores_selected_token_after_disk_load():
    """KERNAL LOAD owns A, so the row calculation must reload the saved token."""
    source = (ROOT / "src" / "cp64.asm").read_text()
    resume = source[source.index("embedding_reloaded:") : source.index("scale_ready:")]
    assert resume.index("lda selected") < resume.index("sbc #'a'")


def test_interactive_request_announces_input_and_each_long_work_stage():
    source = (ROOT / "src" / "cp64.asm").read_text()
    request = source[source.index("accepted_key:") : source.index("jmp read_key", source.index("accepted_key:"))]

    assert request.index("jsr ui_status_thinking") < request.index("jsr load_embedding")
    for step in ("step_token", "step_position", "step_query", "step_key", "step_value", "step_history", "step_scores", "step_two_key_scores", "step_head0", "step_head1", "step_head2", "step_head3", "step_head4", "step_head5", "step_head6", "step_head7", "step_residual_retain", "step_output_load", "step_output_project", "step_output_bias_load", "step_output_bias", "step_residual_add", "step_norm_load", "step_norm_materialize", "step_norm_bias_load", "step_norm_bias_materialize"):
        assert step in source
    assert request.index("jsr ui_step_history") < request.index("jsr capture_legal_history")
    assert request.index("jsr ui_step_scores") < request.index("jsr materialize_self_attention_scores")
    assert source.index("#<step_two_key_scores") < source.index("jsr materialize_two_token_causal_scores")
    for step in ("step_head0", "step_head1", "step_head2", "step_head3", "step_head4", "step_head5", "step_head6", "step_head7"):
        assert source.find("jsr two_key_selected_head_softmax_attention_output", source.index(f"#<{step}")) != -1
    assert source.index("#<step_residual_retain") < source.index("jsr retain_attention_residual") < source.index("jsr project_attention_output")
    assert source.index("#<step_residual_add") < source.index("jsr add_attention_residual")
    assert source.index("#<step_norm_load") < source.index("jsr load_norm_weight")
    assert source.index("#<step_norm_materialize") < source.index("jsr materialize_norm_weight")
    assert source.index("#<step_norm_bias_load") < source.index("jsr load_norm_bias")
    assert source.index("#<step_norm_bias_materialize") < source.index("jsr materialize_norm_bias")


def test_final_display_uses_input_dependent_attention_query_checksum():
    source = (ROOT / "src" / "cp64.asm").read_text()
    display = source[source.index("lda #<result") : source.index("jmp read_key", source.index("lda #<result"))]
    assert "lda query_sumhi" in display
    assert "lda query_sumlo" in display


def test_final_display_reports_layer_norm_centering_checksum():
    source = (ROOT / "src" / "cp64.asm").read_text()
    display = source[source.index("lda #<norm_bias_checksum") : source.index("jmp read_key", source.index("lda #<norm_bias_checksum"))]

    assert "lda #<norm_center_checksum" in display
    assert "lda norm_center_sumhi" in display
    assert "lda norm_center_sumlo" in display


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
    assert not (mpu.p & mpu.CARRY), f"token row {token_row} decoder returned unsupported scale"
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


def q8_8_attention_score(query: list[int], key: list[int]) -> int:
    """Round one four-wide Q8.8 head score after the original /sqrt(4) scale."""
    total = sum(a * b for a, b in zip(query, key))
    return (total + 256) // 512 if total >= 0 else -((-total + 256) // 512)


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


@pytest.mark.parametrize("position_row", range(9))
def test_6502_projects_original_attention_key_for_every_playable_input(tmp_path, position_row):
    prg = tmp_path / "CP64.PRG"
    labels_path = tmp_path / "cp64.lbl"
    subprocess.run(
        [str(ASSEMBLER), "--cbm-prg", f"--labels={labels_path}", "-o", str(prg), str(ROOT / "src" / "cp64.asm")],
        check=True, capture_output=True, text=True,
    )
    symbols = labels(labels_path)
    assert "project_key" in symbols
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

    call(mpu, symbols["project_key"], steps=20_000_000)

    hidden = q8_8_vector_from_original_packet(token_packet, 4 + position_row)
    position = q8_8_vector_from_original_packet(position_packet, position_row)
    expected = [
        q8_8_dot([a + b for a, b in zip(hidden, position)], q8_8_attention_row_from_original_packet(attention_packet, 32 + row))
        for row in range(32)
    ]
    assert signed_vector(mpu, symbols["KEY_VECTOR"]) == expected


@pytest.mark.parametrize("position_row", range(9))
def test_6502_projects_original_attention_value_for_every_playable_input(tmp_path, position_row):
    prg = tmp_path / "CP64.PRG"
    labels_path = tmp_path / "cp64.lbl"
    subprocess.run(
        [str(ASSEMBLER), "--cbm-prg", f"--labels={labels_path}", "-o", str(prg), str(ROOT / "src" / "cp64.asm")],
        check=True, capture_output=True, text=True,
    )
    symbols = labels(labels_path)
    assert "project_value" in symbols
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

    call(mpu, symbols["project_value"], steps=20_000_000)

    hidden = q8_8_vector_from_original_packet(token_packet, 4 + position_row)
    position = q8_8_vector_from_original_packet(position_packet, position_row)
    expected = [
        q8_8_dot([a + b for a, b in zip(hidden, position)], q8_8_attention_row_from_original_packet(attention_packet, 64 + row))
        for row in range(32)
    ]
    assert signed_vector(mpu, symbols["VALUE_VECTOR"]) == expected


@pytest.mark.parametrize("position_row", range(9))
def test_6502_materializes_scaled_self_attention_scores_for_every_playable_input(tmp_path, position_row):
    prg = tmp_path / "CP64.PRG"
    labels_path = tmp_path / "cp64.lbl"
    subprocess.run(
        [str(ASSEMBLER), "--cbm-prg", f"--labels={labels_path}", "-o", str(prg), str(ROOT / "src" / "cp64.asm")],
        check=True, capture_output=True, text=True,
    )
    symbols = labels(labels_path)
    assert "materialize_self_attention_scores" in symbols
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
    call(mpu, symbols["project_key"], steps=20_000_000)

    call(mpu, symbols["materialize_self_attention_scores"])

    query = signed_vector(mpu, symbols["QUERY_VECTOR"])
    key = signed_vector(mpu, symbols["KEY_VECTOR"])
    expected = [q8_8_attention_score(query[offset : offset + 4], key[offset : offset + 4]) for offset in range(0, 32, 4)]
    assert signed_vector(mpu, symbols["ATTENTION_SCORES"])[:8] == expected


def test_6502_single_token_causal_softmax_returns_the_original_value_vector(tmp_path):
    """With one visible causal key, softmax(score) is exactly one."""
    prg = tmp_path / "CP64.PRG"
    labels_path = tmp_path / "cp64.lbl"
    subprocess.run(
        [str(ASSEMBLER), "--cbm-prg", f"--labels={labels_path}", "-o", str(prg), str(ROOT / "src" / "cp64.asm")],
        check=True, capture_output=True, text=True,
    )
    symbols = labels(labels_path)
    assert "single_token_attention_output" in symbols
    assert "ATTENDED_VECTOR" in symbols
    mpu = MPU()
    image = prg.read_bytes()
    load_address = int.from_bytes(image[:2], "little")
    mpu.memory[load_address : load_address + len(image) - 2] = image[2:]
    source = [71, -71, -285, 428, 0, 143, -499, 214] * 4
    for index, value in enumerate(source):
        encoded = value & 0xFFFF
        mpu.memory[symbols["VALUE_VECTOR"] + index * 2] = encoded & 0xFF
        mpu.memory[symbols["VALUE_VECTOR"] + index * 2 + 1] = encoded >> 8

    call(mpu, symbols["single_token_attention_output"])

    assert signed_vector(mpu, symbols["ATTENDED_VECTOR"]) == source


def test_6502_checksums_single_token_attended_output(tmp_path):
    prg = tmp_path / "CP64.PRG"
    labels_path = tmp_path / "cp64.lbl"
    subprocess.run(
        [str(ASSEMBLER), "--cbm-prg", f"--labels={labels_path}", "-o", str(prg), str(ROOT / "src" / "cp64.asm")],
        check=True, capture_output=True, text=True,
    )
    symbols = labels(labels_path)
    assert "checksum_attended_output" in symbols
    mpu = MPU()
    image = prg.read_bytes()
    load_address = int.from_bytes(image[:2], "little")
    mpu.memory[load_address : load_address + len(image) - 2] = image[2:]
    source = [71, -71, -285, 428, 0, 143, -499, 214] * 4
    for index, value in enumerate(source):
        encoded = value & 0xFFFF
        mpu.memory[symbols["ATTENDED_VECTOR"] + index * 2] = encoded & 0xFF
        mpu.memory[symbols["ATTENDED_VECTOR"] + index * 2 + 1] = encoded >> 8

    call(mpu, symbols["checksum_attended_output"])

    expected = sum((index + 1) * value for index, value in enumerate(source)) & 0xFFFF
    actual = mpu.memory[symbols["attended_sumlo"]] | (mpu.memory[symbols["attended_sumhi"]] << 8)
    assert actual == expected


def test_6502_two_key_head0_softmax_uses_original_value_history(tmp_path):
    """Two original visible keys produce normalized Q0.15 weights and V output."""
    prg = tmp_path / "CP64.PRG"
    labels_path = tmp_path / "cp64.lbl"
    subprocess.run([str(ASSEMBLER), "--cbm-prg", f"--labels={labels_path}", "-o", str(prg), str(ROOT / "src" / "cp64.asm")], check=True, capture_output=True, text=True)
    symbols = labels(labels_path)
    assert "two_key_head0_softmax_attention_output" in symbols
    assert "VALUE_HISTORY" in symbols
    mpu = MPU()
    image = prg.read_bytes()
    load_address = int.from_bytes(image[:2], "little")
    mpu.memory[load_address : load_address + len(image) - 2] = image[2:]
    for address, value in ((symbols["CAUSAL_SCORES"], 3), (symbols["CAUSAL_SCORES"] + 16, 28)):
        mpu.memory[address] = value
        mpu.memory[address + 1] = 0
    for base, values in ((symbols["VALUE_HISTORY"], [1387, 4499, 815, 3678]), (symbols["VALUE_HISTORY"] + 64, [2158, 1612, 1809, 1974])):
        for index, value in enumerate(values):
            mpu.memory[base + index * 2] = value & 0xFF
            mpu.memory[base + index * 2 + 1] = value >> 8
    call(mpu, symbols["two_key_head0_softmax_attention_output"], steps=2_000_000)
    assert signed_vector(mpu, symbols["ATTENDED_VECTOR"])[:4] == [1791, 2985, 1336, 2784]
    assert mpu.memory[symbols["softmax_weight_a_lo"]] | (mpu.memory[symbols["softmax_weight_a_hi"]] << 8) == 15585
    assert mpu.memory[symbols["softmax_weight_b_lo"]] | (mpu.memory[symbols["softmax_weight_b_hi"]] << 8) == 17183


def test_6502_two_key_head3_softmax_uses_second_original_attention_head(tmp_path):
    """A second original head uses its own causal scores and projected V lanes."""
    prg = tmp_path / "CP64.PRG"
    labels_path = tmp_path / "cp64.lbl"
    subprocess.run([str(ASSEMBLER), "--cbm-prg", f"--labels={labels_path}", "-o", str(prg), str(ROOT / "src" / "cp64.asm")], check=True, capture_output=True, text=True)
    symbols = labels(labels_path)
    assert "two_key_selected_head_softmax_attention_output" in symbols
    mpu = MPU()
    image = prg.read_bytes()
    load_address = int.from_bytes(image[:2], "little")
    mpu.memory[load_address : load_address + len(image) - 2] = image[2:]
    # b@1 against a@0: head 3 scores [-84, -58], delta 26 Q8.8.
    for address, value in ((symbols["CAUSAL_SCORES"] + 6, -84), (symbols["CAUSAL_SCORES"] + 22, -58)):
        encoded = value & 0xFFFF
        mpu.memory[address] = encoded & 0xFF
        mpu.memory[address + 1] = encoded >> 8
    for base, values in ((symbols["VALUE_HISTORY"] + 24, [3045, -173, 249, 1054]), (symbols["VALUE_HISTORY"] + 88, [-632, -3788, 139, -2177])):
        for index, value in enumerate(values):
            encoded = value & 0xFFFF
            mpu.memory[base + index * 2] = encoded & 0xFF
            mpu.memory[base + index * 2 + 1] = encoded >> 8
    mpu.memory[symbols["softmax_head_offset"]] = 6
    mpu.memory[symbols["softmax_vector_offset"]] = 24

    call(mpu, symbols["two_key_selected_head_softmax_attention_output"], steps=2_000_000)

    assert signed_vector(mpu, symbols["ATTENDED_VECTOR"])[12:16] == [1113, -2072, 191, -643]
    assert mpu.memory[symbols["softmax_weight_a_lo"]] | (mpu.memory[symbols["softmax_weight_a_hi"]] << 8) == 15553
    assert mpu.memory[symbols["softmax_weight_b_lo"]] | (mpu.memory[symbols["softmax_weight_b_hi"]] << 8) == 17215


def test_6502_two_key_combines_two_original_attention_heads(tmp_path):
    """Head 0 and head 3 occupy their original lanes in one attended vector."""
    prg = tmp_path / "CP64.PRG"
    labels_path = tmp_path / "cp64.lbl"
    subprocess.run([str(ASSEMBLER), "--cbm-prg", f"--labels={labels_path}", "-o", str(prg), str(ROOT / "src" / "cp64.asm")], check=True, capture_output=True, text=True)
    symbols = labels(labels_path)
    assert "two_key_head0_and_head3_attention_output" in symbols
    mpu = MPU()
    image = prg.read_bytes()
    load_address = int.from_bytes(image[:2], "little")
    mpu.memory[load_address : load_address + len(image) - 2] = image[2:]
    for offset, value in ((0, 3), (16, 28), (6, -84), (22, -58)):
        encoded = value & 0xFFFF
        mpu.memory[symbols["CAUSAL_SCORES"] + offset] = encoded & 0xFF
        mpu.memory[symbols["CAUSAL_SCORES"] + offset + 1] = encoded >> 8
    for offset, values in ((0, [1387, 4499, 815, 3678]), (64, [2158, 1612, 1809, 1974]), (24, [3045, -173, 249, 1054]), (88, [-632, -3788, 139, -2177])):
        for index, value in enumerate(values):
            encoded = value & 0xFFFF
            mpu.memory[symbols["VALUE_HISTORY"] + offset + index * 2] = encoded & 0xFF
            mpu.memory[symbols["VALUE_HISTORY"] + offset + index * 2 + 1] = encoded >> 8

    call(mpu, symbols["two_key_head0_and_head3_attention_output"], steps=4_000_000)
    call(mpu, symbols["checksum_attended_output"])

    attended = signed_vector(mpu, symbols["ATTENDED_VECTOR"])
    assert attended[:4] == [1791, 2985, 1336, 2784]
    assert attended[12:16] == [1113, -2072, 191, -643]
    assert mpu.memory[symbols["attended_sumlo"]] | (mpu.memory[symbols["attended_sumhi"]] << 8) == 0x03AF


def test_6502_two_key_all_heads_combine_original_attention_output(tmp_path):
    """All eight original A→B attention heads fill the attended vector."""
    prg = tmp_path / "CP64.PRG"
    labels_path = tmp_path / "cp64.lbl"
    subprocess.run([str(ASSEMBLER), "--cbm-prg", f"--labels={labels_path}", "-o", str(prg), str(ROOT / "src" / "cp64.asm")], check=True, capture_output=True, text=True)
    symbols = labels(labels_path)
    assert "two_key_all_heads_attention_output" in symbols
    mpu = MPU()
    image = prg.read_bytes()
    load_address = int.from_bytes(image[:2], "little")
    mpu.memory[load_address : load_address + len(image) - 2] = image[2:]
    packets = [ROOT / "build" / "layers" / name for name in ("C9W00.PRG", "C9W01.PRG", "C9W02.PRG")]

    def project(token_row: int, position_row: int):
        for packet, row_name, row_value, routine in (
            (packets[0], "row", token_row, ("decode_scale", "materialize_embedding")),
            (packets[1], "position_row", position_row, ("decode_position_scale", "materialize_position", "add_position_to_vector")),
        ):
            data = packet.read_bytes()
            mpu.memory[0xC000 : 0xC000 + len(data) - 2] = data[2:]
            mpu.memory[symbols[row_name]] = row_value
            for entry in routine:
                call(mpu, symbols[entry])
        call(mpu, symbols["retain_hidden_vector"])
        data = packets[2].read_bytes()
        mpu.memory[0xC000 : 0xC000 + len(data) - 2] = data[2:]
        for entry in ("project_query", "project_key", "project_value"):
            call(mpu, symbols[entry], steps=20_000_000)
        return tuple(signed_vector(mpu, symbols[name]) for name in ("QUERY_VECTOR", "KEY_VECTOR", "VALUE_VECTOR"))

    _, key_a, value_a = project(4, 0)
    query_b, key_b, value_b = project(5, 1)
    for address, values in ((symbols["KEY_HISTORY"], key_a + key_b), (symbols["VALUE_HISTORY"], value_a + value_b), (symbols["QUERY_VECTOR"], query_b)):
        for index, value in enumerate(values):
            mpu.memory[address + index * 2 : address + index * 2 + 2] = (value & 0xFFFF).to_bytes(2, "little")
    mpu.memory[symbols["causal_query_position"]] = 1
    call(mpu, symbols["materialize_two_token_causal_scores"])
    call(mpu, symbols["two_key_all_heads_attention_output"], steps=16_000_000)
    call(mpu, symbols["checksum_attended_output"])

    assert signed_vector(mpu, symbols["ATTENDED_VECTOR"]) == [1791, 2985, 1336, 2784, 535, -400, 145, 980, -277, -2341, 1273, 2298, 1113, -2072, 191, -643, 1105, 1219, 621, -157, -493, -3859, 1509, -2026, -1149, 981, -1594, 1866, 1358, 1053, -2574, -899]
    assert mpu.memory[symbols["attended_sumlo"]] | (mpu.memory[symbols["attended_sumhi"]] << 8) == 0xFFA0


def test_6502_projects_all_head_attention_through_original_output_weight(tmp_path):
    """C9W04 projects the all-head attended vector with its original INT4 rows."""
    prg = tmp_path / "CP64.PRG"
    labels_path = tmp_path / "cp64.lbl"
    subprocess.run([str(ASSEMBLER), "--cbm-prg", f"--labels={labels_path}", "-o", str(prg), str(ROOT / "src" / "cp64.asm")], check=True, capture_output=True, text=True)
    symbols = labels(labels_path)
    assert "project_attention_output" in symbols
    mpu = MPU()
    image = prg.read_bytes()
    load_address = int.from_bytes(image[:2], "little")
    mpu.memory[load_address : load_address + len(image) - 2] = image[2:]
    attended = [1791, 2985, 1336, 2784, 535, -400, 145, 980, -277, -2341, 1273, 2298, 1113, -2072, 191, -643, 1105, 1219, 621, -157, -493, -3859, 1509, -2026, -1149, 981, -1594, 1866, 1358, 1053, -2574, -899]
    for index, value in enumerate(attended):
        mpu.memory[symbols["ATTENDED_VECTOR"] + index * 2 : symbols["ATTENDED_VECTOR"] + index * 2 + 2] = (value & 0xFFFF).to_bytes(2, "little")
    packet = (ROOT / "build" / "layers" / "C9W04.PRG").read_bytes()
    mpu.memory[0xC000 : 0xC000 + len(packet) - 2] = packet[2:]
    call(mpu, symbols["project_attention_output"], steps=20_000_000)
    call(mpu, symbols["checksum_attended_output"])
    assert signed_vector(mpu, symbols["ATTENDED_VECTOR"]) == [-20509, -8328, 17756, 3716, -5183, 13949, 1662, -2053, 10094, 11390, 5825, -6610, 1449, -2225, -287, -10971, -22552, 15788, 3625, 3714, -426, -8505, 11076, 1362, -6373, -7581, -2633, -23689, -8967, 15104, 10679, -11987]
    assert mpu.memory[symbols["attended_sumlo"]] | (mpu.memory[symbols["attended_sumhi"]] << 8) == 0xCE3E


def test_6502_adds_original_attention_output_bias_to_projected_vector(tmp_path):
    """C9W05's lone original FP16 scale and packed INT4 vector shift all 32 lanes."""
    prg = tmp_path / "CP64.PRG"
    labels_path = tmp_path / "cp64.lbl"
    subprocess.run(
        [str(ASSEMBLER), "--cbm-prg", f"--labels={labels_path}", "-o", str(prg), str(ROOT / "src" / "cp64.asm")],
        check=True, capture_output=True, text=True,
    )
    symbols = labels(labels_path)
    assert "add_attention_output_bias" in symbols
    mpu = MPU()
    image = prg.read_bytes()
    load_address = int.from_bytes(image[:2], "little")
    mpu.memory[load_address : load_address + len(image) - 2] = image[2:]
    projected = [-20509, -8328, 17756, 3716, -5183, 13949, 1662, -2053, 10094, 11390, 5825, -6610, 1449, -2225, -287, -10971, -22552, 15788, 3625, 3714, -426, -8505, 11076, 1362, -6373, -7581, -2633, -23689, -8967, 15104, 10679, -11987]
    for index, value in enumerate(projected):
        mpu.memory[symbols["ATTENDED_VECTOR"] + index * 2 : symbols["ATTENDED_VECTOR"] + index * 2 + 2] = (value & 0xFFFF).to_bytes(2, "little")
    packet = (ROOT / "build" / "layers" / "C9W05.PRG").read_bytes()
    mpu.memory[0xC000 : 0xC000 + len(packet) - 2] = packet[2:]

    call(mpu, symbols["add_attention_output_bias"])
    call(mpu, symbols["checksum_attended_output"])

    bias = q8_8_vector_from_original_packet(ROOT / "build" / "layers" / "C9W05.PRG", 0)
    expected = [((value + offset + 0x8000) & 0xFFFF) - 0x8000 for value, offset in zip(projected, bias)]
    assert signed_vector(mpu, symbols["ATTENDED_VECTOR"]) == expected
    assert mpu.memory[symbols["attended_sumlo"]] | (mpu.memory[symbols["attended_sumhi"]] << 8) == 0xBEEE


def test_6502_adds_original_attention_input_residual(tmp_path):
    """The original post-position hidden vector is added after attention output."""
    prg = tmp_path / "CP64.PRG"
    labels_path = tmp_path / "cp64.lbl"
    subprocess.run([str(ASSEMBLER), "--cbm-prg", f"--labels={labels_path}", "-o", str(prg), str(ROOT / "src" / "cp64.asm")], check=True, capture_output=True, text=True)
    symbols = labels(labels_path)
    assert "add_attention_residual" in symbols
    mpu = MPU()
    image = prg.read_bytes()
    load_address = int.from_bytes(image[:2], "little")
    mpu.memory[load_address : load_address + len(image) - 2] = image[2:]
    before_residual = [-20672, -8246, 18327, 3553, -5020, 13949, 1662, -1971, 10094, 11308, 5743, -6692, 1367, -2388, 39, -10971, -22470, 15380, 3870, 3959, -671, -8097, 10831, 1444, -6455, -8070, -2633, -23771, -8885, 14859, 10761, -11661]
    residual = [-271, 0, -232, -271, -1, -271, -1, -464, 39, 39, 39, -1, 232, -117, -39, 155, 0, -38, -465, -1, 39, -38, 78, 232, 193, 504, -465, -39, 194, -349, 310, -272]
    for base, values in ((symbols["ATTENDED_VECTOR"], before_residual), (symbols["RESIDUAL_VECTOR"], residual)):
        for index, value in enumerate(values):
            mpu.memory[base + index * 2 : base + index * 2 + 2] = (value & 0xFFFF).to_bytes(2, "little")
    call(mpu, symbols["add_attention_residual"])
    call(mpu, symbols["checksum_attended_output"])
    assert signed_vector(mpu, symbols["ATTENDED_VECTOR"]) == [-20943, -8246, 18095, 3282, -5021, 13678, 1661, -2435, 10133, 11347, 5782, -6693, 1599, -2505, 0, -10816, -22470, 15342, 3405, 3958, -632, -8135, 10909, 1676, -6262, -7566, -3098, -23810, -8691, 14510, 11071, -11933]
    assert mpu.memory[symbols["attended_sumlo"]] | (mpu.memory[symbols["attended_sumhi"]] << 8) == 0xAC1A


def test_6502_centers_live_attention_residual_for_layer_norm(tmp_path):
    """The first LayerNorm gate subtracts the symmetric Q8.8 mean from every lane."""
    prg = tmp_path / "CP64.PRG"; labels_path = tmp_path / "cp64.lbl"
    subprocess.run([str(ASSEMBLER), "--cbm-prg", f"--labels={labels_path}", "-o", str(prg), str(ROOT / "src" / "cp64.asm")], check=True, capture_output=True, text=True)
    symbols = labels(labels_path)
    mpu = MPU(); image = prg.read_bytes(); load_address = int.from_bytes(image[:2], "little")
    mpu.memory[load_address : load_address + len(image) - 2] = image[2:]
    residual = [-20943, -8246, 18095, 3282, -5021, 13678, 1661, -2435, 10133, 11347, 5782, -6693, 1599, -2505, 0, -10816, -22470, 15342, 3405, 3958, -632, -8135, 10909, 1676, -6262, -7566, -3098, -23810, -8691, 14510, 11071, -11933]
    for index, value in enumerate(residual):
        mpu.memory[symbols["ATTENDED_VECTOR"] + index * 2 : symbols["ATTENDED_VECTOR"] + index * 2 + 2] = (value & 0xFFFF).to_bytes(2, "little")

    call(mpu, symbols["center_layer_norm_input"])

    total = sum(residual)
    mean = (total + 16) // 32 if total >= 0 else -((-total + 16) // 32)
    expected = [value - mean for value in residual]
    assert mean == -713
    assert signed_vector(mpu, symbols["HIDDEN_VECTOR"]) == expected
    assert mpu.memory[symbols["norm_mean_lo"]] | (mpu.memory[symbols["norm_mean_hi"]] << 8) == (mean & 0xFFFF)
    checksum = sum((index + 1) * value for index, value in enumerate(expected)) & 0xFFFF
    assert mpu.memory[symbols["norm_center_sumlo"]] | (mpu.memory[symbols["norm_center_sumhi"]] << 8) == checksum == 0x6AAA


def test_6502_accumulates_isolated_layer_norm_variance_unsigned32(tmp_path):
    prg = tmp_path / "CP64.PRG"; labels_path = tmp_path / "cp64.lbl"
    subprocess.run([str(ASSEMBLER), "--cbm-prg", f"--labels={labels_path}", "-o", str(prg), str(ROOT / "src" / "cp64.asm")], check=True, capture_output=True, text=True)
    symbols = labels(labels_path); mpu = MPU(); image = prg.read_bytes(); load_address = int.from_bytes(image[:2], "little")
    mpu.memory[load_address : load_address + len(image) - 2] = image[2:]
    residual = [-20943, -8246, 18095, 3282, -5021, 13678, 1661, -2435, 10133, 11347, 5782, -6693, 1599, -2505, 0, -10816, -22470, 15342, 3405, 3958, -632, -8135, 10909, 1676, -6262, -7566, -3098, -23810, -8691, 14510, 11071, -11933]
    for index, value in enumerate(residual): mpu.memory[symbols["ATTENDED_VECTOR"] + index * 2 : symbols["ATTENDED_VECTOR"] + index * 2 + 2] = (value & 0xFFFF).to_bytes(2, "little")
    call(mpu, symbols["center_layer_norm_input"]); call(mpu, symbols["layer_norm_variance32"], steps=5_000_000)
    centered = signed_vector(mpu, symbols["HIDDEN_VECTOR"])
    expected = (sum(value * value for value in centered) + 16) // 32
    actual = sum(mpu.memory[symbols[f"norm_variance{index}"]] << (8 * index) for index in range(4))
    assert expected == actual == 114529754


def test_6502_a_then_b_residual_pipeline_uses_live_attention_state(tmp_path):
    """The browser A→B path retains B's live state, not an isolated fixture."""
    prg = tmp_path / "CP64.PRG"
    labels_path = tmp_path / "cp64.lbl"
    subprocess.run([str(ASSEMBLER), "--cbm-prg", f"--labels={labels_path}", "-o", str(prg), str(ROOT / "src" / "cp64.asm")], check=True, capture_output=True, text=True)
    symbols = labels(labels_path)
    mpu = MPU()
    image = prg.read_bytes()
    load_address = int.from_bytes(image[:2], "little")
    mpu.memory[load_address : load_address + len(image) - 2] = image[2:]

    def page(name: str):
        packet = (ROOT / "build" / "layers" / name).read_bytes()
        mpu.memory[0xC000 : 0xC000 + len(packet) - 2] = packet[2:]

    def run(token: str):
        mpu.memory[symbols["selected"]] = ord(token)
        page("C9W00.PRG"); mpu.memory[symbols["row"]] = 4 + ord(token) - ord("a")
        call(mpu, symbols["decode_scale"]); call(mpu, symbols["materialize_embedding"])
        page("C9W01.PRG"); mpu.memory[symbols["position_row"]] = ord(token) - ord("a")
        call(mpu, symbols["decode_position_scale"]); call(mpu, symbols["materialize_position"]); call(mpu, symbols["add_position_to_vector"]); call(mpu, symbols["retain_hidden_vector"])
        page("C9W02.PRG"); mpu.memory[symbols["projection_packed_offset"]] = 0xC9
        for routine in ("project_query", "project_key", "project_value"):
            call(mpu, symbols[routine], steps=20_000_000)
        call(mpu, symbols["capture_two_key_sequence"]); call(mpu, symbols["materialize_self_attention_scores"])
        if mpu.memory[symbols["two_key_ready"]]:
            mpu.memory[symbols["causal_query_position"]] = 1
            call(mpu, symbols["materialize_two_token_causal_scores"]); call(mpu, symbols["two_key_all_heads_attention_output"], steps=16_000_000)
        else:
            call(mpu, symbols["single_token_attention_output"])
        call(mpu, symbols["retain_attention_residual"])
        page("C9W04.PRG"); call(mpu, symbols["project_attention_output"], steps=20_000_000)
        page("C9W05.PRG"); call(mpu, symbols["add_attention_output_bias"]); call(mpu, symbols["add_attention_residual"]); call(mpu, symbols["checksum_attended_output"])

    run("a"); run("b")
    assert mpu.memory[symbols["attended_sumlo"]] | (mpu.memory[symbols["attended_sumhi"]] << 8) == 0xFF9E
    call(mpu, symbols["center_layer_norm_input"])
    call(mpu, symbols["layer_norm_variance32"], steps=5_000_000)
    actual_variance = sum(mpu.memory[symbols[f"norm_variance{index}"]] << (8 * index) for index in range(4))
    assert actual_variance == 0x06C97ECE
    call(mpu, symbols["sqrt_variance_to_q8_8"])
    assert mpu.memory[symbols["norm_rms_lo"]] | (mpu.memory[symbols["norm_rms_hi"]] << 8) == 0x29AF
    call(mpu, symbols["normalize_layer_norm_input"], steps=5_000_000)
    normalized = [-488, -190, 450, 98, -112, 336, 51, -34, 262, 284, 157, -139, 60, -46, 24, -238, -521, 380, 100, 119, 1, -180, 274, 61, -133, -163, -60, -544, -193, 371, 285, -272]
    assert signed_vector(mpu, symbols["HIDDEN_VECTOR"]) == normalized
    call(mpu, symbols["checksum_normalized_output"])
    assert mpu.memory[symbols["norm_normalized_sumlo"]] | (mpu.memory[symbols["norm_normalized_sumhi"]] << 8) == 0xDF93
    page("C9W06.PRG"); call(mpu, symbols["materialize_norm_weight"])
    page("C9W07.PRG"); call(mpu, symbols["materialize_norm_bias"])
    call(mpu, symbols["apply_norm_affine"], steps=5_000_000)
    affine = [-74, -134, 141, 98, -73, 305, 56, -14, 165, 155, 71, -146, 29, 33, -41, -120, -214, 210, 43, -47, 46, -149, 155, 30, -9, -9, -53, -258, -94, 228, 91, -101]
    assert signed_vector(mpu, symbols["ATTENDED_VECTOR"]) == affine
    call(mpu, symbols["checksum_norm_affine"])
    assert mpu.memory[symbols["norm_affine_sumlo"]] | (mpu.memory[symbols["norm_affine_sumhi"]] << 8) == 0xFCBF


def test_6502_causal_score_row_masks_the_future_original_key(tmp_path):
    """Position zero sees its original key and encodes position one as -infinity."""
    prg = tmp_path / "CP64.PRG"
    labels_path = tmp_path / "cp64.lbl"
    subprocess.run(
        [str(ASSEMBLER), "--cbm-prg", f"--labels={labels_path}", "-o", str(prg), str(ROOT / "src" / "cp64.asm")],
        check=True, capture_output=True, text=True,
    )
    symbols = labels(labels_path)
    assert "materialize_two_token_causal_scores" in symbols
    assert "KEY_HISTORY" in symbols
    mpu = MPU()
    image = prg.read_bytes()
    load_address = int.from_bytes(image[:2], "little")
    mpu.memory[load_address : load_address + len(image) - 2] = image[2:]
    token_packet = ROOT / "build" / "layers" / "C9W00.PRG"
    position_packet = ROOT / "build" / "layers" / "C9W01.PRG"
    attention_packet = ROOT / "build" / "layers" / "C9W02.PRG"

    def project(token_row: int, position_row: int) -> tuple[list[int], list[int]]:
        mpu.memory[0xC000 : 0xC000 + len(token_packet.read_bytes()) - 2] = token_packet.read_bytes()[2:]
        mpu.memory[symbols["row"]] = token_row
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
        call(mpu, symbols["project_key"], steps=20_000_000)
        return signed_vector(mpu, symbols["QUERY_VECTOR"]), signed_vector(mpu, symbols["KEY_VECTOR"])

    query_zero, key_zero = project(4, 0)
    _, key_one = project(5, 1)
    for offset, value in enumerate(key_zero + key_one):
        encoded = value & 0xFFFF
        mpu.memory[symbols["KEY_HISTORY"] + offset * 2] = encoded & 0xFF
        mpu.memory[symbols["KEY_HISTORY"] + offset * 2 + 1] = encoded >> 8
    for offset, value in enumerate(query_zero):
        encoded = value & 0xFFFF
        mpu.memory[symbols["QUERY_VECTOR"] + offset * 2] = encoded & 0xFF
        mpu.memory[symbols["QUERY_VECTOR"] + offset * 2 + 1] = encoded >> 8
    mpu.memory[symbols["causal_query_position"]] = 0

    call(mpu, symbols["materialize_two_token_causal_scores"])

    expected = [q8_8_attention_score(query_zero[offset : offset + 4], key_zero[offset : offset + 4]) for offset in range(0, 32, 4)]
    assert signed_vector(mpu, symbols["CAUSAL_SCORES"])[:8] == expected
    assert signed_vector(mpu, symbols["CAUSAL_SCORES"])[8:16] == [-32768] * 8


def test_6502_three_token_causal_score_row_keeps_prior_original_keys(tmp_path):
    """Position one sees both preceding original keys and masks position two."""
    prg = tmp_path / "CP64.PRG"
    labels_path = tmp_path / "cp64.lbl"
    subprocess.run(
        [str(ASSEMBLER), "--cbm-prg", f"--labels={labels_path}", "-o", str(prg), str(ROOT / "src" / "cp64.asm")],
        check=True, capture_output=True, text=True,
    )
    symbols = labels(labels_path)
    assert "materialize_three_token_causal_scores" in symbols
    assert "KEY_HISTORY" in symbols
    mpu = MPU()
    image = prg.read_bytes()
    load_address = int.from_bytes(image[:2], "little")
    mpu.memory[load_address : load_address + len(image) - 2] = image[2:]
    token_packet = ROOT / "build" / "layers" / "C9W00.PRG"
    position_packet = ROOT / "build" / "layers" / "C9W01.PRG"
    attention_packet = ROOT / "build" / "layers" / "C9W02.PRG"

    def project(token_row: int, position_row: int) -> tuple[list[int], list[int]]:
        mpu.memory[0xC000 : 0xC000 + len(token_packet.read_bytes()) - 2] = token_packet.read_bytes()[2:]
        mpu.memory[symbols["row"]] = token_row
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
        call(mpu, symbols["project_key"], steps=20_000_000)
        return signed_vector(mpu, symbols["QUERY_VECTOR"]), signed_vector(mpu, symbols["KEY_VECTOR"])

    _, key_zero = project(4, 0)
    query_one, key_one = project(5, 1)
    _, key_two = project(6, 2)
    for offset, value in enumerate(key_zero + key_one + key_two):
        encoded = value & 0xFFFF
        mpu.memory[symbols["KEY_HISTORY"] + offset * 2] = encoded & 0xFF
        mpu.memory[symbols["KEY_HISTORY"] + offset * 2 + 1] = encoded >> 8
    for offset, value in enumerate(query_one):
        encoded = value & 0xFFFF
        mpu.memory[symbols["QUERY_VECTOR"] + offset * 2] = encoded & 0xFF
        mpu.memory[symbols["QUERY_VECTOR"] + offset * 2 + 1] = encoded >> 8
    mpu.memory[symbols["causal_query_position"]] = 1

    call(mpu, symbols["materialize_three_token_causal_scores"])

    expected_zero = [q8_8_attention_score(query_one[offset : offset + 4], key_zero[offset : offset + 4]) for offset in range(0, 32, 4)]
    expected_one = [q8_8_attention_score(query_one[offset : offset + 4], key_one[offset : offset + 4]) for offset in range(0, 32, 4)]
    scores = signed_vector(mpu, symbols["CAUSAL_SCORES"])
    assert scores[:8] == expected_zero
    assert scores[8:16] == expected_one
    assert scores[16:24] == [-32768] * 8


def test_6502_projects_live_norm_output_through_all_original_router_rows(tmp_path):
    """C9W08 maps the retained live LayerNorm affine vector to nine router logits."""
    prg = tmp_path / "CP64.PRG"
    labels_path = tmp_path / "cp64.lbl"
    subprocess.run(
        [str(ASSEMBLER), "--cbm-prg", f"--labels={labels_path}", "-o", str(prg), str(ROOT / "src" / "cp64.asm")],
        check=True, capture_output=True, text=True,
    )
    symbols = labels(labels_path)
    assert "project_router" in symbols
    assert "ROUTER_LOGITS" in symbols
    mpu = MPU()
    image = prg.read_bytes()
    load_address = int.from_bytes(image[:2], "little")
    mpu.memory[load_address : load_address + len(image) - 2] = image[2:]
    live_norm_output = [-74, -134, 141, 98, -73, 305, 56, -14, 165, 155, 71, -146, 29, 33, -41, -120, -214, 210, 43, -47, 46, -149, 155, 30, -9, -9, -53, -258, -94, 228, 91, -101]
    for index, value in enumerate(live_norm_output):
        mpu.memory[symbols["ATTENDED_VECTOR"] + index * 2 : symbols["ATTENDED_VECTOR"] + index * 2 + 2] = (value & 0xFFFF).to_bytes(2, "little")
    packet = ROOT / "build" / "layers" / "C9W08.PRG"
    payload = packet.read_bytes()
    mpu.memory[0xC000 : 0xC000 + len(payload) - 2] = payload[2:]

    call(mpu, symbols["project_router"], steps=20_000_000)

    expected = [q8_8_dot(live_norm_output, q8_8_vector_from_original_packet(packet, row)) for row in range(9)]
    actual = []
    for index in range(9):
        value = mpu.memory[symbols["ROUTER_LOGITS"] + index * 2] | (mpu.memory[symbols["ROUTER_LOGITS"] + index * 2 + 1] << 8)
        actual.append(value - 0x10000 if value & 0x8000 else value)
    assert actual == expected


def test_6502_adds_original_router_bias_to_all_live_router_logits(tmp_path):
    """C9W09's original tensor-scale INT4 bias shifts each of the nine logits."""
    prg = tmp_path / "CP64.PRG"
    labels_path = tmp_path / "cp64.lbl"
    subprocess.run(
        [str(ASSEMBLER), "--cbm-prg", f"--labels={labels_path}", "-o", str(prg), str(ROOT / "src" / "cp64.asm")],
        check=True, capture_output=True, text=True,
    )
    symbols = labels(labels_path)
    assert "add_router_bias" in symbols
    assert "ROUTER_LOGITS" in symbols
    mpu = MPU()
    image = prg.read_bytes()
    load_address = int.from_bytes(image[:2], "little")
    mpu.memory[load_address : load_address + len(image) - 2] = image[2:]
    projected_logits = [-839, 1559, 9, -228, 1324, -381, -613, -1574, 878]
    for index, value in enumerate(projected_logits):
        mpu.memory[symbols["ROUTER_LOGITS"] + index * 2 : symbols["ROUTER_LOGITS"] + index * 2 + 2] = (value & 0xFFFF).to_bytes(2, "little")
    packet = ROOT / "build" / "layers" / "C9W09.PRG"
    payload = packet.read_bytes()
    mpu.memory[0xC000 : 0xC000 + len(payload) - 2] = payload[2:]

    call(mpu, symbols["add_router_bias"])

    bias = q8_8_vector_from_original_packet(packet, 0)[:9]
    actual = []
    for index in range(9):
        value = mpu.memory[symbols["ROUTER_LOGITS"] + index * 2] | (mpu.memory[symbols["ROUTER_LOGITS"] + index * 2 + 1] << 8)
        actual.append(value - 0x10000 if value & 0x8000 else value)
    assert actual == [logit + offset for logit, offset in zip(projected_logits, bias)]


def test_6502_selects_the_two_largest_original_router_logits(tmp_path):
    """Top-2 selection preserves the winning C9W08/C9W09 expert indices and logits."""
    prg = tmp_path / "CP64.PRG"
    labels_path = tmp_path / "cp64.lbl"
    subprocess.run(
        [str(ASSEMBLER), "--cbm-prg", f"--labels={labels_path}", "-o", str(prg), str(ROOT / "src" / "cp64.asm")],
        check=True, capture_output=True, text=True,
    )
    symbols = labels(labels_path)
    assert "select_router_top2" in symbols
    mpu = MPU()
    image = prg.read_bytes()
    load_address = int.from_bytes(image[:2], "little")
    mpu.memory[load_address : load_address + len(image) - 2] = image[2:]
    for index, value in enumerate([-839, 1559, 9, -228, 1324, -381, -613, -1574, 878]):
        mpu.memory[symbols["ROUTER_LOGITS"] + index * 2 : symbols["ROUTER_LOGITS"] + index * 2 + 2] = (value & 0xFFFF).to_bytes(2, "little")
    packet = ROOT / "build" / "layers" / "C9W09.PRG"
    payload = packet.read_bytes()
    mpu.memory[0xC000 : 0xC000 + len(payload) - 2] = payload[2:]
    call(mpu, symbols["add_router_bias"])
    call(mpu, symbols["select_router_top2"])

    final_logits = [-839 + value for value in q8_8_vector_from_original_packet(packet, 0)[:1]]
    final_logits += [value + offset for value, offset in zip([1559, 9, -228, 1324, -381, -613, -1574, 878], q8_8_vector_from_original_packet(packet, 0)[1:9])]
    expected = sorted(enumerate(final_logits), key=lambda item: item[1], reverse=True)[:2]
    assert (mpu.memory[symbols["router_top1_index"]], mpu.memory[symbols["router_top1_lo"]] | (mpu.memory[symbols["router_top1_hi"]] << 8)) == (expected[0][0], expected[0][1] & 0xFFFF)
    assert (mpu.memory[symbols["router_top2_index"]], mpu.memory[symbols["router_top2_lo"]] | (mpu.memory[symbols["router_top2_hi"]] << 8)) == (expected[1][0], expected[1][1] & 0xFFFF)


def test_6502_normalizes_selected_original_router_logits_to_q0_15(tmp_path):
    """The selected C9W08/C9W09 logits become a stable two-expert Q0.15 gate."""
    prg = tmp_path / "CP64.PRG"
    labels_path = tmp_path / "cp64.lbl"
    subprocess.run(
        [str(ASSEMBLER), "--cbm-prg", f"--labels={labels_path}", "-o", str(prg), str(ROOT / "src" / "cp64.asm")],
        check=True, capture_output=True, text=True,
    )
    symbols = labels(labels_path)
    assert "normalize_router_top2" in symbols
    mpu = MPU()
    image = prg.read_bytes()
    load_address = int.from_bytes(image[:2], "little")
    mpu.memory[load_address : load_address + len(image) - 2] = image[2:]
    projected_logits = [-839, 1559, 9, -228, 1324, -381, -613, -1574, 878]
    for index, value in enumerate(projected_logits):
        mpu.memory[symbols["ROUTER_LOGITS"] + index * 2 : symbols["ROUTER_LOGITS"] + index * 2 + 2] = (value & 0xFFFF).to_bytes(2, "little")
    packet = ROOT / "build" / "layers" / "C9W09.PRG"
    payload = packet.read_bytes()
    mpu.memory[0xC000 : 0xC000 + len(payload) - 2] = payload[2:]

    call(mpu, symbols["add_router_bias"])
    call(mpu, symbols["select_router_top2"])
    call(mpu, symbols["normalize_router_top2"])

    final_logits = [value + offset for value, offset in zip(projected_logits, q8_8_vector_from_original_packet(packet, 0)[:9])]
    delta = max(final_logits) - sorted(final_logits)[-2]
    expected_top1 = round(32768 / (1 + exp(-delta / 256)))
    expected_top2 = 32768 - expected_top1
    actual_top1 = mpu.memory[symbols["router_weight_top1_lo"]] | (mpu.memory[symbols["router_weight_top1_hi"]] << 8)
    actual_top2 = mpu.memory[symbols["router_weight_top2_lo"]] | (mpu.memory[symbols["router_weight_top2_hi"]] << 8)
    assert (actual_top1, actual_top2) == (expected_top1, expected_top2)


def test_interactive_pipeline_pages_original_router_bias_after_router_projection():
    """The executable gate pages C9W09 only after C9W08 produced all nine logits."""
    source = (ROOT / "src" / "cp64.asm").read_text()
    request = source[source.index("router_loaded:") : source.index("lda #<scale_result")]
    assert request.index("jsr project_router") < request.index("jsr load_router_bias")
    assert request.index("jsr load_router_bias") < request.index("jsr add_router_bias")
    assert 'router_bias_filename: .text "C9W09.PRG"' in source


def test_interactive_pipeline_selects_router_top2_after_adding_original_bias():
    source = (ROOT / "src" / "cp64.asm").read_text()
    request = source[source.index("router_loaded:") : source.index("lda #<scale_result")]
    assert request.index("jsr add_router_bias") < request.index("jsr select_router_top2")


def test_interactive_pipeline_normalizes_router_top2_after_selection():
    source = (ROOT / "src" / "cp64.asm").read_text()
    request = source[source.index("router_loaded:") : source.index("lda #<scale_result")]
    assert request.index("jsr select_router_top2") < request.index("jsr normalize_router_top2")


def test_interactive_pipeline_pages_original_router_after_norm_affine():
    """The executable gate must page C9W08 only after producing its live input."""
    source = (ROOT / "src" / "cp64.asm").read_text()
    request = source[source.index("norm_bias_loaded:") : source.index("lda #<scale_result")]
    assert request.index("jsr apply_norm_affine") < request.index("jsr load_router")
    assert request.index("jsr load_router") < request.index("jsr project_router")
    assert 'router_filename: .text "C9W08.PRG"' in source


def test_6502_selected_expert_first_affines_match_original_packets(tmp_path):
    """Stage 038 executes E1/E4 first affine from verbatim packets on live A→B."""
    prg = tmp_path / "CP64.PRG"; labels_path = tmp_path / "cp64.lbl"
    subprocess.run([str(ASSEMBLER), "--cbm-prg", f"--labels={labels_path}", "-o", str(prg), str(ROOT / "src" / "cp64.asm")], check=True, capture_output=True, text=True)
    symbols = labels(labels_path); mpu = MPU(); image = prg.read_bytes(); load_address = int.from_bytes(image[:2], "little")
    mpu.memory[load_address : load_address + len(image) - 2] = image[2:]
    state = [-74, -134, 141, 98, -73, 305, 56, -14, 165, 155, 71, -146, 29, 33, -41, -120, -214, 210, 43, -47, 46, -149, 155, 30, -9, -9, -53, -258, -94, 228, 91, -101]
    cases = (
        (1, "C9W14.PRG", "C9W15.PRG", [-902, -834, -1747, -707, -492, -2540, -1586, -853, -1236, 76, -1762, -2846, -770, -357, -1794, -1597, -1214, -1637, -753, -2636, -1300, -2107, -512, -1103, -1161, -1044, -1636, -1300, -2228, -701, -2006, -639]),
        (4, "C9W26.PRG", "C9W27.PRG", [-1929, 69, -300, -961, -1662, -842, -773, -2055, -2018, -1302, -2289, -1513, -910, -2190, -1160, -1637, -1431, 240, 1373, 681, -260, -1024, 121, -2714, -143, -1294, 938, -1258, -409, -1016, -774, -2365]),
    )
    for expert, packet_name, bias_name, expected in cases:
        for lane, value in enumerate(state):
            mpu.memory[symbols["ATTENDED_VECTOR"] + lane * 2 : symbols["ATTENDED_VECTOR"] + lane * 2 + 2] = (value & 0xFFFF).to_bytes(2, "little")
        call(mpu, symbols["retain_expert_input"], steps=5_000_000)
        payload = (ROOT / "build" / "layers" / packet_name).read_bytes()[2:]
        mpu.memory[0xC000 : 0xC000 + len(payload)] = payload
        mpu.memory[symbols["expert_index"]] = expert
        call(mpu, symbols["project_selected_expert_first"], steps=100_000_000)
        payload = (ROOT / "build" / "layers" / bias_name).read_bytes()[2:]
        mpu.memory[0xC000 : 0xC000 + len(payload)] = payload
        call(mpu, symbols["add_selected_expert_first_bias"], steps=5_000_000)
        assert signed_vector(mpu, symbols["EXPERT_FIRST_VECTOR"]) == expected


def q8_8_bounded_silu(value: int) -> int:
    """CP64 contract: nearest Q0.15 sigmoid table, |x| clamped to 8.0 Q8.8."""
    magnitude = min(abs(value), 8 * 256)
    table = (ROOT / "src" / "router_sigmoid_q0_15.bin").read_bytes()
    sigmoid = int.from_bytes(table[magnitude * 2 : magnitude * 2 + 2], "little")
    if value < 0:
        sigmoid = 32768 - sigmoid
    product = value * sigmoid
    return (product + 16384) // 32768 if product >= 0 else -((-product + 16384) // 32768)


def test_6502_selected_expert_second_affines_follow_bounded_silu(tmp_path):
    """E1/E4 execute original 0/2 tensors after the declared Q8.8 SiLU contract."""
    prg = tmp_path / "CP64.PRG"; labels_path = tmp_path / "cp64.lbl"
    subprocess.run([str(ASSEMBLER), "--cbm-prg", f"--labels={labels_path}", "-o", str(prg), str(ROOT / "src" / "cp64.asm")], check=True, capture_output=True, text=True)
    symbols = labels(labels_path); mpu = MPU(); image = prg.read_bytes(); load_address = int.from_bytes(image[:2], "little")
    mpu.memory[load_address : load_address + len(image) - 2] = image[2:]
    state = [-74, -134, 141, 98, -73, 305, 56, -14, 165, 155, 71, -146, 29, 33, -41, -120, -214, 210, 43, -47, 46, -149, 155, 30, -9, -9, -53, -258, -94, 228, 91, -101]
    cases = ((1, "C9W14.PRG", "C9W15.PRG", "C9W16.PRG", "C9W17.PRG"), (4, "C9W26.PRG", "C9W27.PRG", "C9W28.PRG", "C9W29.PRG"))
    for expert, first_weight, first_bias, second_weight, second_bias in cases:
        for lane, value in enumerate(state):
            mpu.memory[symbols["ATTENDED_VECTOR"] + lane * 2 : symbols["ATTENDED_VECTOR"] + lane * 2 + 2] = (value & 0xFFFF).to_bytes(2, "little")
        call(mpu, symbols["retain_expert_input"], steps=5_000_000)
        for packet_name, routine in ((first_weight, "project_selected_expert_first"), (first_bias, "add_selected_expert_first_bias"), (None, "apply_selected_expert_silu"), (second_weight, "project_selected_expert_second"), (second_bias, "add_selected_expert_second_bias")):
            if packet_name:
                payload = (ROOT / "build" / "layers" / packet_name).read_bytes()[2:]
                mpu.memory[0xC000 : 0xC000 + len(payload)] = payload
            call(mpu, symbols[routine], steps=100_000_000)
        first = [q8_8_dot(state, q8_8_vector_from_original_packet(ROOT / "build" / "layers" / first_weight, row)) for row in range(32)]
        first_bias_values = q8_8_vector_from_original_packet(ROOT / "build" / "layers" / first_bias, 0)
        activated = [q8_8_bounded_silu(value + bias) for value, bias in zip(first, first_bias_values)]
        second = [q8_8_dot(activated, q8_8_vector_from_original_packet(ROOT / "build" / "layers" / second_weight, row)) for row in range(32)]
        second_bias_values = q8_8_vector_from_original_packet(ROOT / "build" / "layers" / second_bias, 0)
        expected = [((value + bias + 0x8000) & 0xFFFF) - 0x8000 for value, bias in zip(second, second_bias_values)]
        assert signed_vector(mpu, symbols["ATTENDED_VECTOR"]) == expected


def test_6502_e4_first_affine_retains_live_pre_expert_input_after_e1(tmp_path):
    """Live E4 starts from the retained norm output, never E1's second-affine output."""
    prg = tmp_path / "CP64.PRG"; labels_path = tmp_path / "cp64.lbl"
    subprocess.run([str(ASSEMBLER), "--cbm-prg", f"--labels={labels_path}", "-o", str(prg), str(ROOT / "src" / "cp64.asm")], check=True, capture_output=True, text=True)
    symbols = labels(labels_path); mpu = MPU(); image = prg.read_bytes(); load_address = int.from_bytes(image[:2], "little")
    mpu.memory[load_address : load_address + len(image) - 2] = image[2:]
    state = [-74, -134, 141, 98, -73, 305, 56, -14, 165, 155, 71, -146, 29, 33, -41, -120, -214, 210, 43, -47, 46, -149, 155, 30, -9, -9, -53, -258, -94, 228, 91, -101]
    for lane, value in enumerate(state):
        mpu.memory[symbols["ATTENDED_VECTOR"] + lane * 2 : symbols["ATTENDED_VECTOR"] + lane * 2 + 2] = (value & 0xFFFF).to_bytes(2, "little")
    call(mpu, symbols["retain_expert_input"], steps=5_000_000)
    for packet_name, routine in (("C9W14.PRG", "project_selected_expert_first"), ("C9W15.PRG", "add_selected_expert_first_bias"), (None, "apply_selected_expert_silu"), ("C9W16.PRG", "project_selected_expert_second"), ("C9W17.PRG", "add_selected_expert_second_bias"), ("C9W26.PRG", "project_selected_expert_first")):
        if packet_name:
            payload = (ROOT / "build" / "layers" / packet_name).read_bytes()[2:]
            mpu.memory[0xC000 : 0xC000 + len(payload)] = payload
        call(mpu, symbols[routine], steps=100_000_000)
    expected = [q8_8_dot(state, q8_8_vector_from_original_packet(ROOT / "build" / "layers" / "C9W26.PRG", row)) for row in range(32)]
    assert signed_vector(mpu, symbols["EXPERT_FIRST_VECTOR"]) == expected


def test_interactive_pipeline_pages_both_selected_expert_second_affines_after_router_normalization():
    """The user path cannot claim the expert gate without paging all E1/E4 tensors."""
    source = (ROOT / "src" / "cp64.asm").read_text()
    request = source[source.index("jsr normalize_router_top2") : source.index("lda #<scale_result")]
    for routine in ("project_selected_expert_first", "add_selected_expert_first_bias", "apply_selected_expert_silu", "project_selected_expert_second", "add_selected_expert_second_bias"):
        assert request.count(f"jsr {routine}") == 2
    for name in ("C9W14.PRG", "C9W15.PRG", "C9W16.PRG", "C9W17.PRG", "C9W26.PRG", "C9W27.PRG", "C9W28.PRG", "C9W29.PRG"):
        assert name in source


def q8_8_weighted_q0_15(value: int, weight: int) -> int:
    product = value * weight
    return (product + 16384) // 32768 if product >= 0 else -((-product + 16384) // 32768)


def test_6502_merges_selected_expert_outputs_with_live_q0_15_router_weights(tmp_path):
    """Stage 039 forms every bounded MoE lane from E1/E4 and their live weights."""
    prg = tmp_path / "CP64.PRG"; labels_path = tmp_path / "cp64.lbl"
    subprocess.run([str(ASSEMBLER), "--cbm-prg", f"--labels={labels_path}", "-o", str(prg), str(ROOT / "src" / "cp64.asm")], check=True, capture_output=True, text=True)
    symbols = labels(labels_path); mpu = MPU(); image = prg.read_bytes(); load_address = int.from_bytes(image[:2], "little")
    mpu.memory[load_address : load_address + len(image) - 2] = image[2:]
    expert1 = [-1024, -511, -257, -1, 0, 1, 255, 511] * 4
    expert4 = [777, 333, 1, 0, -1, -255, -512, -1000] * 4
    for base, values in ((symbols["EXPERT_ONE_VECTOR"], expert1), (symbols["ATTENDED_VECTOR"], expert4)):
        for lane, value in enumerate(values):
            mpu.memory[base + lane * 2 : base + lane * 2 + 2] = (value & 0xFFFF).to_bytes(2, "little")
    mpu.memory[symbols["router_weight_top1_lo"]] = 0x0F
    mpu.memory[symbols["router_weight_top1_hi"]] = 0x63
    mpu.memory[symbols["router_weight_top2_lo"]] = 0xF1
    mpu.memory[symbols["router_weight_top2_hi"]] = 0x1C
    call(mpu, symbols["merge_selected_expert_outputs"])
    expected = [q8_8_weighted_q0_15(one, 0x630F) + q8_8_weighted_q0_15(four, 0x1CF1) for one, four in zip(expert1, expert4)]
    assert signed_vector(mpu, symbols["ATTENDED_VECTOR"]) == expected


def test_6502_adds_retained_norm_input_after_selected_expert_merge(tmp_path):
    """Stage 040 restores the live pre-MoE norm state after the weighted merge."""
    prg = tmp_path / "CP64.PRG"; labels_path = tmp_path / "cp64.lbl"
    subprocess.run([str(ASSEMBLER), "--cbm-prg", f"--labels={labels_path}", "-o", str(prg), str(ROOT / "src" / "cp64.asm")], check=True, capture_output=True, text=True)
    symbols = labels(labels_path); mpu = MPU(); image = prg.read_bytes(); load_address = int.from_bytes(image[:2], "little")
    mpu.memory[load_address : load_address + len(image) - 2] = image[2:]
    merged = [-32768, -1024, -1, 0, 1, 1024, 32766, 30000] * 4
    retained = [-1, -512, -1, 0, 1, 512, 1, 10000] * 4
    for base, values in ((symbols["ATTENDED_VECTOR"], merged), (symbols["RESIDUAL_VECTOR"], retained)):
        for lane, value in enumerate(values):
            mpu.memory[base + lane * 2 : base + lane * 2 + 2] = (value & 0xFFFF).to_bytes(2, "little")
    call(mpu, symbols["add_selected_expert_residual"])
    expected = [((value + residual + 0x8000) & 0xFFFF) - 0x8000 for value, residual in zip(merged, retained)]
    assert signed_vector(mpu, symbols["ATTENDED_VECTOR"]) == expected


def test_6502_projects_original_output_head_rows_from_post_moe_residual(tmp_path):
    """Stage 041 projects all 13 C9W46 token logits from the live residual."""
    prg = tmp_path / "CP64.PRG"; labels_path = tmp_path / "cp64.lbl"
    subprocess.run([str(ASSEMBLER), "--cbm-prg", f"--labels={labels_path}", "-o", str(prg), str(ROOT / "src" / "cp64.asm")], check=True, capture_output=True, text=True)
    symbols = labels(labels_path); mpu = MPU(); image = prg.read_bytes(); load_address = int.from_bytes(image[:2], "little")
    mpu.memory[load_address : load_address + len(image) - 2] = image[2:]
    state = [-74, -134, 141, 98, -73, 305, 56, -14, 165, 155, 71, -146, 29, 33, -41, -120, -214, 210, 43, -47, 46, -149, 155, 30, -9, -9, -53, -258, -94, 228, 91, -101]
    for lane, value in enumerate(state):
        mpu.memory[symbols["ATTENDED_VECTOR"] + lane * 2 : symbols["ATTENDED_VECTOR"] + lane * 2 + 2] = (value & 0xFFFF).to_bytes(2, "little")
    payload = (ROOT / "build" / "layers" / "C9W46.PRG").read_bytes()[2:]
    mpu.memory[0xC000 : 0xC000 + len(payload)] = payload
    call(mpu, symbols["project_output_head"], steps=100_000_000)
    expected = [q8_8_dot(state, q8_8_vector_from_original_packet(ROOT / "build" / "layers" / "C9W46.PRG", row)) for row in range(13)]
    actual = []
    for row in range(13):
        value = mpu.memory[symbols["OUTPUT_LOGITS"] + row * 2] | (mpu.memory[symbols["OUTPUT_LOGITS"] + row * 2 + 1] << 8)
        actual.append(value - 0x10000 if value & 0x8000 else value)
    assert actual == expected


def test_6502_adds_original_output_head_bias_to_all_13_logits(tmp_path):
    """Stage 042 adds only the 13 declared C9W47 bias lanes, not its pad nibble."""
    prg = tmp_path / "CP64.PRG"; labels_path = tmp_path / "cp64.lbl"
    subprocess.run([str(ASSEMBLER), "--cbm-prg", f"--labels={labels_path}", "-o", str(prg), str(ROOT / "src" / "cp64.asm")], check=True, capture_output=True, text=True)
    symbols = labels(labels_path); mpu = MPU(); image = prg.read_bytes(); load_address = int.from_bytes(image[:2], "little")
    mpu.memory[load_address : load_address + len(image) - 2] = image[2:]
    logits = [-3000, -1024, -1, 0, 1, 1024, 3000, 77, -77, 255, -255, 8191, -8192]
    for row, value in enumerate(logits):
        mpu.memory[symbols["OUTPUT_LOGITS"] + row * 2 : symbols["OUTPUT_LOGITS"] + row * 2 + 2] = (value & 0xFFFF).to_bytes(2, "little")
    packet_path = ROOT / "build" / "layers" / "C9W47.PRG"
    payload = packet_path.read_bytes()[2:]
    mpu.memory[0xC000 : 0xC000 + len(payload)] = payload
    call(mpu, symbols["add_output_head_bias"])
    packet = payload; raw_scale = int.from_bytes(packet[9:11], "little"); exponent = (raw_scale >> 10) & 0x1F; fraction = raw_scale & 0x03FF
    scale = (1024 + fraction) << (exponent - 17) if exponent >= 17 else (1024 + fraction + (1 << (17 - exponent - 1))) >> (17 - exponent)
    codes = [nibble - 16 if nibble >= 8 else nibble for byte in packet[11:] for nibble in (byte & 0x0F, byte >> 4)][:13]
    bias = [(code * scale + 3) // 7 if code >= 0 else -((-code * scale + 3) // 7) for code in codes]
    actual = [int.from_bytes(mpu.memory[symbols["OUTPUT_LOGITS"] + row * 2 : symbols["OUTPUT_LOGITS"] + row * 2 + 2], "little", signed=True) for row in range(13)]
    assert actual == [((value + offset + 0x8000) & 0xFFFF) - 0x8000 for value, offset in zip(logits, bias)]


def test_6502_selects_lowest_index_for_equal_maximum_output_logit(tmp_path):
    """Stage 043 raw argmax covers all 13 logits with a declared low-index tie rule."""
    prg = tmp_path / "CP64.PRG"; labels_path = tmp_path / "cp64.lbl"
    subprocess.run([str(ASSEMBLER), "--cbm-prg", f"--labels={labels_path}", "-o", str(prg), str(ROOT / "src" / "cp64.asm")], check=True, capture_output=True, text=True)
    symbols = labels(labels_path); mpu = MPU(); image = prg.read_bytes(); load_address = int.from_bytes(image[:2], "little")
    mpu.memory[load_address : load_address + len(image) - 2] = image[2:]
    logits = [-32768, 10, 99, 32767, 4, 32767, -1, 200, 0, -99, 1, 2, 3]
    for row, value in enumerate(logits):
        mpu.memory[symbols["OUTPUT_LOGITS"] + row * 2 : symbols["OUTPUT_LOGITS"] + row * 2 + 2] = (value & 0xFFFF).to_bytes(2, "little")
    call(mpu, symbols["select_output_argmax"])
    assert mpu.memory[symbols["output_argmax_index"]] == 3
    assert int.from_bytes(mpu.memory[symbols["output_argmax_lo"] : symbols["output_argmax_lo"] + 2], "little", signed=True) == 32767


def test_6502_maps_only_original_move_token_ids_to_empty_board_cells(tmp_path):
    """A C9W46/C9W47 output ID is a cell only for declared a-i IDs 4-12."""
    vocabulary = json.loads((ROOT.parent / "crystal-9" / "releases" / "huggingface-int4-v1" / "design.json").read_text())["vocabulary"]["tokens"]
    assert vocabulary == ["<pad>", "<bos>", "<eos>", "!", "a", "b", "c", "d", "e", "f", "g", "h", "i"]
    prg = tmp_path / "CP64.PRG"; labels_path = tmp_path / "cp64.lbl"
    subprocess.run([str(ASSEMBLER), "--cbm-prg", f"--labels={labels_path}", "-o", str(prg), str(ROOT / "src" / "cp64.asm")], check=True, capture_output=True, text=True)
    symbols = labels(labels_path); mpu = MPU(); image = prg.read_bytes(); load_address = int.from_bytes(image[:2], "little")
    mpu.memory[load_address : load_address + len(image) - 2] = image[2:]
    assert {"map_output_token_to_empty_cell", "board_occupied", "computer_cell"} <= symbols.keys()

    # Declared vocabulary IDs 4..12 are a..i.  Mark a and e occupied: a
    # predicted e is rejected, while f maps to board cell five.
    mpu.memory[symbols["board_occupied"]] = (1 << 0) | (1 << 4)
    mpu.memory[symbols["output_argmax_index"]] = 8  # declared token e
    call(mpu, symbols["map_output_token_to_empty_cell"])
    assert mpu.p & mpu.CARRY
    mpu.memory[symbols["output_argmax_index"]] = 9  # declared token f
    call(mpu, symbols["map_output_token_to_empty_cell"])
    assert not (mpu.p & mpu.CARRY)
    assert mpu.memory[symbols["computer_cell"]] == 5
    assert mpu.memory[symbols["board_occupied"]] == ((1 << 0) | (1 << 4) | (1 << 5))

    # Special tokens and an out-of-vocabulary byte must never become cells.
    for token_id in (0, 1, 2, 3, 13, 255):
        mpu.memory[symbols["output_argmax_index"]] = token_id
        call(mpu, symbols["map_output_token_to_empty_cell"])
        assert mpu.p & mpu.CARRY


def test_6502_accepted_human_cell_reserves_the_same_board_bit_before_rendering(tmp_path):
    """The legal-empty check is stateful, not inferred from a PETSCII glyph."""
    prg = tmp_path / "CP64.PRG"; labels_path = tmp_path / "cp64.lbl"
    subprocess.run([str(ASSEMBLER), "--cbm-prg", f"--labels={labels_path}", "-o", str(prg), str(ROOT / "src" / "cp64.asm")], check=True, capture_output=True, text=True)
    symbols = labels(labels_path); mpu = MPU(); image = prg.read_bytes(); load_address = int.from_bytes(image[:2], "little")
    mpu.memory[load_address : load_address + len(image) - 2] = image[2:]
    mpu.memory[symbols["selected"]] = ord("i")
    mpu.memory[symbols["sequence_length"]] = 0
    call(mpu, symbols["ui_mark_accepted_human_move"])
    assert mpu.memory[symbols["board_occupied"]] == 0
    assert mpu.memory[symbols["board_occupied_hi"]] == 1


def test_6502_configures_original_output_packets_with_their_13_row_lengths(tmp_path):
    """C9W46/C9W47 are not 32-row expert packets; browser LOAD must accept them."""
    prg = tmp_path / "CP64.PRG"; labels_path = tmp_path / "cp64.lbl"
    subprocess.run([str(ASSEMBLER), "--cbm-prg", f"--labels={labels_path}", "-o", str(prg), str(ROOT / "src" / "cp64.asm")], check=True, capture_output=True, text=True)
    symbols = labels(labels_path); mpu = MPU(); image = prg.read_bytes(); load_address = int.from_bytes(image[:2], "little")
    mpu.memory[load_address : load_address + len(image) - 2] = image[2:]
    for packet_id, scale_bytes, packed_bytes in ((46, 26, 208), (47, 2, 7)):
        mpu.a = packet_id
        call(mpu, symbols["configure_expert_packet"])
        actual_scale = mpu.memory[symbols["packet_scale_lo"]] | (mpu.memory[symbols["packet_scale_hi"]] << 8)
        actual_packed = mpu.memory[symbols["packet_packed_lo"]] | (mpu.memory[symbols["packet_packed_hi"]] << 8)
        assert (actual_scale, actual_packed) == (scale_bytes, packed_bytes)


def test_interactive_pipeline_pages_output_head_then_displays_raw_bounded_argmax():
    """The browser path visibly executes both original head packets after MoE residual."""
    source = (ROOT / "src" / "cp64.asm").read_text()
    request = source[source.index("expert4_bias2_loaded:") : source.index("lda #<scale_result")]
    assert request.index("jsr add_selected_expert_residual") < request.index("jsr load_packet_checked")
    assert request.count("jsr load_packet_checked") == 2
    assert request.index("jsr project_output_head") < request.index("jsr add_output_head_bias") < request.index("jsr select_output_argmax")
    for text in ("38/44 ADD SELECTED-EXPERT RESIDUAL", "39/44 LOAD OUTPUT HEAD C9W46", "40/44 OUTPUT HEAD AFFINE", "41/44 LOAD OUTPUT BIAS C9W47", "42/44 ADD OUTPUT HEAD BIAS", "43/44 RAW NEXT-TOKEN ARGMAX", "RAW BOUNDED NEXT-TOKEN INDEX $"):
        assert text in source


def test_interactive_a_only_arms_legal_history_without_emitting_a_token():
    """The three-key slice must wait after A rather than emit a two-key output."""
    source = (ROOT / "src" / "cp64.asm").read_text()
    request = source[source.index("jsr capture_legal_history") : source.index("attended_two_key:")]
    assert "lda three_key_ready" in request
    assert "jsr ui_status_a" in request
    assert "jmp read_key" in request
    assert "await_second_key_message: .text \"A RETAINED. TYPE B TO RUN THE A->B PROOF.\"" in source


def test_interactive_pipeline_rematerializes_predicted_original_embedding_after_argmax():
    """Stage 044 turns the raw output index back into its C9W00 source vector."""
    source = (ROOT / "src" / "cp64.asm").read_text()
    request = source[source.index("output_bias_loaded:") : source.index("lda #<scale_result")]
    assert request.index("jsr select_output_argmax") < request.index("jsr load_embedding")
    assert request.index("jsr load_embedding") < request.index("jsr decode_scale") < request.index("jsr materialize_embedding")
    for text in ("44/44 LOAD PREDICTED TOKEN C9W00", "PREDICTED TOKEN EMBEDDING CHECKSUM $"):
        assert text in source


def test_interactive_pipeline_retains_e1_then_merges_after_e4():
    """The live path must not overwrite E1 before applying its router weight."""
    source = (ROOT / "src" / "cp64.asm").read_text()
    request = source[source.index("expert1_bias2_loaded:") : source.index("lda #<scale_result")]
    assert request.index("jsr add_selected_expert_second_bias") < request.index("jsr retain_expert_one_output")
    assert request.index("jsr retain_expert_one_output") < request.index("jsr project_selected_expert_first", request.index("expert4_weight1_loaded:"))
    assert request.index("expert4_bias2_loaded:") < request.index("jsr merge_selected_expert_outputs")


def test_6502_legal_history_contract_retains_a_b_c_with_length_and_position(tmp_path):
    """The earliest live three-move slice has explicit state, not an A/B branch."""
    prg = tmp_path / "CP64.PRG"; labels_path = tmp_path / "cp64.lbl"
    subprocess.run([str(ASSEMBLER), "--cbm-prg", f"--labels={labels_path}", "-o", str(prg), str(ROOT / "src" / "cp64.asm")], check=True, capture_output=True, text=True)
    symbols = labels(labels_path)
    assert {"capture_legal_history", "sequence_length", "sequence_position"} <= symbols.keys()
    mpu = MPU(); image = prg.read_bytes(); load_address = int.from_bytes(image[:2], "little")
    mpu.memory[load_address : load_address + len(image) - 2] = image[2:]
    for position, token in enumerate(b"abc"):
        mpu.memory[symbols["selected"]] = token
        for lane in range(64):
            mpu.memory[symbols["KEY_VECTOR"] + lane] = (position * 64 + lane) & 0xff
            mpu.memory[symbols["VALUE_VECTOR"] + lane] = (0xc0 + position * 64 + lane) & 0xff
        call(mpu, symbols["capture_legal_history"])
        assert mpu.memory[symbols["sequence_length"]] == position + 1
        assert mpu.memory[symbols["sequence_position"]] == position
    assert list(mpu.memory[symbols["KEY_HISTORY"] : symbols["KEY_HISTORY"] + 192]) == list(range(192))
    assert list(mpu.memory[symbols["VALUE_HISTORY"] : symbols["VALUE_HISTORY"] + 192]) == [((0xc0 + index) & 0xff) for index in range(192)]


def test_6502_graphical_history_ui_marks_accepted_moves_and_real_progress(tmp_path):
    """Stage 047's PETSCII UI is direct screen memory, not a text-only claim."""
    prg = tmp_path / "CP64.PRG"; labels_path = tmp_path / "cp64.lbl"
    subprocess.run([str(ASSEMBLER), "--cbm-prg", f"--labels={labels_path}", "-o", str(prg), str(ROOT / "src" / "cp64.asm")], check=True, capture_output=True, text=True)
    symbols = labels(labels_path)
    assert {"draw_history_ui", "ui_mark_accepted_human_move", "show_real_progress", "sum_history_bytes"} <= symbols.keys()
    mpu = MPU(); image = prg.read_bytes(); load_address = int.from_bytes(image[:2], "little")
    mpu.memory[load_address : load_address + len(image) - 2] = image[2:]

    # The loading/title stream may have populated the screen before the direct
    # dashboard starts. It must be cleared, then replaced with fixed panel text.
    mpu.memory[0x0400 + 207] = ord("X")
    assert {"ui_clear_dashboard_screen", "ui_draw_static_dashboard"} <= symbols.keys()
    call(mpu, symbols["ui_clear_dashboard_screen"])
    call(mpu, symbols["ui_draw_static_dashboard"])
    assert mpu.memory[0x0400 + 207] == 0x20
    call(mpu, symbols["draw_history_ui"])
    assert [mpu.memory[0x0400 + offset] for offset in (209, 215, 223, 289, 295, 303, 369, 375, 383)] == [0x2e] * 9
    assert bytes(mpu.memory[0x0400 + 2 : 0x0400 + 16]) == bytes(ch - 64 if 65 <= ch <= 90 else ch for ch in b"CP64 CRYSTAL-9")
    assert mpu.memory[0x0400 + 446] == 0x40  # graphical progress bar starts empty

    for length, token, expected_offset, expected_code, expected_color in ((0, ord("a"), 209, 24, 2), (1, ord("b"), 215, 15, 6), (2, ord("c"), 223, 24, 2)):
        mpu.memory[symbols["sequence_length"]] = length
        mpu.memory[symbols["selected"]] = token
        call(mpu, symbols["ui_mark_accepted_human_move"])
        assert mpu.memory[0x0400 + expected_offset] == expected_code
        assert mpu.memory[0xd800 + expected_offset] == expected_color
    mpu.a = 7
    call(mpu, symbols["show_real_progress"])
    # Seven real work boundaries own the whole 28-cell meter: completion must
    # visibly reach 100%, not leave a 7/28 partial bar at the retain boundary.
    assert [mpu.memory[0x0400 + offset] for offset in range(446, 474)] == [0xa0] * 28

    for index in range(192):
        mpu.memory[symbols["KEY_HISTORY"] + index] = index
        mpu.memory[symbols["VALUE_HISTORY"] + index] = (0xc0 + index) & 0xff
    call(mpu, symbols["sum_history_bytes"])
    assert (mpu.memory[symbols["history_key_sumlo"]] | (mpu.memory[symbols["history_key_sumhi"]] << 8)) == sum(range(192)) & 0xffff
    assert (mpu.memory[symbols["history_value_sumlo"]] | (mpu.memory[symbols["history_value_sumhi"]] << 8)) == sum((0xc0 + index) & 0xff for index in range(192)) & 0xffff


def test_6502_dashboard_status_and_diagnostics_are_fixed_colored_screen_writes(tmp_path):
    """Stage 048 must not scroll the Stage 047 dashboard through CHROUT output."""
    prg = tmp_path / "CP64.PRG"; labels_path = tmp_path / "cp64.lbl"
    subprocess.run([str(ASSEMBLER), "--cbm-prg", f"--labels={labels_path}", "-o", str(prg), str(ROOT / "src" / "cp64.asm")], check=True, capture_output=True, text=True)
    symbols = labels(labels_path)
    assert {"draw_history_ui", "ui_status_a", "ui_status_b", "ui_status_complete", "ui_show_history_diagnostics"} <= symbols.keys()
    mpu = MPU(); image = prg.read_bytes(); load_address = int.from_bytes(image[:2], "little")
    mpu.memory[load_address : load_address + len(image) - 2] = image[2:]
    call(mpu, symbols["draw_history_ui"])
    dashboard = list(mpu.memory[0x0400 + 192 : 0x0400 + 640])
    for routine, text in (("ui_status_a", b"A RETAINED: TYPE B"), ("ui_status_b", b"A,B RETAINED: TYPE C")):
        mpu.memory[0x00d1] = 24  # KERNAL cursor row sentinel: direct UI must not move it.
        call(mpu, symbols[routine])
        assert mpu.memory[0x00d1] == 24
        assert bytes(mpu.memory[0x0400 + 600 : 0x0400 + 600 + len(text)]) == bytes(ch - 64 if 65 <= ch <= 90 else ch for ch in text)
        assert list(mpu.memory[0x0400 + 192 : 0x0400 + 560]) == dashboard[:368]
    for index in range(192):
        mpu.memory[symbols["KEY_HISTORY"] + index] = index
        mpu.memory[symbols["VALUE_HISTORY"] + index] = (0xc0 + index) & 0xff
    call(mpu, symbols["sum_history_bytes"])
    call(mpu, symbols["ui_status_complete"])
    call(mpu, symbols["ui_show_history_diagnostics"])
    screen = lambda text: bytes(ch - 64 if 65 <= ch <= 90 else ch for ch in text)
    complete = screen(b"A,B,C RETAINED: COMPUTER MOVE PENDING")
    diagnostic = screen(b"LENGTH $03 KEY SUM $47A0 VALUE SUM $57A0")
    assert bytes(mpu.memory[0x0400 + 600 : 0x0400 + 600 + len(complete)]) == complete
    assert bytes(mpu.memory[0x0400 + 640 : 0x0400 + 640 + len(diagnostic)]) == diagnostic
    for offset in range(600, 680):
        assert mpu.memory[0xd800 + offset] == 0x0d


def test_6502_human_marks_draw_before_model_work_as_alternating_red_x_blue_o(tmp_path):
    """A legal input must visibly become a game mark before any pageable work."""
    prg = tmp_path / "CP64.PRG"; labels_path = tmp_path / "cp64.lbl"
    subprocess.run([str(ASSEMBLER), "--cbm-prg", f"--labels={labels_path}", "-o", str(prg), str(ROOT / "src" / "cp64.asm")], check=True, capture_output=True, text=True)
    symbols = labels(labels_path)
    assert {"ui_mark_accepted_human_move", "sequence_length"} <= symbols.keys()
    source = (ROOT / "src" / "cp64.asm").read_text()
    accepted_path = source[source.index("accepted_key:") : source.index("embedding_reloaded:")]
    assert accepted_path.index("jsr ui_mark_accepted_human_move") < accepted_path.index("jsr ui_status_thinking") < accepted_path.index("jsr load_embedding")
    mpu = MPU(); image = prg.read_bytes(); load_address = int.from_bytes(image[:2], "little")
    mpu.memory[load_address : load_address + len(image) - 2] = image[2:]
    call(mpu, symbols["draw_history_ui"])
    for length, token, offset, code, color in (
        (0, ord("a"), 209, 24, 2),  # X, red
        (1, ord("b"), 215, 15, 6),  # O, blue
        (2, ord("c"), 223, 24, 2),  # X, red
    ):
        mpu.memory[symbols["sequence_length"]] = length
        mpu.memory[symbols["selected"]] = token
        call(mpu, symbols["ui_mark_accepted_human_move"])
        assert mpu.memory[0x0400 + offset] == code
        assert mpu.memory[0xd800 + offset] == color


def test_6502_dashboard_explicitly_sets_black_vic_background_for_blue_o(tmp_path):
    """The fixed dashboard must not inherit a browser emulator's blue background."""
    prg = tmp_path / "CP64.PRG"; labels_path = tmp_path / "cp64.lbl"
    subprocess.run([str(ASSEMBLER), "--cbm-prg", f"--labels={labels_path}", "-o", str(prg), str(ROOT / "src" / "cp64.asm")], check=True, capture_output=True, text=True)
    symbols = labels(labels_path)
    assert "ui_set_dashboard_palette" in symbols
    mpu = MPU(); image = prg.read_bytes(); load_address = int.from_bytes(image[:2], "little")
    mpu.memory[load_address : load_address + len(image) - 2] = image[2:]
    mpu.memory[0xd020] = 0x0e
    mpu.memory[0xd021] = 0x06
    call(mpu, symbols["ui_set_dashboard_palette"])
    assert mpu.memory[0xd021] == 0x00
    assert mpu.memory[0xd020] == 0x0d


def test_6502_hex_diagnostic_nibbles_are_c64_screen_codes(tmp_path):
    """A-F must use screen codes 1-6, never their ASCII values 65-70."""
    prg = tmp_path / "CP64.PRG"; labels_path = tmp_path / "cp64.lbl"
    subprocess.run([str(ASSEMBLER), "--cbm-prg", f"--labels={labels_path}", "-o", str(prg), str(ROOT / "src" / "cp64.asm")], check=True, capture_output=True, text=True)
    symbols = labels(labels_path)
    mpu = MPU(); image = prg.read_bytes(); load_address = int.from_bytes(image[:2], "little")
    mpu.memory[load_address : load_address + len(image) - 2] = image[2:]
    mpu.memory[symbols["pointer"]] = 0x80; mpu.memory[symbols["pointer"] + 1] = 0x06
    call(mpu, symbols["ui_set_color_pointer"])
    for nibble, expected in enumerate((48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 1, 2, 3, 4, 5, 6)):
        mpu.a = nibble
        call(mpu, symbols["ui_hexnibble"])
        assert mpu.memory[0x0680 + nibble] == expected
