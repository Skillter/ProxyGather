import re
import time
import random
import requests
from typing import List, Dict, Optional
from seleniumbase import BaseCase
import helper.turnstile as turnstile

def _solve_challenge_and_get_creds(sb: BaseCase, url: str, verbose: bool) -> dict:
    """
    Uses the browser to solve a Cloudflare challenge on a given URL
    and returns the necessary cookies and user-agent for direct requests.
    """
    if verbose:
        print(f"[INFO] Spys.one: Using browser to access {url}...")
    
    sb.open(url)
    
    try:
        solve_cf_if_present(sb, verbose, 5)
        
        sb.wait_for_element_present(selector='body > table:nth-child(3)', timeout=20)
        if verbose:
            print("[SUCCESS] Spys.one: Challenge solved or bypassed. Table is present.")
        
        cookies = sb.get_cookies()
        cf_clearance_cookie = next((c for c in cookies if c['name'] == 'cf_clearance'), None)
        
        if not cf_clearance_cookie:
            raise ValueError("Could not find 'cf_clearance' cookie after solving challenge.")
            
        user_agent = sb.get_user_agent()
        
        return {
            "cookies": {
                'cf_clearance': cf_clearance_cookie['value']
            },
            "headers": {
                'User-Agent': user_agent
            }
        }

    except Exception as e:
        if verbose:
            print(f"[ERROR] Spys.one: Failed to solve challenge or extract credentials: {e}")
        return {}

def _deobfuscate_ports(html_content: str, verbose: bool = False) -> Dict[str, str]:
    """
    Extracts IP addresses and deobfuscates their corresponding ports from the HTML.
    Returns a dictionary mapping IP addresses to their ports.
    """
    # First, find and parse the main eval script that contains variable definitions
    eval_pattern = r'eval\(function\(p,r,o,x,y,s\){.*?\}.*?\((.*?)\)\)'
    eval_match = re.search(eval_pattern, html_content, re.DOTALL)
    
    if not eval_match:
        if verbose:
            print("[WARN] Spys.one: Could not find eval script for port deobfuscation")
        return {}
    
    # Parse the packed script
    try:
        # Extract the parameters from the eval call
        params_match = re.search(r"'([^']*)',(\d+),(\d+),'([^']*)'\.split\('([^']*)'\)", eval_match.group(1))
        if not params_match:
            if verbose:
                print("[ERROR] Spys.one: Could not parse eval parameters")
            return {}
        
        p, radix, count, words, separator = params_match.groups()
        radix = int(radix)
        count = int(count)
        words_list = words.split(separator)
        
        # Unpack the script
        def base_convert(num, base):
            if num == 0:
                return '0'
            digits = "0123456789abcdefghijklmnopqrstuvwxyz"
            result = []
            while num:
                result.append(digits[num % base])
                num //= base
            return ''.join(reversed(result))
        
        # Replace packed variables
        for i in range(count - 1, -1, -1):
            if i < len(words_list) and words_list[i]:
                key = base_convert(i, radix) if i >= radix else str(i) if i < 10 else chr(i - 10 + ord('a'))
                if radix > 35 and i > 35:
                    key = chr(i + 29)
                p = re.sub(r'\b' + re.escape(key) + r'\b', words_list[i], p)
        
        # Now p contains the unpacked JavaScript with variable assignments
        # Parse the variable assignments
        variables = {}
        
        # Parse simple assignments (e.g., l=11721^3467)
        for match in re.finditer(r'(\w+)=(\d+)\^(\d+)', p):
            var_name, val1, val2 = match.groups()
            variables[var_name] = int(val1) ^ int(val2)
        
        # Parse numeric assignments (e.g., c=4)
        for match in re.finditer(r'(\w+)=(\d+)(?:;|$)', p):
            var_name, value = match.groups()
            if var_name not in variables:  # Don't overwrite XOR results
                variables[var_name] = int(value)
        
        # Parse variable XOR assignments (e.g., K=j^l)
        for match in re.finditer(r'(\w+)=(\w+)\^(\w+)', p):
            var_name, var1, var2 = match.groups()
            if var1 in variables and var2 in variables:
                variables[var_name] = variables[var1] ^ variables[var2]
        
    except Exception as e:
        if verbose:
            print(f"[ERROR] Spys.one: Failed to parse eval script: {e}")
        return {}
    
    # Now extract IPs and their obfuscated port expressions
    ip_port_map = {}
    
    # Pattern to find IP addresses with their script tags
    ip_pattern = r'<font class="spy14">(\d+\.\d+\.\d+\.\d+)<script>document\.write\(":"\+(.*?)\)</script>'
    
    for match in re.finditer(ip_pattern, html_content):
        ip, port_expr = match.groups()
        
        # Parse the port expression (e.g., (ZeroNineFiveNine^Three5Nine)+(Three5FourZero^NineFiveZero)+...)
        port_parts = re.findall(r'\((\w+)\^(\w+)\)', port_expr)
        
        try:
            port = ""
            for var1, var2 in port_parts:
                if var1 in variables and var2 in variables:
                    port += str(variables[var1] ^ variables[var2])
                else:
                    if verbose:
                        print(f"[WARN] Spys.one: Unknown variables {var1} or {var2} for IP {ip}")
                    break
            else:
                # Only add if we successfully decoded all parts
                if port:
                    ip_port_map[ip] = port
        except Exception as e:
            if verbose:
                print(f"[WARN] Spys.one: Failed to decode port for IP {ip}: {e}")
    
    return ip_port_map

def _extract_proxies_from_html(html_content: str, verbose: bool = False) -> List[str]:
    """
    Extracts proxies from the HTML content by deobfuscating the ports.
    """
    ip_port_map = _deobfuscate_ports(html_content, verbose)
    
    proxies = []
    for ip, port in ip_port_map.items():
        proxies.append(f"{ip}:{port}")
    
    return proxies

def _make_request_with_payload(url: str, payload: dict, cookies: dict = None, headers: dict = None, verbose: bool = False) -> Optional[str]:
    """
    Makes a POST request with the given payload and returns the response text.
    """
    try:
        request_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Origin': 'https://spys.one',
            'Referer': url
        }
        
        if headers:
            request_headers.update(headers)
        
        response = requests.post(url, data=payload, headers=request_headers, cookies=cookies, timeout=15)
        
        if response.status_code == 200:
            return response.text
        else:
            if verbose:
                print(f"[WARN] Spys.one: Request failed with status {response.status_code}")
            return None
            
    except Exception as e:
        if verbose:
            print(f"[ERROR] Spys.one: Request failed: {e}")
        return None

def scrape_from_spysone(sb: BaseCase, verbose: bool = False) -> List[str]:
    """
    Scrapes proxies from spys.one using either direct requests or browser automation.
    """
    if verbose:
        print("[RUNNING] 'Spys.one' automation scraper has started.")
    
    all_proxies = set()
    base_url = "https://spys.one/free-proxy-list/ALL/"
    
    # First, try a simple request to check if we need browser automation
    initial_payload = {'xx0': '0', 'xpp': '5', 'xf1': '0', 'xf2': '0', 'xf4': '0', 'xf5': '0'}
    
    if verbose:
        print("[INFO] Spys.one: Attempting direct request...")
    
    initial_response = _make_request_with_payload(base_url, initial_payload, verbose=verbose)
    
    cookies = None
    headers = None
    use_browser = False
    
    if initial_response and '<font class="spy14">' in initial_response:
        # Direct request worked, extract proxies
        if verbose:
            print("[SUCCESS] Spys.one: Direct request successful, extracting proxies...")
        initial_proxies = _extract_proxies_from_html(initial_response, verbose)
        all_proxies.update(initial_proxies)
    else:
        # Need to use browser to solve Cloudflare challenge
        use_browser = True
        if verbose:
            print("[INFO] Spys.one: Direct request failed, using browser automation...")
        
        creds = _solve_challenge_and_get_creds(sb, base_url, verbose)
        
        if creds and 'cookies' in creds:
            cookies = creds['cookies']
            headers = creds.get('headers', {})
            
            # Extract proxies from the current page
            page_content = sb.get_page_source()
            initial_proxies = _extract_proxies_from_html(page_content, verbose)
            all_proxies.update(initial_proxies)
            
            if verbose:
                print(f"[INFO] Spys.one: Found {len(initial_proxies)} proxies from initial page")
        else:
            if verbose:
                print("[ERROR] Spys.one: Failed to solve Cloudflare challenge")
            return list(all_proxies)
    
    # Define the payloads for different proxy types
    payloads = [
        {'xx0': '0', 'xpp': '5', 'xf1': '0', 'xf2': '0', 'xf4': '0', 'xf5': '2'},  # SOCKS
        {'xx0': '0', 'xpp': '5', 'xf1': '2', 'xf2': '2', 'xf4': '0', 'xf5': '1'},  # HTTPS - NOA - SSL+
        {'xx0': '0', 'xpp': '5', 'xf1': '2', 'xf2': '1', 'xf4': '0', 'xf5': '1'},  # HTTPS - NOA - SSL
        {'xx0': '0', 'xpp': '5', 'xf1': '1', 'xf2': '0', 'xf4': '0', 'xf5': '1'},  # HTTP - ANM + HIA
        {'xx0': '0', 'xpp': '5', 'xf1': '2', 'xf2': '0', 'xf4': '0', 'xf5': '1'},  # HTTP - NOA
        {'xx0': '0', 'xpp': '5', 'xf1': '3', 'xf2': '0', 'xf4': '0', 'xf5': '1'},  # HTTP - ANM
        {'xx0': '0', 'xpp': '5', 'xf1': '4', 'xf2': '0', 'xf4': '0', 'xf5': '1'}   # HTTP - HIA
    ]
    
    # Make requests with different payloads
    for i, payload in enumerate(payloads):
        if verbose:
            print(f"[INFO] Spys.one: Fetching page {i+2}/{len(payloads)+1} with payload {payload}...")
        
        # Add a small delay between requests
        time.sleep(random.uniform(1.0, 2.0))
        
        response = _make_request_with_payload(base_url, payload, cookies=cookies, headers=headers, verbose=verbose)
        
        if response and '<font class="spy14">' in response:
            proxies = _extract_proxies_from_html(response, verbose)
            new_proxies = set(proxies) - all_proxies
            all_proxies.update(proxies)
            
            if verbose:
                print(f"[INFO] Spys.one: Found {len(new_proxies)} new proxies. Total: {len(all_proxies)}")
        else:
            if verbose:
                print(f"[WARN] Spys.one: Failed to fetch page with payload {payload}")
    
    final_proxies = sorted(list(all_proxies))
    
    if verbose:
        print(f"[COMPLETED] Spys.one: Finished. Found {len(final_proxies)} unique proxies.")
    
    return final_proxies

def solve_cf_if_present(sb: BaseCase, verbose: bool = False, timeout: int = 7):
    if turnstile.is_turnstile_challenge_present(sb, timeout):
         if verbose: print("[INFO] Spys.one: Cloudflare challenge detected. Solving...")
         sb.uc_gui_click_captcha()
         sb.wait_for_element_present('body > table:nth-child(3)', timeout=10)
         if verbose: print("[SUCCESS] Spys.one: Challenge solved, form is present.")