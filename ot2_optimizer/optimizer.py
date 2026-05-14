from __future__ import annotations

from collections import defaultdict
from itertools import product

from .availability import is_available
from .data_loader import item_index, normalize_name
from .models import CLASS_WEAPONS, CandidateScore, CharacterResult, EquipmentItem
from .scoring import combine_stats, score_candidate
from .stats_data import base_stats_for

AUTO_SLOTS = ("weapon", "shield", "headgear", "body_armor")


def find_item(
    index: dict[str, EquipmentItem], name: str | None
) -> EquipmentItem | None:
    if not name:
        return None
    return index.get(normalize_name(name))


def allowed_for_slot(item: EquipmentItem, slot: str, class_name: str) -> bool:
    if item.slot != slot:
        return False
    if slot == "weapon":
        return item.category in CLASS_WEAPONS[class_name]
    return True


def acquisition_cost(
    item: EquipmentItem,
    current_item: EquipmentItem | None,
    budget_enabled: bool,
    allow_unknown_prices: bool,
) -> int:
    if current_item and current_item.key == item.key:
        return 0
    if item.price is not None:
        return item.price
    if budget_enabled and not allow_unknown_prices:
        return 10**12
    return 0


def survivability_adjustment(
    final_stats: dict[str, int],
    targets: dict[str, int],
    weights: dict[str, float],
) -> tuple[float, list[str]]:
    score = 0.0
    notes: list[str] = []
    for stat, target in targets.items():
        current = final_stats.get(stat, 0)
        weight = float(weights.get(stat, 1))
        if current < int(target):
            penalty = (int(target) - current) * weight
            score -= penalty
            notes.append(f"{stat} target {target}, final {current}: -{penalty:.1f}")
        else:
            bonus = min(current - int(target), 25) * weight * 0.1
            score += bonus
            if bonus:
                notes.append(f"{stat} target {target}, final {current}: +{bonus:.1f}")
    return score, notes


def optimize_character(config: dict, items: list[EquipmentItem]) -> CharacterResult:
    character = config["character"]
    class_name = config["class"]
    level = int(config["level"])
    priorities = config.get("priorities", {})
    minimum_priorities = config.get("minimum_priorities", {})
    progression = config.get("progression", {})
    effect_values = config.get("effect_values", {})
    survivability_targets = config.get("survivability_targets", {})
    survivability_target_weights = config.get("survivability_target_weights", {})
    current_equipment_config = config.get("current_equipment", {})
    index = item_index(items)

    current_equipment = {
        slot: find_item(index, current_equipment_config.get(slot))
        for slot in (
            "weapon",
            "shield",
            "headgear",
            "body_armor",
            "accessory1",
            "accessory2",
        )
    }

    available_items = [item for item in items if is_available(item, progression)]
    excluded_examples = [
        f"{item.name} ({item.slot}: {item.availability})"
        for item in items
        if (
            not is_available(item, progression)
            and item.slot in ("shield", "headgear", "body_armor")
        )
        or (
            not is_available(item, progression)
            and item.slot == "weapon"
            and item.category in CLASS_WEAPONS[class_name]
        )
    ][:20]

    base_stats = config.get("naked_stats")
    if not base_stats:
        base_stats = base_stats_for(character, level)

    budget = progression.get("budget")
    budget_enabled = budget is not None
    allow_unknown_prices = bool(progression.get("allow_unknown_prices", False))

    scored_by_slot: dict[str, list[CandidateScore]] = {}
    for slot in AUTO_SLOTS:
        candidates = [
            item for item in available_items if allowed_for_slot(item, slot, class_name)
        ]
        current_item = current_equipment.get(slot)
        scored = [
            score_candidate(
                item,
                current_item,
                priorities,
                effect_values,
                minimum_priorities,
            )
            for item in candidates
        ]
        # Only add current_item if it's not already in candidates (avoids duplicates)
        current_item_keys = {c.item.key for c in scored}
        if current_item and current_item.key not in current_item_keys:
            scored.append(
                score_candidate(
                    current_item,
                    current_item,
                    priorities,
                    effect_values,
                    minimum_priorities,
                )
            )
        if scored:
            scored_by_slot[slot] = sorted(
                scored, key=lambda item_score: item_score.score, reverse=True
            )

    # Annotate is_current_item and acquisition_cost on all candidates
    slot_order = [slot for slot in AUTO_SLOTS if slot in scored_by_slot]
    for slot in slot_order:
        current_item = current_equipment.get(slot)
        for cs in scored_by_slot[slot]:
            cs.acquisition_cost = acquisition_cost(
                cs.item, current_item, budget_enabled, allow_unknown_prices
            )
            cs.is_current_item = (
                current_item is not None and cs.item.key == current_item.key
            )

    recommendations: dict[str, CandidateScore] = {}
    best_combo: tuple[CandidateScore, ...] | None = None
    best_combo_score = float("-inf")
    best_combo_cost = 0
    best_survival_notes: list[str] = []

    for combo in product(*(scored_by_slot[slot] for slot in slot_order)):
        cost = sum(
            acquisition_cost(
                score.item,
                current_equipment.get(slot_order[index]),
                budget_enabled,
                allow_unknown_prices,
            )
            for index, score in enumerate(combo)
        )
        if budget is not None and cost > int(budget):
            continue
        combo_items = [score.item for score in combo]
        combo_final_stats = combine_stats(base_stats, combo_items)
        survival_score, survival_notes = survivability_adjustment(
            combo_final_stats,
            survivability_targets,
            survivability_target_weights,
        )
        combo_score = sum(score.score for score in combo) + survival_score
        if combo_score > best_combo_score:
            best_combo = combo
            best_combo_score = combo_score
            best_combo_cost = cost
            best_survival_notes = survival_notes

    if best_combo is None and slot_order:
        for slot in slot_order:
            recommendations[slot] = scored_by_slot[slot][0]
    elif best_combo:
        recommendations = {
            slot: score for slot, score in zip(slot_order, best_combo, strict=True)
        }

    # Top candidates per slot — always include the current item even if outside top 5.
    top_candidates: dict[str, list[CandidateScore]] = {}
    for slot in slot_order:
        top = list(scored_by_slot[slot][:5])
        current_item = current_equipment.get(slot)
        if current_item and not any(cs.item.key == current_item.key for cs in top):
            for cs in scored_by_slot[slot]:
                if cs.item.key == current_item.key:
                    top.append(cs)
                    break
        top_candidates[slot] = top

    accessory_review: dict[str, list[EquipmentItem]] = defaultdict(list)
    for item in available_items:
        if item.slot == "accessory" and item.accessory_tier:
            accessory_review[item.accessory_tier].append(item)

    recommended_items = [score.item for score in recommendations.values()]
    current_items = [
        item for slot, item in current_equipment.items() if item and slot in AUTO_SLOTS
    ]
    return CharacterResult(
        character=character,
        level=level,
        class_name=class_name,
        selected_locations=progression.get("allowed_locations") or [],
        recommendations=recommendations,
        accessory_review={
            tier: sorted(items_for_tier, key=lambda item: item.name)
            for tier, items_for_tier in sorted(accessory_review.items())
        },
        current_stats=combine_stats(base_stats, current_items),
        recommended_stats=combine_stats(base_stats, recommended_items),
        total_cost=best_combo_cost,
        excluded_examples=excluded_examples,
        base_stats=base_stats,
        top_candidates=top_candidates,
        survivability_notes=best_survival_notes,
        budget=budget,
    )
