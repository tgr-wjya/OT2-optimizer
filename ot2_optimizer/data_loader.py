from __future__ import annotations

import csv
import json
import re
from pathlib import Path

from .models import (
    CATEGORY_FILES,
    CATEGORY_SLOT,
    EQUIPMENT_CATEGORIES,
    AvailabilitySource,
    EquipmentItem,
    STAT_KEYS,
)
from .rules import classify_accessory, classify_effects


BONUS_MAP = {
    "max. hp": "hp",
    "max hp": "hp",
    "max. sp": "sp",
    "max sp": "sp",
    "phys. atk.": "phys_atk",
    "phys atk.": "phys_atk",
    "elem. atk.": "elem_atk",
    "elem atk.": "elem_atk",
    "phys. def.": "phys_def",
    "phys def.": "phys_def",
    "elem. def.": "elem_def",
    "elem def.": "elem_def",
    "speed": "speed",
    "accuracy": "accuracy",
    "evasion": "evasion",
    "critical": "critical",
}

SOURCE_KIND_ALIASES = {
    "store": "store",
    "chest": "chest",
    "quest": "quest",
    "npc": "npc",
    "boss": "drop",
    "mini-boss": "drop",
}


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def empty_stats() -> dict[str, int]:
    return {key: 0 for key in STAT_KEYS}


def normalize_name(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("(*)", "")).strip().lower()


def parse_price(value: str | None) -> int | None:
    if not value:
        return None
    if "$" not in value:
        return None
    cleaned = value.replace("$", "").replace(",", "").strip()
    if not cleaned.isdigit():
        return None
    return int(cleaned)


def load_store_prices(root: Path | None = None) -> dict[str, int]:
    root = root or project_root()
    store_csv = root / "Octopath Traveler 2 Resource - Store.csv"
    prices: dict[str, int] = {}
    if not store_csv.exists():
        return prices

    with store_csv.open(newline="", encoding="utf-8") as handle:
        for row in csv.reader(handle):
            for index, cell in enumerate(row[:-1]):
                price = parse_price(row[index + 1])
                name = normalize_name(cell)
                if not name or price is None:
                    continue
                current = prices.get(name)
                if current is None or price < current:
                    prices[name] = price
    return prices


def parse_bonus(raw: str | None) -> tuple[str, int] | None:
    if not raw:
        return None
    match = re.match(r"^(.+?)\s*([+-]\d+)$", raw.strip())
    if not match:
        return None
    label = re.sub(r"\s+", " ", match.group(1).strip().lower())
    stat = BONUS_MAP.get(label)
    if not stat:
        return None
    return stat, int(match.group(2))


def parse_sources(availability: str | None) -> list[AvailabilitySource]:
    if not availability:
        return []
    sources: list[AvailabilitySource] = []
    for line in availability.splitlines():
        kind_match = re.match(r"([A-Za-z-]+)(?:<[^>]+>)?\s*", line.strip())
        kind = SOURCE_KIND_ALIASES.get(kind_match.group(1).lower(), "other") if kind_match else "other"
        for location in re.findall(r"\[([^\]]+)\]", line):
            location = location.replace("(*)", "").strip()
            sources.append(AvailabilitySource(kind=kind, location=location, raw=line.strip()))
    return sources


def item_stats(category: str, raw: dict) -> dict[str, int]:
    slot = CATEGORY_SLOT[category]
    stats = empty_stats()
    phys = raw.get("physAtk") or 0
    elem = raw.get("elemAtk") or 0

    if slot == "weapon":
        stats["phys_atk"] += phys
        stats["elem_atk"] += elem
    elif slot in {"shield", "headgear", "body_armor"}:
        stats["phys_def"] += phys
        stats["elem_def"] += elem

    for key in ("bonus1", "bonus2"):
        parsed = parse_bonus(raw.get(key))
        if parsed:
            stat, value = parsed
            stats[stat] += value

    return stats


def load_equipment(root: Path | None = None) -> list[EquipmentItem]:
    root = root or project_root()
    prices = load_store_prices(root)
    items: list[EquipmentItem] = []

    for category in EQUIPMENT_CATEGORIES:
        with (root / "categories" / CATEGORY_FILES[category]).open(encoding="utf-8") as handle:
            raw_items = json.load(handle)
        for raw in raw_items:
            name = raw["name"]
            effect_text = raw.get("effect")
            effect_tags = classify_effects(effect_text)
            accessory_tier, accessory_tags = classify_accessory(name, effect_text, item_stats(category, raw))
            items.append(
                EquipmentItem(
                    name=name,
                    category=category,
                    slot=CATEGORY_SLOT[category],
                    stats=item_stats(category, raw),
                    effect_text=effect_text,
                    effect_tags=effect_tags,
                    accessory_tags=accessory_tags,
                    accessory_tier=accessory_tier,
                    max_ownable=raw.get("maxOwnable") or 99,
                    availability=raw.get("availability"),
                    sources=parse_sources(raw.get("availability")),
                    price=prices.get(normalize_name(name)),
                )
            )
    return items


def item_index(items: list[EquipmentItem]) -> dict[str, EquipmentItem]:
    index: dict[str, EquipmentItem] = {}
    for item in items:
        index[normalize_name(item.name)] = item
        index[f"{normalize_name(item.category)}:{normalize_name(item.name)}"] = item
    return index
