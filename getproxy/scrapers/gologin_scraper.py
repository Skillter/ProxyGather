import requests
import re
from typing import List

# URL to fetch the initial page and find the auth token
GOLOGIN_URL = "https://gologin.com/free-proxy/"

# API endpoint to fetch the proxies from
GEOXY_API_URL = "https://geoxy.io/proxies?count=99999"

# Regex to find the Authorization token in the HTML script tag.
# Looks for 'Authorization': 'some_token' and captures the token.
AUTH_TOKEN_REGEX = re.compile(r"'Authorization':\s*'([^']+)'")

# Standard headers for the initial request
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36'
}

def scrape_from_gologin_api(verbose: bool = False) -> List[str]:
    """
    Scrapes proxies from the geoxy.io API by first extracting the
    required authorization token from the gologin.com website.

    Args:
        verbose: If True, prints detailed status messages.

    Returns:
        A list of unique proxy strings in 'ip:port' format.
    """
    if verbose:
        print("[RUNNING] 'GoLogin/Geoxy' scraper has started.")

    # --- Step 1: Fetch the HTML page to find the token ---
    try:
        if verbose:
            print(f"[INFO] GoLogin: Fetching auth token from {GOLOGIN_URL}")
        
        response = requests.get(GOLOGIN_URL, headers=HEADERS, timeout=20)
        response.raise_for_status()
        html_content = response.text
        
    except requests.exceptions.RequestException as e:
        raise Exception(f"Could not fetch the initial page from GoLogin: {e}") from e

    # --- Step 2: Extract the Authorization token using regex ---
    match = AUTH_TOKEN_REGEX.search(html_content)
    if not match:
        raise Exception("Could not find the Authorization token on the GoLogin page.")
        
    auth_token = match.group(1)
    if verbose:
        # To avoid printing the full sensitive token, just confirm it was found.
        print("[INFO] GoLogin: Successfully extracted Authorization token.")

    # --- Step 3: Use the token to fetch proxies from the API ---
    api_headers = {
        'Authorization': auth_token,
        'Content-Type': 'application/json',
        'User-Agent': HEADERS['User-Agent'] # It's good practice to keep the User-Agent
    }
    
    try:
        if verbose:
            print(f"[INFO] Geoxy API: Fetching proxies from {GEOXY_API_URL}")
        
        response = requests.get(GEOXY_API_URL, headers=api_headers, timeout=30)
        response.raise_for_status()
        proxy_data = response.json()
        
    except requests.exceptions.RequestException as e:
        raise Exception(f"Could not fetch proxies from the Geoxy API: {e}") from e
    except ValueError as e: # Catches JSON decoding errors
        raise Exception(f"Failed to decode JSON from Geoxy API response: {e}") from e

    # --- Step 4: Parse the JSON response and extract proxy addresses ---
    all_proxies = set()
    if not isinstance(proxy_data, list):
        if verbose:
            print("[WARN] Geoxy API: Response was not a list as expected.")
        return []

    for item in proxy_data:
        address = item.get("address")
        # Ensure the address is a valid string before adding
        if isinstance(address, str) and ":" in address:
            all_proxies.add(address)
            
    if verbose:
        print(f"[INFO] Geoxy API: Finished. Found {len(all_proxies)} unique proxies.")

    return sorted(list(all_proxies))