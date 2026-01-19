import requests
import re
import time
from typing import List

CAPTCHA_CHECK_URL = "https://www.proxydocker.com/api/captcha/check"
MAIN_URL = "https://www.proxydocker.com/"
API_URL = "https://www.proxydocker.com/en/api/proxylist/"

# Regex to find the CSRF token in the meta tag
# Matches: <meta name="_token" content= "9ctEFMbiQ3lUIztwzcGVkqUiyxqob3gWx9FVopTpt70">
TOKEN_REGEX = re.compile(r'<meta name="_token" content=\s*"([^"]+)">')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'X-Requested-With': 'XMLHttpRequest',
    'Origin': 'https://www.proxydocker.com',
    'Referer': 'https://www.proxydocker.com/'
}

def scrape_from_proxydocker(verbose: bool = True) -> List[str]:
    """
    Scrapes proxies from proxydocker.com by first establishing a session via their
    captcha check endpoint, extracting a CSRF token, and then paginating through
    their internal API.
    """
    if verbose:
        print("[RUNNING] 'ProxyDocker' scraper has started.")

    all_proxies = set()
    session = requests.Session()
    session.headers.update(HEADERS)

    try:
        if verbose:
            print(f"[INFO] ProxyDocker: Initializing session at {CAPTCHA_CHECK_URL}...")
        
        init_response = session.post(CAPTCHA_CHECK_URL, timeout=15)
        if init_response.status_code != 200 and verbose:
            print(f"[WARN] ProxyDocker: Captcha check returned status {init_response.status_code}, proceeding anyway.")

        if verbose:
            print(f"[INFO] ProxyDocker: Fetching main page to extract token...")
            
        main_response = session.get(MAIN_URL, timeout=15)
        main_response.raise_for_status()
        
        match = TOKEN_REGEX.search(main_response.text)
        if not match:
            if verbose:
                print("[ERROR] ProxyDocker: Could not find '_token' meta tag. Aborting.")
            return []
            
        token = match.group(1)
        if verbose:
            print(f"[INFO] ProxyDocker: Successfully extracted token.")

        page = 1
        while True:
            payload = {
                'token': token,
                'country': 'all',
                'city': 'all',
                'state': 'all',
                'port': 'all',
                'type': 'all',
                'anonymity': 'all',
                'need': 'all',
                'page': page
            }
            
            if verbose:
                print(f"[INFO] ProxyDocker: Scraping API page {page}...")
                
            try:
                api_response = session.post(API_URL, data=payload, timeout=20)
                api_response.raise_for_status()
                
                json_data = api_response.json()
                
                proxies_on_page = []
                
                if isinstance(json_data, list):
                    proxies_on_page = json_data
                elif isinstance(json_data, dict):
                    # Look for common keys if it's a dict
                    for key in ['proxies', 'data', 'list']:
                        if key in json_data and isinstance(json_data[key], list):
                            proxies_on_page = json_data[key]
                            break
                
                # Fallback: if we couldn't easily find a list, convert to text and regex
                if not proxies_on_page:
                    # Regex for IP:PORT
                    page_text = api_response.text
                    proxies_on_page = re.findall(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d+\b', page_text)

                if not proxies_on_page:
                    if verbose:
                        print(f"[INFO]   ... No proxies found on page {page}. Stopping.")
                    break

                new_count = 0
                for item in proxies_on_page:
                    proxy_str = None
                    if isinstance(item, str):
                        proxy_str = item
                    elif isinstance(item, dict):
                        # Construct from dict if keys exist
                        ip = item.get('ip') or item.get('ip_address')
                        port = item.get('port')
                        if ip and port:
                            proxy_str = f"{ip}:{port}"
                    
                    if proxy_str:
                        if proxy_str not in all_proxies:
                            all_proxies.add(proxy_str)
                            new_count += 1

                if verbose:
                    print(f"[INFO]   ... Found {new_count} new proxies. Total unique: {len(all_proxies)}")
                
                # Stop if we didn't find any *new* proxies to avoid infinite loops on some APIs
                # that might return the same last page repeatedly
                if new_count == 0 and len(proxies_on_page) > 0:
                     pass 

                page += 1
                time.sleep(1) # Polite delay

            except Exception as e:
                if verbose:
                    print(f"[ERROR] ProxyDocker: Error on page {page}: {e}")
                break

    except Exception as e:
        if verbose:
            print(f"[ERROR] ProxyDocker: Scraper failed: {e}")

    if verbose:
        print(f"[INFO] ProxyDocker: Finished. Found {len(all_proxies)} unique proxies.")

    return sorted(list(all_proxies))

