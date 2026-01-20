# Weekly Database Report Generator

This tool generates weekly reports from the `priv_data.db` database, showing changes in holdings over the last week. The reports are designed to be easily exported and embedded into Substack articles.

## Features

- **Multiple Export Formats**: CSV, HTML, and Markdown
- **Customizable Time Periods**: Default 7 trading days, but configurable
- **Multiple Funds**: Supports PRIV, PRSD, and HIYS
- **Substack-Ready**: HTML and Markdown formats optimized for Substack publishing

## Installation

The script requires Python 3 and the following packages:

```bash
pip3 install pandas tabulate
```

## Usage

### Basic Usage

Generate a weekly report for PRIV fund (default):

```bash
python3 weekly_report.py
```

### Command-Line Options

```bash
python3 weekly_report.py [OPTIONS]

Options:
  --db PATH              Path to database file (default: priv_data.db)
  --fund {PRIV,PRSD,HIYS}  Fund to analyze (default: PRIV)
  --days N              Number of trading days to look back (default: 7)
  --format {csv,html,markdown,all}  Output format (default: all)
  --output-prefix PREFIX  Prefix for output files (default: weekly_report)
```

### Examples

**Generate report for PRIV fund (last 7 trading days):**
```bash
python3 weekly_report.py --fund PRIV
```

**Generate report for PRSD fund (last 14 trading days):**
```bash
python3 weekly_report.py --fund PRSD --days 14
```

**Generate only HTML format:**
```bash
python3 weekly_report.py --format html
```

**Generate all formats for HIYS:**
```bash
python3 weekly_report.py --fund HIYS --format all
```

## Output Files

The script generates the following files:

### CSV Files
- `weekly_report_{FUND}_new_assets_{DATE}.csv` - New assets added
- `weekly_report_{FUND}_removed_assets_{DATE}.csv` - Assets removed
- `weekly_report_{FUND}_par_changes_{DATE}.csv` - Par value changes
- `weekly_report_{FUND}_combined_{DATE}.csv` - Combined report with summary

### HTML File
- `weekly_report_{FUND}_{DATE}.html` - Styled HTML report ready for Substack

### Markdown File
- `weekly_report_{FUND}_{DATE}.md` - Markdown format for Substack

## Report Sections

### 1. New Assets
Shows assets that were added during the reporting period with:
- Date
- Name
- Last Price (calculated as market_value / par_value × 100)
- Asset Type

### 2. Removed Assets
Shows assets that were removed during the reporting period with:
- Date
- Name
- Last Price
- Asset Type

### 3. Par Value Changes
Shows assets where the par value changed with:
- Date
- Name
- Par Change (positive or negative)
- Asset Type

## Using with Substack

### Option 1: HTML Embed
1. Generate the report with HTML format
2. Open the `.html` file in your browser
3. Copy the content
4. Paste into Substack editor (it will preserve formatting)

### Option 2: Markdown
1. Generate the report with Markdown format
2. Open the `.md` file
3. Copy the content
4. Paste into Substack's markdown editor

### Option 3: CSV for Custom Formatting
1. Generate CSV files
2. Import into your favorite spreadsheet tool
3. Format as desired
4. Export as needed for Substack

## Sample Output

### Summary
```
Report Period: 2026-01-07 to 2026-01-16 (9 days)

Total Market Value: $100,341,687.79
Total Par Value: $122,038,717.28
Securities Count: 205
New Assets: 2
Removed Assets: 1
Par Value Changes: 11
```

### New Assets Example
| Date       | Name                                  | Last Price | Asset Type |
|:-----------|:--------------------------------------|:-----------|:-----------|
| 2026-01-16 | JBS NV 5.95 04/20/2035               | 105.0361   | Non-AOS    |
| 2026-01-16 | BAYER US FINANCE LLC 6.375 11/21/2030| 107.9370   | Non-AOS    |

### Par Value Changes Example
| Date       | Name                              | Par Change  | Asset Type |
|:-----------|:----------------------------------|:------------|:-----------|
| 2026-01-16 | STATE STR INSTI US GOVT CL INST  | 733,999.67  | Non-AOS    |
| 2026-01-16 | PFIZER INC 4.75 05/19/2033       | -200,000.00 | Non-AOS    |

## Automation

You can automate weekly report generation using a cron job:

```bash
# Add to crontab (crontab -e)
# Generate report every Monday at 9 AM
0 9 * * 1 cd /path/to/PRIV && python3 weekly_report.py --fund PRIV --format all
```

## Troubleshooting

**Error: "No module named 'pandas'"**
- Solution: Install dependencies with `pip3 install pandas tabulate`

**Error: "No data available"**
- Check that the database file path is correct
- Verify the fund symbol is spelled correctly (PRIV, PRSD, or HIYS)

**Error: "Insufficient data"**
- The database needs at least 2 dates of data to generate a comparison report

## Notes

- The script looks back a specified number of **trading days**, not calendar days
- "Last Price" is calculated as (market_value / par_value) × 100
- All data is sourced from the `priv_data.db` SQLite database
- The disclosure statement is automatically included in all report formats

## Disclaimer

All information displayed here is public and is not in any way to be construed as investment advice or solicitation. Data is sourced from public filings and we make no claims to veracity or accuracy of the data. It is presented for academic and research purposes only.
