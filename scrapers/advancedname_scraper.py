import base64
import re
import time
from typing import List
from helper.request_utils import get_with_retry

BASE_URL = "https://advanced.name/freeproxy"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# Regex to find adjacent data-ip and data-port attributes.
# Matches: <td data-ip="BASE64"></td>...<td data-port="BASE64"></td>
# We use [\s\S]*? to handle newlines or extra attributes between the tags.
DATA_REGEX = re.compile(r'data-ip="([^"]+)"[^>]*></td>\s*<td\s+data-port="([^"]+)"')

def _decode_base64(encoded_str: str) -> str:
    """Decodes a Base64 string to utf-8, handling potential padding errors."""
    try:
        # Add padding if missing, just in case
        missing_padding = len(encoded_str) % 4
        if missing_padding:
            encoded_str += '=' * (4 - missing_padding)
        return base64.b64decode(encoded_str).decode('utf-8')
    except Exception:
        return ""

def scrape_from_advancedname(verbose: bool = True) -> List[str]:
    """
    Scrapes proxies from advanced.name/freeproxy.
    Extracts Base64 encoded IP and Port from HTML data attributes and decodes them.
    Paginates until no more proxies are found.
    """
    if verbose:
        print("\n[RUNNING] 'Advanced.name' scraper has started.", flush=True)

    all_proxies = set()
    page = 1

    while True:
        url = f"{BASE_URL}?page={page}"
        
        if verbose:
            print(f"[INFO] Advanced.name: Scraping page {page}...", flush=True)

        try:
            response = get_with_retry(url=url, headers=HEADERS, timeout=20, verbose=verbose)
            html_content = response.text
            
            # Find all matches on the page
            matches = DATA_REGEX.findall(html_content)
            
            if not matches:
                if verbose:
                    print(f"[INFO]   ... No proxies found on page {page}. Stopping.", flush=True)
                break

            new_proxies_on_page = 0
            for encoded_ip, encoded_port in matches:
                ip = _decode_base64(encoded_ip)
                port = _decode_base64(encoded_port)
                
                if ip and port:
                    # Basic validation to ensure we decoded something that looks like an IP/Port
                    if '.' in ip and port.isdigit():
                        proxy = f"{ip}:{port}"
                        if proxy not in all_proxies:
                            all_proxies.add(proxy)
                            new_proxies_on_page += 1

            if verbose:
                print(f"[INFO]   ... Found {new_proxies_on_page} new proxies on page {page}. Total unique: {len(all_proxies)}", flush=True)

            # Stop if the page loaded but we found 0 valid new proxies (avoids infinite loops on empty pages)
            if new_proxies_on_page == 0:
                 break

            page += 1
            time.sleep(1) # Polite delay

        except Exception as e:
            if verbose:
                print(f"[ERROR] Advanced.name: Failed to scrape page {page}: {e}", flush=True)
            break

    if verbose:
        print(f"[INFO] Advanced.name: Finished. Found {len(all_proxies)} unique proxies.", flush=True)

    return sorted(list(all_proxies))

