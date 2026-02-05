import argparse
import sys
import queue
import threading
import time
from datetime import datetime
from collections import defaultdict
from typing import Set, Dict
from urllib.parse import urlparse
import re
import random

from ScrapeAllProxies import run_scraper_pipeline, list_available_scrapers, show_legal_disclaimer, DEFAULT_OUTPUT_FILE
from CheckProxies import run_checker_pipeline
from helper.termination import termination_context, should_terminate

def get_source_identifier(url: str, scraper_name: str) -> str:
    """Returns a clean source identifier from URL or scraper name."""
    if scraper_name not in ['Websites', 'Discover']:
        return scraper_name
    
    if not url or url == "N/A": return scraper_name

    gh_pattern = re.compile(r'https?://(?:www\.)?(?:cdn\.jsdelivr\.net/gh|fastly\.jsdelivr\.net/gh|raw\.githubusercontent\.com|github\.com)/([^/]+)/([^/@#?]+)')
    match = gh_pattern.search(url)
    if match:
        user, repo = match.groups()
        return f"github:{user}/{repo}"
    
    try:
        netloc = urlparse(url).netloc
        if netloc.startswith("www."): netloc = netloc[4:]
        return netloc
    except:
        return scraper_name

def handle_pre_checks(args):
    """
    Handles 'List Scrapers' mode and Legal Disclaimer check on the main thread.
    Returns True if we should proceed, False if we should exit (e.g. printed list).
    """
    if (args.only is not None and not args.only) or (args.exclude is not None and not args.exclude):
        list_available_scrapers(args)
        return False

    if not args.compliant:
        show_legal_disclaimer(auto_accept=args.yes)

    return True

def cmd_scrape(args):
    print("=== ProxyGather Scraping Mode ===")
    if not handle_pre_checks(args):
        return
    
    # Use timestamped output if default is set
    if args.output == DEFAULT_OUTPUT_FILE:
         timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
         args.output = f"scraped-proxies-{timestamp}.txt"

    run_scraper_pipeline(args, skip_disclaimer=True)

def cmd_check(args):
    print("=== ProxyGather Checker Mode ===")
    run_checker_pipeline(args)

def cmd_run(args):
    print("=== ProxyGather Unified Run Mode ===")
    
    if not handle_pre_checks(args):
        return

    # --- Filename Logic ---
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    
    # 1. Scraper output: always scraped-proxies-{timestamp}.txt
    scraped_file = f"scraped-proxies-{timestamp}.txt"
    
    # 2. Checker output: if user didn't change default 'working-proxies.txt', 
    #    we set it to None so CheckProxies generates 'working-proxies-{timestamp}.txt'.
    #    If user provided a specific name (e.g. --output my-proxies.txt), we use that.
    if args.output == 'working-proxies.txt':
        args.output = None 
    
    proxy_queue = queue.Queue()
    stats = defaultdict(lambda: {'scraped': 0, 'working': 0})
    proxy_to_sources: Dict[str, Set[str]] = defaultdict(set)
    checked_cache: Dict[str, bool] = {}
    stats_lock = threading.Lock()

    def on_proxy_scraped(scraper_name, source_detail, proxies_found):
        source_id = get_source_identifier(source_detail, scraper_name)
        
        # Convert to list and shuffle to avoid feeding sorted chunks of dead proxies to checker
        proxies_list = list(proxies_found)
        random.shuffle(proxies_list)
        
        with stats_lock:
            stats[source_id]['scraped'] += len(proxies_list)
            for proxy in proxies_list:
                proxy_to_sources[proxy].add(source_id)
                if proxy in checked_cache and checked_cache[proxy]:
                    stats[source_id]['working'] += 1
                
                if len(proxy_to_sources[proxy]) == 1:
                    proxy_queue.put(proxy)

    def on_proxy_checked(proxy, is_working, details):
        with stats_lock:
            checked_cache[proxy] = is_working
            if is_working:
                for source_id in proxy_to_sources.get(proxy, []):
                    stats[source_id]['working'] += 1

    class ScraperArgsWrapper:
        def __init__(self, original_args, output_file):
            self.__dict__ = original_args.__dict__.copy()
            self.threads = original_args.scraper_threads
            self.output = output_file
            
    def scraper_worker():
        s_args = ScraperArgsWrapper(args, scraped_file)
        run_scraper_pipeline(s_args, proxy_found_callback=on_proxy_scraped, handle_signals=False, skip_disclaimer=True)
        proxy_queue.put(None)

    with termination_context():
        scraper_thread = threading.Thread(target=scraper_worker, name="ScraperOrchestrator")
        scraper_thread.start()

        run_checker_pipeline(args, input_queue=proxy_queue, result_callback=on_proxy_checked)
        
        scraper_thread.join()

    print("\n" + "="*60)
    print(f"{'Source':<40} | {'Scraped':<10} | {'Working':<10}")
    print("-" * 60)
    
    sorted_stats = sorted(stats.items(), key=lambda x: x[1]['working'], reverse=True)
    for source, data in sorted_stats:
        print(f"{source[:38]:<40} | {data['scraped']:<10} | {data['working']:<10}")
    
    unique_scraped = len(proxy_to_sources)
    unique_working = sum(1 for w in checked_cache.values() if w)
    
    print("-" * 60)
    print(f"{'TOTAL (Unique)':<40} | {unique_scraped:<10} | {unique_working:<10}")
    print("="*60)

def main():
    parser = argparse.ArgumentParser(description="ProxyGather: Unified Proxy Scraper and Checker")
    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    def add_scraper_args(p):
        p.add_argument('--output', default=DEFAULT_OUTPUT_FILE)
        p.add_argument('--scraper-threads', dest='threads', type=int, default=50)
        p.add_argument('--automation-threads', type=int, default=3)
        p.add_argument('--turnstile-delay', type=float, default=0)
        p.add_argument('--remove-dead-links', action='store_true')
        p.add_argument('--compliant', action='store_true')
        p.add_argument('--use-browser-automation', action='store_true')
        p.add_argument('-y', '--yes', action='store_true')
        p.add_argument('--only', nargs='*')
        p.add_argument('--exclude', nargs='*')
        p.add_argument('-v', '--verbose', action='store_true')

    def add_checker_args(p):
        p.add_argument('--input', nargs='+', default=['scraped-proxies.txt'])
        p.add_argument('--checker-threads', dest='threads', type=int, default=500)
        p.add_argument('--timeout', type=str, default='6s')
        p.add_argument('--prepend-protocol', action='store_true')
        if not any(x.dest == 'verbose' for x in p._actions):
             p.add_argument('-v', '--verbose', action='store_true')

    p_scrape = subparsers.add_parser('scrape')
    add_scraper_args(p_scrape)

    p_check = subparsers.add_parser('check')
    add_checker_args(p_check)

    p_run = subparsers.add_parser('run')
    # Default for checker output in run mode is working-proxies.txt (which acts as a placeholder flag)
    p_run.add_argument('--output', default='working-proxies.txt')
    p_run.add_argument('--scraper-threads', type=int, default=50)
    p_run.add_argument('--checker-threads', dest='threads', type=int, default=500)
    
    p_run.add_argument('--automation-threads', type=int, default=3)
    p_run.add_argument('--turnstile-delay', type=float, default=0)
    p_run.add_argument('--remove-dead-links', action='store_true')
    p_run.add_argument('--compliant', action='store_true')
    p_run.add_argument('--use-browser-automation', action='store_true')
    p_run.add_argument('-y', '--yes', action='store_true')
    p_run.add_argument('--only', nargs='*')
    p_run.add_argument('--exclude', nargs='*')
    p_run.add_argument('-v', '--verbose', action='store_true')
    
    p_run.add_argument('--timeout', type=str, default='6s')
    p_run.add_argument('--prepend-protocol', action='store_true')

    args = parser.parse_args()

    if args.command == 'scrape': cmd_scrape(args)
    elif args.command == 'check': cmd_check(args)
    elif args.command == 'run': cmd_run(args)
    else: parser.print_help()

if __name__ == "__main__":
    main()