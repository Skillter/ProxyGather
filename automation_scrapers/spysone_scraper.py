import time
import re
import requests
from typing import List, Set, Dict
from seleniumbase import BaseCase
import helper.turnstile as turnstile
from bs4 import BeautifulSoup
import fasteners
import re
import time
from contextlib import suppress
from seleniumbase import config as sb_config
from seleniumbase.fixtures import constants
from seleniumbase.fixtures import js_utils
from seleniumbase.fixtures import page_actions
# from seleniumbase.core.browser_launcher import *
from seleniumbase.core.browser_launcher import _uc_gui_click_x_y, __is_cdp_swap_needed, _on_a_cf_turnstile_page, _on_a_g_recaptcha_page, IS_LINUX, get_gui_element_position, IS_WINDOWS, get_configured_pyautogui, install_pyautogui_if_missing  


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
            uc_gui_click_captcha(sb.driver)
            sb.wait_for_element_present('body > table:nth-child(3)', timeout=25)
            if verbose: print("[SUCCESS] Spys.one: Challenge solved.")
            

        sb.select_option_by_value('#xpp', '5', timeout=5)
        
        if turnstile.is_turnstile_challenge_present(sb, 5):
            sb.sleep(4)
            if verbose: print("[INFO] Spys.one: Cloudflare challenge detected. Solving...")
            # sb.uc_gui_click_captcha()
            uc_gui_click_captcha(sb.driver)
            sb.wait_for_element_present('body > table:nth-child(3)', timeout=25)
            if verbose: print("[SUCCESS] Spys.one: Challenge solved.")


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
            
            time.sleep(1.5)  # Be polite between requests

    except Exception as e:
        if verbose:
            print(f"[ERROR] A critical exception occurred in Spys.one scraper: {e}")

    if verbose:
        print(f"[INFO] Spys.one: Finished. Found a total of {len(all_proxies)} unique proxies.")
    
    return sorted(list(all_proxies))














def _uc_gui_click_captcha(
    driver,
    frame="iframe",
    retry=False,
    blind=False,
    ctype=None,
):
    cdp_mode_on_at_start = __is_cdp_swap_needed(driver)
    _on_a_captcha_page = None
    if ctype == "cf_t":
        if not _on_a_cf_turnstile_page(driver):
            return
        else:
            _on_a_captcha_page = _on_a_cf_turnstile_page
    elif ctype == "g_rc":
        if not _on_a_g_recaptcha_page(driver):
            return
        else:
            _on_a_captcha_page = _on_a_g_recaptcha_page
    else:
        if _on_a_g_recaptcha_page(driver):
            ctype = "g_rc"
            _on_a_captcha_page = _on_a_g_recaptcha_page
        elif _on_a_cf_turnstile_page(driver):
            ctype = "cf_t"
            _on_a_captcha_page = _on_a_cf_turnstile_page
        else:
            return
    install_pyautogui_if_missing(driver)
    import pyautogui
    pyautogui = get_configured_pyautogui(pyautogui)
    i_x = None
    i_y = None
    x = None
    y = None
    visible_iframe = True
    gui_lock = fasteners.InterProcessLock(
        constants.MultiBrowser.PYAUTOGUILOCK
    )
    with gui_lock:  # Prevent issues with multiple processes
        needs_switch = False
        width_ratio = 1.0
        is_in_frame = js_utils.is_in_frame(driver)
        if is_in_frame and driver.is_element_present("#challenge-stage"):
            driver.switch_to.parent_frame()
            needs_switch = True
            is_in_frame = js_utils.is_in_frame(driver)
        if not is_in_frame:
            # Make sure the window is on top
            if __is_cdp_swap_needed(driver):
                driver.cdp.bring_active_window_to_front()
            else:
                page_actions.switch_to_window(
                    driver, driver.current_window_handle, 2, uc_lock=False
                )
        if IS_WINDOWS and not __is_cdp_swap_needed(driver):
            window_rect = driver.get_window_rect()
            width = window_rect["width"]
            height = window_rect["height"]
            win_x = window_rect["x"]
            win_y = window_rect["y"]
            scr_width = pyautogui.size().width
            driver.maximize_window()
            win_width = driver.get_window_size()["width"]
            width_ratio = round(float(scr_width) / float(win_width), 2) + 0.01
            if width_ratio < 0.45 or width_ratio > 2.55:
                width_ratio = 1.01
            sb_config._saved_width_ratio = width_ratio
            driver.minimize_window()
            driver.set_window_rect(win_x, win_y, width, height)
        elif IS_WINDOWS and __is_cdp_swap_needed(driver):
            window_rect = driver.cdp.get_window_rect()
            width = window_rect["width"]
            height = window_rect["height"]
            win_x = window_rect["x"]
            win_y = window_rect["y"]
            scr_width = pyautogui.size().width
            driver.cdp.maximize()
            win_width = driver.cdp.get_window_size()["width"]
            width_ratio = round(float(scr_width) / float(win_width), 2) + 0.01
            if width_ratio < 0.45 or width_ratio > 2.55:
                width_ratio = 1.01
            sb_config._saved_width_ratio = width_ratio
            driver.cdp.minimize()
            driver.cdp.set_window_rect(win_x, win_y, width, height)
        if ctype == "cf_t":
            if (
                driver.is_element_present(".cf-turnstile-wrapper iframe")
                or driver.is_element_present(
                    '[data-callback="onCaptchaSuccess"] iframe'
                )
            ):
                pass
            else:
                visible_iframe = False
                if (
                    frame != "iframe"
                    and driver.is_element_present(
                        "%s .cf-turnstile-wrapper" % frame
                    )
                ):
                    frame = "%s .cf-turnstile-wrapper" % frame
                elif (
                    frame != "iframe"
                    and driver.is_element_present(
                        '%s [name*="cf-turnstile"]' % frame
                    )
                    and driver.is_element_present("%s div" % frame)
                ):
                    frame = "%s div" % frame
                elif (
                    driver.is_element_present('[name*="cf-turnstile-"]')
                    and driver.is_element_present("#challenge-form div > div")
                ):
                    frame = "#challenge-form div > div"
                elif (
                    driver.is_element_present('[name*="cf-turnstile-"]')
                    and driver.is_element_present(
                        '[style="display: grid;"] div div'
                    )
                ):
                    frame = '[style="display: grid;"] div div'
                elif (
                    driver.is_element_present('[name*="cf-turnstile-"]')
                    and driver.is_element_present("[class*=spacer] + div div")
                ):
                    frame = '[class*=spacer] + div div'
                elif (
                    driver.is_element_present('[name*="cf-turnstile-"]')
                    and driver.is_element_present("div.spacer div")
                ):
                    frame = "div.spacer div"
                elif (
                    driver.is_element_present('script[src*="challenges.c"]')
                    and driver.is_element_present(
                        '[data-testid*="challenge-"] div'
                    )
                ):
                    frame = '[data-testid*="challenge-"] div'
                elif driver.is_element_present(
                    "div#turnstile-widget div:not([class])"
                ):
                    frame = "div#turnstile-widget div:not([class])"
                elif driver.is_element_present(
                    'form div:not([class]):has(input[name*="cf-turn"])'
                ):
                    frame = 'form div:not([class]):has(input[name*="cf-turn"])'
                elif (
                    driver.is_element_present('[src*="/turnstile/"]')
                    and driver.is_element_present("form div:not(:has(*))")
                ):
                    frame = "form div:not(:has(*))"
                elif (
                    driver.is_element_present('[src*="/turnstile/"]')
                    and driver.is_element_present(
                        "body > div#check > div:not([class])"
                    )
                ):
                    frame = "body > div#check > div:not([class])"
                elif driver.is_element_present(".cf-turnstile-wrapper"):
                    frame = ".cf-turnstile-wrapper"
                elif driver.is_element_present('[class="cf-turnstile"]'):
                    frame = '[class="cf-turnstile"]'
                elif driver.is_element_present(
                    '[data-callback="onCaptchaSuccess"]'
                ):
                    frame = '[data-callback="onCaptchaSuccess"]'
                else:
                    return
            if (
                driver.is_element_present("form")
                and (
                    driver.is_element_present('form[class*="center"]')
                    or driver.is_element_present('form[class*="right"]')
                    or driver.is_element_present('form div[class*="center"]')
                    or driver.is_element_present('form div[class*="right"]')
                )
            ):
                script = (
                    """var $elements = document.querySelectorAll(
                    'form[class], form div[class]');
                    var index = 0, length = $elements.length;
                    for(; index < length; index++){
                    the_class = $elements[index].getAttribute('class');
                    new_class = the_class.replaceAll('center', 'left');
                    new_class = new_class.replaceAll('right', 'left');
                    $elements[index].setAttribute('class', new_class);}"""
                )
                if __is_cdp_swap_needed(driver):
                    driver.cdp.evaluate(script)
                else:
                    driver.execute_script(script)
            elif (
                driver.is_element_present("form")
                and (
                    driver.is_element_present('form div[style*="center"]')
                    or driver.is_element_present('form div[style*="right"]')
                )
            ):
                script = (
                    """var $elements = document.querySelectorAll(
                    'form[style], form div[style]');
                    var index = 0, length = $elements.length;
                    for(; index < length; index++){
                    the_style = $elements[index].getAttribute('style');
                    new_style = the_style.replaceAll('center', 'left');
                    new_style = new_style.replaceAll('right', 'left');
                    $elements[index].setAttribute('style', new_style);}"""
                )
                if __is_cdp_swap_needed(driver):
                    driver.cdp.evaluate(script)
                else:
                    driver.execute_script(script)
            elif (
                driver.is_element_present("form")
                and driver.is_element_present(
                    'form [id*="turnstile"] > div:not([class])'
                )
            ):
                script = (
                    """var $elements = document.querySelectorAll(
                    'form [id*="turnstile"]');
                    var index = 0, length = $elements.length;
                    for(; index < length; index++){
                    $elements[index].setAttribute('align', 'left');}"""
                )
                if __is_cdp_swap_needed(driver):
                    driver.cdp.evaluate(script)
                else:
                    driver.execute_script(script)
        if not is_in_frame or needs_switch:
            # Currently not in frame (or nested frame outside CF one)
            try:
                i_x, i_y = get_gui_element_position(driver, frame)
                if visible_iframe:
                    driver.switch_to_frame(frame)
            except Exception:
                if visible_iframe:
                    if driver.is_element_present("iframe"):
                        i_x, i_y = get_gui_element_position(driver, "iframe")
                        if driver.is_connected():
                            driver.switch_to_frame("iframe")
                    else:
                        return
            if not i_x or not i_y:
                return
        try:
            if ctype == "g_rc" and not driver.is_connected():
                x = (i_x + 29) * width_ratio
                y = (i_y + 35) * width_ratio
            elif visible_iframe:
                selector = "span"
                if ctype == "g_rc":
                    selector = "span.recaptcha-checkbox"
                    if not driver.is_connected():
                        selector = "iframe"
                element = driver.wait_for_element_present(
                    selector, timeout=2.5
                )
                x = i_x + element.rect["x"] + (element.rect["width"] / 2.0)
                x += 0.5
                y = i_y + element.rect["y"] + (element.rect["height"] / 2.0)
                y += 0.5
            else:
                x = (i_x + 32) * width_ratio
                y = (i_y + 32) * width_ratio
            if driver.is_connected():
                driver.switch_to.default_content()
        except Exception:
            if driver.is_connected():
                try:
                    driver.switch_to.default_content()
                except Exception:
                    return
        if x and y:
            sb_config._saved_cf_x_y = (x, y)
            if not __is_cdp_swap_needed(driver):
                if driver.is_element_present(".footer .clearfix .ray-id"):
                    driver.uc_open_with_disconnect(
                        driver.get_current_url(), 3.8
                    )
                else:
                    driver.disconnect()
            with suppress(Exception):
                _uc_gui_click_x_y(driver, x, y, timeframe=0.32)
                if __is_cdp_swap_needed(driver):
                    time.sleep(float(constants.UC.RECONNECT_TIME) / 2.0)
                    return
    reconnect_time = (float(constants.UC.RECONNECT_TIME) / 2.0) + 0.6
    if IS_LINUX:
        reconnect_time = constants.UC.RECONNECT_TIME + 0.2
    if not x or not y:
        reconnect_time = 1  # Make it quick (it already failed)
    driver.reconnect(reconnect_time)
    caught = False
    if (
        driver.is_element_present(".footer .clearfix .ray-id")
        and not driver.is_element_visible("#challenge-success-text")
    ):
        blind = True
        caught = True
    if blind:
        retry = True
    if retry and x and y and (caught or _on_a_captcha_page(driver)):
        with gui_lock:  # Prevent issues with multiple processes
            # Make sure the window is on top
            if __is_cdp_swap_needed(driver):
                driver.cdp.bring_active_window_to_front()
            else:
                page_actions.switch_to_window(
                    driver, driver.current_window_handle, 2, uc_lock=False
                )
            if driver.is_element_present("iframe"):
                try:
                    driver.switch_to_frame(frame)
                except Exception:
                    try:
                        driver.switch_to_frame("iframe")
                    except Exception:
                        return
                checkbox_success = None
                if ctype == "cf_t":
                    checkbox_success = "#success-icon"
                elif ctype == "g_rc":
                    checkbox_success = "span.recaptcha-checkbox-checked"
                else:
                    return  # If this line is reached, ctype wasn't set
                if driver.is_element_visible("#success-icon"):
                    driver.switch_to.parent_frame(checkbox_success)
                    return
            if blind:
                driver.uc_open_with_disconnect(driver.get_current_url(), 3.8)
                if __is_cdp_swap_needed(driver) and _on_a_captcha_page(driver):
                    _uc_gui_click_x_y(driver, x, y, timeframe=0.32)
                else:
                    time.sleep(0.1)
            else:
                driver.uc_open_with_reconnect(driver.get_current_url(), 3.8)
                if _on_a_captcha_page(driver):
                    driver.disconnect()
                    _uc_gui_click_x_y(driver, x, y, timeframe=0.32)
        if not cdp_mode_on_at_start:
            driver.reconnect(reconnect_time)


def uc_gui_click_captcha(driver, frame="iframe", retry=False, blind=False):
    _uc_gui_click_captcha(
        driver,
        frame=frame,
        retry=retry,
        blind=blind,
        ctype=None,
    )


