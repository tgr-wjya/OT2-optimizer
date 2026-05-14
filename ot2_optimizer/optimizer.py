from __future__ import annotations

from collections import defaultdict
from itertools import product

from .availability import available_equipment_by_slot, is_available, is_equippable_in_slot
from .data_loader import item_index, normalize_name
from .models import CLASS_WEAPONS, CandidateScore, CharacterResult, EquipmentItem
from .scoring import combine_stats, score_candidate
from .stats_data import base_stats_for
from .templates import CLASS_EFFECT_VALUES, CLASS_MINIMUM_PRIORITIES, CLASS_PRIORITIES

AUTO_SLOTS = ("weapon", "shield", "headgear", "body_armor")

SURVIVABILITY_PROFILE = {
    "Scholar": {"phys_def": 1.65, "elem_def": 1.55, "hp": 1.15, "evasion": 1.05},
    "Cleric": {"phys_def": 1.6, "elem_def": 1.6, "hp": 1.15, "evasion": 1.0},
    "Warrior": {"phys_def": 1.45, "elem_def": 1.3, "hp": 1.1, "evasion": 0.95},
    "Hunter": {"phys_def": 1.4, "elem_def": 1.25, "hp": 1.05, "evasion": 1.0},
    "Thief": {"phys_def": 1.35, "elem_def": 1.25, "hp": 1.05, "evasion": 1.1},
    "Dancer": {"phys_def": 1.35, "elem_def": 1.35, "hp": 1.05, "evasion": 1.05},
    "Merchant": {"phys_def": 1.4, "elem_def": 1.3, "hp": 1.1, "evasion": 1.0},
    "Apothecary": {"phys_def": 1.45, "elem_def": 1.35, "hp": 1.15, "evasion": 0.95},
}


def find_item(
    index: dict[str, EquipmentItem], name: str | None
) -> EquipmentItem | None:
    if not name:
        return None
    return index.get(normalize_name(name))


def resolve_equipment_selection(
    index: dict[str, EquipmentItem],
    selection: object,
) -> EquipmentItem | None:
    if not selection:
        return None
    if isinstance(selection, str):
        return find_item(index, selection)
    if isinstance(selection, dict):
        name = selection.get("name") or selection.get("item")
        category = selection.get("category")
        key = selection.get("key")
        if key:
            item = index.get(normalize_name(str(key)))
            if item:
                return item
        if name and category:
            item = index.get(f"{normalize_name(str(category))}:{normalize_name(str(name))}")
            if item:
                return item
        if name:
            return find_item(index, str(name))
    return None


def acquisition_cost(
    item: EquipmentItem,
    current_item: EquipmentItem | None,
    budget_enabled: bool,
    allow_unknown_prices: bool,
    no_purchase_mode: bool = False,
) -> int:
    if no_purchase_mode:
        return 0
    if current_item and current_item.key == item.key:
        return 0
    if item.price is not None:
        return item.price
    if budget_enabled and not allow_unknown_prices:
        return 10**12
    return 0


def _parse_inventory_quantities(
    index: dict[str, EquipmentItem],
    inventory_payload: object,
    field_name: str,
) -> dict[str, int]:
    if not inventory_payload:
        return {}

    entries: list[object]
    if isinstance(inventory_payload, list):
        entries = inventory_payload
    else:
        raise ValueError(f"{field_name} must be a list")

    quantities: dict[str, int] = defaultdict(int)
    for idx, entry in enumerate(entries):
        item: EquipmentItem | None = None
        quantity = 1
        label = f"{field_name}[{idx}]"

        if isinstance(entry, str):
            item = resolve_equipment_selection(index, entry)
        elif isinstance(entry, dict):
            quantity_raw = entry.get("quantity", 1)
            if isinstance(quantity_raw, bool):
                raise ValueError(f"{label}.quantity must be an integer >= 1")
            try:
                quantity = int(quantity_raw)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{label}.quantity must be an integer >= 1") from exc
            if quantity < 1:
                raise ValueError(f"{label}.quantity must be >= 1")
            item = resolve_equipment_selection(index, entry)
            if item is None:
                item_name = entry.get("name") or entry.get("item") or entry.get("key")
                raise ValueError(f"{label} could not resolve item: {item_name!r}")
        else:
            raise ValueError(f"{label} must be string or object")

        if item is None:
            raise ValueError(f"{label} could not resolve item")
        quantities[item.key] += quantity

    return dict(quantities)


def _effective_owned_quantities(
    owned_quantities: dict[str, int],
    reserved_quantities: dict[str, int],
    respect_other_characters: bool,
) -> dict[str, int]:
    if not respect_other_characters:
        return dict(owned_quantities)

    effective: dict[str, int] = {}
    for key, qty in owned_quantities.items():
        remaining = qty - reserved_quantities.get(key, 0)
        if remaining > 0:
            effective[key] = remaining
    return effective


def _owned_equipment_by_slot(
    items: list[EquipmentItem],
    quantities: dict[str, int],
    class_name: str,
    slots: tuple[str, ...],
) -> dict[str, list[EquipmentItem]]:
    grouped: dict[str, list[EquipmentItem]] = defaultdict(list)
    for item in items:
        if quantities.get(item.key, 0) <= 0:
            continue
        if item.slot not in slots:
            continue
        if not is_equippable_in_slot(item, item.slot, class_name):
            continue
        grouped[item.slot].append(item)
    for slot in grouped:
        grouped[slot].sort(key=lambda item: (item.category, item.name))
    return dict(grouped)


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


def class_defaults(class_name: str) -> tuple[dict[str, float], dict[str, float], dict[str, float]]:
    priorities = CLASS_PRIORITIES.get(class_name, CLASS_PRIORITIES["Warrior"])
    minimum_priorities = CLASS_MINIMUM_PRIORITIES.get(class_name, {})
    effect_values = CLASS_EFFECT_VALUES.get(class_name, {})
    return priorities, minimum_priorities, effect_values


def survivability_policy(
    class_name: str,
    base_stats: dict[str, int],
) -> tuple[dict[str, int], dict[str, float]]:
    profile = SURVIVABILITY_PROFILE.get(class_name, SURVIVABILITY_PROFILE["Warrior"])
    targets: dict[str, int] = {}
    for stat, multiplier in profile.items():
        current = int(base_stats.get(stat, 0))
        if current <= 0:
            continue
        targets[stat] = max(current, int(round(current * multiplier)))
    weights = {"phys_def": 1.0, "elem_def": 1.0, "hp": 0.25, "evasion": 0.1}
    return targets, weights


def optimize_character(config: dict, items: list[EquipmentItem]) -> CharacterResult:
    character = config["character"]
    class_name = config["class"]
    level = int(config["level"])
    progression = config.get("progression", {})
    index = item_index(items)

    priorities, minimum_priorities, effect_values = class_defaults(class_name)

    current_equipment_config = config.get("current_equipment") or {}
    if not isinstance(current_equipment_config, dict):
        current_equipment_config = {}

    current_equipment = {
        slot: resolve_equipment_selection(index, current_equipment_config.get(slot))
        for slot in (
            "weapon",
            "shield",
            "headgear",
            "body_armor",
            "accessory1",
            "accessory2",
        )
    }

    owned_quantities = _parse_inventory_quantities(index, config.get("owned_inventory"), "owned_inventory")
    respect_other_characters = bool(config.get("respect_other_characters", False))
    reserved_quantities = (
        _parse_inventory_quantities(
            index,
            config.get("reserved_inventory"),
            "reserved_inventory",
        )
        if respect_other_characters
        else {}
    )
    effective_owned_quantities = _effective_owned_quantities(
        owned_quantities,
        reserved_quantities,
        respect_other_characters,
    )

    budget = progression.get("budget")
    owned_only_mode = budget == 0 and bool(owned_quantities)
    if owned_only_mode:
        for slot in AUTO_SLOTS:
            current_item = current_equipment.get(slot)
            if current_item:
                effective_owned_quantities[current_item.key] = max(
                    effective_owned_quantities.get(current_item.key, 0),
                    1,
                )
        available_items = [
            item for item in items if effective_owned_quantities.get(item.key, 0) > 0
        ]
        excluded_examples: list[str] = []
    else:
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

    survivability_targets, survivability_target_weights = survivability_policy(
        class_name,
        base_stats,
    )

    budget_enabled = budget is not None
    allow_unknown_prices = bool(progression.get("allow_unknown_prices", False))

    available_by_slot = (
        _owned_equipment_by_slot(items, effective_owned_quantities, class_name, AUTO_SLOTS)
        if owned_only_mode
        else available_equipment_by_slot(available_items, progression, class_name)
    )

    scored_by_slot: dict[str, list[CandidateScore]] = {}
    for slot in AUTO_SLOTS:
        candidates = available_by_slot.get(slot, [])
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
                cs.item,
                current_item,
                budget_enabled,
                allow_unknown_prices,
                no_purchase_mode=owned_only_mode,
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
                no_purchase_mode=owned_only_mode,
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
