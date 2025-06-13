import requests
import time
import random
from typing import List

# --- Configuration for Geonode API and polite scraping ---
API_BASE_URL = "https://proxylist.geonode.com/api/proxy-list"
API_LIMIT = 500  # The maximum number of results per page

# Delay settings to avoid being rate-limited
BASE_DELAY_SECONDS = 1.5
RANDOM_DELAY_RANGE = (0.5, 1.0)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36'
}

def scrape_from_geonode_api(verbose: bool = False) -> List[str]:
    """
    Fetches all proxies from the Geonode API by handling pagination.

    It iterates through pages until the API returns no more proxies, with
    a polite delay between each request.

    Args:
        verbose: If True, prints detailed status messages.

    Returns:
        A list of unique proxy strings in 'ip:port' format.
    """
    all_proxies = set()
    page = 1

    while True:
        # Define parameters for the API request
        params = {
            'limit': API_LIMIT,
            'page': page,
            'sort_by': 'lastChecked',
            'sort_type': 'desc',
            'speed': 'fast', # As per the requested URL
        }

        if verbose:
            print(f"[INFO] Fetching Geonode API page {page}...")

        try:
            response = requests.get(API_BASE_URL, params=params, headers=HEADERS, timeout=20)
            response.raise_for_status()

            api_data = response.json()
            proxies_on_page = api_data.get('data', [])

            # If the 'data' key is empty or missing, we've reached the end
            if not proxies_on_page:
                if verbose:
                    print("[INFO]   ... No more proxies found. Stopping Geonode scrape.")
                break # Exit the while loop

            # Process the found proxies
            initial_count = len(all_proxies)
            for proxy_info in proxies_on_page:
                ip = proxy_info.get('ip')
                port = proxy_info.get('port')
                if ip and port:
                    all_proxies.add(f"{ip}:{port}")
            
            new_proxies_count = len(all_proxies) - initial_count
            if verbose:
                print(f"[INFO]   ... Found {new_proxies_count} new unique proxies. Total unique: {len(all_proxies)}")

            # Prepare for the next iteration
            page += 1
            
            # --- Rate-limiting logic ---
            # Wait before the next request to be polite
            sleep_duration = BASE_DELAY_SECONDS + random.uniform(*RANDOM_DELAY_RANGE)
            if verbose:
                print(f"[INFO]   ... Waiting for {sleep_duration:.2f} seconds.")
            time.sleep(sleep_duration)

        except requests.exceptions.RequestException as e:
            if verbose:
                print(f"[ERROR] Could not fetch Geonode API on page {page}: {e}")
            break # Stop on any network-related error
        except (ValueError, KeyError) as e:
            if verbose:
                print(f"[ERROR] Could not parse JSON response from Geonode on page {page}: {e}")
            break # Stop if the JSON is malformed

    return sorted(list(all_proxies))