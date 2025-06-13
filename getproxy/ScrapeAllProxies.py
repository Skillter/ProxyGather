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
from scrapers.gologin_scraper import scrape_from_gologin_api
from automation_scrapers.openproxylist_scraper import scrape_from_openproxylist


# --- Configuration ---
SITES_FILE = 'sites-to-get-proxies-from.txt'
OUTPUT_FILE = 'scraped-proxies.txt'
MAX_WORKERS = 8

def save_proxies_to_file(proxies: list, filename: str):
    """Saves a list of proxies to a text file, one per line, using UTF-8 encoding."""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            for proxy in proxies:
                f.write(proxy + '\n')
        print(f"\n[SUCCESS] Successfully saved {len(proxies)} unique proxies to '{filename}'")
    except IOError as e:
        print(f"\n[ERROR] Could not write to file '{filename}': {e}")

def parse_sites_file(filename: str) -> List[Tuple[str, Union[Dict, None], Union[Dict, None]]]:
    """
    Parses the sites file, which can contain a URL and optional JSON for payload and headers,
    separated by pipes '|'. Format: URL|PAYLOAD_JSON|HEADERS_JSON

    Returns:
        A list of tuples, where each is (url, payload_or_none, headers_or_none).
    """
    scrape_targets = []
    with open(filename, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            parts = line.split('|', 2)
            url = parts[0].strip()
            payload = None
            headers = None

            # Safely process payload if it exists
            if len(parts) > 1 and parts[1].strip():
                try:
                    payload = json.loads(parts[1].strip())
                except json.JSONDecodeError:
                    print(f"[WARN] Invalid JSON in payload for URL: {url}. Skipping payload.")
            
            # Safely process headers if they exist
            if len(parts) > 2 and parts[2].strip():
                try:
                    headers = json.loads(parts[2].strip())
                except json.JSONDecodeError:
                    print(f"[WARN] Invalid JSON in headers for URL: {url}. Skipping headers.")
            
            scrape_targets.append((url, payload, headers))
    return scrape_targets

def main():
    """
    Main function to run all scrapers concurrently, combine results, and save them.
    """
    # A dictionary to hold the functions to run
    scraper_tasks = {
        'ProxyScrape API': fetch_from_api,
        # 'ProxyDB': scrape_all_from_proxydb,
        # 'Geonode API': scrape_from_geonode_api,
        # 'CheckerProxy Archive': scrape_checkerproxy_archive,
        # 'ProxyList.org': scrape_from_proxylistorg,
        # 'XSEO.in': lambda: scrape_from_xseo(True),
        # 'GoLogin/Geoxy API': lambda: scrape_from_gologin_api(True),
        # 'OpenProxyList': lambda: scrape_from_openproxylist(True),
    }

    # --- Prepare the website scraping task separately ---
    # try:
    #     scrape_targets = parse_sites_file(SITES_FILE)
    #     if not scrape_targets:
    #          print(f"[WARN] The URL file '{SITES_FILE}' is empty or contains no valid targets. Skipping generic website scraping.")
    #     else:
    #          # Add the powerful generic scraper to the tasks list.
    #          # It now handles its own concurrency and pagination.
    #          scraper_tasks[f'Websites ({SITES_FILE})'] = lambda: scrape_proxies(scrape_targets, verbose=True, max_workers=MAX_WORKERS)
    # except FileNotFoundError:
    #     print(f"[ERROR] The file '{SITES_FILE}' was not found. Skipping generic website scraping.")
    
    # This dictionary will hold the results from each scraper
    results = {}

    # --- MODIFIED: Concurrency for *dedicated* scrapers is handled here.
    # The generic scraper handles its own internal concurrency.
    dedicated_scrapers = {name: func for name, func in scraper_tasks.items() if not name.startswith("Websites")}
    
    print(f"--- Starting {len(dedicated_scrapers)} dedicated scrapers concurrently (max workers: {MAX_WORKERS}) ---")
    if f'Websites ({SITES_FILE})' in scraper_tasks:
        print(f"--- The General Website Scraper will run separately and manage its own tasks. ---")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_scraper = {executor.submit(func): name for name, func in dedicated_scrapers.items()}
        
        for future in as_completed(future_to_scraper):
            scraper_name = future_to_scraper[future]
            try:
                proxies_found = future.result()
                results[scraper_name] = proxies_found
                print(f"[COMPLETED] '{scraper_name}' finished, found {len(proxies_found)} proxies.")
            except Exception as e:
                print(f"[ERROR] Scraper '{scraper_name}' failed with an exception: {e}")
                results[scraper_name] = []

    # Run the general scraper task if it exists
    if f'Websites ({SITES_FILE})' in scraper_tasks:
        try:
            name = f'Websites ({SITES_FILE})'
            print(f"--- [RUNNING] '{name}' ---")
            proxies_found = scraper_tasks[name]()
            results[name] = proxies_found
            print(f"[COMPLETED] '{name}' finished, found {len(proxies_found)} proxies.")
        except Exception as e:
            print(f"[ERROR] Scraper '{name}' failed with an exception: {e}")
            results[name] = []


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