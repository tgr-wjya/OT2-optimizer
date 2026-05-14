# OT2 Python Optimizer

This is the Python-first restart of the optimizer. It is intentionally separate
from the existing TypeScript GUI so the optimizer logic can survive even if the
old app directory is deleted later.

For local setup and usage, start with [README.md](README.md).

## What Exists Now

- One-character optimizer first.
- Minimal config surface for the default workflow.
- Class-specific scoring and survivability behavior are automatic.
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

Start from `configs/one_character.example.json` or a generated config.

Important fields:

- `character`: the traveler name.
- `class`: original class for that traveler.
- `level`: character level.
- `current_equipment`: set to `null` for a naked baseline.
- `progression.allowed_locations`: towns and areas currently available.
- `progression.allowed_source_types`: usually start with only `["store"]`.
- `progression.budget`: maximum new purchase cost for the recommendation.

If `current_equipment` is `null`, the optimizer loads naked base stats from
`Octopath Traveler 2 Resource - Stats.csv` automatically.

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
5. Add a local browser GUI on top of the Python engine.
