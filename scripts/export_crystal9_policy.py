#!/usr/bin/env python3
"""Export a C64-sized distilled Crystal-9 policy table for board experiments.

The shipped Crystal-9 INT4 tensor artifact is 46 KiB before C64 program RAM.
This exporter is deliberately explicit about the boundary: it samples the
source artifact and writes a policy table, not its original neural weights.
"""
from __future__ import annotations

from pathlib import Path

AMBIGUOUS_MOVE = 0xFF
CELL_VALUE = {".": 0, "X": 1, "O": 2}


def board_index(board: str) -> int:
    """Encode a nine-cell board as a little-endian base-3 integer."""
    if len(board) != 9 or set(board) - set(CELL_VALUE):
        raise ValueError("board must contain exactly nine ., X, or O cells")
    value = 0
    factor = 1
    for cell in board:
        value += CELL_VALUE[cell] * factor
        factor *= 3
    return value


def select_policy(predictions: list[tuple[int, int]]) -> int:
    """Return a unique source-model move or a sentinel for order dependence."""
    moves = {move for _, move in predictions}
    return moves.pop() if len(moves) == 1 else AMBIGUOUS_MOVE


def main() -> None:
    import argparse
    import json
    import sys

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--crystal-root", type=Path, default=Path.home() / "crystal-9")
    parser.add_argument("--output", type=Path, default=Path("src/crystal9_board_policy.inc"))
    args = parser.parse_args()

    release = args.crystal_root / "releases" / "huggingface-int4-v1"
    sys.path[:0] = [str(release), str(args.crystal_root)]
    import torch
    from crystal9 import GameTokenizer
    from packed_int4 import PackedInt4Policy

    tokenizer = GameTokenizer.from_design_file(release / "design.json")
    policy = PackedInt4Policy.load(release / "artifacts" / "crystal-9-int4-group2-packed-fp16-scales-v1.pt").eval()
    symbols = "abcdefghi"
    histories = [""]
    live_odd = []
    while histories:
        history = histories.pop()
        if len(history) % 2:
            live_odd.append(history)
        for symbol in symbols:
            candidate = history + symbol
            if policy.predict(candidate, tokenizer) != "!":
                histories.append(candidate)

    grouped: dict[int, list[tuple[int, int]]] = {}
    with torch.no_grad():
        for start in range(0, len(live_odd), 512):
            batch = live_odd[start : start + 512]
            encoded = [tokenizer.encode_history(history) + [0] * (9 - len(history)) for history in batch]
            ids = torch.tensor(encoded)
            moves = policy(ids).argmax(dim=-1).tolist()
            for history, token_id in zip(batch, moves):
                move = symbols.index(tokenizer.decode_id(token_id))
                cells = ["."] * 9
                for turn, symbol in enumerate(history):
                    cells[symbols.index(symbol)] = "X" if turn % 2 == 0 else "O"
                grouped.setdefault(board_index("".join(cells)), []).append((len(history), move))

    table = [AMBIGUOUS_MOVE] * (3**9)
    for index, predictions in grouped.items():
        table[index] = select_policy(predictions)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("; generated from Crystal-9 packed INT4 artifact; see export script\ncrystal9_policy:\n    .byte " + ", ".join(f"${value:02x}" for value in table) + "\n")
    print(json.dumps({"source_histories": len(live_odd), "board_states": len(grouped), "ambiguous_boards": sum(value == AMBIGUOUS_MOVE for value in table if value == AMBIGUOUS_MOVE), "bytes": len(table)}, sort_keys=True))


if __name__ == "__main__":
    main()
