import re
import requests
import argparse
from typing import List

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

def scrape_proxies(urls: List[str], verbose: bool = False) -> List[str]:
    """
    Scrapes proxy addresses from a list of URLs.

    Args:
        urls: A list of URL strings to scrape from.
        verbose: If True, prints status messages during scraping.

    Returns:
        A list of unique proxy strings in 'ip:port' format.
    """
    all_proxies = set() # Use a set to automatically handle duplicates

    for url in urls:
        if verbose:
            print(f"[INFO] Scraping proxies from: {url}")
        try:
            response = requests.get(url, headers=HEADERS, timeout=10)
            response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)

            found_on_page = False
            for pattern in PATTERNS:
                matches = re.findall(pattern, response.text)
                if matches:
                    if verbose:
                        print(f"[INFO]   ... Found {len(matches)} proxies using pattern: {pattern}")
                    for match in matches:
                        ip, port = match
                        proxy = f'{ip}:{port}'
                        all_proxies.add(proxy)
                    found_on_page = True
            
            if not found_on_page and verbose:
                print(f"[WARN]   ... Could not find any proxies on {url}")

        except requests.exceptions.RequestException as e:
            if verbose:
                print(f"[ERROR] Could not fetch URL {url}: {e}")
            continue # Move to the next URL

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