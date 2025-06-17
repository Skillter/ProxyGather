import json
import sys
import argparse
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed, wait
from datetime import datetime
import glob

from checker.proxy_checker import ProxyChecker

SAVE_BATCH_SIZE = 25

def _save_working_proxies(proxy_data, prepend_protocol, output_base, is_final=False):
    """Saves the working proxies, creating the output directory if needed."""
    # Split the base name and extension to insert the protocol correctly
    base, ext = os.path.splitext(output_base)
    # If the user didn't provide an extension, default to .txt
    if not ext:
        ext = ".txt"

    # check once for the base directory
    directory = os.path.dirname(base)
    if directory and not os.path.exists(directory):
        print(f"[INFO] Creating output directory: {directory}")
        os.makedirs(directory)

    for protocol, proxies_set in proxy_data.items():
        if not proxies_set: continue
        # Construct the filename correctly: e.g., 'path/to/base-http.txt'
        filename = f"{base}-{protocol}{ext}"
        try:
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

def load_proxies_from_patterns(patterns: list) -> list:
    """
    Finds all files matching the given patterns, loads all proxies,
    and returns a de-duplicated list.
    """
    all_files = set()
    for pattern in patterns:
        all_files.update(glob.glob(pattern))

    if not all_files:
        print("[ERROR] No files found matching the specified patterns.")
        sys.exit(1)
        
    print(f"[INFO] Found {len(all_files)} files to process:")
    for f in sorted(list(all_files)):
        print(f"  - {f}")

    unique_proxies = set()
    for filepath in all_files:
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    proxy = line.strip()
                    if proxy and not proxy.startswith('#'):
                        unique_proxies.add(proxy)
        except IOError as e:
            print(f"[WARN] Could not read file {filepath}: {e}")
            
    print(f"[INFO] Loaded {len(unique_proxies)} unique proxies from all source files.")
    return sorted(list(unique_proxies))


def main():
    parser = argparse.ArgumentParser(
        description="A high-performance, memory-efficient proxy checker that can be safely interrupted and resumed."
    )
    parser.add_argument(
        '--input', 
        nargs='+',
        default=['scraped-proxies.txt'], 
        help="One or more input files or file patterns (e.g., 'proxies-*.txt')."
    )
    parser.add_argument(
        '--output',
        type=str,
        default=None,
        help="The base name for output files (e.g., 'results/verified'). If not provided, a timestamped name will be used."
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

    try:
        timeout = parse_timeout(args.timeout)
        if timeout <= 0: timeout = 1.0
    except ValueError:
        print(f"[ERROR] Invalid timeout format: {args.timeout}. Please use formats like '500ms', '10s', or '8'.")
        return

    all_unique_proxies = load_proxies_from_patterns(args.input)
    if not all_unique_proxies:
        print("[ERROR] No proxies to check after loading files. Exiting.")
        return

    print("\n[INFO] Initializing Proxy Checker...")
    checker = ProxyChecker(timeout=timeout)
    if not checker.ip:
        print("[ERROR] Could not determine your public IP. Aborting check.")
        return
    
    if args.output:
        output_base_name = args.output
    else:
        now_str = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        output_base_name = f"working-proxies-{now_str}"

    in_flight = {}
    submitted_proxies = set()
    working_proxies = {'all': set(), 'http': set(), 'socks4': set(), 'socks5': set()}
    
    executor = ThreadPoolExecutor(max_workers=args.threads)

    try:
        print(f"[INFO] Your public IP is: {checker.ip}")
        print(f"--- Starting check on {len(all_unique_proxies)} unique proxies with {args.threads} workers and a {timeout}s timeout ---")

        for proxy in all_unique_proxies:
            future = executor.submit(check_and_format_proxy, checker, proxy)
            in_flight[future] = proxy
            submitted_proxies.add(proxy)

            while len(in_flight) >= args.threads * 2:
                done_futures, _ = wait(in_flight.keys(), return_when='FIRST_COMPLETED')
                for future_done in done_futures:
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
                                _save_working_proxies(working_proxies, args.prepend_protocol, output_base_name)
                        else:
                            print(".", end="", flush=True)
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
                        _save_working_proxies(working_proxies, args.prepend_protocol, output_base_name)
                else:
                    print(".", end="", flush=True)
            except Exception as exc:
                print(f"\n[ERROR] An exception occurred while checking proxy {proxy_from_future}: {exc}")

    except KeyboardInterrupt:
        print("\n\n[INTERRUPTED] User stopped the script. Shutting down threads immediately...")
        executor.shutdown(wait=False, cancel_futures=True)
        
        proxies_to_recheck = set(all_unique_proxies) - submitted_proxies
        proxies_to_recheck.update(in_flight.values())
        
        if args.output:
             resume_filename = f"{args.output}-resume.txt"
        else:
             resume_filename = f"proxies-to-resume-{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.txt"
             
        print(f"[INFO] Saving {len(proxies_to_recheck)} remaining proxies to '{resume_filename}'...")
        
        try:
            # create the directory for the resume file if it doesn't exist
            directory = os.path.dirname(resume_filename)
            if directory and not os.path.exists(directory):
                os.makedirs(directory)

            with open(resume_filename, 'w', encoding='utf-8') as f_out:
                for proxy in sorted(list(proxies_to_recheck)):
                    f_out.write(proxy + '\n')
            
            print(f"[SUCCESS] Resume file created. To continue, run with --input {resume_filename}")
        except Exception as e:
            print(f"\n[ERROR] Could not save resume file: {e}")

    except Exception as e:
        print(f"\n[ERROR] An unexpected error occurred: {e}")
        executor.shutdown(wait=False, cancel_futures=True)

    finally:
        print(f"\n\n--- Check Finished or Interrupted ---")
        total_found = len(working_proxies['all'])
        print(f"Found {total_found} working proxies in total.")
        if total_found > 0:
            print(f"[INFO] Performing final save...")
            _save_working_proxies(working_proxies, args.prepend_protocol, output_base_name, is_final=True)
            print(f"[SUCCESS] Final lists saved.")
        else:
            print("[INFO] No working proxies were found to save.")
            
if __name__ == "__main__":
    main()