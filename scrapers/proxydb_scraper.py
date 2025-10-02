import time
import random
from typing import List
from .proxy_scraper import scrape_proxies

BASE_DELAY_SECONDS = 1
RANDOM_DELAY_RANGE = (0.0, 0.0)

MAX_PAGES_COMPLIANT = 2
MAX_PAGES_AGGRESSIVE = 10

def scrape_all_from_proxydb(verbose: bool = False, compliant_mode: bool = False) -> List[str]:
    """
    Scrapes pages from proxydb.net by iterating through offsets,
    with a polite delay between each page request to avoid rate-limiting.

    Args:
        verbose: If True, prints detailed status messages for each page.
        compliant_mode: If True, limits scraping to MAX_PAGES_COMPLIANT pages.

    Returns:
        A list of all unique proxies found across all pages.
    """
    all_found_proxies = set()
    offset = 0
    page_num = 1
    max_pages = MAX_PAGES_COMPLIANT if compliant_mode else MAX_PAGES_AGGRESSIVE

    if verbose:
        mode_name = "compliant" if compliant_mode else "aggressive"
        print(f"[INFO] ProxyDB: Running in {mode_name} mode (max {max_pages} pages)")

    while page_num <= max_pages:
        url = f"http://proxydb.net/?offset={offset}&sort_column_id=response_time_avg"
        
        if verbose:
            print(f"[INFO] Scraping ProxyDB page {page_num} (offset={offset})...")
        
        # --- FIXED: Correctly unpack the tuple returned by scrape_proxies ---
        # scrape_proxies now returns (proxies, successful_urls), so we need to account for that.
        # We only care about the proxies here, so we can ignore the second value.
        newly_scraped, _ = scrape_proxies([(url, None, None)], verbose)
        
        if not newly_scraped:
            if verbose:
                print(f"[INFO]   ... No proxies found on page {page_num}. Assuming end of list.")
            break
            
        initial_count = len(all_found_proxies)
        all_found_proxies.update(newly_scraped)
        
        if verbose:
            print(f"[INFO]   ... Found {len(newly_scraped)} proxies. Total unique: {len(all_found_proxies)}.")

        if len(all_found_proxies) == initial_count:
             if verbose:
                print("[INFO]   ... No new unique proxies found. Stopping.")
             break
        
        # --- ADDED: Rate-limiting logic ---
        # Be a polite scraper: wait before hitting the next page to avoid being blocked.
        sleep_duration = BASE_DELAY_SECONDS + random.uniform(*RANDOM_DELAY_RANGE)
        if verbose:
            # Format the float to two decimal places for cleaner output
            print(f"[INFO] Waiting for {sleep_duration:.2f} seconds before next page...")
        time.sleep(sleep_duration)
        # --- END of added logic ---
            
        offset += 30
        page_num += 1
        
    return sorted(list(all_found_proxies))