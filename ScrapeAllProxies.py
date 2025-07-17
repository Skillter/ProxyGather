import os
import sys
import json
import argparse
import re
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from typing import List, Dict, Union, Tuple
from seleniumbase import SB

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

SITES_FILE = 'sites-to-get-proxies-from.txt'
DEFAULT_OUTPUT_FILE = 'scraped-proxies.txt'

INVALID_IP_REGEX = re.compile(
    r"^(10\.|127\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[01])\.|169\.254\.|0\.|2(2[4-9]|3[0-9])\.|2(4[0-9]|5[0-5])\.)"
)

def save_proxies_to_file(proxies: list, filename: str):
    try:
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

def run_automation_task(scraper_name: str, scraper_func, verbose_flag: bool, is_headful: bool):
    """
    A wrapper to run a single automation scraper in its own browser instance,
    with configurable headful/headless mode.
    """
    with SB(uc=True, headed=is_headful, headless2=(not is_headful), disable_csp=True) as sb:
        return scraper_func(sb, verbose=verbose_flag)

def main():
    parser = argparse.ArgumentParser(description="A powerful, multi-source proxy scraper.")
    parser.add_argument('--output', default=DEFAULT_OUTPUT_FILE, help=f"The output file for scraped proxies. Defaults to '{DEFAULT_OUTPUT_FILE}'.")
    parser.add_argument('--threads', type=int, default=50, help="Number of threads for regular web scrapers. Default: 50")
    parser.add_argument('--automation-threads', type=int, default=3, help="Max concurrent headless browser automation scrapers (processes). Default: 3")
    parser.add_argument('--remove-dead-links', action='store_true', help="Removes URLs from the sites file that return no proxies.")
    parser.add_argument('-v', '--verbose', action='store_true', help="Enable detailed logging for each scraper.")
    
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--only', nargs='*', help="Only run the specified scrapers (case-insensitive). Pass with no values to see choices.")
    group.add_argument('--exclude', '--except', nargs='*', help="Exclude scrapers from the run (case-insensitive). Pass with no values to see choices.")
    
    args = parser.parse_args()

    all_scraper_tasks = {
        'ProxyScrape': fetch_from_api,
        'ProxyDB': scrape_all_from_proxydb,
        'Geonode': scrape_from_geonode_api,
        'CheckerProxy': scrape_checkerproxy_archive,
        'ProxyList.org': scrape_from_proxylistorg,
        'XSEO': scrape_from_xseo,
        'GoLogin': scrape_from_gologin_api,
        'ProxyHttp': scrape_from_proxyhttp,
        'Spys.one': scrape_from_spysone,
        'OpenProxyList': scrape_from_openproxylist,
        'Webshare': scrape_from_webshare,
        'Hide.mn': scrape_from_hidemn,
    }
    
    AUTOMATION_SCRAPER_NAMES = ['OpenProxyList', 'Webshare', 'Hide.mn', 'Spys.one']
    HEADFUL_SCRAPERS = ['Hide.mn', 'Webshare']
    general_scraper_name = 'Websites'
    all_scraper_names = sorted(list(all_scraper_tasks.keys()) + [general_scraper_name])

    if (args.only is not None and not args.only) or (args.exclude is not None and not args.exclude):
        print("Available scraper sources are:")
        print(f"  {general_scraper_name} - Websites from {SITES_FILE}")
        for name in all_scraper_names:
            if name != general_scraper_name:
                print(f"  {name}")
        sys.exit(0)

    tasks_to_run = all_scraper_tasks.copy()
    try:
        scrape_targets = parse_sites_file(SITES_FILE)
        if scrape_targets:
            tasks_to_run[general_scraper_name] = lambda verbose: scrape_proxies(scrape_targets, verbose=verbose, max_workers=args.threads)
    except FileNotFoundError:
        print(f"[WARN] '{SITES_FILE}' not found. '{general_scraper_name}' scraper is unavailable.")

    scraper_name_map = {name.lower(): name for name in list(tasks_to_run.keys())}
    def resolve_user_input(user_list):
        return {scraper_name_map[name.lower()] for name in user_list if name.lower() in scraper_name_map}

    if args.only:
        sources_to_run = resolve_user_input(args.only)
        tasks_to_run = {name: func for name, func in tasks_to_run.items() if name in sources_to_run}
        print(f"--- Running ONLY the following scrapers: {', '.join(tasks_to_run.keys())} ---")
    elif args.exclude:
        sources_to_exclude = resolve_user_input(args.exclude)
        tasks_to_run = {name: func for name, func in tasks_to_run.items() if name not in sources_to_exclude}
        print(f"--- EXCLUDING the following scrapers: {', '.join(sources_to_exclude)} ---")

    if not tasks_to_run:
        print("[ERROR] No scrapers selected to run. Exiting.")
        sys.exit(1)

    if sys.platform == "linux" and not os.environ.get('DISPLAY'):
        print("[INFO] Linux/WSL detected. Checking for xvfb-run...")
        if shutil.which("xvfb-run"):
            print("[INFO] xvfb-run found. Re-launching inside a virtual display...")
            command = [shutil.which("xvfb-run"), '--auto-servernum', sys.executable, *sys.argv]
            subprocess.run(command)
            sys.exit(0)
        else:
            print("\n[ERROR] xvfb-run is required for browser automation on headless Linux/WSL but is not installed.")
            print("Please install it: sudo apt-get update && sudo apt-get install -y xvfb")
            sys.exit(1)

    results = {}
    successful_general_urls = []
    
    automation_tasks = {name: func for name, func in tasks_to_run.items() if name in AUTOMATION_SCRAPER_NAMES}
    normal_tasks = {name: func for name, func in tasks_to_run.items() if name not in AUTOMATION_SCRAPER_NAMES}

    headful_automation_tasks = {name: func for name, func in automation_tasks.items() if name in HEADFUL_SCRAPERS}
    headless_automation_tasks = {name: func for name, func in automation_tasks.items() if name not in HEADFUL_SCRAPERS}

    all_futures = []
    future_to_scraper = {}

    # Use a list of executors to manage them easily
    executors = []

    if normal_tasks:
        print(f"--- Submitting {len(normal_tasks)} regular scraper(s) using a ThreadPool...")
        executor = ThreadPoolExecutor(max_workers=args.threads, thread_name_prefix='NormalScraper')
        executors.append(executor)
        for name, func in normal_tasks.items():
            future = executor.submit(func, args.verbose)
            future_to_scraper[future] = name
            all_futures.append(future)

    if headless_automation_tasks:
        print(f"--- Submitting {len(headless_automation_tasks)} headless automation scraper(s) using a ProcessPool...")
        executor = ProcessPoolExecutor(max_workers=args.automation_threads)
        executors.append(executor)
        for name, func in headless_automation_tasks.items():
            future = executor.submit(run_automation_task, name, func, args.verbose, is_headful=False)
            future_to_scraper[future] = name
            all_futures.append(future)

    if headful_automation_tasks:
        print(f"--- Submitting {len(headful_automation_tasks)} headful automation scraper(s) sequentially using a ProcessPool (1 worker)...")
        executor = ProcessPoolExecutor(max_workers=1)
        executors.append(executor)
        for name, func in headful_automation_tasks.items():
            future = executor.submit(run_automation_task, name, func, args.verbose, is_headful=True)
            future_to_scraper[future] = name
            all_futures.append(future)

    try:
        if all_futures:
            print("\n--- Waiting for all scrapers to complete... ---")
            for future in as_completed(all_futures):
                name = future_to_scraper.get(future, "Unknown")
                try:
                    result_data = future.result()
                    if name == general_scraper_name:
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
        for executor in executors:
            executor.shutdown(wait=True)

    print("\n--- Combining and processing all results ---")
    combined_proxies = {p for proxy_list in results.values() if proxy_list for p in proxy_list if p and p.strip()}
    final_proxies = sorted(list({p for p in combined_proxies if not INVALID_IP_REGEX.match(p)}))
    
    spam_count = len(combined_proxies) - len(final_proxies)
    if spam_count > 0:
        print(f"[INFO] Removed {spam_count} spam/invalid proxies from reserved IP ranges.")
        
    print("\n--- Summary ---")
    for name in sorted(results.keys()): print(f"Found {len(results.get(name, []))} proxies from {name}.")
    print(f"\nTotal unique & valid proxies: {len(final_proxies)}")

    if final_proxies:
        save_proxies_to_file(final_proxies, args.output)
    else:
        print("\nCould not find any proxies from any source.")

    if args.remove_dead_links and successful_general_urls:
        print(f"\n[INFO] Updating '{SITES_FILE}' to remove dead links...")
        try:
            lines_to_keep = []
            with open(SITES_FILE, 'r', encoding='utf-8') as f:
                for line in f:
                    stripped_line = line.strip()
                    if not stripped_line or stripped_line.startswith('#') or stripped_line.split('|')[0].strip() in successful_general_urls:
                        lines_to_keep.append(line)
            with open(SITES_FILE, 'w', encoding='utf-8') as f:
                f.writelines(lines_to_keep)
            print(f"[SUCCESS] Successfully updated '{SITES_FILE}'.")
        except Exception as e:
            print(f"[ERROR] Failed to update '{SITES_FILE}': {e}")

if __name__ == "__main__":
    main()