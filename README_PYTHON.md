# OT2 Python Optimizer

This is the Python-first restart of the optimizer. It is intentionally separate
from the existing TypeScript GUI so the optimizer logic can survive even if the
old app directory is deleted later.

## What Exists Now

- One-character optimizer first.
- Editable JSON config for level, naked stats, current gear, locations, source
  types, priorities, and effect values.
- Strict availability filtering. Unknown availability is excluded by default.
- Current gear is used as the baseline, so recommendations are based on actual
  improvement, not just absolute item stats.
- Accessories are categorized for manual review instead of blindly optimized.
- HTML report output gives lightweight visualization without extra packages.

## v1 Manual Testing

This is ready for in-game manual testing on one character at a time.

- Generate a starter config for any of the 8 travelers with
  `python -m ot2_optimizer.cli --generate-config CHARACTER`.
- Edit `configs/one_character.example.json` or a generated config, then run
  `python -m ot2_optimizer.cli --config <path>`.
- The optimizer handles all 8 original-class travelers, but it still outputs
  one character's gear plan per run.
- Roster-wide conflict solving is not in v1 yet.

## Run

```bash
python -m ot2_optimizer.cli --config configs/one_character.example.json
```

Outputs:

- `reports/one_character.result.json`
- `reports/one_character.report.html`

## Edit The Input

Change this file:

```text
configs/one_character.example.json
```

Important fields:

- `level`: character level.
- `naked_stats`: your stats with no equipment. If this is omitted, the optimizer
  loads base stats for `character` + `level` from
  `Octopath Traveler 2 Resource - Stats.csv`.
- `current_equipment`: what you currently wear.
- `progression.allowed_locations`: towns/areas currently available.
- `progression.allowed_source_types`: usually start with only `["store"]`.
- `progression.budget`: maximum new purchase cost for the recommendation.
- `progression.allow_unknown_prices`: defaults to false behavior in the optimizer;
  unknown-price paid items are not treated as free when a budget exists.
- `priorities`: how much this character values each stat/effect.
- `effect_values`: base point values for special effects.
- `minimum_priorities`: stat floors that still matter even when they are not the
  character's main job-defining stat. This prevents defense from becoming
  worthless on offense-focused characters.
- `survivability_targets`: final stat targets for the whole recommended loadout.
  This lets the optimizer trade down damage if keeping a weak shield/armor leaves
  the character too fragile.

## Source Types

Use these in `allowed_source_types`:

- `store`
- `chest`
- `npc`
- `quest`
- `drop`
- `other`

For a fresh or early run, `["store"]` is the least surprising option.

## Accessory Model

Accessories are not optimized automatically yet. The report groups them into:

- `overpowered_manual`
- `situational`
- `economy_farming`
- `generic_good`
- `niche`

That keeps broken or situational accessories visible without forcing fake numeric
scores onto things like elemental resistance, EXP/JP gain, leaves gain, or status
immunity.

## Next Milestones

1. Make the one-character report feel correct.
2. Improve effect and accessory rules with manual review.
3. Add budget-aware item selection.
4. Add whole-roster optimization and limited-copy conflict handling.
5. Add a CLI config for multiple characters.
