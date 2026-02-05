import os
import sys
import json
import argparse
import re
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed, wait, FIRST_COMPLETED
from typing import List, Dict, Union, Tuple, Set, Optional, Callable
from urllib.parse import urlparse
from seleniumbase import SB
from contextlib import contextmanager

from scrapers.proxy_scraper import scrape_proxies
from scrapers.proxyscrape_api_fetcher import fetch_from_api
from scrapers.proxydb_scraper import scrape_all_from_proxydb
from scrapers.geonode_scraper import scrape_from_geonode_api
from scrapers.checkerproxy_scraper import scrape_checkerproxy_archive
from scrapers.proxylistorg_scraper import scrape_from_proxylistorg
# from scrapers.xseo_scraper import scrape_from_xseo # Deprecated, server gone
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
from scrapers.source_discoverer import discover_urls_from_file, convert_to_jsdelivr_url
from helper.termination import termination_context, should_terminate, get_termination_handler

SITES_FILE = 'sites-to-get-proxies-from.txt'
SOURCES_FILE = 'sites-to-get-sources-from.txt'
DEFAULT_OUTPUT_FILE = 'scraped-proxies.txt'
__all__ = ['DEFAULT_OUTPUT_FILE', 'run_scraper_pipeline', 'list_available_scrapers', 'show_legal_disclaimer']
INVALID_IP_REGEX = re.compile(
    r"^(10\.|127\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[01])\.|169\.254\.|0\.|2(2[4-9]|3[0-9])\.|2(4[0-9]|5[0-5])\.)"
)

# Define scrapers globally so they can be accessed by list_available_scrapers
ALL_SCRAPER_TASKS = {
    'ProxyScrape': fetch_from_api,
    'Geonode': scrape_from_geonode_api,
    'ProxyDB': scrape_all_from_proxydb, # Wrapper handled in logic
    'CheckerProxy': scrape_checkerproxy_archive,
    'Spys.one': scrape_from_spysone,
    'OpenProxyList': scrape_from_openproxylist,
    'Hide.mn': scrape_from_hidemn,
    # 'XSEO': scrape_from_xseo, # Deprecated, server gone
    'GoLogin': scrape_from_gologin_api,
    'ProxyList.org': scrape_from_proxylistorg,
    'ProxyHttp': scrape_from_proxyhttp,
    'ProxyDocker': scrape_from_proxydocker,
    'Advanced.name': scrape_from_advancedname,
    'ProxyServers.pro': scrape_from_proxyservers,
    'Proxy-Daily': scrape_from_proxydaily, # Wrapper handled in logic
    'ProxyNova': scrape_from_proxynova,
    'PremProxy': scrape_from_premproxy,
    'Discover': None, # Handled dynamically
    'Websites': None # Handled dynamically
}
AUTOMATION_SCRAPER_NAMES = ['OpenProxyList', 'Hide.mn', 'Spys.one']
ANTI_BOT_BYPASS_SCRAPERS = ['OpenProxyList', 'Hide.mn', 'Spys.one', 'ProxyDocker', 'Advanced.name', 'ProxyServers.pro', 'ProxyNova', 'PremProxy']

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
    if not os.path.exists(filename):
        return []
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
        with SB(uc=True, headed=is_headful, headless2=(not is_headful), disable_csp=True, user_data_dir=temp_dir) as sb:
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

def show_legal_disclaimer(auto_accept=False):
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

def list_available_scrapers(args):
    """Prints available scrapers and exits."""
    print("Available scraper sources are:", flush=True)
    print(f"  Websites (URLs from {SITES_FILE})", flush=True)
    print(f"  Discover (URLs discovered from website lists from {SOURCES_FILE})", flush=True)
    
    # Sort for consistent output
    sorted_names = sorted(list(ALL_SCRAPER_TASKS.keys()))
    
    for name in sorted_names:
        if name in ['Websites', 'Discover']: continue
        
        extra_info = []
        if name in ANTI_BOT_BYPASS_SCRAPERS and args.compliant:
            extra_info.append("SKIPPED in --compliant mode")
        if name in AUTOMATION_SCRAPER_NAMES and not args.use_browser_automation:
            extra_info.append("Pass --use-browser-automation to enable")
            
        marker_str = f" ({', '.join(extra_info)})" if extra_info else ""
        print(f"  {name}{marker_str}", flush=True)

def run_scraper_pipeline(
    args, 
    proxy_found_callback: Optional[Callable[[str, str, List[str]], None]] = None,
    handle_signals: bool = True,
    skip_disclaimer: bool = False
):
    """
    Main scraping logic.
    Args:
        args: Parsed arguments.
        proxy_found_callback: fn(scraper_name, source_detail, proxies)
        handle_signals: If True, registers signal handlers for Ctrl+C. 
        skip_disclaimer: If True, skips the legal disclaimer (assumes caller handled it).
    """
    
    # Check for Info Mode (empty --only list)
    if args.only is not None and not args.only:
        list_available_scrapers(args)
        # If this is called from a thread (ProxyGather), we shouldn't kill the process, just return
        return [], {}

    if args.exclude is not None and not args.exclude:
        list_available_scrapers(args)
        return [], {}

    # Only show disclaimer if we are not in compliant mode AND we are actually about to run logic (not just listing sources)
    # Legal Disclaimer
    if not skip_disclaimer and not args.compliant:
        show_legal_disclaimer(auto_accept=args.yes)

    scrape_targets = []
    general_scraper_name = 'Websites'
    discovery_scraper_name = 'Discover'

    # Build the task map (reconstruct to allow closures like lambda verbose: ...)
    tasks_to_run = {}
    
    # 1. Standard scrapers
    for name, func in ALL_SCRAPER_TASKS.items():
        if name in ['Websites', 'Discover']: continue
        if name == 'ProxyDB':
            tasks_to_run[name] = lambda verbose: scrape_all_from_proxydb(verbose=verbose, compliant_mode=args.compliant)
        elif name == 'Proxy-Daily':
            tasks_to_run[name] = lambda verbose: scrape_from_proxydaily(verbose=verbose, compliant_mode=args.compliant)
        elif name == 'Geonode':
            tasks_to_run[name] = lambda verbose: scrape_from_geonode_api(verbose=verbose, compliant_mode=args.compliant)
        else:
            tasks_to_run[name] = func

    # 2. Websites scraper (Generic)
    file_targets = parse_sites_file(SITES_FILE)
    scrape_targets.extend(file_targets)
    if scrape_targets:
        def websites_cb(url, proxies):
            if proxy_found_callback: proxy_found_callback(general_scraper_name, url, list(proxies))
        tasks_to_run[general_scraper_name] = lambda verbose: scrape_proxies(
            scrape_targets, verbose=verbose, max_workers=args.threads, 
            respect_robots_txt=args.compliant, callback=websites_cb
        )

    # 3. Discovery scraper
    def run_discovery_scraper(verbose: bool):
        discovered_urls = discover_urls_from_file(SOURCES_FILE, verbose=verbose)
        if not discovered_urls: return []
        
        # Deduplicate against Websites
        if general_scraper_name in tasks_to_run:
            existing_urls = {convert_to_jsdelivr_url(t[0]) for t in scrape_targets}
            # Also dedup domains roughly
            existing_domains = {urlparse(u).netloc.replace("www.", "") for u in existing_urls}
            
            filtered_urls = []
            for d_url in discovered_urls:
                try:
                    conv_url = convert_to_jsdelivr_url(d_url)
                    netloc = urlparse(conv_url).netloc.replace("www.", "")
                    if conv_url not in existing_urls and netloc not in existing_domains:
                        filtered_urls.append(d_url)
                except: pass
            discovered_urls = filtered_urls

        if not discovered_urls: return []

        targets = [(url, None, None) for url in discovered_urls]
        def internal_cb(url, proxies):
            if proxy_found_callback: proxy_found_callback(discovery_scraper_name, url, list(proxies))

        proxies, _ = scrape_proxies(targets, verbose=verbose, max_workers=args.threads, respect_robots_txt=args.compliant, callback=internal_cb)
        return proxies
    
    tasks_to_run[discovery_scraper_name] = run_discovery_scraper

    HEADFUL_SCRAPERS = ['Hide.mn', 'Spys.one']

    if args.compliant:
        print("[INFO] Running in COMPLIANT mode.", flush=True)
        for name in ANTI_BOT_BYPASS_SCRAPERS:
            if name in tasks_to_run: del tasks_to_run[name]

    # Filter tasks based on args
    scraper_name_map = {name.lower(): name for name in tasks_to_run.keys()}
    if args.only:
        allowed = {scraper_name_map[n.lower()] for n in args.only if n.lower() in scraper_name_map}
        tasks_to_run = {n: f for n, f in tasks_to_run.items() if n in allowed}
        print(f"--- Running ONLY: {', '.join(tasks_to_run.keys())} ---", flush=True)
    elif args.exclude:
        excluded = {scraper_name_map[n.lower()] for n in args.exclude if n.lower() in scraper_name_map}
        tasks_to_run = {n: f for n, f in tasks_to_run.items() if n not in excluded}
        print(f"--- EXCLUDING: {', '.join(excluded)} ---", flush=True)

    if not args.only and not args.use_browser_automation:
        for name in AUTOMATION_SCRAPER_NAMES:
            if name in tasks_to_run: del tasks_to_run[name]

    # Get threads value - handle both 'threads' (legacy) and 'scraper_threads' (new) attribute names
    threads = getattr(args, 'scraper_threads', getattr(args, 'threads', 50))

    if not tasks_to_run:
        print("[ERROR] No scrapers selected.", flush=True)
        return []

    # Headful automation check
    if any(name in tasks_to_run for name in HEADFUL_SCRAPERS) and sys.platform == "linux" and not os.environ.get('DISPLAY'):
        if shutil.which("xvfb-run"):
            print("[INFO] Re-launching with xvfb-run...", flush=True)
            subprocess.run([shutil.which("xvfb-run"), '--auto-servernum', sys.executable, *sys.argv])
            sys.exit(0)
        else:
            print("[ERROR] xvfb-run missing for headful scrapers.", flush=True)
            sys.exit(1)

    if any(name in tasks_to_run for name in AUTOMATION_SCRAPER_NAMES):
        pre_run_browser_setup()

    results = {}
    successful_general_urls = []
    
    automation_tasks = {n: f for n, f in tasks_to_run.items() if n in AUTOMATION_SCRAPER_NAMES}
    normal_tasks = {n: f for n, f in tasks_to_run.items() if n not in AUTOMATION_SCRAPER_NAMES}
    headful_automation = {n: f for n, f in automation_tasks.items() if n in HEADFUL_SCRAPERS}
    headless_automation = {n: f for n, f in automation_tasks.items() if n not in HEADFUL_SCRAPERS}

    executors = []
    future_to_scraper = {}
    
    def shutdown_all():
        for ex in executors: ex.shutdown(wait=False, cancel_futures=True)

    # Use a custom context manager depending on whether we handle signals or not
    @contextmanager
    def safe_termination_context():
        if handle_signals:
            # Main thread: full signal handling
            with termination_context(callbacks=[shutdown_all]):
                yield
        else:
            # Sub-thread: just register callback, don't touch signals
            handler = get_termination_handler()
            handler.register_callback(shutdown_all)
            try:
                yield
            finally:
                handler.unregister_callback(shutdown_all)

    with safe_termination_context():
        if normal_tasks:
            print(f"--- Submitting {len(normal_tasks)} regular scraper(s)...", flush=True)
            ex = ThreadPoolExecutor(max_workers=threads, thread_name_prefix='NormalScraper')
            executors.append(ex)
            for name, func in normal_tasks.items():
                future_to_scraper[ex.submit(func, args.verbose)] = name

        if headless_automation:
            print(f"--- Submitting {len(headless_automation)} headless automation scraper(s)...", flush=True)
            ex = ThreadPoolExecutor(max_workers=args.automation_threads, thread_name_prefix='HeadlessAutomation')
            executors.append(ex)
            for name, func in headless_automation.items():
                future_to_scraper[ex.submit(run_automation_task, name, func, args.verbose, False, args.turnstile_delay)] = name

        if headful_automation:
            print(f"--- Submitting {len(headful_automation)} headful scraper(s)...", flush=True)
            ex = ThreadPoolExecutor(max_workers=1, thread_name_prefix='HeadfulAutomation')
            executors.append(ex)
            for name, func in headful_automation.items():
                future_to_scraper[ex.submit(run_automation_task, name, func, args.verbose, True, args.turnstile_delay)] = name

        pending_futures = set(future_to_scraper.keys())
        while pending_futures:
            if should_terminate(): break
            done, _ = wait(pending_futures, timeout=0.5, return_when=FIRST_COMPLETED)
            if not done: continue
            
            for future in done:
                pending_futures.remove(future)
                name = future_to_scraper.get(future)
                try:
                    res = future.result()
                    proxies = []
                    if name == general_scraper_name:
                        proxies, urls = res
                        successful_general_urls.extend(urls)
                    else:
                        proxies = res
                    
                    results[name] = proxies
                    # For non-streaming scrapers, we invoke callback here with full results
                    if name != general_scraper_name and name != discovery_scraper_name and proxy_found_callback:
                        proxy_found_callback(name, "N/A", proxies)
                        
                    print(f"[COMPLETED] '{name}' finished, found {len(proxies)} proxies.", flush=True)
                except Exception as e:
                    print(f"[ERROR] Scraper '{name}' failed: {e}", flush=True)
        
        for ex in executors: ex.shutdown(wait=True, cancel_futures=True)

    combined_proxies = {p for proxy_list in results.values() if proxy_list for p in proxy_list if p and p.strip()}
    final_proxies = sorted(list({p for p in combined_proxies if not INVALID_IP_REGEX.match(p)}))
    
    if final_proxies:
        save_proxies_to_file(final_proxies, args.output)

    if args.remove_dead_links and successful_general_urls:
        print(f"[INFO] Updating '{SITES_FILE}'...", flush=True)
        try:
            with open(SITES_FILE, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            with open(SITES_FILE, 'w', encoding='utf-8') as f:
                for line in lines:
                    if not line.strip() or line.strip().startswith('#') or line.split('|')[0].strip() in successful_general_urls:
                        f.write(line)
        except Exception as e:
            print(f"[ERROR] Failed to update sites file: {e}", flush=True)

    return final_proxies, results

def main():
    parser = argparse.ArgumentParser(description="Multi-source proxy scraper.")
    parser.add_argument('--output', default=DEFAULT_OUTPUT_FILE)
    parser.add_argument('--threads', type=int, default=50)
    parser.add_argument('--automation-threads', type=int, default=3)
    parser.add_argument('--turnstile-delay', type=float, default=0)
    parser.add_argument('--remove-dead-links', action='store_true')
    parser.add_argument('-v', '--verbose', action='store_true')
    parser.add_argument('--compliant', action='store_true')
    parser.add_argument('--use-browser-automation', action='store_true')
    parser.add_argument('-y', '--yes', action='store_true')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--only', nargs='*')
    group.add_argument('--exclude', '--except', nargs='*')

    args = parser.parse_args()
    proxies, results = run_scraper_pipeline(args)
    if proxies:
        print(f"\n[SUMMARY] Total unique proxies scraped: {len(proxies)}", flush=True)

if __name__ == "__main__":
    main()

