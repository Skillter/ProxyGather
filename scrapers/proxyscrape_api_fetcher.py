import requests
from typing import List
import time

# The base URL for the API, we'll add the skip parameter in the loop
API_URL_TEMPLATE = "https://api.proxyscrape.com/v4/free-proxy-list/get?request=displayproxies&timeout=8000&country=all&ssl=all&anonymity=all"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
}

def fetch_from_api(verbose: bool = False) -> List[str]:
    """
    Fetches all proxies from the ProxyScrape.com API by iterating through pages
    using the 'skip' parameter.

    Args:
        verbose: If True, prints status messages.

    Returns:
        A list of proxy strings in 'ip:port' format, or an empty list on failure.
    """
    if verbose:
        print("[INFO] Fetching proxies from ProxyScrape API (paginated)...")
    
    all_proxies = set()
    skip = 0
    page_num = 1
    
    while True:
        # we construct the url with the current skip value
        paginated_url = f"{API_URL_TEMPLATE}&skip={skip}"
        
        try:
            response = requests.get(paginated_url, headers=HEADERS, timeout=25)
            response.raise_for_status() # check for http errors

            # the api returns plain text with one proxy per line
            proxies_on_page = [line for line in response.text.strip().splitlines() if line]

            # if the page is empty, we've reached the end
            if not proxies_on_page:
                if verbose:
                    print("[INFO]   ... No more proxies found. Stopping.")
                break

            all_proxies.update(proxies_on_page)
            
            if verbose:
                print(f"[INFO]   ... Found {len(proxies_on_page)} proxies on page {page_num}. Total unique: {len(all_proxies)}")

            # prepare for the next iteration
            skip += 2000
            page_num += 1
            time.sleep(0.5) # a small delay to be nice to the api

        except requests.exceptions.RequestException as e:
            if verbose:
                print(f"[ERROR] Could not fetch proxies from API on page {page_num}: {e}")
            break # stop if there's an error

    if verbose:
        print(f"[INFO] ProxyScrape API: Finished. Found a total of {len(all_proxies)} unique proxies.")
        
    return list(all_proxies)