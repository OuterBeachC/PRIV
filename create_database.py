# create_database.py

import sqlite3

# Connect to SQLite (creates the file if it doesn't exist)
conn = sqlite3.connect("priv_data.db")
cursor = conn.cursor()

# Create table
cursor.execute("""
CREATE TABLE IF NOT EXISTS financial_data (
    date TEXT,
    name TEXT,
    identifier TEXT,
    sedol TEXT,
    weight REAL,
    coupon TEXT,
    par_value REAL,
    market_value REAL,
    local_currency TEXT,
    maturity TEXT,
    asset_breakdown TEXT
)
""")

conn.commit()
conn.close()
print("Database and table created.")