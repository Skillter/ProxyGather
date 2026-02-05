import time
import random
import re
from datetime import datetime, timedelta
from typing import List
from helper.request_utils import get_with_retry

# Define the base URLs for the API
ARCHIVE_LIST_URL = "https://api.checkerproxy.net/v1/landing/archive/"
DAILY_PROXY_URL_TEMPLATE = "https://api.checkerproxy.net/v1/landing/archive/{date}"

# Regex to validate proxy format (IP:PORT)
PROXY_VALIDATION_REGEX = re.compile(r"^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{1,5})$")

# Standard headers to mimic a browser
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
}

# Polite scraping configuration
BASE_DELAY_SECONDS = 0.3
RANDOM_DELAY_RANGE = (0.1, 0.4)


def scrape_checkerproxy_archive(verbose: bool = True) -> List[str]:
    """
    Scrapes all available proxy lists from the checkerproxy.net API archive.

    Args:
        verbose: If True, prints detailed status messages to the console.

    Returns:
        A list of all unique, validated proxies found across all archived dates.
    """
    all_proxies = set()
    
    print("\n[RUNNING] 'CheckerProxy' scraper has started.", flush=True)

    # --- Step 1: Get the list of available dates ---
    try:
        response = get_with_retry(url=ARCHIVE_LIST_URL, headers=HEADERS, timeout=20, verbose=verbose)
        archive_data = response.json()

        if not archive_data.get("success") or not archive_data.get("data", {}).get("items"):
            if verbose:
                print("[ERROR] CheckerProxy archive list API did not return a successful or valid response.", flush=True)
            return []

        dates_to_scrape = [item['date'] for item in archive_data['data']['items']]
        total_dates = len(dates_to_scrape)
        if verbose:
            print(f"[INFO] CheckerProxy: Found {total_dates} archive dates to process.", flush=True)

    except Exception as e:
        if verbose:
            print(f"[ERROR] CheckerProxy: Failed to fetch archive list after retries: {e}", flush=True)
        return []

    # --- Step 2: Scrape each daily list ---
    for idx, date in enumerate(dates_to_scrape, start=1):
        if verbose:
            print(f"[INFO] CheckerProxy: Fetching date {date} ({idx}/{total_dates})...", flush=True)

        try:
            url = DAILY_PROXY_URL_TEMPLATE.format(date=date)
            response = get_with_retry(url=url, headers=HEADERS, timeout=20, verbose=verbose)
            daily_data = response.json()

            if not daily_data.get("success"):
                if verbose:
                    print(f"[WARN] CheckerProxy: API returned unsuccessful for {date}. Skipping.", flush=True)
                continue

            proxy_list = daily_data.get('data', {}).get('proxyList', [])
            if not proxy_list:
                if verbose:
                    print(f"[INFO] CheckerProxy: No proxies found for {date}.", flush=True)
                continue

            valid_count = 0
            invalid_count = 0

            for proxy_str in proxy_list:
                if proxy_str and PROXY_VALIDATION_REGEX.match(proxy_str):
                    all_proxies.add(proxy_str)
                    valid_count += 1
                else:
                    invalid_count += 1

            if verbose:
                print(f"[INFO]   ... Found {len(proxy_list)} entries. {valid_count} valid, {invalid_count} invalid.", flush=True)

        except Exception as e:
            if verbose:
                print(f"[WARN] CheckerProxy: Skipping date {date} due to error: {e}", flush=True)
            continue

        sleep_duration = BASE_DELAY_SECONDS + random.uniform(*RANDOM_DELAY_RANGE)
        time.sleep(sleep_duration)

    if verbose:
        print(f"[INFO] CheckerProxy: Finished. Processed {len(all_proxies)} unique proxies.", flush=True)

    return sorted(list(all_proxies))
