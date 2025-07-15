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
        print("1")
        sb.open_new_tab()
        print("2")
        new_tab = sb.driver.window_handles[-1]
        print("3")
        sb.switch_to_window(new_tab)
        
        print("4")
        try:
            offset = 0
            while True:
                url = URL_TEMPLATE.format(offset=offset)
                print("5")
                if verbose:
                    print(f"[INFO] Hide.mn: Navigating to page with offset {offset}...")
                
                sb.open(url)

                print("6")
                try:
                    # Don't use sb.bring_to_front(), it results in an exception and table.proxy__t not being visible
                    print("7")
                    time.sleep(0.5)
                    sb.uc_gui_handle_captcha()
                    print("last before switch to tab")
                    # sb.switch_to_tab(new_tab)
                    print("8")
                    sb.wait_for_element_present(selector='.table_block > table:nth-child(1)', timeout=15)
                    print("9")
                except Exception:
                    print("Exception occured on the while trying to handle captcha")
                    if not sb.wait_for_element_present(selector='.table_block > table:nth-child(1)'):
                        print("[ERROR] Hide.mn: Failed to solve CAPTCHA or find table. Aborting.")
                        break

                page_content = sb.get_page_source()
                print("10")
                if "No proxies found" in page_content:
                    if verbose: print(f"[INFO] Hide.mn: Page reports no more proxies.")
                    break

                print("11")
                newly_found = extract_proxies_from_content(page_content, verbose=False)
                print("12")
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
            print(f"[ERROR] An exception occurred in Hide.mn scraper: {e}")
        finally:
            if len(sb.driver.window_handles) > 1:
                sb.switch_to_window(new_tab)
                sb.driver.close()
            sb.switch_to_window(main_window)
            if verbose:
                print("[INFO] Hide.mn: Released browser lock.")

    if verbose:
        print(f"[INFO] Hide.mn: Finished. Found a total of {len(all_proxies)} unique proxies.")
    
    return sorted(list(all_proxies))