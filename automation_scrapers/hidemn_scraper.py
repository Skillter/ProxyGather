import logging
import time
from typing import List

from helper.selenium_controller import pass_cloudflare_challenge
from scrapers.proxy_scraper import extract_proxies_from_content

URL_TEMPLATE = "https://hide.mn/en/proxy-list/?start={offset}"
DELAY_SECONDS = 2.0

def scrape_from_hidemn(sb, verbose: bool = True) -> List[str]:
    """
    Scrapes hide.mn, which uses Cloudflare's Turnstile.
    This scraper uses a shared SeleniumBase SB() instance in UC Mode.
    """
    if verbose:
        print("[RUNNING] 'Hide.mn' automation scraper has started (using SeleniumBase).")
    
    all_proxies = set()
    offset = 0
    
    while True:
        url = URL_TEMPLATE.format(offset=offset)
        if verbose:
            print(f"[INFO] Hide.mn: Navigating to page with offset {offset}...")
        
        sb.uc_open_with_reconnect(url, 4)


        if verbose:
            sb.set_messenger_theme(theme="flat", location="top_center")

        try:
            if verbose:
                sb.post_message("Checking for Cloudflare challenge...")
            
            # sb.uc_gui_handle_captcha()
            challenge_passed = pass_cloudflare_challenge(sb)

            if challenge_passed:
                logging.info(f"Successfully landed on page: {sb.get_title()}")
                sb.post_message("Cloudflare Challenge Bypassed!", duration=3)
            else:
                logging.error("Could not complete the main task.")
                sb.fail("Could not bypass the Cloudflare challenge.")
                    
            ##########


            sb.wait_for_element('table.proxy__t', timeout=10)
            if verbose:
                sb.post_message("Challenge passed or not present.", duration=2)
        except Exception:
            if verbose:
                sb.post_message("Could not bypass challenge or find table. Stopping.", duration=3)
            break

        page_content = sb.get_page_source()
        
        if "No proxies found" in page_content:
            if verbose:
                print(f"[INFO] Hide.mn: Page reports no more proxies. Stopping scrape.")
            break

        newly_found = extract_proxies_from_content(page_content, verbose=False)
        
        if not newly_found:
            if verbose:
                print(f"[INFO]   ... No proxies found on this page. Assuming end of list.")
            break
            
        initial_count = len(all_proxies)
        all_proxies.update(newly_found)
        
        if verbose:
            print(f"[INFO]   ... Found {len(newly_found)} proxies on this page. Total unique: {len(all_proxies)}.")

        if len(all_proxies) == initial_count and offset > 0:
            if verbose:
                print("[INFO]   ... No new unique proxies found. Stopping to prevent infinite loop.")
            break
        
        offset += 64
        time.sleep(DELAY_SECONDS)

    if verbose:
        print(f"[INFO] Hide.mn: Finished. Found a total of {len(all_proxies)} unique proxies.")
    
    return sorted(list(all_proxies))