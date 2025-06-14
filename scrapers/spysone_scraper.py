
import time
import random
import requests
from typing import List

# Import the reusable components from our other scraper module
from .proxy_scraper import extract_proxies_from_content, DEFAULT_HEADERS

# URL for the POST requests
SPYSONE_URL = "https://spys.one/en/free-proxy-list/"

xx0 = '654b5e2c40e457c7b2c0803e7e77fe2d'

# Payloads provided for the 7 different requests
PAYLOADS = [
    {'xx0': xx0, 'xpp': '5', 'xf1': '0', 'xf2': '0', 'xf4': '0', 'xf5': '2'},
    # The xx0 value for request 2 is different in your prompt. I will use the one you provided.
    {'xx0': xx0, 'xpp': '5', 'xf1': '2', 'xf2': '2', 'xf4': '0', 'xf5': '1'},
    {'xx0': xx0, 'xpp': '5', 'xf1': '2', 'xf2': '1', 'xf4': '0', 'xf5': '1'},
    {'xx0': xx0, 'xpp': '5', 'xf1': '1', 'xf2': '0', 'xf4': '0', 'xf5': '1'},
    {'xx0': xx0, 'xpp': '5', 'xf1': '2', 'xf2': '0', 'xf4': '0', 'xf5': '1'},
    {'xx0': xx0, 'xpp': '5', 'xf1': '3', 'xf2': '0', 'xf4': '0', 'xf5': '1'},
    {'xx0': xx0, 'xpp': '5', 'xf1': '4', 'xf2': '0', 'xf4': '0', 'xf5': '1'}
]

# Rate limiting settings to be polite
BASE_DELAY_SECONDS = 2
RANDOM_DELAY_RANGE = (0.5, 2.0)

def scrape_from_spysone(verbose: bool = False) -> List[str]:
    """
    NOT WORKING.
    spys.one has some weird anti-scraping session logic.
    Scrapes spys.one by sending multiple POST requests with different payloads.
    Includes rate-limiting to avoid being blocked.

    Args:
        verbose: If True, prints detailed status messages.

    Returns:
        A list of unique proxies found from all requests.
    """
    all_proxies = set()
    # Using a session is more efficient as it reuses the underlying TCP connection
    session = requests.Session()
    session.headers.update(HEADERS)

    for i, payload in enumerate(PAYLOADS):
        page_num = i + 1
        if verbose:
            print(f"[INFO] Scraping Spys.one - request {page_num}/{len(PAYLOADS)}...")

        try:
            response = session.post(SPYSONE_URL, data=payload, timeout=20)
            response.raise_for_status()

            # Use our reusable extraction logic on the response HTML
            newly_found = extract_proxies_from_content(response.text)
            
            if verbose:
                if newly_found:
                    # The `|` operator is a union for sets
                    print(f"[INFO]   ... Found {len(newly_found)} proxies on this page. Total unique: {len(all_proxies | newly_found)}")
                else:
                    print(f"[WARN]   ... No proxies found for request {page_num}.")

            all_proxies.update(newly_found)

        except requests.exceptions.RequestException as e:
            if verbose:
                print(f"[ERROR] Could not fetch Spys.one page {page_num}: {e}")
        
        # Don't wait after the very last request
        if page_num < len(PAYLOADS):
            sleep_duration = BASE_DELAY_SECONDS + random.uniform(*RANDOM_DELAY_RANGE)
            if verbose:
                print(f"[INFO] Waiting for {sleep_duration:.2f} seconds...")
            time.sleep(sleep_duration)

    return sorted(list(all_proxies))