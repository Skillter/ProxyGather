import requests
import re
import json
from typing import List, Dict, Union, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

# Define the possible patterns for scraping proxies
# Using a set to automatically handle duplicate patterns
PATTERNS = {
    r'<td>(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})<\/td>\s*<td>(\d+)<\/td>',
    r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d+)',
    r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})&nbsp;&nbsp;(\d+)',
    r'<td>\s*(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s*</td>\s*<td>\s*(\d+)\s*</td>',
    r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}).*?(\d{2,5})',
    # r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})[^0-9]*(\d+)', # Too broad, matches wrong things in https://xseo.in/proxylist
    r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s*:\s*(\d+)',
    r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})[\s-]+(\d{2,5})',
    r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})<.*?>(\d+)<',
    r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}).*?port\s*:\s*(\d+)'
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3',
    # Add content-type header for POST requests
    'Content-Type': 'application/json'
}

def _fetch_and_extract(url: str, payload: Union[Dict, None], verbose: bool = False) -> set:
    """
    Helper function to fetch one URL and extract proxies.
    Sends a POST request if a payload is provided, otherwise sends a GET request.
    Runs in a thread.
    """
    proxies_found = set()
    request_type = "POST" if payload else "GET"
    
    if verbose:
        print(f"[INFO] Scraping ({request_type}): {url}")
        
    try:
        # --- MODIFIED: Choose between GET and POST ---
        if payload:
            response = requests.post(url, headers=HEADERS, json=payload, timeout=15)
        else:
            # For GET requests, we don't need the Content-Type header
            get_headers = HEADERS.copy()
            get_headers.pop('Content-Type', None)
            response = requests.get(url, headers=get_headers, timeout=15)
        
        response.raise_for_status()

        found_on_page = False
        for pattern in PATTERNS:
            matches = re.findall(pattern, response.text)
            if matches:
                for match in matches:
                    ip, port = match
                    proxies_found.add(f'{ip}:{port}')
                found_on_page = True
        
        if verbose:
            if found_on_page:
                 print(f"[INFO]   ... Found {len(proxies_found)} unique proxies on {url}")
            else:
                 print(f"[WARN]   ... Could not find any proxies on {url}")

    except requests.exceptions.RequestException as e:
        if verbose:
            print(f"[ERROR] Could not fetch URL ({request_type}) {url}: {e}")
    
    return proxies_found


def scrape_proxies(
    scrape_targets: List[Tuple[str, Union[Dict, None]]],
    verbose: bool = False,
    max_workers: int = 10
) -> List[str]:
    """
    Scrapes proxy addresses concurrently from a list of targets.
    Each target is a tuple containing a URL and an optional payload dictionary.

    Args:
        scrape_targets: A list of tuples, where each is (url, optional_payload).
        verbose: If True, prints status messages during scraping.
        max_workers: The maximum number of threads to use for scraping.

    Returns:
        A list of unique proxy strings in 'ip:port' format.
    """
    all_proxies = set()
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Create a future for each URL and its payload
        future_to_url = {
            executor.submit(_fetch_and_extract, url, payload, verbose): url
            for url, payload in scrape_targets
        }
        
        for future in as_completed(future_to_url):
            try:
                proxies_from_url = future.result()
                all_proxies.update(proxies_from_url)
            except Exception as exc:
                url = future_to_url[future]
                if verbose:
                    print(f"[ERROR] An exception occurred while processing {url}: {exc}")

    return sorted(list(all_proxies))