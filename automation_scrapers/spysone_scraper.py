import time
import re
import requests
from typing import List, Set, Dict
from seleniumbase import BaseCase
import helper.turnstile as turnstile
from bs4 import BeautifulSoup



def _get_browser_cookies(sb: BaseCase) -> Dict[str, str]:
    """Extract cookies from the browser session."""
    cookies = {}
    for cookie in sb.driver.get_cookies():
        cookies[cookie['name']] = cookie['value']
    return cookies

def _extract_and_deobfuscate_from_html(html_content: str, verbose: bool) -> Set[str]:
    """
    Extracts IPs and deobfuscates ports from HTML content.
    This version works with raw HTML instead of browser elements.
    """
    found_proxies = set()
    if verbose: print("[DEBUG] Starting extraction and deobfuscation from HTML...")

    # Find ALL script tags that might contain variable definitions
    all_scripts = re.findall(r'<script[^>]*>([\s\S]*?)</script>', html_content, re.IGNORECASE)
    
    # First pass: Extract ALL simple variable definitions (e.g., n4c3=6216)
    simple_vars = {}
    for script in all_scripts:
        if '=' in script and ';' in script:
            # Match simple assignments like n4c3=6216
            simple_pattern = r'(\w+)=(\d+);'
            for match in re.finditer(simple_pattern, script):
                var_name = match.group(1)
                var_value = int(match.group(2))
                simple_vars[var_name] = var_value
    
    # Second pass: Process XOR operations (e.g., p6h8i9=0^n4c3)
    xor_vars = {}
    for script in all_scripts:
        if '=' in script and '^' in script:
            # Match XOR assignments like p6h8i9=0^n4c3
            xor_pattern = r'(\w+)=(\d+)\^(\w+);'
            for match in re.finditer(xor_pattern, script):
                var_name = match.group(1)
                operand1 = int(match.group(2))
                operand2_name = match.group(3)
                
                if operand2_name in simple_vars:
                    xor_vars[var_name] = operand1 ^ simple_vars[operand2_name]
                elif operand2_name in xor_vars:
                    xor_vars[var_name] = operand1 ^ xor_vars[operand2_name]
    
    # Combine all variables
    all_vars = {**simple_vars, **xor_vars}
    
    if verbose: 
        print(f"[DEBUG] Extracted {len(simple_vars)} simple variables and {len(xor_vars)} XOR variables")
        if len(all_vars) < 50:  # Only print if reasonable number
            print(f"[DEBUG] All variables: {sorted(all_vars.keys())}")

    # Use BeautifulSoup to parse the HTML
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Find all proxy rows
    proxy_rows = soup.find_all('tr', class_=['spy1x', 'spy1xx'])
    if verbose: print(f"[DEBUG] Found {len(proxy_rows)} potential proxy rows in the table.")

    for i, row in enumerate(proxy_rows):
        try:
            # Find the IP address
            ip_element = row.find('font', class_='spy14')
            if not ip_element:
                continue
                
            ip_text = ip_element.get_text()
            ip_match = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', ip_text)
            if not ip_match:
                if verbose: print(f"[DEBUG] Row {i+1}: No IP found in text: '{ip_text}'")
                continue
            ip = ip_match.group(1)

            # Find the script tag within the current row
            port_script = row.find('script')
            if not port_script:
                continue
                
            port_script_content = port_script.string or ""

            # Extract XOR expressions from document.write
            write_match = re.search(r'document\.write\(".*?"\+(.+)\)', port_script_content)
            if not write_match:
                if verbose: print(f"[DEBUG] Row {i+1}: Could not find document.write pattern for IP {ip}")
                continue
            
            expressions_part = write_match.group(1)
            
            # Extract individual XOR expressions
            xor_expressions = re.findall(r'\(([^)]+)\)', expressions_part)
            
            if not xor_expressions:
                if verbose: print(f"[DEBUG] Row {i+1}: No XOR expressions found for IP {ip}")
                continue
            
            # Evaluate each XOR expression
            port_parts = []
            for expr in xor_expressions:
                try:
                    # Parse the XOR expression (e.g., "h8t0t0^i9r8")
                    parts = expr.split('^')
                    if len(parts) == 2:
                        var1 = parts[0].strip()
                        var2 = parts[1].strip()
                        
                        # Look up variables in our combined dictionary
                        if var1 in all_vars and var2 in all_vars:
                            result = all_vars[var1] ^ all_vars[var2]
                            port_parts.append(str(result))
                        else:
                            if verbose: 
                                missing = []
                                if var1 not in all_vars: missing.append(var1)
                                if var2 not in all_vars: missing.append(var2)
                                print(f"[DEBUG] Row {i+1}: Missing variables {missing} for expression '{expr}'")
                            break
                except Exception as e:
                    if verbose: print(f"[DEBUG] Row {i+1}: Failed to evaluate expression '{expr}': {e}")
                    break
            
            if len(port_parts) == len(xor_expressions) and port_parts:
                port = ''.join(port_parts)
                
                if ip and port and port.isdigit():
                    proxy_str = f"{ip}:{port}"
                    if verbose: print(f"[DEBUG] Row {i+1}: Successfully deobfuscated proxy: {proxy_str}")
                    found_proxies.add(proxy_str)
                else:
                    if verbose: print(f"[DEBUG] Row {i+1}: Invalid port '{port}' for IP {ip}")

        except Exception as e:
            if verbose: print(f"[DEBUG] Row {i+1}: Skipped due to an error during processing: {e}")
            continue
            
    return found_proxies

def _extract_and_deobfuscate(sb: BaseCase, verbose: bool) -> Set[str]:
    """
    Browser-based extraction for the initial page.
    This uses the browser's JavaScript engine to evaluate the expressions.
    """
    found_proxies = set()
    if verbose: print("[DEBUG] Starting browser-based extraction and deobfuscation...")

    # Get all proxy rows
    proxy_rows = sb.find_elements('//tr[(@class="spy1x" or @class="spy1xx") and .//font[@class="spy14"]]')
    if verbose: print(f"[DEBUG] Found {len(proxy_rows)} potential proxy rows in the table.")

    for i, row in enumerate(proxy_rows):
        try:
            # Get the IP address
            ip_element = row.find_element("css selector", "font.spy14")
            ip_text = ip_element.get_attribute('textContent')
            ip_match = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', ip_text)
            if not ip_match:
                continue
            ip = ip_match.group(1)

            # Find port script and extract the JavaScript code
            port_script_element = row.find_element("css selector", "script")
            port_script_content = port_script_element.get_attribute('innerHTML')
            
            # Execute the script to get the port
            # Replace document.write with a return statement
            modified_script = port_script_content.replace('document.write("<font class=spy2>:<\\/font>"', 'return ("').replace(')</script>', ')')
            
            try:
                port = sb.execute_script(modified_script)
                if port and str(port).isdigit():
                    proxy_str = f"{ip}:{port}"
                    if verbose: print(f"[DEBUG] Row {i+1}: Successfully extracted proxy: {proxy_str}")
                    found_proxies.add(proxy_str)
            except Exception as e:
                if verbose: print(f"[DEBUG] Row {i+1}: Failed to execute port script: {e}")

        except Exception as e:
            if verbose: print(f"[DEBUG] Row {i+1}: Skipped due to error: {e}")
            continue
            
    return found_proxies

def scrape_from_spysone(sb: BaseCase, verbose: bool = False) -> List[str]:
    """
    Scrapes spys.one using a browser for the initial Cloudflare challenge,
    then uses requests for subsequent pages.
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
            # sb._uc_gui_click_captcha()
            turnstile.uc_gui_click_captcha(sb.driver)
            sb.wait_for_element_present('body > table:nth-child(3)', timeout=25)
            if verbose: print("[SUCCESS] Spys.one: Challenge solved.")
            

        sb.select_option_by_value('#xpp', '5', timeout=5)
        
        if turnstile.is_turnstile_challenge_present(sb, 5):
            sb.sleep(4)
            if verbose: print("[INFO] Spys.one: Cloudflare challenge detected. Solving...")
            # sb.uc_gui_click_captcha()
            turnstile.uc_gui_click_captcha(sb.driver)
            sb.wait_for_element_present('body > table:nth-child(3)', timeout=25)
            if verbose: print("[SUCCESS] Spys.one: Challenge solved.")

        print("waiting a bit for the cookie")
        sb.sleep(5)
        
        # Get the user agent from the browser
        user_agent = sb.execute_script("return navigator.userAgent;")
        if verbose: print(f"[DEBUG] Browser User-Agent: {user_agent}")

        # Get cookies from the browser, including cf_clearance
        cookies = _get_browser_cookies(sb)
        if verbose: 
            print(f"[DEBUG] Extracted cookies: {list(cookies.keys())}")
            if 'cf_clearance' in cookies:
                print("[DEBUG] cf_clearance cookie found!")

        # Dynamically get the xx0 token from the page
        try:
            xx0_token = sb.get_attribute('input[name="xx0"]', 'value')
            if verbose: print(f"[DEBUG] Dynamically extracted xx0 token: {xx0_token}")
        except Exception as e:
            if verbose: print(f"[ERROR] Could not find xx0 token on page, scraper may fail: {e}")
            return []

        # Update payloads with the dynamic token
        payloads = [
            {'xx0': xx0_token, 'xpp': '5', 'xf1': '0', 'xf2': '0', 'xf4': '0', 'xf5': '0'}, # All types
            {'xx0': xx0_token, 'xpp': '5', 'xf1': '0', 'xf2': '0', 'xf4': '0', 'xf5': '2'}, # SOCKS
            {'xx0': xx0_token, 'xpp': '5', 'xf1': '1', 'xf2': '0', 'xf4': '0', 'xf5': '1'}, # HTTP - ANM+HIA
            {'xx0': xx0_token, 'xpp': '5', 'xf1': '2', 'xf2': '0', 'xf4': '0', 'xf5': '1'}, # HTTP - NOA
            {'xx0': xx0_token, 'xpp': '5', 'xf1': '3', 'xf2': '0', 'xf4': '0', 'xf5': '1'}, # HTTP - ANM
            {'xx0': xx0_token, 'xpp': '5', 'xf1': '4', 'xf2': '0', 'xf4': '0', 'xf5': '1'}, # HTTP - HIA
        ]

        # Process the first page with the browser (we're already on it)
        if verbose: print(f"[INFO] Spys.one: Processing initial page with browser...")
        newly_found = _extract_and_deobfuscate(sb, verbose)
        if verbose:
            print(f"[INFO]   ... Found {len(newly_found)} proxies on initial page.")
        all_proxies.update(newly_found)

        # Set up session for requests
        session = requests.Session()
        
        # Set headers including User-Agent
        headers = {
            'User-Agent': user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Origin': 'https://spys.one',
            'Referer': base_url,
        }

        # sb.sleep(20)
                
                
        # Now use requests for subsequent pages (skip the first payload as we already processed it)
        for i, payload in enumerate(payloads[1:], 1):
            if verbose:
                print(f"[INFO] Spys.one: Processing page {i+1}/{len(payloads)} with payload: {payload}")
            
            try:
                # Make POST request with cookies and headers
                response = session.post(
                    base_url,
                    data=payload,
                    headers=headers,
                    cookies=cookies,
                    timeout=30
                )
                
                if response.status_code == 200:
                    # Extract and deobfuscate proxies from the response
                    newly_found = _extract_and_deobfuscate_from_html(response.text, verbose)
                    
                    if verbose:
                        print(f"[INFO]   ... Found {len(newly_found)} proxies on this page. Total unique: {len(all_proxies | newly_found)}")
                    
                    all_proxies.update(newly_found)
                else:
                    if verbose:
                        print(f"[WARN] Spys.one: Got status code {response.status_code} for page {i+1}")
                
            except Exception as e:
                if verbose:
                    print(f"[ERROR] Failed to fetch page {i+1}: {e}")
                continue
            
            time.sleep(5)  # Be polite between requests

    except Exception as e:
        if verbose:
            print(f"[ERROR] A critical exception occurred in Spys.one scraper: {e}")

    if verbose:
        print(f"[INFO] Spys.one: Finished. Found a total of {len(all_proxies)} unique proxies.")
    
    return sorted(list(all_proxies))













