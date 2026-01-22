#!/usr/bin/env python3
"""
Master Database Update Script

This script orchestrates the complete workflow:
1. Downloads all files (SSGA and Invesco) via WebSitechecker
2. Verifies all expected files are available
3. Processes and syncs all data to the database
4. Cleans up temporary files

Usage:
    python update_database.py [--db DATABASE] [--keep-files]

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

INVESCO_TICKERS = ["HIYS", "GTO", "GTOC"]

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
        "info": "ℹ",
        "success": "✓",
        "error": "✗",
        "warning": "⚠"
    }
    symbol = symbols.get(status, "•")
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


def verify_files_exist():
    """
    Verify all expected files exist after download.

    Returns:
        tuple: (success: bool, missing_files: list)
    """
    missing = []

    # Check SSGA files
    for name, filename in SSGA_FILES.items():
        if not os.path.exists(filename):
            missing.append(f"SSGA {name}: {filename}")

    # Check Invesco files - we need at least one CSV per ticker
    invesco_csv_files = glob.glob("*.csv")

    # Since Invesco files may have variable names, we'll just check if we have
    # at least the expected number of CSV files
    # A more robust check would parse the CSV filenames
    if len(invesco_csv_files) < len(INVESCO_TICKERS):
        print_status(
            f"Expected at least {len(INVESCO_TICKERS)} Invesco CSV files, found {len(invesco_csv_files)}",
            "warning"
        )

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


def step2_verify_files():
    """
    Step 2: Verify all expected files are present.

    Returns:
        bool: True if all files present, False otherwise
    """
    print_section("STEP 2: Verifying Downloaded Files")

    success, missing = verify_files_exist()

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


def step3_process_ssga_files(db_file):
    """
    Step 3: Process all SSGA XLSX files and sync to database.

    Args:
        db_file: Path to database file

    Returns:
        bool: True if all SSGA files processed successfully
    """
    print_section("STEP 3: Processing SSGA Files")

    all_success = True

    for name, filename in SSGA_FILES.items():
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


def step4_process_invesco_files(db_file):
    """
    Step 4: Process all Invesco CSV files and sync to database.

    Args:
        db_file: Path to database file

    Returns:
        bool: True if all Invesco files processed successfully
    """
    print_section("STEP 4: Processing Invesco Files")

    # Find all CSV files (Invesco downloads)
    csv_files = glob.glob("*.csv")

    if not csv_files:
        print_status("No Invesco CSV files found to process", "warning")
        return False

    all_success = True
    processed_count = 0

    # We need to match CSV files to tickers
    # Since WebSitechecker may produce files with variable names,
    # we'll process each ticker and let it find the appropriate file

    for ticker in INVESCO_TICKERS:
        print(f"\n--- Processing {ticker} ---")

        # Find CSV file that likely corresponds to this ticker
        # This is a heuristic - files might be named like "HIYS_*.csv" or similar
        matching_files = [f for f in csv_files if ticker.lower() in f.lower()]

        if not matching_files:
            print_status(f"No CSV file found for ticker {ticker}", "warning")
            # Try to find any unprocessed CSV
            if csv_files:
                matching_files = [csv_files[0]]
                print_status(f"Attempting to process {matching_files[0]} as {ticker}", "info")

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
                    # Remove from list to avoid reprocessing
                    csv_files.remove(csv_file)

            except subprocess.TimeoutExpired:
                print_status(f"Processing {ticker} timed out", "error")
                all_success = False
            except Exception as e:
                print_status(f"Error processing {ticker}: {e}", "error")
                all_success = False

    print(f"\nProcessed {processed_count}/{len(INVESCO_TICKERS)} Invesco tickers")

    return all_success and processed_count == len(INVESCO_TICKERS)


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

    # SSGA XLSX files
    for filename in SSGA_FILES.values():
        if os.path.exists(filename):
            files_to_remove.append(filename)

    # CSV files (both Invesco originals and processed)
    csv_files = glob.glob("*.csv")
    files_to_remove.extend(csv_files)

    if not files_to_remove:
        print_status("No files to clean up", "info")
        return

    print_status(f"Removing {len(files_to_remove)} temporary file(s)", "info")

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

    args = parser.parse_args()

    start_time = datetime.now()

    print("="*80)
    print("  DATABASE UPDATE WORKFLOW")
    print(f"  Started: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
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
    if not step2_verify_files():
        print_status("File verification failed. Aborting workflow.", "error")
        sys.exit(1)

    # Step 3: Process SSGA files
    if not step3_process_ssga_files(args.database):
        print_status("SSGA processing encountered errors", "warning")
        success = False

    # Step 4: Process Invesco files
    if not step4_process_invesco_files(args.database):
        print_status("Invesco processing encountered errors", "warning")
        success = False

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
