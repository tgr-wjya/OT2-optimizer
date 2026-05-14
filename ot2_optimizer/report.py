from __future__ import annotations

import html
from pathlib import Path
from typing import TYPE_CHECKING

from .models import STAT_KEYS, CharacterResult

if TYPE_CHECKING:
    from .damage_sim import DamageComparison

# ─── HTML helpers ─────────────────────────────────────────────────────────────


def _delta_short_html(stat_delta: dict[str, int], max_stats: int = 3) -> str:
    """Top N most impactful stat deltas as coloured HTML spans."""
    if not stat_delta:
        return "<em style='color:#555'>—</em>"
    top = sorted(stat_delta.items(), key=lambda kv: abs(kv[1]), reverse=True)[
        :max_stats
    ]
    parts = []
    for k, v in top:
        color = "#68d391" if v >= 0 else "#fc8181"
        parts.append(
            f'<span style="color:{color}">{html.escape(k)}&thinsp;{v:+d}</span>'
        )
    return "&ensp;".join(parts)


def _tags_html(tags: list[str], limit: int = 5) -> str:
    """Render a list of tag strings as small badge spans."""
    return " ".join(f'<span class="tag">{html.escape(t)}</span>' for t in tags[:limit])


def _stats_html(stats: dict[str, int]) -> str:
    """Render non-zero stats as coloured spans; returns em-dash if all zero."""
    non_zero = {k: v for k, v in stats.items() if v}
    if not non_zero:
        return "<em style='color:#555'>none</em>"
    parts = []
    for k, v in non_zero.items():
        color = "#68d391" if v >= 0 else "#fc8181"
        parts.append(
            f'<span style="color:{color}">{html.escape(k)}&thinsp;{v:+d}</span>'
        )
    return "&ensp;".join(parts)


# ─── Table builders ───────────────────────────────────────────────────────────


def stat_rows(result: CharacterResult) -> str:
    """Current vs recommended stats table body rows."""
    rows = []
    for stat in STAT_KEYS:
        current = result.current_stats.get(stat, 0)
        recommended = result.recommended_stats.get(stat, 0)
        delta = recommended - current
        width = min(100, max(4, abs(delta)))
        color = "#2f855a" if delta >= 0 else "#c53030"
        rows.append(
            f"<tr>"
            f"<td>{html.escape(stat)}</td>"
            f"<td>{current}</td>"
            f"<td>{recommended}</td>"
            f"<td>{delta:+d}</td>"
            f"<td><div class='bar'>"
            f"<span style='width:{width}%;background:{color}'></span>"
            f"</div></td>"
            f"</tr>"
        )
    return "\n".join(rows)


def base_stat_rows(base_stats: dict[str, int]) -> str:
    """Base (naked) stats table body rows, ordered by STAT_KEYS."""
    rows = []
    for stat in STAT_KEYS:
        if stat in base_stats:
            rows.append(
                f"<tr><td>{html.escape(stat)}</td><td>{base_stats[stat]}</td></tr>"
            )
    # Any extra keys not in STAT_KEYS (shouldn't happen, but be safe).
    for stat, val in base_stats.items():
        if stat not in STAT_KEYS:
            rows.append(f"<tr><td>{html.escape(stat)}</td><td>{val}</td></tr>")
    return "\n".join(rows)


def candidates_table_html(slot: str, recommended_score, result: CharacterResult) -> str:
    """Build a top-candidates HTML table for a given slot.

    Returns an empty string if no candidates are available.
    """
    top_candidates: dict[str, list] = getattr(result, "top_candidates", {})
    candidates = top_candidates.get(slot, [])
    if not candidates:
        return ""

    rows: list[str] = []
    for rank, cand in enumerate(candidates, start=1):
        is_rec = cand.item.key == recommended_score.item.key
        is_cur = getattr(cand, "is_current_item", False)
        # acquisition_cost: use field if present, fall back to item price.
        raw_acq = getattr(cand, "acquisition_cost", cand.item.price or 0)
        acq_cost = "N/A" if raw_acq >= 10**9 else str(raw_acq)

        # Row highlight class
        row_class = ""
        if is_rec:
            row_class = " class='row-recommended'"
        elif is_cur:
            row_class = " class='row-current'"

        # Item name cell — append "(current)" badge if applicable.
        name_cell = html.escape(cand.item.name)
        if is_cur:
            name_cell += ' <span class="badge-keep">current</span>'

        delta_html = _delta_short_html(cand.stat_delta)
        tags_html = _tags_html(cand.item.effect_tags)
        avail_text = html.escape(cand.item.availability or "—")

        rows.append(
            f"<tr{row_class}>"
            f"<td>{rank}</td>"
            f"<td>{name_cell}</td>"
            f"<td>{cand.score:.2f}</td>"
            f"<td>{cand.item.price if cand.item.price is not None else '—'}</td>"
            f"<td>{acq_cost}</td>"
            f"<td>{delta_html}</td>"
            f"<td>{tags_html}</td>"
            f"<td><small>{avail_text}</small></td>"
            f"</tr>"
        )

    return (
        "<table class='candidates-table'>"
        "<thead><tr>"
        "<th>#</th><th>Item</th><th>Score</th><th>Price</th><th>Acq. Cost</th>"
        "<th>Stat Delta</th><th>Tags</th><th>Availability</th>"
        "</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        "</table>"
    )


# ─── Main report writer ───────────────────────────────────────────────────────


def damage_comparison_html(comp: "DamageComparison") -> str:
    """Build the Damage Simulation HTML section."""
    elem_delta = comp.recommended_elem_atk - comp.current_elem_atk
    elem_pct = (
        (comp.recommended_elem_atk / comp.current_elem_atk - 1) * 100
        if comp.current_elem_atk > 0
        else 0.0
    )
    sign_color = "#68d391" if elem_delta >= 0 else "#fc8181"

    rows_html: list[str] = []
    for row in comp.rows:
        label = html.escape(row.scenario.label or row.display_name)
        cur_total = html.escape(row.current.total_str())
        rec_total = html.escape(row.recommended.total_str())
        pct_str = f"{row.delta_pct:+.0f}%"
        pct_color = "#68d391" if row.delta_pct >= 0 else "#fc8181"
        conf = row.current.confidence
        conf_badge = (
            ""
            if conf == "HIGH"
            else (
                f' <span class="tag" title="MEDIUM confidence: values from community datamine">~</span>'
                if conf == "MEDIUM"
                else f' <span class="tag" style="background:#744210;color:#fbd38d" title="LOW confidence: estimates only">?</span>'
            )
        )
        rows_html.append(
            f"<tr>"
            f"<td>{label}{conf_badge}</td>"
            f"<td style='text-align:center'>{row.current.bp}</td>"
            f"<td style='text-align:center'>{row.current.intensity}</td>"
            f"<td style='text-align:center'>{html.escape(row.current.hits_str())}</td>"
            f"<td style='text-align:right'>{cur_total}</td>"
            f"<td style='text-align:right'>{rec_total}</td>"
            f"<td style='text-align:right;color:{pct_color}'><strong>{html.escape(pct_str)}</strong></td>"
            f"</tr>"
        )

    conf_note_html = (
        f"<p style='color:#a0aec0;font-size:.85em;margin-top:.5rem'>{html.escape(comp.confidence_note)}</p>"
        if comp.confidence_note
        else ""
    )

    return (
        "<section>"
        "<h2>Damage Simulation</h2>"
        f"<p>vs enemy Elem. Def: <strong>{comp.enemy_elem_def}</strong>"
        f" &nbsp;|&nbsp; Level {comp.level}, mult: <strong>{comp.level_mult}</strong></p>"
        f"<p>Elem. Atk: <strong>{comp.current_elem_atk}</strong> (current)"
        f" &rarr; <strong>{comp.recommended_elem_atk}</strong> (recommended)"
        f" <span style='color:{sign_color}'>{elem_delta:+d}&nbsp;({elem_pct:+.1f}%)</span></p>"
        "<table><thead><tr>"
        "<th>Scenario</th><th>BP</th><th>Intensity</th><th>Hits</th>"
        "<th style='text-align:right'>Current</th>"
        "<th style='text-align:right'>Recommended</th>"
        "<th style='text-align:right'>Delta</th>"
        "</tr></thead>"
        f"<tbody>{''.join(rows_html)}</tbody>"
        "</table>"
        f"{conf_note_html}"
        "</section>"
    )


def write_html_report(
    result: CharacterResult,
    path: Path,
    damage_comp: "DamageComparison | None" = None,
) -> None:
    base_stats: dict[str, int] = getattr(result, "base_stats", {})
    surv_notes: list[str] = getattr(result, "survivability_notes", [])
    budget = getattr(result, "budget", None)
    top_candidates: dict[str, list] = getattr(result, "top_candidates", {})

    # ── Budget / cost blurb ──────────────────────────────────────────────────
    if budget is not None:
        remaining = budget - result.total_cost
        cost_info = (
            f"Total cost: <strong>{result.total_cost}</strong> leaves"
            f"&nbsp;&nbsp;|&nbsp;&nbsp;"
            f"Budget: {budget}"
            f"&nbsp;&nbsp;|&nbsp;&nbsp;"
            f"Remaining: <strong>{remaining}</strong>"
        )
    else:
        cost_info = f"Total cost: <strong>{result.total_cost}</strong> leaves"

    # ── Base stats section ───────────────────────────────────────────────────
    if base_stats:
        base_stats_section = (
            "<h2>Base (Naked) Stats</h2>"
            "<table style='width:auto;min-width:220px'>"
            "<thead><tr><th>Stat</th><th>Base</th></tr></thead>"
            f"<tbody>{base_stat_rows(base_stats)}</tbody>"
            "</table>"
        )
    else:
        base_stats_section = ""

    # ── Survivability notes card ─────────────────────────────────────────────
    if surv_notes:
        notes_li = "".join(f"<li>{html.escape(n)}</li>" for n in surv_notes)
        surv_section = (
            "<section class='surv-notes'>"
            "<h3>&#9888; Survivability Targets</h3>"
            f"<ul>{notes_li}</ul>"
            "</section>"
        )
    else:
        surv_section = ""

    # ── Per-slot recommendations ─────────────────────────────────────────────
    recommendation_sections: list[str] = []
    for slot, score in result.recommendations.items():
        is_current = getattr(score, "is_current_item", False)
        acq_cost = getattr(score, "acquisition_cost", 0)

        badge = (
            '<span class="badge-keep">Keeping Current</span>'
            if is_current
            else '<span class="badge-new">New Item</span>'
        )

        if is_current:
            price_info = "acquisition cost: <strong>0</strong>"
            # Check for budget-constraint note
            budget_html = ""
            if budget is not None:
                remaining_budget = budget - result.total_cost
                slot_cands = top_candidates.get(slot, [])
                better = [
                    c
                    for c in slot_cands
                    if not getattr(c, "is_current_item", False) and c.score > 0
                ]
                if better:
                    best_alt = better[0]
                    alt_price = best_alt.item.price
                    if alt_price is not None and alt_price > remaining_budget:
                        budget_html = (
                            f"<p style='color:#f6ad55;font-size:.9em'>&#9888; Budget constraint: "
                            f"best alternative <strong>{html.escape(best_alt.item.name)}</strong> "
                            f"costs {alt_price:,} but only {remaining_budget:,} leaves remain.</p>"
                        )
        else:
            price_info = (
                f"store price: <strong>{score.item.price or 0}</strong>"
                f"&nbsp;&nbsp;|&nbsp;&nbsp;"
                f"acquisition cost: <strong>{acq_cost}</strong>"
            )
            budget_html = ""

        effect_html = (
            f"<p class='effect-text'>{html.escape(score.item.effect_text)}</p>"
            if score.item.effect_text
            else ""
        )

        # Filter out any legacy per-slot survivability reasons.
        display_reasons = [
            r for r in score.reasons if not r.startswith("loadout survivability:")
        ]
        reasons_html = "".join(f"<li>{html.escape(r)}</li>" for r in display_reasons)
        reasons_section = f"<ul>{reasons_html}</ul>" if display_reasons else ""

        cand_table = candidates_table_html(slot, score, result)
        cand_section = f"<h4>Top Candidates</h4>{cand_table}" if cand_table else ""

        recommendation_sections.append(
            f"<section>"
            f"<h3>{html.escape(slot.upper())} {badge}</h3>"
            f"<p>"
            f"<strong>{html.escape(score.item.name)}</strong>"
            f"&ensp;<em>({html.escape(score.item.category)})</em>"
            f"&nbsp;&nbsp;|&nbsp;&nbsp;score <strong>{score.score:.2f}</strong>"
            f"&nbsp;&nbsp;|&nbsp;&nbsp;{price_info}"
            f"</p>"
            f"{effect_html}"
            f"{budget_html}"
            f"{reasons_section}"
            f"{cand_section}"
            f"</section>"
        )

    # ── Accessory review ─────────────────────────────────────────────────────
    accessory_sections: list[str] = []
    for tier, items in result.accessory_review.items():
        lines: list[str] = []
        for item in items[:20]:
            tags_str = (
                html.escape(", ".join(item.accessory_tags))
                if item.accessory_tags
                else ""
            )
            stats_html = _stats_html(item.stats)
            avail_text = html.escape(item.availability or "—")

            # Truncate effect text for the summary view.
            effect_raw = item.effect_text or ""
            if len(effect_raw) > 80:
                effect_display = html.escape(effect_raw[:80]) + "…"
            else:
                effect_display = html.escape(effect_raw)

            lines.append(
                f"<li>"
                f"<strong>{html.escape(item.name)}</strong>"
                f"&ensp;&mdash;&ensp;{tags_str}"
                f"<br><small>Stats: {stats_html}</small>"
                f"<br><small>{effect_display}</small>"
                f"<br><small style='color:#666'>{avail_text}</small>"
                f"</li>"
            )

        accessory_sections.append(
            f"<section><h3>{html.escape(tier)}</h3><ul>{''.join(lines)}</ul></section>"
        )

    # ── Damage simulation section ────────────────────────────────────────────
    damage_section = (
        damage_comparison_html(damage_comp) if damage_comp is not None else ""
    )

    # ── Assemble full document ───────────────────────────────────────────────
    document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>OT2 Optimizer &mdash; {html.escape(result.character)}</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; }}
    body {{
      font-family: system-ui, sans-serif;
      background: #111;
      color: #eee;
      margin: 2rem auto;
      max-width: 1100px;
      line-height: 1.5;
    }}
    h1, h2, h3, h4 {{ color: #e2e8f0; margin-top: 1.5rem; }}
    h1 {{ font-size: 1.6rem; border-bottom: 1px solid #333; padding-bottom: .5rem; }}
    h2 {{ font-size: 1.2rem; color: #a0aec0; text-transform: uppercase;
          letter-spacing: .06em; margin-top: 2rem; }}
    h3 {{ font-size: 1.05rem; margin: 0 0 .5rem; }}
    h4 {{ font-size: .9rem; color: #a0aec0; margin: 1rem 0 .4rem; }}
    table {{ border-collapse: collapse; width: 100%; margin: .75rem 0 1.5rem; }}
    th, td {{ border-bottom: 1px solid #2d3748; padding: .45rem .75rem; text-align: left;
              vertical-align: top; }}
    th {{ background: #1a202c; color: #a0aec0; font-size: .8em;
          text-transform: uppercase; letter-spacing: .05em; }}
    section {{ border: 1px solid #333; border-radius: 6px; padding: 1rem 1.25rem; margin: 1rem 0; }}
    p {{ margin: .35rem 0; }}
    ul {{ margin: .5rem 0; padding-left: 1.5rem; }}
    li {{ margin: .25rem 0; }}
    small {{ color: #aaa; }}
    .bar {{ width: 180px; background: #222; height: 10px; display: inline-block; vertical-align: middle; }}
    .bar span {{ display: block; height: 10px; }}
    /* Badges */
    .badge-keep {{ background: #555; color: #eee; padding: 2px 6px; border-radius: 3px; font-size: .8em; font-style: normal; }}
    .badge-new  {{ background: #276749; color: #eee; padding: 2px 6px; border-radius: 3px; font-size: .8em; font-style: normal; }}
    /* Candidates table row states */
    .row-recommended {{ background: #1a2e1a; }}
    .row-current {{ font-style: italic; }}
    /* Effect/tag pills */
    .tag {{ background: #2d3748; color: #a0aec0; padding: 1px 5px; border-radius: 3px;
            font-size: .78em; white-space: nowrap; margin-right: 2px; }}
    /* Survivability notes card */
    .surv-notes {{ border-color: #744210; background: #1a1200; }}
    .surv-notes h3 {{ color: #f6ad55; }}
    .surv-notes li {{ color: #fbd38d; }}
    /* Flavour text */
    .effect-text {{ color: #a0aec0; font-style: italic; font-size: .95em; }}
    /* Candidates sub-table */
    .candidates-table {{ font-size: .88em; margin-top: .5rem; }}
    .candidates-table th {{ font-size: .75em; }}
  </style>
</head>
<body>
  <h1>{html.escape(result.character)} &mdash; Level {result.level} Optimizer Report</h1>
  <p>Class: <strong>{html.escape(result.class_name)}</strong>
  &nbsp;&nbsp;|&nbsp;&nbsp;
  {cost_info}</p>

  {base_stats_section}

  <h2>Current vs Recommended Stats</h2>
  <table>
    <thead>
      <tr><th>Stat</th><th>Current</th><th>Recommended</th><th>Delta</th><th></th></tr>
    </thead>
    <tbody>{stat_rows(result)}</tbody>
  </table>

  {surv_section}

  {damage_section}

  <h2>Recommendations</h2>
  {"".join(recommendation_sections)}

  <h2>Accessory Review</h2>
  {"".join(accessory_sections)}
</body>
</html>"""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(document, encoding="utf-8")
