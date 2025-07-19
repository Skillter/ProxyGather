import time
from seleniumbase import BaseCase
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




def is_turnstile_challenge_present(sb: BaseCase, timeout: int = 5) -> bool:
    """
    Comprehensive detection of Cloudflare Turnstile challenges.
    Checks multiple indicators including iframes, scripts, DOM elements, and JS variables.
    """
    
    # Wait for the page to stabilize (better than sleep)
    sb.wait_for_ready_state_complete()
    
    # List of selectors to check
    turnstile_selectors = [
        # Direct Turnstile elements
        'iframe[src*="challenges.cloudflare.com"]',
        'iframe[src*="turnstile"]',
        'div.cf-turnstile',
        'div[class*="cf-turnstile"]',
        'div[id*="cf-turnstile"]',
        
        # Challenge containers
        'div[class*="challenge-container"]',
        'div[class*="challenge-wrapper"]',
        
        # Turnstile widget containers
        'div[data-turnstile-widget]',
        'div[data-cf-turnstile]',
        
        # Shadow DOM host elements
        'cf-turnstile',
        'cloudflare-app',
    ]
    
    # Check for any of the selectors
    for selector in turnstile_selectors:
        try:
            if sb.is_element_present(selector, timeout=0.5):
                return True
        except:
            continue
    
    # Check for Turnstile scripts in the page
    try:
        scripts_present = sb.execute_script("""
            const scripts = Array.from(document.scripts);
            return scripts.some(script => {
                const src = script.src || '';
                const content = script.textContent || '';
                return src.includes('turnstile') || 
                       src.includes('challenges.cloudflare.com') ||
                       content.includes('turnstile') ||
                       content.includes('cf-challenge');
            });
        """)
        if scripts_present:
            return True
    except:
        pass
    
    # Check for Turnstile-related global JavaScript variables
    try:
        js_vars_present = sb.execute_script("""
            return (
                typeof window.turnstile !== 'undefined' ||
                typeof window.cf !== 'undefined' ||
                typeof window.cfTurnstile !== 'undefined' ||
                typeof window.__CF !== 'undefined' ||
                typeof window.__cfRLUnblockHandlers !== 'undefined'
            );
        """)
        if js_vars_present:
            return True
    except:
        pass
    
    # Check for challenge-related text (multiple languages)
    challenge_texts = [
        "Verifying you are human",
        "Checking your browser",
        "Just a moment",
        "One more step",
        "Please wait",
        "Verify you are human",
        "Security check",
        "Verificando que eres humano",  # Spanish
        "Vérification que vous êtes humain",  # French
        "Überprüfung, ob Sie ein Mensch sind",  # German
    ]
    
    for text in challenge_texts:
        try:
            if sb.is_text_visible(text, timeout=0.5):
                # Additional check: ensure it's not just random page content
                page_title = sb.get_title().lower()
                if any(keyword in page_title for keyword in ['cloudflare', 'attention', 'just a moment']):
                    return True
                # Check if the text is in a challenge-like container
                if sb.is_element_present('div[class*="challenge"]', timeout=0.5):
                    return True
        except:
            continue
    
    # Check for Turnstile in shadow DOM
    try:
        shadow_check = sb.execute_script("""
            function checkShadowDOM(element) {
                if (element.shadowRoot) {
                    const shadowContent = element.shadowRoot.innerHTML;
                    if (shadowContent.includes('turnstile') || 
                        shadowContent.includes('cf-challenge')) {
                        return true;
                    }
                    // Recursively check shadow DOM children
                    const shadowElements = element.shadowRoot.querySelectorAll('*');
                    for (let el of shadowElements) {
                        if (checkShadowDOM(el)) return true;
                    }
                }
                return false;
            }
            
            const allElements = document.querySelectorAll('*');
            for (let element of allElements) {
                if (checkShadowDOM(element)) return true;
            }
            return false;
        """)
        if shadow_check:
            return True
    except:
        pass
    
    # Check meta tags for Cloudflare indicators
    try:
        meta_check = sb.execute_script("""
            const metas = document.getElementsByTagName('meta');
            for (let meta of metas) {
                const content = (meta.content || '').toLowerCase();
                const name = (meta.name || '').toLowerCase();
                if (content.includes('cloudflare') || 
                    name.includes('cf-') ||
                    content.includes('turnstile')) {
                    return true;
                }
            }
            return false;
        """)
        if meta_check:
            return True
    except:
        pass
    
    # Check for invisible/hidden Turnstile challenges
    try:
        hidden_elements = sb.execute_script("""
            const elements = document.querySelectorAll('div, iframe');
            for (let el of elements) {
                const style = window.getComputedStyle(el);
                const classes = el.className || '';
                const id = el.id || '';
                
                // Check if element is related to Turnstile but hidden
                if ((classes.includes('turnstile') || 
                     id.includes('turnstile') ||
                     classes.includes('cf-')) &&
                    (style.display === 'none' || 
                     style.visibility === 'hidden' ||
                     parseFloat(style.opacity) === 0)) {
                    return true;
                }
            }
            return false;
        """)
        if hidden_elements:
            return True
    except:
        pass
    
    # Final check: Look for Cloudflare Ray ID (indicates CF protection)
    try:
        if sb.is_element_present('div[class*="ray-id"]', timeout=0.5):
            # If Ray ID is present with challenge elements
            if sb.is_element_present('div[class*="challenge"]', timeout=0.5):
                return True
    except:
        pass
    
    return False


def wait_for_turnstile_completion(sb: BaseCase, max_wait: int = 30) -> bool:
    """
    Waits for Turnstile challenge to complete.
    Returns True if challenge was completed, False if timeout.
    """
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        # Check if we're still on a challenge page
        if not is_turnstile_challenge_present(sb, timeout=2):
            # Additional check: ensure we've navigated away from challenge
            try:
                current_url = sb.get_current_url()
                if 'challenges.cloudflare.com' not in current_url:
                    return True
            except:
                pass
        
        # Check for completion indicators
        try:
            completion_check = sb.execute_script("""
                return (
                    // Check if turnstile callback was executed
                    window.__cfTurnstileCompleted === true ||
                    // Check for success token
                    document.querySelector('input[name="cf-turnstile-response"]')?.value?.length > 0 ||
                    // Check for completion classes
                    document.querySelector('.cf-turnstile-success') !== null
                );
            """)
            if completion_check:
                sb.sleep(0.5)  # Brief wait for redirect
                return True
        except:
            pass
        
        sb.sleep(0.5)
    
    return False



# --- Edited source code of SeleniumBase ---
# --- With removed page reload, to handle POST requests correctly ---
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
                    print("driver.uc_open_with_disconnect(driver.get_current_url(), 3.8) would've executed")
                    # driver.uc_open_with_disconnect(driver.get_current_url(), 3.8)
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
                print("driver.uc_open_with_disconnect(driver.get_current_url(), 3.8)")
                # driver.uc_open_with_disconnect(driver.get_current_url(), 3.8)
                if __is_cdp_swap_needed(driver) and _on_a_captcha_page(driver):
                    _uc_gui_click_x_y(driver, x, y, timeframe=0.32)
                else:
                    time.sleep(0.1)
            else:
                print("driver.uc_open_with_reconnect(driver.get_current_url(), 3.8)")
                # driver.uc_open_with_reconnect(driver.get_current_url(), 3.8)
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


