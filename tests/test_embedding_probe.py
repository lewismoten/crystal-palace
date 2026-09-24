import importlib.util
from pathlib import Path


def load_probe():
    path = Path(__file__).parents[1] / "scripts" / "embedding_probe.py"
    spec = importlib.util.spec_from_file_location("embedding_probe", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_unpack_int4_is_low_nibble_first_and_signed():
    probe = load_probe()
    assert probe.unpack_int4(bytes((0x78, 0xf0))) == [-8, 7, 0, -1]


def test_weighted_checksum_uses_one_based_positions():
    probe = load_probe()
    assert probe.weighted_checksum([1, -2, 3]) == 6


def test_fp16_scale_and_int4_code_materialize_q8_8_activation():
    probe = load_probe()
    assert probe.fp16le_to_q8_8(bytes.fromhex("cc3f")) == 499
    assert probe.fp16le_to_q8_8(bytes.fromhex("3c40")) == 542
    assert probe.scale_int4_code_q8_8(-4, 499) == -285


def test_materialized_token_embedding_a_matches_fixed_point_reference():
    probe = load_probe()
    packet = Path(__file__).parents[1] / "build" / "layers" / "C9W00.PRG"

    values = probe.materialized_embedding_row(packet, "a")

    assert values == [
        71, -71, -285, -71, 71, 0, 71, 428,
        0, 0, -71, -499, 71, -214, 0, -285,
        -143, -71, -285, 71, 0, -71, 428, -71,
        143, 0, -71, 0, -214, 214, 285, 285,
    ]
    assert probe.weighted_checksum(values) & 0xFFFF == 0x20AD
