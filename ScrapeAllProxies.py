import sys
import json
import argparse
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
from scrapers.spysone_scraper import scrape_from_spysone
from automation_scrapers.openproxylist_scraper import scrape_from_openproxylist


# --- Configuration ---
SITES_FILE = 'sites-to-get-proxies-from.txt'
OUTPUT_FILE = 'scraped-proxies.txt'
# MAX_WORKERS is now controlled via CLI arguments.

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
    Parses the sites file, which can contain a URL and optional JSON for payload and headers.
    """
    scrape_targets = []
    with open(filename, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'): continue
            parts = line.split('|', 2)
            url = parts[0].strip()
            payload = None
            headers = None
            if len(parts) > 1 and parts[1].strip():
                try: payload = json.loads(parts[1].strip())
                except json.JSONDecodeError: print(f"[WARN] Invalid JSON in payload for URL: {url}. Skipping.")
            if len(parts) > 2 and parts[2].strip():
                try: headers = json.loads(parts[2].strip())
                except json.JSONDecodeError: print(f"[WARN] Invalid JSON in headers for URL: {url}. Skipping.")
            scrape_targets.append((url, payload, headers))
    return scrape_targets

def main():
    """
    Main function to run all scrapers concurrently, combine results, and save them.
    """
    parser = argparse.ArgumentParser(description="A powerful, multi-source proxy scraper.")
    parser.add_argument('--threads', type=int, default=50, help="Default number of threads for scrapers.")
    parser.add_argument('--solana-threads', type=int, default=3, help="Dedicated (lower) thread count for automation scrapers.")
    parser.add_argument('--remove-dead-links', action='store_true', help="Removes URLs from the sites file that return no proxies.")
    args = parser.parse_args()

    # --- MODIFIED: Identify special case scrapers that need a dedicated thread count ---
    # We use the automation scraper as the stand-in for the "solana" scraper.
    SPECIAL_CASE_SCRAPER_NAMES = ['OpenProxyList']
    
    # A dictionary to hold the functions to run
    all_scraper_tasks = {
        # 'ProxyScrape API': fetch_from_api,
        # 'ProxyDB': scrape_all_from_proxydb,
        # 'Geonode API': scrape_from_geonode_api,
        # 'CheckerProxy Archive': scrape_checkerproxy_archive,
        # 'ProxyList.org': scrape_from_proxylistorg,
        # 'XSEO.in': lambda: scrape_from_xseo(True),
        # 'GoLogin/Geoxy API': lambda: scrape_from_gologin_api(True),
        # 'OpenProxyList': lambda: scrape_from_openproxylist(True),
    }

     # Prepare the general scraper task
    try:
        scrape_targets = parse_sites_file(SITES_FILE)
        if scrape_targets:
            def general_scraper_task():
                # Pass the main threads argument to the general scraper
                return scrape_proxies(scrape_targets, verbose=True, max_workers=args.threads)
            all_scraper_tasks[f'Websites ({SITES_FILE})'] = general_scraper_task
        else:
            print(f"[WARN] The URL file '{SITES_FILE}' is empty. Skipping generic website scraping.")
    except FileNotFoundError:
        print(f"[ERROR] The file '{SITES_FILE}' was not found. Skipping generic website scraping.")
    
    results = {}
    
    # --- MODIFIED: Split tasks into normal, special, and general ---
    special_case_tasks = {name: func for name, func in all_scraper_tasks.items() if name in SPECIAL_CASE_SCRAPER_NAMES}
    normal_dedicated_tasks = {name: func for name, func in all_scraper_tasks.items() if name not in SPECIAL_CASE_SCRAPER_NAMES and not name.startswith("Websites")}
    general_task = all_scraper_tasks.get(f'Websites ({SITES_FILE})')

    # --- Run scraper tasks with their respective thread counts ---
    if special_case_tasks:
        print(f"--- Starting {len(special_case_tasks)} special-case scraper(s) with {args.solana_threads} threads ---")
        with ThreadPoolExecutor(max_workers=args.solana_threads) as executor:
            future_to_scraper = {executor.submit(func): name for name, func in special_case_tasks.items()}
            for future in as_completed(future_to_scraper):
                name = future_to_scraper[future]
                try: results[name] = future.result()
                except Exception as e: results[name] = []; print(f"[ERROR] Scraper '{name}' failed: {e}")
                print(f"[COMPLETED] '{name}' finished, found {len(results[name])} proxies.")

    if normal_dedicated_tasks:
        print(f"--- Starting {len(normal_dedicated_tasks)} dedicated scraper(s) with {args.threads} threads ---")
        with ThreadPoolExecutor(max_workers=args.threads) as executor:
            future_to_scraper = {executor.submit(func): name for name, func in normal_dedicated_tasks.items()}
            for future in as_completed(future_to_scraper):
                name = future_to_scraper[future]
                try: results[name] = future.result()
                except Exception as e: results[name] = []; print(f"[ERROR] Scraper '{name}' failed: {e}")
                print(f"[COMPLETED] '{name}' finished, found {len(results[name])} proxies.")
    
    successful_general_urls = []
    if general_task:
        name = f'Websites ({SITES_FILE})'
        print(f"--- [RUNNING] '{name}' with {args.threads} threads ---")
        try:
            proxies_found, successful_general_urls = general_task()
            results[name] = proxies_found
            print(f"[COMPLETED] '{name}' finished, found {len(results[name])} proxies.")
        except Exception as e:
            print(f"[ERROR] Scraper '{name}' failed: {e}")
            results[name] = []

    print("\n--- Combining and processing all results ---")
    combined_proxies = []
    for proxy_list in results.values(): combined_proxies.extend(proxy_list)
    final_proxies = sorted(list(set(p for p in combined_proxies if p and p.strip())))
    
    print("\n--- Summary ---")
    for name in sorted(results.keys()): print(f"Found {len(results.get(name, []))} proxies from {name}.")
    print(f"\nTotal unique proxies: {len(final_proxies)}")

    if final_proxies: save_proxies_to_file(final_proxies, OUTPUT_FILE)
    else: print("\nCould not find any proxies from any source.")

    if args.remove_dead_links:
        print(f"\n[INFO] --remove-dead-links is active. Updating '{SITES_FILE}'...")
        try:
            lines_to_keep = []
            with open(SITES_FILE, 'r', encoding='utf-8') as f:
                for line in f:
                    stripped_line = line.strip()
                    if not stripped_line or stripped_line.startswith('#'):
                        lines_to_keep.append(line)
                        continue
                    url_part = stripped_line.split('|')[0].strip()
                    if url_part in successful_general_urls: lines_to_keep.append(line)
            with open(SITES_FILE, 'w', encoding='utf-8') as f: f.writelines(lines_to_keep)
            print(f"[SUCCESS] Successfully updated '{SITES_FILE}'.")
        except Exception as e:
            print(f"[ERROR] Failed to update '{SITES_FILE}': {e}")

if __name__ == "__main__":
    main()