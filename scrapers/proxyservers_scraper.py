import re
import time
from typing import List
from helper.request_utils import get_with_retry

BASE_URL = "https://proxyservers.pro/proxy/list/order/updated/order_dir/desc"
URL_TEMPLATE = "https://proxyservers.pro/proxy/list/order/updated/order_dir/desc/page/{page}"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
    'Accept-Language': 'en-US,en;q=0.9',
}

# Regex to find the 'chash' variable in the script tags.
# Matches: var chash = "SOME_KEY"; OR var chash = 'SOME_KEY';
# UPDATED: Now handles both single and double quotes.
CHASH_REGEX = re.compile(r'var\s+chash\s*=\s*[\'"]([^\'"]+)[\'"]')

# Regex to find adjacent IP and Port data.
# Matches: <a href="/proxy/IP"...>IP</a> ... <span class="port" data-port="HEX_STRING"></span>
# We use [\s\S]*? to handle newlines and tags in between.
PROXY_DATA_REGEX = re.compile(r'<a href="/proxy/([^"]+)"[^>]*>[\s\S]*?<span class="port" data-port="([^"]+)">')

def _decode_port(encoded_hex: str, key: str) -> str:
    """
    Decodes the port using the logic reversed from the site's JS.
    1. Parse hex string into bytes.
    2. XOR each byte with the key's char code (cycling through key).
    """
    try:
        # Step 1: Parse hex string into integer values (pairs of 2 chars)
        hex_values = [int(encoded_hex[i:i+2], 16) for i in range(0, len(encoded_hex), 2)]
        
        # Step 2: Convert key to char codes
        key_codes = [ord(c) for c in key]
        key_len = len(key_codes)
        
        # Step 3: XOR decode
        decoded_chars = []
        for i, val in enumerate(hex_values):
            decoded_char_code = val ^ key_codes[i % key_len]
            decoded_chars.append(chr(decoded_char_code))
            
        return "".join(decoded_chars)
    except Exception:
        return ""

def scrape_from_proxyservers(verbose: bool = False) -> List[str]:
    """
    Scrapes proxies from proxyservers.pro.
    Extracts the 'chash' key from the page and uses it to XOR decode the hex-encoded ports.
    Paginates until no more proxies are found.
    """
    if verbose:
        print("\n[RUNNING] 'ProxyServers.pro' scraper has started.", flush=True)

    all_proxies = set()
    page = 1
    
    # We need a session to persist cookies if necessary, though requests usually handles single GETs fine.
    # The 'chash' might change per page or be session-based, so we extract it every time to be safe.

    while True:
        if page == 1:
            url = BASE_URL
        else:
            url = URL_TEMPLATE.format(page=page)
            
        if verbose:
            print(f"[INFO] ProxyServers.pro: Scraping page {page}...", flush=True)

        try:
            response = get_with_retry(url=url, headers=HEADERS, timeout=20, verbose=verbose)
            html_content = response.text
            
            # 1. Extract the decoding key (chash)
            chash_match = CHASH_REGEX.search(html_content)
            if not chash_match:
                # If we can't find the key, we can't decode ports. 
                # This might happen if they change protection or we get a captcha/block page.
                if verbose:
                    print(f"[ERROR] ProxyServers.pro: Could not find 'chash' key on page {page}. Content sample: {html_content[:200]}...", flush=True)
                break
            
            chash_key = chash_match.group(1)
            if verbose and page == 1:
                 print(f"[INFO]   ... Found chash key: {chash_key}", flush=True)

            # 2. Extract IP and Encoded Port pairs
            matches = PROXY_DATA_REGEX.findall(html_content)
            
            if not matches:
                if verbose:
                    print(f"[INFO]   ... No proxies found on page {page}. Stopping.", flush=True)
                break

            new_proxies_on_page = 0
            for ip, encoded_port in matches:
                port = _decode_port(encoded_port, chash_key)
                
                if ip and port and port.isdigit():
                    proxy = f"{ip}:{port}"
                    if proxy not in all_proxies:
                        all_proxies.add(proxy)
                        new_proxies_on_page += 1

            if verbose:
                print(f"[INFO]   ... Found {new_proxies_on_page} new proxies on page {page}. Total unique: {len(all_proxies)}", flush=True)

            if new_proxies_on_page == 0:
                 # If we found matches but they were all duplicates, we might be looping or at the end of useful lists.
                 # Usually paginated lists eventually return empty or 404, but let's be safe.
                 if len(all_proxies) > 0: # Only stop if we already have data, otherwise keep trying next page might have fresh ones
                     break 

            page += 1
            time.sleep(1.5) # Polite delay

        except Exception as e:
            if verbose:
                print(f"[ERROR] ProxyServers.pro: Failed to scrape page {page}: {e}", flush=True)
            break

    if verbose:
        print(f"[INFO] ProxyServers.pro: Finished. Found {len(all_proxies)} unique proxies.", flush=True)

    return sorted(list(all_proxies))

