import requests
import time
import random
import re
from typing import List

# Define the base URLs for the API
ARCHIVE_LIST_URL = "https://api.checkerproxy.net/v1/landing/archive/"
DAILY_PROXY_URL_TEMPLATE = "https://api.checkerproxy.net/v1/landing/archive/{date}"

# Regex to validate proxy format (IP:PORT).
# This ensures we only capture validly formatted strings.
# ^ asserts position at start of the string
# (\d{1,3}\.){3}\d{1,3} matches the IP address format
# : matches the literal ":"
# \d{1,5} matches the port number (1 to 5 digits)
# $ asserts position at the end of the string
PROXY_VALIDATION_REGEX = re.compile(r"^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{1,5})$")

# Standard headers to mimic a browser
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
}

# Polite scraping configuration
BASE_DELAY_SECONDS = 1
RANDOM_DELAY_RANGE = (0.2, 0.8)

def scrape_checkerproxy_archive(verbose: bool = True) -> List[str]:
    """
    Scrapes all available proxy lists from the checkerproxy.net API archive.
    It handles multiple proxy list formats, validates each entry with regex,
    and provides detailed logging.

    Args:
        verbose: If True, prints detailed status messages to the console.

    Returns:
        A list of all unique, validated proxies found across all archived dates.
    """
    all_proxies = set()
    
    # This function is called from a concurrent setup, so print a starting message.
    print("[RUNNING] 'CheckerProxy' scraper has started.")

    # --- Step 1: Get the list of available dates ---
    try:
        response = requests.get(ARCHIVE_LIST_URL, headers=HEADERS, timeout=20)
        response.raise_for_status()
        archive_data = response.json()

        if not archive_data.get("success") or not archive_data.get("data", {}).get("items"):
            if verbose:
                print("[ERROR] CheckerProxy archive list API did not return a successful or valid response.")
            return []
        
        dates_to_scrape = [item['date'] for item in archive_data['data']['items']]
        total_dates = len(dates_to_scrape)
        if verbose:
            print(f"[INFO] CheckerProxy: Found {total_dates} archive dates to process.")

    except requests.exceptions.RequestException as e:
        raise Exception(f"Could not fetch CheckerProxy archive list: {e}") from e
    except ValueError as e: # Catches JSON decoding errors
        raise Exception(f"Failed to decode JSON from CheckerProxy archive list: {e}") from e

    # --- Step 2: Scrape each daily list ---
    total_valid_entries_processed = 0  # Keep a running total of all valid entries
    
    for i, date in enumerate(dates_to_scrape):
        if verbose:
            print(f"[INFO] CheckerProxy: Fetching date {date} ({i + 1}/{total_dates})...")
        
        try:
            response = requests.get(DAILY_PROXY_URL_TEMPLATE.format(date=date), headers=HEADERS, timeout=20)
            response.raise_for_status()
            daily_data = response.json()

            if daily_data.get("success"):
                raw_proxy_data = daily_data.get("data", {}).get("proxyList")
                proxies_to_process = []
                
                # Handle both list and dictionary (object) formats for the proxy list
                if isinstance(raw_proxy_data, list):
                    proxies_to_process = raw_proxy_data
                elif isinstance(raw_proxy_data, dict):
                    proxies_to_process = raw_proxy_data.values()
                
                if not proxies_to_process:
                    if verbose:
                        print(f"[WARN]   ... No proxy entries found for {date}.")
                    continue

                # Regex validation for each proxy string
                initial_count = len(proxies_to_process)
                validated_proxies = {
                    p for p in proxies_to_process 
                    if isinstance(p, str) and PROXY_VALIDATION_REGEX.match(p)
                }
                
                valid_count = len(validated_proxies)
                total_valid_entries_processed += valid_count  # Add to running total
                invalid_count = initial_count - valid_count
                
                if verbose:
                    print(f"[INFO]   ... Found {initial_count} entries. {valid_count} valid, {invalid_count} invalid.")

                all_proxies.update(validated_proxies)
            else:
                 if verbose:
                    print(f"[WARN]   ... API reported failure for date {date}.")

        except requests.exceptions.RequestException as e:
            if verbose: print(f"[ERROR]  ... Could not fetch proxy list for {date}: {e}")
            continue # Move to the next date
        except ValueError:
             if verbose: print(f"[ERROR]  ... Failed to decode JSON for date {date}.")
             continue

        # Polite Rate-limiting: Wait before hitting the next page
        # Don't sleep on the very last item.
        if i < total_dates - 1:
            sleep_duration = BASE_DELAY_SECONDS + random.uniform(*RANDOM_DELAY_RANGE)
            time.sleep(sleep_duration)

    # --- Final summary log for this specific scraper ---
    final_unique_count = len(all_proxies)
    if verbose:
        duplicates_found = total_valid_entries_processed - final_unique_count
        print(f"[INFO] CheckerProxy: Finished. Processed {total_valid_entries_processed} valid entries "
              f"and found {final_unique_count} unique proxies ({duplicates_found} duplicates removed).")

    return sorted(list(all_proxies))