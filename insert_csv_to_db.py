#!/usr/bin/env python3
"""
insert_csv_to_db.py - Simple script to insert a single CSV file into the financial database

This script takes a CSV file and inserts it into the SQLite database, checking for
duplicate dates to avoid inserting the same data twice.
"""

import pandas as pd
import sqlite3
import sys
import os
import argparse

def insert_csv_to_db(csv_file, db_file, table_name="financial_data", check_duplicates=True):
    """
    Insert CSV data into SQLite database.
    
    Args:
        csv_file (str): Path to CSV file
        db_file (str): Path to SQLite database file
        table_name (str): Name of the database table (default: financial_data)
        check_duplicates (bool): Whether to check for duplicate dates (default: True)
    
    Returns:
        bool: True if successful, False otherwise
    """
    
    # Check if CSV file exists
    if not os.path.exists(csv_file):
        print(f"❌ Error: CSV file '{csv_file}' not found.")
        return False
    
    # Load CSV
    print(f"📁 Loading CSV file: {csv_file}")
    try:
        df = pd.read_csv(csv_file)
    except Exception as e:
        print(f"❌ Error reading CSV file: {str(e)}")
        return False
    
    print(f"📊 Loaded {len(df)} rows and {len(df.columns)} columns")
    
    # Print original column names for debugging
    print("\n📋 Original column names:")
    for i, col in enumerate(df.columns):
        print(f"  [{i}]: '{col}'")
    
    # Normalize column names to match database expectations
    original_columns = df.columns.tolist()
    df.columns = [col.lower().replace(" ", "_") for col in df.columns]
    
    # Print normalized column names
    print("\n🔄 Normalized column names:")
    for i, col in enumerate(df.columns):
        print(f"  [{i}]: '{col}' (was: '{original_columns[i]}')")
    
    # Connect to database
    print(f"\n🔗 Connecting to database: {db_file}")
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    # Check for duplicates if requested and date column exists
    rows_to_insert = len(df)
    if check_duplicates and 'date' in df.columns:
        try:
            # Get existing dates from database
            existing_dates = cursor.execute(f"SELECT DISTINCT date FROM {table_name}").fetchall()
            existing_dates = set(date[0] for date in existing_dates)
            print(f"📅 Found {len(existing_dates)} existing dates in database")
            
            # Get dates from CSV
            csv_dates = df["date"].dropna().unique()
            print(f"📅 Found {len(csv_dates)} unique dates in CSV")
            
            # Filter out rows with existing dates
            initial_rows = len(df)
            df = df[~df["date"].isin(existing_dates)]
            filtered_rows = len(df)
            rows_to_insert = filtered_rows
            
            if initial_rows > filtered_rows:
                print(f"⚠️  Filtered out {initial_rows - filtered_rows} rows with duplicate dates")
            
            if df.empty:
                print("ℹ️  All dates in this CSV already exist in the database. No new data to insert.")
                conn.close()
                return True
                
        except sqlite3.OperationalError as e:
            if "no such table" in str(e):
                print(f"📝 Table '{table_name}' doesn't exist yet. All data will be inserted as new.")
            else:
                print(f"❌ Database error: {str(e)}")
                conn.close()
                return False
    elif check_duplicates and 'date' not in df.columns:
        print("⚠️  Warning: No 'date' column found. Cannot check for duplicates.")
    
    # Insert data into database
    try:
        print(f"\n💾 Inserting {rows_to_insert} rows into table '{table_name}'...")
        df.to_sql(table_name, conn, if_exists="append", index=False)
        conn.commit()
        conn.close()
        
        print(f"✅ Successfully inserted {rows_to_insert} rows into the database!")
        return True
        
    except Exception as e:
        print(f"❌ Error inserting data into database: {str(e)}")
        conn.rollback()
        conn.close()
        return False

def show_table_info(db_file, table_name="financial_data"):
    """
    Show information about the database table.
    
    Args:
        db_file (str): Path to SQLite database file
        table_name (str): Name of the database table
    """
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        
        # Check if table exists
        tables = cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        table_names = [table[0] for table in tables]
        
        if table_name not in table_names:
            print(f"❌ Table '{table_name}' does not exist in database.")
            print(f"Available tables: {table_names}")
            conn.close()
            return
        
        # Get table info
        table_info = cursor.execute(f"PRAGMA table_info({table_name})").fetchall()
        row_count = cursor.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        
        print(f"\n📊 Table '{table_name}' Information:")
        print(f"   📈 Total rows: {row_count}")
        print(f"   📋 Columns ({len(table_info)}):")
        
        for col in table_info:
            col_id, name, data_type, not_null, default_val, primary_key = col
            nullable = "NOT NULL" if not_null else "NULL"
            pk = " (PRIMARY KEY)" if primary_key else ""
            print(f"      [{col_id}] {name} ({data_type}) {nullable}{pk}")
        
        # Show date range if date column exists
        date_columns = [col[1] for col in table_info if 'date' in col[1].lower()]
        if date_columns:
            date_col = date_columns[0]
            date_range = cursor.execute(f"SELECT MIN({date_col}), MAX({date_col}) FROM {table_name}").fetchone()
            if date_range[0] and date_range[1]:
                print(f"   📅 Date range: {date_range[0]} to {date_range[1]}")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error getting table info: {str(e)}")

def main():
    parser = argparse.ArgumentParser(
        description="Insert a CSV file into the financial database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python insert_csv_to_db.py data.csv
  python insert_csv_to_db.py data.csv -d my_database.db
  python insert_csv_to_db.py data.csv -t holdings_data --no-duplicate-check
  python insert_csv_to_db.py --info -d priv_data.db
        """
    )
    
    parser.add_argument("csv_file", nargs='?', help="Path to CSV file to insert")
    parser.add_argument("-d", "--database", default="priv_data.db", 
                       help="Path to SQLite database file (default: priv_data.db)")
    parser.add_argument("-t", "--table", default="financial_data", 
                       help="Database table name (default: financial_data)")
    parser.add_argument("--no-duplicate-check", action="store_true", 
                       help="Skip checking for duplicate dates (faster but may create duplicates)")
    parser.add_argument("--info", action="store_true", 
                       help="Show database table information and exit")
    
    args = parser.parse_args()
    
    # Show table info if requested
    if args.info:
        show_table_info(args.database, args.table)
        return
    
    # Validate arguments
    if not args.csv_file:
        parser.error("CSV file path is required (unless using --info)")
    
    # Insert CSV data
    check_duplicates = not args.no_duplicate_check
    success = insert_csv_to_db(
        csv_file=args.csv_file,
        db_file=args.database,
        table_name=args.table,
        check_duplicates=check_duplicates
    )
    
    if not success:
        sys.exit(1)
    
    # Show updated table info
    print("\n" + "="*50)
    show_table_info(args.database, args.table)

if __name__ == "__main__":
    main()