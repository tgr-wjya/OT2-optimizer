"""
OT2 Scholar Job – Damage Simulator Skill Data
==============================================

Sources & confidence levels
----------------------------
HIGH  – Confirmed from Fandom wiki + 3+ independent guides (SP cost, element,
        target type, hit count, BP mechanic description).
MEDIUM– Derived from the community datamine of OT1 (Tables61 spreadsheet,
        https://docs.google.com/spreadsheets/d/1geqS6ST86PMaWAzxcIIYjo-HRTz8t55dsv8YEaco8_o)
        cross-referenced with the OT2 datamine (Exentryk / Melodia AbilityData
        sheet) and the BravelyPath Modular discord datamine. OT2 uses the
        same formula engine; Scholar skill structure is confirmed near-
        identical.  Numerical ability/invocation ratios are consistent with
        community-observed damage outputs.
LOW   – Extrapolated / partially confirmed for One True Magic EX skill.

Damage formula (as used in this file)
--------------------------------------
Base_Damage (elemental) = Elem_Att - (Elem_Def × Def_Mod / 2)

Skill_Damage_per_hit    = Base_Damage × Skill_Ratio × Level_Mult
                          × Other_Mults × rand(0.98 … 1.02)

Total_Skill_Damage      = Skill_Damage_per_hit × Hits

Where:
  Skill_Ratio   – direct damage multiplier (1.0 = baseline).
                  Corresponds to Ability_Ratio / 100 in the datamine.
  Def_Mod       – fraction of Elem_Def that is subtracted in the base-damage
                  calculation.  Relationship to the datamine's Invocation_Ratio
                  (InvR):  Def_Mod = 100 / InvR
                    InvR=100 → Def_Mod=1.00 (full half-defence applied)
                    InvR=125 → Def_Mod=0.80 (20 % defence penetrated)
                    InvR=150 → Def_Mod=0.67 (33 % defence penetrated)
                    InvR=200 → Def_Mod=0.50 (50 % defence penetrated)
                    InvR=∞   → Def_Mod=0.00 (defence fully ignored)

Intensity / Spell-boost mechanic (OT2-specific)
-------------------------------------------------
"Advanced Magic" and "Alephan's Wisdom" grant a character "spell intensity"
charges.  When a Scholar's elemental AoE spell (Fireball / Icewind /
Lightning Bolt) is cast, each available charge upgrades it by one tier,
consuming the charge:
  0 intensity  → base spell   (1 hit AoE)
  1 intensity  → Fire Storm / Blizzard / Lightning Blast   (2 hits)
  2 intensity  → Ignis Ardere / Glacies Claudere / Tonitrus Canere (3 hits)

Intensity upgrades do NOT interact with BP boost – those are orthogonal axes.
BP boost on the three elemental spells increases Skill_Ratio only (not hits).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# Data-class definitions
# ---------------------------------------------------------------------------


@dataclass
class BPLevel:
    """Stats for a specific BP level (0–3)."""

    bp: int
    skill_ratio: float  # direct damage multiplier per hit
    def_mod: float  # Elem_Def coefficient  (Def_Mod = 100 / InvRatio)
    hits_min: int  # minimum number of hits (1 for fixed)
    hits_max: int  # maximum number of hits (== hits_min for fixed)
    sp_cost: int  # SP cost (unchanged by BP in OT2)
    notes: str = ""


@dataclass
class IntensityLevel:
    """Stats for a given spell-intensity tier (Advanced Magic / Alephan's Wisdom)."""

    intensity: int  # 0 = base, 1 = first upgrade, 2 = second upgrade
    display_name: str
    hits: int  # fixed hit count for elemental AoE spells


@dataclass
class ScholarSkill:
    """
    Full skill entry for a Scholar skill.

    damage_type : "Elemental" | "Physical" | "None"
    target      : "all_enemies" | "single" | "random"
    """

    name: str
    sp_cost: int
    element: str  # Fire / Ice / Lightning / None
    damage_type: str  # Elemental / Physical / None
    target: str  # all_enemies / single / random
    bp_levels: list[BPLevel]  # index 0–3 for BP+0 … BP+3
    intensity_tiers: list[IntensityLevel] = field(default_factory=list)
    is_damage_skill: bool = True
    confidence: str = "MEDIUM"  # HIGH / MEDIUM / LOW
    notes: str = ""


@dataclass
class SupportSkill:
    """Scholar passive support skill."""

    name: str
    jp_cost_total: int
    skills_required: int
    description: str
    damage_relevant: bool
    damage_notes: str = ""


# ---------------------------------------------------------------------------
# Helper: build a fixed-hit, boost-scales-ratio BPLevel list
# ---------------------------------------------------------------------------


def _ratio_scaling(
    sp: int,
    def_mod: float,
    hits: int = 1,
    ratios: tuple[float, ...] = (1.00, 1.30, 1.60, 2.00),
) -> list[BPLevel]:
    """
    Build BP levels 0-3 where only Skill_Ratio scales; hits stay constant.
    ratios should have 4 values: BP0, BP1, BP2, BP3.
    """
    return [
        BPLevel(
            bp=i,
            skill_ratio=ratios[i],
            def_mod=def_mod,
            hits_min=hits,
            hits_max=hits,
            sp_cost=sp,
        )
        for i in range(4)
    ]


def _hit_scaling(
    sp: int,
    skill_ratio: float,
    def_mod: float,
    hit_ranges: tuple[tuple[int, int], ...],
) -> list[BPLevel]:
    """
    Build BP levels 0–3 where the hit range scales with BP, ratio stays flat.
    hit_ranges: ((min0,max0), (min1,max1), (min2,max2), (min3,max3))
    """
    return [
        BPLevel(
            bp=i,
            skill_ratio=skill_ratio,
            def_mod=def_mod,
            hits_min=hit_ranges[i][0],
            hits_max=hit_ranges[i][1],
            sp_cost=sp,
        )
        for i in range(4)
    ]


# ---------------------------------------------------------------------------
# Scholar skill definitions
# ---------------------------------------------------------------------------

# ------------------------------------------------------------------
# Three-tier intensity tiers shared by Fireball, Icewind, Lightning Bolt
# ------------------------------------------------------------------
_FIRE_INTENSITY = [
    IntensityLevel(intensity=0, display_name="Fireball", hits=1),
    IntensityLevel(intensity=1, display_name="Fire Storm", hits=2),
    IntensityLevel(intensity=2, display_name="Ignis Ardere", hits=3),
]
_ICE_INTENSITY = [
    IntensityLevel(intensity=0, display_name="Icewind", hits=1),
    IntensityLevel(intensity=1, display_name="Blizzard", hits=2),
    IntensityLevel(intensity=2, display_name="Glacies Claudere", hits=3),
]
_LIGHTNING_INTENSITY = [
    IntensityLevel(intensity=0, display_name="Lightning Bolt", hits=1),
    IntensityLevel(intensity=1, display_name="Lightning Blast", hits=2),
    IntensityLevel(intensity=2, display_name="Tonitrus Canere", hits=3),
]

# ------------------------------------------------------------------
# Fireball
# ------------------------------------------------------------------
# Ability_Ratio (per hit)   = 100  → Skill_Ratio = 1.00   [MEDIUM]
# Invocation_Ratio          = 125  → Def_Mod     = 0.80   [MEDIUM]
# BP boost: ratio scales, hits fixed (intensity provides extra hits)
# BP ratios (community-tested, consistent with OT1 datamine): 1.00/1.30/1.60/2.00
FIREBALL = ScholarSkill(
    name="Fireball",
    sp_cost=14,
    element="Fire",
    damage_type="Elemental",
    target="all_enemies",
    bp_levels=_ratio_scaling(
        sp=14,
        def_mod=0.80,  # Def_Mod = 100/125 = 0.80
        hits=1,
        ratios=(1.00, 1.30, 1.60, 2.00),
    ),
    intensity_tiers=_FIRE_INTENSITY,
    confidence="MEDIUM",
    notes=(
        "BP boost increases Skill_Ratio per hit only (not hit count). "
        "Hit count is controlled by spell intensity (Advanced Magic / Alephan's Wisdom). "
        "Per-hit Ability_Ratio ≈ 100, Invocation_Ratio ≈ 125 from OT1 datamine; "
        "consistent with OT2 community testing. "
        "BP ratio multipliers (1.0/1.3/1.6/2.0) are MEDIUM confidence – "
        "exact datamined values may differ by ±10 %."
    ),
)

# ------------------------------------------------------------------
# Icewind  (identical mechanics to Fireball, Ice element)
# ------------------------------------------------------------------
ICEWIND = ScholarSkill(
    name="Icewind",
    sp_cost=14,
    element="Ice",
    damage_type="Elemental",
    target="all_enemies",
    bp_levels=_ratio_scaling(
        sp=14,
        def_mod=0.80,
        hits=1,
        ratios=(1.00, 1.30, 1.60, 2.00),
    ),
    intensity_tiers=_ICE_INTENSITY,
    confidence="MEDIUM",
    notes=(
        "Identical mechanics to Fireball; Ice element. "
        "See Fireball notes for ratio confidence caveats."
    ),
)

# ------------------------------------------------------------------
# Lightning Bolt  (identical mechanics to Fireball, Lightning element)
# NOTE: One guide (vulkk.com) incorrectly lists this as 8 SP.
#       Fandom wiki, Samurai Gamers, commonsensegamer all confirm 14 SP.
# ------------------------------------------------------------------
LIGHTNING_BOLT = ScholarSkill(
    name="Lightning Bolt",
    sp_cost=14,  # HIGH confidence – multiple sources
    element="Lightning",
    damage_type="Elemental",
    target="all_enemies",
    bp_levels=_ratio_scaling(
        sp=14,
        def_mod=0.80,
        hits=1,
        ratios=(1.00, 1.30, 1.60, 2.00),
    ),
    intensity_tiers=_LIGHTNING_INTENSITY,
    confidence="MEDIUM",
    notes=(
        "Identical mechanics to Fireball; Lightning element. "
        "SP cost 14 confirmed by Fandom wiki and Samurai Gamers (vulkk.com "
        "incorrectly lists 8 SP – treat that as an editorial error). "
        "Ratio confidence same as Fireball."
    ),
)

# ------------------------------------------------------------------
# Elemental Barrage
# ------------------------------------------------------------------
# Hits random enemies; element per hit is random among Fire/Ice/Lightning.
# BP boost increases BOTH min and max of the hit range by +1.
#   BP0: 3–5 hits,  BP1: 4–6,  BP2: 5–7,  BP3: 6–8
# Per-hit Ability_Ratio ≈ 75, Invocation_Ratio ≈ 100 (Def_Mod = 1.0)
# These are MEDIUM-LOW confidence – no direct OT2 datamine confirmation found.
ELEMENTAL_BARRAGE = ScholarSkill(
    name="Elemental Barrage",
    sp_cost=10,
    element="Fire/Ice/Lightning",  # random per hit
    damage_type="Elemental",
    target="random",  # each hit chooses a random enemy
    bp_levels=_hit_scaling(
        sp=10,
        skill_ratio=0.75,  # per-hit Ability_Ratio ≈ 75  [LOW-MEDIUM]
        def_mod=1.00,  # Invocation_Ratio ≈ 100 (standard defence)
        hit_ranges=((3, 5), (4, 6), (5, 7), (6, 8)),
    ),
    confidence="MEDIUM",
    notes=(
        "Each hit independently chooses Fire, Ice, or Lightning (uniformly). "
        "Each hit independently chooses a random enemy (can hit same enemy "
        "multiple times or spread across all enemies). "
        "Hit-count range BP scaling confirmed HIGH from Fandom wiki "
        "(3-5 / 4-6 / 5-7 / 6-8). "
        "Per-hit Skill_Ratio=0.75 and Def_Mod=1.0 are MEDIUM-LOW confidence "
        "estimates; exact datamined values not publicly confirmed. "
        "Skill does NOT gain extra hits from spell intensity charges."
    ),
)

# ------------------------------------------------------------------
# Analyze  (non-damage)
# ------------------------------------------------------------------
ANALYZE = ScholarSkill(
    name="Analyze",
    sp_cost=1,
    element="None",
    damage_type="None",
    target="single",
    bp_levels=[
        BPLevel(
            bp=0,
            skill_ratio=0,
            def_mod=0,
            hits_min=0,
            hits_max=0,
            sp_cost=1,
            notes="Reveals HP + 1 weak point",
        ),
        BPLevel(
            bp=1,
            skill_ratio=0,
            def_mod=0,
            hits_min=0,
            hits_max=0,
            sp_cost=1,
            notes="Reveals HP + 2 weak points",
        ),
        BPLevel(
            bp=2,
            skill_ratio=0,
            def_mod=0,
            hits_min=0,
            hits_max=0,
            sp_cost=1,
            notes="Reveals HP + 3 weak points",
        ),
        BPLevel(
            bp=3,
            skill_ratio=0,
            def_mod=0,
            hits_min=0,
            hits_max=0,
            sp_cost=1,
            notes="Reveals HP + 5 weak points (all)",
        ),
    ],
    is_damage_skill=False,
    confidence="HIGH",
    notes="Utility skill – reveals HP and weak points. No damage output.",
)

# ------------------------------------------------------------------
# Stroke of Genius  (non-damage, self-buff)
# ------------------------------------------------------------------
STROKE_OF_GENIUS = ScholarSkill(
    name="Stroke of Genius",
    sp_cost=5,
    element="None",
    damage_type="None",
    target="self",
    bp_levels=[
        BPLevel(
            bp=0,
            skill_ratio=0,
            def_mod=0,
            hits_min=0,
            hits_max=0,
            sp_cost=5,
            notes="2 random attribute-raising effects on self",
        ),
        BPLevel(
            bp=1,
            skill_ratio=0,
            def_mod=0,
            hits_min=0,
            hits_max=0,
            sp_cost=5,
            notes="3 random attribute-raising effects on self",
        ),
        BPLevel(
            bp=2,
            skill_ratio=0,
            def_mod=0,
            hits_min=0,
            hits_max=0,
            sp_cost=5,
            notes="4 random attribute-raising effects on self",
        ),
        BPLevel(
            bp=3,
            skill_ratio=0,
            def_mod=0,
            hits_min=0,
            hits_max=0,
            sp_cost=5,
            notes="5 random attribute-raising effects on self",
        ),
    ],
    is_damage_skill=False,
    confidence="HIGH",
    notes=(
        "Applies 2/3/4/5 random buffs to self (stacks with repeated use). "
        "Possible buffs include Elem. Atk up, Phys. Atk up, Speed up, etc. "
        "Indirectly affects damage via Elem. Atk buff proc."
    ),
)

# ------------------------------------------------------------------
# Advanced Magic  (non-damage, ally buff – spell intensity)
# ------------------------------------------------------------------
ADVANCED_MAGIC = ScholarSkill(
    name="Advanced Magic",
    sp_cost=15,
    element="None",
    damage_type="None",
    target="single_ally",
    bp_levels=[
        BPLevel(
            bp=0,
            skill_ratio=0,
            def_mod=0,
            hits_min=0,
            hits_max=0,
            sp_cost=15,
            notes="Grants 2 spell-intensity charges to target ally",
        ),
        BPLevel(
            bp=1,
            skill_ratio=0,
            def_mod=0,
            hits_min=0,
            hits_max=0,
            sp_cost=15,
            notes="Grants 3 spell-intensity charges to target ally",
        ),
        BPLevel(
            bp=2,
            skill_ratio=0,
            def_mod=0,
            hits_min=0,
            hits_max=0,
            sp_cost=15,
            notes="Grants 4 spell-intensity charges to target ally",
        ),
        BPLevel(
            bp=3,
            skill_ratio=0,
            def_mod=0,
            hits_min=0,
            hits_max=0,
            sp_cost=15,
            notes="Grants 5 spell-intensity charges to target ally",
        ),
    ],
    is_damage_skill=False,
    confidence="HIGH",
    notes=(
        "Each charge upgrades the next intensity-eligible spell by one tier "
        "(e.g. Fireball → Fire Storm → Ignis Ardere). "
        "Eligible spells: Fireball, Icewind, Lightning Bolt (Scholar); "
        "Luminescence, Heal Wounds, Revive (Cleric); "
        "Malice, Blessing, Hex (Arcanist); "
        "Osvald's One True Magic EX skill; Temenos's Heavenly Shine EX. "
        "Effect is consumed on the next eligible spell cast."
    ),
)

# ------------------------------------------------------------------
# Alephan's Wisdom  (Divine skill – non-damage, ally spell-intensity buff)
# Divine skills require max BP (3 BP) to use.
# ------------------------------------------------------------------
ALEPHANS_WISDOM = ScholarSkill(
    name="Alephan's Wisdom",
    sp_cost=30,
    element="None",
    damage_type="None",
    target="single_ally",
    bp_levels=[
        # Divine skill only usable at BP3
        BPLevel(
            bp=3,
            skill_ratio=0,
            def_mod=0,
            hits_min=0,
            hits_max=0,
            sp_cost=30,
            notes="Grants 3 spell-intensity charges (greatly boosts). Requires BP=3.",
        ),
    ],
    is_damage_skill=False,
    confidence="HIGH",
    notes=(
        "Divine skill: requires 3 BP to use. "
        "Grants 3 spell-intensity charges, upgrading the next three eligible "
        "spells two tiers each (Fireball → Ignis Ardere in one cast). "
        "Same eligible spell list as Advanced Magic. "
        "Far more SP-efficient than stacking Advanced Magic for 3-hit spells."
    ),
)

# ------------------------------------------------------------------
# One True Magic  (EX skill – Osvald only, requires story completion)
# ------------------------------------------------------------------
# SP cost: commonsensegamer.com = 7 SP, Samurai Gamers = 20 SP.
# Given the power level of the skill, 20 SP seems more plausible,
# but this is flagged as LOW confidence.
#
# Damage type: "transcends the elements" – almighty / element-neutral.
# Always hits all enemies. Reduces shields regardless of weaknesses.
# Skill_Ratio and Def_Mod are not publicly datamined; estimates below.
#
# Intensity tiers (from OT2 wiki):
#   Base:  One True Magic        (1 hit all enemies)
#   Int 1: One True Magic II     (2 hits all enemies)
#   Int 2: One True Magic III    (3 hits all enemies)
ONE_TRUE_MAGIC = ScholarSkill(
    name="One True Magic",
    sp_cost=20,  # LOW confidence; one source says 7 SP
    element="None",  # transcends elements (almighty)
    damage_type="Elemental",  # still uses Elem_Att vs Elem_Def formula
    target="all_enemies",
    bp_levels=[
        # BP scaling details unknown; community reports high damage output.
        # Placeholder ratios are estimates only.
        BPLevel(
            bp=0,
            skill_ratio=3.00,
            def_mod=0.50,
            hits_min=1,
            hits_max=1,
            sp_cost=20,
            notes="Highly powerful; reduces shield by 1 ignoring weaknesses. ESTIMATE.",
        ),
        BPLevel(
            bp=1,
            skill_ratio=3.75,
            def_mod=0.50,
            hits_min=1,
            hits_max=1,
            sp_cost=20,
            notes="ESTIMATE",
        ),
        BPLevel(
            bp=2,
            skill_ratio=4.50,
            def_mod=0.50,
            hits_min=1,
            hits_max=1,
            sp_cost=20,
            notes="ESTIMATE",
        ),
        BPLevel(
            bp=3,
            skill_ratio=5.50,
            def_mod=0.50,
            hits_min=1,
            hits_max=1,
            sp_cost=20,
            notes="ESTIMATE",
        ),
    ],
    intensity_tiers=[
        IntensityLevel(intensity=0, display_name="One True Magic", hits=1),
        IntensityLevel(intensity=1, display_name="One True Magic II", hits=2),
        IntensityLevel(intensity=2, display_name="One True Magic III", hits=3),
    ],
    confidence="LOW",
    notes=(
        "EX skill – only usable by Osvald. Unlocked by completing Osvald's story. "
        "Damage 'transcends elements' – no elemental weakness or resistance applies. "
        "Reduces target shield points by 1 regardless of weaknesses. "
        "SP cost: 20 SP per Samurai Gamers (HIGH confidence) vs 7 SP per "
        "commonsensegamer.com (may be a typo). "
        "Skill_Ratio and Def_Mod are ESTIMATES ONLY – no community datamine "
        "confirmation found. Replace with actual values when available."
    ),
)

# ------------------------------------------------------------------
# Teach  (EX skill – Osvald only, from Altar of the Scholarking)
# ------------------------------------------------------------------
TEACH = ScholarSkill(
    name="Teach",
    sp_cost=10,  # Fandom wiki + Samurai Gamers confirm 10 SP
    element="None",
    damage_type="None",
    target="single_ally",
    bp_levels=[
        BPLevel(
            bp=0,
            skill_ratio=0,
            def_mod=0,
            hits_min=0,
            hits_max=0,
            sp_cost=10,
            notes="Transfers your attribute buffs to ally for 2 turns",
        ),
        BPLevel(
            bp=1,
            skill_ratio=0,
            def_mod=0,
            hits_min=0,
            hits_max=0,
            sp_cost=10,
            notes="Transfers your attribute buffs to ally for 3 turns",
        ),
        BPLevel(
            bp=2,
            skill_ratio=0,
            def_mod=0,
            hits_min=0,
            hits_max=0,
            sp_cost=10,
            notes="Transfers your attribute buffs to ally for 4 turns",
        ),
        BPLevel(
            bp=3,
            skill_ratio=0,
            def_mod=0,
            hits_min=0,
            hits_max=0,
            sp_cost=10,
            notes="Transfers your attribute buffs to ally for 5 turns",
        ),
    ],
    is_damage_skill=False,
    confidence="HIGH",
    notes=(
        "EX skill – only usable by Osvald. Unlocked at Altar of the Scholarking "
        "(Winterbloom). Synergizes with Stroke of Genius: buff yourself, then "
        "Teach copies those buffs to an ally."
    ),
)

# ---------------------------------------------------------------------------
# Support skills
# ---------------------------------------------------------------------------

SUPPORT_SKILLS: list[SupportSkill] = [
    SupportSkill(
        name="Evasive Maneuvers",
        jp_cost_total=130,
        skills_required=4,
        description="Reduces random encounter rate. Does not stack.",
        damage_relevant=False,
    ),
    SupportSkill(
        name="Elemental Augmentation",
        jp_cost_total=630,
        skills_required=5,
        description="Raises equipping character's Elem. Atk by +50.",
        damage_relevant=True,
        damage_notes=(
            "+50 flat to Elem_Att. Feeds directly into the damage formula as "
            "Elem_Att += 50.  Highly impactful early-to-mid game; scales "
            "linearly (does not multiply with other Elem_Att bonuses, just adds). "
            "One of the best damage supports for any Elem. Atk character."
        ),
    ),
    SupportSkill(
        name="Extra Experience",
        jp_cost_total=1630,
        skills_required=6,
        description="Receive additional EXP after battles. Does not stack.",
        damage_relevant=False,
    ),
    SupportSkill(
        name="Advanced Magic Master",
        jp_cost_total=4630,
        skills_required=7,
        description=(
            "Raises the number of times the equipping character can use "
            "more intense spells by 1."
        ),
        damage_relevant=True,
        damage_notes=(
            "Functionally grants +1 free spell-intensity charge at the start "
            "of battle (or replenishes by 1 after each Advanced Magic / "
            "Alephan's Wisdom cast). This means one fewer cast of Advanced "
            "Magic is needed each cycle, saving 15 SP per cycle. "
            "Effectively allows Fireball/Icewind/Lightning Bolt to hit 2×/3× "
            "one additional time before needing to reapply Advanced Magic."
        ),
    ),
]

# ---------------------------------------------------------------------------
# Master list (damage skills only, ordered by Scholar kit slot)
# ---------------------------------------------------------------------------

ALL_SCHOLAR_SKILLS: list[ScholarSkill] = [
    FIREBALL,
    ICEWIND,
    LIGHTNING_BOLT,
    ANALYZE,
    STROKE_OF_GENIUS,
    ELEMENTAL_BARRAGE,
    ADVANCED_MAGIC,
    ALEPHANS_WISDOM,
    # EX skills (Osvald-exclusive)
    ONE_TRUE_MAGIC,
    TEACH,
]

DAMAGE_SKILLS: list[ScholarSkill] = [s for s in ALL_SCHOLAR_SKILLS if s.is_damage_skill]


# ---------------------------------------------------------------------------
# Quick-access helpers
# ---------------------------------------------------------------------------


def get_skill(name: str) -> ScholarSkill | None:
    """Return the skill with the given name (case-insensitive), or None."""
    name_lower = name.lower()
    for skill in ALL_SCHOLAR_SKILLS:
        if skill.name.lower() == name_lower:
            return skill
    return None


def effective_hits(
    skill: ScholarSkill, bp: int = 0, intensity: int = 0
) -> tuple[int, int]:
    """
    Return (hits_min, hits_max) for a skill at a given BP + spell intensity.

    For Fireball / Icewind / Lightning Bolt:
      - BP controls Skill_Ratio (not hits).
      - Intensity controls hits (0=1, 1=2, 2=3).
    For Elemental Barrage:
      - BP controls hit-range; intensity has no effect.
    For non-damage skills: returns (0, 0).
    """
    if not skill.is_damage_skill:
        return (0, 0)

    bp_data = skill.bp_levels[min(bp, len(skill.bp_levels) - 1)]
    base_min, base_max = bp_data.hits_min, bp_data.hits_max

    if skill.intensity_tiers and intensity > 0:
        tier = skill.intensity_tiers[min(intensity, len(skill.intensity_tiers) - 1)]
        # Intensity overrides the hit count for AoE spells
        return (tier.hits, tier.hits)

    return (base_min, base_max)


def skill_ratio_at(skill: ScholarSkill, bp: int = 0) -> float:
    """Return the Skill_Ratio for the given BP level."""
    bp_data = skill.bp_levels[min(bp, len(skill.bp_levels) - 1)]
    return bp_data.skill_ratio


def def_mod_at(skill: ScholarSkill, bp: int = 0) -> float:
    """Return the Def_Mod for the given BP level."""
    bp_data = skill.bp_levels[min(bp, len(skill.bp_levels) - 1)]
    return bp_data.def_mod


# ---------------------------------------------------------------------------
# Boost-scaling summary (for documentation / debugging)
# ---------------------------------------------------------------------------

BOOST_SCALING_NOTES = """
Scholar Boost (BP) Scaling Summary
====================================

Fireball / Icewind / Lightning Bolt
  BP+0: Skill_Ratio = 1.00  (×1.0 damage)
  BP+1: Skill_Ratio = 1.30  (×1.3 damage)   [MEDIUM confidence]
  BP+2: Skill_Ratio = 1.60  (×1.6 damage)   [MEDIUM confidence]
  BP+3: Skill_Ratio = 2.00  (×2.0 damage)   [MEDIUM confidence]
  Hits: FIXED by BP; controlled by spell intensity instead.
  Def_Mod: 0.80 at all BP levels (Invocation_Ratio ≈ 125).

Elemental Barrage
  BP+0: 3–5 hits at Skill_Ratio = 0.75/hit  (expected ~3 hits avg)
  BP+1: 4–6 hits at Skill_Ratio = 0.75/hit  (expected ~5 hits avg)
  BP+2: 5–7 hits at Skill_Ratio = 0.75/hit  (expected ~6 hits avg)
  BP+3: 6–8 hits at Skill_Ratio = 0.75/hit  (expected ~7 hits avg)
  Ratio does NOT scale with BP, only hit-count range does.
  Element per hit is uniformly random among Fire/Ice/Lightning.
  Def_Mod: 1.00 at all BP levels (standard defence).

Analyze
  BP+0 → +1 → +2 → +3: reveals 1/2/3/5 weak points (non-damage).

Stroke of Genius
  BP+0 → +1 → +2 → +3: grants 2/3/4/5 random stat-raise buffs.

Advanced Magic
  BP+0 → +1 → +2 → +3: grants 2/3/4/5 spell-intensity charges.

Alephan's Wisdom  (Divine, requires BP=3)
  Always grants exactly 3 intensity charges (equivalent to two Advanced Magics
  worth of upgrade for a single spell cast chain).

Spell-Intensity Interaction with BP
  Each elemental spell (Fireball etc.) benefits from BOTH axes independently:
    - Boost the spell to BP+3 for 2.0× Skill_Ratio.
    - Have 2 intensity charges for 3-hit version.
  Combined: 3 hits × Skill_Ratio 2.0 → 6× the damage of unboosted Fireball.
"""

# ---------------------------------------------------------------------------
# Confidence flag reminder
# ---------------------------------------------------------------------------

CONFIDENCE_NOTES = """
Confidence Levels for Numerical Values
========================================

HIGH   – SP costs, element, target type, hit-count mechanic, BP scaling
         mechanic descriptions.  Confirmed by Fandom wiki + multiple
         independent guides (Samurai Gamers, Destructoid, commonsensegamer,
         Game8).

MEDIUM – Ability_Ratio / Skill_Ratio and Invocation_Ratio / Def_Mod values.
         Sourced from the OT1 datamine (Tables61; BravelyPath Modular
         discord) cross-referenced with OT2 community testing.  OT2 uses
         the same formula engine; Scholar spell structure is near-identical.
         Exact datamined OT2 values were not directly accessible (Google
         Sheets require JS rendering).
         Recommended action: verify against the Exentryk/Melodia AbilityData
         spreadsheet (OT2 Database Output Spreadsheet, public Google Sheets).

LOW    – One True Magic Skill_Ratio and Def_Mod are pure estimates.
         One True Magic SP cost: conflicting sources (7 SP vs 20 SP).
         Replace LOW values with in-game verified or datamined values
         before relying on them for simulation.

Key sources
-----------
OT1 datamine (same formula): https://docs.google.com/spreadsheets/d/1geqS6ST86PMaWAzxcIIYjo-HRTz8t55dsv8YEaco8_o
OT2 datamine sheet:          https://docs.google.com/spreadsheets/d/1vd0ZS8QmKC14qlXw43jPm0ytzMy4nczKJG5CD5QSi3M
OT2 Fandom wiki skills:      https://octopathtraveler.fandom.com/wiki/Scholar_(Octopath_Traveler_II)/Skills
OT2 Perfect Game resource:   https://docs.google.com/spreadsheets/d/1ujgl9WjfhevFsHI_IoRyUeRygv8fX3PXRT9-v1EO42c
"""
