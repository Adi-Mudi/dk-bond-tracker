from html import escape

from .export_csv import serialize_records
from .notifications import list_notifications
from .queries import (
    bond_month_totals,
    monthly_history,
    portfolio_totals,
    status_overview,
    summary_counts,
    this_month_returns,
)
from .validators import AppError

MASK = "••••"
SECTION_KEYS = ("totals", "per_bond", "history", "alerts")
SECTION_TITLES = {
    "totals": "Portfolio totals",
    "per_bond": "Per-bond list",
    "history": "Monthly history",
    "alerts": "Alerts",
}

SHARE_STYLE = """
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: "Segoe UI", system-ui, -apple-system, sans-serif; color: #1e1e1e; background: #f8f9fa; padding: 24px 16px 48px; line-height: 1.45; }
  .sheet { max-width: 860px; margin: 0 auto; background: #ffffff; border: 1px solid #adb5bd; padding: 20px 24px; }
  h1 { font-size: 20px; margin-bottom: 4px; }
  .sub { font-size: 12px; color: #495057; margin-bottom: 16px; }
  .share-sec { margin-bottom: 20px; }
  .share-sec h2 { font-size: 13px; font-weight: 800; text-transform: uppercase; letter-spacing: 0.06em; border-bottom: 1.5px solid #1e1e1e; padding-bottom: 3px; margin-bottom: 8px; }
  table { width: 100%; border-collapse: collapse; font-size: 12.5px; }
  th { background: #e9ecef; border: 1px solid #1e1e1e; padding: 5px 7px; text-align: left; font-size: 11px; text-transform: uppercase; }
  td { border: 1px solid #ced4da; padding: 5px 7px; vertical-align: top; }
  td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
  .money { white-space: nowrap; }
  .foot { font-size: 11px; color: #495057; border-top: 1.5px solid #1e1e1e; padding-top: 8px; font-style: italic; }
  @media print { body { background: #fff; padding: 0; } .sheet { border: none; padding: 0; } }
"""


def _selected_sections(sections):
    if not isinstance(sections, dict):
        raise AppError(
            "ERR-share-export",
            f"sections must be a mapping of checkboxes: {type(sections).__name__}",
        )
    unknown = [str(key) for key in sections if key not in SECTION_KEYS]
    if unknown:
        raise AppError(
            "ERR-share-export",
            f"unknown share section(s): {', '.join(sorted(unknown))}",
        )
    selected = [key for key in SECTION_KEYS if sections.get(key)]
    if not selected:
        raise AppError(
            "ERR-share-export",
            "no sections selected — check at least one section checkbox",
        )
    return selected


def _load_section(conn, key):
    try:
        if key == "totals":
            return {
                "counts": summary_counts(conn),
                "totals": portfolio_totals(conn),
                "month_returns": this_month_returns(conn),
            }
        if key == "per_bond":
            rows = []
            for entry in status_overview(conn):
                till = bond_month_totals(conn, entry["id"])["k"]
                rows.append(
                    {
                        "company": entry["company"],
                        "isin": entry["isin"],
                        "status": entry["status"],
                        "amount": float(entry["amount"] or 0.0),
                        "till_return": float(till),
                    }
                )
            return {"rows": rows}
        if key == "history":
            return {"rows": monthly_history(conn)}
        if key == "alerts":
            return {"rows": list_notifications(conn, limit=20)}
    except AppError as exc:
        raise AppError("ERR-share-export", f"section {key} failed: {exc.message}") from exc
    except Exception as exc:
        raise AppError("ERR-share-export", f"section {key} failed: {exc}") from exc
    raise AppError("ERR-share-export", f"unknown share section: {key!r}")


def _html_money(value, show):
    if not show:
        return f'<span class="money">{MASK}</span>'
    numeric = float(value or 0.0)
    return f'<span class="money" data-amount="{numeric:.2f}">₹{numeric:.2f}</span>'


def _csv_money(value, show):
    if not show:
        return MASK
    return f"{float(value or 0.0):.2f}"


def _totals_rows(data):
    counts = data["counts"]
    totals = data["totals"]
    month_returns = data["month_returns"]
    return [
        ("Total bonds", str(counts["total"]), False),
        ("Danger", str(counts["danger"]), False),
        ("On-going", str(counts["ongoing"]), False),
        ("Completed", str(counts["completed"]), False),
        ("Total investment", totals["total_investment"], True),
        ("Till return", totals["till_return"], True),
        ("Balance", totals["balance"], True),
        ("This month received", month_returns["total"] or 0.0, True),
    ]


def _render_totals_html(data, show):
    lines = [
        '<section class="share-sec" id="share-totals">',
        f"<h2>{SECTION_TITLES['totals']}</h2>",
        "<table><tr><th>Metric</th><th>Value</th></tr>",
    ]
    for label, value, is_money in _totals_rows(data):
        rendered = _html_money(value, show) if is_money else escape(str(value))
        lines.append(f"<tr><td>{escape(label)}</td><td>{rendered}</td></tr>")
    lines.append("</table></section>")
    return "\n".join(lines)


def _render_per_bond_html(data, show):
    lines = [
        '<section class="share-sec" id="share-per-bond">',
        f"<h2>{SECTION_TITLES['per_bond']}</h2>",
        "<table><tr><th>Bond</th><th>ISIN</th><th>Status</th>"
        '<th class="num">Invested</th><th class="num">Till return</th></tr>',
    ]
    for row in data["rows"]:
        lines.append(
            "<tr>"
            f"<td>{escape(str(row['company'] or ''))}</td>"
            f"<td>{escape(str(row['isin'] or ''))}</td>"
            f"<td>{escape(str(row['status'] or ''))}</td>"
            f'<td class="num">{_html_money(row["amount"], show)}</td>'
            f'<td class="num">{_html_money(row["till_return"], show)}</td>'
            "</tr>"
        )
    lines.append("</table></section>")
    return "\n".join(lines)


def _render_history_html(data, show):
    lines = [
        '<section class="share-sec" id="share-history">',
        f"<h2>{SECTION_TITLES['history']}</h2>",
        "<table><tr><th>Month</th><th class=\"num\">Received</th></tr>",
    ]
    for row in data["rows"]:
        lines.append(
            "<tr>"
            f"<td>{escape(str(row['month'] or ''))}</td>"
            f'<td class="num">{_html_money(row["total"], show)}</td>'
            "</tr>"
        )
    lines.append("</table></section>")
    return "\n".join(lines)


def _render_alerts_html(data):
    lines = [
        '<section class="share-sec" id="share-alerts">',
        f"<h2>{SECTION_TITLES['alerts']}</h2>",
        "<table><tr><th>Severity</th><th>Message</th><th>Created</th></tr>",
    ]
    for row in data["rows"]:
        lines.append(
            "<tr>"
            f"<td>{escape(str(row['severity'] or ''))}</td>"
            f"<td>{escape(str(row['message'] or ''))}</td>"
            f"<td>{escape(str(row['created_at'] or ''))}</td>"
            "</tr>"
        )
    lines.append("</table></section>")
    return "\n".join(lines)


_HTML_RENDERERS = {
    "totals": _render_totals_html,
    "per_bond": _render_per_bond_html,
    "history": _render_history_html,
}


def _render_snapshot_html(selected, data, show):
    blocks = []
    for key in selected:
        if key == "alerts":
            blocks.append(_render_alerts_html(data[key]))
        else:
            blocks.append(_HTML_RENDERERS[key](data[key], show))
    body = "\n".join(blocks)
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        "<title>DK Bond Tracker — Share snapshot</title>\n"
        f"<style>{SHARE_STYLE}</style>\n"
        "</head>\n"
        "<body>\n"
        '<div class="sheet">\n'
        "<h1>Share snapshot</h1>\n"
        f'<p class="sub">Selected sections: {escape(", ".join(SECTION_TITLES[key] for key in selected))}</p>\n'
        f"{body}\n"
        '<p class="foot">generated offline by DK Bond Tracker — personal use; not a tax or audit document.</p>\n'
        "</div>\n"
        "</body>\n"
        "</html>\n"
    )


def _render_totals_csv(data, show):
    records = [["section", "totals"], ["metric", "value"]]
    for label, value, is_money in _totals_rows(data):
        cell = _csv_money(value, show) if is_money else str(value)
        records.append([label, cell])
    return records


def _render_per_bond_csv(data, show):
    records = [
        ["section", "per_bond"],
        ["company", "isin", "status", "invested", "till_return"],
    ]
    for row in data["rows"]:
        records.append(
            [
                str(row["company"] or ""),
                str(row["isin"] or ""),
                str(row["status"] or ""),
                _csv_money(row["amount"], show),
                _csv_money(row["till_return"], show),
            ]
        )
    return records


def _render_history_csv(data, show):
    records = [["section", "history"], ["month", "total"]]
    for row in data["rows"]:
        records.append([str(row["month"] or ""), _csv_money(row["total"], show)])
    return records


def _render_alerts_csv(data, show):
    records = [["section", "alerts"], ["severity", "message", "created_at"]]
    for row in data["rows"]:
        records.append(
            [
                str(row["severity"] or ""),
                str(row["message"] or ""),
                str(row["created_at"] or ""),
            ]
        )
    return records


_CSV_RENDERERS = {
    "totals": _render_totals_csv,
    "per_bond": _render_per_bond_csv,
    "history": _render_history_csv,
    "alerts": _render_alerts_csv,
}


def build_share_snapshot(conn, sections, include_amounts, privacy_on=False):
    selected = _selected_sections(sections)
    show = bool(include_amounts) and not bool(privacy_on)
    try:
        data = {key: _load_section(conn, key) for key in selected}
        return _render_snapshot_html(selected, data, show)
    except AppError:
        raise
    except Exception as exc:
        raise AppError("ERR-share-export", f"snapshot build failed: {exc}") from exc


def share_csv(conn, sections, include_amounts=True, privacy_on=False):
    selected = _selected_sections(sections)
    show = bool(include_amounts) and not bool(privacy_on)
    try:
        data = {key: _load_section(conn, key) for key in selected}
        records = []
        for key in selected:
            records.extend(_CSV_RENDERERS[key](data[key], show))
        return serialize_records(records)
    except AppError:
        raise
    except Exception as exc:
        raise AppError("ERR-share-export", f"CSV build failed: {exc}") from exc
