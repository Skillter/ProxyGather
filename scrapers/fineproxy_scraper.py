import re
import time
import requests
from typing import List
from scrapers.proxy_scraper import extract_proxies_from_content

MAIN_URL = "https://fineproxy.org/free-proxy/"
API_URL = "https://fineproxy.org/wp-admin/admin-ajax.php"

# Mimic a modern browser to avoid 403 Forbidden (Cloudflare)
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Referer': 'https://www.google.com/',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'cross-site',
    'Sec-Fetch-User': '?1',
    'Cache-Control': 'max-age=0',
    'Connection': 'keep-alive'
}

# Regex to extract the nonce from the JavaScript object in the HTML
# Looks for: "nonce":"f99f9c33e7"
NONCE_REGEX = re.compile(r'"nonce"\s*:\s*"([^"]+)"')

def scrape_from_fineproxy(verbose: bool = True) -> List[str]:
    """
    Scrapes proxies from FineProxy.org using a session to handle cookies.
    1. Extracts proxies from the HTML of the main page.
    2. Extracts a 'nonce' token from the HTML source.
    3. Uses the token to query their internal AJAX API for a plain text list.
    """
    if verbose:
        print("\n[RUNNING] 'FineProxy' scraper has started.", flush=True)

    all_proxies = set()
    session = requests.Session()
    session.headers.update(HEADERS)

    # --- Step 1: Fetch Main Page ---
    if verbose:
        print(f"[INFO] FineProxy: Fetching main page {MAIN_URL}...", flush=True)

    try:
        response = session.get(MAIN_URL, timeout=20)
        
        # Check for blocking
        if response.status_code == 403:
            if verbose:
                print("[ERROR] FineProxy: Access denied (403). The site is likely blocking 'requests'.", flush=True)
            return []

        response.raise_for_status()
        html_content = response.text

        # Extract proxies directly from the HTML (general regex)
        initial_proxies = extract_proxies_from_content(html_content, verbose=False)
        all_proxies.update(initial_proxies)

        if verbose:
            print(f"[INFO]   ... Found {len(initial_proxies)} proxies on the main HTML page.", flush=True)

        # --- Step 2: Extract Nonce ---
        match = NONCE_REGEX.search(html_content)
        if not match:
            if verbose:
                print("[WARN] FineProxy: Could not find 'nonce' token in HTML. Skipping API scrape.", flush=True)
            return sorted(list(all_proxies))
        
        nonce = match.group(1)
        if verbose:
            print(f"[INFO] FineProxy: Found nonce token: {nonce}", flush=True)

        # --- Step 3: Call API ---
        # Update Referer to point to the main page for the AJAX call
        session.headers.update({'Referer': MAIN_URL})
        
        params = {
            'action': 'proxylister_download',
            'nonce': nonce,
            'format': 'txt',
            'filter': '{}'
        }

        if verbose:
            print(f"[INFO] FineProxy: Querying API...", flush=True)
        
        # Polite delay before hitting the API
        time.sleep(1.5)

        api_response = session.get(API_URL, params=params, timeout=20)
        api_response.raise_for_status()
        
        # The API returns a plain text list of IP:PORT
        api_proxies = extract_proxies_from_content(api_response.text, verbose=False)
        
        initial_count = len(all_proxies)
        all_proxies.update(api_proxies)
        new_count = len(all_proxies) - initial_count

        if verbose:
            print(f"[INFO]   ... API returned {len(api_proxies)} proxies ({new_count} new unique).", flush=True)

    except Exception as e:
        if verbose:
            print(f"[ERROR] FineProxy: Scraper failed: {e}", flush=True)

    if verbose:
        print(f"[INFO] FineProxy: Finished. Found {len(all_proxies)} unique proxies.", flush=True)

    return sorted(list(all_proxies))