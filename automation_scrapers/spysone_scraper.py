import time
import re
from typing import List, Set
from seleniumbase import BaseCase
import helper.turnstile as turnstile

# This token is found in the form POST data and may need updating if the scraper breaks.
XX0_TOKEN = '54c88a278700021f71dc98e29b41228a'

# Payloads for different proxy filters. xpp=5 means 500 proxies per page.
PAYLOADS = [
    {'xx0': XX0_TOKEN, 'xpp': '5', 'xf1': '0', 'xf2': '0', 'xf4': '0', 'xf5': '0'}, # All types
    {'xx0': XX0_TOKEN, 'xpp': '5', 'xf1': '0', 'xf2': '0', 'xf4': '0', 'xf5': '2'}, # SOCKS
    {'xx0': XX0_TOKEN, 'xpp': '5', 'xf1': '1', 'xf2': '0', 'xf4': '0', 'xf5': '1'}, # HTTP - ANM+HIA
    {'xx0': XX0_TOKEN, 'xpp': '5', 'xf1': '2', 'xf2': '0', 'xf4': '0', 'xf5': '1'}, # HTTP - NOA (Non-Anonymous)
    {'xx0': XX0_TOKEN, 'xpp': '5', 'xf1': '3', 'xf2': '0', 'xf4': '0', 'xf5': '1'}, # HTTP - ANM (Anonymous)
    {'xx0': XX0_TOKEN, 'xpp': '5', 'xf1': '4', 'xf2': '0', 'xf4': '0', 'xf5': '1'}, # HTTP - HIA (High-Anonymous)
]

def _extract_and_deobfuscate(sb: BaseCase, verbose: bool) -> Set[str]:
    """
    Extracts IPs and deobfuscates ports from the current page in the browser.
    It works by executing the site's own JS to make the port variables available,
    then executes the small port calculation scripts for each proxy entry.
    """
    found_proxies = set()
    if verbose: print("[DEBUG] Starting extraction and deobfuscation...")

    # 1. Get the page source to find the obfuscation script
    html_content = sb.get_page_source()
    
    # 2. Find the main script that defines the obfuscated port variables.
    script_match = re.search(
        r'<script type="text/javascript">([\s\S]*?)</script>',
        html_content
    )
    
    if not script_match or "=" not in script_match.group(1):
        if verbose: print("[DEBUG] Spys.one: Could not find the port deobfuscation variable script.")
        return set()
    
    deobfuscation_vars_script = script_match.group(1)
    if verbose: print(f"[DEBUG] Found deobfuscation variable script: {deobfuscation_vars_script[:100]}...")
        
    # 3. Execute this script in the browser to define the variables in the window scope.
    try:
        sb.execute_script(deobfuscation_vars_script)
        if verbose: print("[DEBUG] Successfully executed the variable definition script.")
    except Exception as e:
        if verbose: print(f"[DEBUG] Spys.one: Failed to execute deobfuscation script: {e}")
        return set()

    # 4. Find all proxy table rows that contain an IP address.
    proxy_rows = sb.find_elements('//tr[(@class="spy1x" or @class="spy1xx") and .//font[@class="spy14"]]')
    if verbose: print(f"[DEBUG] Found {len(proxy_rows)} potential proxy rows in the table.")

    for i, row in enumerate(proxy_rows):
        try:
            # 5. Get the IP address text from the <font> tag.
            ip_element = row.find_element("css selector", "font.spy14")
            ip_text = ip_element.get_attribute('textContent')
            ip_match = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', ip_text)
            if not ip_match:
                if verbose: print(f"[DEBUG] Row {i+1}: No IP found in text: '{ip_text}'")
                continue
            ip = ip_match.group(1)

            # 6. Find the script tag within the current row (tr).
            port_script_element = row.find_element("css selector", "script")
            port_script_content = port_script_element.get_attribute('innerHTML')
            if verbose: print(f"[DEBUG] Row {i+1}: Found port script content for IP {ip}: {port_script_content.strip()}")

            # 7. Extract all XOR expressions and concatenate them to form the port
            # Pattern matches: (var1 ^ var2) expressions
            xor_expressions = re.findall(r'\(([^)]+\^[^)]+)\)', port_script_content)
            
            if not xor_expressions:
                if verbose: print(f"[DEBUG] Row {i+1}: Could not find port calculation expressions for IP {ip}")
                continue
            
            # Build JavaScript to evaluate all XOR expressions and concatenate them
            port_calc_js = "return String(" + " + String(".join(xor_expressions) + ")" * len(xor_expressions)
            
            if verbose: print(f"[DEBUG] Row {i+1}: Executing port script for IP {ip}: `{port_calc_js}`")
            
            port = sb.execute_script(port_calc_js)
            
            if ip and port:
                proxy_str = f"{ip}:{port}"
                if verbose: print(f"[DEBUG] Row {i+1}: Successfully deobfuscated proxy: {proxy_str}")
                found_proxies.add(proxy_str)
            else:
                if verbose: print(f"[DEBUG] Row {i+1}: Deobfuscation for IP {ip} resulted in an empty or invalid port: '{port}'")

        except Exception as e:
            if verbose: print(f"[DEBUG] Row {i+1}: Skipped due to an error during processing: {e}")
            continue
            
    return found_proxies
def scrape_from_spysone(sb: BaseCase, verbose: bool = False) -> List[str]:
    """
    Scrapes spys.one using a browser to handle JavaScript and Cloudflare challenges.
    It iterates through different filter payloads to gather a wide range of proxies.
    """
    if verbose:
        print("[RUNNING] 'Spys.one' automation scraper has started.")
    
    all_proxies = set()
    base_url = "https://spys.one/en/free-proxy-list/"
    
    try:
        # Initial visit to solve any potential Cloudflare challenge
        if verbose: print(f"[INFO] Spys.one: Navigating to {base_url} to handle initial challenges...")
        sb.open(base_url)
        
        if turnstile.is_turnstile_challenge_present(sb, 5):
            if verbose: print("[INFO] Spys.one: Cloudflare challenge detected. Solving...")
            sb.uc_gui_click_captcha()
            sb.wait_for_element_present('body > table:nth-child(3)', timeout=25)
            if verbose: print("[SUCCESS] Spys.one: Challenge solved.")

        # Dynamically get the xx0 token from the page
        try:
            xx0_token = sb.get_attribute('input[name="xx0"]', 'value')
            if verbose: print(f"[DEBUG] Dynamically extracted xx0 token: {xx0_token}")
        except Exception as e:
            if verbose: print(f"[ERROR] Could not find xx0 token on page, scraper may fail: {e}")
            return []

        # Update payloads with the dynamic token
        payloads = [
            {'xx0': xx0_token, 'xpp': '5', 'xf1': '0', 'xf2': '0', 'xf4': '0', 'xf5': '0'}, # All
            {'xx0': xx0_token, 'xpp': '5', 'xf1': '0', 'xf2': '0', 'xf4': '0', 'xf5': '2'}, # SOCKS
            {'xx0': xx0_token, 'xpp': '5', 'xf1': '1', 'xf2': '0', 'xf4': '0', 'xf5': '1'}, # HTTP - ANM+HIA
            {'xx0': xx0_token, 'xpp': '5', 'xf1': '2', 'xf2': '0', 'xf4': '0', 'xf5': '1'}, # HTTP - NOA
            {'xx0': xx0_token, 'xpp': '5', 'xf1': '3', 'xf2': '0', 'xf4': '0', 'xf5': '1'}, # HTTP - ANM
            {'xx0': xx0_token, 'xpp': '5', 'xf1': '4', 'xf2': '0', 'xf4': '0', 'xf5': '1'}, # HTTP - HIA
        ]

        # Iterate through all payloads to get different proxy lists
        for i, payload in enumerate(payloads):
            if verbose:
                print(f"[INFO] Spys.one: Processing page {i+1}/{len(payloads)} with payload: {payload}")
            
            # Use JavaScript to create and submit a form with the current payload.
            form_js = f"var form = document.createElement('form'); form.method = 'POST'; form.action = '{base_url}';"
            for key, value in payload.items():
                form_js += f"var i_{key}=document.createElement('input'); i_{key}.type='hidden'; i_{key}.name='{key}'; i_{key}.value='{value}'; form.appendChild(i_{key});"
            form_js += "document.body.appendChild(form); form.submit();"
            sb.execute_script(form_js)
            
            # Wait for the page to reload with the new proxy list
            try:
                sb.wait_for_element_present('body > table:nth-child(3)', timeout=15)
            except Exception:
                if verbose: print(f"[WARN] Spys.one: Timed out waiting for page {i+1} to load. Skipping.")
                continue

            # Extract and deobfuscate proxies from the loaded page
            newly_found = _extract_and_deobfuscate(sb, verbose)
            
            if verbose:
                print(f"[INFO]   ... Found {len(newly_found)} proxies on this page. Total unique: {len(all_proxies | newly_found)}")
            
            all_proxies.update(newly_found)
            
            time.sleep(1.5) # Be polite between requests

    except Exception as e:
        if verbose:
            print(f"[ERROR] A critical exception occurred in Spys.one scraper: {e}")

    if verbose:
        print(f"[INFO] Spys.one: Finished. Found a total of {len(all_proxies)} unique proxies.")
    
    return sorted(list(all_proxies))