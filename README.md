# PRIV Project

Financial data tracking and analysis project for PRIV, PRSD, and HIYS funds.

## Project Structure

```
PRIV/
├── src/                    # Source code
│   ├── apps/              # Streamlit applications
│   └── scripts/           # Analysis and utility scripts
├── data/                   # Data files
│   ├── invesco_downloads/ # Downloaded Invesco data
│   ├── *.csv             # Daily fund data files (PRIV, PRSD, HIYS)
│   ├── *.xlsx            # Excel format fund data
│   └── priv_data.db      # SQLite database
├── output/                 # Generated reports and analysis
│   ├── weekly_report_*   # Weekly fund reports (CSV, HTML, MD)
│   ├── aos_*.csv         # AOS coupon analysis
│   └── debug files       # Debug outputs and screenshots
├── docs/                   # Documentation
│   ├── README_WEEKLY_REPORT.md
│   ├── SECURITY_AUDIT_FINAL.md
│   ├── IMPLEMENTATION_SUMMARY.md
│   ├── DEPENDENCY_AUDIT_REPORT.md
│   └── LICENSE
├── scripts/                # Shell scripts
│   ├── setup-venv.sh     # Virtual environment setup
│   └── security-check.sh # Security checking
└── config/                 # Configuration files
    ├── requirements*.txt  # Python dependencies
    ├── .python-version   # Python version
    └── *_last_modified.txt # File tracking

```

## Data Files

### CSV Format
- `MMDDYYYYPRIV.csv` - PRIV fund daily holdings
- `MMDDYYYYPRSD.csv` - PRSD fund daily holdings
- `MMDDYYYYHIYS.csv` - HIYS fund daily holdings
- Large database exports in `data/`

### Excel Format
- `holdings-daily-us-en-priv*.xlsx` - PRIV fund holdings
- `holdings-daily-us-en-prsd*.xlsx` - PRSD fund holdings

## Key Applications

### Streamlit Apps (src/apps/)
- `streamlit_app.py` - Main analysis dashboard
- `streamlit_app2.py` - Secondary analysis tools
- `streamlit_app2-1.py` - Additional analysis features

### Analysis Scripts (src/scripts/)
- `weekly_report.py` - Generate weekly fund reports
- `analyze_aos_coupons.py` - AOS bond coupon analysis
- `analyze_aos_coupon_payments.py` - Payment schedule analysis
- `sync_csv_to_db.py` - Sync CSV data to database
- `create_database.py` - Database initialization
- `invesco.py` - Invesco data fetching

## Setup

1. Create virtual environment:
   ```bash
   ./scripts/setup-venv.sh
   ```

2. Install dependencies:
   ```bash
   pip install -r config/requirements.txt
   ```

3. Run the main application:
   ```bash
   streamlit run src/apps/streamlit_app.py
   ```

## Output Files

Generated reports are stored in `output/`:
- Weekly reports (CSV, HTML, Markdown)
- AOS coupon analysis
- Debug files and screenshots

These files are gitignored to keep the repository clean.
