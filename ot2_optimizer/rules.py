from __future__ import annotations


def classify_effects(effect_text: str | None) -> list[str]:
    if not effect_text:
        return []
    text = effect_text.lower()
    tags: list[str] = []

    if "raises potency of physical skills" in text:
        tags.append("physical_skill_potency")
    if "fire-based" in text:
        tags.append("fire_potency")
    if "ice-based" in text:
        tags.append("ice_potency")
    if "lightning-based" in text:
        tags.append("lightning_potency")
    if "wind-based" in text:
        tags.append("wind_potency")
    if "dark-based" in text:
        tags.append("dark_potency")
    if "light-based" in text:
        tags.append("light_potency")
    if "recover sp" in text:
        tags.append("sp_sustain")
    if "more damage when your hp is low" in text:
        tags.append("low_hp_damage")
    if "additional exp" in text:
        tags.append("exp_farming")
    if "additional jp" in text:
        tags.append("jp_farming")
    if "additional leaves" in text:
        tags.append("leaves_farming")
    if "wards off all enemy encounters" in text:
        tags.append("encounter_control")
    if "raises the chances of encountering" in text:
        tags.append("encounter_farming")
    if "reduces" in text and "damage" in text:
        tags.append("elemental_resistance")
    if "prevents" in text:
        tags.append("status_immunity")
    if "instantly kill" in text:
        tags.append("instant_kill")

    return tags


def classify_accessory(name: str, effect_text: str | None, stats: dict[str, int]) -> tuple[str | None, list[str]]:
    tags = classify_effects(effect_text)
    if not tags and any(stats.values()):
        tags = []

    accessory_tags: list[str] = []
    if any(stats[key] > 0 for key in ("phys_atk", "elem_atk", "critical")):
        accessory_tags.append("damage")
    if any(stats[key] > 0 for key in ("hp", "phys_def", "elem_def", "evasion")):
        accessory_tags.append("survival")
    if any(stats[key] > 0 for key in ("sp",)):
        accessory_tags.append("sustain")
    if any(stats[key] > 0 for key in ("speed", "accuracy")):
        accessory_tags.append("speed_turn_order")

    accessory_tags.extend(tags)
    accessory_tags = sorted(set(accessory_tags))

    if not accessory_tags:
        return None, []

    if {"low_hp_damage", "encounter_control"} & set(accessory_tags):
        tier = "overpowered_manual"
    elif {"elemental_resistance", "status_immunity", "instant_kill"} & set(accessory_tags):
        tier = "situational"
    elif {"exp_farming", "jp_farming", "leaves_farming", "encounter_farming"} & set(accessory_tags):
        tier = "economy_farming"
    elif {"damage", "survival", "sustain", "speed_turn_order"} & set(accessory_tags):
        tier = "generic_good"
    else:
        tier = "niche"

    lowered = name.lower()
    if "alpione" in lowered or "fang of ferocity" in lowered:
        tier = "overpowered_manual"

    return tier, accessory_tags

