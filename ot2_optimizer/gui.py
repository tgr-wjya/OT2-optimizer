from __future__ import annotations

import argparse
import json
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from .data_loader import load_equipment, project_root
from .models import STAT_KEYS
from .optimizer import optimize_character
from .templates import CHARACTER_DEFAULT_CLASS, list_characters, list_classes

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
DEFAULT_EXAMPLE_CONFIG = {
    "character": "Osvald",
    "class": "Scholar",
    "level": 18,
    "progression": {
        "allowed_locations": [
            "New Delsta",
            "Canalbrine",
            "Beasting Village",
            "Ryu",
            "Flamechurch",
            "Oresrush",
            "Cropdale",
            "Cape Cold",
        ],
        "allowed_source_types": ["store"],
        "include_unknown_availability": False,
        "budget": 25000,
    },
    "current_equipment": None,
    "owned_inventory": None,
    "respect_other_characters": False,
    "reserved_inventory": None,
    "naked_stats": {},
}


def _unique_locations(items) -> list[str]:
    locations = set()
    for item in items:
        for source in item.sources:
            if source.location:
                locations.add(source.location)
    for regions in CHARACTER_STARTING_REGION_VALUES.values():
        locations.update(regions)
    return sorted(locations)


def _slot_options(items, slot: str) -> list[str]:
    return sorted({item.name for item in items if item.slot == slot})


def _load_default_config() -> dict[str, Any]:
    config_path = project_root() / "configs" / "one_character.example.json"
    if config_path.exists():
        try:
            return json.loads(config_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return dict(DEFAULT_EXAMPLE_CONFIG)


def _load_gui_state() -> dict[str, Any]:
    items = load_equipment(project_root())
    default_config = _load_default_config()
    return {
        "characters": list_characters(),
        "classes": list_classes(),
        "default_class_by_character": CHARACTER_DEFAULT_CLASS,
        "default_config": default_config,
        "starting_regions": CHARACTER_STARTING_REGION_VALUES,
        "locations": _unique_locations(items),
        "weapon_options": _slot_options(items, "weapon"),
        "shield_options": _slot_options(items, "shield"),
        "headgear_options": _slot_options(items, "headgear"),
        "body_armor_options": _slot_options(items, "body_armor"),
        "accessory_options": _slot_options(items, "accessory"),
    }


CHARACTER_STARTING_REGION_VALUES = {
    "Osvald": ["Cape Cold", "New Delsta"],
    "Temenos": ["Flamechurch", "Oresrush"],
    "Hikari": ["Ryu", "Sai"],
    "Throné": ["Oresrush", "New Delsta"],
    "Ochette": ["Beasting Village", "Ryu"],
    "Castti": ["Canalbrine", "New Delsta"],
    "Agnea": ["Cropdale", "New Delsta"],
    "Partitio": ["Oresrush", "New Delsta"],
}


def _default_class_for(character: str) -> str:
    return CHARACTER_DEFAULT_CLASS.get(character, "Scholar")


def _equipment_payload(form_data: dict[str, Any]) -> dict[str, str] | None:
    equipment = {}
    for slot in ("weapon", "shield", "headgear", "body_armor", "accessory1", "accessory2"):
        value = str(form_data.get(slot, "")).strip()
        if value:
            equipment[slot] = value
    return equipment or None


def _naked_stats_payload(payload: dict[str, Any]) -> dict[str, int] | None:
    raw_stats = payload.get("naked_stats")
    if isinstance(raw_stats, dict):
        source = raw_stats
    else:
        source = {stat: payload.get(f"naked_{stat}", "") for stat in STAT_KEYS}

    naked_stats: dict[str, int] = {}
    for stat in STAT_KEYS:
        value = str(source.get(stat, "")).strip()
        if not value:
            continue
        parsed = int(value)
        if parsed < 0:
            raise ValueError(f"naked stat {stat} must be >= 0")
        naked_stats[stat] = parsed
    return naked_stats or None


def _locations_payload(raw_locations: str) -> list[str]:
    return [part.strip() for part in raw_locations.replace("\n", ",").split(",") if part.strip()]


def _inventory_payload(payload: dict[str, Any], key: str) -> list[dict[str, Any]] | None:
    raw = payload.get(key)
    if raw is None:
        return None
    if not isinstance(raw, list):
        raise ValueError(f"{key} must be a list")

    inventory: list[dict[str, Any]] = []
    for idx, entry in enumerate(raw):
        if isinstance(entry, str):
            name = entry.strip()
            if not name:
                continue
            inventory.append({"name": name, "quantity": 1})
            continue
        if not isinstance(entry, dict):
            raise ValueError(f"{key}[{idx}] must be object or string")
        name = str(entry.get("name") or entry.get("item") or "").strip()
        if not name:
            raise ValueError(f"{key}[{idx}] missing name/item")
        quantity_raw = entry.get("quantity", 1)
        try:
            quantity = int(quantity_raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{key}[{idx}].quantity must be integer >= 1") from exc
        if quantity < 1:
            raise ValueError(f"{key}[{idx}].quantity must be integer >= 1")
        payload_entry = {"name": name, "quantity": quantity}
        category = entry.get("category")
        if category is not None and str(category).strip():
            payload_entry["category"] = str(category).strip()
        inventory.append(payload_entry)
    return inventory or None


def _parse_json_body(body: bytes) -> dict[str, Any]:
    if not body:
        return {}
    return json.loads(body.decode("utf-8"))


def _build_config(payload: dict[str, Any]) -> dict[str, Any]:
    character = str(payload.get("character", "Osvald"))
    level = int(payload.get("level", 1) or 1)
    budget_raw = str(payload.get("budget", "")).strip()
    budget = int(budget_raw) if budget_raw else None
    no_leaves_mode = budget == 0
    owned_inventory = _inventory_payload(payload, "owned_inventory")
    reserved_inventory = _inventory_payload(payload, "reserved_inventory")
    respect_other_characters = bool(payload.get("respect_other_characters", False))
    config = {
        "character": character,
        "class": _default_class_for(character),
        "level": level,
        "progression": {
            "allowed_locations": _locations_payload(str(payload.get("allowed_locations", ""))),
            "allowed_source_types": [
                value
                for value in (payload.get("allowed_source_types") or [])
                if value
            ],
            "include_unknown_availability": False,
            "budget": budget,
        },
        "current_equipment": _equipment_payload(payload),
        "owned_inventory": owned_inventory,
        "respect_other_characters": respect_other_characters,
        "reserved_inventory": reserved_inventory if respect_other_characters else None,
    }
    naked_stats = _naked_stats_payload(payload)
    if naked_stats is not None:
        config["naked_stats"] = naked_stats
    if no_leaves_mode:
        config["progression"]["allowed_source_types"] = []
    elif not config["progression"]["allowed_source_types"]:
        config["progression"]["allowed_source_types"] = ["store"]
    return config


def _json_response(handler: BaseHTTPRequestHandler, payload: dict[str, Any], status: int = 200) -> None:
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(raw)))
    handler.end_headers()
    handler.wfile.write(raw)


def _html_response(handler: BaseHTTPRequestHandler, html: str, status: int = 200) -> None:
    raw = html.encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(raw)))
    handler.end_headers()
    handler.wfile.write(raw)


def _page_html(state: dict[str, Any]) -> str:
    state_json = json.dumps(state, ensure_ascii=False)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>OT2 Optimizer GUI</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #0b1020;
      --panel: rgba(17, 24, 39, 0.86);
      --panel-2: rgba(15, 23, 42, 0.95);
      --line: rgba(148, 163, 184, 0.18);
      --text: #e5e7eb;
      --muted: #94a3b8;
      --accent: #60a5fa;
      --accent-2: #34d399;
      --warn: #fbbf24;
      --danger: #f87171;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at top left, rgba(96, 165, 250, 0.18), transparent 28%),
        radial-gradient(circle at top right, rgba(52, 211, 153, 0.14), transparent 24%),
        linear-gradient(160deg, #070b16 0%, #0b1020 46%, #111827 100%);
      min-height: 100vh;
    }}
    .wrap {{ max-width: 1460px; margin: 0 auto; padding: 28px; }}
    .hero {{
      display: grid;
      grid-template-columns: 1.15fr 0.85fr;
      gap: 18px;
      align-items: end;
      margin-bottom: 18px;
    }}
    .title {{ font-size: clamp(2rem, 5vw, 3.4rem); margin: 0; line-height: 1.02; }}
    .subtitle {{ margin: 10px 0 0; color: var(--muted); max-width: 70ch; }}
    .pill {{ display: inline-flex; gap: .4rem; align-items: center; padding: .35rem .7rem; border: 1px solid var(--line); border-radius: 999px; color: #dbeafe; background: rgba(96, 165, 250, 0.09); font-size: .82rem; }}
    .grid {{ display: grid; grid-template-columns: 390px 1fr; gap: 18px; }}
    .panel {{ background: var(--panel); border: 1px solid var(--line); border-radius: 18px; box-shadow: 0 24px 80px rgba(0,0,0,.25); backdrop-filter: blur(12px); }}
    .panel .inner {{ padding: 18px; }}
    .section-title {{ margin: 0 0 12px; font-size: .96rem; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); }}
    label {{ display: block; font-size: .86rem; color: #cbd5e1; margin-bottom: 6px; }}
    input, select, textarea {{
      width: 100%;
      border: 1px solid rgba(148, 163, 184, 0.22);
      border-radius: 12px;
      background: rgba(2, 6, 23, 0.7);
      color: var(--text);
      padding: 10px 12px;
      font: inherit;
      outline: none;
    }}
    textarea {{ min-height: 94px; resize: vertical; }}
    input:focus, select:focus, textarea:focus {{ border-color: rgba(96, 165, 250, 0.8); box-shadow: 0 0 0 3px rgba(96, 165, 250, 0.14); }}
    .field {{ margin-bottom: 14px; }}
    .row2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
    .row3 {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; }}
    .budget-row {{ display: grid; gap: 8px; }}
    .budget-toggle {{ display: inline-flex; gap: 8px; align-items: center; font-size: .9rem; color: var(--text); }}
    .budget-toggle input {{ width: auto; }}
    .source-grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px 10px; }}
    .source-grid label {{ margin: 0; display: flex; gap: 8px; align-items: center; font-size: .9rem; color: var(--text); }}
    .source-grid input {{ width: auto; }}
    .slot-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
    .naked-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }}
    .hint {{ color: var(--muted); font-size: .82rem; margin-top: 6px; }}
    .button-row {{ display: flex; gap: 10px; margin-top: 10px; flex-wrap: wrap; }}
    button {{
      border: 0;
      border-radius: 12px;
      padding: 11px 16px;
      font: inherit;
      font-weight: 700;
      cursor: pointer;
    }}
    .primary {{ background: linear-gradient(135deg, var(--accent), #7c3aed); color: white; }}
    .secondary {{ background: rgba(148, 163, 184, 0.16); color: var(--text); border: 1px solid var(--line); }}
    .status {{ margin-top: 10px; color: var(--muted); font-size: .88rem; min-height: 1.4em; }}
    .results {{ display: grid; gap: 14px; }}
    .hero-card {{ padding: 18px; border-bottom: 1px solid var(--line); background: linear-gradient(180deg, rgba(96,165,250,.08), transparent); border-radius: 18px 18px 0 0; }}
    .hero-metrics {{ display: flex; gap: 14px; flex-wrap: wrap; margin-top: 10px; }}
    .metric {{ padding: 12px 14px; border-radius: 14px; background: rgba(2,6,23,.48); border: 1px solid rgba(148,163,184,.15); min-width: 0; flex: 1 1 180px; }}
    .metric .k {{ display: block; color: var(--muted); font-size: .78rem; text-transform: uppercase; letter-spacing: .08em; }}
    .metric .v {{ font-size: 1.2rem; font-weight: 800; margin-top: 6px; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ text-align: left; padding: 9px 10px; border-bottom: 1px solid rgba(148,163,184,.14); vertical-align: top; }}
    th {{ color: #cbd5e1; font-size: .8rem; text-transform: uppercase; letter-spacing: .08em; }}
    .card {{ padding: 16px; border: 1px solid var(--line); border-radius: 16px; background: var(--panel-2); }}
    .card h3 {{ margin: 0 0 10px; font-size: 1rem; }}
    .slot-grid-result {{ display: grid; grid-template-columns: 1fr; gap: 12px; }}
    .slot-badge {{ display: inline-flex; align-items: center; gap: 6px; padding: .28rem .55rem; border-radius: 999px; background: rgba(52,211,153,.12); color: #a7f3d0; font-size: .78rem; border: 1px solid rgba(52,211,153,.2); }}
    .slot-badge {{ max-width: 100%; white-space: normal; }}
    .muted {{ color: var(--muted); }}
    details {{ border: 1px solid rgba(148,163,184,.14); border-radius: 12px; padding: 10px 12px; background: rgba(2,6,23,.35); }}
    details + details {{ margin-top: 10px; }}
    summary {{ cursor: pointer; font-weight: 700; color: #e2e8f0; }}
    .error {{ color: #fecaca; background: rgba(127, 29, 29, .24); border: 1px solid rgba(248, 113, 113, .32); padding: 10px 12px; border-radius: 12px; white-space: pre-wrap; }}
    .loading {{ opacity: .75; pointer-events: none; }}
    .tiny {{ font-size: .82rem; color: var(--muted); }}
    .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 10px; }}
    .stat-box {{ padding: 10px 12px; border-radius: 12px; background: rgba(2,6,23,.38); border: 1px solid rgba(148,163,184,.12); }}
    .stat-box .n {{ display:block; color: var(--muted); font-size: .75rem; text-transform: uppercase; letter-spacing: .08em; }}
    .stat-box .v {{ display:block; margin-top: 4px; font-size: 1rem; font-weight: 700; }}
    .badge {{ display:inline-block; margin-left: 6px; padding: .18rem .42rem; border-radius: 999px; background: rgba(96,165,250,.16); color: #bfdbfe; font-size: .72rem; }}
    .list {{ margin: 0; padding-left: 1.1rem; }}
    .list li {{ margin: .28rem 0; }}
    .candidate-list {{ display: grid; gap: 10px; }}
    .candidate-row {{ padding: 12px; border: 1px solid rgba(148,163,184,.14); border-radius: 12px; background: rgba(2,6,23,.35); }}
    .candidate-row .meta {{ display: flex; gap: 8px; flex-wrap: wrap; align-items: baseline; margin-bottom: 6px; }}
    .candidate-row .rank {{ font-weight: 800; color: #dbeafe; }}
    .candidate-row .name {{ font-weight: 700; }}
    .candidate-row .tiny {{ margin-top: 4px; }}
    @media (max-width: 1080px) {{
      .hero, .grid {{ grid-template-columns: 1fr; }}
      .source-grid, .slot-grid {{ grid-template-columns: 1fr 1fr; }}
    }}
    @media (max-width: 680px) {{
      .wrap {{ padding: 16px; }}
      .source-grid, .slot-grid, .row2, .row3 {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="hero">
      <div>
        <div class="pill">Local browser app · Python engine</div>
        <h1 class="title">OT2 Optimizer GUI</h1>
        <p class="subtitle">One-character optimization. No priority tuning. No damage sim in the default flow. Pick a traveler, leave gear blank for a naked baseline, and run the optimizer directly in your browser.</p>
      </div>
      <div class="panel">
        <div class="inner">
          <div class="section-title">Current Defaults</div>
          <div class="tiny">Traveler: <strong id="default-char">Osvald</strong></div>
          <div class="tiny">Class: <strong id="default-class">Scholar</strong></div>
          <div class="tiny">Base locations: <strong id="default-locations">New Delsta, Canalbrine, Beasting Village, Ryu, Flamechurch, Oresrush, Cropdale, Cape Cold</strong></div>
        </div>
      </div>
    </div>

    <div class="grid">
      <div class="panel">
        <div class="inner">
          <div class="section-title">Build</div>
          <form id="opt-form">
            <div class="row2">
              <div class="field">
                <label for="character">Traveler</label>
                <select id="character" name="character"></select>
              </div>
              <div class="field">
                <label>Class</label>
                <input id="class" name="class" type="text" readonly>
              </div>
            </div>
            <div class="row2">
              <div class="field">
                <label for="level">Level</label>
                <input id="level" name="level" type="number" min="1" max="99" value="18">
              </div>
              <div class="field">
                <label for="budget">Budget</label>
                <div class="budget-row">
                  <input id="budget" name="budget" type="number" min="0" placeholder="Leave blank for unlimited">
                  <label class="budget-toggle" for="no_leaves">
                    <input id="no_leaves" name="no_leaves" type="checkbox">
                    I don't have any leaves
                  </label>
                </div>
              </div>
            </div>
            <div class="field" id="locations-field">
              <label for="allowed_locations">Allowed locations</label>
              <textarea id="allowed_locations" name="allowed_locations" placeholder="Comma or newline separated towns / areas"></textarea>
              <div class="hint">Leave as-is for a quick test. Blank locations are allowed, but the optimizer becomes more restrictive.</div>
            </div>
            <div class="field" id="source-types-field">
              <label>Allowed source types</label>
              <div class="source-grid" id="source-types"></div>
            </div>
            <div class="field">
              <label>Current equipment</label>
              <div class="slot-grid">
                <div><label for="weapon">Weapon</label><input id="weapon" name="weapon" list="weapon-list" placeholder="Leave blank for naked"></div>
                <div><label for="shield">Shield</label><input id="shield" name="shield" list="shield-list" placeholder="Leave blank for naked"></div>
                <div><label for="headgear">Headgear</label><input id="headgear" name="headgear" list="headgear-list" placeholder="Leave blank for naked"></div>
                <div><label for="body_armor">Body armor</label><input id="body_armor" name="body_armor" list="body-armor-list" placeholder="Leave blank for naked"></div>
                <div><label for="accessory1">Accessory 1</label><input id="accessory1" name="accessory1" list="accessory-list" placeholder="Optional"></div>
                <div><label for="accessory2">Accessory 2</label><input id="accessory2" name="accessory2" list="accessory-list" placeholder="Optional"></div>
              </div>
              <div class="hint">Leave every slot blank to test from naked stats.</div>
            </div>
            <div class="field">
              <label for="owned_inventory">Owned inventory (used in no-leaves mode)</label>
              <textarea id="owned_inventory" name="owned_inventory" placeholder="One per line: Item Name|Quantity&#10;Example: Silver Sword|2"></textarea>
              <label class="budget-toggle" for="respect_other_characters" style="margin-top:8px">
                <input id="respect_other_characters" name="respect_other_characters" type="checkbox">
                Exclude copies equipped by other characters
              </label>
              <textarea id="reserved_inventory" name="reserved_inventory" placeholder="Reserved by other characters (Item Name|Quantity)" style="margin-top:8px"></textarea>
              <div class="hint">When no-leaves is enabled, recommendations come only from this inventory list.</div>
            </div>
            <div class="field">
              <label>Custom naked base stats</label>
              <div class="naked-grid" id="naked-stats"></div>
              <div class="hint">Leave blank to use loaded CSV stats. Fill values to override the naked baseline.</div>
            </div>
            <div class="button-row">
              <button class="primary" type="submit">Run optimizer</button>
              <button class="secondary" type="button" id="reset-btn">Load example</button>
            </div>
            <div id="status" class="status">Ready.</div>
          </form>
        </div>
      </div>

      <div class="results panel">
        <div class="hero-card">
          <div class="section-title">Results</div>
          <div id="results-summary" class="muted">Run the optimizer to see recommended gear.</div>
        </div>
        <div class="inner" id="results"></div>
      </div>
    </div>
  </div>

  <datalist id="weapon-list"></datalist>
  <datalist id="shield-list"></datalist>
  <datalist id="headgear-list"></datalist>
  <datalist id="body-armor-list"></datalist>
  <datalist id="accessory-list"></datalist>

  <script>
    const GUI = {state_json};
    const STAT_KEYS = ["hp","sp","phys_atk","elem_atk","phys_def","elem_def","speed","accuracy","evasion","critical"];
    const SOURCE_TYPES = ["store","chest","npc","quest","drop","other"];

    const els = {{
      form: document.getElementById('opt-form'),
      status: document.getElementById('status'),
      results: document.getElementById('results'),
      summary: document.getElementById('results-summary'),
      character: document.getElementById('character'),
      className: document.getElementById('class'),
      level: document.getElementById('level'),
      budget: document.getElementById('budget'),
      noLeaves: document.getElementById('no_leaves'),
      allowedLocations: document.getElementById('allowed_locations'),
      locationsField: document.getElementById('locations-field'),
      sourceTypesField: document.getElementById('source-types-field'),
      ownedInventory: document.getElementById('owned_inventory'),
      reservedInventory: document.getElementById('reserved_inventory'),
      respectOtherCharacters: document.getElementById('respect_other_characters'),
      resetBtn: document.getElementById('reset-btn'),
      sourceTypes: document.getElementById('source-types'),
      defaultChar: document.getElementById('default-char'),
      defaultClass: document.getElementById('default-class'),
      defaultLocations: document.getElementById('default-locations'),
      nakedStats: document.getElementById('naked-stats'),
    }};

    function escapeHtml(text) {{
      return String(text)
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#39;');
    }}

    function setStatus(text, kind = 'info') {{
      els.status.textContent = text;
      els.status.className = 'status' + (kind === 'error' ? ' error' : '');
    }}

    function defaultClassFor(character) {{
      return GUI.default_class_by_character[character] || 'Scholar';
    }}

    function defaultLocationsFor(character) {{
      const regions = GUI.starting_regions[character] || [];
      return regions.join(', ');
    }}

    function fillCharacterOptions() {{
      els.character.innerHTML = GUI.characters.map((character) => `
        <option value="${{escapeHtml(character)}}">${{escapeHtml(character)}}</option>
      `).join('');
      els.character.value = GUI.default_config.character || GUI.characters[0];
    }}

    function fillSourceTypes() {{
      els.sourceTypes.innerHTML = SOURCE_TYPES.map((source) => `
        <label><input type="checkbox" name="source_type" value="${{source}}" ${{source === 'store' ? 'checked' : ''}}> ${{source}}</label>
      `).join('');
    }}

    function fillNakedStats() {{
      els.nakedStats.innerHTML = STAT_KEYS.map((stat) => `
        <div>
          <label for="naked_${{stat}}">${{escapeHtml(stat)}}</label>
          <input id="naked_${{stat}}" name="naked_${{stat}}" type="number" min="0" step="1" placeholder="Use CSV default">
        </div>
      `).join('');
    }}

    function fillDatalist(id, values) {{
      document.getElementById(id).innerHTML = values.map((value) => `<option value="${{escapeHtml(value)}}"></option>`).join('');
    }}

    function parseInventoryTextarea(text) {{
      const lines = String(text || '').split('\\n').map((line) => line.trim()).filter(Boolean);
      const inventory = [];
      for (const line of lines) {{
        const parts = line.split('|').map((part) => part.trim());
        if (!parts[0]) continue;
        const quantity = parts.length > 1 ? Number(parts[1]) : 1;
        if (!Number.isInteger(quantity) || quantity < 1) {{
          throw new Error(`Invalid inventory quantity in line: "${{line}}"`);
        }}
        inventory.push({{ name: parts[0], quantity }});
      }}
      return inventory;
    }}

    function formatInventoryTextarea(entries) {{
      if (!Array.isArray(entries)) return '';
      return entries
        .map((entry) => {{
          const name = String(entry?.name || entry?.item || '').trim();
          const qty = Number(entry?.quantity || 1);
          if (!name) return '';
          return `${{name}}|${{Number.isInteger(qty) && qty > 0 ? qty : 1}}`;
        }})
        .filter(Boolean)
        .join('\\n');
    }}

    function syncBudgetMode() {{
      const noLeaves = els.noLeaves.checked;
      els.budget.disabled = noLeaves;
      if (noLeaves) {{
        els.budget.value = '';
      }}
      els.allowedLocations.disabled = noLeaves;
      for (const checkbox of document.querySelectorAll('input[name="source_type"]')) {{
        checkbox.disabled = noLeaves;
      }}
      if (els.locationsField) {{
        els.locationsField.style.opacity = noLeaves ? '0.55' : '1';
      }}
      if (els.sourceTypesField) {{
        els.sourceTypesField.style.opacity = noLeaves ? '0.55' : '1';
      }}
      if (els.respectOtherCharacters) {{
        els.respectOtherCharacters.disabled = !noLeaves;
      }}
      if (els.ownedInventory) {{
        els.ownedInventory.disabled = !noLeaves;
      }}
      if (els.reservedInventory) {{
        const reservationOn = noLeaves && els.respectOtherCharacters.checked;
        els.reservedInventory.disabled = !reservationOn;
      }}
    }}

    function resetForm() {{
      const config = GUI.default_config;
      els.character.value = config.character || GUI.characters[0];
      syncCharacter();
      els.level.value = config.level ?? 1;
      const budget = config.progression?.budget;
      els.noLeaves.checked = budget === 0;
      els.budget.value = budget && budget > 0 ? budget : '';
      syncBudgetMode();
      els.allowedLocations.value = (config.progression?.allowed_locations || []).join(', ');
      for (const input of ['weapon', 'shield', 'headgear', 'body_armor', 'accessory1', 'accessory2']) {{
        document.getElementById(input).value = '';
      }}
      for (const checkbox of document.querySelectorAll('input[name="source_type"]')) {{
        checkbox.checked = checkbox.value === 'store';
      }}
      els.ownedInventory.value = formatInventoryTextarea(config.owned_inventory || []);
      els.respectOtherCharacters.checked = !!config.respect_other_characters;
      els.reservedInventory.value = formatInventoryTextarea(config.reserved_inventory || []);
      const nakedStats = config.naked_stats || {{}};
      for (const stat of STAT_KEYS) {{
        document.getElementById(`naked_${{stat}}`).value = nakedStats[stat] ?? '';
      }}
      els.summary.textContent = 'Run the optimizer to see recommended gear.';
      els.results.innerHTML = '';
      setStatus('Loaded example. Leave gear blank for naked baseline.');
    }}

    function syncCharacter() {{
      const character = els.character.value;
      els.className.value = defaultClassFor(character);
      els.defaultChar.textContent = character;
      els.defaultClass.textContent = defaultClassFor(character);
      els.defaultLocations.textContent = defaultLocationsFor(character) || 'No default locations';
    }}

    function collectPayload() {{
      const sourceTypes = Array.from(document.querySelectorAll('input[name="source_type"]:checked')).map((el) => el.value);
      const nakedStats = {{}};
      for (const stat of STAT_KEYS) {{
        const raw = document.getElementById(`naked_${{stat}}`).value.trim();
        if (!raw) continue;
        const value = Number(raw);
        if (!Number.isInteger(value) || value < 0) {{
          throw new Error(`naked stat ${{stat}} must be a whole number >= 0`);
        }}
        nakedStats[stat] = value;
      }}
      const budget = els.noLeaves.checked ? 0 : els.budget.value;
      const ownedInventory = parseInventoryTextarea(els.ownedInventory.value);
      const reservedInventory = parseInventoryTextarea(els.reservedInventory.value);
      return {{
        character: els.character.value,
        level: Number(els.level.value || 1),
        budget,
        allowed_locations: els.allowedLocations.value,
        allowed_source_types: sourceTypes,
        weapon: document.getElementById('weapon').value,
        shield: document.getElementById('shield').value,
        headgear: document.getElementById('headgear').value,
        body_armor: document.getElementById('body_armor').value,
        accessory1: document.getElementById('accessory1').value,
        accessory2: document.getElementById('accessory2').value,
        owned_inventory: ownedInventory,
        respect_other_characters: els.noLeaves.checked ? els.respectOtherCharacters.checked : false,
        reserved_inventory: els.noLeaves.checked && els.respectOtherCharacters.checked ? reservedInventory : [],
        naked_stats: Object.keys(nakedStats).length ? nakedStats : null,
      }};
    }}

    function statGrid(stats, otherStats) {{
      return STAT_KEYS.map((stat) => `
        <div class="stat-box">
          <span class="n">${{escapeHtml(stat)}}</span>
          <span class="v">${{Number(stats?.[stat] || 0).toLocaleString()}}</span>
          <div class="tiny">Δ ${{Number((otherStats?.[stat] || 0) - (stats?.[stat] || 0)).toLocaleString()}}</div>
        </div>
      `).join('');
    }}

    function renderCandidates(candidates) {{
      if (!candidates || !candidates.length) return '<div class="tiny">No candidates.</div>';
      return `
        <div class="candidate-list">
          ${{candidates.map((candidate, index) => `
            <div class="candidate-row">
              <div class="meta">
                <span class="rank">#${{index + 1}}</span>
                <span class="name">${{escapeHtml(candidate.item)}}</span>
                <span class="tiny">${{escapeHtml(candidate.category)}} · score ${{candidate.score.toFixed(2)}} · acq. ${{candidate.acquisition_cost >= 10**9 ? 'N/A' : candidate.acquisition_cost}}</span>
              </div>
              <div class="tiny">${{escapeHtml(Object.entries(candidate.stat_delta || {{}}).map(([k, v]) => `${{k}}:${{v >= 0 ? '+' : ''}}${{v}}`).join('  ') || '—')}}</div>
            </div>
          `).join('')}}
        </div>
      `;
    }}

    function renderRecommendations(result) {{
      const recs = Object.entries(result.recommendations || {{}});
      return recs.map(([slot, score]) => `
        <div class="card">
          <h3>${{escapeHtml(slot.toUpperCase())}} <span class="slot-badge">${{escapeHtml(score.item)}}</span></h3>
          <div class="tiny">${{escapeHtml(score.category)}} · score ${{Number(score.score).toFixed(2)}} · acquisition cost ${{Number(score.acquisition_cost || 0).toLocaleString()}}</div>
          <div class="tiny" style="margin-top:8px">${{escapeHtml((score.effect_tags || []).join(', ') || 'No effect tags')}}</div>
          <div style="margin-top:10px"><strong>Reasons</strong><ul class="list">${{(score.reasons || []).map((reason) => `<li>${{escapeHtml(reason)}}</li>`).join('') || '<li class="muted">No reasons returned.</li>'}}</ul></div>
          <details>
            <summary>Top candidates</summary>
            ${{renderCandidates((result.top_candidates || {{}})[slot])}}
          </details>
        </div>
      `).join('');
    }}

    function renderAccessories(result) {{
      const tiers = result.accessory_review || {{}};
      return Object.entries(tiers).map(([tier, items]) => `
        <details>
          <summary>${{escapeHtml(tier)}} <span class="badge">${{items.length}}</span></summary>
          <ul class="list">
            ${{items.map((item) => `
              <li>
                <strong>${{escapeHtml(item.name)}}</strong>
                <div class="tiny">${{escapeHtml((item.tags || []).join(', ') || '—')}} · ${{escapeHtml(Object.entries(item.stats || {{}}).map(([k, v]) => `${{k}}:${{v >= 0 ? '+' : ''}}${{v}}`).join('  ') || 'no stats')}}</div>
              </li>
            `).join('')}}
          </ul>
        </details>
      `).join('');
    }}

    function renderResult(result) {{
      const current = result.current_stats || {{}};
      const recommended = result.recommended_stats || {{}};
      const selected = (result.selected_locations || []).join(', ') || 'No location limit';
      const budget = result.budget;
      const cost = Number(result.total_cost || 0);
      const remaining = budget == null ? null : Number(budget) - cost;

      els.summary.innerHTML = `
        <div class="metric"><span class="k">Traveler</span><span class="v">${{escapeHtml(result.character)}} <span class="badge">${{escapeHtml(result.class)}}</span></span></div>
        <div class="metric"><span class="k">Level</span><span class="v">${{result.level}}</span></div>
        <div class="metric"><span class="k">Total Cost</span><span class="v">${{cost.toLocaleString()}}</span></div>
        <div class="metric"><span class="k">Budget</span><span class="v">${{budget == null ? 'Unlimited' : Number(budget).toLocaleString()}}</span></div>
        <div class="metric"><span class="k">Remaining</span><span class="v">${{remaining == null ? 'Unlimited' : remaining.toLocaleString()}}</span></div>
        <div class="metric" style="min-width: 280px"><span class="k">Locations</span><span class="v" style="font-size:.95rem;font-weight:650">${{escapeHtml(selected)}}</span></div>
      `;

      const survivability = (result.survivability_notes || []).length
        ? `<div class="card"><h3>Survivability Notes</h3><ul class="list">${{result.survivability_notes.map((note) => `<li>${{escapeHtml(note)}}</li>`).join('')}}</ul></div>`
        : '';

      const excluded = (result.excluded_examples || []).length
        ? `<details><summary>Excluded examples</summary><ul class="list">${{result.excluded_examples.map((entry) => `<li>${{escapeHtml(entry)}}</li>`).join('')}}</ul></details>`
        : '';

      els.results.innerHTML = `
        <div class="card">
          <h3>Stats</h3>
          <div class="stats-grid">${{statGrid(current, recommended)}}</div>
        </div>
        ${{survivability}}
        <div class="slot-grid-result">${{renderRecommendations(result)}}</div>
        <div class="card">
          <h3>Accessory Review</h3>
          ${{renderAccessories(result)}}
        </div>
        ${{excluded}}
      `;
    }}

    async function runOptimizer(event) {{
      event.preventDefault();
      setStatus('Running optimizer...');
      document.body.classList.add('loading');
      try {{
        const response = await fetch('/api/optimize', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify(collectPayload()),
        }});
        const payload = await response.json();
        if (!response.ok) {{
          throw new Error(payload.error || 'Optimization failed');
        }}
        renderResult(payload.result);
        setStatus('Done.');
      }} catch (error) {{
        els.results.innerHTML = `<div class="error">${{escapeHtml(error.message || String(error))}}</div>`;
        setStatus('Run failed.', 'error');
      }} finally {{
        document.body.classList.remove('loading');
      }}
    }}

    fillCharacterOptions();
    fillSourceTypes();
    fillNakedStats();
    fillDatalist('weapon-list', GUI.weapon_options || []);
    fillDatalist('shield-list', GUI.shield_options || []);
    fillDatalist('headgear-list', GUI.headgear_options || []);
    fillDatalist('body-armor-list', GUI.body_armor_options || []);
    fillDatalist('accessory-list', GUI.accessory_options || []);

    els.character.addEventListener('change', syncCharacter);
    els.noLeaves.addEventListener('change', syncBudgetMode);
    els.respectOtherCharacters.addEventListener('change', syncBudgetMode);
    els.form.addEventListener('submit', runOptimizer);
    els.resetBtn.addEventListener('click', resetForm);

    resetForm();
  </script>
</body>
</html>"""


class _GuiHandler(BaseHTTPRequestHandler):
    state: dict[str, Any] = {}
    items = []

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return

    def do_GET(self) -> None:  # noqa: N802
        if self.path in ("/", "/index.html"):
            _html_response(self, _page_html(self.state))
            return
        if self.path == "/api/state":
            _json_response(self, self.state)
            return
        self.send_error(404, "Not found")

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/api/optimize":
            self.send_error(404, "Not found")
            return

        length = int(self.headers.get("Content-Length", "0"))
        try:
            payload = _parse_json_body(self.rfile.read(length))
            config = _build_config(payload)
            result = optimize_character(config, self.items)
            _json_response(self, {"ok": True, "result": result.to_jsonable()})
        except Exception as exc:  # pragma: no cover - server-side guard
            _json_response(self, {"ok": False, "error": str(exc)}, status=500)


def serve(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, open_browser: bool = True) -> None:
    state = _load_gui_state()
    _GuiHandler.state = state
    _GuiHandler.items = load_equipment(project_root())
    server = ThreadingHTTPServer((host, port), _GuiHandler)
    url = f"http://{host}:{port}"
    print(f"OT2 GUI running at {url}")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(description="OT2 local GUI")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    serve(args.host, args.port, open_browser=not args.no_browser)


if __name__ == "__main__":
    main()
