import time
import random
from typing import List
from helper.request_utils import get_with_retry

# --- Configuration for Geonode API and polite scraping ---
API_BASE_URL = "https://proxylist.geonode.com/api/proxy-list"
API_LIMIT = 500  # The maximum number of results per page

# Delay settings to avoid being rate-limited
BASE_DELAY_SECONDS = 0.5
RANDOM_DELAY_RANGE = (0.1, 0.5)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36'
}

def scrape_from_geonode_api(verbose: bool = False, compliant_mode: bool = True) -> List[str]:
    """
    Fetches all proxies from the Geonode API by handling pagination.

    It iterates through pages until the API returns no more proxies, with
    a polite delay between each request.

    Args:
        verbose: If True, prints detailed status messages.
        compliant_mode: If False (aggressive mode), limits pagination to page 8.

    Returns:
        A list of unique proxy strings in 'ip:port' format.
    """
    if verbose:
        print("\n[RUNNING] 'Geonode' scraper has started.", flush=True)

    all_proxies = set()
    page = 1
    max_page = None if compliant_mode else 8

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
            print(f"[INFO] Fetching Geonode API page {page}...", flush=True)

        try:
            response = get_with_retry(url=API_BASE_URL, headers=HEADERS, timeout=20, verbose=verbose, params=params)
            api_data = response.json()
            proxies_on_page = api_data.get('data', [])

            # If the 'data' key is empty or missing, we've reached the end
            if not proxies_on_page:
                if verbose:
                    print("[INFO]   ... No more proxies found. Stopping Geonode scrape.", flush=True)
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
                print(f"[INFO]   ... Found {new_proxies_count} new unique proxies. Total unique: {len(all_proxies)}", flush=True)

            # Prepare for the next iteration
            page += 1

            # Stop if we've reached the max page limit (non-compliant mode)
            if max_page is not None and page > max_page:
                if verbose:
                    print(f"[INFO]   ... Reached page limit ({max_page}) in aggressive mode. Stopping.", flush=True)
                break

            # --- Rate-limiting logic ---
            # Wait before the next request to be polite
            sleep_duration = BASE_DELAY_SECONDS + random.uniform(*RANDOM_DELAY_RANGE)
            if verbose:
                print(f"[INFO]   ... Waiting for {sleep_duration:.2f} seconds.", flush=True)
            time.sleep(sleep_duration)

        except (ValueError, KeyError) as e:
            if verbose:
                print(f"[ERROR] Could not parse JSON response from Geonode on page {page}: {e}", flush=True)
            break # Stop if the JSON is malformed
        except Exception:
            break # Stop on any network-related error

    return sorted(list(all_proxies))
