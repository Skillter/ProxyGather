import time
import threading
from typing import List
from seleniumbase import BaseCase

from scrapers.proxy_scraper import extract_proxies_from_content

URL_TEMPLATE = "https://hide.mn/en/proxy-list/?start={offset}"
DELAY_SECONDS = 1.5

def scrape_from_hidemn(sb: BaseCase, browser_lock: threading.Lock, verbose: bool = True) -> List[str]:
    """
    Scrapes hide.mn by acquiring a lock on the shared browser instance,
    performing all actions in its own tab, and then releasing the lock.
    """
    if verbose:
        print("[RUNNING] 'Hide.mn' automation scraper has started.")
    
    all_proxies = set()
    
    with browser_lock:
        if verbose:
            print("[INFO] Hide.mn: Acquired browser lock.")
        
        main_window = sb.driver.current_window_handle
        sb.open_new_tab()
        new_tab = sb.driver.window_handles[-1]
        sb.switch_to_window(new_tab)
        
        try:
            offset = 0
            while True:
                url = URL_TEMPLATE.format(offset=offset)
                if verbose:
                    print(f"[INFO] Hide.mn: Navigating to page with offset {offset}...")
                
                sb.open(url)

                try:
                    time.sleep(0.5)
                    sb.uc_gui_handle_captcha()
                    sb.wait_for_element_present(selector='.table_block > table:nth-child(1)', timeout=15)
                except Exception as e:
                    if verbose:
                        print(f"[DEBUG] Hide.mn: Initial exception during CAPTCHA/table wait: {e}")
                    if not sb.is_element_present(selector='.table_block > table:nth-child(1)'):
                        if verbose:
                            print("[ERROR] Hide.mn: Failed to solve CAPTCHA or find table. Aborting.")
                        break

                page_content = sb.get_page_source()
                if "No proxies found" in page_content:
                    if verbose: print(f"[INFO] Hide.mn: Page reports no more proxies.")
                    break

                newly_found = extract_proxies_from_content(page_content, verbose=False)
                if not newly_found and offset > 0:
                    if verbose: print(f"[INFO]   ... No proxies found on this page. Assuming end of list.")
                    break
                    
                initial_count = len(all_proxies)
                all_proxies.update(newly_found)
                
                if verbose:
                    print(f"[INFO]   ... Hide.mn: Found {len(newly_found)} proxies. Total unique: {len(all_proxies)}.")

                if len(all_proxies) == initial_count and offset > 0:
                    if verbose: print("[INFO]   ... Hide.mn: No new unique proxies found. Stopping.")
                    break
                
                offset += 64
                time.sleep(DELAY_SECONDS)
        except Exception as e:
            if verbose:
                print(f"[ERROR] An exception occurred in Hide.mn scraper: {e}")
        finally:
            if new_tab in sb.driver.window_handles and len(sb.driver.window_handles) > 1:
                sb.switch_to_window(new_tab)
                sb.driver.close()
            if main_window in sb.driver.window_handles:
                sb.switch_to_window(main_window)
            if verbose:
                print("[INFO] Hide.mn: Released browser lock.")

    if verbose:
        print(f"[INFO] Hide.mn: Finished. Found a total of {len(all_proxies)} unique proxies.")
    
    return sorted(list(all_proxies))