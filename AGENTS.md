# AI Agent Guide: OT2-Optimizer

## Project Summary

**OT2-Optimizer** is a Python-first equipment optimizer for Octopath Traveler 2. It recommends character gear upgrades based on current stats, level, story progression (unlocked locations), budget, and class-specific priorities.

- **Scope**: Single-character optimization (no roster-wide optimization yet)
- **Runtime**: Python stdlib only—no external dependencies for CLI/core
- **Interfaces**: CLI, browser-based GUI (port 8000), Jupyter notebooks
- **Output**: JSON results + color-coded HTML report

## Quick Start

### Setup
```bash
source .venv/bin/activate  # Existing venv with all setup complete
```

### Run CLI
```bash
python -m ot2_optimizer.cli --config configs/one_character.example.json
```

### Run GUI
```bash
python -m ot2_optimizer.gui  # Opens http://127.0.0.1:8000
```

### Generate Config
```bash
python -m ot2_optimizer.cli --generate-config Osvald  # Default class
python -m ot2_optimizer.cli --generate-config Hikari Warrior 18  # Specific class + level
```

## Architecture

| Module | Purpose | Key Exports |
|--------|---------|-------------|
| [models.py](ot2_optimizer/models.py) | Data structures | `EquipmentItem`, `CandidateScore`, `CharacterResult`, stat/category constants |
| [data_loader.py](ot2_optimizer/data_loader.py) | Load game data | Parses `categories/*.json`, CSV store prices; normalizes item names |
| [optimizer.py](ot2_optimizer/optimizer.py) | **Core optimization logic** | `optimize_loadout()` — combo-optimization + survivability penalties |
| [scoring.py](ot2_optimizer/scoring.py) | Score items per class | `score_item()` — stat priority + effect value |
| [rules.py](ot2_optimizer/rules.py) | Parse equipment effects | `parse_effect_tags()` — maps text to tag IDs (fire_potency, sp_sustain, etc.) |
| [templates.py](ot2_optimizer/templates.py) | Class-specific behavior | Stat/effect priorities per class; config templates |
| [availability.py](ot2_optimizer/availability.py) | Filter by source/budget/location | `available_equipment()` |
| [cli.py](ot2_optimizer/cli.py) | Command-line interface | Main entry; parses args, calls optimizer, formats output |
| [gui.py](ot2_optimizer/gui.py) | Browser UI | Local server; form → optimizer → HTML result |
| [report.py](ot2_optimizer/report.py) | HTML report generation | Stat tables, deltas, candidate rankings |

## Data Flow

```
JSON Config
  ↓
Load base stats (data/Octopath_Traveler2_Resource_Stats.csv)
  ↓
Load equipment (categories/*.json + store prices from CSV)
  ↓
Filter by availability (location, source type, budget)
  ↓
Score candidates per slot (class priorities + effect tags)
  ↓
Combo-optimize loadout (slot interdependencies + survivability)
  ↓
JSON Result + HTML Report
```

## Development Conventions

- **No domain logic classes**: Use dataclasses for data only. Logic stays functional.
- **Type hints everywhere**: `from __future__ import annotations` at file top.
- **Visual section markers**: `# ─── Section Name ────` to break up logic.
- **Naming**: `lowercase_underscore` for stats, tags, categories. PascalCase for classes only.
- **No external dependencies**: Stdlib only (core + CLI). GUI uses no deps either.
- **Config format**: JSON objects with string keys; see [one_character.example.json](configs/one_character.example.json) or [hikari.example.json](configs/hikari.example.json).

## Key Patterns

### Adding a New Stat or Category
1. Add constant to [models.py](ot2_optimizer/models.py): `STATS`, `CATEGORIES`.
2. Update parsing in [data_loader.py](ot2_optimizer/data_loader.py) if loading from game data.
3. Add default weights in [templates.py](ot2_optimizer/templates.py) for each class.

### Changing Scoring Logic
- Weights/priorities → [templates.py](ot2_optimizer/templates.py)
- Effect parsing → [rules.py](ot2_optimizer/rules.py)
- Scoring formula → [scoring.py](ot2_optimizer/scoring.py)
- Survivability floor → [optimizer.py](ot2_optimizer/optimizer.py)

### Adding a New Traveler or Class
1. Add base stats to `data/Octopath_Traveler2_Resource_Stats.csv`.
2. Add priorities/survival rules to [templates.py](ot2_optimizer/templates.py).
3. Test via CLI with `--generate-config`.

## Input/Output Specs

### Config JSON
Required fields: `character`, `class`, `level`, `current_equipment`.
Optional: `locations` (available map areas), `budget` (gold max), `source_types` (store/chest/quest/etc.).

See [one_character.example.json](configs/one_character.example.json) for full schema.

### Result JSON
Contains optimized loadout + stat deltas from current gear.
Path: `reports/{config_name}.result.json`.

### HTML Report
Color-coded stat changes, equipment swaps, alternative candidates per slot.
Path: `reports/{config_name}.report.html` — open in browser.

## Critical Files & Data

| Path | Purpose | Notes |
|------|---------|-------|
| `categories/*.json` | Equipment definitions | Parsed from CSV; one file per category |
| `data/Octopath_Traveler2_Resource_Stats.csv` | Base stats per traveler/class/level | Required at runtime |
| `data/Octopath_Traveler2_Resource_Store.csv` | Equipment prices | Required for availability |
| `configs/*.json` | User configs (input) | Example: one_character.example.json |
| `reports/*.json` | Optimizer output | One per config run |
| `reports/*.html` | User-facing report | Generated by report.py |

## Common Pitfalls

1. **Item name mismatch**: Data loader normalizes names (spaces, case). Check [data_loader.py](ot2_optimizer/data_loader.py) `_normalize_item_name()` if lookups fail.
2. **Missing locations**: Availability filters by location; if a location isn't in the config, those items are skipped.
3. **Survivability violations**: Optimizer penalizes loadouts that drop below class-specific defense/HP minimums. Check [templates.py](ot2_optimizer/templates.py) for `survive_*` keys.
4. **CSV path changes**: Game data is baked in `data/`. If the CSV structure changes (column names, rows), update [data_loader.py](ot2_optimizer/data_loader.py) parsing.

## Testing

No automated test suite exists. Validation is manual:
- Run CLI with example configs; inspect JSON + HTML output.
- GUI form submission → verify result matches manual calculation.
- Notebooks in [notebooks/](notebooks/) for one-off analysis.

## Session Skills

This workspace includes [caveman-mode skills](/.agents/skills/) for context-efficient work:
- `caveman`: Compressed communication (~75% token reduction)
- `caveman-commit`: Ultra-brief commit messages
- `caveman-review`: One-line PR feedback
- Use `/caveman-mode` or `/caveman-stats` to toggle/monitor.

---

**Last Updated**: 2026-05-14  
**For Questions**: Check README.md or explore the module docstrings.
