from __future__ import annotations

from .models import EquipmentItem


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

