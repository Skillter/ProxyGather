import json
import re
import ssl
import time
import urllib.request
from typing import List
from helper.request_utils import get_with_retry

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


def fetch_with_ssl_adapter(url: str, headers: dict, timeout: int = 30, verbose: bool = False) -> str:
    """
    Fetches URL using urllib with custom SSL context to handle connection issues.
    Falls back to requests with retry if urllib fails.
    """
    # Create SSL context with TLS 1.2+ support
    ssl_context = ssl.create_default_context()
    ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    # Build request
    req = urllib.request.Request(url, headers=headers)
    
    last_exception = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, context=ssl_context, timeout=timeout) as response:
                return response.read().decode('utf-8')
        except urllib.error.HTTPError as e:
            # HTTP errors (4xx, 5xx) - don't retry
            raise Exception(f"HTTP {e.code}: {e.reason}") from e
        except Exception as e:
            last_exception = e
            if verbose:
                print(f"[WARN] GoLogin: Request attempt {attempt + 1} failed: {e}", flush=True)
            if attempt < 2:
                time.sleep(1 * (attempt + 1))
    
    # All attempts failed
    raise last_exception if last_exception else Exception("Unknown error")

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
        print("\n[RUNNING] 'GoLogin/Geoxy' scraper has started.", flush=True)

    # --- Step 1: Fetch the HTML page to find the token ---
    try:
        if verbose:
            print(f"[INFO] GoLogin: Fetching auth token from {GOLOGIN_URL}", flush=True)
        
        response = get_with_retry(url=GOLOGIN_URL, headers=HEADERS, timeout=20, verbose=verbose)
        html_content = response.text
        
    except Exception as e:
        raise Exception(f"Could not fetch the initial page from GoLogin: {e}") from e

    # --- Step 2: Extract the Authorization token using regex ---
    match = AUTH_TOKEN_REGEX.search(html_content)
    if not match:
        raise Exception("Could not find the Authorization token on the GoLogin page.")
        
    auth_token = match.group(1)
    if verbose:
        # To avoid printing the full sensitive token, just confirm it was found.
        print("[INFO] GoLogin: Successfully extracted Authorization token.", flush=True)

    # --- Step 3: Use the token to fetch proxies from the API ---
    api_headers = {
        'Authorization': auth_token,
        'Content-Type': 'application/json',
        'User-Agent': HEADERS['User-Agent'] # It's good practice to keep the User-Agent
    }
    
    try:
        if verbose:
            print(f"[INFO] Geoxy API: Fetching proxies from {GEOXY_API_URL}", flush=True)
        
        # Use urllib with custom SSL context to handle connection issues
        response_text = fetch_with_ssl_adapter(url=GEOXY_API_URL, headers=api_headers, timeout=30, verbose=verbose)
        proxy_data = json.loads(response_text)
        
    except ValueError as e: # Catches JSON decoding errors
        raise Exception(f"Failed to decode JSON from Geoxy API response: {e}") from e
    except Exception as e:
        raise Exception(f"Could not fetch proxies from the Geoxy API: {e}") from e

    # --- Step 4: Parse the JSON response and extract proxy addresses ---
    all_proxies = set()
    if not isinstance(proxy_data, list):
        if verbose:
            print("[WARN] Geoxy API: Response was not a list as expected.", flush=True)
        return []

    for item in proxy_data:
        address = item.get("address")
        # Ensure the address is a valid string before adding
        if isinstance(address, str) and ":" in address:
            all_proxies.add(address)
            
    if verbose:
        print(f"[INFO] Geoxy API: Finished. Found {len(all_proxies)} unique proxies.", flush=True)

    return sorted(list(all_proxies))

