from __future__ import annotations

from collections import defaultdict

from .models import CLASS_WEAPONS, EquipmentItem


def location_matches(source_location: str | None, allowed_locations: list[str]) -> bool:
    if not source_location:
        return False
    source = source_location.lower()
    for allowed in allowed_locations:
        target = allowed.lower()
        if source == target or source.startswith(f"{target}:") or target in source:
            return True
    return False


def is_available(item: EquipmentItem, progression: dict) -> bool:
    allowed_locations = progression.get("allowed_locations") or []
    allowed_source_types = set(progression.get("allowed_source_types") or ["store"])
    include_unknown = bool(progression.get("include_unknown_availability", False))

    if not item.sources:
        return include_unknown

    if not allowed_locations:
        return any(source.kind in allowed_source_types for source in item.sources)

    return any(
        source.kind in allowed_source_types and location_matches(source.location, allowed_locations)
        for source in item.sources
    )


def is_equippable_in_slot(item: EquipmentItem, slot: str, class_name: str) -> bool:
    if item.slot != slot:
        return False
    if slot == "weapon":
        return item.category in CLASS_WEAPONS[class_name]
    return True


def available_equipment_by_slot(
    items: list[EquipmentItem],
    progression: dict,
    class_name: str,
    slots: tuple[str, ...] = ("weapon", "shield", "headgear", "body_armor", "accessory"),
) -> dict[str, list[EquipmentItem]]:
    grouped: dict[str, list[EquipmentItem]] = defaultdict(list)
    for item in items:
        if item.slot not in slots:
            continue
        if not is_available(item, progression):
            continue
        if not is_equippable_in_slot(item, item.slot, class_name):
            continue
        grouped[item.slot].append(item)
    for slot in grouped:
        grouped[slot].sort(key=lambda item: (item.category, item.name))
    return dict(grouped)
