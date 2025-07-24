import time
import re
from typing import Callable, List, Set, Any, TypeVar
from seleniumbase import BaseCase
import helper.turnstile as turnstile
import fasteners
import re
import time
from contextlib import suppress
from seleniumbase import config as sb_config
from seleniumbase.fixtures import constants
from seleniumbase.fixtures import js_utils
from seleniumbase.fixtures import page_actions
from seleniumbase.core.browser_launcher import _uc_gui_click_x_y, __is_cdp_swap_needed, _on_a_cf_turnstile_page, _on_a_g_recaptcha_page, IS_LINUX, get_gui_element_position, IS_WINDOWS, get_configured_pyautogui, install_pyautogui_if_missing  


def _extract_proxies_from_html(html_content: str, verbose: bool = False) -> Set[str]:
    """
    Extract proxies from spys.one HTML using regex.
    Finds patterns like: <font class="spy14">IP<script>...</script>:PORT</font>
    """
    proxies = set()
    
    # Regex pattern to match IP:PORT while ignoring script blocks
    pattern = r'<font class="spy14">(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})<script>.*?</script>:(\d+)</font>'
    
    matches = re.findall(pattern, html_content, re.DOTALL)
    
    for ip, port in matches:
        proxy = f"{ip}:{port}"
        proxies.add(proxy)
    
    if verbose:
        print(f"[DEBUG] Extracted {len(proxies)} proxies from HTML")
    
    return proxies

def _handle_turnstile(sb: BaseCase, verbose: bool, callable_after_page_reload: Callable=None):
    if turnstile.is_turnstile_challenge_present(sb, 10): #5
        if verbose: print("[INFO] Spys.one: Cloudflare challenge detected. Solving...")
        _uc_gui_click_captcha(sb, callable_after_page_reload=callable_after_page_reload)
        # sb.uc_gui_click_x_y(240, 330) # This could work, but is more prone for different setups/less stable
        
        sb.wait_for_element_present('body > table:nth-child(3)', timeout=20)
        if verbose: print("[SUCCESS] Spys.one: Challenge solved.")

def scrape_from_spysone(sb: BaseCase, verbose: bool = False) -> List[str]:
    """
    Scrapes spys.one using automation browser for all pages.
    Compatible with Windows and Linux on Python 3.12.9.
    """
    if verbose:
        print("[RUNNING] 'Spys.one' automation scraper has started.")
    
    all_proxies = set()
    # base_url = "https://spys.one/free-proxy-list/ALL/"
    base_url = "https://spys.one/en/"
    
    
    try:
        # Navigate to the main page
        if verbose: print(f"[INFO] Spys.one: Navigating to {base_url}...")
        sb.open(base_url)
        sb.ad_block()
        
        # time.sleep(100)
        # Check and solve initial turnstile challenge
        _handle_turnstile(sb, verbose)

        try:
            time.sleep(0.5)
            sb.find_element("button.fc-primary-button[aria-label='Consent']", timeout=6).click()
        except Exception as e:
            print("An exception occurred while trying to find and click the cookie consent button.")
            print(e)

        
        # Extract proxies from initial page
        page_content = sb.get_page_source()
        initial_proxies = _extract_proxies_from_html(page_content, verbose)
        all_proxies.update(initial_proxies)
        if verbose: print(f"[INFO] Spys.one: Found {len(initial_proxies)} proxies on initial page.")
        
        try:
            time.sleep(0.5)
            sb.find_element("a[href='/en/free-proxy-list/']", timeout=6).click()
            time.sleep(1)
            sb.js_click('#dismiss-button', all_matches=True, timeout=3)
            # sb.find_element("#dismiss-button", timeout=2).click()
            time.sleep(0.5)
            sb.wait_for_element_present('body > table:nth-child(3)', timeout=20)
        except Exception as e:
            print("An exception occurred while trying to find and click the Proxy search button.")
            print(e)
        
        # Define all page configurations to visit
        # page_configs = [
        #     {'xpp': '5', 'xf1': '0', 'xf2': '0', 'xf4': '0', 'xf5': '0'}, # All types
        #     {'xpp': '5', 'xf1': '0', 'xf2': '0', 'xf4': '0', 'xf5': '2'}, # SOCKS
        #     {'xpp': '5', 'xf1': '1', 'xf2': '0', 'xf4': '0', 'xf5': '1'}, # HTTP - ANM+HIA
        #     {'xpp': '5', 'xf1': '2', 'xf2': '0', 'xf4': '0', 'xf5': '1'}, # HTTP - NOA
        #     {'xpp': '5', 'xf1': '3', 'xf2': '0', 'xf4': '0', 'xf5': '1'}, # HTTP - ANM
        #     {'xpp': '5', 'xf1': '4', 'xf2': '0', 'xf4': '0', 'xf5': '1'}, # HTTP - HIA
        # ]
        page_configs = [
            {'xpp': '5'}, # All types
            {'xpp': '5'}, # All types

        ]
        
        # Process each configuration
        for i, config in enumerate(page_configs):
            if verbose:
                print(f"[INFO] Spys.one: Processing configuration {i+1}/{len(page_configs)}: {config}")
            
            try:
                # sb.execute_script("""
                #     document.querySelectorAll('select.clssel').forEach(function(select) {
                #         select.removeAttribute('onchange');
                #     });
                # """)
                

                for dropdown_id, value in config.items():
                    
                    def callable_after_page_reload():
                        print(f'{dropdown_id} has been pressed')
                        sb.get_element(f'#{dropdown_id}', timeout=5).click()
                        sb.select_option_by_value(f'#{dropdown_id}', value, timeout=5)
                        time.sleep(0.5)  # Small delay between selections
                    callable_after_page_reload()
                    time.sleep(3)
                    _handle_turnstile(sb, verbose, callable_after_page_reload())


                # sb.execute_script("""
                #     var forms = document.querySelectorAll('form');
                #     if (forms.length > 0) {
                #         forms[0].submit();
                #     }
                # """)
                
                # Wait for page load
                time.sleep(3)
                
                # Check for turnstile after form submission

                
                # Extract proxies from current page
                page_content = sb.get_page_source()
                new_proxies = _extract_proxies_from_html(page_content, verbose)
                
                # Calculate newly found unique proxies
                before_count = len(all_proxies)
                all_proxies.update(new_proxies)
                newly_added = len(all_proxies) - before_count
                
                if verbose:
                    print(f"[INFO]   ... Found {len(new_proxies)} proxies, {newly_added} new unique. Total: {len(all_proxies)}")
                
                # Be respectful between page loads
                time.sleep(3)
                
            except Exception as e:
                if verbose:
                    print(f"[ERROR] Failed to process configuration {i+1}: {e}")
                continue
    
    except Exception as e:
        if verbose:
            print(f"[ERROR] A critical exception occurred in Spys.one scraper: {e}")
    
    if verbose:
        print(f"[INFO] Spys.one: Finished. Found a total of {len(all_proxies)} unique proxies.")
    
    return sorted(list(all_proxies))








def _uc_gui_click_captcha(
    sb: BaseCase,
    frame="iframe",
    retry=False,
    blind=False,
    ctype=None,
    callable_after_page_reload: Callable=None
):
    driver = sb.driver
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
                    print("driver.uc_open_with_disconnect(driver.get_current_url(), 3.8)")
                    driver.uc_open_with_disconnect(driver.get_current_url(), 3.8)
                    
                    # --- The fix for spys.one starts here ---
                    # After a reload we lose the POST payload, so we need to send the payload again, before we click the captcha (otherwise turnstile doesn't show up)
                    
                    print("callable_after_page_reload() starts now")
                    callable_after_page_reload()
                    print("callable_after_page_reload() ends now")
                    
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
                print("if blind: driver.uc_open_with_disconnect(driver.get_current_url(), 3.8)")
                driver.uc_open_with_disconnect(driver.get_current_url(), 3.8)
                if __is_cdp_swap_needed(driver) and _on_a_captcha_page(driver):
                    _uc_gui_click_x_y(driver, x, y, timeframe=0.32)
                else:
                    time.sleep(0.1)
            else:
                print("else: driver.uc_open_with_reconnect(driver.get_current_url(), 3.8)")
                driver.uc_open_with_reconnect(driver.get_current_url(), 3.8)
                if _on_a_captcha_page(driver):
                    driver.disconnect()
                    _uc_gui_click_x_y(driver, x, y, timeframe=0.32)
        if not cdp_mode_on_at_start:
            driver.reconnect(reconnect_time)


