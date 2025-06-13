import time
import random
from typing import List
from .proxy_scraper import scrape_proxies

# --- ADDED: Configuration for polite scraping ---
# Base delay in seconds to wait between requests to the same site
BASE_DELAY_SECONDS = 1
# A random additional delay to make the scraping pattern less predictable
# We will add a random float between 0.5 and 1.5 seconds to the base delay.
RANDOM_DELAY_RANGE = (0.0, 0.0)

def scrape_all_from_proxydb(verbose: bool = False) -> List[str]:
    """
    Scrapes all pages from proxydb.net by iterating through offsets,
    with a polite delay between each page request to avoid rate-limiting.

    Args:
        verbose: If True, prints detailed status messages for each page.

    Returns:
        A list of all unique proxies found across all pages.
    """
    all_found_proxies = set()
    offset = 0
    page_num = 1
    
    while True:
        url = f"http://proxydb.net/?offset={offset}&sort_column_id=response_time_avg"
        
        if verbose:
            print(f"[INFO] Scraping ProxyDB page {page_num} (offset={offset})...")
        
        newly_scraped = scrape_proxies([url], verbose=False)
        
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