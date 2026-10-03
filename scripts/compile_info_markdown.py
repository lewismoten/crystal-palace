#!/usr/bin/env python3
"""Compile the bounded Crystal Palace archive Markdown viewer data for 6502."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).parents[1]
SOURCE = ROOT / "assets" / "crystal-palace-screen-states" / "ARCHIVE.md"
OUTPUT = ROOT / "src" / "info_markdown.inc"
WIDTH = 29

COLOUR = {"body": 1, "header": 7, "bold": 10, "italic": 3, "quote": 4, "list": 13, "table": 14}


def screen_code(character: str) -> int:
    """Map archive text to the supplied custom charset's C64 screen codes."""
    if "a" <= character <= "z":
        character = character.upper()
    if "A" <= character <= "Z":
        return ord(character) - ord("A") + 1
    if character == " ":
        return 0
    # These are verified against the supplied charset bitmap, rather than the
    # normal PETSCII punctuation positions.  In particular, 45/46 are parens,
    # while the archive's hyphen and period are 42/39.
    return {
        "?": 37, ":": 38, ".": 39, ",": 40, "/": 41, "-": 42,
        "!": 43, "(": 45, ")": 46, '"': 47, "“": 47, "”": 47,
        ";": 38, "|": 0,
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
                current.append((" ", current[-1][1]))
                current.extend(word[:available])
                word = word[available:]
                result.append(current)
                current = []
            else:
                result.append(word[:width])
                word = word[width:]

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
    return line[:WIDTH]


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
            # Keep the whole table to the C64 text viewport.
            while sum(widths) + (len(widths) - 1) * 3 > WIDTH:
                widest = max(range(len(widths)), key=widths.__getitem__)
                widths[widest] -= 1
            lines.append(table_row(header, widths))
            lines.append([(char, "table") for char in "-" * min(WIDTH, sum(widths) + (len(widths) - 1) * 3)])
            lines.extend(table_row(row, widths) for row in rows)
            continue
        if line.startswith("# "):
            lines.extend(wrap(inline(line[2:], "header")))
        elif line.startswith("- "):
            lines.extend(wrap([(".", "list"), (" ", "list"), *inline(line[2:], "list")]))
        elif line.startswith("> "):
            lines.extend(wrap([(" ", "quote"), (" ", "quote"), *inline(line[2:], "quote")]))
        else:
            lines.extend(wrap(inline(line)))
        index += 1
    return lines


def compile_data() -> tuple[bytes, bytes, int]:
    lines = parse_markdown(SOURCE.read_text())
    chars = bytearray()
    colours = bytearray()
    for line in lines:
        line = line[:WIDTH]
        chars.extend(screen_code(char) for char, _ in line)
        chars.extend(bytes(WIDTH - len(line)))
        colours.extend(COLOUR[style] for _, style in line)
        colours.extend(bytes((COLOUR["body"],)) * (WIDTH - len(line)))
    return bytes(chars), bytes(colours), len(lines)


def asm_bytes(name: str, data: bytes) -> str:
    rows = [f"{name}:"]
    for offset in range(0, len(data), 30):
        rows.append("    .byte " + ", ".join(str(value) for value in data[offset : offset + 30]))
    return "\n".join(rows)


def main() -> None:
    chars, colours, count = compile_data()
    content = "\n".join((
        "; Generated from assets/crystal-palace-screen-states/ARCHIVE.md; do not hand-edit.",
        f"INFO_LINE_COUNT = {count}",
        f"INFO_LINE_WIDTH = {WIDTH}",
        asm_bytes("info_markdown_chars", chars),
        asm_bytes("info_markdown_colours", colours),
        "",
    ))
    OUTPUT.write_text(content)
    print(f"{OUTPUT.relative_to(ROOT)}: {count} lines × {WIDTH} columns")


if __name__ == "__main__":
    main()
