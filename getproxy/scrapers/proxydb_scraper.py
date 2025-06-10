from typing import List
# The '.' is crucial for a relative import. It tells Python to
# look for proxy_scraper in the same package (the scraper_library folder).
from .proxy_scraper import scrape_proxies

def scrape_all_from_proxydb(verbose: bool = False) -> List[str]:
    """
    Scrapes all pages from proxydb.net by iterating through offsets.

    This function repeatedly calls the generic scrape_proxies function,
    incrementing the page offset by 30 each time, until no new proxies
    are found.

    Args:
        verbose: If True, prints detailed status messages for each page.

    Returns:
        A list of all unique proxies found across all pages.
    """
    # Using a set to automatically handle duplicates found across different pages
    all_found_proxies = set()
    offset = 0
    page_num = 1
    
    while True:
        # Construct the URL for the current page
        url = f"http://proxydb.net/?offset={offset}&sort_column_id=response_time_avg"
        
        if verbose:
            print(f"[INFO] Scraping ProxyDB page {page_num} (offset={offset})...")
        
        # We call the generic scraper with just this one URL.
        # We set its internal verbosity to False to avoid repetitive log lines.
        newly_scraped = scrape_proxies([url], verbose=False)
        
        # If the scraper returns nothing, we've reached the end.
        if not newly_scraped:
            if verbose:
                print(f"[INFO]   ... No proxies found on page {page_num}. Assuming end of list.")
            break # Exit the while loop
            
        # Check how many *truly* new proxies we found to avoid looping forever
        # on a page that keeps returning the same (already seen) proxies.
        initial_count = len(all_found_proxies)
        all_found_proxies.update(newly_scraped)
        
        if verbose:
            print(f"[INFO]   ... Found {len(newly_scraped)} proxies. Total unique: {len(all_found_proxies)}.")

        # If the set size didn't increase, we are done.
        if len(all_found_proxies) == initial_count:
             if verbose:
                print("[INFO]   ... No new unique proxies found. Stopping.")
             break
            
        # Prepare for the next iteration
        offset += 30
        page_num += 1
        
    # Return a sorted list for consistent output
    return sorted(list(all_found_proxies))