import requests
from typing import List

# The specific API URL provided in the request
API_URL = "https://api.proxyscrape.com/v2/?request=displayproxies&timeout=20000&country=all&ssl=all&anonymity=all"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
}

def fetch_from_api(verbose: bool = False) -> List[str]:
    """
    Fetches proxies from the ProxyScrape.com API.

    Args:
        verbose: If True, prints status messages.

    Returns:
        A list of proxy strings in 'ip:port' format, or an empty list on failure.
    """
    if verbose:
        print("[INFO] Fetching proxies from ProxyScrape API...")
    
    try:
        response = requests.get(API_URL, headers=HEADERS, timeout=25)
        response.raise_for_status() # Check for HTTP errors

        # The API returns plain text with one proxy per line.
        # We split the text by newlines and filter out any empty lines.
        proxies = [line for line in response.text.strip().split('\n') if line]

        if verbose:
            print(f"[INFO]   ... Found {len(proxies)} proxies from the API.")
        return proxies

    except requests.exceptions.RequestException as e:
        if verbose:
            print(f"[ERROR] Could not fetch proxies from API: {e}")
        return [] # Return an empty list on error