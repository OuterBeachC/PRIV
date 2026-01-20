# sync_csv_to_db.py (Enhanced with XLSX conversion, auto-download, and Invesco support)
import pandas as pd
import sqlite3
import sys
import os
import argparse
from datetime import datetime
import requests
import re

# =============================================================================
# INVESCO CONFIGURATION
# =============================================================================
INVESCO_TARGET_COMPANY = "AP Grange Holdings LLC"

# =============================================================================
# SSGA DOWNLOAD FUNCTIONS
# =============================================================================

def download_latest_priv_xlsx(output_path):
    url = "https://www.ssga.com/us/en/intermediary/library-content/products/fund-data/etfs/us/holdings-daily-us-en-priv.xlsx"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        print(f"Downloading latest PRIV XLSX from {url} ...")
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            with open(output_path, "wb") as f:
                f.write(response.content)
            print(f"Downloaded to {output_path}")
            return True
        else:
            print(f"Failed to download file: {response.status_code}")
            return False
    except Exception as e:
        print(f"Error downloading file: {e}")
        return False

# =============================================================================
# INVESCO FUNCTIONS
# =============================================================================

def extract_date_from_invesco_csv(filepath: str) -> str:
    """
    Extract the date from the last line of the Invesco CSV file.
    The format is: # as of 2026-01-07
    Returns date in M/D/YYYY format.
    """
    try:
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            lines = f.readlines()
        
        # Find the line with the date (usually last non-empty line)
        for line in reversed(lines):
            line = line.strip()
            if line.startswith('# as of'):
                # Extract date: "# as of 2026-01-07"
                date_str = line.replace('# as of', '').strip()
                # Parse and reformat
                parsed_date = datetime.strptime(date_str, '%Y-%m-%d')
                # Format as M/D/YYYY (no leading zeros)
                if os.name == 'nt':
                    formatted_date = parsed_date.strftime("%#m/%#d/%Y")
                else:
                    formatted_date = parsed_date.strftime("%-m/%-d/%Y")
                print(f"Extracted date from Invesco file: {formatted_date}")
                return formatted_date
        
        print("Warning: Could not find date in Invesco file")
        return None
        
    except Exception as e:
        print(f"Error extracting date from Invesco file: {e}")
        return None


def convert_invesco_csv(input_file: str, output_file: str = None) -> str:
    """
    Extract and transform data for AP Grange Holdings LLC from Invesco CSV.
    
    Args:
        input_file: Path to the Invesco CSV file
        output_file: Path to output CSV file (optional, auto-generated if not provided)
    
    Returns:
        Path to the transformed CSV file, or None if failed.
    """
    print(f"\n--- Processing Invesco file: {input_file} ---")
    print(f"Looking for: {INVESCO_TARGET_COMPANY}")
    
    # Read the CSV file
    df = pd.read_csv(input_file, encoding='utf-8-sig')
    
    # Find the target company row
    target_row = df[df['Company'].str.lower() == INVESCO_TARGET_COMPANY.lower()]
    
    if target_row.empty:
        print(f"✗ Could not find '{INVESCO_TARGET_COMPANY}' in the file")
        return None
    
    print(f"✓ Found {INVESCO_TARGET_COMPANY}")
    
    # Extract the row data
    row = target_row.iloc[0]
    
    # Get the date from the file
    extracted_date = extract_date_from_invesco_csv(input_file)
    if not extracted_date:
        print("✗ Could not extract date from file")
        return None
    
    # Extract coupon and maturity for the transformed name
    coupon = row['Coupon/ Div yield'].replace('%', '')  # "6.50%" -> "6.50"
    maturity = row['Maturity date']  # "03/20/2045"
    
    # Transform name: "AP Grange Holdings LLC" -> "AP GRANGE HOLDINGS LLC 6.5 03/20/2045"
    # Remove trailing zero from coupon if present (6.50 -> 6.5)
    coupon_float = float(coupon)
    if coupon_float == int(coupon_float):
        coupon_display = str(int(coupon_float))
    else:
        coupon_display = str(coupon_float).rstrip('0').rstrip('.')
    
    transformed_name = f"{INVESCO_TARGET_COMPANY.upper()} {coupon_display} {maturity}"
    print(f"Transformed name: {transformed_name}")
    
    # Clean up values
    def clean_numeric(value):
        """Remove $ and , from numeric values"""
        if pd.isna(value):
            return None
        return str(value).replace('$', '').replace(',', '')
    
    def clean_percentage(value):
        """Remove % from percentage values"""
        if pd.isna(value):
            return None
        return str(value).replace('%', '')
    
    # Map to database structure (column names match expected DB columns)
    transformed_data = {
        'Date': extracted_date,
        'Name': transformed_name,
        'Identifier': row['CUSIP'],
        'SEDOL': None,
        'Weight': clean_percentage(row['% TNA']),
        'Coupon': clean_percentage(row['Coupon/ Div yield']),
        'Par Value': clean_numeric(row['Share/ Par']),
        'Market Value': clean_numeric(row['Market value']),
        'Local Currency': 'USD',
        'Maturity': maturity,
        'Asset Breakdown': row['Class of shares'],
        'Source_Identifier': 'HIYS'
    }
    
    # Create DataFrame with single row
    output_df = pd.DataFrame([transformed_data])
    
    # Generate output filename if not provided (MMDDYYYYHIYS.csv)
    if output_file is None:
        date_parts = extracted_date.split('/')
        month = date_parts[0].zfill(2)
        day = date_parts[1].zfill(2)
        year = date_parts[2]
        output_filename = f"{month}{day}{year}HIYS.csv"
        
        # Save to same directory as input file
        input_dir = os.path.dirname(input_file)
        if input_dir:
            output_file = os.path.join(input_dir, output_filename)
        else:
            output_file = output_filename
    
    output_df.to_csv(output_file, index=False)
    print(f"✓ Saved transformed data to: {output_file}")
    
    return output_file


# =============================================================================
# XLSX FUNCTIONS
# =============================================================================

def extract_value_from_b2(input_file, sheet_name=0):
    """
    Extract value from cell B2 in the XLSX file for use as filename suffix.
    
    Args:
        input_file (str): Path to input XLSX file
        sheet_name (str/int): Sheet name or index (default: 0)
    
    Returns:
        str: Cleaned value from B2 suitable for filename, or 'DATA' as fallback
    """
    try:
        print(f"Extracting value from cell B2 in: {input_file}")
        b2_df = pd.read_excel(input_file, sheet_name=sheet_name, header=None, nrows=2)
        
        # Get value from cell B2 (row 1, column 1 in 0-based indexing)
        b2_value = b2_df.iloc[1, 1]  # Row 2, Column B
        
        if pd.isna(b2_value):
            print("Warning: Cell B2 is empty, using 'DATA' as fallback")
            return "DATA"
        
        # Convert to string and clean for filename use
        b2_str = str(b2_value).strip()
        
        print(f"Raw value from B2: '{b2_value}'")
        
        # Clean the value for use in filename (remove special characters, spaces, etc.)
        # Keep only alphanumeric characters and convert to uppercase
        cleaned_value = re.sub(r'[^a-zA-Z0-9]', '', b2_str).upper()
        
        if not cleaned_value:
            print("Warning: B2 value resulted in empty string after cleaning, using 'DATA' as fallback")
            return "DATA"
        
        print(f"Cleaned B2 value for filename: '{cleaned_value}'")
        return cleaned_value
        
    except Exception as e:
        print(f"Error extracting value from B2: {str(e)}")
        print("Using 'DATA' as fallback")
        return "DATA"

def extract_date_from_b3(input_file, sheet_name=0):
    """
    Extract date value from cell B3 in the XLSX file, stripping 'As of' prefix.
    
    Args:
        input_file (str): Path to input XLSX file
        sheet_name (str/int): Sheet name or index (default: 0)
    
    Returns:
        str: Formatted date string (M/D/YYYY) or None if extraction failed
    """
    try:
        print(f"Extracting date from cell B3 in: {input_file}")
        date_df = pd.read_excel(input_file, sheet_name=sheet_name, header=None, nrows=3)
        
        # Get value from cell B3 (row 2, column 1 in 0-based indexing)
        date_value = date_df.iloc[2, 1]  # Row 3, Column B
        
        if pd.isna(date_value):
            print("Warning: Cell B3 is empty")
            return None
        
        # Convert to string and strip 'As of' prefix
        date_str = str(date_value).strip()
        
        # Remove 'As of' prefix (case insensitive)
        if date_str.lower().startswith('as of'):
            date_str = date_str[5:].strip()  # Remove 'As of' and any following spaces
        
        print(f"Raw date value from B3: '{date_value}'")
        print(f"Cleaned date string: '{date_str}'")
        
        # Try to parse the date with multiple formats
        date_formats = [
            "%d-%b-%Y",      # 28-Jul-2025
            "%d-%B-%Y",      # 28-July-2025
            "%m/%d/%Y",      # 7/28/2025
            "%m-%d-%Y",      # 7-28-2025
            "%Y-%m-%d",      # 2025-07-28
            "%d/%m/%Y",      # 28/7/2025
            "%b %d, %Y",     # Jul 28, 2025
            "%B %d, %Y",     # July 28, 2025
        ]
        
        parsed_date = None
        
        # If it's already a pandas Timestamp, use it directly
        if isinstance(date_value, pd.Timestamp):
            parsed_date = date_value
        else:
            # Try parsing with different formats
            for fmt in date_formats:
                try:
                    parsed_date = pd.to_datetime(date_str, format=fmt)
                    print(f"Successfully parsed date using format: {fmt}")
                    break
                except:
                    continue
            
            # If no format worked, try pandas' smart parsing
            if parsed_date is None:
                try:
                    parsed_date = pd.to_datetime(date_str)
                    print("Successfully parsed date using pandas auto-detection")
                except:
                    print(f"Warning: Could not parse date '{date_str}' with any known format")
                    return None
        
        # Format as M/D/YYYY (removing leading zeros)
        formatted_date = parsed_date.strftime("%-m/%-d/%Y") if os.name != 'nt' else parsed_date.strftime("%#m/%#d/%Y")
        
        print(f"Extracted date: {formatted_date}")
        return formatted_date
        
    except Exception as e:
        print(f"Error extracting date from B3: {str(e)}")
        return None

def convert_xlsx_to_csv(input_file, output_file=None, skip_rows=4, skip_footer=37, sheet_name=0):
    """
    Convert XLSX file to CSV while trimming rows from top and/or bottom.
    
    Args:
        input_file (str): Path to input XLSX file
        output_file (str): Path to output CSV file (optional)
        skip_rows (int): Number of rows to skip from the top (default: 4 for PRIV files)
        skip_footer (int): Number of rows to skip from the bottom
        sheet_name (str/int): Sheet name or index to convert (default: 0)
    
    Returns:
        str: Path to the created CSV file, or None if conversion failed
    """
    
    try:
        # Check if input file exists
        if not os.path.exists(input_file):
            print(f"Error: Input file '{input_file}' not found.")
            return None
        
        # Extract date from B3 for the date column
        extracted_date = extract_date_from_b3(input_file, sheet_name)
        
        # Extract value from B2 for filename suffix and data column
        try:
            b2_value = extract_value_from_b2(input_file, sheet_name)
        except ValueError as e:
            print(str(e))
            print("Please check that cell B2 contains a valid identifier (alphanumeric characters).")
            return None
        
        # Generate output filename if not provided
        if output_file is None:
            try:
                # Use the extracted date for filename
                if extracted_date:
                    # Convert date format from M/D/YYYY to MMDDYYYY for filename
                    date_parts = extracted_date.split("/")
                    month = date_parts[0].zfill(2)
                    day = date_parts[1].zfill(2)
                    year = date_parts[2]
                    date_str = f"{month}{day}{year}"
                else:
                    # Fallback to current date
                    print("Warning: Using current date for filename")
                    date_str = datetime.now().strftime("%m%d%Y")
                
                # Create filename with date and B2 value suffix
                input_dir = os.path.dirname(input_file)
                output_file = os.path.join(input_dir, f"{date_str}{b2_value}.csv")
                print(f"Generated CSV filename: {output_file}")
                
            except Exception as e:
                print(f"Warning: Could not generate filename, using default naming: {e}")
                base_name = os.path.splitext(input_file)[0]
                output_file = f"{base_name}.csv"
        
        # Read the XLSX file for conversion
        print(f"Reading XLSX file: {input_file} (skipping {skip_rows} rows)")
        df = pd.read_excel(input_file, sheet_name=sheet_name, skiprows=skip_rows)
        
        # Skip rows from the bottom if specified
        if skip_footer > 0:
            df = df.iloc[:-skip_footer]
        
        # Add date column with the extracted date value
        if extracted_date:
            print(f"Adding date column with value: {extracted_date}")
            # Only add date to rows that have data in other columns (not all NaN)
            mask = df.notna().any(axis=1)  # True for rows with at least one non-NaN value
            df['Date'] = None  # Initialize column
            df.loc[mask, 'Date'] = extracted_date  # Set date only for rows with data
            print(f"Added date to {mask.sum()} rows with data")
        else:
            print("ERROR: Could not extract date from B3. Cannot proceed without date.")
            print("Please check that cell B3 contains a valid date in the format 'As of DD-MMM-YYYY'")
            return None
        
        # Add B2 value column
        print(f"Adding B2 value column with value: {b2_value}")
        mask = df.notna().any(axis=1)  # True for rows with at least one non-NaN value
        df['Source_Identifier'] = None  # Initialize column
        df.loc[mask, 'Source_Identifier'] = b2_value  # Set B2 value only for rows with data
        print(f"Added source identifier to {mask.sum()} rows with data")
        
        # Convert to CSV
        print(f"Converting to CSV: {output_file}")
        df.to_csv(output_file, index=False)
        
        print(f"✅ Successfully converted '{input_file}' to '{output_file}'")
        print(f"   Rows processed: {len(df)}")
        print(f"   Columns: {len(df.columns)}")
        
        return output_file
        
    except Exception as e:
        print(f"❌ Error during conversion: {str(e)}")
        return None

def sync_csv_to_db(csv_file, db_file):
    """
    Sync CSV data to SQLite database, avoiding duplicate date/source combinations.
    
    Args:
        csv_file (str): Path to CSV file
        db_file (str): Path to SQLite database file
    """
    
    # Check if CSV file exists
    if not os.path.exists(csv_file):
        print(f"Error: CSV file '{csv_file}' not found.")
        return False
    
    # Load CSV
    print(f"Loading CSV file: {csv_file}")
    df = pd.read_csv(csv_file)
    
    # Print original column names for debugging
    print("Original column names:")
    for i, col in enumerate(df.columns):
        print(f"  [{i}]: '{col}'")
    
    # Ensure column names match DB
    original_columns = df.columns.tolist()
    df.columns = [col.lower().replace(" ", "_") for col in df.columns]
    
    # Print normalized column names for debugging
    print("Normalized column names:")
    for i, col in enumerate(df.columns):
        print(f"  [{i}]: '{col}' (was: '{original_columns[i]}')")
    
    # Check if 'date' column exists after normalization
    if 'date' not in df.columns:
        print("❌ ERROR: No 'date' column found after normalization!")
        print("Available columns:", list(df.columns))
        
        # Try to find a date-like column
        possible_date_columns = [col for col in df.columns if 'date' in col.lower() or 'time' in col.lower() or 'as_of' in col.lower()]
        if possible_date_columns:
            print(f"Possible date columns found: {possible_date_columns}")
            print("You may need to rename one of these columns to 'date' or adjust the column mapping.")
        else:
            print("No obvious date columns found. Please check your source file structure.")
        
        return False
    
    # Check if 'source_identifier' column exists after normalization
    if 'source_identifier' not in df.columns:
        print("❌ ERROR: No 'source_identifier' column found after normalization!")
        print("Available columns:", list(df.columns))
        return False
    
    # Extract all unique date/source combinations in the file
    csv_combinations = df[["date", "source_identifier"]].dropna().drop_duplicates()
    print(f"Found {len(csv_combinations)} unique date/source combinations in CSV:")
    for _, row in csv_combinations.iterrows():
        print(f"  {row['date']} - {row['source_identifier']}")
    
    # Connect to DB
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    # Check if the financial_data table exists and get existing date/source combinations
    try:
        existing_combinations = cursor.execute("SELECT DISTINCT date, source_identifier FROM financial_data").fetchall()
        existing_combinations = set((combo[0], combo[1]) for combo in existing_combinations)
        print(f"Found {len(existing_combinations)} existing date/source combinations in database")
        if existing_combinations:
            print("Existing combinations:")
            for date, source in sorted(list(existing_combinations)):
                print(f"  {date} - {source}")
    except sqlite3.OperationalError as e:
        if "no such table" in str(e):
            print("Table 'financial_data' doesn't exist yet. All data will be inserted as new.")
            existing_combinations = set()
        else:
            raise e
    
    # Filter out rows with already existing date/source combinations
    def is_new_combination(row):
        return (row['date'], row['source_identifier']) not in existing_combinations
    
    new_data_mask = df.apply(is_new_combination, axis=1)
    df_new = df[new_data_mask]
    
    if df_new.empty:
        print("All date/source combinations in this CSV already exist in the database. No new data inserted.")
        conn.close()
        return True
    
    print(f"Found {len(df_new)} rows with new date/source combinations to insert")
    
    # Expected columns for the database (updated to include source_identifier)
    expected_columns = [
        "date", "name", "identifier", "sedol", "weight", "coupon",
        "par_value", "market_value", "local_currency", "maturity", "asset_breakdown", "source_identifier"
    ]
    
    # Check which expected columns are missing
    missing_columns = [col for col in expected_columns if col not in df_new.columns]
    if missing_columns:
        print(f"WARNING: Missing expected columns: {missing_columns}")
        print("Available columns:", list(df_new.columns))
        
        # Only use columns that exist
        available_columns = [col for col in expected_columns if col in df_new.columns]
        print(f"Using available columns: {available_columns}")
    else:
        available_columns = expected_columns
    
    # Insert remaining new rows
    try:
        df_new[available_columns].to_sql("financial_data", conn, if_exists="append", index=False)
        conn.close()
        
        print(f"✅ Inserted {len(df_new)} new rows into the database.")
        return True
    except Exception as e:
        print(f"❌ Error inserting data into database: {str(e)}")
        conn.close()
        return False

def main():
    parser = argparse.ArgumentParser(description="Sync CSV/XLSX data to SQLite database")
    parser.add_argument("input_file", help="Path to input CSV or XLSX file, or 'download' to fetch latest PRIV XLSX")
    parser.add_argument("-d", "--database", default="priv_data.db", 
                       help="Path to SQLite database file (default: priv_data.db)")
    parser.add_argument("-s", "--skip-rows", type=int, default=4, 
                       help="Number of rows to skip from top (XLSX only, default: 4)")
    parser.add_argument("-f", "--skip-footer", type=int, default=37, 
                       help="Number of rows to skip from bottom (XLSX only, default: 37)")
    parser.add_argument("-w", "--sheet", default=0, 
                       help="Sheet name or index to convert (XLSX only)")
    parser.add_argument("--keep-csv", action="store_true", 
                       help="Keep converted CSV file (don't delete after processing)")
    parser.add_argument("--invesco", action="store_true",
                       help="Process as Invesco CSV file (extract AP Grange Holdings LLC)")
    args = parser.parse_args()

    # --- New: Download if requested ---
    if args.input_file.lower() == "download":
        xlsx_path = "holdings-daily-us-en-priv.xlsx"
        if not download_latest_priv_xlsx(xlsx_path):
            print("❌ Could not download latest XLSX. Exiting.")
            sys.exit(1)
        input_file = xlsx_path
    else:
        input_file = args.input_file

    db_file = args.database
    csv_file = input_file
    temp_csv_created = False

    # Check if processing Invesco file
    if args.invesco:
        print("Invesco mode enabled. Processing Invesco CSV file...")
        csv_file = convert_invesco_csv(input_file)
        if csv_file is None:
            print("❌ Failed to process Invesco file. Exiting.")
            sys.exit(1)
        temp_csv_created = True
        print()
    # Check if input file is XLSX
    elif input_file.lower().endswith(('.xlsx', '.xls')):
        print("XLSX file detected. Converting to CSV first...")
        try:
            sheet_name = int(args.sheet)
        except ValueError:
            sheet_name = args.sheet
        csv_file = convert_xlsx_to_csv(
            input_file=input_file,
            skip_rows=args.skip_rows,
            skip_footer=args.skip_footer,
            sheet_name=sheet_name
        )
        if csv_file is None:
            print("❌ Failed to convert XLSX file. Exiting.")
            sys.exit(1)
        temp_csv_created = True
        print()

    # Sync CSV to database
    success = sync_csv_to_db(csv_file, db_file)

    # Clean up temporary CSV file if it was created and not requested to keep

    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()