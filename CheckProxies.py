import json
import sys
import argparse
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from checker.proxy_checker import ProxyChecker

SAVE_BATCH_SIZE = 25

def _save_working_proxies(proxy_data, prepend_protocol, datetime_str, is_final=False):
    """A helper function to save the dictionary of working proxies to their respective files."""
    for protocol, proxies_set in proxy_data.items():
        if not proxies_set: continue
        # this now includes the full date and time
        filename = f"working-proxies-{protocol}-{datetime_str}.txt"
        try:
            # using 'w' is fine, since the timestamp makes the filename unique
            with open(filename, 'w', encoding='utf-8') as f:
                for proxy in sorted(proxies_set):
                    if prepend_protocol and protocol != 'all':
                        f.write(f"{protocol}://{proxy}\n")
                    else:
                        f.write(f"{proxy}\n")
        except IOError as e:
            print(f"\n[ERROR] Could not write to output file '{filename}': {e}")
    if not is_final:
        total_proxies = len(proxy_data.get('all', set()))
        print(f"\n[PROGRESS] Interim save complete. {total_proxies} total working proxies saved.")

def check_and_format_proxy(checker, proxy_line):
    """A helper function to be run in each thread."""
    details = checker.check_proxy(proxy_line)
    if details:
        return (proxy_line, details)
    return None

def parse_timeout(timeout_str: str) -> float:
    """Parses a timeout string like '500ms', '10s', or '8' into a float of seconds."""
    timeout_str = timeout_str.strip().lower()
    try:
        if timeout_str.endswith('ms'):
            return float(timeout_str[:-2]) / 1000.0
        if timeout_str.endswith('s'):
            return float(timeout_str[:-1])
        return float(timeout_str)
    except (ValueError, TypeError):
        raise ValueError("Invalid timeout format")

def main():
    parser = argparse.ArgumentParser(
        description="A high-performance, memory-efficient proxy checker that can be safely interrupted and resumed."
    )
    parser.add_argument(
        '--file', 
        type=str, 
        default='scraped-proxies.txt', 
        help="Path to the input file containing proxies to check (default: scraped-proxies.txt)."
    )
    parser.add_argument('--threads', type=int, default=100, help="Number of threads for checking proxies.")
    parser.add_argument(
        '--timeout', 
        type=str, 
        default='8s', 
        help="Timeout for each proxy check. E.g., '500ms', '10s', '8'. Default is 8 seconds."
    )
    parser.add_argument('--prepend-protocol', action='store_true', help="Prepend protocol to proxies in specific files.")
    args = parser.parse_args()

    # --- Setup timeout ---
    try:
        timeout = parse_timeout(args.timeout)
        if timeout <= 0: timeout = 1.0
    except ValueError:
        print(f"[ERROR] Invalid timeout format: {args.timeout}. Please use formats like '500ms', '10s', or '8'.")
        return

    # --- Setup files and checker ---
    input_filename = args.file
    if not os.path.exists(input_filename):
        print(f"[ERROR] Input file '{input_filename}' not found.")
        return

    print("[INFO] Initializing Proxy Checker...")
    checker = ProxyChecker(timeout=timeout)
    if not checker.ip:
        print("[ERROR] Could not determine your public IP. Aborting check.")
        return
    
    now_str = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    in_flight = {}
    working_proxies = {'all': set(), 'http': set(), 'socks4': set(), 'socks5': set()}
    input_file_handle = None
    
    executor = ThreadPoolExecutor(max_workers=args.threads)

    try:
        input_file_handle = open(input_filename, 'r', encoding='utf-8')
        
        print(f"[INFO] Your public IP is: {checker.ip}")
        print(f"--- Starting check from '{input_filename}' with {args.threads} workers and a {timeout}s timeout ---")

        for line in input_file_handle:
            proxy = line.strip()
            if not proxy or proxy.startswith('#'):
                continue

            future = executor.submit(check_and_format_proxy, checker, proxy)
            in_flight[future] = proxy

            if len(in_flight) >= args.threads * 2:
                future_done = next(as_completed(in_flight))
                proxy_from_future = in_flight.pop(future_done)
                try:
                    result = future_done.result()
                    if result:
                        proxy_line, details = result
                        working_proxies['all'].add(proxy_line)
                        for proto in details.get('protocols', []):
                            if proto in working_proxies: working_proxies[proto].add(proxy_line)
                        print(f"\n[SUCCESS] Proxy: {proxy_line:<22} | Anonymity: {details['anonymity']:<11} | Protocols: {','.join(details['protocols']):<15} | Timeout: {details['timeout']}ms")
                        if len(working_proxies['all']) % SAVE_BATCH_SIZE == 0:
                            _save_working_proxies(working_proxies, args.prepend_protocol, now_str)
                    # else:
                    #     print(".", end="", flush=True)
                except Exception as exc:
                    print(f"\n[ERROR] An exception occurred while checking proxy {proxy_from_future}: {exc}")
        
        print("\n[INFO] All proxies have been submitted. Waiting for the last checks to complete...")
        for future_done in as_completed(in_flight):
            proxy_from_future = in_flight.pop(future_done)
            try:
                result = future_done.result()
                if result:
                    proxy_line, details = result
                    working_proxies['all'].add(proxy_line)
                    for proto in details.get('protocols', []):
                        if proto in working_proxies: working_proxies[proto].add(proxy_line)
                    print(f"\n[SUCCESS] Proxy: {proxy_line:<22} | Anonymity: {details['anonymity']:<11} | Protocols: {','.join(details['protocols']):<15} | Timeout: {details['timeout']}ms")
                    if len(working_proxies['all']) % SAVE_BATCH_SIZE == 0:
                        _save_working_proxies(working_proxies, args.prepend_protocol, now_str)
                # else:
                #     print(".", end="", flush=True)
            except Exception as exc:
                print(f"\n[ERROR] An exception occurred while checking proxy {proxy_from_future}: {exc}")

    except KeyboardInterrupt:
        print("\n\n[INTERRUPTED] User stopped the script. Shutting down threads immediately...")
        executor.shutdown(wait=False, cancel_futures=True)
        
        # here is the new logic for handling the resume file name
        if "-resume" in input_filename:
            resume_filename = input_filename
            print(f"[INFO] Overwriting resume file '{resume_filename}'...")
        else:
            base, ext = os.path.splitext(input_filename)
            resume_filename = f"{base}-resume{ext}"
            print(f"[INFO] Creating resume file '{resume_filename}'...")

        with open(resume_filename, 'w', encoding='utf-8') as f_out:
            for proxy in in_flight.values():
                f_out.write(proxy + '\n')
            
            if input_file_handle and not input_file_handle.closed:
                for line in input_file_handle:
                    f_out.write(line)
        print(f"[SUCCESS] Resume file updated. To continue, run the script with --file {resume_filename}")
    
    except Exception as e:
        print(f"\n[ERROR] An unexpected error occurred: {e}")
        executor.shutdown(wait=False, cancel_futures=True)

    finally:
        if input_file_handle and not input_file_handle.closed:
            input_file_handle.close()

        print(f"\n\n--- Check Finished or Interrupted ---")
        total_found = len(working_proxies['all'])
        print(f"Found {total_found} working proxies in total.")
        if total_found > 0:
            print(f"[INFO] Performing final save...")
            _save_working_proxies(working_proxies, args.prepend_protocol, now_str, is_final=True)
            print(f"[SUCCESS] Final lists saved.")
        else:
            print("[INFO] No working proxies were found to save.")
            
if __name__ == "__main__":
    main()