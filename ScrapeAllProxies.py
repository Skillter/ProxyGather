import os
import sys
import json
import argparse
import re
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
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
from scrapers.proxyhttp_scraper import scrape_from_proxyhttp
from automation_scrapers.spysone_scraper import scrape_from_spysone
from automation_scrapers.openproxylist_scraper import scrape_from_openproxylist
from automation_scrapers.hidemn_scraper import scrape_from_hidemn

SITES_FILE = 'sites-to-get-proxies-from.txt'
DEFAULT_OUTPUT_FILE = 'scraped-proxies.txt'
INDIVIDUAL_SCRAPER_TIMEOUT = 100
MAX_TOTAL_RUNTIME = 300

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

def run_automation_task(scraper_name: str, scraper_func, verbose_flag: bool, is_headful: bool, turnstile_delay: float = 0):
    """
    A wrapper to run a single automation scraper in its own browser instance,
    with a dedicated, temporary user profile to ensure isolation.
    """
    temp_dir = tempfile.mkdtemp()
    try:
        with SB(
            uc=True,
            headed=is_headful,
            headless2=(not is_headful),
            disable_csp=True,
            user_data_dir=temp_dir
        ) as sb:
            return scraper_func(sb, verbose=verbose_flag, turnstile_delay=turnstile_delay)
    except Exception as e:
        print(f"[ERROR] {scraper_name} scraper failed: {e}")
        return []
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

def pre_run_browser_setup():
    """
    Initializes and closes a browser instance to trigger the driver download
    and setup process once, before any concurrent tasks start.
    """
    print("[INFO] Performing browser driver pre-flight check...")
    try:
        with SB(uc=True, headless2=True) as sb:
            sb.open("about:blank")
            driver_executable_path = sb.driver.service.path
            drivers_folder_path = os.path.dirname(driver_executable_path)
            
            uc_driver_filename = "uc_driver.exe" if sys.platform == "win32" else "uc_driver"
            
            if os.path.exists(os.path.join(drivers_folder_path, uc_driver_filename)):
                print("[SUCCESS] Browser driver is ready.")
            else:
                print("[WARN] UC driver not found after initial check, but pre-flight check completed.")
    except Exception as e:
        print(f"[ERROR] A critical error occurred during browser pre-flight check: {e}")
        print("[INFO] The script will continue, but may face issues with concurrent browser startup.")


def show_legal_disclaimer(auto_accept=False):
    """Display legal disclaimer and get user confirmation."""
    print("\n" + "="*70)
    print("LEGAL COMPLIANCE NOTICE")
    print("="*70)
    print("\nWARNING: Scraping websites may violate their Terms of Service or local")
    print("laws. By continuing in this mode, you acknowledge that:")
    print("")
    print("  - You are responsible for ensuring compliance with all applicable laws")
    print("  - You are responsible for respecting scraped websites' Terms of Service")
    print("  - This mode may bypass anti-bot measures and ignore robots.txt")
    print("  - You assume all legal liability for your use of this tool")
    print("")
    print("Recommended: Use --compliant mode for legal compliance:")
    print("  python ScrapeAllProxies.py --compliant")
    print("")
    print("Compliant mode will:")
    print("  - Respect robots.txt directives")
    print("  - Skip sources that use anti-bot bypassing (Cloudflare Turnstile,")
    print("    JavaScript obfuscation decoding, browser automation)")
    print("  - Significantly reduce the number of scraped proxies")
    print("="*70)
    print("")

    if auto_accept:
        import time
        print("[INFO] Auto-accepting disclaimer (--yes flag provided). Proceeding in 2 seconds...")
        time.sleep(2)
        print("\n[INFO] Proceeding in aggressive mode. You are responsible for legal compliance.\n")
        return True

    while True:
        response = input("Type 'y' or 'yes' to accept and continue in aggressive mode: ").strip().lower()
        if response in ['y', 'yes']:
            print("\n[INFO] Proceeding in aggressive mode. You are responsible for legal compliance.\n")
            return True
        elif response in ['n', 'no']:
            print("\n[INFO] Operation cancelled. Use --compliant for legal compliance.")
            sys.exit(0)
        else:
            print("Invalid input. Please type 'y', 'yes', 'n', or 'no'.")

def main():
    parser = argparse.ArgumentParser(description="A powerful, multi-source proxy scraper.")
    parser.add_argument('--output', default=DEFAULT_OUTPUT_FILE, help=f"The output file for scraped proxies. Defaults to '{DEFAULT_OUTPUT_FILE}'.")
    parser.add_argument('--threads', type=int, default=50, help="Number of threads for regular web scrapers. Default: 50")
    parser.add_argument('--automation-threads', type=int, default=3, help="Max concurrent headless browser automation scrapers (processes). Default: 3")
    parser.add_argument('--turnstile-delay', type=float, default=0, help="Delay in seconds to wait for Turnstile to load on slow computers. Default: 0 (no delay)")
    parser.add_argument('--remove-dead-links', action='store_true', help="Removes URLs from the sites file that return no proxies.")
    parser.add_argument('-v', '--verbose', action='store_true', help="Enable detailed logging for each scraper.")
    parser.add_argument('--compliant', action='store_true', help="Run in compliant mode: respect robots.txt, skip automation scrapers and anti-bot logic.")
    parser.add_argument('-y', '--yes', action='store_true', help="Auto-accept legal disclaimer (shows warning, waits 2 seconds, then proceeds).")

    group = parser.add_mutually_exclusive_group()
    group.add_argument('--only', nargs='*', help="Only run the specified scrapers (case-insensitive). Pass with no values to see choices.")
    group.add_argument('--exclude', '--except', nargs='*', help="Exclude scrapers from the run (case-insensitive). Pass with no values to see choices.")

    args = parser.parse_args()

    if not args.compliant:
        show_legal_disclaimer(auto_accept=args.yes)

    all_scraper_tasks = {
        'ProxyScrape': fetch_from_api,
        'Geonode': scrape_from_geonode_api,
        'ProxyDB': lambda verbose: scrape_all_from_proxydb(verbose=verbose, compliant_mode=args.compliant),
        'CheckerProxy': scrape_checkerproxy_archive,
        'Spys.one': scrape_from_spysone,
        'OpenProxyList': scrape_from_openproxylist,
        'Hide.mn': scrape_from_hidemn,
        'XSEO': scrape_from_xseo,
        'GoLogin': scrape_from_gologin_api,
        'ProxyList.org': scrape_from_proxylistorg,
        'ProxyHttp': scrape_from_proxyhttp,
    }
    
    AUTOMATION_SCRAPER_NAMES = ['OpenProxyList', 'Hide.mn', 'Spys.one']
    ANTI_BOT_BYPASS_SCRAPERS = ['OpenProxyList', 'Hide.mn', 'Spys.one', 'XSEO']
    HEADFUL_SCRAPERS = ['Hide.mn', 'Spys.one']
    general_scraper_name = 'Websites'
    all_scraper_names = sorted(list(all_scraper_tasks.keys()) + [general_scraper_name])

    if args.compliant:
        print("[INFO] Running in COMPLIANT mode - respecting robots.txt and skipping anti-bot bypass scrapers")

    if (args.only is not None and not args.only) or (args.exclude is not None and not args.exclude):
        print("Available scraper sources are:")
        print(f"  {general_scraper_name} - Websites from {SITES_FILE}")
        for name in all_scraper_names:
            if name != general_scraper_name:
                automation_marker = " (SKIPPED in --compliant mode)" if name in ANTI_BOT_BYPASS_SCRAPERS and args.compliant else ""
                print(f"  {name}{automation_marker}")
        sys.exit(0)

    tasks_to_run = all_scraper_tasks.copy()

    if args.compliant:
        for scraper_name in ANTI_BOT_BYPASS_SCRAPERS:
            if scraper_name in tasks_to_run:
                del tasks_to_run[scraper_name]
                if args.verbose:
                    print(f"[INFO] Skipping '{scraper_name}' in compliant mode (uses anti-bot circumvention)")

    try:
        scrape_targets = parse_sites_file(SITES_FILE)
        if scrape_targets:
            tasks_to_run[general_scraper_name] = lambda verbose: scrape_proxies(scrape_targets, verbose=verbose, max_workers=args.threads, respect_robots_txt=args.compliant)
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

    automation_tasks_present = any(name in tasks_to_run for name in AUTOMATION_SCRAPER_NAMES)
    headful_tasks_present = any(name in tasks_to_run for name in HEADFUL_SCRAPERS)

    if headful_tasks_present and sys.platform == "linux" and not os.environ.get('DISPLAY'):
        print("[INFO] Linux/WSL detected. Checking for xvfb-run...")
        if shutil.which("xvfb-run"):
            print("[INFO] xvfb-run found. Re-launching inside a virtual display...")
            command = [shutil.which("xvfb-run"), '--auto-servernum', sys.executable, *sys.argv]
            subprocess.run(command)
            sys.exit(0)
        else:
            print("\n[ERROR] xvfb-run is required for headful browser automation on headless Linux/WSL but is not installed.")
            print("Please install it: sudo apt-get update && sudo apt-get install -y xvfb")
            sys.exit(1)
    
    if automation_tasks_present:
        pre_run_browser_setup()

    results = {}
    successful_general_urls = []
    
    automation_tasks = {name: func for name, func in tasks_to_run.items() if name in AUTOMATION_SCRAPER_NAMES}
    normal_tasks = {name: func for name, func in tasks_to_run.items() if name not in AUTOMATION_SCRAPER_NAMES}

    headful_automation_tasks = {name: func for name, func in automation_tasks.items() if name in HEADFUL_SCRAPERS}
    headless_automation_tasks = {name: func for name, func in automation_tasks.items() if name not in HEADFUL_SCRAPERS}

    all_futures = []
    future_to_scraper = {}

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
        print(f"--- Submitting {len(headless_automation_tasks)} headless automation scraper(s) using a ThreadPool...")
        executor = ThreadPoolExecutor(max_workers=args.automation_threads, thread_name_prefix='HeadlessAutomation')
        executors.append(executor)
        for name, func in headless_automation_tasks.items():
            future = executor.submit(run_automation_task, name, func, args.verbose, is_headful=False, turnstile_delay=args.turnstile_delay)
            future_to_scraper[future] = name
            all_futures.append(future)

    if headful_automation_tasks:
        print(f"--- Submitting {len(headful_automation_tasks)} headful automation scraper(s) sequentially using a ThreadPool (1 worker)...")
        executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='HeadfulAutomation')
        executors.append(executor)
        for name, func in headful_automation_tasks.items():
            future = executor.submit(run_automation_task, name, func, args.verbose, is_headful=True, turnstile_delay=args.turnstile_delay)
            future_to_scraper[future] = name
            all_futures.append(future)

    try:
        if all_futures:
            print("\n--- Waiting for all scrapers to complete... ---")
            for future in as_completed(all_futures):
                name = future_to_scraper.get(future, "Unknown")
                try:
                    result_data = future.result(timeout=INDIVIDUAL_SCRAPER_TIMEOUT)
                    if name == general_scraper_name:
                        proxies_found, urls = result_data
                        results[name] = proxies_found
                        successful_general_urls.extend(urls)
                    else:
                        results[name] = result_data
                    print(f"[COMPLETED] '{name}' finished, found {len(results.get(name, []))} proxies.")
                except TimeoutError:
                    results[name] = []
                    print(f"[TIMEOUT] Scraper '{name}' exceeded {INDIVIDUAL_SCRAPER_TIMEOUT}s timeout. Cancelling...")
                    future.cancel()
                except Exception as e:
                    results[name] = []
                    print(f"[ERROR] Scraper '{name}' failed: {e}")
    finally:
        for executor in executors:
            executor.shutdown(wait=True, cancel_futures=True)

        for future, name in future_to_scraper.items():
            if name not in results and future.done():
                try:
                    result_data = future.result(timeout=0)
                    if name == general_scraper_name:
                        proxies_found, urls = result_data
                        results[name] = proxies_found
                        successful_general_urls.extend(urls)
                    else:
                        results[name] = result_data
                    print(f"[RECOVERED] '{name}' finished after shutdown, found {len(results.get(name, []))} proxies.")
                except Exception as e:
                    results[name] = []
                    print(f"[ERROR] Could not recover results from '{name}': {e}")

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
    import sys
    try:
        main()
    finally:
        sys.exit(0)