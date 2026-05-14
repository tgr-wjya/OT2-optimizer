from __future__ import annotations

import csv
from pathlib import Path

from .data_loader import project_root


CHARACTER_ALIASES = {
    "Osvald": "Osvald V. Vanstein",
    "Temenos": "Temenos Mistral",
    "Throné": "Throné Anguis",
    "Throne": "Throné Anguis",
    "Ochette": "Ochette",
    "Castti": "Castti Florenz",
    "Partitio": "Partitio Yellowil",
    "Agnea": "Agnea Bristarni",
    "Hikari": "Hikari",
}

STAT_LABELS = {
    "Max. HP": "hp",
    "Max. SP": "sp",
    "Phys. Atk.": "phys_atk",
    "Elem. Atk.": "elem_atk",
    "Phys. Def.": "phys_def",
    "Elem. Def.": "elem_def",
    "Accuracy": "accuracy",
    "Speed": "speed",
    "Critical": "critical",
    "Evasion": "evasion",
}


def parse_int(value: str) -> int | None:
    cleaned = value.replace(",", "").strip()
    if not cleaned:
        return None
    try:
        return int(cleaned)
    except ValueError:
        return None


def parse_float(value: str) -> float | None:
    cleaned = value.strip()
    if not cleaned:
        return None
    return float(cleaned)


def stats_csv_rows(root: Path | None = None) -> list[list[str]]:
    root = root or project_root()
    with (root / "data/Octopath_Traveler2_Resource_Stats.csv").open(
        newline="",
        encoding="utf-8",
    ) as handle:
        return list(csv.reader(handle))


def load_level_multipliers(root: Path | None = None) -> dict[int, float]:
    rows = stats_csv_rows(root)
    multipliers: dict[int, float] = {}
    start = next(index for index, row in enumerate(rows) if row and row[0] == "Level Multiplier")
    for row in rows[start + 2 : start + 12]:
        for level_col in range(1, len(row), 3):
            if level_col + 1 >= len(row):
                continue
            level = parse_int(row[level_col])
            multiplier = parse_float(row[level_col + 1])
            if level is not None and multiplier is not None:
                multipliers[level] = multiplier
    return multipliers


def load_character_base_stats(root: Path | None = None) -> dict[str, dict[int, dict[str, int]]]:
    rows = stats_csv_rows(root)
    reverse_alias = {full: short for short, full in CHARACTER_ALIASES.items() if short != "Throne"}
    result: dict[str, dict[int, dict[str, int]]] = {}

    for index, row in enumerate(rows):
        if not row or row[0] not in reverse_alias:
            continue
        character = reverse_alias[row[0]]
        result[character] = {}
        header_rows = [index + 1, index + 12, index + 23]

        for header_row_index in header_rows:
            if header_row_index >= len(rows):
                continue
            levels = {
                column: parse_int(value)
                for column, value in enumerate(rows[header_row_index])
                if parse_int(value) is not None
            }
            for offset in range(1, 11):
                stat_row_index = header_row_index + offset
                if stat_row_index >= len(rows):
                    continue
                stat_row = rows[stat_row_index]
                if len(stat_row) < 2:
                    continue
                stat_key = STAT_LABELS.get(stat_row[1].strip())
                if not stat_key:
                    continue
                for column, level in levels.items():
                    value = parse_int(stat_row[column]) if column < len(stat_row) else None
                    if value is None:
                        continue
                    result[character].setdefault(level, {})[stat_key] = value

    return result


def base_stats_for(character: str, level: int, root: Path | None = None) -> dict[str, int]:
    stats = load_character_base_stats(root)
    return stats[character][level]
