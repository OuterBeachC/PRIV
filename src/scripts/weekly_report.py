#!/usr/bin/env python3
"""
Weekly Database Report Generator
Generates a weekly report from priv_data.db showing changes over the last week.
Export formats: CSV, HTML (for Substack), and Markdown
"""

import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import argparse
import sys


def load_data(db_path, fund_symbol):
    """Load data for a specific fund from the database."""
    conn = sqlite3.connect(db_path)
    try:
        df = pd.read_sql(
            "SELECT * FROM financial_data WHERE source_identifier = ?",
            conn,
            params=(fund_symbol,)
        )
        df["date"] = pd.to_datetime(df["date"])
        return df
    except Exception as e:
        print(f"Error loading data for {fund_symbol}: {str(e)}", file=sys.stderr)
        return pd.DataFrame()
    finally:
        conn.close()


def create_composite_key(df):
    """Create composite key for asset comparison."""
    df = df.copy()
    df['composite_key'] = df.apply(
        lambda row: row['name'] if row['identifier'] == '-' else row['identifier'],
        axis=1
    )
    return df.set_index('composite_key')


def generate_weekly_report(db_path, fund_symbol="PRIV", days_back=7):
    """
    Generate a weekly report showing changes in the last week.

    Args:
        db_path: Path to the priv_data.db database
        fund_symbol: Fund to analyze (PRIV, PRSD, or HIYS)
        days_back: Number of days to look back (default 7 for weekly)

    Returns:
        Dictionary containing report data and dataframes
    """
    # Load data
    df = load_data(db_path, fund_symbol)

    if df.empty:
        return {"error": f"No data available for {fund_symbol}"}

    # Get all available dates
    available_dates = sorted(df["date"].dt.date.unique(), reverse=True)

    if len(available_dates) < 2:
        return {"error": f"Insufficient data for {fund_symbol}. Need at least 2 dates."}

    # Get most recent date and date from one week ago
    most_recent_date = available_dates[0]

    # Find the date closest to days_back trading days ago
    week_ago_idx = min(days_back, len(available_dates) - 1)
    week_ago_date = available_dates[week_ago_idx]

    # Filter data for current and previous periods
    df_current = df[df["date"].dt.date == most_recent_date].copy()
    df_previous = df[df["date"].dt.date == week_ago_date].copy()

    # Calculate Last Price for current data
    df_current["last_price"] = (df_current["market_value"] / df_current["par_value"] * 100).round(4)

    # Create indexed dataframes for comparison
    df_current_indexed = create_composite_key(df_current)
    df_previous_indexed = create_composite_key(df_previous)

    # Identify new assets
    new_assets = df_current_indexed[~df_current_indexed.index.isin(df_previous_indexed.index)].copy()

    # Identify removed assets
    removed_assets = df_previous_indexed[~df_previous_indexed.index.isin(df_current_indexed.index)].copy()

    # Identify par value changes across all dates in the range
    # Get all dates between week_ago_date and most_recent_date
    dates_in_range = [d for d in available_dates if week_ago_date <= d <= most_recent_date]
    dates_in_range.sort()  # Sort chronologically

    # Track par value changes for each asset across all dates
    par_changes_list = []

    if len(dates_in_range) >= 2:
        # Filter data for the entire date range
        df_range = df[df["date"].dt.date.isin(dates_in_range)].copy()

        # Add composite key
        df_range['composite_key'] = df_range.apply(
            lambda row: row['name'] if row['identifier'] == '-' else row['identifier'],
            axis=1
        )

        # Sort by composite_key and date
        df_range = df_range.sort_values(['composite_key', 'date'])

        # For each asset, calculate par value changes between consecutive dates
        for asset_key in df_range['composite_key'].unique():
            asset_data = df_range[df_range['composite_key'] == asset_key].copy()

            # Skip if asset only appears once in the range
            if len(asset_data) < 2:
                continue

            # Calculate changes between consecutive dates
            asset_data['par_change'] = asset_data['par_value'].diff()

            # Get rows where par value changed (skip first row which will be NaN)
            changes = asset_data[asset_data['par_change'].notna() & (asset_data['par_change'] != 0)]

            for _, row in changes.iterrows():
                par_changes_list.append({
                    'date': row['date'],
                    'name': row['name'],
                    'par_change': row['par_change'],
                    'asset_breakdown': row['asset_breakdown']
                })

    # Prepare export dataframes with requested columns

    # New Assets: Date, Name, Last Price, Asset Type
    if not new_assets.empty:
        new_assets_export = new_assets.reset_index()[["date", "name", "last_price", "asset_breakdown"]].copy()
        new_assets_export.columns = ["Date", "Name", "Last Price", "Asset Type"]
        new_assets_export["Date"] = pd.to_datetime(new_assets_export["Date"]).dt.strftime("%Y-%m-%d")
    else:
        new_assets_export = pd.DataFrame(columns=["Date", "Name", "Last Price", "Asset Type"])

    # Removed Assets: Date, Name, Last Price, Asset Type
    if not removed_assets.empty:
        removed_assets["last_price"] = (removed_assets["market_value"] / removed_assets["par_value"] * 100).round(4)
        removed_assets_export = removed_assets.reset_index()[["date", "name", "last_price", "asset_breakdown"]].copy()
        removed_assets_export.columns = ["Date", "Name", "Last Price", "Asset Type"]
        removed_assets_export["Date"] = pd.to_datetime(removed_assets_export["Date"]).dt.strftime("%Y-%m-%d")
    else:
        removed_assets_export = pd.DataFrame(columns=["Date", "Name", "Last Price", "Asset Type"])

    # Par Value Changes: Date, Name, Par Change, Asset Type
    if par_changes_list:
        par_changes_export = pd.DataFrame(par_changes_list)
        par_changes_export.columns = ["Date", "Name", "Par Change", "Asset Type"]
        par_changes_export["Date"] = pd.to_datetime(par_changes_export["Date"]).dt.strftime("%Y-%m-%d")
        par_changes_export["Par Change"] = par_changes_export["Par Change"].round(2)
        # Sort by date (most recent first) then by name
        par_changes_export = par_changes_export.sort_values(['Date', 'Name'], ascending=[False, True])
    else:
        par_changes_export = pd.DataFrame(columns=["Date", "Name", "Par Change", "Asset Type"])

    # Summary statistics
    summary = {
        "fund": fund_symbol,
        "report_date": most_recent_date.strftime("%Y-%m-%d"),
        "comparison_date": week_ago_date.strftime("%Y-%m-%d"),
        "days_back": (most_recent_date - week_ago_date).days,
        "total_market_value": df_current["market_value"].sum(),
        "total_par_value": df_current["par_value"].sum(),
        "securities_count": len(df_current),
        "new_assets_count": len(new_assets),
        "removed_assets_count": len(removed_assets),
        "par_changes_count": len(par_changes_list)
    }

    return {
        "summary": summary,
        "new_assets": new_assets_export,
        "removed_assets": removed_assets_export,
        "par_changes": par_changes_export
    }


def export_to_csv(report_data, output_prefix="weekly_report"):
    """Export report data to CSV files."""
    fund = report_data["summary"]["fund"]
    report_date = report_data["summary"]["report_date"]

    files_created = []

    # Export new assets
    if not report_data["new_assets"].empty:
        filename = f"{output_prefix}_{fund}_new_assets_{report_date}.csv"
        report_data["new_assets"].to_csv(filename, index=False)
        files_created.append(filename)

    # Export removed assets
    if not report_data["removed_assets"].empty:
        filename = f"{output_prefix}_{fund}_removed_assets_{report_date}.csv"
        report_data["removed_assets"].to_csv(filename, index=False)
        files_created.append(filename)

    # Export par changes
    if not report_data["par_changes"].empty:
        filename = f"{output_prefix}_{fund}_par_changes_{report_date}.csv"
        report_data["par_changes"].to_csv(filename, index=False)
        files_created.append(filename)

    # Export combined report
    combined_filename = f"{output_prefix}_{fund}_combined_{report_date}.csv"
    with open(combined_filename, 'w') as f:
        f.write(f"# Weekly Report for {fund}\n")
        f.write(f"# Report Date: {report_date}\n")
        f.write(f"# Comparison Date: {report_data['summary']['comparison_date']}\n")
        f.write(f"# Days Back: {report_data['summary']['days_back']}\n\n")

        f.write("# SUMMARY\n")
        f.write(f"Total Market Value,${report_data['summary']['total_market_value']:,.2f}\n")
        f.write(f"Total Par Value,${report_data['summary']['total_par_value']:,.2f}\n")
        f.write(f"Securities Count,{report_data['summary']['securities_count']}\n")
        f.write(f"New Assets,{report_data['summary']['new_assets_count']}\n")
        f.write(f"Removed Assets,{report_data['summary']['removed_assets_count']}\n")
        f.write(f"Par Value Changes,{report_data['summary']['par_changes_count']}\n\n")

        if not report_data["new_assets"].empty:
            f.write("# NEW ASSETS\n")
            report_data["new_assets"].to_csv(f, index=False)
            f.write("\n")

        if not report_data["removed_assets"].empty:
            f.write("# REMOVED ASSETS\n")
            report_data["removed_assets"].to_csv(f, index=False)
            f.write("\n")

        if not report_data["par_changes"].empty:
            f.write("# PAR VALUE CHANGES\n")
            report_data["par_changes"].to_csv(f, index=False)
            f.write("\n")

    files_created.append(combined_filename)
    return files_created


def export_to_html(report_data, output_file="weekly_report.html"):
    """Export report data to HTML format suitable for Substack."""
    summary = report_data["summary"]

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Weekly Report - {summary['fund']}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            max-width: 900px;
            margin: 40px auto;
            padding: 0 20px;
            color: #333;
            line-height: 1.6;
        }}
        h1 {{
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #34495e;
            margin-top: 30px;
            border-bottom: 2px solid #ecf0f1;
            padding-bottom: 8px;
        }}
        .summary {{
            background-color: #f8f9fa;
            border-left: 4px solid #3498db;
            padding: 15px 20px;
            margin: 20px 0;
        }}
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-top: 15px;
        }}
        .summary-item {{
            padding: 10px;
            background: white;
            border-radius: 5px;
        }}
        .summary-label {{
            font-size: 0.85em;
            color: #7f8c8d;
            margin-bottom: 5px;
        }}
        .summary-value {{
            font-size: 1.3em;
            font-weight: bold;
            color: #2c3e50;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            background: white;
            box-shadow: 0 1px 3px rgba(0,0,0,0.12);
        }}
        th {{
            background-color: #3498db;
            color: white;
            padding: 12px;
            text-align: left;
            font-weight: 600;
        }}
        td {{
            padding: 10px 12px;
            border-bottom: 1px solid #ecf0f1;
        }}
        tr:hover {{
            background-color: #f8f9fa;
        }}
        .no-data {{
            color: #95a5a6;
            font-style: italic;
            padding: 20px;
            text-align: center;
        }}
        .positive {{
            color: #27ae60;
        }}
        .negative {{
            color: #e74c3c;
        }}
        .footer {{
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #ecf0f1;
            font-size: 0.9em;
            color: #7f8c8d;
        }}
    </style>
</head>
<body>
    <h1>📊 {summary['fund']} Weekly Report</h1>

    <div class="summary">
        <strong>Report Period:</strong> {summary['comparison_date']} to {summary['report_date']} ({summary['days_back']} days)

        <div class="summary-grid">
            <div class="summary-item">
                <div class="summary-label">Total Market Value</div>
                <div class="summary-value">${summary['total_market_value']:,.2f}</div>
            </div>
            <div class="summary-item">
                <div class="summary-label">Total Par Value</div>
                <div class="summary-value">${summary['total_par_value']:,.2f}</div>
            </div>
            <div class="summary-item">
                <div class="summary-label">Securities Count</div>
                <div class="summary-value">{summary['securities_count']}</div>
            </div>
            <div class="summary-item">
                <div class="summary-label">New Assets</div>
                <div class="summary-value">{summary['new_assets_count']}</div>
            </div>
            <div class="summary-item">
                <div class="summary-label">Removed Assets</div>
                <div class="summary-value">{summary['removed_assets_count']}</div>
            </div>
            <div class="summary-item">
                <div class="summary-label">Par Value Changes</div>
                <div class="summary-value">{summary['par_changes_count']}</div>
            </div>
        </div>
    </div>
"""

    # New Assets Section
    html += "\n    <h2>➕ New Assets</h2>\n"
    if not report_data["new_assets"].empty:
        html += "    <table>\n"
        html += "        <thead>\n            <tr>\n"
        for col in report_data["new_assets"].columns:
            html += f"                <th>{col}</th>\n"
        html += "            </tr>\n        </thead>\n        <tbody>\n"

        for _, row in report_data["new_assets"].iterrows():
            html += "            <tr>\n"
            for col in report_data["new_assets"].columns:
                value = row[col]
                if col == "Last Price":
                    html += f"                <td>{value:.4f}</td>\n"
                else:
                    html += f"                <td>{value}</td>\n"
            html += "            </tr>\n"

        html += "        </tbody>\n    </table>\n"
    else:
        html += '    <div class="no-data">No new assets this week</div>\n'

    # Removed Assets Section
    html += "\n    <h2>➖ Removed Assets</h2>\n"
    if not report_data["removed_assets"].empty:
        html += "    <table>\n"
        html += "        <thead>\n            <tr>\n"
        for col in report_data["removed_assets"].columns:
            html += f"                <th>{col}</th>\n"
        html += "            </tr>\n        </thead>\n        <tbody>\n"

        for _, row in report_data["removed_assets"].iterrows():
            html += "            <tr>\n"
            for col in report_data["removed_assets"].columns:
                value = row[col]
                if col == "Last Price":
                    html += f"                <td>{value:.4f}</td>\n"
                else:
                    html += f"                <td>{value}</td>\n"
            html += "            </tr>\n"

        html += "        </tbody>\n    </table>\n"
    else:
        html += '    <div class="no-data">No removed assets this week</div>\n'

    # Par Value Changes Section
    html += "\n    <h2>🔁 Par Value Changes</h2>\n"
    if not report_data["par_changes"].empty:
        html += "    <table>\n"
        html += "        <thead>\n            <tr>\n"
        for col in report_data["par_changes"].columns:
            html += f"                <th>{col}</th>\n"
        html += "            </tr>\n        </thead>\n        <tbody>\n"

        for _, row in report_data["par_changes"].iterrows():
            html += "            <tr>\n"
            for col in report_data["par_changes"].columns:
                value = row[col]
                if col == "Par Change":
                    css_class = "positive" if value > 0 else "negative" if value < 0 else ""
                    sign = "+" if value > 0 else ""
                    html += f'                <td class="{css_class}">{sign}{value:,.2f}</td>\n'
                else:
                    html += f"                <td>{value}</td>\n"
            html += "            </tr>\n"

        html += "        </tbody>\n    </table>\n"
    else:
        html += '    <div class="no-data">No par value changes this week</div>\n'

    # Footer
    html += """
    <div class="footer">
        <strong>Disclosure:</strong> All information displayed here is public and is not in any way to be construed as investment advice or solicitation.
        Data is sourced from public filings and we make no claims to veracity or accuracy of the data.
        It is presented for academic and research purposes only.
    </div>
</body>
</html>
"""

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)

    return output_file


def export_to_markdown(report_data, output_file="weekly_report.md"):
    """Export report data to Markdown format suitable for Substack."""
    summary = report_data["summary"]

    md = f"""# 📊 {summary['fund']} Weekly Report

**Report Period:** {summary['comparison_date']} to {summary['report_date']} ({summary['days_back']} days)

## Summary

| Metric | Value |
|--------|-------|
| Total Market Value | ${summary['total_market_value']:,.2f} |
| Total Par Value | ${summary['total_par_value']:,.2f} |
| Securities Count | {summary['securities_count']} |
| New Assets | {summary['new_assets_count']} |
| Removed Assets | {summary['removed_assets_count']} |
| Par Value Changes | {summary['par_changes_count']} |

---

"""

    # New Assets Section
    md += "## ➕ New Assets\n\n"
    if not report_data["new_assets"].empty:
        md += report_data["new_assets"].to_markdown(index=False)
        md += "\n\n"
    else:
        md += "*No new assets this week*\n\n"

    # Removed Assets Section
    md += "## ➖ Removed Assets\n\n"
    if not report_data["removed_assets"].empty:
        md += report_data["removed_assets"].to_markdown(index=False)
        md += "\n\n"
    else:
        md += "*No removed assets this week*\n\n"

    # Par Value Changes Section
    md += "## 🔁 Par Value Changes\n\n"
    if not report_data["par_changes"].empty:
        md += report_data["par_changes"].to_markdown(index=False)
        md += "\n\n"
    else:
        md += "*No par value changes this week*\n\n"

    # Footer
    md += """---

**Disclosure:** All information displayed here is public and is not in any way to be construed as investment advice or solicitation.
Data is sourced from public filings and we make no claims to veracity or accuracy of the data.
It is presented for academic and research purposes only.
"""

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(md)

    return output_file


def main():
    parser = argparse.ArgumentParser(
        description="Generate weekly report from priv_data.db database"
    )
    parser.add_argument(
        "--db",
        default="priv_data.db",
        help="Path to database file (default: priv_data.db)"
    )
    parser.add_argument(
        "--fund",
        default="PRIV",
        choices=["PRIV", "PRSD", "HIYS"],
        help="Fund to analyze (default: PRIV)"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Number of trading days to look back (default: 7)"
    )
    parser.add_argument(
        "--format",
        choices=["csv", "html", "markdown", "all"],
        default="all",
        help="Output format (default: all)"
    )
    parser.add_argument(
        "--output-prefix",
        default="weekly_report",
        help="Prefix for output files (default: weekly_report)"
    )

    args = parser.parse_args()

    # Generate report
    print(f"Generating weekly report for {args.fund}...")
    print(f"Looking back {args.days} trading days...")

    report_data = generate_weekly_report(args.db, args.fund, args.days)

    if "error" in report_data:
        print(f"Error: {report_data['error']}", file=sys.stderr)
        return 1

    # Display summary
    summary = report_data["summary"]
    print(f"\n{'='*60}")
    print(f"Weekly Report Summary - {summary['fund']}")
    print(f"{'='*60}")
    print(f"Report Date:        {summary['report_date']}")
    print(f"Comparison Date:    {summary['comparison_date']}")
    print(f"Days Back:          {summary['days_back']}")
    print(f"Total Market Value: ${summary['total_market_value']:,.2f}")
    print(f"Total Par Value:    ${summary['total_par_value']:,.2f}")
    print(f"Securities Count:   {summary['securities_count']}")
    print(f"New Assets:         {summary['new_assets_count']}")
    print(f"Removed Assets:     {summary['removed_assets_count']}")
    print(f"Par Value Changes:  {summary['par_changes_count']}")
    print(f"{'='*60}\n")

    # Export based on format
    files_created = []

    if args.format in ["csv", "all"]:
        csv_files = export_to_csv(report_data, args.output_prefix)
        files_created.extend(csv_files)
        print(f"✓ CSV files created: {len(csv_files)}")
        for f in csv_files:
            print(f"  - {f}")

    if args.format in ["html", "all"]:
        html_file = export_to_html(
            report_data,
            f"{args.output_prefix}_{summary['fund']}_{summary['report_date']}.html"
        )
        files_created.append(html_file)
        print(f"✓ HTML file created: {html_file}")

    if args.format in ["markdown", "all"]:
        md_file = export_to_markdown(
            report_data,
            f"{args.output_prefix}_{summary['fund']}_{summary['report_date']}.md"
        )
        files_created.append(md_file)
        print(f"✓ Markdown file created: {md_file}")

    print(f"\n✅ Report generation complete! {len(files_created)} file(s) created.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
