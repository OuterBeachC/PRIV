#!/usr/bin/env python3
"""
export_asset_data.py - Export all historical data for a given asset to CSV

Queries the priv_data.db SQLite database for all records matching an asset
by name, identifier (CUSIP), or SEDOL, and writes the results to a CSV file.
"""

import sqlite3
import pandas as pd
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
        os.path.join(script_dir, "..", "..", default_name),
        os.path.join(script_dir, "data", default_name),
        os.path.join(script_dir, "..", "data", default_name),
    ]

    for location in possible_locations:
        abs_path = os.path.abspath(location)
        if os.path.exists(abs_path):
            return abs_path

    return os.path.abspath(default_name)


def list_assets(db_path, fund=None):
    """List all unique assets in the database."""
    conn = sqlite3.connect(db_path)
    try:
        query = """
            SELECT DISTINCT name, identifier, sedol, source_identifier,
                   COUNT(*) as observations,
                   MIN(date) as first_seen,
                   MAX(date) as last_seen
            FROM financial_data
        """
        params = []
        if fund:
            query += " WHERE source_identifier = ?"
            params.append(fund)
        query += " GROUP BY name, identifier, source_identifier ORDER BY name"

        df = pd.read_sql(query, conn, params=params)
        return df
    finally:
        conn.close()


def search_assets(db_path, search_term, fund=None):
    """Search for assets matching a term (partial match on name, identifier, or SEDOL)."""
    conn = sqlite3.connect(db_path)
    try:
        query = """
            SELECT DISTINCT name, identifier, sedol, source_identifier,
                   COUNT(*) as observations,
                   MIN(date) as first_seen,
                   MAX(date) as last_seen
            FROM financial_data
            WHERE (name LIKE ? OR identifier LIKE ? OR sedol LIKE ?)
        """
        like_term = f"%{search_term}%"
        params = [like_term, like_term, like_term]

        if fund:
            query += " AND source_identifier = ?"
            params.append(fund)

        query += " GROUP BY name, identifier, source_identifier ORDER BY name"

        df = pd.read_sql(query, conn, params=params)
        return df
    finally:
        conn.close()


def export_asset_data(db_path, asset, fund=None, start_date=None, end_date=None):
    """
    Query all historical data for a given asset.

    The asset argument is matched against name, identifier, and SEDOL columns.
    An exact match is tried first; if no results, a partial (LIKE) match is used.

    Returns:
        pd.DataFrame with all matching rows sorted by date.
    """
    conn = sqlite3.connect(db_path)
    try:
        # Try exact match first
        query = """
            SELECT date, name, identifier, sedol, weight, coupon,
                   par_value, market_value, local_currency, maturity,
                   asset_breakdown, source_identifier
            FROM financial_data
            WHERE (name = ? OR identifier = ? OR sedol = ?)
        """
        params = [asset, asset, asset]

        if fund:
            query += " AND source_identifier = ?"
            params.append(fund)
        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)

        query += " ORDER BY date"

        df = pd.read_sql(query, conn, params=params)

        # If no exact match, try partial match
        if df.empty:
            like_term = f"%{asset}%"
            query = """
                SELECT date, name, identifier, sedol, weight, coupon,
                       par_value, market_value, local_currency, maturity,
                       asset_breakdown, source_identifier
                FROM financial_data
                WHERE (name LIKE ? OR identifier LIKE ? OR sedol LIKE ?)
            """
            params = [like_term, like_term, like_term]

            if fund:
                query += " AND source_identifier = ?"
                params.append(fund)
            if start_date:
                query += " AND date >= ?"
                params.append(start_date)
            if end_date:
                query += " AND date <= ?"
                params.append(end_date)

            query += " ORDER BY date"

            df = pd.read_sql(query, conn, params=params)

        return df
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="Export all historical data for a given asset to CSV",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python export_asset_data.py "TREASURY NOTE 3.875 06/30/2030"
  python export_asset_data.py US3132DWPR87
  python export_asset_data.py "AP Grange" --fund HIYS
  python export_asset_data.py "TREASURY NOTE" --start-date 1/1/2026 --end-date 1/31/2026
  python export_asset_data.py --search "MORTGAGE"
  python export_asset_data.py --list --fund PRIV
        """
    )

    parser.add_argument(
        "asset", nargs="?",
        help="Asset name, identifier (CUSIP), or SEDOL to look up"
    )
    parser.add_argument(
        "-d", "--database", default="priv_data.db",
        help="Path to SQLite database file (default: priv_data.db)"
    )
    parser.add_argument(
        "--fund",
        help="Filter by fund/source identifier (e.g. PRIV, PRSD, HIYS)"
    )
    parser.add_argument(
        "--start-date",
        help="Start date filter (inclusive, format: M/D/YYYY)"
    )
    parser.add_argument(
        "--end-date",
        help="End date filter (inclusive, format: M/D/YYYY)"
    )
    parser.add_argument(
        "-o", "--output",
        help="Output CSV file path (default: <asset>_history.csv)"
    )
    parser.add_argument(
        "--list", action="store_true",
        help="List all unique assets in the database and exit"
    )
    parser.add_argument(
        "--search",
        help="Search for assets matching a term and exit"
    )

    args = parser.parse_args()

    # Find database
    db_path = find_database(args.database)
    if not os.path.exists(db_path):
        print(f"Error: Database not found at {db_path}", file=sys.stderr)
        return 1

    print(f"Using database: {db_path}")

    # List mode
    if args.list:
        df = list_assets(db_path, fund=args.fund)
        if df.empty:
            print("No assets found.")
            return 0
        print(f"\nFound {len(df)} unique assets:\n")
        print(df.to_string(index=False))
        return 0

    # Search mode
    if args.search:
        df = search_assets(db_path, args.search, fund=args.fund)
        if df.empty:
            print(f"No assets matching '{args.search}'.")
            return 0
        print(f"\nFound {len(df)} assets matching '{args.search}':\n")
        print(df.to_string(index=False))
        return 0

    # Export mode — asset argument is required
    if not args.asset:
        parser.error("Please provide an asset name/identifier, or use --list / --search")

    # Query historical data
    print(f"Querying historical data for: {args.asset}")
    if args.fund:
        print(f"  Fund filter: {args.fund}")
    if args.start_date:
        print(f"  Start date: {args.start_date}")
    if args.end_date:
        print(f"  End date: {args.end_date}")

    df = export_asset_data(
        db_path,
        args.asset,
        fund=args.fund,
        start_date=args.start_date,
        end_date=args.end_date,
    )

    if df.empty:
        print(f"\nNo records found for '{args.asset}'.")
        return 1

    # Determine output filename
    if args.output:
        output_file = args.output
    else:
        # Sanitize the asset string for use as a filename
        safe_name = args.asset.replace("/", "-").replace(" ", "_").replace(".", "_")
        safe_name = "".join(c for c in safe_name if c.isalnum() or c in ("_", "-"))
        output_file = f"{safe_name}_history.csv"

    # Show summary before writing
    unique_names = df["name"].unique()
    unique_dates = df["date"].unique()
    print(f"\nResults:")
    print(f"  Matched asset(s): {len(unique_names)}")
    for name in unique_names:
        print(f"    - {name}")
    print(f"  Total records: {len(df)}")
    print(f"  Date range: {df['date'].iloc[0]} to {df['date'].iloc[-1]}")
    print(f"  Unique dates: {len(unique_dates)}")

    # Write CSV
    df.to_csv(output_file, index=False)
    print(f"\nExported to: {output_file}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
