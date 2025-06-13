import json
import sys
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- MODIFIED: Import the checker ---
from checker.proxy_checker import ProxyChecker

# --- Configuration ---
INPUT_FILENAME = "scraped-proxies.txt"
# NOTE: Output filenames are now generated dynamically.
# Adjust this number based on your internet connection and system resources.
MAX_WORKERS = 100
# How often to save progress (after every N working proxies found in the 'all' list)
SAVE_BATCH_SIZE = 25

def _save_working_proxies(proxy_data, prepend_protocol, is_final=False):
    """
    A helper function to save the dictionary of working proxies to their respective files.
    """
    for protocol, proxies_set in proxy_data.items():
        if not proxies_set:
            continue

        filename = f"working-proxies-{protocol}.txt"
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                for proxy in sorted(proxies_set):
                    # --- ADDED: Conditional formatting based on the flag ---
                    if prepend_protocol and protocol != 'all':
                        f.write(f"{protocol}://{proxy}\n")
                    else:
                        f.write(f"{proxy}\n")
        except IOError as e:
            print(f"\n[ERROR] Could not write to output file '{filename}': {e}")
            
    if not is_final:
        total_proxies = len(proxy_data.get('all', set()))
        print(f"\n[PROGRESS] Interim save complete. {total_proxies} total working proxies saved to respective files.")


def check_and_format_proxy(checker, proxy_line):
    """
    A helper function to be run in each thread.
    It checks a single proxy and returns a formatted result or None.
    """
    details = checker.check_proxy(proxy_line)
    if details:
        # If the proxy works, return the original line and its details
        return (proxy_line, details)
    return None

def main():
    # --- ADDED: Command-line argument parser ---
    parser = argparse.ArgumentParser(
        description="A high-performance, multi-threaded proxy checker."
    )
    parser.add_argument(
        '--prepend-protocol', 
        action='store_true', 
        help="Prepend the protocol (e.g., 'http://') to proxies in protocol-specific files."
    )
    args = parser.parse_args()

    proxies_to_check = []
    try:
        with open(INPUT_FILENAME, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    proxies_to_check.append(line)
        if not proxies_to_check:
            print(f"[WARN] Input file '{INPUT_FILENAME}' is empty. Nothing to do.")
            return
    except FileNotFoundError:
        print(f"[ERROR] Input file '{INPUT_FILENAME}' not found.")
        return

    print("[INFO] Initializing Proxy Checker (this may take a moment)...")
    checker = ProxyChecker()
    if not checker.ip:
        print("[ERROR] Could not determine your public IP. Aborting check.")
        return
    
    print(f"[INFO] Your public IP is: {checker.ip}")
    print(f"--- Starting check for {len(proxies_to_check)} proxies with {MAX_WORKERS} workers ---")

    # --- MODIFIED: Use a dictionary of sets to hold proxies by protocol ---
    working_proxies = {
        'all': set(),
        'http': set(),
        'socks4': set(),
        'socks5': set()
    }
    
    try:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_proxy = {
                executor.submit(check_and_format_proxy, checker, proxy): proxy 
                for proxy in proxies_to_check
            }

            for future in as_completed(future_to_proxy):
                proxy = future_to_proxy[future]
                try:
                    result = future.result()
                    
                    if result:
                        proxy_line, details = result
                        
                        # --- MODIFIED: Populate the dictionary of proxy sets ---
                        working_proxies['all'].add(proxy_line)
                        for proto in details.get('protocols', []):
                            if proto in working_proxies:
                                working_proxies[proto].add(proxy_line)

                        print(f"\n[SUCCESS] Proxy: {proxy_line:<22} | Anonymity: {details['anonymity']:<11} | Protocols: {','.join(details['protocols']):<15} | Timeout: {details['timeout']}ms")
                        
                        if len(working_proxies['all']) % SAVE_BATCH_SIZE == 0:
                            _save_working_proxies(working_proxies, args.prepend_protocol)

                    else:
                        print(".", end="", flush=True)

                except Exception as exc:
                    print(f"\n[ERROR] An exception occurred while checking proxy {proxy}: {exc}")
    
    except KeyboardInterrupt:
        print("\n\n[INTERRUPTED] User stopped the script. Finalizing progress...")
    
    finally:
        print(f"\n\n--- Check Finished or Interrupted ---")
        total_found = len(working_proxies['all'])
        print(f"Found {total_found} working proxies in total.")

        if total_found > 0:
            print(f"[INFO] Performing final save...")
            _save_working_proxies(working_proxies, args.prepend_protocol, is_final=True)
            print(f"[SUCCESS] Final lists saved.")
        else:
            print("[INFO] No working proxies were found to save.")
            
if __name__ == "__main__":
    main()