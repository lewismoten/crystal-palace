#!/usr/bin/env python3
"""Compile the bounded Crystal Palace archive Markdown viewer data for 6502."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).parents[1]
SOURCE = ROOT / "assets" / "archive" / "archive.md"
OUTPUT = ROOT / "src" / "info_markdown.inc"
ARCHIVE_OUTPUT = ROOT / "build" / "ARCHIVE.PRG"
WIDTH = 29
ARCHIVE_LOAD_ADDRESS = 0xC000
ARCHIVE_HEADER_SIZE = 8
ARCHIVE_VERSION = 1

COLOR = {"body": 1, "header": 7, "bold": 10, "italic": 3, "quote": 4, "list": 13, "table": 14}


def screen_code(character: str) -> int:
    """Map archive text to the supplied custom charset's C64 screen codes."""
    if "a" <= character <= "z":
        character = character.upper()
    if "A" <= character <= "Z":
        return ord(character) - ord("A") + 1
    if character == " ":
        return 0
    if "0" <= character <= "9":
        return ord(character) - ord("0") + 27
    # These are verified against the supplied charset bitmap, rather than the
    # normal PETSCII punctuation positions.  Slot 55 is the only readable
    # vertical table separator; slot 47 is the supplied straight quote.
    return {
        "?": 37, ":": 38, ".": 39, ",": 40, "/": 41, "-": 42,
        "!": 43, "(": 45, ")": 46, '"': 47, "“": 47, "”": 47,
        ";": 40, "|": 55,
    }.get(character, 0)


def inline(text: str, base: str = "body") -> list[tuple[str, str]]:
    parts: list[tuple[str, str]] = []
    index = 0
    active = base
    while index < len(text):
        if text.startswith("**", index):
            active = "bold" if active != "bold" else base
            index += 2
        elif text[index] == "*":
            active = "italic" if active != "italic" else base
            index += 1
        else:
            parts.append((text[index], active))
            index += 1
    return parts


def wrap(parts: list[tuple[str, str]], width: int = WIDTH) -> list[list[tuple[str, str]]]:
    result: list[list[tuple[str, str]]] = []
    current: list[tuple[str, str]] = []
    word: list[tuple[str, str]] = []
    def append_word() -> None:
        """Append one styled word, splitting it only when the viewport requires."""
        nonlocal current, word
        while word:
            separator = 1 if current else 0
            available = width - len(current) - separator
            if len(word) <= width and len(word) > available and current:
                result.append(current)
                current = word
                word = []
            elif len(word) <= available:
                if current:
                    current.append((" ", current[-1][1]))
                current.extend(word)
                word = []
            elif current:
                # An oversized compound word gets a fresh row so a hyphen can
                # become a natural break instead of leaving a clipped prefix.
                if len(word) > width and len(current) > 2:
                    result.append(current)
                    current = []
                else:
                    current.append((" ", current[-1][1]))
                    split_at = next(
                        (offset + 1 for offset in range(available - 1, 0, -1) if word[offset][0] == "-"),
                        available,
                    )
                    current.extend(word[:split_at])
                    word = word[split_at:]
                    result.append(current)
                    current = []
            else:
                split_at = next(
                    (offset + 1 for offset in range(width - 1, 0, -1) if word[offset][0] == "-"),
                    width,
                )
                result.append(word[:split_at])
                word = word[split_at:]

    for pair in parts + [(" ", "body")]:
        if pair[0].isspace():
            if word:
                append_word()
            if pair[0] == "\n" and current:
                result.append(current)
                current = []
        else:
            word.append(pair)
    if current:
        result.append(current)
    return result or [[]]


def table_row(cells: list[str], widths: list[int]) -> list[tuple[str, str]]:
    line: list[tuple[str, str]] = []
    for index, cell in enumerate(cells):
        if index:
            line.append((" ", "table")); line.append(("|", "table")); line.append((" ", "table"))
        for char in cell.ljust(widths[index])[:widths[index]]:
            line.append((char, "table"))
    return line


def table_rows(cells: list[str], widths: list[int]) -> list[list[tuple[str, str]]]:
    """Wrap every table cell and retain its continuation rows."""
    wrapped = [wrap(inline(cell, "table"), width) for cell, width in zip(cells, widths)]
    return [
        table_row(
            ["".join(char for char, _ in column[row]) if row < len(column) else "" for column in wrapped],
            widths,
        )
        for row in range(max(map(len, wrapped)))
    ]


def parse_markdown(text: str) -> list[list[tuple[str, str]]]:
    lines: list[list[tuple[str, str]]] = []
    raw = [line.rstrip() for line in text.splitlines()]
    index = 0
    while index < len(raw):
        line = raw[index]
        if not line:
            index += 1
            continue
        if line.startswith("|") and index + 1 < len(raw) and raw[index + 1].startswith("|"):
            header = [cell.strip() for cell in line.strip("|").split("|")]
            index += 2  # skip Markdown separator
            rows = []
            while index < len(raw) and raw[index].startswith("|"):
                rows.append([cell.strip() for cell in raw[index].strip("|").split("|")])
                index += 1
            widths = [max(len(row[column]) for row in [header, *rows]) for column in range(len(header))]
            if len(widths) == 2:
                # Table identifiers stay whole when possible; the descriptive
                # column consumes the remaining viewport cells and wraps.
                widths[1] = WIDTH - 3 - widths[0]
            else:
                while sum(widths) + (len(widths) - 1) * 3 > WIDTH:
                    widest = max(range(len(widths)), key=lambda column: (widths[column], column))
                    widths[widest] -= 1
            lines.append(table_row(header, widths))
            lines.append(table_row(["-" * width for width in widths], widths))
            for row in rows:
                lines.extend(table_rows(row, widths))
            continue
        if line.startswith("# "):
            lines.extend(wrap(inline(line[2:], "header")))
        elif line.startswith("- "):
            lines.extend(wrap([("-", "list"), (" ", "list"), *inline(line[2:], "list")]))
        elif line.startswith("> "):
            lines.extend(wrap([(" ", "quote"), (" ", "quote"), *inline(line[2:], "quote")]))
        else:
            lines.extend(wrap(inline(line)))
        index += 1
    return lines


def compile_data() -> tuple[bytes, bytes, int]:
    lines = parse_markdown(SOURCE.read_text())
    chars = bytearray()
    colors = bytearray()
    for line in lines:
        line = line[:WIDTH]
        chars.extend(screen_code(char) for char, _ in line)
        chars.extend(bytes(WIDTH - len(line)))
        colors.extend(COLOR[style] for _, style in line)
        colors.extend(bytes((COLOR["body"],)) * (WIDTH - len(line)))
    return bytes(chars), bytes(colors), len(lines)


def archive_payload() -> bytes:
    """Return the versioned disk PRG consumed only when INFO is opened."""
    chars, colors, count = compile_data()
    header = b"ARCV" + bytes((ARCHIVE_VERSION,)) + count.to_bytes(2, "little") + bytes((WIDTH,))
    return ARCHIVE_LOAD_ADDRESS.to_bytes(2, "little") + header + chars + colors


def main() -> None:
    chars, colors, count = compile_data()
    content = "\n".join((
        "; Generated from assets/archive/archive.md; do not hand-edit.",
        f"INFO_LINE_COUNT = {count}",
        f"INFO_LINE_WIDTH = {WIDTH}",
        f"ARCHIVE_LOAD_ADDRESS = ${ARCHIVE_LOAD_ADDRESS:04x}",
        f"ARCHIVE_HEADER_SIZE = {ARCHIVE_HEADER_SIZE}",
        f"ARCHIVE_PAYLOAD_BYTES = {len(chars) + len(colors)}",
        f"ARCHIVE_COPY_FULL_PAGES = {len(chars) // 256}",
        f"ARCHIVE_COPY_TAIL = {len(chars) % 256}",
        "info_markdown_chars = $a600",
        "info_markdown_colors = $b800",
        "",
    ))
    OUTPUT.write_text(content)
    ARCHIVE_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    ARCHIVE_OUTPUT.write_bytes(archive_payload())
    print(f"{OUTPUT.relative_to(ROOT)} + {ARCHIVE_OUTPUT.relative_to(ROOT)}: {count} lines × {WIDTH} columns")


if __name__ == "__main__":
    main()
