import requests
import re
import json
from typing import List, Dict, Union, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- MODIFIED: Changed from a set to a list to enforce a prioritized order. ---
# Patterns are ordered from most specific/reliable to most generic/broad.
PATTERNS = [
    # --- High Priority: Very specific and low risk of false positives ---
    # 1. Matches `IP:PORT` inside quotes, common in JS/JSON.
    r'["\'](\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d{2,5})["\']',
    
    # 2. MODIFIED: Robustly matches IP and Port in table rows, even with non-adjacent columns and newlines.
    #    This now uses [\s\S]*? to match across newlines and correctly parse formatted HTML tables.
    r'<tr[^>]*>[\s\S]*?<td>\s*(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s*</td>[\s\S]*?<td>\s*(\d+)\s*</td>',
    
    # 3. Matches IP and Port in adjacent table cells, allowing for whitespace.
    r'<td>\s*(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s*</td>\s*<td>\s*(\d+)\s*</td>',
    # 4. A simpler version for adjacent table cells.
    r'<td>(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})<\/td>\s*<td>(\d+)<\/td>',
    # 5. Matches IP and Port separated by non-breaking spaces.
    r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})  (\d+)',

    # --- Medium Priority: Common formats, slightly higher risk ---
    # 6. Standard `IP:PORT` format, allowing for whitespace around the colon.
    r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s*:\s*(\d+)',
    # 7. The most common `IP:PORT` format without extra whitespace.
    r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d+)',
    # 8. IP and Port in adjacent HTML tags, a moderately reliable pattern.
    r'>\s*(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s*<[^>]+>(\d{2,5})<',
    
    # 9. MODIFIED: Looks for an IP near the word "port", now matching across newlines.
    r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})[\s\S]{0,50}?port\s*:\s*(\d+)',
    
    # --- Low Priority: Broad patterns, higher risk of false positives ---
    # 10. IP followed by whitespace or a hyphen, then the port.
    r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})[\s-]+(\d{2,5})',
    # 11. IP and Port separated by some unknown HTML tag.
    r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})<.*?>(\d+)<',
    # 12. The most generic pattern: IP, some characters, and a port-like number (on a single line).
    r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}).*?(\d{2,5})',
]


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

        # --- The loop now iterates through the prioritized list of patterns ---
        found_on_page = False
        for pattern in PATTERNS:
            matches_for_pattern = set()
            try:
                matches = re.findall(pattern, response.text)
                if matches:
                    for match in matches:
                        # Ensure match is a tuple with at least two elements
                        if isinstance(match, tuple) and len(match) >= 2:
                            ip, port = match[0], match[1]
                            matches_for_pattern.add(f'{ip}:{port}')
                        # Handle cases where re.findall returns a list of strings
                        elif isinstance(match, str) and ":" in match:
                             matches_for_pattern.add(match)

                    if matches_for_pattern:
                        proxies_found.update(matches_for_pattern)
                        found_on_page = True
            except re.error as e:
                if verbose:
                    print(f"[ERROR] Regex error for pattern '{pattern}' on {url}: {e}")

        
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