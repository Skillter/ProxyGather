import os
import sys
import json
import argparse
import re
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError, wait, FIRST_COMPLETED
from typing import List, Dict, Union, Tuple
from urllib.parse import urlparse
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
from scrapers.proxydocker_scraper import scrape_from_proxydocker
from scrapers.advancedname_scraper import scrape_from_advancedname
from scrapers.proxyservers_scraper import scrape_from_proxyservers
from scrapers.proxydaily_scraper import scrape_from_proxydaily
from scrapers.proxynova_scraper import scrape_from_proxynova
from scrapers.premproxy_scraper import scrape_from_premproxy
from automation_scrapers.spysone_scraper import scrape_from_spysone
from automation_scrapers.openproxylist_scraper import scrape_from_openproxylist
from automation_scrapers.hidemn_scraper import scrape_from_hidemn
from scrapers.source_discoverer import discover_urls_from_file
from helper.termination import termination_context, should_terminate, get_termination_handler

SITES_FILE = 'sites-to-get-proxies-from.txt'
SOURCES_FILE = 'sites-to-get-sources-from.txt'
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
            print(f"[INFO] Creating output directory: {directory}", flush=True)
            os.makedirs(directory)

        with open(filename, 'w', encoding='utf-8') as f:
            for proxy in proxies:
                f.write(proxy + '\n')
        print(f"[SUCCESS] Successfully saved {len(proxies)} unique proxies to '{filename}'", flush=True)
    except IOError as e:
        print(f"[ERROR] Could not write to file '{filename}': {e}", flush=True)

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
                except json.JSONDecodeError: print(f"[WARN] Invalid JSON in payload for URL: {url}. Skipping.", flush=True)
            if len(parts) > 2 and parts[2].strip():
                try: headers = json.loads(parts[2].strip())
                except json.JSONDecodeError: print(f"[WARN] Invalid JSON in headers for URL: {url}. Skipping.", flush=True)
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
        print(f"[ERROR] {scraper_name} scraper failed: {e}", flush=True)
        return []
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

def pre_run_browser_setup():
    """
    Initializes and closes a browser instance to trigger the driver download
    and setup process once, before any concurrent tasks start.
    """
    print("[INFO] Performing browser driver pre-flight check...", flush=True)
    try:
        with SB(uc=True, headless2=True) as sb:
            sb.open("about:blank")
            driver_executable_path = sb.driver.service.path
            drivers_folder_path = os.path.dirname(driver_executable_path)
            
            uc_driver_filename = "uc_driver.exe" if sys.platform == "win32" else "uc_driver"
            
            if os.path.exists(os.path.join(drivers_folder_path, uc_driver_filename)):
                print("[SUCCESS] Browser driver is ready.", flush=True)
            else:
                print("[WARN] UC driver not found after initial check, but pre-flight check completed.", flush=True)
    except Exception as e:
        print(f"[ERROR] A critical error occurred during browser pre-flight check: {e}", flush=True)
        print("[INFO] The script will continue, but may face issues with concurrent browser startup.", flush=True)


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
        print("[INFO] Auto-accepting disclaimer (--yes flag provided). Proceeding in 2 seconds...", flush=True)
        time.sleep(2)
        print("\n[INFO] Proceeding in aggressive mode. You are responsible for legal compliance.\n", flush=True)
        return True

    while True:
        response = input("Type 'y' or 'yes' to accept and continue in aggressive mode: ").strip().lower()
        if response in ['y', 'yes']:
            print("[INFO] Proceeding in aggressive mode. You are responsible for legal compliance.\n", flush=True)
            return True
        elif response in ['n', 'no']:
            print("[INFO] Operation cancelled. Use --compliant for legal compliance.", flush=True)
            sys.exit(0)
        else:
            print("Invalid input. Please type 'y', 'yes', 'n', or 'no'.", flush=True)

def main():
    parser = argparse.ArgumentParser(description="A powerful, multi-source proxy scraper.")
    parser.add_argument('--output', default=DEFAULT_OUTPUT_FILE, help=f"The output file for scraped proxies. Defaults to '{DEFAULT_OUTPUT_FILE}'.")
    parser.add_argument('--threads', type=int, default=50, help="Number of threads for regular web scrapers. Default: 50")
    parser.add_argument('--automation-threads', type=int, default=3, help="Max concurrent headless browser automation scrapers (processes). Default: 3")
    parser.add_argument('--turnstile-delay', type=float, default=0, help="Delay in seconds to wait for Turnstile to load on slow computers. Default: 0 (no delay)")
    parser.add_argument('--remove-dead-links', action='store_true', help="Removes URLs from the sites file that return no proxies.")
    parser.add_argument('-v', '--verbose', action='store_true', help="Enable detailed logging for each scraper.")
    parser.add_argument('--compliant', action='store_true', help="Run in compliant mode: respect robots.txt, skip automation scrapers and anti-bot logic.")
    parser.add_argument('--use-browser-automation', action='store_true', help="Enable heavy browser automation scrapers (disabled by default).")
    parser.add_argument('-y', '--yes', action='store_true', help="Auto-accept legal disclaimer (shows warning, waits 2 seconds, then proceeds).")

    group = parser.add_mutually_exclusive_group()
    group.add_argument('--only', nargs='*', help="Only run the specified scrapers (case-insensitive). Pass with no values to see choices.")
    group.add_argument('--exclude', '--except', nargs='*', help="Exclude scrapers from the run (case-insensitive). Pass with no values to see choices.")

    args = parser.parse_args()

    # Only show disclaimer if we are not in compliant mode AND we are actually about to run logic (not just listing sources)
    if not args.compliant and not (args.only is not None and not args.only) and not (args.exclude is not None and not args.exclude):
        show_legal_disclaimer(auto_accept=args.yes)

    scrape_targets = []

    def run_discovery_scraper(verbose: bool):
        """Wrapper to run the discovery process and then scrape found URLs."""
        discovered_urls = discover_urls_from_file(SOURCES_FILE, verbose=verbose)
        if not discovered_urls:
            return []
        
        # Logic: Don't scrape from discovered source urls, if their domain is already gonna be scraped from site-to-get-proxies-from.txt
        # UNLESS the Websites category isn't selected for the scraping run.
        if general_scraper_name in tasks_to_run:
            existing_domains = set()
            for t_url, _, _ in scrape_targets:
                try:
                    netloc = urlparse(t_url).netloc
                    # Remove 'www.' for broader matching
                    if netloc.startswith("www."): netloc = netloc[4:]
                    existing_domains.add(netloc)
                except: pass
            
            filtered_urls = []
            for d_url in discovered_urls:
                try:
                    d_netloc = urlparse(d_url).netloc
                    if d_netloc.startswith("www."): d_netloc = d_netloc[4:]
                    
                    if d_netloc not in existing_domains:
                        filtered_urls.append(d_url)
                except: pass
            
            if verbose and len(filtered_urls) < len(discovered_urls):
                print(f"[INFO] {discovery_scraper_name}: Skipped {len(discovered_urls) - len(filtered_urls)} URLs because their domain is already in {SITES_FILE}.", flush=True)
            
            discovered_urls = filtered_urls

        if not discovered_urls:
            return []

        # Convert simple URLs to the target format (url, payload, headers)
        targets = [(url, None, None) for url in discovered_urls]
        
        # Run the generic proxy scraper on these targets
        # Note: scrape_proxies returns (proxies, successful_urls). We return only the proxies list.
        proxies, _ = scrape_proxies(targets, verbose=verbose, max_workers=args.threads, respect_robots_txt=args.compliant)
        return proxies

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
        'ProxyDocker': scrape_from_proxydocker,
        'Advanced.name': scrape_from_advancedname,
        'ProxyServers.pro': scrape_from_proxyservers,
        'Proxy-Daily': lambda verbose: scrape_from_proxydaily(verbose=verbose, compliant_mode=args.compliant),
        'ProxyNova': scrape_from_proxynova,
        'PremProxy': scrape_from_premproxy,
        'Discovery': run_discovery_scraper, # New discovery source
    }
    
    AUTOMATION_SCRAPER_NAMES = ['OpenProxyList', 'Hide.mn', 'Spys.one']
    ANTI_BOT_BYPASS_SCRAPERS = ['OpenProxyList', 'Hide.mn', 'Spys.one', 'XSEO', 'ProxyDocker', 'Advanced.name', 'ProxyServers.pro', 'ProxyNova', 'PremProxy']
    HEADFUL_SCRAPERS = ['Hide.mn', 'Spys.one']
    general_scraper_name = 'Websites'
    discovery_scraper_name = 'Discover'
    all_scraper_names = sorted(list(all_scraper_tasks.keys()) + [general_scraper_name])

    if args.compliant:
        print("[INFO] Running in COMPLIANT mode - respecting robots.txt and skipping anti-bot bypass scrapers", flush=True)

    if (args.only is not None and not args.only) or (args.exclude is not None and not args.exclude):
        print("Available scraper sources are:", flush=True)
        print(f"  {general_scraper_name} (URLs from {SITES_FILE})", flush=True)
        print(f"  {discovery_scraper_name} (URLs discovered from website lists from {SOURCES_FILE})", flush=True)
        for name in all_scraper_names:
            if name != general_scraper_name and name != discovery_scraper_name:
                extra_info = []
                if name in ANTI_BOT_BYPASS_SCRAPERS and args.compliant:
                    extra_info.append("SKIPPED in --compliant mode")
                if name in AUTOMATION_SCRAPER_NAMES and not args.use_browser_automation:
                    extra_info.append("Pass --use-browser-automation to enable")
                
                marker_str = f" ({', '.join(extra_info)})" if extra_info else ""
                marker_str = f" ({', '.join(extra_info)})" if extra_info else ""
                print(f"  {name}{marker_str}", flush=True)
        sys.exit(0)

    tasks_to_run = all_scraper_tasks.copy()

    if args.compliant:
        for scraper_name in ANTI_BOT_BYPASS_SCRAPERS:
            if scraper_name in tasks_to_run:
                del tasks_to_run[scraper_name]
                if args.verbose:
                    print(f"[INFO] Skipping '{scraper_name}' in compliant mode (uses anti-bot circumvention)", flush=True)

    try:
        file_targets = parse_sites_file(SITES_FILE)
        scrape_targets.extend(file_targets)
        if scrape_targets:
            tasks_to_run[general_scraper_name] = lambda verbose: scrape_proxies(scrape_targets, verbose=verbose, max_workers=args.threads, respect_robots_txt=args.compliant)
    except FileNotFoundError:
        print(f"[WARN] '{SITES_FILE}' not found. '{general_scraper_name}' scraper is unavailable.", flush=True)

    scraper_name_map = {name.lower(): name for name in list(tasks_to_run.keys())}
    def resolve_user_input(user_list):
        return {scraper_name_map[name.lower()] for name in user_list if name.lower() in scraper_name_map}

    if args.only:
        sources_to_run = resolve_user_input(args.only)
        tasks_to_run = {name: func for name, func in tasks_to_run.items() if name in sources_to_run}
        print(f"--- Running ONLY the following scrapers: {', '.join(tasks_to_run.keys())} ---", flush=True)
    elif args.exclude:
        sources_to_exclude = resolve_user_input(args.exclude)
        tasks_to_run = {name: func for name, func in tasks_to_run.items() if name not in sources_to_exclude}
        print(f"--- EXCLUDING the following scrapers: {', '.join(sources_to_exclude)} ---", flush=True)

    if not args.only and not args.use_browser_automation:
        removed_automation = []
        for name in AUTOMATION_SCRAPER_NAMES:
            if name in tasks_to_run:
                del tasks_to_run[name]
                removed_automation.append(name)

        if removed_automation and args.verbose:
            print(f"[INFO] Skipped browser automation scrapers by default: {', '.join(removed_automation)}", flush=True)
            print("[INFO] Use --use-browser-automation to enable them.", flush=True)

    if not tasks_to_run:
        print("[ERROR] No scrapers selected to run. Exiting.", flush=True)
        sys.exit(1)

    automation_tasks_present = any(name in tasks_to_run for name in AUTOMATION_SCRAPER_NAMES)
    headful_tasks_present = any(name in tasks_to_run for name in HEADFUL_SCRAPERS)

    if headful_tasks_present and sys.platform == "linux" and not os.environ.get('DISPLAY'):
        print("[INFO] Linux/WSL detected. Checking for xvfb-run...", flush=True)
        if shutil.which("xvfb-run"):
            print("[INFO] xvfb-run found. Re-launching inside a virtual display...", flush=True)
            command = [shutil.which("xvfb-run"), '--auto-servernum', sys.executable, *sys.argv]
            subprocess.run(command)
            sys.exit(0)
        else:
            print("[ERROR] xvfb-run is required for headful browser automation on headless Linux/WSL but is not installed.", flush=True)
            print("Please install it: sudo apt-get update && sudo apt-get install -y xvfb", flush=True)
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

    def shutdown_all_executors():
        """Callback to shutdown all executors immediately."""
        for executor in executors:
            try:
                executor.shutdown(wait=False, cancel_futures=True)
            except Exception:
                pass

    with termination_context(callbacks=[shutdown_all_executors]):
        if normal_tasks:
            print(f"--- Submitting {len(normal_tasks)} regular scraper(s) using a ThreadPool...", flush=True)
            executor = ThreadPoolExecutor(max_workers=args.threads, thread_name_prefix='NormalScraper')
            executors.append(executor)
            for name, func in normal_tasks.items():
                future = executor.submit(func, args.verbose)
                future_to_scraper[future] = name
                all_futures.append(future)

        if headless_automation_tasks:
            print(f"--- Submitting {len(headless_automation_tasks)} headless automation scraper(s) using a ThreadPool...", flush=True)
            executor = ThreadPoolExecutor(max_workers=args.automation_threads, thread_name_prefix='HeadlessAutomation')
            executors.append(executor)
            for name, func in headless_automation_tasks.items():
                future = executor.submit(run_automation_task, name, func, args.verbose, is_headful=False, turnstile_delay=args.turnstile_delay)
                future_to_scraper[future] = name
                all_futures.append(future)

        if headful_automation_tasks:
            print(f"--- Submitting {len(headful_automation_tasks)} headful automation scraper(s) sequentially using a ThreadPool (1 worker)...", flush=True)
            executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='HeadfulAutomation')
            executors.append(executor)
            for name, func in headful_automation_tasks.items():
                future = executor.submit(run_automation_task, name, func, args.verbose, is_headful=True, turnstile_delay=args.turnstile_delay)
                future_to_scraper[future] = name
                all_futures.append(future)

        try:
            if all_futures:
                print("\n--- Waiting for all scrapers to complete... ---", flush=True)
                
                # Convert to set for efficient removal
                pending_futures = set(all_futures)
                
                while pending_futures:
                    if should_terminate():
                        print("\n[INFO] Termination requested, stopping result collection...", flush=True)
                        break
                    
                    # Wait for at least one future to complete, but timeout to allow checking termination flag
                    done_futures, _ = wait(pending_futures, timeout=0.5, return_when=FIRST_COMPLETED)
                    
                    if not done_futures:
                        continue
                        
                    for future in done_futures:
                        pending_futures.remove(future)
                        
                        name = future_to_scraper.get(future, "Unknown")
                        try:
                            # The future is already done, so this call is non-blocking
                            result_data = future.result() 
                            if name == general_scraper_name:
                                proxies_found, urls = result_data
                                results[name] = proxies_found
                                successful_general_urls.extend(urls)
                            else:
                                results[name] = result_data
                            print(f"[COMPLETED] '{name}' finished, found {len(results.get(name, []))} proxies.", flush=True)
                        except TimeoutError:
                            results[name] = []
                            print(f"[TIMEOUT] Scraper '{name}' exceeded execution time. Cancelling...", flush=True)
                            future.cancel()
                        except Exception as e:
                            results[name] = []
                            print(f"[ERROR] Scraper '{name}' failed: {e}", flush=True)
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
                        print(f"[RECOVERED] '{name}' finished after shutdown, found {len(results.get(name, []))} proxies.", flush=True)
                    except Exception as e:
                        results[name] = []
                        print(f"[ERROR] Could not recover results from '{name}': {e}", flush=True)

        print("\n--- Combining and processing all results ---", flush=True)
        combined_proxies = {p for proxy_list in results.values() if proxy_list for p in proxy_list if p and p.strip()}
        final_proxies = sorted(list({p for p in combined_proxies if not INVALID_IP_REGEX.match(p)}))

        spam_count = len(combined_proxies) - len(final_proxies)
        if spam_count > 0:
            print(f"[INFO] Removed {spam_count} spam/invalid proxies from reserved IP ranges.", flush=True)

        print("--- Summary ---", flush=True)
        for name in sorted(results.keys()): print(f"Found {len(results.get(name, []))} proxies from {name}.", flush=True)
        print(f"Total unique & valid proxies: {len(final_proxies)}", flush=True)

        if final_proxies:
            save_proxies_to_file(final_proxies, args.output)
        else:
            print("Could not find any proxies from any source.", flush=True)

        if args.remove_dead_links and successful_general_urls:
            print(f"[INFO] Updating '{SITES_FILE}' to remove dead links...", flush=True)
            try:
                lines_to_keep = []
                with open(SITES_FILE, 'r', encoding='utf-8') as f:
                    for line in f:
                        stripped_line = line.strip()
                        if not stripped_line or stripped_line.startswith('#') or stripped_line.split('|')[0].strip() in successful_general_urls:
                            lines_to_keep.append(line)
                with open(SITES_FILE, 'w', encoding='utf-8') as f:
                    f.writelines(lines_to_keep)
                print(f"[SUCCESS] Successfully updated '{SITES_FILE}'.", flush=True)
            except Exception as e:
                print(f"[ERROR] Failed to update '{SITES_FILE}': {e}", flush=True)

        if should_terminate():
            print("[INFO] Script terminated by user. Partial results have been saved.", flush=True)
            return

if __name__ == "__main__":
    import sys
    try:
        main()
    finally:
        sys.exit(0)

