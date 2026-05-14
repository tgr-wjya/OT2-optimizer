from __future__ import annotations

import argparse
import json
from pathlib import Path

from .damage_sim import DamageComparison, run_comparison_from_config
from .data_loader import load_equipment
from .optimizer import optimize_character
from .report import write_html_report
from .templates import (
    CHARACTER_DEFAULT_CLASS,
    generate_config_template,
    list_characters,
    list_classes,
    save_config_template,
)


def _delta_short(stat_delta: dict[str, int], max_stats: int = 3) -> str:
    """Return the N most impactful stat deltas as a compact string."""
    if not stat_delta:
        return ""
    top = sorted(stat_delta.items(), key=lambda kv: abs(kv[1]), reverse=True)[
        :max_stats
    ]
    return "  ".join(f"{k}:{v:+d}" for k, v in top)


def print_damage_comparison(comp: DamageComparison) -> None:
    """Print the damage simulation comparison table."""
    elem_delta = comp.recommended_elem_atk - comp.current_elem_atk
    elem_pct = (
        (comp.recommended_elem_atk / comp.current_elem_atk - 1) * 100
        if comp.current_elem_atk > 0
        else 0.0
    )
    print("─" * 80)
    print(
        f"Damage Simulation  (vs enemy Elem. Def: {comp.enemy_elem_def}"
        f" | Level {comp.level}, mult: {comp.level_mult})"
    )
    print(
        f"  Elem. Atk: {comp.current_elem_atk} (current)"
        f" → {comp.recommended_elem_atk} (recommended)"
        f"  [{elem_delta:+d}, {elem_pct:+.1f}%]"
    )
    print()

    W_LABEL = 30
    W_HITS = 5
    W_DMG = 11  # "XXXX–YYYY"
    W_DELTA = 8
    SEP = "  "
    header = (
        f"  {'Scenario':<{W_LABEL}}{SEP}"
        f"{'BP':>2}{SEP}{'I':>1}{SEP}"
        f"{'Hits':>{W_HITS}}{SEP}"
        f"{'Current':>{W_DMG}}{SEP}"
        f"{'Recommended':>{W_DMG}}{SEP}"
        f"{'Delta':>{W_DELTA}}"
    )
    print(header)
    print("  " + "─" * (len(header) - 2))

    for row in comp.rows:
        label = row.scenario.label or row.display_name
        label_trunc = label[:W_LABEL]
        cur_str = row.current.total_str()
        rec_str = row.recommended.total_str()
        pct_str = f"{row.delta_pct:+.0f}%"
        conf_marker = (
            ""
            if row.current.confidence == "HIGH"
            else (" ~" if row.current.confidence == "MEDIUM" else " ?")
        )
        print(
            f"  {label_trunc:<{W_LABEL}}{SEP}"
            f"{row.current.bp:>2}{SEP}{row.current.intensity:>1}{SEP}"
            f"{row.current.hits_str():>{W_HITS}}{SEP}"
            f"{cur_str:>{W_DMG}}{SEP}"
            f"{rec_str:>{W_DMG}}{SEP}"
            f"{pct_str:>{W_DELTA}}{conf_marker}"
        )

    print()
    if comp.confidence_note:
        print(f"  {comp.confidence_note}")
    print("─" * 80)
    print()


def print_result(result, damage_comp: DamageComparison | None = None) -> None:
    # ── 1. Header ──────────────────────────────────────────────────────────────
    print(f"{result.character} level {result.level} ({result.class_name})")
    locations = ", ".join(result.selected_locations) or "no location limit"
    print(f"Locations: {locations}")

    budget = getattr(result, "budget", None)
    if budget is not None:
        remaining = budget - result.total_cost
        print(
            f"Total cost: {result.total_cost} leaves"
            f"  (budget: {budget:,}, remaining: {remaining:,})"
        )
    else:
        print(f"Total cost: {result.total_cost} leaves")
    print()

    # ── 2. Base (naked) stats ──────────────────────────────────────────────────
    base_stats: dict[str, int] = getattr(result, "base_stats", {})
    if base_stats:
        print("Base (naked) stats:")
        items_list = list(base_stats.items())
        for i in range(0, len(items_list), 4):
            chunk = items_list[i : i + 4]
            print("  " + " | ".join(f"{k}: {v}" for k, v in chunk))
        print()

    # ── 3. Survivability notes ─────────────────────────────────────────────────
    survivability_notes: list[str] = getattr(result, "survivability_notes", [])
    if survivability_notes:
        print("Survivability targets:")
        for note in survivability_notes:
            print(f"  - {note}")
        print()

    # ── 4 & 5. Per-slot recommendations + top candidates ───────────────────────
    top_candidates: dict[str, list] = getattr(result, "top_candidates", {})

    for slot, score in result.recommendations.items():
        is_current = getattr(score, "is_current_item", False)
        acq_cost = getattr(score, "acquisition_cost", 0)

        print(f"=== {slot.upper()} ===")
        print(f"  {score.item.name} [{score.item.category}]  score: {score.score:.2f}")
        # Note if combo-level optimization chose a lower individual scorer
        candidates = top_candidates.get(slot, [])
        if candidates and not is_current:
            top_scorer = candidates[0]
            if top_scorer.item.key != score.item.key and top_scorer.score > score.score:
                print(
                    f"  (note: {top_scorer.item.name} scored higher individually"
                    f" [{top_scorer.score:.2f}] but this was selected by combo optimization)"
                )

        if is_current:
            print("  (keeping current — acquisition cost: 0)")
            # Check whether a better option exists but budget ran out.
            budget_val = getattr(result, "budget", None)
            if budget_val is not None:
                remaining_budget = budget_val - result.total_cost
                slot_candidates = top_candidates.get(slot, [])
                better = [
                    c
                    for c in slot_candidates
                    if not getattr(c, "is_current_item", False) and c.score > 0
                ]
                if better:
                    best_alt = better[0]
                    alt_price = best_alt.item.price
                    if alt_price is not None and alt_price > remaining_budget:
                        print(
                            f"  ! Budget constraint: best alternative is"
                            f" {best_alt.item.name} (store price: {alt_price:,})"
                            f" but only {remaining_budget:,} leaves remain."
                        )
        else:
            price = score.item.price or 0
            print(f"  (NEW — store price: {price:,}, acquisition cost: {acq_cost:,})")

        if score.item.effect_text:
            print(f"  effect: {score.item.effect_text}")

        if score.stat_delta:
            delta_parts = "  ".join(f"{k}: {v:+d}" for k, v in score.stat_delta.items())
            print(f"  stat delta: {delta_parts}")

        # Filter out any legacy survivability reasons — they now live at the top level.
        display_reasons = [
            r for r in score.reasons if not r.startswith("loadout survivability:")
        ]
        for reason in display_reasons:
            print(f"  - {reason}")

        # ── Top candidates table ───────────────────────────────────────────────
        candidates = top_candidates.get(slot, [])
        if candidates:
            print()
            # Column widths (characters)
            W_NUM = 3  # marker char + rank digits
            W_ITEM = 30
            W_SCORE = 7
            W_PRICE = 7
            W_DELTA = 42  # wide enough for 3 full stat entries
            SEP = "  "

            header = (
                f"  {'#':<{W_NUM}}{SEP}"
                f"{'Item':<{W_ITEM}}{SEP}"
                f"{'Score':>{W_SCORE}}{SEP}"
                f"{'Acq.Cost':>{W_PRICE}}{SEP}"
                f"{'Delta':<{W_DELTA}}{SEP}"
                f"Tags"
            )
            # Divider spans the fixed columns; tags are open-ended.
            divider_len = (
                2
                + W_NUM
                + len(SEP)
                + W_ITEM
                + len(SEP)
                + W_SCORE
                + len(SEP)
                + W_PRICE
                + len(SEP)
                + W_DELTA
                + len(SEP)
                + 20
            )
            print(header)
            print("  " + "─" * (divider_len - 2))

            for rank, cand in enumerate(candidates, start=1):
                is_rec = cand.item.key == score.item.key
                is_cur = getattr(cand, "is_current_item", False)
                marker = "*" if is_rec else ("C" if is_cur else " ")

                name_trunc = cand.item.name[:W_ITEM]
                score_str = f"{cand.score:.2f}"
                acq_disp = getattr(cand, "acquisition_cost", cand.item.price or 0)
                price_str = "N/A" if acq_disp >= 10**9 else str(acq_disp)
                delta_str = _delta_short(cand.stat_delta)[:W_DELTA]
                tags_str = ", ".join(cand.item.effect_tags[:3])

                row = (
                    f"  {marker}{rank:<{W_NUM - 1}}{SEP}"
                    f"{name_trunc:<{W_ITEM}}{SEP}"
                    f"{score_str:>{W_SCORE}}{SEP}"
                    f"{price_str:>{W_PRICE}}{SEP}"
                    f"{delta_str:<{W_DELTA}}{SEP}"
                    f"{tags_str}"
                )
                print(row)

        print()

    # ── 6. Accessories ─────────────────────────────────────────────────────────
    # ── 7. Damage simulation ───────────────────────────────────────────────────
    if damage_comp is not None:
        print_damage_comparison(damage_comp)

    print("Accessories to review:")
    for tier, items in result.accessory_review.items():
        print(f"  {tier}:")
        for item in items[:10]:
            tags_str = ", ".join(item.accessory_tags) if item.accessory_tags else ""
            non_zero = {k: v for k, v in item.stats.items() if v}
            stat_str = ""
            if non_zero:
                stat_str = (
                    "  [" + ", ".join(f"{k}:{v:+d}" for k, v in non_zero.items()) + "]"
                )
            effect_str = ""
            if item.effect_text:
                text = item.effect_text[:60]
                if len(item.effect_text) > 60:
                    text += "…"
                effect_str = f"  {text}"
            print(f"    - {item.name}: {tags_str}{stat_str}{effect_str}")
        if len(items) > 10:
            print(f"    ... {len(items) - 10} more")


def main() -> None:
    parser = argparse.ArgumentParser(description="OT2 Python optimizer")

    # ── generate-config subcommand ─────────────────────────────────────────
    parser.add_argument(
        "--generate-config",
        nargs="+",
        metavar=("CHARACTER", "..."),
        help=(
            "Generate a starter config and exit. "
            "Usage: --generate-config CHARACTER [CLASS] [LEVEL] "
            "  CLASS defaults to each character's original class. "
            "  LEVEL defaults to 1. "
            f"  Characters: {', '.join(list_characters())}. "
            f"  Classes:    {', '.join(list_classes())}."
        ),
    )
    parser.add_argument(
        "--config-out",
        default=None,
        metavar="PATH",
        help="Where to save the generated config (default: print to stdout).",
    )

    # ── normal optimizer flags ─────────────────────────────────────────────
    parser.add_argument("--config", default="configs/one_character.example.json")
    parser.add_argument("--json-out", default="reports/one_character.result.json")
    parser.add_argument("--html-out", default="reports/one_character.report.html")
    args = parser.parse_args()

    # ── handle generate-config early exit ─────────────────────────────────
    if args.generate_config:
        parts = args.generate_config
        character = parts[0]
        class_name = (
            parts[1]
            if len(parts) > 1
            else CHARACTER_DEFAULT_CLASS.get(character, "Warrior")
        )
        level = int(parts[2]) if len(parts) > 2 else 1
        template = generate_config_template(character, class_name, level)
        if args.config_out:
            out_path = Path(args.config_out)
            save_config_template(template, out_path)
            print(f"Config template written to: {out_path}")
        else:
            print(json.dumps(template, indent=2, ensure_ascii=False))
        return

    config_path = Path(args.config)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    result = optimize_character(config, load_equipment())

    damage_comp = run_comparison_from_config(
        config,
        current_elem_atk=result.current_stats.get("elem_atk", 0),
        recommended_elem_atk=result.recommended_stats.get("elem_atk", 0),
        level=result.level,
    )

    print_result(result, damage_comp)

    out: dict = result.to_jsonable()
    if damage_comp is not None:
        out["damage_simulation"] = damage_comp.to_jsonable()

    json_path = Path(args.json_out)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    write_html_report(result, Path(args.html_out), damage_comp)

    print()
    print(f"Wrote JSON: {json_path}")
    print(f"Wrote HTML report: {args.html_out}")


if __name__ == "__main__":
    main()
