import importlib.util
from pathlib import Path


def load_builder():
    path = Path(__file__).parents[1] / "scripts" / "make_d64.py"
    spec = importlib.util.spec_from_file_location("make_d64", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_interleaved_allocation_uses_drive_rotation_gap_on_first_track():
    builder = load_builder()

    sectors = builder.interleaved_sectors(1, 6, interleave=10)

    assert sectors == [0, 10, 20, 9, 19, 8]
