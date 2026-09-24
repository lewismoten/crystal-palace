import importlib.util
from pathlib import Path


def load_exporter():
    path = Path(__file__).parents[1] / "scripts" / "export_crystal9_policy.py"
    spec = importlib.util.spec_from_file_location("export_crystal9_policy", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_board_index_encodes_empty_x_and_o_ternary_cells():
    exporter = load_exporter()
    assert exporter.board_index(".........") == 0
    assert exporter.board_index("X........") == 1
    assert exporter.board_index("O........") == 2
    assert exporter.board_index("XO.......") == 7


def test_select_policy_rejects_order_dependent_board_predictions():
    exporter = load_exporter()
    assert exporter.select_policy([(3, 4), (3, 4)]) == 4
    assert exporter.select_policy([(3, 4), (3, 8)]) == exporter.AMBIGUOUS_MOVE
