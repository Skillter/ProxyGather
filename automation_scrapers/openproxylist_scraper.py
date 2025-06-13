import time
import requests
import re
import undetected_chromedriver as uc
from selenium.webdriver.support.ui import WebDriverWait
from typing import List

# --- MODIFIED: Import our powerful, centralized extraction function ---
from scrapers.proxy_scraper import extract_proxies_from_content

# --- Configuration ---
# The initial URL the browser visits to get the token
BROWSER_VISIT_URL = "https://openproxylist.com/proxy/"
# The correct URL to send the POST requests to
POST_TARGET_URL = "https://openproxylist.com/get-list.html"
# --- REMOVED: The hardcoded site key is no longer needed ---
# RECAPTCHA_SITE_KEY = "6LepNaEaAAAAAMcfZb4shvxaVWulaKUfjhOxOHRS"

def scrape_from_openproxylist(verbose: bool = True) -> List[str]:
    """
    Scrapes proxies from OpenProxyList. It keeps a browser open to dynamically
    find the reCAPTCHA site key and then generate a fresh token for each
    paginated POST request.

    Args:
        verbose: If True, prints detailed status messages.

    Returns:
        A list of unique proxy strings found.
    """
    if verbose:
        print("[RUNNING] 'OpenProxyList' automation scraper has started.")
    
    all_proxies = set()
    driver = None
    
    try:
        # --- Step 1: Initialize the automated browser and leave it open ---
        if verbose:
            print("[INFO] OpenProxyList: Initializing automated browser...")
        
        options = uc.ChromeOptions()
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-gpu")
        options.add_argument("--headless")
        driver = uc.Chrome(options=options, use_subprocess=True)

        if verbose:
            print(f"[INFO] OpenProxyList: Navigating to {BROWSER_VISIT_URL} to prepare for token generation...")
        driver.get(BROWSER_VISIT_URL)

        # --- ADDED: Dynamically find the reCAPTCHA site key ---
        if verbose:
            print("[INFO] OpenProxyList: Searching for dynamic reCAPTCHA site key...")
        
        html_content = driver.page_source
        site_key_regex = re.compile(r'recaptcha/api\.js\?render=([\w-]+)')
        match = site_key_regex.search(html_content)
        
        if not match:
            raise ValueError("Could not dynamically find the reCAPTCHA site key on the page.")
            
        recaptcha_site_key = match.group(1)
        if verbose:
            print(f"[INFO] OpenProxyList: Dynamically found site key: {recaptcha_site_key}")

        wait = WebDriverWait(driver, 45)
        wait.until(
            lambda d: d.execute_script("return typeof grecaptcha !== 'undefined' && typeof grecaptcha.execute !== 'undefined'")
        )
        if verbose:
            print("[INFO] OpenProxyList: reCAPTCHA library is loaded. Starting page scraping.")
        
        # --- Step 2: Loop through pages, generating a new token each time ---
        page_num = 1
        session = requests.Session()

        while True:
            # --- MODIFIED: Generate a fresh token INSIDE the loop ---
            if verbose:
                print(f"[INFO] OpenProxyList: Generating new token for page {page_num}...")
            
            # --- MODIFIED: Use the dynamically found site key ---
            js_command = f"return grecaptcha.execute('{recaptcha_site_key}', {{action: 'proxy'}})"
            token = driver.execute_script(js_command)

            if not token:
                if verbose:
                    print(f"[WARN]   ... Failed to generate reCAPTCHA token for page {page_num}. Stopping.")
                break

            # Create the form data payload with the new token
            post_data = {
                'g-recaptcha-response': token,
                'response': '',
                'sort': 'sortlast',
                'page': str(page_num)
            }
            
            if verbose:
                print(f"[INFO]   ... POSTing to {POST_TARGET_URL} for page {page_num}...")
            
            try:
                response = session.post(POST_TARGET_URL, data=post_data, timeout=20)
                response.raise_for_status()

                newly_found = extract_proxies_from_content(response.text, verbose=False)
                
                if not newly_found:
                    if verbose:
                        print(f"[INFO]   ... No proxies found on page {page_num}. Assuming end of list.")
                    break

                initial_count = len(all_proxies)
                all_proxies.update(newly_found)
                
                if verbose:
                    print(f"[INFO]   ... Found {len(newly_found)} proxies on this page. Total unique: {len(all_proxies)}.")

                if len(all_proxies) == initial_count:
                    if verbose:
                        print("[INFO]   ... No new unique proxies found. Stopping.")
                    break

                page_num += 1
                time.sleep(1)

            except requests.RequestException as e:
                if verbose:
                    print(f"[ERROR]  ... Request for page {page_num} failed: {e}. Stopping.")
                break
    
    finally:
        # --- Step 3: Close the browser only after all scraping is done ---
        if driver:
            if verbose:
                print("[INFO] OpenProxyList: Shutting down the browser.")
            driver.quit()

    if verbose:
        print(f"[INFO] OpenProxyList: Finished. Found a total of {len(all_proxies)} unique proxies.")
    
    return sorted(list(all_proxies))