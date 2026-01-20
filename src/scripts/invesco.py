"""
Invesco ETF Holdings Downloader (Selenium)
==========================================

Downloads ETF holdings CSV from Invesco using a real browser.

Requirements:
    pip install selenium webdriver-manager pandas
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time
import os
import glob
import pandas as pd


# =============================================================================
# CONFIGURATION - Change these settings
# =============================================================================
TICKER = "HIYS"
DOWNLOAD_DIR = os.path.join(os.getcwd(), "invesco_downloads")  # Where to save files
HEADLESS = False  # Set to True to run without browser window
# =============================================================================


def download_invesco_holdings(ticker: str, download_dir: str, headless: bool = False) -> str:
    """
    Download Invesco ETF holdings using Selenium.
    
    Args:
        ticker: ETF ticker symbol (e.g., 'HIYS', 'QQQ')
        download_dir: Directory to save the downloaded file
        headless: Run browser without visible window
    
    Returns:
        Path to downloaded file, or None if failed
    """
    ticker = ticker.upper()
    
    # Create download directory if it doesn't exist
    os.makedirs(download_dir, exist_ok=True)
    download_dir = os.path.abspath(download_dir)
    
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
    print(f"Download directory: {download_dir}")
    
    # Initialize Chrome driver
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    try:
        # Navigate to the holdings page
        url = f"https://www.invesco.com/us/financial-products/etfs/holdings?audienceType=Investor&ticker={ticker}"
        print(f"Opening: {url}")
        driver.get(url)
        time.sleep(3)
        
        # Handle "Select your role" popup if it appears
        try:
            print("Checking for role selection popup...")
            investor_btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//div[contains(text(), 'Individual Investor')]"))
            )
            investor_btn.click()
            time.sleep(1)
            
            confirm_btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Confirm')]"))
            )
            confirm_btn.click()
            time.sleep(2)
            print("  Role selected.")
        except:
            print("  No role popup found.")
        
        # Handle cookie consent if it appears
        try:
            accept_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Accept')]")
            accept_btn.click()
            time.sleep(1)
            print("  Cookie consent accepted.")
        except:
            pass
        
        # Find and click the Export Data button
        print("Looking for Export Data button...")
        
        export_selectors = [
            "//button[contains(text(), 'Export Data')]",
            "//a[contains(text(), 'Export Data')]",
            "//button[contains(text(), 'Export')]",
            "//a[contains(text(), 'Export')]",
            "//*[contains(@class, 'export')]",
            "//button[contains(@class, 'download')]",
        ]
        
        clicked = False
        for selector in export_selectors:
            try:
                btn = WebDriverWait(driver, 3).until(
                    EC.element_to_be_clickable((By.XPATH, selector))
                )
                btn.click()
                print(f"  Clicked: {selector}")
                clicked = True
                break
            except:
                continue
        
        if not clicked:
            print("  Could not find Export button. Trying direct download URL...")
            download_url = f"https://www.invesco.com/us/financial-products/etfs/holdings/main/holdings/0?audienceType=Investor&action=download&ticker={ticker}"
            driver.get(download_url)
        
        # Wait for download to complete
        print("Waiting for download to complete...")
        time.sleep(5)
        
        # Find the downloaded CSV file
        csv_files = glob.glob(os.path.join(download_dir, "*.csv"))
        
        if csv_files:
            # Get the most recently created file
            latest_file = max(csv_files, key=os.path.getctime)
            
            # Verify it's valid CSV
            df = pd.read_csv(latest_file)
            print(f"\n✓ Success! Downloaded {len(df)} holdings")
            print(f"  File: {latest_file}")
            return latest_file
        else:
            print("\n✗ No CSV file found in download directory")
            return None
            
    except Exception as e:
        print(f"\n✗ Error: {e}")
        return None
        
    finally:
        driver.quit()
        print("Browser closed.")


def main():
    print(f"\nInvesco ETF Holdings Downloader (Selenium)")
    print(f"=" * 50)
    print(f"Ticker: {TICKER}")
    print(f"Download folder: {DOWNLOAD_DIR}")
    print(f"Headless mode: {HEADLESS}\n")
    
    filepath = download_invesco_holdings(TICKER, DOWNLOAD_DIR, HEADLESS)
    
    print(f"\n{'=' * 50}")
    if filepath:
        print(f"File saved to: {filepath}")
        
    else:
        print("Download failed.")


if __name__ == "__main__":
    main()