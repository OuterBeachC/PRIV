#!/usr/bin/env python3
"""
Weekly Asset Export Report
Exports all new assets for PRIV and PRSD and maps all par value changes
between given dates from the database.

Usage:
    python weekly_asset_export_report.py --start-date 2026-01-06 --end-date 2026-01-12
    python weekly_asset_export_report.py  # defaults to last 7 calendar days
    python weekly_asset_export_report.py --fund PRIV --format csv
"""

import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import argparse
import sys
import os


def find_database(default_name="priv_data.db"):
    """Find the database file in common locations."""
    script_dir = os.path.dirname(os.path.abspath(__file__))

    possible_locations = [
        default_name,
        os.path.join(script_dir, default_name),
        os.path.join(script_dir, "..", default_name),
        os.path.join(script_dir, "data", default_name),
    ]

    for location in possible_locations:
        abs_path = os.path.abspath(location)
        if os.path.exists(abs_path):
            return abs_path

    return os.path.abspath(default_name)


def load_fund_data(db_path, fund_symbol):
    """Load all data for a specific fund from the database."""
    conn = sqlite3.connect(db_path)
    try:
        df = pd.read_sql(
            "SELECT * FROM financial_data WHERE source_identifier = ?",
            conn,
            params=(fund_symbol,),
        )
        df["date"] = pd.to_datetime(df["date"])
        # Coerce numeric columns that may contain non-numeric strings
        for col in ("par_value", "market_value", "weight"):
            df[col] = pd.to_numeric(df[col], errors="coerce")
        return df
    except Exception as e:
        print(f"Error loading data for {fund_symbol}: {e}", file=sys.stderr)
        return pd.DataFrame()
    finally:
        conn.close()


def get_available_dates(db_path, fund_symbol):
    """Return sorted list of available dates for a fund."""
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT DISTINCT date FROM financial_data WHERE source_identifier = ?",
            (fund_symbol,),
        ).fetchall()
        dates = sorted(pd.to_datetime([r[0] for r in rows]))
        return dates
    finally:
        conn.close()


def resolve_boundary_dates(available_dates, start_date, end_date):
    """
    Find the closest available dates on or within the requested range.

    Returns (resolved_start, resolved_end) as datetime objects, or (None, None)
    if no data falls in the range.
    """
    if not available_dates:
        return None, None

    dates_in_range = [d for d in available_dates if start_date <= d <= end_date]
    if len(dates_in_range) < 1:
        return None, None

    return min(dates_in_range), max(dates_in_range)


def composite_key(row):
    """Return a stable identifier for an asset row."""
    return row["name"] if row["identifier"] == "-" else row["identifier"]


def detect_new_assets(df, start_date, end_date):
    """
    Identify assets present on end_date that were not present on start_date.

    Returns a DataFrame with columns:
        Date, Name, Identifier, Par Value, Market Value, Last Price, Asset Type
    """
    df_start = df[df["date"] == start_date].copy()
    df_end = df[df["date"] == end_date].copy()

    df_start["_key"] = df_start.apply(composite_key, axis=1)
    df_end["_key"] = df_end.apply(composite_key, axis=1)

    start_keys = set(df_start["_key"])
    new_mask = ~df_end["_key"].isin(start_keys)
    new = df_end[new_mask].copy()

    if new.empty:
        return pd.DataFrame(
            columns=["Date", "Name", "Identifier", "Par Value",
                      "Market Value", "Last Price", "Asset Type"]
        )

    new["last_price"] = new.apply(
        lambda r: round(r["market_value"] / r["par_value"] * 100, 4)
        if pd.notna(r["par_value"]) and r["par_value"] != 0
        else None,
        axis=1,
    )
    out = new[["date", "name", "identifier", "par_value", "market_value",
               "last_price", "asset_breakdown"]].copy()
    out.columns = ["Date", "Name", "Identifier", "Par Value",
                   "Market Value", "Last Price", "Asset Type"]
    out["Date"] = out["Date"].dt.strftime("%Y-%m-%d")
    out = out.sort_values("Name").reset_index(drop=True)
    return out


def detect_removed_assets(df, start_date, end_date):
    """
    Identify assets present on start_date that are no longer present on end_date.

    Returns a DataFrame with columns:
        Date, Name, Identifier, Par Value, Market Value, Last Price, Asset Type
    """
    df_start = df[df["date"] == start_date].copy()
    df_end = df[df["date"] == end_date].copy()

    df_start["_key"] = df_start.apply(composite_key, axis=1)
    df_end["_key"] = df_end.apply(composite_key, axis=1)

    end_keys = set(df_end["_key"])
    removed_mask = ~df_start["_key"].isin(end_keys)
    removed = df_start[removed_mask].copy()

    if removed.empty:
        return pd.DataFrame(
            columns=["Date", "Name", "Identifier", "Par Value",
                      "Market Value", "Last Price", "Asset Type"]
        )

    removed["last_price"] = removed.apply(
        lambda r: round(r["market_value"] / r["par_value"] * 100, 4)
        if pd.notna(r["par_value"]) and r["par_value"] != 0
        else None,
        axis=1,
    )
    out = removed[["date", "name", "identifier", "par_value", "market_value",
                    "last_price", "asset_breakdown"]].copy()
    out.columns = ["Date", "Name", "Identifier", "Par Value",
                   "Market Value", "Last Price", "Asset Type"]
    out["Date"] = out["Date"].dt.strftime("%Y-%m-%d")
    out = out.sort_values("Name").reset_index(drop=True)
    return out


def map_par_value_changes(df, available_dates, start_date, end_date):
    """
    Track par value changes for every asset across consecutive observation
    dates within the range.

    Returns a DataFrame with columns:
        Date, Name, Identifier, Par Value (Previous), Par Value (Current),
        Par Change, Asset Type
    """
    dates_in_range = sorted(
        d for d in available_dates if start_date <= d <= end_date
    )

    if len(dates_in_range) < 2:
        return pd.DataFrame(
            columns=["Date", "Name", "Identifier", "Par Value (Previous)",
                      "Par Value (Current)", "Par Change", "Asset Type"]
        )

    df_range = df[df["date"].isin(dates_in_range)].copy()
    df_range["_key"] = df_range.apply(composite_key, axis=1)
    df_range = df_range.sort_values(["_key", "date"])

    changes = []
    for key, group in df_range.groupby("_key"):
        if len(group) < 2:
            continue
        par_vals = group["par_value"].values
        diffs = pd.Series(par_vals).diff()

        for i in range(1, len(group)):
            diff = diffs.iloc[i]
            if diff != 0 and pd.notna(diff):
                row = group.iloc[i]
                prev_row = group.iloc[i - 1]
                changes.append(
                    {
                        "Date": row["date"],
                        "Name": row["name"],
                        "Identifier": row["identifier"],
                        "Par Value (Previous)": prev_row["par_value"],
                        "Par Value (Current)": row["par_value"],
                        "Par Change": round(diff, 2),
                        "Asset Type": row["asset_breakdown"],
                    }
                )

    if not changes:
        return pd.DataFrame(
            columns=["Date", "Name", "Identifier", "Par Value (Previous)",
                      "Par Value (Current)", "Par Change", "Asset Type"]
        )

    out = pd.DataFrame(changes)
    out["Date"] = pd.to_datetime(out["Date"]).dt.strftime("%Y-%m-%d")
    out = out.sort_values(["Date", "Name"], ascending=[False, True]).reset_index(
        drop=True
    )
    return out


def build_fund_report(db_path, fund_symbol, start_date, end_date):
    """
    Build the full report for a single fund between the given dates.

    Returns a dict with keys:
        summary, new_assets, removed_assets, par_changes
    """
    df = load_fund_data(db_path, fund_symbol)
    if df.empty:
        return {"error": f"No data available for {fund_symbol}"}

    available = get_available_dates(db_path, fund_symbol)
    resolved_start, resolved_end = resolve_boundary_dates(
        available, start_date, end_date
    )

    if resolved_start is None or resolved_end is None:
        return {
            "error": (
                f"No data for {fund_symbol} in range "
                f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
            )
        }

    if resolved_start == resolved_end:
        return {
            "error": (
                f"Only one observation date for {fund_symbol} in range; "
                "need at least two dates to compare."
            )
        }

    new_assets = detect_new_assets(df, resolved_start, resolved_end)
    removed_assets = detect_removed_assets(df, resolved_start, resolved_end)
    par_changes = map_par_value_changes(df, available, resolved_start, resolved_end)

    df_end = df[df["date"] == resolved_end]

    summary = {
        "fund": fund_symbol,
        "start_date": resolved_start.strftime("%Y-%m-%d"),
        "end_date": resolved_end.strftime("%Y-%m-%d"),
        "observation_dates": len(
            [d for d in available if resolved_start <= d <= resolved_end]
        ),
        "total_market_value": df_end["market_value"].sum(),
        "total_par_value": df_end["par_value"].sum(),
        "securities_count": len(df_end),
        "new_assets_count": len(new_assets),
        "removed_assets_count": len(removed_assets),
        "par_changes_count": len(par_changes),
    }

    return {
        "summary": summary,
        "new_assets": new_assets,
        "removed_assets": removed_assets,
        "par_changes": par_changes,
    }


def generate_report(db_path, funds, start_date, end_date):
    """
    Generate the combined weekly asset export report for the requested funds.

    Returns a dict keyed by fund symbol, each containing that fund's report.
    """
    results = {}
    for fund in funds:
        results[fund] = build_fund_report(db_path, fund, start_date, end_date)
    return results


# ---------------------------------------------------------------------------
# Export helpers
# ---------------------------------------------------------------------------


def _fund_section_csv(f, fund, report):
    """Write a single fund's section into the combined CSV."""
    s = report["summary"]
    f.write(f"# {fund} Report\n")
    f.write(f"# Period: {s['start_date']} to {s['end_date']}\n")
    f.write(f"# Observation Dates: {s['observation_dates']}\n")
    f.write(f"# Total Market Value: ${s['total_market_value']:,.2f}\n")
    f.write(f"# Total Par Value: ${s['total_par_value']:,.2f}\n")
    f.write(f"# Securities Count: {s['securities_count']}\n")
    f.write(f"# New Assets: {s['new_assets_count']}\n")
    f.write(f"# Removed Assets: {s['removed_assets_count']}\n")
    f.write(f"# Par Value Changes: {s['par_changes_count']}\n\n")

    f.write(f"# {fund} - NEW ASSETS\n")
    if not report["new_assets"].empty:
        report["new_assets"].to_csv(f, index=False)
    else:
        f.write("# (none)\n")
    f.write("\n")

    f.write(f"# {fund} - REMOVED ASSETS\n")
    if not report["removed_assets"].empty:
        report["removed_assets"].to_csv(f, index=False)
    else:
        f.write("# (none)\n")
    f.write("\n")

    f.write(f"# {fund} - PAR VALUE CHANGES\n")
    if not report["par_changes"].empty:
        report["par_changes"].to_csv(f, index=False)
    else:
        f.write("# (none)\n")
    f.write("\n")


def export_csv(reports, output_dir):
    """Export reports as CSV files (per-fund + combined)."""
    files = []

    for fund, report in reports.items():
        if "error" in report:
            continue

        s = report["summary"]
        tag = f"{fund}_{s['start_date']}_to_{s['end_date']}"

        # Individual section CSVs
        if not report["new_assets"].empty:
            path = os.path.join(output_dir, f"new_assets_{tag}.csv")
            report["new_assets"].to_csv(path, index=False)
            files.append(path)

        if not report["removed_assets"].empty:
            path = os.path.join(output_dir, f"removed_assets_{tag}.csv")
            report["removed_assets"].to_csv(path, index=False)
            files.append(path)

        if not report["par_changes"].empty:
            path = os.path.join(output_dir, f"par_changes_{tag}.csv")
            report["par_changes"].to_csv(path, index=False)
            files.append(path)

    # Combined CSV
    any_report = next(
        (r for r in reports.values() if "error" not in r), None
    )
    if any_report:
        s = any_report["summary"]
        combined_path = os.path.join(
            output_dir,
            f"weekly_asset_report_{s['start_date']}_to_{s['end_date']}.csv",
        )
        with open(combined_path, "w") as f:
            f.write(
                f"# Weekly Asset Export Report: "
                f"{s['start_date']} to {s['end_date']}\n\n"
            )
            for fund, report in reports.items():
                if "error" in report:
                    f.write(f"# {fund}: {report['error']}\n\n")
                    continue
                _fund_section_csv(f, fund, report)
                f.write("\n")
        files.append(combined_path)

    return files


def _html_table(df):
    """Render a DataFrame as an HTML table string."""
    if df.empty:
        return '<div class="no-data">No data for this section</div>'

    html = "<table>\n<thead>\n<tr>\n"
    for col in df.columns:
        html += f"  <th>{col}</th>\n"
    html += "</tr>\n</thead>\n<tbody>\n"

    for _, row in df.iterrows():
        html += "<tr>\n"
        for col in df.columns:
            val = row[col]
            if "Change" in col and isinstance(val, (int, float)):
                css = "positive" if val > 0 else "negative" if val < 0 else ""
                sign = "+" if val > 0 else ""
                html += f'  <td class="{css}">{sign}{val:,.2f}</td>\n'
            elif isinstance(val, float):
                html += f"  <td>{val:,.4f}</td>\n"
            else:
                html += f"  <td>{val}</td>\n"
        html += "</tr>\n"

    html += "</tbody>\n</table>\n"
    return html


def export_html(reports, output_dir):
    """Export as a single combined HTML report."""
    any_report = next(
        (r for r in reports.values() if "error" not in r), None
    )
    if not any_report:
        return []

    s = any_report["summary"]
    funds_label = " / ".join(reports.keys())

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>Weekly Asset Export Report - {funds_label}</title>
<style>
body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
    max-width: 1000px; margin: 40px auto; padding: 0 20px;
    color: #333; line-height: 1.6;
}}
h1 {{ color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }}
h2 {{ color: #2c3e50; margin-top: 40px; }}
h3 {{ color: #34495e; margin-top: 25px; border-bottom: 1px solid #ecf0f1; padding-bottom: 6px; }}
.summary {{
    background: #f8f9fa; border-left: 4px solid #3498db;
    padding: 15px 20px; margin: 20px 0;
}}
.summary-grid {{
    display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 12px; margin-top: 12px;
}}
.summary-item {{ padding: 8px; background: white; border-radius: 4px; }}
.summary-label {{ font-size: 0.85em; color: #7f8c8d; }}
.summary-value {{ font-size: 1.2em; font-weight: bold; color: #2c3e50; }}
table {{ width: 100%; border-collapse: collapse; margin: 15px 0; background: white; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
th {{ background: #3498db; color: white; padding: 10px 12px; text-align: left; }}
td {{ padding: 8px 12px; border-bottom: 1px solid #ecf0f1; }}
tr:hover {{ background: #f8f9fa; }}
.positive {{ color: #27ae60; }}
.negative {{ color: #e74c3c; }}
.no-data {{ color: #95a5a6; font-style: italic; padding: 15px; text-align: center; }}
.footer {{ margin-top: 40px; padding-top: 15px; border-top: 1px solid #ecf0f1; font-size: 0.9em; color: #7f8c8d; }}
</style>
</head>
<body>
<h1>{funds_label} Weekly Asset Export Report</h1>
<p><strong>Period:</strong> {s['start_date']} to {s['end_date']}</p>
"""

    for fund, report in reports.items():
        if "error" in report:
            html += f"<h2>{fund}</h2>\n<p>{report['error']}</p>\n"
            continue

        fs = report["summary"]
        html += f"""
<h2>{fund}</h2>
<div class="summary">
<div class="summary-grid">
  <div class="summary-item"><div class="summary-label">Total Market Value</div><div class="summary-value">${fs['total_market_value']:,.2f}</div></div>
  <div class="summary-item"><div class="summary-label">Total Par Value</div><div class="summary-value">${fs['total_par_value']:,.2f}</div></div>
  <div class="summary-item"><div class="summary-label">Securities</div><div class="summary-value">{fs['securities_count']}</div></div>
  <div class="summary-item"><div class="summary-label">New Assets</div><div class="summary-value">{fs['new_assets_count']}</div></div>
  <div class="summary-item"><div class="summary-label">Removed</div><div class="summary-value">{fs['removed_assets_count']}</div></div>
  <div class="summary-item"><div class="summary-label">Par Changes</div><div class="summary-value">{fs['par_changes_count']}</div></div>
</div>
</div>
"""
        html += f"<h3>{fund} - New Assets</h3>\n"
        html += _html_table(report["new_assets"])

        html += f"<h3>{fund} - Removed Assets</h3>\n"
        html += _html_table(report["removed_assets"])

        html += f"<h3>{fund} - Par Value Changes</h3>\n"
        html += _html_table(report["par_changes"])

    html += """
<div class="footer">
<strong>Disclosure:</strong> All information displayed here is public and is not in any way to be
construed as investment advice or solicitation. Data is sourced from public filings and we make no
claims to veracity or accuracy of the data. It is presented for academic and research purposes only.
</div>
</body>
</html>
"""

    out_path = os.path.join(
        output_dir,
        f"weekly_asset_report_{s['start_date']}_to_{s['end_date']}.html",
    )
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    return [out_path]


def export_markdown(reports, output_dir):
    """Export as a combined Markdown report."""
    any_report = next(
        (r for r in reports.values() if "error" not in r), None
    )
    if not any_report:
        return []

    s = any_report["summary"]
    funds_label = " / ".join(reports.keys())

    md = f"# {funds_label} Weekly Asset Export Report\n\n"
    md += f"**Period:** {s['start_date']} to {s['end_date']}\n\n---\n\n"

    for fund, report in reports.items():
        if "error" in report:
            md += f"## {fund}\n\n{report['error']}\n\n"
            continue

        fs = report["summary"]
        md += f"## {fund}\n\n"
        md += "| Metric | Value |\n|--------|-------|\n"
        md += f"| Total Market Value | ${fs['total_market_value']:,.2f} |\n"
        md += f"| Total Par Value | ${fs['total_par_value']:,.2f} |\n"
        md += f"| Securities Count | {fs['securities_count']} |\n"
        md += f"| New Assets | {fs['new_assets_count']} |\n"
        md += f"| Removed Assets | {fs['removed_assets_count']} |\n"
        md += f"| Par Value Changes | {fs['par_changes_count']} |\n\n"

        md += f"### {fund} - New Assets\n\n"
        if not report["new_assets"].empty:
            md += report["new_assets"].to_markdown(index=False) + "\n\n"
        else:
            md += "*No new assets*\n\n"

        md += f"### {fund} - Removed Assets\n\n"
        if not report["removed_assets"].empty:
            md += report["removed_assets"].to_markdown(index=False) + "\n\n"
        else:
            md += "*No removed assets*\n\n"

        md += f"### {fund} - Par Value Changes\n\n"
        if not report["par_changes"].empty:
            md += report["par_changes"].to_markdown(index=False) + "\n\n"
        else:
            md += "*No par value changes*\n\n"

        md += "---\n\n"

    md += (
        "**Disclosure:** All information displayed here is public and is not in any "
        "way to be construed as investment advice or solicitation. Data is sourced from "
        "public filings and we make no claims to veracity or accuracy of the data. "
        "It is presented for academic and research purposes only.\n"
    )

    out_path = os.path.join(
        output_dir,
        f"weekly_asset_report_{s['start_date']}_to_{s['end_date']}.md",
    )
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(md)
    return [out_path]


def export_substack(reports, output_dir):
    """Export as plain text optimized for Substack copy/paste."""
    any_report = next(
        (r for r in reports.values() if "error" not in r), None
    )
    if not any_report:
        return []

    s = any_report["summary"]
    funds_label = " / ".join(reports.keys())

    txt = f"{'='*70}\n"
    txt += f"{funds_label} WEEKLY ASSET EXPORT REPORT\n"
    txt += f"{'='*70}\n\n"
    txt += f"Period: {s['start_date']} to {s['end_date']}\n\n"

    for fund, report in reports.items():
        if "error" in report:
            txt += f"{fund}: {report['error']}\n\n"
            continue

        fs = report["summary"]
        txt += f"{'='*70}\n"
        txt += f"{fund} SUMMARY\n"
        txt += f"{'='*70}\n"
        txt += f"Total Market Value:    ${fs['total_market_value']:>20,.2f}\n"
        txt += f"Total Par Value:       ${fs['total_par_value']:>20,.2f}\n"
        txt += f"Securities Count:      {fs['securities_count']:>20}\n"
        txt += f"New Assets:            {fs['new_assets_count']:>20}\n"
        txt += f"Removed Assets:        {fs['removed_assets_count']:>20}\n"
        txt += f"Par Value Changes:     {fs['par_changes_count']:>20}\n\n"

        txt += f"{'─'*70}\n{fund} - NEW ASSETS\n{'─'*70}\n\n"
        if not report["new_assets"].empty:
            for _, row in report["new_assets"].iterrows():
                txt += f"Date:        {row['Date']}\n"
                txt += f"Name:        {row['Name']}\n"
                txt += f"Identifier:  {row['Identifier']}\n"
                txt += f"Par Value:   ${row['Par Value']:,.2f}\n"
                txt += f"Last Price:  {row['Last Price']:.4f}\n"
                txt += f"Asset Type:  {row['Asset Type']}\n"
                txt += f"{'-'*70}\n"
        else:
            txt += "(none)\n"
        txt += "\n"

        txt += f"{'─'*70}\n{fund} - REMOVED ASSETS\n{'─'*70}\n\n"
        if not report["removed_assets"].empty:
            for _, row in report["removed_assets"].iterrows():
                txt += f"Date:        {row['Date']}\n"
                txt += f"Name:        {row['Name']}\n"
                txt += f"Identifier:  {row['Identifier']}\n"
                txt += f"Par Value:   ${row['Par Value']:,.2f}\n"
                txt += f"Last Price:  {row['Last Price']:.4f}\n"
                txt += f"Asset Type:  {row['Asset Type']}\n"
                txt += f"{'-'*70}\n"
        else:
            txt += "(none)\n"
        txt += "\n"

        txt += f"{'─'*70}\n{fund} - PAR VALUE CHANGES\n{'─'*70}\n\n"
        if not report["par_changes"].empty:
            for _, row in report["par_changes"].iterrows():
                sign = "+" if row["Par Change"] > 0 else ""
                txt += f"Date:            {row['Date']}\n"
                txt += f"Name:            {row['Name']}\n"
                txt += f"Identifier:      {row['Identifier']}\n"
                txt += f"Previous Par:    ${row['Par Value (Previous)']:,.2f}\n"
                txt += f"Current Par:     ${row['Par Value (Current)']:,.2f}\n"
                txt += f"Par Change:      {sign}${row['Par Change']:,.2f}\n"
                txt += f"Asset Type:      {row['Asset Type']}\n"
                txt += f"{'-'*70}\n"
        else:
            txt += "(none)\n"
        txt += "\n"

    txt += f"{'='*70}\nDISCLOSURE\n{'='*70}\n"
    txt += (
        "All information displayed here is public and is not in any way to be\n"
        "construed as investment advice or solicitation. Data is sourced from\n"
        "public filings and we make no claims to veracity or accuracy of the\n"
        "data. It is presented for academic and research purposes only.\n"
    )

    out_path = os.path.join(
        output_dir,
        f"weekly_asset_report_{s['start_date']}_to_{s['end_date']}_substack.txt",
    )
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(txt)
    return [out_path]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def print_summary(reports):
    """Print a human-readable summary to stdout."""
    for fund, report in reports.items():
        if "error" in report:
            print(f"\n{fund}: {report['error']}")
            continue

        s = report["summary"]
        print(f"\n{'='*60}")
        print(f"  {fund}  |  {s['start_date']}  ->  {s['end_date']}  "
              f"({s['observation_dates']} observation dates)")
        print(f"{'='*60}")
        print(f"  Total Market Value: ${s['total_market_value']:>18,.2f}")
        print(f"  Total Par Value:    ${s['total_par_value']:>18,.2f}")
        print(f"  Securities Count:   {s['securities_count']:>19}")
        print(f"  New Assets:         {s['new_assets_count']:>19}")
        print(f"  Removed Assets:     {s['removed_assets_count']:>19}")
        print(f"  Par Value Changes:  {s['par_changes_count']:>19}")
        print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Weekly Asset Export Report - exports new assets and par value "
            "changes for PRIV and PRSD between given dates."
        )
    )
    parser.add_argument(
        "--db",
        default="priv_data.db",
        help="Path to database file (default: priv_data.db)",
    )
    parser.add_argument(
        "--fund",
        nargs="+",
        default=["PRIV", "PRSD"],
        help="Fund(s) to include (default: PRIV PRSD)",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default=None,
        help="Start date in YYYY-MM-DD format (default: 7 days before end date)",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        default=None,
        help="End date in YYYY-MM-DD format (default: today)",
    )
    parser.add_argument(
        "--format",
        choices=["csv", "html", "markdown", "substack", "all"],
        default="all",
        help="Output format (default: all)",
    )
    parser.add_argument(
        "--output-dir",
        default="output",
        help="Directory for output files (default: output/)",
    )

    args = parser.parse_args()

    # Resolve dates
    if args.end_date:
        end_date = pd.Timestamp(args.end_date)
    else:
        end_date = pd.Timestamp(datetime.now().strftime("%Y-%m-%d"))

    if args.start_date:
        start_date = pd.Timestamp(args.start_date)
    else:
        start_date = end_date - timedelta(days=7)

    if start_date >= end_date:
        print("Error: --start-date must be before --end-date", file=sys.stderr)
        return 1

    # Locate database
    db_path = find_database(args.db)
    if not os.path.exists(db_path):
        print(f"Error: Database not found at {db_path}", file=sys.stderr)
        return 1

    # Ensure output directory exists
    os.makedirs(args.output_dir, exist_ok=True)

    print(f"Database:   {db_path}")
    print(f"Funds:      {', '.join(args.fund)}")
    print(f"Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    print(f"Format:     {args.format}")
    print(f"Output dir: {os.path.abspath(args.output_dir)}")

    # Generate reports
    reports = generate_report(db_path, args.fund, start_date, end_date)

    # Print summary
    print_summary(reports)

    # Export
    all_files = []

    if args.format in ("csv", "all"):
        all_files.extend(export_csv(reports, args.output_dir))

    if args.format in ("html", "all"):
        all_files.extend(export_html(reports, args.output_dir))

    if args.format in ("markdown", "all"):
        all_files.extend(export_markdown(reports, args.output_dir))

    if args.format in ("substack", "all"):
        all_files.extend(export_substack(reports, args.output_dir))

    if all_files:
        print(f"\nFiles created ({len(all_files)}):")
        for f in all_files:
            print(f"  {f}")
    else:
        print("\nNo output files created (no data matched the criteria).")

    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
