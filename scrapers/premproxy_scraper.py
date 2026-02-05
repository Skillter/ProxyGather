import re
import requests
import time
from typing import List, Dict
import urllib3

# Suppress InsecureRequestWarning
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://premproxy.com/list/"
PAGE_URL_TEMPLATE = "https://premproxy.com/list/{page:02d}.htm"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Referer': 'https://premproxy.com/list/'
}

JS_FILE_REGEX = re.compile(r'<input type="hidden" name="pr" value="([^"]+)">')
PROXY_ROW_REGEX = re.compile(r'value="(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\|([a-z0-9]+)"')
PACKER_REGEX = re.compile(r"\}\('(.+?)',(\d+),(\d+),'([^']+)'\.split\('\|'\)")

# Updated Regex to handle potential backslashes before quotes in the raw string
PORT_MAP_REGEX = re.compile(r"\$\(\\?['\"]\.(.*?)\\?['\"]\)\.html\((\d+)\)")

def _base_encode(n: int) -> str:
    """
    Mimics the base-62 encoding used in the JS packer.
    """
    digits = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    if n == 0: 
        return digits[0]
    
    result = ""
    while n > 0:
        val = n % 62
        result = digits[val] + result
        n = n // 62
    return result

def _decode_packer(payload: str, radix: int, count: int, keywords: List[str]) -> str:
    """
    Unpacks the Dean Edwards packed JavaScript code.
    """
    unpacked = payload
    # Iterate backwards to avoid replacing substrings of larger tokens
    for i in range(count - 1, -1, -1):
        token = _base_encode(i)
        
        # Determine replacement
        if i < len(keywords) and keywords[i]:
            replacement = keywords[i]
        else:
            # If keyword is empty/missing, the token maps to itself
            continue
            
        # Use regex with word boundaries to replace exact token matches
        pattern = r'\b' + re.escape(token) + r'\b'
        unpacked = re.sub(pattern, replacement, unpacked)
            
    return unpacked

def _get_port_map(html_content: str, session: requests.Session, verbose: bool) -> Dict[str, str]:
    match = JS_FILE_REGEX.search(html_content)
    if not match:
        if verbose: print("[ERROR] PremProxy: Could not find port mapping JS filename.", flush=True)
        return {}
    
    js_filename = match.group(1)
    js_url = f"https://premproxy.com/js/{js_filename}"
    
    try:
        if verbose: print(f"[INFO] PremProxy: Fetching port map from {js_url}...", flush=True)
        resp = session.get(js_url, timeout=15, verify=False)
        resp.raise_for_status()
        js_content = resp.text
        
        pm = PACKER_REGEX.search(js_content)
        if not pm:
            if verbose: print("[ERROR] PremProxy: Could not parse packed JS.", flush=True)
            return {}
        
        payload = pm.group(1)
        radix = int(pm.group(2))
        count = int(pm.group(3))
        keywords = pm.group(4).split('|')
        
        unpacked_js = _decode_packer(payload, radix, count, keywords)
        
        mappings = dict(PORT_MAP_REGEX.findall(unpacked_js))
        if verbose: print(f"[INFO] PremProxy: Extracted {len(mappings)} port mappings.", flush=True)
        return mappings
        
    except Exception as e:
        if verbose: print(f"[ERROR] PremProxy: Failed to get port map: {e}", flush=True)
        return {}

def scrape_from_premproxy(verbose: bool = False) -> List[str]:
    """
    Scrapes proxies from premproxy.com.
    """
    if verbose:
        print("\n[RUNNING] 'PremProxy' scraper has started.", flush=True)

    all_proxies = set()
    session = requests.Session()
    session.headers.update(HEADERS)
    
    try:
        if verbose: print(f"[INFO] PremProxy: Scraping page 1...", flush=True)
        response = session.get(BASE_URL, timeout=20, verify=False)
        if response.status_code != 200:
            if verbose: print(f"[ERROR] PremProxy: Failed to load main page (HTTP {response.status_code})", flush=True)
            return []
        
        page_html = response.text
        port_map = _get_port_map(page_html, session, verbose)
        if not port_map:
            return []
        
        matches = PROXY_ROW_REGEX.findall(page_html)
        for ip, port_class in matches:
            port = port_map.get(port_class)
            if port:
                all_proxies.add(f"{ip}:{port}")
        
        if verbose:
            print(f"[INFO]   ... Found {len(all_proxies)} proxies on page 1.", flush=True)

        page = 2
        while True:
            url = PAGE_URL_TEMPLATE.format(page=page)
            if verbose: print(f"[INFO] PremProxy: Scraping page {page}...", flush=True)
            
            try:
                resp = session.get(url, timeout=15, verify=False)
                if resp.status_code == 404:
                    if verbose: print("[INFO] PremProxy: Reached end of list (404).", flush=True)
                    break
                if resp.status_code != 200:
                    if verbose: print(f"[WARN] PremProxy: Error on page {page} (HTTP {resp.status_code}).", flush=True)
                    break
                
                content = resp.text
                new_matches = PROXY_ROW_REGEX.findall(content)
                
                if not new_matches:
                    if verbose: print("[INFO] PremProxy: No proxies found on page. Stopping.", flush=True)
                    break
                
                new_count = 0
                for ip, port_class in new_matches:
                    port = port_map.get(port_class)
                    if port:
                        proxy = f"{ip}:{port}"
                        if proxy not in all_proxies:
                            all_proxies.add(proxy)
                            new_count += 1
                
                if verbose:
                    print(f"[INFO]   ... Found {new_count} new proxies. Total: {len(all_proxies)}", flush=True)
                
                # Automatically stop if no NEW proxies were found on this page
                if new_count == 0:
                    if verbose: print("[INFO] PremProxy: No new unique proxies found on this page. Stopping.", flush=True)
                    break

                page += 1
                time.sleep(1) 
                
            except Exception as e:
                if verbose: print(f"[ERROR] PremProxy: Error on page {page}: {e}", flush=True)
                break

    except Exception as e:
        if verbose: print(f"[ERROR] PremProxy: Critical error: {e}", flush=True)

    if verbose:
        print(f"[INFO] PremProxy: Finished. Found {len(all_proxies)} unique proxies.", flush=True)

    return sorted(list(all_proxies))

