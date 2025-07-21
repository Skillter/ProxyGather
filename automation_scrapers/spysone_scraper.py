import time
import re
from typing import List, Set
from seleniumbase import BaseCase
import helper.turnstile as turnstile


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
            
        # time.sleep(100)
        # Check and solve initial turnstile challenge
        if turnstile.is_turnstile_challenge_present(sb, 5):
            if verbose: print("[INFO] Spys.one: Cloudflare challenge detected. Solving...")
            turnstile.uc_gui_click_captcha(sb)
            # sb.uc_gui_handle_cf(sb)
            sb.wait_for_element_present('body > table:nth-child(3)', timeout=20)
            if verbose: print("[SUCCESS] Spys.one: Challenge solved.")
        
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
                    sb.get_element(f'#{dropdown_id}', timeout=5).click()
                    sb.select_option_by_value(f'#{dropdown_id}', value, timeout=5)
                    time.sleep(2)  # Small delay between selections
                

                # sb.execute_script("""
                #     var forms = document.querySelectorAll('form');
                #     if (forms.length > 0) {
                #         forms[0].submit();
                #     }
                # """)
                
                # Wait for page load
                time.sleep(3)
                
                # Check for turnstile after form submission
                if turnstile.is_turnstile_challenge_present(sb, 5):
                    if verbose: print("[INFO] Spys.one: Cloudflare challenge detected. Solving...")
                    # turnstile.uc_gui_click_captcha(sb)
                    sb.uc_gui_click_x_y(240, 330)
                    
                    sb.wait_for_element_present('body > table:nth-child(3)', timeout=20)
                    if verbose: print("[SUCCESS] Spys.one: Challenge solved.")
                
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