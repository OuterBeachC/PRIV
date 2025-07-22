# sync_csv_to_db.py (Fixed)

import pandas as pd
import sqlite3
import sys

# === CONFIG ===
csv_file = "PRIV Database 20250721.csv"
db_file = "priv_data.db"

# Load CSV
df = pd.read_csv(csv_file)

# Ensure column names match DB
df.columns = [col.lower().replace(" ", "_") for col in df.columns]

# Extract all unique dates in the file
csv_dates = df["date"].dropna().unique()

# Connect to DB
conn = sqlite3.connect(db_file)
cursor = conn.cursor()

# Check if any of the dates already exist
existing_dates = cursor.execute("SELECT DISTINCT date FROM financial_data").fetchall()
existing_dates = set(date[0] for date in existing_dates)

# Filter out rows with already existing dates
df = df[~df["date"].isin(existing_dates)]

if df.empty:
    print("All dates in this CSV already exist in the database. No new data inserted.")
    conn.close()
    sys.exit()

# Reorder columns to match DB
columns = [
    "date", "name", "identifier", "sedol", "weight", "coupon",
    "par_value", "market_value", "local_currency", "maturity", "asset_type"
]

# Insert remaining new rows
df[columns].to_sql("financial_data", conn, if_exists="append", index=False)
conn.close()

print(f"Inserted {len(df)} new rows into the database.")
