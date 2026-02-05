import json
import sys
import argparse
import os
import re
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed, wait
from datetime import datetime
import glob
from typing import Optional, Callable, List
import random

from checker.proxy_checker import ProxyChecker
from helper.termination import termination_context, should_terminate

SAVE_BATCH_SIZE = 25

def _save_working_proxies(proxy_data, prepend_protocol, output_base, is_final=False):
    """Saves the working proxies, creating the output directory if needed."""
    base, ext = os.path.splitext(output_base)
    if not ext: ext = ".txt"
    directory = os.path.dirname(base)
    if directory and not os.path.exists(directory): os.makedirs(directory)

    for protocol, proxies_set in proxy_data.items():
        if not proxies_set: continue
        filename = f"{base}-{protocol}{ext}"
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                for proxy in sorted(proxies_set):
                    if prepend_protocol and protocol != 'all':
                        f.write(f"{protocol}://{proxy}\n")
                    else:
                        f.write(f"{proxy}\n")
        except IOError as e:
            print(f"[ERROR] Could not write to output file '{filename}': {e}", flush=True)
    if not is_final:
        total = len(proxy_data.get('all', set()))
        print(f"[PROGRESS] Interim save complete. {total} total working proxies.", flush=True)

def check_and_format_proxy(checker, proxy_line):
    details = checker.check_proxy(proxy_line)
    if details: return (proxy_line, details)
    return None

def parse_timeout(timeout_str: str) -> float:
    timeout_str = timeout_str.strip().lower()
    try:
        if timeout_str.endswith('ms'): return float(timeout_str[:-2]) / 1000.0
        if timeout_str.endswith('s'): return float(timeout_str[:-1])
        return float(timeout_str)
    except (ValueError, TypeError):
        raise ValueError("Invalid timeout format")

def load_proxies_from_patterns(patterns: list) -> list:
    """
    Finds all files matching the given patterns, loads all proxies,
    and returns a de-duplicated list.
    """
    all_files = set()
    for pattern in patterns: all_files.update(glob.glob(pattern))
    if not all_files:
        print("[ERROR] No files found matching patterns.", flush=True)
        return []
    
    unique_proxies = set()
    for filepath in all_files:
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    p = line.strip()
                    if p and not p.startswith('#'): unique_proxies.add(p)
        except IOError: pass
    
    print(f"[INFO] Loaded {len(unique_proxies)} unique proxies from files.", flush=True)
    
    # Shuffle the proxies to avoid hitting large blocks of dead subnets (Tail of Death)
    # which causes the checker to seemingly stall or slow down significantly.
    proxy_list = list(unique_proxies)
    random.shuffle(proxy_list)
    return proxy_list

def run_checker_pipeline(args, input_queue: Optional[queue.Queue] = None, result_callback: Optional[Callable[[str, bool, dict], None]] = None):
    try:
        timeout = parse_timeout(args.timeout)
        if timeout <= 0: timeout = 1.0
    except ValueError:
        print(f"[ERROR] Invalid timeout: {args.timeout}", flush=True)
        return

    initial_proxies = []
    if not input_queue:
        initial_proxies = load_proxies_from_patterns(args.input)
        if not initial_proxies:
            print("[ERROR] No proxies to check.", flush=True)
            return

    print("[INFO] Initializing Proxy Checker...", flush=True)
    checker = ProxyChecker(timeout=timeout, verbose=args.verbose)
    if not checker.ip:
        print("[ERROR] Could not determine public IP. Aborting.", flush=True)
        return
    
    if args.output: output_base_name = args.output
    else: output_base_name = f"working-proxies-{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"

    in_flight = {}
    submitted_proxies = set()
    working_proxies = {'all': set(), 'http': set(), 'socks4': set(), 'socks5': set()}
    executor = ThreadPoolExecutor(max_workers=args.threads)

    def shutdown_executor():
        try: executor.shutdown(wait=False, cancel_futures=True)
        except: pass

    def save_resume_file():
        # Only simple resume for file-based mode
        if input_queue: return
        remaining = set(initial_proxies) - submitted_proxies
        remaining.update(in_flight.values())
        if not remaining: return
        
        fname = f"{os.path.splitext(args.output)[0] if args.output else 'proxies'}-resume.txt"
        try:
            with open(fname, 'w', encoding='utf-8') as f:
                for p in sorted(list(remaining)): f.write(p + '\n')
            print(f"[SUCCESS] Resume file saved: {fname}", flush=True)
        except Exception as e:
            print(f"[ERROR] Failed to save resume file: {e}", flush=True)

    with termination_context(callbacks=[shutdown_executor]):
        try:
            print(f"[INFO] Public IP: {checker.ip}")
            print(f"--- Checking with {args.threads} workers, {timeout}s timeout ---", flush=True)

            pending_list = list(initial_proxies)
            pending_index = 0
            pipeline_mode = (input_queue is not None)
            
            while True:
                if should_terminate(): break

                while len(in_flight) < args.threads * 2:
                    proxy_to_check = None
                    
                    if input_queue:
                        try:
                            proxy_to_check = input_queue.get_nowait()
                            if proxy_to_check is None: # Sentinel
                                pipeline_mode = False
                                break
                        except queue.Empty: pass
                    
                    if not proxy_to_check and pending_index < len(pending_list):
                        proxy_to_check = pending_list[pending_index]
                        pending_index += 1
                    
                    if proxy_to_check:
                        if proxy_to_check not in submitted_proxies:
                            future = executor.submit(check_and_format_proxy, checker, proxy_to_check)
                            in_flight[future] = proxy_to_check
                            submitted_proxies.add(proxy_to_check)
                    else:
                        break
                
                if in_flight:
                    done_futures, _ = wait(in_flight.keys(), timeout=0.1, return_when='FIRST_COMPLETED')
                    for future in done_futures:
                        proxy = in_flight.pop(future)
                        try:
                            result = future.result()
                            if result:
                                line, details = result
                                working_proxies['all'].add(line)
                                for p in details.get('protocols', []):
                                    if p in working_proxies: working_proxies[p].add(line)

                                print(f"\n[SUCCESS] Proxy: {line:<21} | Anon: {details['anonymity']:<11} | {','.join(details['protocols']):<14} | {details['timeout']}ms", flush=True)
                                if len(working_proxies['all']) % SAVE_BATCH_SIZE == 0:
                                    _save_working_proxies(working_proxies, args.prepend_protocol, output_base_name)

                                if result_callback: result_callback(proxy, True, details)
                            else:
                                if args.verbose: print(".", end="", flush=True)
                                if result_callback: result_callback(proxy, False, {})
                        except Exception as exc:
                            if args.verbose: print(f"\n[ERROR] Exception checking {proxy}: {exc}", flush=True)
                            if result_callback: result_callback(proxy, False, {})
                
                if not in_flight and not pipeline_mode and pending_index >= len(pending_list):
                    break
                
                if not in_flight:
                    import time
                    time.sleep(0.5)

        except Exception as e:
            print(f"[ERROR] Checker loop error: {e}", flush=True)
            return

        if should_terminate():
            print("[INTERRUPTED] Stopping...", flush=True)
            save_resume_file()

        print("--- Check Finished ---", flush=True)
        total = len(working_proxies['all'])
        print(f"Found {total} working proxies.", flush=True)
        if total > 0:
            _save_working_proxies(working_proxies, args.prepend_protocol, output_base_name, is_final=True)

def main():
    parser = argparse.ArgumentParser(description="Proxy checker.")
    parser.add_argument('--input', nargs='+', default=['scraped-proxies.txt'])
    parser.add_argument('--output', type=str, default=None)
    parser.add_argument('--threads', type=int, default=500)
    parser.add_argument('--timeout', type=str, default='6s')
    parser.add_argument('--prepend-protocol', action='store_true')
    parser.add_argument('-v', '--verbose', action='store_true')
    args = parser.parse_args()
    run_checker_pipeline(args)

if __name__ == "__main__":
    main()
