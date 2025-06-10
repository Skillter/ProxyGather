import re
import requests
import argparse
from typing import List, Set
from concurrent.futures import ThreadPoolExecutor, as_completed

# Define the possible patterns for scraping proxies
# Using a set to automatically handle duplicate patterns
PATTERNS = {
    r'<td>(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})<\/td>\s*<td>(\d+)<\/td>',
    r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d+)',
    r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})&nbsp;&nbsp;(\d+)',
    r'<td>\s*(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s*</td>\s*<td>\s*(\d+)\s*</td>',
    r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}).*?(\d{2,5})',
    r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})[^0-9]*(\d+)',
    r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s*:\s*(\d+)',
    r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})[\s-]+(\d{2,5})',
    r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})<.*?>(\d+)<',
    r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}).*?port\s*:\s*(\d+)'
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
}

def extract_proxies_from_text(text: str) -> Set[str]:
    """
    Extracts proxies from a string of HTML/text using predefined regex patterns.

    Args:
        text: A string containing the content to search for proxies.

    Returns:
        A set of unique proxy strings in 'ip:port' format found in the text.
    """
    found_proxies = set()
    for pattern in PATTERNS:
        matches = re.findall(pattern, text)
        if matches:
            for match in matches:
                ip, port = match
                proxy = f'{ip}:{port}'
                found_proxies.add(proxy)
    return found_proxies


def _fetch_and_extract(url: str, verbose: bool = False) -> Set[str]:
    """Helper function to fetch one URL via GET and extract proxies. Runs in a thread."""
    if verbose:
        print(f"[INFO] Scraping proxies from: {url}")
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()

        # --- REFACTORED ---
        # Use the new, reusable extraction function
        proxies_found = extract_proxies_from_text(response.text)
        
        if verbose:
            if proxies_found:
                 print(f"[INFO]   ... Found {len(proxies_found)} unique proxies on {url}")
            else:
                 print(f"[WARN]   ... Could not find any proxies on {url}")
        
        return proxies_found

    except requests.exceptions.RequestException as e:
        if verbose:
            print(f"[ERROR] Could not fetch URL {url}: {e}")
    
    return set() # Return an empty set on failure


def scrape_proxies(urls: List[str], verbose: bool = False, max_workers: int = 10) -> List[str]:
    """
    Scrapes proxy addresses concurrently from a list of URLs using GET requests.
    (Function body remains the same as before, no changes needed here)
    """
    all_proxies = set()
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {executor.submit(_fetch_and_extract, url, verbose): url for url in urls}
        for future in as_completed(future_to_url):
            try:
                proxies_from_url = future.result()
                all_proxies.update(proxies_from_url)
            except Exception as exc:
                url = future_to_url[future]
                if verbose:
                    print(f"[ERROR] An exception occurred while processing {url}: {exc}")

    return sorted(list(all_proxies))

# This block runs only when the script is executed directly from the command line
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="A command-line tool to scrape proxy IPs and ports from one or more URLs."
    )
    
    parser.add_argument(
        'urls', 
        metavar='URL', 
        type=str, 
        nargs='+',  # This allows one or more arguments
        help='A space-separated list of URLs to scrape for proxies.'
    )
    
    args = parser.parse_args()
    
    print("--- Starting Proxy Scraper ---")
    # Call the main function with the URLs from the command line and set verbose to True
    found_proxies = scrape_proxies(args.urls, verbose=True)
    
    print("\n--- Scraping Complete ---")
    if not found_proxies:
        print("\nError: Could not find any proxies across all provided URLs.")
    else:
        print(f"\nFound a total of {len(found_proxies)} unique proxies:")
        for proxy in found_proxies:
            print(proxy)