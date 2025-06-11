import sys
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Union, Tuple

# Import from all our library packages
from scrapers.proxy_scraper import scrape_proxies
from scrapers.proxyscrape_api_fetcher import fetch_from_api
from scrapers.proxydb_scraper import scrape_all_from_proxydb
from scrapers.geonode_scraper import scrape_from_geonode_api
from scrapers.checkerproxy_scraper import scrape_checkerproxy_archive
from scrapers.proxylistorg_scraper import scrape_from_proxylistorg
from scrapers.xseo_scraper import scrape_from_xseo


# from scrapers.spysone_scraper import scrape_from_spysone # keep this comment

# --- Configuration ---
SITES_FILE = 'sites-to-get-proxies-from.txt'
OUTPUT_FILE = 'scraped-proxies.txt'
MAX_WORKERS = 8

def save_proxies_to_file(proxies: list, filename: str):
    """Saves a list of proxies to a text file, one per line, using UTF-8 encoding."""
    try:
        # --- MODIFIED: Added encoding='utf-8' for consistent file writing ---
        with open(filename, 'w', encoding='utf-8') as f:
            for proxy in proxies:
                f.write(proxy + '\n')
        print(f"\n[SUCCESS] Successfully saved {len(proxies)} unique proxies to '{filename}'")
    except IOError as e:
        print(f"\n[ERROR] Could not write to file '{filename}': {e}")

def parse_sites_file(filename: str) -> List[Tuple[str, Union[Dict, None]]]:
    """
    Parses the sites file, which can contain a URL and an optional JSON payload
    separated by a pipe '|'

    Returns:
        A list of tuples, where each tuple is (url, payload_or_none).
    """
    scrape_targets = []
    # --- MODIFIED: Added encoding='utf-8' to handle special characters in the file ---
    with open(filename, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            parts = line.split('|', 1)
            url = parts[0].strip()
            payload = None

            if len(parts) > 1:
                try:
                    payload = json.loads(parts[1].strip())
                except json.JSONDecodeError:
                    print(f"[WARN] Invalid JSON payload for URL: {url}. Skipping payload.")
                    # Keep the URL for a GET request attempt
            
            scrape_targets.append((url, payload))
    return scrape_targets

def main():
    """
    Main function to run all scrapers concurrently, combine results, and save them.
    """
    # A dictionary to hold the functions to run
    scraper_tasks = {
        # 'ProxyScrape API': fetch_from_api,
        # 'ProxyDB': scrape_all_from_proxydb,
        # 'Geonode API': scrape_from_geonode_api,
        # 'CheckerProxy Archive': scrape_checkerproxy_archive,
        'ProxyList.org': scrape_from_proxylistorg,
        'XSEO.in': lambda: scrape_from_xseo(True),
    }

    # --- Prepare the website scraping task separately ---
    # try:
    #     scrape_targets = parse_sites_file(SITES_FILE)
    #     if not scrape_targets:
    #          print(f"[WARN] The URL file '{SITES_FILE}' is empty or contains no valid targets. Skipping generic website scraping.")
    #     else:
    #          # Add the website scraper to the tasks if targets are present.
    #          scraper_tasks[f'Websites ({SITES_FILE})'] = lambda: scrape_proxies(scrape_targets, verbose=True)
    # except FileNotFoundError:
    #     print(f"[ERROR] The file '{SITES_FILE}' was not found. Skipping generic website scraping.")
    
    # This dictionary will hold the results from each scraper
    results = {}

    print(f"--- Starting {len(scraper_tasks)} scrapers concurrently (max workers: {MAX_WORKERS}) ---")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_scraper = {executor.submit(func): name for name, func in scraper_tasks.items()}
        
        for future in as_completed(future_to_scraper):
            scraper_name = future_to_scraper[future]
            try:
                proxies_found = future.result()
                results[scraper_name] = proxies_found
                print(f"[COMPLETED] '{scraper_name}' finished, found {len(proxies_found)} proxies.")
            except Exception as e:
                print(f"[ERROR] Scraper '{scraper_name}' failed with an exception: {e}")
                results[scraper_name] = []

    # --- Combine, Deduplicate, and Clean all results ---
    print("\n--- Combining and processing all results ---")
    
    combined_proxies = []
    for proxy_list in results.values():
        combined_proxies.extend(proxy_list)
    
    non_empty_proxies = [p for p in combined_proxies if p and p.strip()]
    unique_proxies = set(non_empty_proxies)
    final_proxies = sorted(list(unique_proxies))
    
    print("\n--- Summary ---")
    for name in sorted(results.keys()):
        print(f"Found {len(results.get(name, []))} proxies from {name}.")
    
    print(f"\nTotal unique proxies after cleaning and deduplication: {len(final_proxies)}")

    # --- Save the final list ---
    if not final_proxies:
        print("\nCould not find any proxies from any source.")
    else:
        save_proxies_to_file(final_proxies, OUTPUT_FILE)


if __name__ == "__main__":
    main()