# OT2 Optimizer

Python-first equipment optimizer for Octopath Traveler 2.

This repo is focused on one-character optimization first. It uses your current
character level, naked base stats, current gear, available locations, and budget
to recommend equipment from the local game data files.

## What It Does

- Optimizes one character per run.
- Supports all 8 original-class travelers.
- Uses current gear as the baseline, so recommendations are upgrades from what
  you actually have equipped.
- Auto-loads class-specific scoring and survivability behavior internally.
- Filters by availability and source type.
- Treats accessories as review items instead of auto-equipping them blindly.
- Writes both JSON output and an HTML report.

## Local Setup

The optimizer code uses only the Python standard library at runtime.

If you already have the repo checked out, the simplest path is to use the
included virtual environment:

```bash
source .venv/bin/activate
```

If you want to create a fresh environment instead, use:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

No additional runtime packages are required for the CLI.

Optional notebook support:

```bash
python -m pip install jupyter matplotlib
```

## Run The Optimizer

The default example config is:

`configs/one_character.example.json`

Run it with:

```bash
python -m ot2_optimizer.cli --config configs/one_character.example.json
```

This writes:

- `reports/one_character.result.json`
- `reports/one_character.report.html`

## Generate A Starter Config

You can generate a starting config for any traveler and class:

```bash
python -m ot2_optimizer.cli --generate-config Osvald
python -m ot2_optimizer.cli --generate-config Hikari Warrior 18
```

To save the generated config to a file:

```bash
python -m ot2_optimizer.cli --generate-config Osvald --config-out configs/osvald.json
```

If you do not pass a class, the CLI uses the traveler’s default class.
If you do not pass a level, the CLI uses level 1.

## Edit Your Config

Start from `configs/one_character.example.json` or a generated config and edit:

- `character`: the traveler name.
- `class`: original class for that traveler.
- `level`: current character level.
- `current_equipment`: set to `null` for a naked baseline.
- `progression.allowed_locations`: towns and areas you can already reach.
- `progression.allowed_source_types`: usually start with `store` only.
- `progression.budget`: how many leaves you want to spend.

If `current_equipment` is `null`, the optimizer uses naked base stats from
`Octopath Traveler 2 Resource - Stats.csv`.

## One-Character Testing Workflow

Use this for manual in-game testing:

1. Pick one traveler.
2. Generate or edit a config for that traveler.
3. Set the locations, source types, and budget to match your current save.
4. Run the CLI.
5. Equip the recommended items in game and compare the result.

The current version is intentionally one-character focused. It does support all
8 travelers, but it does not yet solve shared equipment conflicts across a full
roster.

## Notebook

The notebook in `notebooks/01_one_character_optimizer.ipynb` is a thin
visualization layer around the same Python modules.

Open it with Jupyter and run the cells after editing the example config.

## Data Files

The optimizer reads local project data from:

- `categories/`
- `Octopath Traveler 2 Resource - Stats.csv`
- `Octopath Traveler 2 Resource - Store.csv`

Those files are required for normal runs.

## Outputs

The CLI writes both machine-readable and human-readable results:

- JSON: `reports/one_character.result.json`
- HTML: `reports/one_character.report.html`

## Repo Layout

- `ot2_optimizer/` - Python optimizer package
- `configs/` - example and generated configs
- `notebooks/` - notebook-based inspection workflow
- `reports/` - generated output
- `categories/` - item data by category

## Troubleshooting

If the CLI cannot find data files, make sure you are running commands from the
repo root.

If the notebook cannot import the package, add the repo root to `sys.path` or
start Jupyter from the repository directory.

If you change the config and the report still looks stale, rerun the CLI so the
JSON and HTML outputs regenerate.

## Current Scope

This repo is ready for one-character manual testing. Roster-wide conflict
resolution is a later step.