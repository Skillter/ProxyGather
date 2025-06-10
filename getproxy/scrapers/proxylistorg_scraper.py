import requests
import re
import base64
import time
import random
from typing import List

# The URL template for the website, with a placeholder for the page number
URL_TEMPLATE = "https://proxy-list.org/english/index.php?p={page}"

# Regex to find the Base64 encoded string inside the Proxy() javascript function
# It looks for Proxy('...') and captures the content inside the single quotes.
PROXY_EXTRACTION_REGEX = re.compile(r"Proxy\('([a-zA-Z0-9+/=]+)'\)")

# Standard headers to mimic a browser
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3',
    'Referer': 'https://proxy-list.org/english/index.php'
}

# Polite scraping configuration
BASE_DELAY_SECONDS = 2
RANDOM_DELAY_RANGE = (0.5, 1.5)

def scrape_from_proxylistorg(verbose: bool = True) -> List[str]:
    """
    Scrapes all pages from proxy-list.org by iterating through page numbers.

    It finds the Base64 encoded proxies, decodes them, and collects the results
    with a polite delay between each page request to avoid rate-limiting.

    Args:
        verbose: If True, prints detailed status messages for each page.

    Returns:
        A list of all unique proxies found across all pages.
    """
    all_proxies = set()
    page_num = 1
    
    print("[RUNNING] 'ProxyList.org' scraper has started.")

    while True:
        url = URL_TEMPLATE.format(page=page_num)
        
        if verbose:
            print(f"[INFO] ProxyList.org: Scraping page {page_num}...")

        try:
            response = requests.get(url, headers=HEADERS, timeout=20)
            response.raise_for_status()

            # Find all the Base64 encoded strings on the page
            encoded_proxies = PROXY_EXTRACTION_REGEX.findall(response.text)
            
            # If no proxies are found, we've reached the last page
            if not encoded_proxies:
                if verbose:
                    print(f"[INFO]   ... No proxies found on page {page_num}. Assuming end of list.")
                break # Exit the while loop
            
            newly_found_on_page = set()
            for encoded_proxy in encoded_proxies:
                try:
                    # Decode the Base64 string. The result is in bytes.
                    decoded_bytes = base64.b64decode(encoded_proxy)
                    # Convert the bytes to a regular string.
                    decoded_string = decoded_bytes.decode('utf-8')
                    newly_found_on_page.add(decoded_string)
                except (ValueError, UnicodeDecodeError) as e:
                    if verbose:
                        print(f"[WARN]   ... Could not decode '{encoded_proxy}': {e}")
                    continue # Skip to the next proxy
            
            if verbose:
                print(f"[INFO]   ... Found and successfully decoded {len(newly_found_on_page)} proxies.")
            
            # If we didn't add any new proxies to our main set, we might be in a loop
            initial_count = len(all_proxies)
            all_proxies.update(newly_found_on_page)
            if len(all_proxies) == initial_count:
                if verbose:
                    print("[INFO]   ... No new unique proxies found. Stopping to prevent infinite loop.")
                break

        except requests.exceptions.RequestException as e:
            if verbose:
                print(f"[ERROR]  ... Could not fetch page {page_num}: {e}. Stopping this scraper.")
            break # Stop if a page fails to load
        
        # Polite Rate-limiting: Wait before hitting the next page
        sleep_duration = BASE_DELAY_SECONDS + random.uniform(*RANDOM_DELAY_RANGE)
        if verbose:
            print(f"[INFO] Waiting for {sleep_duration:.2f} seconds before next page...")
        time.sleep(sleep_duration)
        
        page_num += 1
    
    if verbose:
        print(f"[INFO] ProxyList.org: Finished. Found a total of {len(all_proxies)} unique proxies.")

    return sorted(list(all_proxies))