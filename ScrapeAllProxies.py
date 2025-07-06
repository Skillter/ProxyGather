import os
import sys
import json
import argparse
import re
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
from scrapers.proxyhttp_scraper import scrape_from_proxyhttp
from automation_scrapers.openproxylist_scraper import scrape_from_openproxylist
from automation_scrapers.webshare_scraper import scrape_from_webshare
from automation_scrapers.hidemn_scraper import scrape_from_hidemn

# --- Configuration ---
SITES_FILE = 'sites-to-get-proxies-from.txt'
DEFAULT_OUTPUT_FILE = 'scraped-proxies.txt'

INVALID_IP_REGEX = re.compile(
    r"^(10\.|127\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[01])\.|169\.254\.|0\.|2(2[4-9]|3[0-9])\.|2(4[0-9]|5[0-5])\.)"
)

def save_proxies_to_file(proxies: list, filename: str):
    """Saves a list of proxies to a text file, creating the directory if it doesn't exist."""
    try:
        # this logic correctly handles creating directories like "proxies/"
        directory = os.path.dirname(filename)
        if directory and not os.path.exists(directory):
            print(f"[INFO] Creating output directory: {directory}")
            os.makedirs(directory)

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
    parser.add_argument('--output', default=DEFAULT_OUTPUT_FILE, help=f"The output file for scraped proxies. Defaults to '{DEFAULT_OUTPUT_FILE}'.")
    parser.add_argument('--threads', type=int, default=50, help="Number of threads for scrapers. Default: 50")
    parser.add_argument('--solana-threads', type=int, default=3, help="Dedicated (lower) thread count for automation scrapers. Default: 3")
    parser.add_argument('--remove-dead-links', action='store_true', help="Removes URLs from the sites file that return no proxies.")
    # i added the verbose argument here
    parser.add_argument('-v', '--verbose', action='store_true', help="Enable detailed logging for each scraper.")
    
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--only', nargs='*', help="Only run the specified scrapers (case-insensitive). Pass with no values to see choices.")
    group.add_argument('--exclude', '--except', nargs='*', help="Exclude scrapers from the run (case-insensitive). Pass with no values to see choices.")
    
    args = parser.parse_args()

    # we define the tasks after parsing args so we can pass the verbose flag
    all_scraper_tasks = {
        'ProxyScrape': lambda: fetch_from_api(verbose=args.verbose),
        'ProxyDB': lambda: scrape_all_from_proxydb(verbose=args.verbose),
        'Geonode': lambda: scrape_from_geonode_api(verbose=args.verbose),
        'CheckerProxy': lambda: scrape_checkerproxy_archive(verbose=args.verbose),
        'ProxyList.org': lambda: scrape_from_proxylistorg(verbose=args.verbose),
        'XSEO': lambda: scrape_from_xseo(verbose=args.verbose),
        'GoLogin': lambda: scrape_from_gologin_api(verbose=args.verbose),
        'ProxyHttp': lambda: scrape_from_proxyhttp(verbose=args.verbose),
        'OpenProxyList': lambda: scrape_from_openproxylist(verbose=args.verbose),
        'Webshare': lambda: scrape_from_webshare(verbose=args.verbose),
        # 'Hide.mn': lambda: scrape_from_hidemn(verbose=args.verbose), # NOT WORKING, uses turnstile
    }
    
    SPECIAL_CASE_SCRAPER_NAMES = [
        'OpenProxyList', 
        'Webshare', 
        # 'Hide.mn', # NOT WORKING, uses turnstile
    ]

    general_scraper_name = f'Websites'
    
    all_scraper_names = sorted(list(all_scraper_tasks.keys()) + [general_scraper_name])

    if (args.only is not None and not args.only) or (args.exclude is not None and not args.exclude):
        print("Available scraper sources are:")
        print(f"  {general_scraper_name} - The websites from {SITES_FILE} that do not require extra logic to scrape")
        print("Dedicated scrapers with implemented logic (Recommended):")
        for name in all_scraper_names:
            if (name == general_scraper_name) or (name in SPECIAL_CASE_SCRAPER_NAMES): 
                continue
            print(f"  {name}")
        print("Dedicated Solana scrapers that are heavier to run:")
        for name in SPECIAL_CASE_SCRAPER_NAMES:
            print(f"  {name}")
        sys.exit(0)

    tasks_to_run = all_scraper_tasks.copy()
    try:
        scrape_targets = parse_sites_file(SITES_FILE)
        if scrape_targets:
            def general_scraper_task():
                # make sure the general scraper also respects the verbose flag
                return scrape_proxies(scrape_targets, verbose=args.verbose, max_workers=args.threads)
            tasks_to_run[general_scraper_name] = general_scraper_task
    except FileNotFoundError:
        print(f"[WARN] The URL file '{SITES_FILE}' was not found. The '{general_scraper_name}' scraper will not be available.")

    scraper_name_map = {name.lower(): name for name in list(tasks_to_run.keys())}

    def resolve_user_input(user_list):
        resolved_names = set()
        for name in user_list:
            lower_name = name.lower()
            if lower_name in scraper_name_map:
                resolved_names.add(scraper_name_map[lower_name])
            else:
                print(f"[WARN] Unknown scraper source '{name}' will be ignored.")
        return resolved_names

    if args.only:
        sources_to_run = resolve_user_input(args.only)
        tasks_to_run = {name: func for name, func in tasks_to_run.items() if name in sources_to_run}
        print(f"--- Running ONLY the following scrapers: {', '.join(tasks_to_run.keys())} ---")
    elif args.exclude:
        sources_to_exclude = resolve_user_input(args.exclude)
        for name in sources_to_exclude:
            tasks_to_run.pop(name, None)
        print(f"--- EXCLUDING the following scrapers: {', '.join(sources_to_exclude)} ---")

    if not tasks_to_run:
        print("[ERROR] No scrapers selected to run. Exiting.")
        sys.exit(1)

    results = {}
    successful_general_urls = []
    
    special_case_tasks = {name: func for name, func in tasks_to_run.items() if name in SPECIAL_CASE_SCRAPER_NAMES}
    normal_tasks = {name: func for name, func in tasks_to_run.items() if name not in SPECIAL_CASE_SCRAPER_NAMES}

    special_executor = ThreadPoolExecutor(max_workers=args.solana_threads, thread_name_prefix='SolanaScraper')
    normal_executor = ThreadPoolExecutor(max_workers=args.threads, thread_name_prefix='NormalScraper')

    try:
        future_to_scraper = {}
        
        if special_case_tasks:
            print(f"\n--- Submitting {len(special_case_tasks)} special-case scraper(s) to a pool of {args.solana_threads} threads ---")
            for name, func in special_case_tasks.items():
                future = special_executor.submit(func)
                future_to_scraper[future] = name

        if normal_tasks:
            print(f"--- Submitting {len(normal_tasks)} normal scraper(s) to a pool of {args.threads} threads ---")
            for name, func in normal_tasks.items():
                future = normal_executor.submit(func)
                future_to_scraper[future] = name

        print("\n--- All scrapers submitted. Waiting for results... ---")

        for future in as_completed(future_to_scraper):
            name = future_to_scraper[future]
            try:
                result_data = future.result()
                if name.startswith('Websites'):
                    proxies_found, urls = result_data
                    results[name] = proxies_found
                    successful_general_urls.extend(urls)
                else:
                    results[name] = result_data
                
                print(f"[COMPLETED] '{name}' finished, found {len(results.get(name, []))} proxies.")
            except Exception as e:
                results[name] = []
                print(f"[ERROR] Scraper '{name}' failed: {e}")

    finally:
        special_executor.shutdown()
        normal_executor.shutdown()

    print("\n--- Combining and processing all results ---")
    combined_proxies = []
    for proxy_list in results.values():
        if proxy_list: combined_proxies.extend(proxy_list)
        
    unique_proxies_before_filter = set(p for p in combined_proxies if p and p.strip())
    
    final_proxies = {p for p in unique_proxies_before_filter if not INVALID_IP_REGEX.match(p)}
    
    spam_count = len(unique_proxies_before_filter) - len(final_proxies)
    if spam_count > 0:
        print(f"[INFO] Removed {spam_count} spam/invalid proxies from reserved IP ranges.")
        
    sorted_final_proxies = sorted(list(final_proxies))
    
    print("\n--- Summary ---")
    for name in sorted(results.keys()): print(f"Found {len(results.get(name, []))} proxies from {name}.")
    print(f"\nTotal unique & valid proxies: {len(sorted_final_proxies)}")

    if sorted_final_proxies:
        save_proxies_to_file(sorted_final_proxies, args.output)
    else:
        print("\nCould not find any proxies from any source.")

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