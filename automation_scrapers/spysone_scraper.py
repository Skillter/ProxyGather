import re
import time
import random
from typing import List
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

def scrape_from_spysone(sb: BaseCase, verbose: bool = False) -> List[str]:
    """
    Scrapes spys.one by using a browser to navigate, apply filters, handle
    Cloudflare challenges, and deobfuscate ports.
    """
    if verbose: print("[RUNNING] 'Spys.one' automation scraper has started.")
    
    
    all_proxies = set()
    base_url = "https://spys.one/en/free-proxy-list/"
    
    payloads = [
        {'xf1': '0', 'xf5': '0'},  # All Proxies
        {'xf1': '0', 'xf5': '2'},  # SOCKS
        {'xf1': '1', 'xf5': '1'},  # HTTP/S - ANM + HIA
        {'xf1': '2', 'xf5': '1'},  # HTTP/S - NOA
        {'xf1': '3', 'xf5': '1'},  # HTTP/S - ANM
        {'xf1': '4', 'xf5': '1'},  # HTTP/S - HIA
    ]

    try:
        for i, payload in enumerate(payloads):
            if verbose: print(f"[INFO] Spys.one: Scraping page {i+1}/{len(payloads)} with payload {payload}...")
            
            # sb.user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:140.0) Gecko/20100101 Firefox/140.0'
            
            sb.open(base_url)
            sb.wait_for_ready_state_complete()

            solve_cf_if_present(sb, verbose)
            # Now that the page is loaded, interact with the form
            sb.wait_for_element_visible('#xpp')
            # Remove onchange handlers to prevent auto-submit on each selection
            sb.execute_script("document.querySelectorAll('form[method=post] select').forEach(s => s.removeAttribute('onchange'));")
            # Set to 500 proxies per page for maximum efficiency
            print("before 6")
            sb.select_option_by_value('#xpp', '5')
            solve_cf_if_present(sb, verbose)
            
            # Set payload values for the current filter set
            for key, value in payload.items():
                sb.select_option_by_value(f'select[name={key}]', value)

            # Manually submit the form with all filters applied
            sb.execute_script("document.querySelector('form[method=post]').submit();")
            time.sleep(1.5)

            # Check for challenge again after submission, as it can reappear
            solve_cf_if_present(sb, verbose)
            html_content = sb.get_page_source()
            newly_found = _deobfuscate_and_extract(html_content, verbose)
            if verbose:
                print(f"[INFO]   ... Found {len(newly_found)} proxies. Total unique: {len(all_proxies | set(newly_found))}")
            
            all_proxies.update(newly_found)
            time.sleep(random.uniform(2.0, 4.0)) # Be polite between different filter scrapes

    except Exception as e:
        if verbose:
            print(f"[ERROR] A critical exception occurred in Spys.one scraper: {e}")
            sb.save_screenshot("spysone_error.png")
            sb.save_page_source("spysone_error.html")

    if verbose:
        print(f"[INFO] Spys.one: Finished. Found a total of {len(all_proxies)} unique proxies.")
    
    return sorted(list(all_proxies))


def solve_cf_if_present(sb: BaseCase, verbose: bool = False, timeout: int = 7):
    if turnstile.is_turnstile_challenge_present(sb, timeout):
         if verbose: print("[INFO] Spys.one: Cloudflare challenge detected. Solving...")
         sb.uc_gui_click_captcha()
         sb.wait_for_element_present('body > table:nth-child(3)', timeout=10)
         if verbose: print("[SUCCESS] Spys.one: Challenge solved, form is present.")