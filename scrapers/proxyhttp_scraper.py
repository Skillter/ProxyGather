import requests
import re
from typing import List, Dict
import time
import random

# --- Configuration ---
BASE_URL = "https://proxyhttp.net/"
# The base URL for the specific paginated list we want to scrape
PAGINATED_LIST_URL = "https://proxyhttp.net/free-list/anonymous-server-hide-ip-address/"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36'
}

BASE_DELAY_SECONDS = 0
RANDOM_DELAY_RANGE = (0.1, 0.5)
RATE_LIMIT_DELAY_SECONDS = 10


# --- Regex patterns to deconstruct the obfuscation ---
VAR_SCRIPT_REGEX = re.compile(r'<script type="text/javascript">\s*//<!\[CDATA\[\s*([\s\S]*?)\s*//\]\]>\s*</script>')
VAR_ASSIGN_REGEX = re.compile(r'(\w+)\s*=\s*([\w\d\^]+);')
PROXY_ROW_REGEX = re.compile(r'<tr>\s*<td class="t_ip">([\d.]+)</td>\s*<td class="t_port">\s*<script[^>]+>.*?document\.write\(([\w\d\^]+)\);.*?</script>', re.DOTALL)

def _deobfuscate_variables(script_content: str) -> Dict[str, int]:
    """
    Parses the JavaScript block and iteratively solves the chained
    XOR variable assignments.
    """
    variables = {}
    assignments = VAR_ASSIGN_REGEX.findall(script_content)
    
    unsolved_count = -1
    while len(assignments) != unsolved_count:
        unsolved_count = len(assignments)
        remaining_assignments = []
        
        for name, value_str in assignments:
            parts = value_str.split('^')
            try:
                current_val = 0
                for part in parts:
                    if part.isdigit():
                        current_val ^= int(part)
                    elif part in variables:
                        current_val ^= variables[part]
                    else:
                        raise ValueError("Dependency not solved")
                
                variables[name] = current_val
            except (ValueError, TypeError):
                remaining_assignments.append((name, value_str))
        
        assignments = remaining_assignments
        
    return variables

def scrape_from_proxyhttp(verbose: bool = True) -> List[str]:
    """
    Scrapes and de-obfuscates proxies from the main page and all paginated
    lists of proxyhttp.net.
    """
    if verbose:
        print("[RUNNING] 'ProxyHttp.net' scraper has started.")
    
    all_found_proxies = set()
    
    # --- Step 1: Scrape the main index page ---
    if verbose: print(f"[INFO] ProxyHttp.net: Scraping main page at {BASE_URL}...")
    try:
        response = requests.get(BASE_URL, headers=HEADERS, timeout=20)
        response.raise_for_status()
        html = response.text

        script_match = VAR_SCRIPT_REGEX.search(html)
        if script_match:
            var_map = _deobfuscate_variables(script_match.group(1))
            proxy_rows = PROXY_ROW_REGEX.findall(html)
            for ip, port_script in proxy_rows:
                try:
                    port_parts = port_script.split('^')
                    port = 0
                    for part in port_parts:
                        port ^= int(part) if part.isdigit() else var_map[part]
                    all_found_proxies.add(f"{ip}:{port}")
                except Exception as e:
                    if verbose: print(f"[WARN] ProxyHttp.net: Could not calculate port for IP {ip} on main page: {e}")
            if verbose: print(f"[INFO]   ... Found {len(all_found_proxies)} proxies on the main page.")
        else:
            if verbose: print("[WARN] ProxyHttp.net: No variable script found on main page.")

    except requests.exceptions.RequestException as e:
        if verbose: print(f"[ERROR] ProxyHttp.net: Could not fetch main page: {e}")

    # --- Step 2: Scrape the paginated anonymous list ---
    page_num = 1
    while True:
        # --- MODIFIED: Handle the special URL for page 1 ---
        if page_num == 1:
            url = PAGINATED_LIST_URL
        else:
            url = f"{PAGINATED_LIST_URL}{page_num}"

        if verbose:
            print(f"[INFO] ProxyHttp.net: Scraping anonymous list page {page_num}...")
            
        try:
            response = requests.get(url, headers=HEADERS, timeout=20)
            response.raise_for_status()
            html = response.text
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code in [429, 503]:
                if verbose:
                    print(f"[RATE-LIMITED] ProxyHttp.net: Received status {e.response.status_code}. Waiting for {RATE_LIMIT_DELAY_SECONDS} seconds before retrying page {page_num}...")
                time.sleep(RATE_LIMIT_DELAY_SECONDS)
                continue
            else:
                if verbose:
                    print(f"[ERROR] ProxyHttp.net: Unrecoverable HTTP error {e.response.status_code} on page {page_num}. Stopping.")
                break
        except requests.exceptions.RequestException as e:
            if verbose:
                print(f"[ERROR] ProxyHttp.net: Could not fetch page {page_num}: {e}")
            break

        script_match = VAR_SCRIPT_REGEX.search(html)
        if not script_match:
            if verbose:
                print(f"[ERROR] ProxyHttp.net: Could not find variable script on page {page_num}. Stopping.")
            break
        
        var_map = _deobfuscate_variables(script_match.group(1))
        
        proxy_rows = PROXY_ROW_REGEX.findall(html)
        if not proxy_rows:
            if verbose:
                print(f"[INFO] ProxyHttp.net: No proxies found on page {page_num}. Assuming end of list.")
            break

        newly_found_on_page = set()
        for ip, port_script in proxy_rows:
            try:
                port_parts = port_script.split('^')
                port = 0
                for part in port_parts:
                    port ^= int(part) if part.isdigit() else var_map[part]
                newly_found_on_page.add(f"{ip}:{port}")
            except Exception as e:
                if verbose:
                    print(f"[WARN] ProxyHttp.net: Could not calculate port for IP {ip}: {e}")
                continue
        
        if verbose:
            print(f"[INFO]   ... Found {len(newly_found_on_page)} proxies on this page. Total unique: {len(all_found_proxies | newly_found_on_page)}")
            
        # Stop if we find a page that successfully loads but has no new proxies.
        if not newly_found_on_page and page_num > 1:
            if verbose:
                print(f"[INFO] ProxyHttp.net: Found no new proxies on page {page_num}, stopping.")
            break

        all_found_proxies.update(newly_found_on_page)
        page_num += 1
        
        sleep_duration = BASE_DELAY_SECONDS + random.uniform(*RANDOM_DELAY_RANGE)
        time.sleep(sleep_duration)

    if verbose:
        print(f"[INFO] ProxyHttp.net: Finished. Found a total of {len(all_found_proxies)} unique proxies.")
        
    return sorted(list(all_found_proxies))