import time
import requests
import re
from DrissionPage import ChromiumPage, ChromiumOptions 
from typing import List
import sys
import os

from scrapers.proxy_scraper import extract_proxies_from_content

# --- Configuration ---
BROWSER_VISIT_URL = "https://openproxylist.com/proxy/"
POST_TARGET_URL = "https://openproxylist.com/get-list.html"

def scrape_from_openproxylist(verbose: bool = True) -> List[str]:
    """
    Scrapes proxies from OpenProxyList using DrissionPage in headless mode.
    """
    if verbose:
        print("[RUNNING] 'OpenProxyList' automation scraper has started (using DrissionPage).")
    
    all_proxies = set()
    page = None
    
    try:
        # --- Step 1: Initialize the browser with DrissionPage ---
        if verbose:
            print("[INFO] OpenProxyList: Initializing browser with DrissionPage...")
        
        co = ChromiumOptions()
        co.set_argument("--headless", "new")

        # the github actions runner needs this, even if not running as root
        if sys.platform == "linux":
            print("[WARNING] You are running the script on Linux. Applying --no-sandbox as a workaround.")
            co.set_argument('--no-sandbox')
        
        page = ChromiumPage(co)

        if verbose:
            print(f"[INFO] OpenProxyList: Navigating to {BROWSER_VISIT_URL} to prepare for token generation...")
        page.get(BROWSER_VISIT_URL)

        # --- Step 2: Dynamically find the reCAPTCHA site key ---
        if verbose:
            print("[INFO] OpenProxyList: Searching for dynamic reCAPTCHA site key...")
        
        html_content = page.html
        site_key_regex = re.compile(r'recaptcha/api\.js\?render=([\w-]+)')
        match = site_key_regex.search(html_content)
        
        if not match:
            raise ValueError("Could not dynamically find the reCAPTCHA site key on the page.")
            
        recaptcha_site_key = match.group(1)
        if verbose:
            print(f"[INFO] OpenProxyList: Dynamically found site key: {recaptcha_site_key}")

        time.sleep(5) 
        
        if verbose:
            print("[INFO] OpenProxyList: reCAPTCHA library should be loaded. Starting page scraping.")
        
        # --- Step 3: Loop through pages, generating a new token each time ---
        page_num = 1
        session = requests.Session()

        while True:
            if verbose:
                print(f"[INFO] OpenProxyList: Generating new token for page {page_num}...")
            
            js_command = f"return grecaptcha.execute('{recaptcha_site_key}', {{action: 'proxy'}})"
            token = page.run_js(js_command)

            if not token:
                if verbose:
                    print(f"[WARN]   ... Failed to generate reCAPTCHA token for page {page_num}. Stopping.")
                    break

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

                if len(all_proxies) == initial_count and page_num > 1:
                    if verbose:
                        print("[INFO]   ... No new unique proxies found. Stopping.")
                    break

                page_num += 1
                time.sleep(1) # a small delay between post requests

            except requests.RequestException as e:
                if verbose:
                    print(f"[ERROR]  ... Request for page {page_num} failed: {e}. Stopping.")
                break
    
    except Exception as e:
        if verbose:
            print(f"[ERROR] DrissionPage scraper failed with an exception: {e}")

    finally:
        # --- Step 4: Close the browser ---
        if page:
            if verbose:
                print("[INFO] OpenProxyList: Shutting down the browser.")
            page.quit()

    if verbose:
        print(f"[INFO] OpenProxyList: Finished. Found a total of {len(all_proxies)} unique proxies.")
    
    return sorted(list(all_proxies))