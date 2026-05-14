"""
Config template generator for the OT2 optimizer.

Provides a minimal starter config for any character + class + level
combination. Class-specific tuning stays inside the engine.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Class defaults
# ---------------------------------------------------------------------------

# Stat + effect priorities per original class.
# Effect tags that aren't relevant to a class are left at 0 so they
# don't accidentally pull in useless effect gear.
CLASS_PRIORITIES: dict[str, dict[str, float]] = {
    "Scholar": {
        "hp": 0.05,
        "sp": 0.25,
        "phys_atk": 0.0,
        "elem_atk": 1.0,
        "phys_def": 0.25,
        "elem_def": 0.35,
        "speed": 0.15,
        "accuracy": 0.0,
        "evasion": 0.1,
        "critical": 0.0,
        # effect tags
        "fire_potency": 1.0,
        "ice_potency": 1.0,
        "lightning_potency": 1.0,
        "wind_potency": 0.2,
        "sp_sustain": 0.6,
    },
    "Cleric": {
        "hp": 0.1,
        "sp": 0.4,  # SP is life for healers
        "phys_atk": 0.0,
        "elem_atk": 0.6,  # heals scale with Elem. Atk in OT2
        "phys_def": 0.25,
        "elem_def": 0.35,
        "speed": 0.25,  # speed matters for healing priority
        "accuracy": 0.0,
        "evasion": 0.1,
        "critical": 0.0,
        "light_potency": 0.8,
        "sp_sustain": 0.8,
    },
    "Warrior": {
        "hp": 0.1,
        "sp": 0.05,
        "phys_atk": 1.0,
        "elem_atk": 0.0,
        "phys_def": 0.35,
        "elem_def": 0.2,
        "speed": 0.15,
        "accuracy": 0.1,
        "evasion": 0.05,
        "critical": 0.1,
        "physical_skill_potency": 0.5,
    },
    "Hunter": {
        "hp": 0.05,
        "sp": 0.1,
        "phys_atk": 1.0,
        "elem_atk": 0.0,
        "phys_def": 0.25,
        "elem_def": 0.15,
        "speed": 0.25,
        "accuracy": 0.2,
        "evasion": 0.1,
        "critical": 0.15,
        "physical_skill_potency": 0.3,
    },
    "Thief": {
        "hp": 0.05,
        "sp": 0.1,
        "phys_atk": 0.8,
        "elem_atk": 0.0,
        "phys_def": 0.2,
        "elem_def": 0.15,
        "speed": 0.35,  # speed is a Thief priority
        "accuracy": 0.1,
        "evasion": 0.25,  # evasion matters for Thief survivability
        "critical": 0.15,
    },
    "Dancer": {
        "hp": 0.05,
        "sp": 0.25,
        "phys_atk": 0.0,
        "elem_atk": 0.5,  # Dancer damage scales with Elem. Atk
        "phys_def": 0.2,
        "elem_def": 0.25,
        "speed": 0.4,  # turn order is critical for Dancer support
        "accuracy": 0.0,
        "evasion": 0.15,
        "critical": 0.0,
        "sp_sustain": 0.4,
    },
    "Merchant": {
        "hp": 0.1,
        "sp": 0.1,
        "phys_atk": 0.7,
        "elem_atk": 0.0,
        "phys_def": 0.3,
        "elem_def": 0.2,
        "speed": 0.2,
        "accuracy": 0.1,
        "evasion": 0.05,
        "critical": 0.1,
    },
    "Apothecary": {
        "hp": 0.1,
        "sp": 0.2,
        "phys_atk": 0.6,
        "elem_atk": 0.0,
        "phys_def": 0.3,
        "elem_def": 0.2,
        "speed": 0.1,
        "accuracy": 0.15,
        "evasion": 0.05,
        "critical": 0.05,
        "sp_sustain": 0.3,
    },
}

# Minimum stat weights — a stat is never scored below these even if the
# user's priority is lower.  Ensures survivability is never ignored.
CLASS_MINIMUM_PRIORITIES: dict[str, dict[str, float]] = {
    "Scholar": {"hp": 0.08, "phys_def": 0.55, "elem_def": 0.55, "evasion": 0.12},
    "Cleric": {"hp": 0.1, "phys_def": 0.5, "elem_def": 0.5, "evasion": 0.1},
    "Warrior": {"hp": 0.1, "phys_def": 0.5, "elem_def": 0.35},
    "Hunter": {"hp": 0.08, "phys_def": 0.45, "elem_def": 0.3},
    "Thief": {"hp": 0.05, "phys_def": 0.4, "elem_def": 0.3, "evasion": 0.2},
    "Dancer": {"hp": 0.05, "phys_def": 0.4, "elem_def": 0.4},
    "Merchant": {"hp": 0.1, "phys_def": 0.45, "elem_def": 0.35},
    "Apothecary": {"hp": 0.1, "phys_def": 0.45, "elem_def": 0.35},
}

# Effect tag values — how many virtual stat points an effect is worth.
# These feed into the effect scoring branch of the optimizer.
CLASS_EFFECT_VALUES: dict[str, dict[str, float]] = {
    "Scholar": {
        "physical_skill_potency": 0,
        "fire_potency": 35,
        "ice_potency": 35,
        "lightning_potency": 35,
        "wind_potency": 20,
        "dark_potency": 20,
        "light_potency": 20,
        "sp_sustain": 25,
        "low_hp_damage": 0,
        "instant_kill": 0,
    },
    "Cleric": {
        "physical_skill_potency": 0,
        "light_potency": 30,
        "sp_sustain": 35,
        "instant_kill": 0,
    },
    "Warrior": {
        "physical_skill_potency": 30,
        "sp_sustain": 10,
        "low_hp_damage": 0,
        "instant_kill": 0,
    },
    "Hunter": {
        "physical_skill_potency": 25,
        "sp_sustain": 10,
    },
    "Thief": {
        "physical_skill_potency": 20,
        "sp_sustain": 10,
    },
    "Dancer": {
        "sp_sustain": 20,
        "fire_potency": 15,
        "ice_potency": 15,
        "lightning_potency": 15,
    },
    "Merchant": {
        "physical_skill_potency": 20,
        "sp_sustain": 10,
    },
    "Apothecary": {
        "sp_sustain": 20,
        "physical_skill_potency": 15,
    },
}

# Default class for each character (original class only).
CHARACTER_DEFAULT_CLASS: dict[str, str] = {
    "Osvald": "Scholar",
    "Temenos": "Cleric",
    "Hikari": "Warrior",
    "Throné": "Thief",
    "Ochette": "Hunter",
    "Castti": "Apothecary",
    "Agnea": "Dancer",
    "Partitio": "Merchant",
}

# Typical starting town for each character's chapter 1 region.
# Used as a hint comment in generated configs; not restrictive.
CHARACTER_STARTING_REGION: dict[str, list[str]] = {
    "Osvald": ["Cape Cold", "New Delsta"],
    "Temenos": ["Flamechurch", "Oresrush"],
    "Hikari": ["Ryu", "Sai"],
    "Throné": ["Oresrush", "New Delsta"],
    "Ochette": ["Beasting Village", "Ryu"],
    "Castti": ["Canalbrine", "New Delsta"],
    "Agnea": ["Cropdale", "New Delsta"],
    "Partitio": ["Oresrush", "New Delsta"],
}


# ---------------------------------------------------------------------------
# Template generator
# ---------------------------------------------------------------------------


def generate_config_template(
    character: str,
    class_name: str,
    level: int,
    allowed_locations: list[str] | None = None,
    budget: int | None = None,
) -> dict[str, Any]:
    """
    Generate a complete optimizer config template for any character / class /
    level combination.

    Parameters
    ----------
    character         : Character name (e.g. "Hikari")
    class_name        : Original class (e.g. "Warrior")
    level             : Character level (1–99)
    allowed_locations : List of town/location names the player has reached.
                        Pass None or [] to leave blank for the user to fill in.
    budget            : Leaf budget, or None for unlimited.
    """
    config: dict[str, Any] = {
        "character": character,
        "class": class_name,
        "level": level,
        "progression": {
            "allowed_locations": allowed_locations or [],
            "allowed_source_types": ["store"],
            "include_unknown_availability": False,
            "budget": budget,
        },
        "current_equipment": None,
        "owned_inventory": None,
        "respect_other_characters": False,
        "reserved_inventory": None,
        "naked_stats": {},
    }

    return config


def save_config_template(
    config: dict[str, Any],
    path: Path,
) -> None:
    """Write a config template to a JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")


def list_characters() -> list[str]:
    return sorted(CHARACTER_DEFAULT_CLASS.keys())


def list_classes() -> list[str]:
    return sorted(CLASS_PRIORITIES.keys())
