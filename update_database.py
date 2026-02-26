#!/usr/bin/env python3
"""
Master Database Update Script

This script orchestrates the complete workflow:
1. Downloads all files (SSGA and Invesco) via WebSitechecker
2. Verifies all expected files are available
3. Processes and syncs all data to the database
4. Cleans up temporary files

Usage:
    python update_database.py [--database DATABASE] [--keep-files] [--skip-download] [--only SOURCE ...]

Exit codes:
    0: Success - all files downloaded and processed
    1: Failure - missing files or processing errors
"""

import subprocess
import sys
import os
import glob
import argparse
from datetime import datetime


# =============================================================================
# CONFIGURATION
# =============================================================================

# Expected files from WebSitechecker
SSGA_FILES = {
    "PRIV": "holdings-daily-us-en-priv.xlsx",
    "PRSD": "holdings-daily-us-en-prsd.xlsx"
}

INVESCO_TICKERS = ["GTOH", "GTO", "GTOC"]

# Invesco expected filenames (downloaded by WebSitechecker)
INVESCO_FILES = {
    "GTOH": "invesco_short_duration_high_yield_etf-monthly_holdings.csv",
    "GTO": "invesco_total_return_bond_etf-monthly_holdings.csv",
    "GTOC": "invesco_core_fixed_income_etf-monthly_holdings.csv"
}

# All valid source names (for --only flag)
ALL_SOURCES = list(SSGA_FILES.keys()) + INVESCO_TICKERS  # ["PRIV", "PRSD", "GTOH", "GTO", "GTOC"]

# Database configuration
DEFAULT_DB = "priv_data.db"


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def print_section(title):
    """Print a formatted section header."""
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}\n")


def print_status(message, status="info"):
    """Print a status message with formatting."""
    symbols = {
        "info": "[INFO]",
        "success": "[OK]",
        "error": "[ERROR]",
        "warning": "[WARNING]"
    }
    symbol = symbols.get(status, "[*]")
    print(f"{symbol} {message}")


def find_invesco_csv_files():
    """Find all downloaded Invesco CSV files in the current directory."""
    csv_files = glob.glob("*.csv")
    # Filter out processed files (MMDDYYYYTICKER.csv format)
    invesco_files = []
    for f in csv_files:
        # Look for files that don't match the processed format
        # Invesco raw files typically have format like "HIYS_holdings_YYYY-MM-DD.csv"
        # or just ticker-related names
        basename = os.path.basename(f)
        # Skip if it matches our processed format (MMDDYYYYTICKER.csv)
        if not (len(basename) >= 12 and basename[:8].isdigit() and
                basename[8:12].replace('.csv', '').isupper()):
            invesco_files.append(f)
    return invesco_files


def verify_files_exist(selected_sources=None):
    """
    Verify all expected files exist after download.

    Args:
        selected_sources: Set of source names to check, or None for all.

    Returns:
        tuple: (success: bool, missing_files: list)
    """
    missing = []

    # Check SSGA files
    for name, filename in SSGA_FILES.items():
        if selected_sources and name not in selected_sources:
            continue
        if not os.path.exists(filename):
            missing.append(f"SSGA {name}: {filename}")

    # Check Invesco files - check for exact filenames
    for ticker, filename in INVESCO_FILES.items():
        if selected_sources and ticker not in selected_sources:
            continue
        if not os.path.exists(filename):
            missing.append(f"Invesco {ticker}: {filename}")

    return (len(missing) == 0, missing)


# =============================================================================
# MAIN WORKFLOW STEPS
# =============================================================================

def step1_download_files():
    """
    Step 1: Run WebSitechecker to download all files.

    Returns:
        bool: True if download succeeded, False otherwise
    """
    print_section("STEP 1: Downloading Files")

    try:
        result = subprocess.run(
            ["python", "WebSitechecker.py"],
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )

        # Print the output from WebSitechecker
        print(result.stdout)

        if result.stderr:
            print("Errors/Warnings:")
            print(result.stderr)

        if result.returncode != 0:
            print_status("WebSitechecker failed with non-zero exit code", "error")
            return False

        print_status("Download step completed", "success")
        return True

    except subprocess.TimeoutExpired:
        print_status("WebSitechecker timed out after 5 minutes", "error")
        return False
    except Exception as e:
        print_status(f"Error running WebSitechecker: {e}", "error")
        return False


def step2_verify_files(selected_sources=None):
    """
    Step 2: Verify all expected files are present.

    Args:
        selected_sources: Set of source names to verify, or None for all.

    Returns:
        bool: True if all files present, False otherwise
    """
    print_section("STEP 2: Verifying Downloaded Files")

    success, missing = verify_files_exist(selected_sources)

    if success:
        print_status("All expected SSGA files found", "success")

        # List found CSV files
        csv_files = glob.glob("*.csv")
        if csv_files:
            print_status(f"Found {len(csv_files)} CSV file(s) (Invesco)", "success")
            for f in csv_files[:5]:  # Show first 5
                print(f"    - {f}")
            if len(csv_files) > 5:
                print(f"    ... and {len(csv_files) - 5} more")
        return True
    else:
        print_status("Missing required files:", "error")
        for f in missing:
            print(f"    - {f}")
        return False


def step3_process_ssga_files(db_file, selected_sources=None):
    """
    Step 3: Process SSGA XLSX files and sync to database.

    Args:
        db_file: Path to database file
        selected_sources: Set of source names to process, or None for all.

    Returns:
        bool: True if all selected SSGA files processed successfully
    """
    print_section("STEP 3: Processing SSGA Files")

    all_success = True

    for name, filename in SSGA_FILES.items():
        if selected_sources and name not in selected_sources:
            continue
        print(f"\n--- Processing {name} ---")

        try:
            result = subprocess.run(
                ["python", "sync_csv_to_db.py", filename, "-d", db_file],
                capture_output=True,
                text=True,
                timeout=120
            )

            print(result.stdout)

            if result.stderr:
                print("Warnings/Errors:")
                print(result.stderr)

            if result.returncode != 0:
                print_status(f"Failed to process {name}", "error")
                all_success = False
            else:
                print_status(f"Successfully processed {name}", "success")

        except subprocess.TimeoutExpired:
            print_status(f"Processing {name} timed out", "error")
            all_success = False
        except Exception as e:
            print_status(f"Error processing {name}: {e}", "error")
            all_success = False

    return all_success


def is_invesco_download(filename):
    """
    Check if a CSV file is a raw Invesco download from WebSitechecker.

    Args:
        filename: The CSV filename to check

    Returns:
        bool: True if the file appears to be a raw Invesco download
    """
    basename = os.path.basename(filename).lower()

    # Invesco files typically contain "invesco" in the name
    # Examples: invesco_high_yield_select_etf-monthly_holdings.csv
    if "invesco" in basename and basename.endswith(".csv"):
        return True

    return False


def is_processed_csv(filename):
    """
    Check if a CSV file is already processed (MMDDYYYYTICKER.csv format).

    Args:
        filename: The CSV filename to check

    Returns:
        bool: True if the file matches the processed format
    """
    import re
    basename = os.path.basename(filename)
    # Match pattern: 8 digits followed by uppercase letters, then .csv
    # Example: 01072026GTOH.csv
    pattern = r'^\d{8}[A-Z]+\.csv$'
    return bool(re.match(pattern, basename))


def step4_process_invesco_files(db_file, selected_sources=None):
    """
    Step 4: Process Invesco CSV files and sync to database.

    Args:
        db_file: Path to database file
        selected_sources: Set of source names to process, or None for all.

    Returns:
        bool: True if all selected Invesco files processed successfully
    """
    print_section("STEP 4: Processing Invesco Files")

    # Find all CSV files (Invesco downloads)
    all_csv_files = glob.glob("*.csv")

    # Filter to only Invesco download files
    csv_files = [f for f in all_csv_files if is_invesco_download(f)]

    if not csv_files:
        print_status("No Invesco CSV files found to process", "warning")
        print_status(f"Found {len(all_csv_files)} total CSV files, but none appear to be Invesco downloads", "info")
        print_status("Invesco files should contain 'invesco' in the filename", "info")
        return False

    print_status(f"Found {len(csv_files)} Invesco CSV file(s) to process", "info")
    for f in csv_files:
        print(f"    - {f}")

    all_success = True
    processed_count = 0

    # Track which raw files we've used
    raw_files_by_ticker = {}

    # We need to match CSV files to tickers
    # Since WebSitechecker may produce files with variable names,
    # we'll process each ticker and let it find the appropriate file

    tickers_to_process = [t for t in INVESCO_TICKERS if not selected_sources or t in selected_sources]

    if not tickers_to_process:
        print_status("No Invesco tickers selected for processing", "info")
        return True

    for ticker in tickers_to_process:
        print(f"\n--- Processing {ticker} ---")

        # Find CSV file that corresponds to this ticker
        # First, try to find the exact expected filename
        expected_filename = INVESCO_FILES.get(ticker)
        matching_files = []

        if expected_filename and expected_filename in csv_files:
            matching_files.append(expected_filename)
        else:
            # Fallback: search by patterns in filename
            ticker_patterns = {
                "GTOH": ["short_duration_high_yield", "gtoh", "hiys"],
                "GTO": ["total_return_bond", "gto"],
                "GTOC": ["core_fixed_income", "gtoc"]
            }
            patterns = ticker_patterns.get(ticker, [ticker.lower()])

            for csv_file in csv_files:
                csv_lower = csv_file.lower()
                if any(pattern in csv_lower for pattern in patterns):
                    matching_files.append(csv_file)

        if not matching_files:
            print_status(f"No CSV file found for ticker {ticker}", "warning")
            # Try to find any unprocessed CSV that hasn't been used yet
            unused_files = [f for f in csv_files if f not in raw_files_by_ticker.values()]
            if unused_files:
                matching_files = [unused_files[0]]
                print_status(f"Attempting to process {matching_files[0]} as {ticker}", "info")
            else:
                print_status(f"No unused Invesco files available for {ticker}", "error")
                all_success = False
                continue

        for csv_file in matching_files[:1]:  # Process only the first match
            try:
                result = subprocess.run(
                    ["python", "sync_csv_to_db.py", csv_file,
                     "-d", db_file, "--invesco", "--ticker", ticker],
                    capture_output=True,
                    text=True,
                    timeout=120
                )

                print(result.stdout)

                if result.stderr:
                    print("Warnings/Errors:")
                    print(result.stderr)

                if result.returncode != 0:
                    print_status(f"Failed to process {ticker}", "error")
                    all_success = False
                else:
                    print_status(f"Successfully processed {ticker}", "success")
                    processed_count += 1
                    # Track which raw file was used for this ticker
                    raw_files_by_ticker[ticker] = csv_file
                    # Remove from list to avoid reprocessing
                    csv_files.remove(csv_file)

            except subprocess.TimeoutExpired:
                print_status(f"Processing {ticker} timed out", "error")
                all_success = False
            except Exception as e:
                print_status(f"Error processing {ticker}: {e}", "error")
                all_success = False

    print(f"\nProcessed {processed_count}/{len(tickers_to_process)} Invesco tickers")

    return all_success and processed_count == len(tickers_to_process)


def step5_cleanup(keep_files):
    """
    Step 5: Clean up downloaded files.

    Args:
        keep_files: If True, skip cleanup
    """
    print_section("STEP 5: Cleanup")

    if keep_files:
        print_status("Skipping cleanup (--keep-files specified)", "info")
        return

    files_to_remove = []

    # SSGA XLSX files (original downloads)
    for filename in SSGA_FILES.values():
        if os.path.exists(filename):
            files_to_remove.append(filename)

    # SSGA CSV files (converted from XLSX, these have MMDDYYYYSOURCE.csv format)
    # We keep these as they're the processed output
    # Only remove raw Invesco CSV downloads (not the processed MMDDYYYYTICKER.csv files)
    all_csv_files = glob.glob("*.csv")
    for csv_file in all_csv_files:
        # Only remove raw Invesco downloads (files that are NOT in processed format)
        if not is_processed_csv(csv_file):
            files_to_remove.append(csv_file)

    if not files_to_remove:
        print_status("No files to clean up", "info")
        return

    print_status(f"Removing {len(files_to_remove)} temporary file(s)", "info")
    print_status("Keeping processed CSV files for database sync", "info")

    for filepath in files_to_remove:
        try:
            os.remove(filepath)
            print(f"    Removed: {filepath}")
        except Exception as e:
            print_status(f"Could not remove {filepath}: {e}", "warning")


# =============================================================================
# MAIN FUNCTION
# =============================================================================

def main():
    """Main orchestration function."""
    parser = argparse.ArgumentParser(
        description="Update database with latest SSGA and Invesco data"
    )
    parser.add_argument(
        "-d", "--database",
        default=DEFAULT_DB,
        help=f"Path to SQLite database file (default: {DEFAULT_DB})"
    )
    parser.add_argument(
        "--keep-files",
        action="store_true",
        help="Keep downloaded files after processing (don't clean up)"
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Skip download step (use existing files)"
    )
    parser.add_argument(
        "--only",
        nargs="+",
        choices=ALL_SOURCES,
        metavar="SOURCE",
        help="Only process these sources (choices: %(choices)s). Omit to process all."
    )

    args = parser.parse_args()

    # Determine which sources to process
    selected_sources = set(args.only) if args.only else set(ALL_SOURCES)

    start_time = datetime.now()

    print("="*80)
    print("  DATABASE UPDATE WORKFLOW")
    print(f"  Started: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    if args.only:
        print(f"  Sources: {', '.join(sorted(selected_sources))}")
    print("="*80)

    # Track overall success
    success = True

    # Step 1: Download files
    if not args.skip_download:
        if not step1_download_files():
            print_status("Download failed. Aborting workflow.", "error")
            sys.exit(1)
    else:
        print_section("STEP 1: Downloading Files (SKIPPED)")
        print_status("Using existing files", "info")

    # Step 2: Verify files
    if not step2_verify_files(selected_sources):
        print_status("File verification failed. Aborting workflow.", "error")
        sys.exit(1)

    # Step 3: Process SSGA files (skip if no SSGA sources selected)
    ssga_selected = selected_sources & set(SSGA_FILES.keys())
    if ssga_selected:
        if not step3_process_ssga_files(args.database, selected_sources):
            print_status("SSGA processing encountered errors", "warning")
            success = False
    else:
        print_section("STEP 3: Processing SSGA Files (SKIPPED)")
        print_status("No SSGA sources selected", "info")

    # Step 4: Process Invesco files (skip if no Invesco sources selected)
    invesco_selected = selected_sources & set(INVESCO_TICKERS)
    if invesco_selected:
        if not step4_process_invesco_files(args.database, selected_sources):
            print_status("Invesco processing encountered errors", "warning")
            success = False
    else:
        print_section("STEP 4: Processing Invesco Files (SKIPPED)")
        print_status("No Invesco sources selected", "info")

    # Step 5: Cleanup
    step5_cleanup(args.keep_files)

    # Final summary
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    print_section("SUMMARY")
    print(f"Started:  {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Finished: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Duration: {duration:.1f} seconds")
    print(f"Database: {args.database}")

    if success:
        print_status("All operations completed successfully!", "success")
        sys.exit(0)
    else:
        print_status("Workflow completed with errors. Check logs above.", "error")
        sys.exit(1)


if __name__ == "__main__":
    main()
