def download_invesco_holdings(ticker: str, download_dir: str, headless: bool = True) -> str:
    """
    Download Invesco ETF holdings using Selenium.
    """
    ticker = ticker.upper()
    
    # Create download directory if it doesn't exist
    os.makedirs(download_dir, exist_ok=True)
    download_dir = os.path.abspath(download_dir)
    
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
        time.sleep(3)
        
        # Handle "Select your role" popup
        role_selectors = [
            "//div[contains(text(), 'Individual Investor')]",
            "//*[contains(text(), 'Individual Investor')]",
            "//span[contains(text(), 'Individual Investor')]",
        ]
        
        for selector in role_selectors:
            try:
                element = WebDriverWait(driver, 2).until(
                    EC.element_to_be_clickable((By.XPATH, selector))
                )
                element.click()
                print("Clicked: Individual Investor")
                time.sleep(1)
                break
            except:
                continue
        
        # Try to click Confirm button
        confirm_selectors = [
            "//button[contains(text(), 'Confirm')]",
            "//button[contains(text(), 'Continue')]",
        ]
        
        for selector in confirm_selectors:
            try:
                btn = WebDriverWait(driver, 2).until(
                    EC.element_to_be_clickable((By.XPATH, selector))
                )
                btn.click()
                print("Clicked: Confirm/Continue")
                time.sleep(2)
                break
            except:
                continue
        
        # Handle cookie consent if it appears
        try:
            accept_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Accept')]")
            accept_btn.click()
            print("Clicked: Accept cookies")
            time.sleep(1)
        except:
            pass
        
        time.sleep(3)
        
        # Scroll down to make sure Export button is visible
        driver.execute_script("window.scrollTo(0, 500);")
        time.sleep(1)
        
        # Find and click the Export Data button - expanded selectors
        export_selectors = [
            "//button[contains(text(), 'Export Data')]",
            "//a[contains(text(), 'Export Data')]",
            "//button[contains(text(), 'Export')]",
            "//a[contains(text(), 'Export')]",
            "//button[contains(@class, 'export')]",
            "//a[contains(@class, 'export')]",
            "//*[contains(@class, 'download')]//button",
            "//button[contains(@aria-label, 'export')]",
            "//button[contains(@aria-label, 'Export')]",
            "//button[contains(@aria-label, 'download')]",
            "//*[@data-testid='export-button']",
        ]
        
        clicked = False
        for selector in export_selectors:
            try:
                btn = WebDriverWait(driver, 2).until(
                    EC.element_to_be_clickable((By.XPATH, selector))
                )
                btn.click()
                print(f"Clicked export button: {selector}")
                clicked = True
                break
            except:
                continue
        
        if not clicked:
            # Try finding by partial link text
            try:
                btn = driver.find_element(By.PARTIAL_LINK_TEXT, "Export")
                btn.click()
                print("Clicked export via partial link text")
                clicked = True
            except:
                pass
        
        if not clicked:
            # Debug: print all buttons on the page
            print("\nDEBUG - Buttons found on page:")
            buttons = driver.find_elements(By.TAG_NAME, "button")
            for i, btn in enumerate(buttons):
                try:
                    text = btn.text.strip()
                    if text:
                        print(f"  Button {i}: '{text}'")
                except:
                    pass
            
            print("\nDEBUG - Links found on page:")
            links = driver.find_elements(By.TAG_NAME, "a")
            for i, link in enumerate(links):
                try:
                    text = link.text.strip()
                    href = link.get_attribute("href") or ""
                    if "export" in text.lower() or "download" in text.lower() or "export" in href.lower() or "download" in href.lower():
                        print(f"  Link {i}: '{text}' -> {href}")
                except:
                    pass
            
            print("\n✗ Could not find Export button")
            
            # Save screenshot for debugging
            screenshot_path = os.path.join(download_dir, "debug_screenshot.png")
            driver.save_screenshot(screenshot_path)
            print(f"Screenshot saved to: {screenshot_path}")
            
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
                print(f"✓ Downloaded: {latest_file}")
                return latest_file
            
            print(f"  Waiting... ({i+1}/{max_wait}s)")
        
        print(f"✗ No new CSV file downloaded after {max_wait} seconds")
        return None
            
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return None
        
    finally:
        driver.quit()