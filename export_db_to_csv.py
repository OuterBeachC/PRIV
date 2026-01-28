#!/usr/bin/env python3
"""Export all data from priv_data.db to a CSV file."""

import sqlite3
import csv
from datetime import datetime

DB_PATH = "priv_data.db"
OUTPUT_CSV = f"priv_data_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"


def export_to_csv():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get all data from financial_data table
    cursor.execute("SELECT * FROM financial_data")
    rows = cursor.fetchall()

    # Get column names
    column_names = [description[0] for description in cursor.description]

    # Write to CSV
    with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(column_names)  # Header row
        writer.writerows(rows)

    conn.close()
    print(f"Exported {len(rows)} rows to {OUTPUT_CSV}")


if __name__ == "__main__":
    export_to_csv()
