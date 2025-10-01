import time
import random
import re
from typing import List
from helper.request_utils import get_with_retry

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
        response = get_with_retry(url=ARCHIVE_LIST_URL, headers=HEADERS, timeout=20, verbose=verbose, verify=False)
        archive_data = response.json()

        if not archive_data.get("success") or not archive_data.get("data", {}).get("items"):
            if verbose:
                print("[ERROR] CheckerProxy archive list API did not return a successful or valid response.")
            return []

        dates_to_scrape = [item['date'] for item in archive_data['data']['items']]
        total_dates = len(dates_to_scrape)
        if verbose:
            print(f"[INFO] CheckerProxy: Found {total_dates} archive dates to process.")

    except Exception as e:
        if verbose:
            print(f"[ERROR] CheckerProxy: Failed to fetch archive list after retries: {e}")
        return []

    # --- Step 2: Scrape each daily list ---
    for idx, date in enumerate(dates_to_scrape, start=1):
        if verbose:
            print(f"[INFO] CheckerProxy: Fetching date {date} ({idx}/{total_dates})...")

        try:
            url = DAILY_PROXY_URL_TEMPLATE.format(date=date)
            response = get_with_retry(url=url, headers=HEADERS, timeout=20, verbose=verbose, verify=False)
            daily_data = response.json()

            if not daily_data.get("success") or not daily_data.get("data", {}).get("items"):
                if verbose:
                    print(f"[WARN] CheckerProxy: No valid data for {date}. Skipping.")
                continue

            items = daily_data['data']['items']
            valid_count = 0
            invalid_count = 0

            for item in items:
                proxy_str = item.get('address')
                if proxy_str and PROXY_VALIDATION_REGEX.match(proxy_str):
                    all_proxies.add(proxy_str)
                    valid_count += 1
                else:
                    invalid_count += 1

            if verbose:
                print(f"[INFO]   ... Found {len(items)} entries. {valid_count} valid, {invalid_count} invalid.")

        except Exception as e:
            if verbose:
                print(f"[WARN] CheckerProxy: Skipping date {date} due to error: {e}")
            continue

        sleep_duration = BASE_DELAY_SECONDS + random.uniform(*RANDOM_DELAY_RANGE)
        time.sleep(sleep_duration)

    if verbose:
        duplicates_removed = sum(len(daily_data.get("data", {}).get("items", [])) for daily_data in []) - len(all_proxies)
        print(f"[INFO] CheckerProxy: Finished. Processed {len(all_proxies)} unique proxies.")

    return sorted(list(all_proxies))
