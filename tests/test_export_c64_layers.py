import importlib.util
from pathlib import Path


def load_exporter():
    path = Path(__file__).parents[1] / "scripts" / "export_c64_layers.py"
    spec = importlib.util.spec_from_file_location("export_c64_layers", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_pack_layer_preserves_scale_and_int4_payload_bytes():
    exporter = load_exporter()

    packet = exporter.pack_layer(7, b"\x00\x3c", b"\x21\xfe")

    assert packet[:4] == b"C9W1"
    assert packet[4] == 7
    assert packet[5:9] == bytes((2, 0, 2, 0))
    assert packet[9:] == b"\x00\x3c\x21\xfe"
