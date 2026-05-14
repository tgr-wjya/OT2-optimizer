from __future__ import annotations

from .models import CandidateScore, EquipmentItem, STAT_KEYS


def combine_stats(base: dict[str, int], items: list[EquipmentItem]) -> dict[str, int]:
    stats = {key: int(base.get(key, 0)) for key in STAT_KEYS}
    for item in items:
        for stat, value in item.stats.items():
            stats[stat] += value
    return stats


def score_candidate(
    candidate: EquipmentItem,
    current_item: EquipmentItem | None,
    priorities: dict[str, float],
    effect_values: dict[str, float],
    minimum_priorities: dict[str, float] | None = None,
) -> CandidateScore:
    minimum_priorities = minimum_priorities or {}
    effective_priorities = {
        key: max(float(priorities.get(key, 0)), float(minimum_priorities.get(key, 0)))
        for key in set(priorities) | set(minimum_priorities) | set(STAT_KEYS)
    }
    stat_delta: dict[str, int] = {}
    for stat in STAT_KEYS:
        stat_delta[stat] = candidate.stats.get(stat, 0) - (
            current_item.stats.get(stat, 0) if current_item else 0
        )

    score = 0.0
    reasons: list[str] = []
    for stat, delta in stat_delta.items():
        weight = effective_priorities.get(stat, 0)
        if delta and weight:
            points = delta * weight
            score += points
            source = "floor" if weight > float(priorities.get(stat, 0)) else "priority"
            reasons.append(f"{stat} {delta:+d} x {weight:g} ({source}) = {points:+.1f}")

    effect_points: dict[str, float] = {}
    for tag in candidate.effect_tags:
        value = float(effect_values.get(tag, 0)) * effective_priorities.get(tag, 1)
        if value:
            score += value
            effect_points[tag] = value
            reasons.append(f"effect {tag} = {value:+.1f}")

    return CandidateScore(
        item=candidate,
        score=score,
        stat_delta={key: value for key, value in stat_delta.items() if value},
        effect_points=effect_points,
        reasons=reasons,
    )
