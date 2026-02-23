import requests
import os
import time
import glob

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

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
INVESCO_TICKERS = ["GTOH", "GTO", "GTOC"]
INVESCO_DOWNLOAD_DIR = os.path.join(os.getcwd())
INVESCO_HEADLESS = True  # Set to False to see browser window

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
        "GTOH": "invesco_short_duation_high_yield_etf-monthly_holdings*.csv",
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
# MAIN
# =============================================================================

def check_and_download_all():
    """Check and download all configured files."""
    print("Starting download check for all files...")
    
    # Download SSGA files
    ssga_downloads = 0
    for name, config in URLS.items():
        if check_and_download_single(name, config):
            ssga_downloads += 1
    
    # Download Invesco files
    invesco_downloads = check_and_download_invesco()
    
    print(f"\n--- Summary ---")
    print(f"SSGA files checked: {len(URLS)}")
    print(f"SSGA files downloaded: {ssga_downloads}")
    print(f"Invesco files checked: {len(INVESCO_TICKERS)}")
    print(f"Invesco files downloaded: {invesco_downloads}")

if __name__ == "__main__":
    check_and_download_all()