import re
import time
import random
import requests
from typing import List, Dict
from seleniumbase import BaseCase
import helper.turnstile as turnstile

def _deobfuscate_and_extract(html_content: str, verbose: bool) -> List[str]:
    """
    Parses the raw HTML from spys.one, deobfuscates the JavaScript-encoded
    ports, and returns a list of full IP:PORT proxies.
    """
    proxies = []
    
    # Step 1: Find the main packer script which contains the port deobfuscation logic.
    packer_match = re.search(r"eval\(function\(p,r,o,x,y,s\)\{.*\}\((.*)\)\)", html_content, re.DOTALL)
    if not packer_match:
        if verbose: print("[WARN] Spys.one: Could not find the main packer script for deobfuscation.")
        return []

    # Step 2: Unpack the script to get the raw variable assignments.
    # This is a Python port of the JS packer/unpacker logic.
    try:
        m = re.search(r"\}\('(.+)',(\d+),(\d+),'(.+)'\.split", packer_match.group(0))
        p, r, o, x_str = m.groups()
        r, o = int(r), int(o)
        x = x_str.split('^')
    except Exception as e:
        if verbose: print(f"[ERROR] Spys.one: Failed to parse packer arguments: {e}")
        return []

    def get_key(val):
        base = r
        chars = "0123456789abcdefghijklmnopqrstuvwxyz"
        s = '' if val < base else get_key(val // base)
        val = val % base
        return s + (chr(val + 29) if val > 35 else chars[val])

    for i in range(o - 1, -1, -1):
        if x[i]:
            key = get_key(i)
            p = re.sub(r'\b' + re.escape(key) + r'\b', x[i], p)
    
    deobfuscated_js = p

    # Step 3: Evaluate the deobfuscated JS to get the values of port variables.
    port_vars = {}
    assignments = deobfuscated_js.strip().split(';')
    for assignment in assignments:
        if not assignment or '=' not in assignment:
            continue
        try:
            var_name, expression = assignment.split('=', 1)
            var_name = var_name.strip()
            expression = expression.strip()
            
            if '^' in expression:
                op1_name, op2_name = expression.split('^')
                op1 = port_vars[op1_name.strip()]
                op2 = port_vars[op2_name.strip()]
                port_vars[var_name] = op1 ^ op2
            else:
                port_vars[var_name] = int(expression)
        except (ValueError, KeyError) as e:
            if verbose: print(f"[WARN] Spys.one: Could not evaluate JS expression '{assignment}': {e}")
            continue

    # Step 4: Find all proxy table rows and extract the IP and the obfuscated port script.
    proxy_rows = re.findall(r'<tr class="spy1x.*?" onmouseover.*?</tr>|<tr class="spy1xx.*?" onmouseover.*?</tr>', html_content, re.DOTALL)
    ip_regex = re.compile(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})')
    script_regex = re.compile(r'<script>document\.write\(":"\+(.*?)\)</script>')

    for row in proxy_rows:
        ip_match = ip_regex.search(row)
        if not ip_match: continue
        ip = ip_match.group(1)

        script_match = script_regex.search(row)
        if not script_match: continue
        
        port_expression = script_match.group(1)
        port_parts_str = re.findall(r'\(([^)]+)\)', port_expression)
        
        # Step 5: Calculate the real port using the variables and expressions.
        try:
            port = ""
            for part in port_parts_str:
                op1_name, op2_name = part.split('^')
                val1 = port_vars[op1_name.strip()]
                val2 = port_vars[op2_name.strip()]
                port += str(val1 ^ val2)
            
            if port:
                proxies.append(f"{ip}:{port}")
        except (KeyError, ValueError) as e:
            if verbose: print(f"[WARN] Spys.one: Failed to deobfuscate port for IP {ip}: {e}")
            continue
            
    return proxies

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

def scrape_from_spysone(sb: BaseCase, verbose: bool = False) -> List[str]:
    """
    Scrapes spys.one by first attempting direct requests. If that fails (likely due to Cloudflare),
    uses a browser to bypass challenges, extract initial proxies, and then uses direct requests
    with obtained credentials for remaining payloads.
    """
    if verbose: print("[RUNNING] 'Spys.one' automation scraper has started.")
    
    all_proxies = set()
    base_url = "https://spys.one/en/free-proxy-list/"
    
    # Initial payload as per prompt (note: xx00 is likely a typo for xx0, set to empty as specified)
    initial_payload = {'xx0': '', 'xpp': '5', 'xf1': '0', 'xf2': '0', 'xf4': '0', 'xf5': '0'}
    
    # Construct initial URL with payload as GET params for browser opening, as per prompt
    from urllib.parse import urlencode
    initial_url = "https://spys.one/free-proxy-list/ALL/?" + urlencode(initial_payload)
    
    # Default headers for direct requests
    default_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Referer': base_url,
    }
    
    # Step 1: Try initial direct POST request
    try:
        if verbose: print("[INFO] Spys.one: Attempting direct POST request for initial proxies...")
        response = requests.post(base_url, data=initial_payload, headers=default_headers, timeout=10)
        response.raise_for_status()
        
        initial_html = response.text
        initial_proxies_list = _deobfuscate_and_extract(initial_html, verbose)
        
        if initial_proxies_list:
            if verbose: print(f"[SUCCESS] Spys.one: Direct request succeeded. Found {len(initial_proxies_list)} initial proxies.")
            all_proxies.update(initial_proxies_list)
            
            # Extract xx0 from initial HTML (find selected option in select name=xx0)
            xx0_match = re.search(r'<select name=xx0>.*?<option value="(\d+)" selected', initial_html, re.DOTALL)
            xx0 = xx0_match.group(1) if xx0_match else '0'  # Default to '0' if not found
            
            # Proceed with direct POSTs for other payloads
            PAYLOADS = [
                {'xx0': xx0, 'xpp': '5', 'xf1': '0', 'xf2': '0', 'xf4': '0', 'xf5': '2'},
                {'xx0': xx0, 'xpp': '5', 'xf1': '2', 'xf2': '2', 'xf4': '0', 'xf5': '1'},
                {'xx0': xx0, 'xpp': '5', 'xf1': '2', 'xf2': '1', 'xf4': '0', 'xf5': '1'},
                {'xx0': xx0, 'xpp': '5', 'xf1': '1', 'xf2': '0', 'xf4': '0', 'xf5': '1'},
                {'xx0': xx0, 'xpp': '5', 'xf1': '2', 'xf2': '0', 'xf4': '0', 'xf5': '1'},
                {'xx0': xx0, 'xpp': '5', 'xf1': '3', 'xf2': '0', 'xf4': '0', 'xf5': '1'},
                {'xx0': xx0, 'xpp': '5', 'xf1': '4', 'xf2': '0', 'xf4': '0', 'xf5': '1'}
            ]
            
            session = requests.Session()
            for idx, payload in enumerate(PAYLOADS, 1):
                if verbose: print(f"[INFO] Spys.one: Direct POST {idx}/{len(PAYLOADS)} with payload {payload}...")
                resp = session.post(base_url, data=payload, headers=default_headers, timeout=10)
                if resp.ok:
                    proxies = _deobfuscate_and_extract(resp.text, verbose)
                    all_proxies.update(proxies)
                time.sleep(random.uniform(1.0, 2.0))  # Polite delay
            
            if verbose: print(f"[INFO] Spys.one: Finished direct scraping. Total unique proxies: {len(all_proxies)}")
            return sorted(list(all_proxies))
        else:
            if verbose: print("[WARN] Spys.one: Direct request returned no proxies. Falling back to browser...")
    
    except Exception as e:
        if verbose: print(f"[ERROR] Spys.one: Direct request failed: {e}. Falling back to browser...")
    
    # Step 2: Use browser for initial access and challenge solving
    creds = _solve_challenge_and_get_creds(sb, initial_url, verbose)
    if not creds:
        if verbose: print("[ERROR] Spys.one: Failed to obtain credentials via browser.")
        return []
    
    # Extract initial proxies from browser page source
    page_content = sb.get_page_source()
    initial_proxies_list = _deobfuscate_and_extract(page_content, verbose)
    all_proxies.update(initial_proxies_list)
    
    # Extract xx0 from browser DOM
    try:
        xx0 = sb.execute_script('return document.querySelector("select[name=\'xx0\']")?.value || "0";')
    except Exception:
        xx0 = '0'  # Fallback
    
    if verbose: print(f"[INFO] Spys.one: Extracted xx0 value: {xx0}")
    
    # Step 3: Prepare for subsequent direct requests with credentials
    req_headers = creds['headers']
    req_headers.update(default_headers)  # Merge with defaults
    req_cookies = creds['cookies']
    
    # Define payloads with extracted xx0
    PAYLOADS = [
        {'xx0': xx0, 'xpp': '5', 'xf1': '0', 'xf2': '0', 'xf4': '0', 'xf5': '2'},
        {'xx0': xx0, 'xpp': '5', 'xf1': '2', 'xf2': '2', 'xf4': '0', 'xf5': '1'},
        {'xx0': xx0, 'xpp': '5', 'xf1': '2', 'xf2': '1', 'xf4': '0', 'xf5': '1'},
        {'xx0': xx0, 'xpp': '5', 'xf1': '1', 'xf2': '0', 'xf4': '0', 'xf5': '1'},
        {'xx0': xx0, 'xpp': '5', 'xf1': '2', 'xf2': '0', 'xf4': '0', 'xf5': '1'},
        {'xx0': xx0, 'xpp': '5', 'xf1': '3', 'xf2': '0', 'xf4': '0', 'xf5': '1'},
        {'xx0': xx0, 'xpp': '5', 'xf1': '4', 'xf2': '0', 'xf4': '0', 'xf5': '1'}
    ]
    
    # Use session for subsequent POSTs
    session = requests.Session()
    session.cookies.update(req_cookies)
    
    for idx, payload in enumerate(PAYLOADS, 1):
        try:
            if verbose: print(f"[INFO] Spys.one: Credentialed POST {idx}/{len(PAYLOADS)} with payload {payload}...")
            resp = session.post(base_url, data=payload, headers=req_headers, timeout=10)
            resp.raise_for_status()
            proxies = _deobfuscate_and_extract(resp.text, verbose)
            all_proxies.update(proxies)
            time.sleep(random.uniform(1.0, 2.0))  # Polite delay
        except Exception as e:
            if verbose: print(f"[WARN] Spys.one: Failed POST for payload {idx}: {e}")
    
    if verbose: print(f"[INFO] Spys.one: Finished. Total unique proxies: {len(all_proxies)}")
    return sorted(list(all_proxies))


def solve_cf_if_present(sb: BaseCase, verbose: bool = False, timeout: int = 7):
    if turnstile.is_turnstile_challenge_present(sb, timeout):
         if verbose: print("[INFO] Spys.one: Cloudflare challenge detected. Solving...")
         sb.uc_gui_click_captcha()
         sb.wait_for_element_present('body > table:nth-child(3)', timeout=10)
         if verbose: print("[SUCCESS] Spys.one: Challenge solved, form is present.")