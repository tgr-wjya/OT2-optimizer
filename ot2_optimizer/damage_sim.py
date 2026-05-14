"""
OT2 Damage Simulator
====================

Implements the game's damage formula and provides a side-by-side comparison of
current vs recommended gear for a set of skill scenarios.

Formula (from the Stats.csv "Damage Formula" section):
    Base_Damage   = Elem_Att - (Elem_Def × Def_Mod / 2)        [elemental skills]
    Per_Hit       = Base_Damage × Skill_Ratio × Level_Mult × Other_Mults
    Total_Damage  = Per_Hit × Hits × rand(0.98 … 1.02)

Where:
    Def_Mod    – per-skill defence penetration fraction (1.0 = full half-def
                 applied; 0.80 = 20% penetration, i.e. less defence subtracted)
    Skill_Ratio– per-skill/BP multiplier on the base damage
    Level_Mult – character level scaling (0.5625 at Lv1, 1.0 at ~Lv50)
    rand       – ±2% random variance applied per hit in the game engine

Other multipliers that are NOT modelled by default (can be passed via
`other_mult`):
    Weakness    +30%   (hitting an elemental weakness)
    Broken      +100%  (target is broken)
    Atk Buff    +50%
    Def Debuff  +50%
    Atk Debuff  -33%
    Def Buff    -33%
    Crit        +25%  (spells normally cannot crit; exception: forced-crit buffs)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .scholar_skills import (
    ScholarSkill,
    effective_hits,
    get_skill,
)
from .stats_data import load_level_multipliers

# ---------------------------------------------------------------------------
# Data-classes
# ---------------------------------------------------------------------------


@dataclass
class DamageResult:
    """Damage output for one (skill, bp, intensity, stats) combination."""

    skill_name: str
    display_name: str  # intensity-aware name (e.g. "Ignis Ardere")
    bp: int
    intensity: int
    elem_atk: int
    enemy_elem_def: int
    base_damage: float  # Elem_Att − (Elem_Def × Def_Mod / 2)
    skill_ratio: float
    level_mult: float
    hits_min: int
    hits_max: int
    per_hit_nominal: int  # round(base_damage × skill_ratio × level_mult)
    total_nominal: int  # per_hit_nominal × avg(hits_min, hits_max)
    total_min: int  # per_hit_nominal × 0.98 × hits_min
    total_max: int  # per_hit_nominal × 1.02 × hits_max
    confidence: str  # HIGH / MEDIUM / LOW

    def hits_str(self) -> str:
        if self.hits_min == self.hits_max:
            return str(self.hits_min)
        return f"{self.hits_min}–{self.hits_max}"

    def total_str(self) -> str:
        return f"{self.total_min}–{self.total_max}"

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "skill_name": self.skill_name,
            "display_name": self.display_name,
            "bp": self.bp,
            "intensity": self.intensity,
            "elem_atk": self.elem_atk,
            "enemy_elem_def": self.enemy_elem_def,
            "base_damage": round(self.base_damage, 1),
            "skill_ratio": self.skill_ratio,
            "level_mult": self.level_mult,
            "hits": self.hits_str(),
            "per_hit_nominal": self.per_hit_nominal,
            "total_nominal": self.total_nominal,
            "total_min": self.total_min,
            "total_max": self.total_max,
            "confidence": self.confidence,
        }


@dataclass
class DamageScenario:
    """One user-specified scenario to simulate."""

    skill: str
    bp: int = 0
    intensity: int = 0
    label: str = ""  # optional custom display label

    @property
    def display_label(self) -> str:
        if self.label:
            return self.label
        suffix = f"BP+{self.bp}" if self.bp else "BP+0"
        if self.intensity:
            suffix += f"/I{self.intensity}"
        return f"{self.skill} ({suffix})"


@dataclass
class DamageComparisonRow:
    """Side-by-side result for current vs recommended elem_atk."""

    scenario: DamageScenario
    current: DamageResult
    recommended: DamageResult

    @property
    def display_name(self) -> str:
        return self.current.display_name

    @property
    def delta_nominal(self) -> int:
        return self.recommended.total_nominal - self.current.total_nominal

    @property
    def delta_pct(self) -> float:
        if self.current.total_nominal <= 0:
            return 0.0
        return (self.recommended.total_nominal / self.current.total_nominal - 1) * 100


@dataclass
class DamageComparison:
    """Full damage comparison for one character's current vs recommended gear."""

    enemy_elem_def: int
    level: int
    level_mult: float
    current_elem_atk: int
    recommended_elem_atk: int
    rows: list[DamageComparisonRow]
    confidence_note: str = ""

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "enemy_elem_def": self.enemy_elem_def,
            "level": self.level,
            "level_mult": self.level_mult,
            "current_elem_atk": self.current_elem_atk,
            "recommended_elem_atk": self.recommended_elem_atk,
            "scenarios": [
                {
                    "label": row.scenario.display_label,
                    "skill": row.scenario.skill,
                    "bp": row.scenario.bp,
                    "intensity": row.scenario.intensity,
                    "current": row.current.to_jsonable(),
                    "recommended": row.recommended.to_jsonable(),
                    "delta_nominal": row.delta_nominal,
                    "delta_pct": round(row.delta_pct, 1),
                }
                for row in self.rows
            ],
            "confidence_note": self.confidence_note,
        }


# ---------------------------------------------------------------------------
# Core calculation
# ---------------------------------------------------------------------------


def _get_level_mult(level: int, level_mults: dict[int, float]) -> float:
    """Return level multiplier, falling back to the closest known level."""
    if level in level_mults:
        return level_mults[level]
    if not level_mults:
        return 0.715  # Lv18 hardcoded last resort
    closest = min(level_mults.keys(), key=lambda k: abs(k - level))
    return level_mults[closest]


def calculate_damage(
    skill: ScholarSkill,
    elem_atk: int,
    enemy_elem_def: int,
    level: int,
    bp: int = 0,
    intensity: int = 0,
    other_mult: float = 1.0,
    level_mults: dict[int, float] | None = None,
) -> DamageResult:
    """
    Compute damage output for a single scenario.

    Parameters
    ----------
    skill          : ScholarSkill instance
    elem_atk       : character's total Elem. Atk (base + gear)
    enemy_elem_def : enemy's Elem. Def
    level          : character level (for level multiplier lookup)
    bp             : boost points spent (0–3)
    intensity      : spell intensity tier (0 = base, 1/2 = upgraded)
    other_mult     : combined other multipliers (weakness, broken, buffs…)
    level_mults    : preloaded multiplier table; loaded fresh if None
    """
    if level_mults is None:
        level_mults = load_level_multipliers()

    lv_mult = _get_level_mult(level, level_mults)
    bp_idx = min(bp, len(skill.bp_levels) - 1)
    bp_data = skill.bp_levels[bp_idx]
    s_ratio = bp_data.skill_ratio
    d_mod = bp_data.def_mod

    # Base damage — clamped to minimum 1 so high-def enemies still take damage
    base_dmg = max(1.0, float(elem_atk) - (float(enemy_elem_def) * d_mod / 2.0))

    per_hit_f = base_dmg * s_ratio * lv_mult * other_mult
    per_hit_nominal = round(per_hit_f)

    hits_min_v, hits_max_v = effective_hits(skill, bp_idx, intensity)
    avg_hits = (hits_min_v + hits_max_v) / 2.0

    total_nominal = round(per_hit_f * avg_hits)
    total_min = round(per_hit_f * 0.98 * hits_min_v)
    total_max = round(per_hit_f * 1.02 * hits_max_v)

    # Intensity-aware display name
    display_name = skill.name
    if skill.intensity_tiers:
        tier_idx = min(intensity, len(skill.intensity_tiers) - 1)
        display_name = skill.intensity_tiers[tier_idx].display_name

    return DamageResult(
        skill_name=skill.name,
        display_name=display_name,
        bp=bp,
        intensity=intensity,
        elem_atk=elem_atk,
        enemy_elem_def=enemy_elem_def,
        base_damage=round(base_dmg, 1),
        skill_ratio=s_ratio,
        level_mult=lv_mult,
        hits_min=hits_min_v,
        hits_max=hits_max_v,
        per_hit_nominal=per_hit_nominal,
        total_nominal=total_nominal,
        total_min=total_min,
        total_max=total_max,
        confidence=skill.confidence,
    )


# ---------------------------------------------------------------------------
# Comparison runner
# ---------------------------------------------------------------------------


def run_comparison(
    scenarios: list[DamageScenario],
    current_elem_atk: int,
    recommended_elem_atk: int,
    enemy_elem_def: int,
    level: int,
    other_mult: float = 1.0,
) -> DamageComparison:
    """Evaluate all scenarios for both current and recommended elem_atk."""
    level_mults = load_level_multipliers()
    lv_mult = _get_level_mult(level, level_mults)

    rows: list[DamageComparisonRow] = []
    confidences: set[str] = set()

    for scenario in scenarios:
        skill = get_skill(scenario.skill)
        if skill is None or not skill.is_damage_skill:
            continue

        kwargs = dict(
            enemy_elem_def=enemy_elem_def,
            level=level,
            bp=scenario.bp,
            intensity=scenario.intensity,
            other_mult=other_mult,
            level_mults=level_mults,
        )
        current = calculate_damage(skill=skill, elem_atk=current_elem_atk, **kwargs)
        recommended = calculate_damage(
            skill=skill, elem_atk=recommended_elem_atk, **kwargs
        )

        rows.append(
            DamageComparisonRow(
                scenario=scenario,
                current=current,
                recommended=recommended,
            )
        )
        confidences.add(skill.confidence)

    if "LOW" in confidences:
        conf_note = (
            "⚠ Some scenarios are LOW confidence — Skill_Ratio/Def_Mod are estimates."
            " Replace with verified values when available."
        )
    elif "MEDIUM" in confidences:
        conf_note = (
            "ℹ Skill_Ratio and Def_Mod values are MEDIUM confidence"
            " (community datamine; may differ ≈±10%)."
        )
    else:
        conf_note = ""

    return DamageComparison(
        enemy_elem_def=enemy_elem_def,
        level=level,
        level_mult=lv_mult,
        current_elem_atk=current_elem_atk,
        recommended_elem_atk=recommended_elem_atk,
        rows=rows,
        confidence_note=conf_note,
    )


def run_comparison_from_config(
    config: dict,
    current_elem_atk: int,
    recommended_elem_atk: int,
    level: int,
) -> DamageComparison | None:
    """
    Parse a ``damage_sim`` config section and run the comparison.
    Returns None if the section is missing or contains no valid scenarios.
    """
    cfg = config.get("damage_sim")
    if not cfg:
        return None

    raw = cfg.get("scenarios", [])
    if not raw:
        return None

    scenarios = [
        DamageScenario(
            skill=s["skill"],
            bp=int(s.get("bp", 0)),
            intensity=int(s.get("intensity", 0)),
            label=s.get("label", ""),
        )
        for s in raw
    ]

    comp = run_comparison(
        scenarios=scenarios,
        current_elem_atk=current_elem_atk,
        recommended_elem_atk=recommended_elem_atk,
        enemy_elem_def=int(cfg.get("enemy_elem_def", 100)),
        level=level,
        other_mult=float(cfg.get("other_multiplier", 1.0)),
    )
    return comp if comp.rows else None
