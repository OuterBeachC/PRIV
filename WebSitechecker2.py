import requests
import os
import time
import glob
import re
import io
from datetime import datetime, timedelta

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager

import pandas as pd

# =============================================================================
# CONFIGURATION
# =============================================================================

# SSGA URLs (direct download)
URLS = {
    "priv": {
        "url": "https://www.ssga.com/us/en/intermediary/library-content/products/fund-data/etfs/us/holdings-daily-us-en-priv.xlsx",
        "meta_file": "priv_last_modified.txt",
        "local_file": "holdings-daily-us-en-priv.xlsx"
    },
    "prsd": {
        "url": "https://www.ssga.com/us/en/intermediary/library-content/products/fund-data/etfs/us/holdings-daily-us-en-prsd.xlsx",
        "meta_file": "prsd_last_modified.txt",
        "local_file": "holdings-daily-us-en-prsd.xlsx"
    }
}

# Invesco ETFs (Selenium download)
INVESCO_TICKERS = ["GTO", "GTOC"]
INVESCO_DOWNLOAD_DIR = os.path.join(os.getcwd())
INVESCO_HEADLESS = True  # Set to False to see browser window

# New tickers — shared settings
DOWNLOAD_DIR = os.getcwd()
HEADLESS = True  # Set to False to see browser window for new tickers
DATE_URL_LOOKBACK = 5  # Business days to look back for date-based URLs

# WisdomTree uses Cloudflare; headless Chrome is reliably blocked.
# Set to False to run the browser visibly (recommended for HYIN).
HYIN_HEADLESS = False

# New ticker URLs
VANECK_BIZD_URL = "https://www.vaneck.com/us/en/investments/bdc-income-etf-bizd/holdings/"
WISDOMTREE_HYIN_URL = "https://www.wisdomtree.com/investments/etfs/alternative/hyin#"
FRANKLINTEMPLETON_PBDC_URL = (
    "https://www.franklintempleton.com/investments/options/exchange-traded-funds"
    "/products/39500/SINGLCLASS/putnam-bdc-income-etf/PBDC#portfolio"
)
BONDBLOXX_PCMM_URL = "https://bondbloxxetf.com/bondbloxx-private-credit-clo-etf/#portfolio"
HILTON_HBDC_URL = "https://www.hiltonetfs.com/hbdc-all-holdings"
ENTREPRENEURSHARES_XOVR_URL = "https://entrepreneurshares.com/xovr-etf/#fund-top-10-holdings"

# Baron Capital UUID (hardcoded from known URL; update if Baron changes it)
BARON_RONB_UUID = "a02798d8-cb16-49e0-bbdc-eb1315aa4cbf"

# =============================================================================
# SSGA FUNCTIONS
# =============================================================================

def get_last_modified(meta_file):
    """Read the last modified timestamp from local file."""
    if os.path.exists(meta_file):
        with open(meta_file, "r") as f:
            return f.read().strip()
    return None

def save_last_modified(meta_file, last_modified):
    """Save the last modified timestamp to local file."""
    with open(meta_file, "w") as f:
        f.write(last_modified)

def check_and_download_single(name, config):
    """Check and download a single file based on its configuration."""
    print(f"\n--- Checking {name.upper()} ---")

    # First, check if local file exists
    if not os.path.exists(config["local_file"]):
        print(f"Local file not found. Downloading...")
        if download_file(config["url"], config["local_file"], name):
            # Save the Last-Modified header for future checks
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.head(config["url"], headers=headers, allow_redirects=True)
            if response.status_code == 200:
                last_modified = response.headers.get("Last-Modified")
                if last_modified:
                    save_last_modified(config["meta_file"], last_modified)
            return True
        return False

    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.head(config["url"], headers=headers, allow_redirects=True)

    if response.status_code != 200:
        print(f"Failed to fetch headers for {name}: {response.status_code}")
        return False

    last_modified = response.headers.get("Last-Modified")
    if not last_modified:
        print(f"No Last-Modified header found for {name}. Downloading file anyway.")
        return download_file(config["url"], config["local_file"], name)

    print(f"Remote Last-Modified: {last_modified}")
    local_last_modified = get_last_modified(config["meta_file"])
    print(f"Local Last-Modified: {local_last_modified}")

    if local_last_modified != last_modified:
        print(f"File {name} has been updated. Downloading new version...")
        if download_file(config["url"], config["local_file"], name):
            save_last_modified(config["meta_file"], last_modified)
            return True
    else:
        print(f"File {name} has not been updated. No download needed.")
        return False

def download_file(url, local_file, name):
    """Download a file from the given URL."""
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        with open(local_file, "wb") as f:
            f.write(response.content)
        print(f"Downloaded latest {name} file to {local_file}")
        return True
    else:
        print(f"Failed to download {name} file: {response.status_code}")
        return False

# =============================================================================
# INVESCO FUNCTIONS (Selenium)
# =============================================================================

def download_invesco_holdings(ticker: str, download_dir: str, headless: bool = True) -> str:
    """
    Download Invesco ETF holdings using Selenium.
    """
    ticker = ticker.upper()

    # Create download directory if it doesn't exist
    os.makedirs(download_dir, exist_ok=True)
    download_dir = os.path.abspath(download_dir)

    # Delete old Invesco files for this ticker to avoid " (1)" filename issues
    ticker_patterns = {
        "GTO": "invesco_total_return_bond_etf-monthly_holdings*.csv",
        "GTOC": "invesco_core_fixed_income_etf-monthly_holdings*.csv"
    }

    pattern = ticker_patterns.get(ticker)
    if pattern:
        old_files = glob.glob(os.path.join(download_dir, pattern))
        for old_file in old_files:
            try:
                os.remove(old_file)
                print(f"Deleted old file: {os.path.basename(old_file)}")
            except Exception as e:
                print(f"Warning: Could not delete {old_file}: {e}")

    # Get existing CSV files BEFORE download
    existing_files = set(glob.glob(os.path.join(download_dir, "*.csv")))

    # Configure Chrome options
    chrome_options = Options()
    if headless:
        chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")

    # Set download directory
    prefs = {
        "download.default_directory": download_dir,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True
    }
    chrome_options.add_experimental_option("prefs", prefs)

    print(f"Starting browser...")

    # Initialize Chrome driver
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        # Navigate to the holdings page
        url = f"https://www.invesco.com/us/financial-products/etfs/holdings?audienceType=Investor&ticker={ticker}"
        print(f"Opening: {url}")
        driver.get(url)
        time.sleep(4)

        # Handle "Select your role" popup - find button 94 (Individual Investor)
        role_clicked = False

        # Method 1: Find all buttons and click the one containing "Individual Investor"
        buttons = driver.find_elements(By.TAG_NAME, "button")
        for btn in buttons:
            try:
                text = btn.text
                if "Individual Investor" in text:
                    # Use JavaScript click to bypass any overlay issues
                    driver.execute_script("arguments[0].click();", btn)
                    print(f"Clicked (JS): Individual Investor button")
                    role_clicked = True
                    time.sleep(2)
                    break
            except:
                continue

        # Method 2: Try CSS selector if Method 1 failed
        if not role_clicked:
            try:
                # Look for button in modal/dialog
                btn = driver.find_element(By.CSS_SELECTOR, "[data-audiencetype='Investor']")
                driver.execute_script("arguments[0].click();", btn)
                print("Clicked via data-audiencetype selector")
                role_clicked = True
                time.sleep(2)
            except:
                pass

        # Method 3: Try clicking by index (button 94 from your debug output)
        if not role_clicked:
            try:
                buttons = driver.find_elements(By.TAG_NAME, "button")
                if len(buttons) > 94:
                    driver.execute_script("arguments[0].click();", buttons[94])
                    print("Clicked button by index (94)")
                    role_clicked = True
                    time.sleep(2)
            except:
                pass

        if not role_clicked:
            print("Warning: Could not click role selector, attempting to continue anyway...")

        # Wait for page to load after role selection
        time.sleep(4)

        # Handle cookie consent if it appears
        try:
            cookies_buttons = driver.find_elements(By.TAG_NAME, "button")
            for btn in cookies_buttons:
                if "Accept" in btn.text:
                    driver.execute_script("arguments[0].click();", btn)
                    print("Clicked: Accept cookies")
                    time.sleep(1)
                    break
        except:
            pass

        # Wait for holdings page to fully load
        time.sleep(3)

        # Scroll down to make sure Export button is visible
        driver.execute_script("window.scrollTo(0, 500);")
        time.sleep(1)

        # Find and click the Export Data button
        clicked = False

        # Try buttons first
        buttons = driver.find_elements(By.TAG_NAME, "button")
        for btn in buttons:
            try:
                text = btn.text.lower()
                if "export" in text or "download" in text:
                    driver.execute_script("arguments[0].click();", btn)
                    print(f"Clicked export button: '{btn.text.strip()}'")
                    clicked = True
                    break
            except:
                continue

        # Try links if buttons didn't work
        if not clicked:
            links = driver.find_elements(By.TAG_NAME, "a")
            for link in links:
                try:
                    text = link.text.lower()
                    href = (link.get_attribute("href") or "").lower()
                    if "export" in text or "download" in text or "export" in href or "download" in href:
                        driver.execute_script("arguments[0].click();", link)
                        print(f"Clicked export link: '{link.text.strip()}'")
                        clicked = True
                        break
                except:
                    continue

        if not clicked:
            print("\n[ERROR] Could not find Export button")

            # Save screenshot for debugging
            screenshot_path = os.path.join(download_dir, "debug_screenshot.png")
            driver.save_screenshot(screenshot_path)
            print(f"Screenshot saved to: {screenshot_path}")

            # Also save page source for debugging
            html_path = os.path.join(download_dir, "debug_page.html")
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            print(f"Page HTML saved to: {html_path}")

            return None

        # Wait for download to complete (with polling)
        print("Waiting for download...")
        max_wait = 15
        for i in range(max_wait):
            time.sleep(1)
            current_files = set(glob.glob(os.path.join(download_dir, "*.csv")))
            new_files = current_files - existing_files

            # Check for incomplete Chrome downloads
            downloading = glob.glob(os.path.join(download_dir, "*.crdownload"))

            if new_files and not downloading:
                latest_file = list(new_files)[0]
                print(f"[SUCCESS] Downloaded: {latest_file}")
                return latest_file

            print(f"  Waiting... ({i+1}/{max_wait}s)")

        print(f"[ERROR] No new CSV file downloaded after {max_wait} seconds")
        return None

    except Exception as e:
        print(f"[ERROR] Error: {e}")
        import traceback
        traceback.print_exc()
        return None

    finally:
        driver.quit()

def check_and_download_invesco():
    """Download all configured Invesco ETFs."""
    downloads_performed = 0

    for ticker in INVESCO_TICKERS:
        print(f"\n--- Checking {ticker} (Invesco) ---")
        filepath = download_invesco_holdings(ticker, INVESCO_DOWNLOAD_DIR, INVESCO_HEADLESS)
        if filepath:
            downloads_performed += 1

    return downloads_performed

# =============================================================================
# SHARED SELENIUM HELPERS (used by new ticker functions)
# =============================================================================

def _build_chrome_driver(download_dir: str, headless: bool = True) -> webdriver.Chrome:
    """Build and return a configured headless Chrome WebDriver."""
    os.makedirs(download_dir, exist_ok=True)
    download_dir = os.path.abspath(download_dir)

    chrome_options = Options()
    if headless:
        chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")

    prefs = {
        "download.default_directory": download_dir,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True
    }
    chrome_options.add_experimental_option("prefs", prefs)

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.set_page_load_timeout(90)
    return driver


def _save_debug_artifacts(driver, download_dir: str, ticker: str):
    """Save screenshot and page HTML on Selenium failure."""
    try:
        path = os.path.join(download_dir, f"debug_{ticker.lower()}_screenshot.png")
        driver.save_screenshot(path)
        print(f"Screenshot saved to: {path}")
    except Exception:
        pass
    try:
        path = os.path.join(download_dir, f"debug_{ticker.lower()}_page.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        print(f"Page HTML saved to: {path}")
    except Exception:
        pass


def _get_recent_business_dates(max_days_back: int = 5):
    """Yield recent business dates (Mon–Fri) from today backwards."""
    current = datetime.today()
    days_yielded = 0
    while days_yielded < max_days_back:
        if current.weekday() < 5:  # 0=Mon … 4=Fri
            yield current
            days_yielded += 1
        current -= timedelta(days=1)


def _accept_cookies_and_consent(driver):
    """Try to dismiss common cookie/consent popups."""
    try:
        for btn in driver.find_elements(By.TAG_NAME, "button"):
            try:
                text = btn.text.lower()
                if any(kw in text for kw in ["accept", "agree", "consent", "got it", "ok"]):
                    driver.execute_script("arguments[0].click();", btn)
                    print(f"  Dismissed popup: '{btn.text.strip()}'")
                    time.sleep(1)
                    return
            except Exception:
                continue
    except Exception:
        pass


def _poll_for_new_file(
    download_dir: str,
    existing_files: set,
    extensions: tuple = ("*.csv", "*.xls", "*.xlsx"),
    timeout: int = 20,
) -> str | None:
    """Poll download_dir for a newly appeared file. Returns path or None."""
    patterns = [os.path.join(download_dir, ext) for ext in extensions]
    print("Waiting for download...")
    for i in range(timeout):
        time.sleep(1)
        current_files = set()
        for pat in patterns:
            current_files.update(glob.glob(pat))
        new_files = current_files - existing_files
        downloading = glob.glob(os.path.join(download_dir, "*.crdownload"))
        if new_files and not downloading:
            latest = list(new_files)[0]
            print(f"[SUCCESS] Downloaded: {latest}")
            return latest
        print(f"  Waiting... ({i+1}/{timeout}s)")
    print(f"[ERROR] No new file appeared after {timeout} seconds")
    return None


def _extract_table_via_selenium(driver) -> pd.DataFrame | None:
    """
    Extract the first non-empty HTML table from the current Selenium page
    using DOM traversal (no external HTML parser required).
    Returns a DataFrame or None.
    """
    try:
        tables = driver.find_elements(By.TAG_NAME, "table")
        for table in tables:
            rows = table.find_elements(By.TAG_NAME, "tr")
            if not rows:
                continue

            # Headers: prefer <th>, fall back to first <td> row
            header_cells = rows[0].find_elements(By.TAG_NAME, "th")
            if not header_cells:
                header_cells = rows[0].find_elements(By.TAG_NAME, "td")
            headers = [c.text.strip() for c in header_cells]

            data = []
            for row in rows[1:]:
                cells = row.find_elements(By.TAG_NAME, "td")
                if not cells:
                    continue
                row_data = [c.text.strip() for c in cells]
                if any(row_data):
                    data.append(row_data)

            if not data:
                continue

            # Normalise column count
            max_cols = max(len(headers), max(len(r) for r in data))
            if len(headers) < max_cols:
                headers += [f"Column{i}" for i in range(len(headers), max_cols)]
            aligned = [r + [""] * (max_cols - len(r)) for r in data]
            return pd.DataFrame(aligned, columns=headers[:max_cols])

        return None
    except Exception as e:
        print(f"  [ERROR] Table extraction: {e}")
        return None


def _delete_old_files(download_dir: str, *patterns: str):
    """Delete existing files matching any of the given glob patterns."""
    for pattern in patterns:
        for path in glob.glob(os.path.join(download_dir, pattern)):
            try:
                os.remove(path)
                print(f"  Deleted old file: {os.path.basename(path)}")
            except Exception as e:
                print(f"  Warning: could not delete {path}: {e}")


def _snapshot_existing(download_dir: str, extensions: tuple = ("*.csv", "*.xls", "*.xlsx")) -> set:
    """Return a set of all currently present downloadable files."""
    files = set()
    for ext in extensions:
        files.update(glob.glob(os.path.join(download_dir, ext)))
    return files


# =============================================================================
# VANECK (BIZD) — Selenium XLS download (similar to Invesco / GTO / GTOC)
# =============================================================================

def download_vaneck_holdings(ticker: str, download_dir: str, headless: bool = True) -> str | None:
    """
    Download VanEck ETF holdings (e.g. BIZD) via Selenium.
    Mimics the Invesco pattern: click Download/XLS/Export, poll for new file.
    """
    ticker = ticker.upper()
    os.makedirs(download_dir, exist_ok=True)
    download_dir = os.path.abspath(download_dir)

    _delete_old_files(download_dir, f"vaneck*{ticker.lower()}*.xls*", f"vaneck*{ticker.lower()}*.csv")
    existing_files = _snapshot_existing(download_dir)

    print("Starting browser...")
    driver = _build_chrome_driver(download_dir, headless)
    try:
        print(f"Opening: {VANECK_BIZD_URL}")
        driver.get(VANECK_BIZD_URL)
        time.sleep(5)

        _accept_cookies_and_consent(driver)
        time.sleep(2)

        driver.execute_script("window.scrollTo(0, 500);")
        time.sleep(1)

        clicked = False
        # Try buttons
        for btn in driver.find_elements(By.TAG_NAME, "button"):
            try:
                text = btn.text.lower()
                if any(kw in text for kw in ["download", "xls", "export", "excel"]):
                    driver.execute_script("arguments[0].click();", btn)
                    print(f"  Clicked button: '{btn.text.strip()}'")
                    clicked = True
                    break
            except Exception:
                continue

        # Try links / anchors
        if not clicked:
            for link in driver.find_elements(By.TAG_NAME, "a"):
                try:
                    text = link.text.lower()
                    href = (link.get_attribute("href") or "").lower()
                    title = (link.get_attribute("title") or "").lower()
                    combined = f"{text} {href} {title}"
                    if any(kw in combined for kw in ["download", "xls", "export", "excel"]):
                        driver.execute_script("arguments[0].click();", link)
                        print(f"  Clicked link: '{link.text.strip()}'")
                        clicked = True
                        break
                except Exception:
                    continue

        if not clicked:
            print(f"[ERROR] Could not find download button for {ticker}")
            _save_debug_artifacts(driver, download_dir, ticker)
            return None

        return _poll_for_new_file(download_dir, existing_files, timeout=20)

    except Exception as e:
        print(f"[ERROR] {ticker}: {e}")
        import traceback; traceback.print_exc()
        return None
    finally:
        driver.quit()


# =============================================================================
# WISDOMTREE (HYIN) — undetected-chromedriver: ALL HOLDINGS → Export Holdings
#
# WisdomTree is protected by Cloudflare, which blocks standard headless Chrome.
# undetected-chromedriver patches Chrome's automation fingerprint so Cloudflare
# does not trigger the "Please enable cookies" / "You have been blocked" page.
# Running non-headless (HYIN_HEADLESS = False) is strongly recommended because
# Cloudflare's headless detection is more aggressive than its visible-browser checks.
# =============================================================================

def download_wisdomtree_holdings(ticker: str, url: str, download_dir: str, headless: bool = False) -> str | None:
    """
    Download WisdomTree ETF holdings using undetected-chromedriver to bypass Cloudflare.
    Steps: click 'ALL HOLDINGS' to expand full list, then click 'Export Holdings'.
    """
    try:
        import undetected_chromedriver as uc
    except ImportError:
        print("[ERROR] undetected-chromedriver not installed. Run: pip install undetected-chromedriver")
        return None

    ticker = ticker.upper()
    os.makedirs(download_dir, exist_ok=True)
    download_dir = os.path.abspath(download_dir)

    _delete_old_files(download_dir, f"wisdomtree*{ticker.lower()}*.csv", f"wisdomtree*{ticker.lower()}*.xls*")
    existing_files = _snapshot_existing(download_dir)

    print("Starting browser (undetected-chromedriver)...")
    options = uc.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_experimental_option("prefs", {
        "download.default_directory": download_dir,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True,
    })

    driver = uc.Chrome(options=options, headless=headless)
    try:
        print(f"Opening: {url}")
        driver.get(url)
        # Allow extra time for any Cloudflare JS challenge to resolve
        time.sleep(10)

        # Verify the page loaded (not a Cloudflare block page)
        page_src = driver.page_source.lower()
        if "you have been blocked" in page_src or ("enable cookies" in page_src and "cloudflare" in page_src):
            print("[ERROR] Cloudflare block page detected. Try setting HYIN_HEADLESS = False "
                  "and ensure undetected-chromedriver is up to date.")
            _save_debug_artifacts(driver, download_dir, ticker)
            return None

        _accept_cookies_and_consent(driver)
        time.sleep(2)

        # Step 1: Click "ALL HOLDINGS" to load the full list
        all_clicked = False
        candidates = (
            driver.find_elements(By.TAG_NAME, "button")
            + driver.find_elements(By.TAG_NAME, "a")
            + driver.find_elements(By.TAG_NAME, "span")
        )
        for el in candidates:
            try:
                text = el.text.strip().upper()
                if text in ("ALL HOLDINGS", "ALL", "VIEW ALL", "SHOW ALL") or "ALL HOLDINGS" in text:
                    driver.execute_script("arguments[0].click();", el)
                    print(f"  Clicked 'ALL HOLDINGS': '{el.text.strip()}'")
                    all_clicked = True
                    time.sleep(4)
                    break
            except Exception:
                continue

        if not all_clicked:
            print("  [WARNING] Could not find 'ALL HOLDINGS' button; attempting export anyway...")

        # Step 2: Click "Export Holdings"
        export_clicked = False
        for el in driver.find_elements(By.TAG_NAME, "button") + driver.find_elements(By.TAG_NAME, "a"):
            try:
                text = el.text.lower()
                if "export" in text or ("download" in text and "holding" in text):
                    driver.execute_script("arguments[0].click();", el)
                    print(f"  Clicked export: '{el.text.strip()}'")
                    export_clicked = True
                    break
            except Exception:
                continue

        if not export_clicked:
            print(f"[ERROR] Could not find 'Export Holdings' button for {ticker}")
            _save_debug_artifacts(driver, download_dir, ticker)
            return None

        return _poll_for_new_file(download_dir, existing_files, timeout=20)

    except Exception as e:
        print(f"[ERROR] {ticker}: {e}")
        import traceback; traceback.print_exc()
        return None
    finally:
        driver.quit()


# =============================================================================
# FRANKLIN TEMPLETON (PBDC) — Selenium: click XLS button
# =============================================================================

def download_franklintempleton_holdings(ticker: str, url: str, download_dir: str, headless: bool = True) -> str | None:
    """
    Download Franklin Templeton ETF holdings via Selenium.
    Finds and clicks the XLS download button on the portfolio page.
    """
    ticker = ticker.upper()
    os.makedirs(download_dir, exist_ok=True)
    download_dir = os.path.abspath(download_dir)

    _delete_old_files(download_dir, f"*{ticker.lower()}*.xls*", f"franklintempleton*{ticker.lower()}*.csv")
    existing_files = _snapshot_existing(download_dir)

    print("Starting browser...")
    driver = _build_chrome_driver(download_dir, headless)
    try:
        print(f"Opening: {url}")
        driver.get(url)
        time.sleep(7)

        _accept_cookies_and_consent(driver)
        time.sleep(2)

        # Scroll to portfolio section
        driver.execute_script("window.scrollTo(0, 800);")
        time.sleep(2)

        clicked = False
        all_elements = driver.find_elements(By.TAG_NAME, "button") + driver.find_elements(By.TAG_NAME, "a")

        # First pass: look for explicit "XLS" / "Excel" label
        for el in all_elements:
            try:
                text = el.text.strip()
                title = (el.get_attribute("title") or "")
                aria = (el.get_attribute("aria-label") or "")
                combined = f"{text} {title} {aria}".lower()
                if "xls" in combined or "excel" in combined:
                    driver.execute_script("arguments[0].click();", el)
                    print(f"  Clicked XLS element: '{text or title or aria}'")
                    clicked = True
                    break
            except Exception:
                continue

        # Second pass: any download/export button
        if not clicked:
            for el in all_elements:
                try:
                    text = el.text.lower()
                    if "download" in text or "export" in text:
                        driver.execute_script("arguments[0].click();", el)
                        print(f"  Clicked fallback download: '{el.text.strip()}'")
                        clicked = True
                        break
                except Exception:
                    continue

        if not clicked:
            print(f"[ERROR] Could not find XLS/download button for {ticker}")
            _save_debug_artifacts(driver, download_dir, ticker)
            return None

        return _poll_for_new_file(download_dir, existing_files, timeout=20)

    except Exception as e:
        print(f"[ERROR] {ticker}: {e}")
        import traceback; traceback.print_exc()
        return None
    finally:
        driver.quit()


# =============================================================================
# BONDBLOXX (PCMM) — Selenium: click Download CSV button
# =============================================================================

def download_bondbloxx_holdings(ticker: str, url: str, download_dir: str, headless: bool = True) -> str | None:
    """
    Download BondBloxx ETF holdings via Selenium.
    Clicks the 'Download CSV' button in the portfolio section.
    """
    ticker = ticker.upper()
    os.makedirs(download_dir, exist_ok=True)
    download_dir = os.path.abspath(download_dir)

    _delete_old_files(download_dir, f"bondbloxx*{ticker.lower()}*.csv")
    existing_files = set(glob.glob(os.path.join(download_dir, "*.csv")))

    print("Starting browser...")
    driver = _build_chrome_driver(download_dir, headless)
    try:
        print(f"Opening: {url}")
        driver.get(url)
        time.sleep(5)

        _accept_cookies_and_consent(driver)
        time.sleep(2)

        driver.execute_script("window.scrollTo(0, 600);")
        time.sleep(1)

        clicked = False
        all_elements = driver.find_elements(By.TAG_NAME, "button") + driver.find_elements(By.TAG_NAME, "a")

        # First pass: explicit "Download CSV"
        for el in all_elements:
            try:
                text = el.text.lower()
                if "csv" in text or ("download" in text and "csv" in text):
                    driver.execute_script("arguments[0].click();", el)
                    print(f"  Clicked 'Download CSV': '{el.text.strip()}'")
                    clicked = True
                    break
            except Exception:
                continue

        # Second pass: any download button
        if not clicked:
            for el in all_elements:
                try:
                    text = el.text.lower()
                    if "download" in text:
                        driver.execute_script("arguments[0].click();", el)
                        print(f"  Clicked download: '{el.text.strip()}'")
                        clicked = True
                        break
                except Exception:
                    continue

        if not clicked:
            print(f"[ERROR] Could not find Download CSV button for {ticker}")
            _save_debug_artifacts(driver, download_dir, ticker)
            return None

        return _poll_for_new_file(download_dir, existing_files, extensions=("*.csv",), timeout=15)

    except Exception as e:
        print(f"[ERROR] {ticker}: {e}")
        import traceback; traceback.print_exc()
        return None
    finally:
        driver.quit()


# =============================================================================
# SIMPLIFY (PCR) — Direct XLSX download + filter rows by ticker
# =============================================================================

def download_simplify_holdings(ticker: str, download_dir: str, days_back: int = DATE_URL_LOOKBACK) -> str | None:
    """
    Download the Simplify Portfolio EOD Tracker XLSX and extract rows where
    column A (FUND NAME) contains the given ticker. Saves result as CSV.

    URL format: https://www.simplify.us/sites/default/files/excel_holdings/YYYY_MM_DD_Simplify_Portfolio_EOD_Tracker.xlsx
    """
    ticker = ticker.upper()
    os.makedirs(download_dir, exist_ok=True)
    headers = {"User-Agent": "Mozilla/5.0"}

    for date in _get_recent_business_dates(days_back):
        date_str = date.strftime("%Y_%m_%d")
        url = (
            f"https://www.simplify.us/sites/default/files/excel_holdings/"
            f"{date_str}_Simplify_Portfolio_EOD_Tracker.xlsx"
        )
        print(f"  Trying: {url}")

        try:
            response = requests.get(url, headers=headers, timeout=30)
            if response.status_code != 200:
                print(f"  Not found ({response.status_code})")
                continue

            print(f"  Found! Parsing XLSX...")
            df = pd.read_excel(io.BytesIO(response.content), engine="openpyxl")

            # Column A is typically "FUND NAME" — search case-insensitively
            first_col = df.columns[0]
            mask = df[first_col].astype(str).str.upper().str.contains(ticker, na=False)
            filtered = df[mask]

            if filtered.empty:
                print(f"  [WARNING] No rows with '{ticker}' in column A ('{first_col}'). "
                      f"Sample values: {df[first_col].dropna().unique()[:5].tolist()}")
            else:
                print(f"  Found {len(filtered)} row(s) with '{ticker}'")

            out_file = os.path.join(download_dir, f"{date.strftime('%m%d%Y')}{ticker}.csv")
            filtered.to_csv(out_file, index=False)
            print(f"[SUCCESS] Saved: {out_file}")
            return out_file

        except Exception as e:
            print(f"  [ERROR] {e}")
            continue

    print(f"[ERROR] Could not download Simplify XLSX for {ticker} in last {days_back} business days")
    return None


# =============================================================================
# HILTON ETFS (HBDC) — Requests + date validation + table scrape
# =============================================================================

def download_hilton_holdings(ticker: str, url: str, download_dir: str) -> str | None:
    """
    Download Hilton ETFs holdings table, first verifying the 'as of' date is fresh.

    Strategy:
      1. requests.get() the page.
      2. Extract 'as of MM/DD/YYYY' with regex; reject if stale.
      3. Try pd.read_html() for the table (needs bs4/lxml installed).
      4. Fall back to Selenium DOM extraction if requests returns no table.
    """
    ticker = ticker.upper()
    os.makedirs(download_dir, exist_ok=True)
    headers_http = {"User-Agent": "Mozilla/5.0"}

    html_text = None
    try:
        resp = requests.get(url, headers=headers_http, timeout=20)
        if resp.status_code == 200:
            html_text = resp.text
        else:
            print(f"  requests returned {resp.status_code}; falling back to Selenium")
    except Exception as e:
        print(f"  requests failed ({e}); falling back to Selenium")

    def _parse_as_of_date(text: str):
        match = re.search(r'as\s+of\s+(\d{1,2}/\d{1,2}/\d{4})', text, re.IGNORECASE)
        if match:
            try:
                return datetime.strptime(match.group(1), "%m/%d/%Y")
            except ValueError:
                pass
        return None

    def _is_fresh(as_of_date: datetime) -> bool:
        business_dates = list(_get_recent_business_dates(DATE_URL_LOOKBACK))
        oldest_ok = min(d.date() for d in business_dates)
        return as_of_date.date() >= oldest_ok

    as_of_date = None
    df = None

    if html_text:
        as_of_date = _parse_as_of_date(html_text)
        if as_of_date:
            print(f"  Page 'as of' date: {as_of_date.strftime('%m/%d/%Y')}")
            if not _is_fresh(as_of_date):
                print(f"[WARNING] HBDC data is stale (as of {as_of_date.strftime('%m/%d/%Y')}). Skipping.")
                return None
        else:
            print("  [WARNING] Could not find 'as of' date; proceeding anyway...")

        # Attempt pd.read_html() — requires bs4, lxml, or html5lib
        try:
            tables = pd.read_html(io.StringIO(html_text))
            if tables:
                df = max(tables, key=len)
                print(f"  Extracted table via requests ({len(df)} rows)")
        except Exception:
            pass  # will fall through to Selenium below

    # Fall back to Selenium if table not yet found
    if df is None:
        print("  Using Selenium for table extraction...")
        driver = _build_chrome_driver(download_dir, HEADLESS)
        try:
            try:
                driver.get(url)
            except TimeoutException:
                print("  [WARNING] Page load timed out; attempting extraction from partial load...")
            time.sleep(5)
            _accept_cookies_and_consent(driver)
            time.sleep(2)

            if as_of_date is None:
                as_of_date = _parse_as_of_date(driver.page_source)
                if as_of_date:
                    print(f"  Page 'as of' date (Selenium): {as_of_date.strftime('%m/%d/%Y')}")
                    if not _is_fresh(as_of_date):
                        print(f"[WARNING] HBDC data is stale. Skipping.")
                        return None

            df = _extract_table_via_selenium(driver)
            if df is not None:
                print(f"  Extracted table via Selenium ({len(df)} rows)")
        finally:
            driver.quit()

    if df is None or df.empty:
        print(f"[ERROR] Could not extract table from {url}")
        return None

    file_date = as_of_date if as_of_date else datetime.today()
    out_file = os.path.join(download_dir, f"{file_date.strftime('%m%d%Y')}{ticker}.csv")
    df.to_csv(out_file, index=False)
    print(f"[SUCCESS] Saved: {out_file}")
    return out_file


# =============================================================================
# KRANESHARES (AGIX) — Direct CSV download, date-based URL
# =============================================================================

def download_kraneshares_holdings(ticker: str, download_dir: str, days_back: int = DATE_URL_LOOKBACK) -> str | None:
    """
    Download KraneShares ETF holdings CSV.

    URL format: https://kraneshares.com/csv/MM_DD_YYYY_{ticker_lower}_holdings.csv
    Example:    https://kraneshares.com/csv/03_02_2026_agix_holdings.csv
    """
    ticker = ticker.upper()
    os.makedirs(download_dir, exist_ok=True)
    headers = {"User-Agent": "Mozilla/5.0"}

    for date in _get_recent_business_dates(days_back):
        date_str = date.strftime("%m_%d_%Y")
        url = f"https://kraneshares.com/csv/{date_str}_{ticker.lower()}_holdings.csv"
        print(f"  Trying: {url}")

        try:
            response = requests.get(url, headers=headers, timeout=20)
            if response.status_code != 200:
                print(f"  Not found ({response.status_code})")
                continue

            content = response.content
            if len(content) < 20:
                print("  Empty response, skipping")
                continue

            out_file = os.path.join(download_dir, f"{date.strftime('%m%d%Y')}{ticker}.csv")
            with open(out_file, "wb") as f:
                f.write(content)
            print(f"[SUCCESS] Saved: {out_file}")
            return out_file

        except Exception as e:
            print(f"  [ERROR] {e}")
            continue

    print(f"[ERROR] Could not download KraneShares CSV for {ticker} in last {days_back} business days")
    return None


# =============================================================================
# BARON CAPITAL (RONB) — Direct CSV download, date-based URL
# =============================================================================

def download_baron_holdings(ticker: str, download_dir: str, days_back: int = DATE_URL_LOOKBACK) -> str | None:
    """
    Download Baron Capital ETF holdings CSV.

    URL format: https://www.baroncapitalgroup.com/api/product/media/csv/{TICKER}-HOLDINGS-{YYYYMMDD}-0.csv
    Example:    RONB-HOLDINGS-20260302-0.csv
    """
    ticker = ticker.upper()
    os.makedirs(download_dir, exist_ok=True)
    headers = {"User-Agent": "Mozilla/5.0"}

    for date in _get_recent_business_dates(days_back):
        date_str = date.strftime("%Y%m%d")
        url = (
            f"https://www.baroncapitalgroup.com/api/product/media/csv/"
            f"{ticker}-HOLDINGS-{date_str}-0.csv"
            f"?product_type=etf-downloads&id={BARON_RONB_UUID}"
        )
        print(f"  Trying: {url}")

        try:
            response = requests.get(url, headers=headers, timeout=20)
            if response.status_code != 200:
                print(f"  Not found ({response.status_code})")
                continue

            content = response.content
            if len(content) < 20:
                print("  Empty response, skipping")
                continue

            out_file = os.path.join(download_dir, f"{date.strftime('%m%d%Y')}{ticker}.csv")
            with open(out_file, "wb") as f:
                f.write(content)
            print(f"[SUCCESS] Saved: {out_file}")
            return out_file

        except Exception as e:
            print(f"  [ERROR] {e}")
            continue

    print(f"[ERROR] Could not download Baron Capital CSV for {ticker} in last {days_back} business days")
    return None


# =============================================================================
# ENTREPRENEUR SHARES (XOVR) — Selenium: click VIEW ALL HOLDINGS → scrape table
# =============================================================================

def download_entrepreneurshares_holdings(ticker: str, url: str, download_dir: str, headless: bool = True) -> str | None:
    """
    Download Entrepreneur Shares ETF holdings via Selenium.
    Steps: click 'VIEW ALL HOLDINGS', wait for popup/expanded table, scrape it.
    """
    ticker = ticker.upper()
    os.makedirs(download_dir, exist_ok=True)
    download_dir = os.path.abspath(download_dir)

    print("Starting browser...")
    driver = _build_chrome_driver(download_dir, headless)
    try:
        print(f"Opening: {url}")
        driver.get(url)
        time.sleep(5)

        _accept_cookies_and_consent(driver)
        time.sleep(2)

        # Find and click "VIEW ALL HOLDINGS"
        clicked = False
        candidates = (
            driver.find_elements(By.TAG_NAME, "button")
            + driver.find_elements(By.TAG_NAME, "a")
            + driver.find_elements(By.TAG_NAME, "span")
        )
        for el in candidates:
            try:
                text = el.text.strip().upper()
                if "VIEW ALL HOLDINGS" in text or text == "VIEW ALL" or "ALL HOLDINGS" in text:
                    driver.execute_script("arguments[0].click();", el)
                    print(f"  Clicked: '{el.text.strip()}'")
                    clicked = True
                    time.sleep(4)
                    break
            except Exception:
                continue

        if not clicked:
            print(f"[ERROR] Could not find 'VIEW ALL HOLDINGS' button for {ticker}")
            _save_debug_artifacts(driver, download_dir, ticker)
            return None

        # Wait for modal/expanded content
        time.sleep(3)

        # If the popup is inside an iframe, switch into it
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        if iframes:
            try:
                driver.switch_to.frame(iframes[-1])
                print("  Switched to iframe")
            except Exception:
                pass

        # Extract table via DOM
        df = _extract_table_via_selenium(driver)

        if df is None or df.empty:
            print(f"[ERROR] No table found after clicking VIEW ALL HOLDINGS for {ticker}")
            _save_debug_artifacts(driver, download_dir, ticker)
            return None

        print(f"  Extracted table ({len(df)} rows, {len(df.columns)} columns)")

        out_file = os.path.join(download_dir, f"{datetime.today().strftime('%m%d%Y')}{ticker}.csv")
        df.to_csv(out_file, index=False)
        print(f"[SUCCESS] Saved: {out_file}")
        return out_file

    except Exception as e:
        print(f"[ERROR] {ticker}: {e}")
        import traceback; traceback.print_exc()
        return None
    finally:
        driver.quit()


# =============================================================================
# MAIN
# =============================================================================

def check_and_download_all():
    """Check and download all configured files."""
    print("Starting download check for all files...")

    # ---- Original: SSGA files ----
    ssga_downloads = 0
    for name, config in URLS.items():
        if check_and_download_single(name, config):
            ssga_downloads += 1

    # ---- Original: Invesco files ----
    invesco_downloads = check_and_download_invesco()

    # ---- New: Additional tickers ----
    new_results = {}

    print("\n--- Checking BIZD (VanEck) ---")
    new_results["BIZD"] = download_vaneck_holdings("BIZD", DOWNLOAD_DIR, HEADLESS)

    print("\n--- Checking HYIN (WisdomTree) ---")
    new_results["HYIN"] = download_wisdomtree_holdings("HYIN", WISDOMTREE_HYIN_URL, DOWNLOAD_DIR, HYIN_HEADLESS)

    print("\n--- Checking PBDC (Franklin Templeton) ---")
    new_results["PBDC"] = download_franklintempleton_holdings("PBDC", FRANKLINTEMPLETON_PBDC_URL, DOWNLOAD_DIR, HEADLESS)

    print("\n--- Checking PCMM (BondBloxx) ---")
    new_results["PCMM"] = download_bondbloxx_holdings("PCMM", BONDBLOXX_PCMM_URL, DOWNLOAD_DIR, HEADLESS)

    print("\n--- Checking PCR (Simplify) ---")
    new_results["PCR"] = download_simplify_holdings("PCR", DOWNLOAD_DIR)

    print("\n--- Checking HBDC (Hilton ETFs) ---")
    new_results["HBDC"] = download_hilton_holdings("HBDC", HILTON_HBDC_URL, DOWNLOAD_DIR)

    print("\n--- Checking AGIX (KraneShares) ---")
    new_results["AGIX"] = download_kraneshares_holdings("AGIX", DOWNLOAD_DIR)

    print("\n--- Checking RONB (Baron Capital) ---")
    new_results["RONB"] = download_baron_holdings("RONB", DOWNLOAD_DIR)

    print("\n--- Checking XOVR (Entrepreneur Shares) ---")
    new_results["XOVR"] = download_entrepreneurshares_holdings("XOVR", ENTREPRENEURSHARES_XOVR_URL, DOWNLOAD_DIR, HEADLESS)

    new_downloads = sum(1 for v in new_results.values() if v)

    print(f"\n--- Summary ---")
    print(f"SSGA files checked: {len(URLS)}")
    print(f"SSGA files downloaded: {ssga_downloads}")
    print(f"Invesco files checked: {len(INVESCO_TICKERS)}")
    print(f"Invesco files downloaded: {invesco_downloads}")
    print(f"New tickers checked: {len(new_results)}")
    print(f"New tickers downloaded: {new_downloads}")
    for ticker, path in new_results.items():
        status = f"OK  → {os.path.basename(path)}" if path else "FAILED"
        print(f"  {ticker}: {status}")


if __name__ == "__main__":
    check_and_download_all()
