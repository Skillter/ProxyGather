import time
import requests
import re
import threading
from typing import List
from seleniumbase import BaseCase

from scrapers.proxy_scraper import extract_proxies_from_content

BROWSER_VISIT_URL = "https://openproxylist.com/proxy/"
POST_TARGET_URL = "https://openproxylist.com/get-list.html"

def scrape_from_openproxylist(sb: BaseCase, browser_lock: threading.Lock, verbose: bool = True) -> List[str]:
    if verbose:
        print("[RUNNING] 'OpenProxyList' automation scraper has started.")
    
    all_proxies = set()
    
    with browser_lock:
        if verbose:
            print("[INFO] OpenProxyList: Acquired browser lock.")
        
        main_window = sb.driver.current_window_handle
        sb.open_new_tab()
        new_tab = sb.driver.window_handles[-1]
        sb.switch_to_window(new_tab)

        try:
            if verbose:
                print(f"[INFO] OpenProxyList: Navigating to {BROWSER_VISIT_URL}...")
            sb.open(BROWSER_VISIT_URL)
            
            time.sleep(2)
            sb.wait_for_element_present('script[src*="recaptcha/api.js?render="]', timeout=20)
            
            time.sleep(1)

            html_content = sb.get_page_source()
            site_key_regex = re.compile(r'recaptcha/api\.js\?render=([\w-]+)')
            match = site_key_regex.search(html_content)
            
            if not match:
                raise ValueError("Could not find reCAPTCHA site key.")
                
            recaptcha_site_key = match.group(1)
            if verbose:
                print(f"[INFO] OpenProxyList: Found site key: {recaptcha_site_key}")

            time.sleep(5)
            
            page_num = 1
            session = requests.Session()

            while True:
                if verbose:
                    print(f"[INFO] OpenProxyList: Generating token for page {page_num}...")
                
                js_command = f"return grecaptcha.execute('{recaptcha_site_key}', {{action: 'proxy'}})"
                token = sb.execute_script(js_command)

                if not token:
                    if verbose: print(f"[WARN]   ... Failed to generate token. Stopping.")
                    break

                post_data = {'g-recaptcha-response': token, 'response': '', 'sort': 'sortlast', 'page': str(page_num)}
                
                response = session.post(POST_TARGET_URL, data=post_data, timeout=20)
                response.raise_for_status()
                newly_found = extract_proxies_from_content(response.text, verbose=False)
                
                if not newly_found:
                    if verbose: print(f"[INFO]   ... No proxies found on page {page_num}. End of list.")
                    break

                initial_count = len(all_proxies)
                all_proxies.update(newly_found)
                
                if verbose:
                    print(f"[INFO]   ... Found {len(newly_found)} proxies. Total unique: {len(all_proxies)}.")

                if len(all_proxies) == initial_count and page_num > 1:
                    if verbose: print("[INFO]   ... No new unique proxies found. Stopping.")
                    break

                page_num += 1
                time.sleep(1)
        
        except Exception as e:
            if verbose:
                print(f"[ERROR] OpenProxyList scraper failed: {e}")
        finally:
            if new_tab in sb.driver.window_handles and len(sb.driver.window_handles) > 1:
                sb.switch_to_window(new_tab)
                sb.driver.close()
            if main_window in sb.driver.window_handles:
                sb.switch_to_window(main_window)
            if verbose: print("[INFO] OpenProxyList: Released browser lock.")

    if verbose:
        print(f"[INFO] OpenProxyList: Finished. Found a total of {len(all_proxies)} unique proxies.")
    
    return sorted(list(all_proxies))