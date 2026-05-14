from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

STAT_KEYS = (
    "hp",
    "sp",
    "phys_atk",
    "elem_atk",
    "phys_def",
    "elem_def",
    "speed",
    "accuracy",
    "evasion",
    "critical",
)

EQUIPMENT_CATEGORIES = (
    "Swords",
    "Polearms",
    "Daggers",
    "Axes",
    "Bows",
    "Staves",
    "Shields",
    "Headgear",
    "Body Armor",
    "Accessories",
)

CATEGORY_FILES = {
    "Swords": "swords.json",
    "Polearms": "polearms.json",
    "Daggers": "daggers.json",
    "Axes": "axes.json",
    "Bows": "bows.json",
    "Staves": "staves.json",
    "Shields": "shields.json",
    "Headgear": "headgear.json",
    "Body Armor": "body_armor.json",
    "Accessories": "accessories.json",
}

CATEGORY_SLOT = {
    "Swords": "weapon",
    "Polearms": "weapon",
    "Daggers": "weapon",
    "Axes": "weapon",
    "Bows": "weapon",
    "Staves": "weapon",
    "Shields": "shield",
    "Headgear": "headgear",
    "Body Armor": "body_armor",
    "Accessories": "accessory",
}

CLASS_WEAPONS = {
    "Warrior": ["Swords", "Polearms"],
    "Hunter": ["Axes", "Bows"],
    "Thief": ["Swords", "Daggers"],
    "Scholar": ["Staves"],
    "Cleric": ["Staves"],
    "Dancer": ["Daggers"],
    "Merchant": ["Polearms", "Bows"],
    "Apothecary": ["Axes"],
}


@dataclass(frozen=True)
class AvailabilitySource:
    kind: str
    location: str | None
    raw: str


@dataclass(frozen=True)
class EquipmentItem:
    name: str
    category: str
    slot: str
    stats: dict[str, int]
    effect_text: str | None
    effect_tags: list[str]
    accessory_tags: list[str]
    accessory_tier: str | None
    max_ownable: int
    availability: str | None
    sources: list[AvailabilitySource]
    price: int | None

    @property
    def key(self) -> str:
        return f"{self.category}:{self.name}".lower()


@dataclass
class CandidateScore:
    item: EquipmentItem
    score: float
    stat_delta: dict[str, int]
    effect_points: dict[str, float]
    reasons: list[str] = field(default_factory=list)
    is_current_item: bool = False
    acquisition_cost: int = 0


@dataclass
class CharacterResult:
    character: str
    level: int
    class_name: str
    selected_locations: list[str]
    recommendations: dict[str, CandidateScore]
    accessory_review: dict[str, list[EquipmentItem]]
    current_stats: dict[str, int]
    recommended_stats: dict[str, int]
    total_cost: int
    excluded_examples: list[str]
    base_stats: dict[str, int] = field(default_factory=dict)
    top_candidates: dict[str, list[CandidateScore]] = field(default_factory=dict)
    survivability_notes: list[str] = field(default_factory=list)
    budget: int | None = None

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "character": self.character,
            "level": self.level,
            "class": self.class_name,
            "selected_locations": self.selected_locations,
            "total_cost": self.total_cost,
            "budget": self.budget,
            "base_stats": self.base_stats,
            "current_stats": self.current_stats,
            "recommended_stats": self.recommended_stats,
            "recommendations": {
                slot: {
                    "item": score.item.name,
                    "category": score.item.category,
                    "score": round(score.score, 2),
                    "price": score.item.price,
                    "acquisition_cost": score.acquisition_cost,
                    "is_current_item": score.is_current_item,
                    "stat_delta": score.stat_delta,
                    "effect_points": score.effect_points,
                    "effect_tags": score.item.effect_tags,
                    "availability": score.item.availability,
                    "reasons": score.reasons,
                }
                for slot, score in self.recommendations.items()
            },
            "top_candidates": {
                slot: [
                    {
                        "item": cs.item.name,
                        "category": cs.item.category,
                        "score": round(cs.score, 2),
                        "price": cs.item.price,
                        "acquisition_cost": cs.acquisition_cost,
                        "is_current_item": cs.is_current_item,
                        "stat_delta": cs.stat_delta,
                        "effect_tags": cs.item.effect_tags,
                        "availability": cs.item.availability,
                    }
                    for cs in candidates
                ]
                for slot, candidates in self.top_candidates.items()
            },
            "accessory_review": {
                tier: [
                    {
                        "name": item.name,
                        "tags": item.accessory_tags,
                        "effect": item.effect_text,
                        "availability": item.availability,
                        "stats": {k: v for k, v in item.stats.items() if v},
                    }
                    for item in items
                ]
                for tier, items in self.accessory_review.items()
            },
            "survivability_notes": self.survivability_notes,
            "excluded_examples": self.excluded_examples,
        }
