import time
import requests
from typing import List
from seleniumbase import BaseCase
import helper.turnstile as turnstile

from scrapers.proxy_scraper import extract_proxies_from_content

URL_TEMPLATE = "https://hide.mn/en/proxy-list/?start={offset}"
DELAY_SECONDS = 1.5

def _solve_challenge_and_get_creds(sb: BaseCase, url: str, verbose: bool) -> dict:
    """
    Uses the browser to solve a Cloudflare challenge on a given URL
    and returns the necessary cookies and user-agent for direct requests.
    """
    if verbose:
        print(f"[INFO] Hide.mn: Using browser to access {url}...")
    
    sb.open(url)
    
    try:
        if turnstile.is_turnstile_present(sb, 5):
            if verbose:
                print("[INFO] Hide.mn: Cloudflare challenge detected. Attempting to solve...")
            sb.uc_gui_click_captcha()
        
        
        # sb.wait_for_element_present(selector='.table_block > table:nth-child(1)', timeout=20)
        try:
            sb.wait_for_element_present(selector='.table_block > table:nth-child(1)', timeout=20)
        except Exception as e:
            if verbose:
                print("[SUCCESS] Hide.mn: First challenge solving failed, trying alternative method.")
            sb.uc_gui_handle_cf()
            if verbose:
                print("[INFO] Hide.mn: Waiting for the table element...")  
            sb.wait_for_element_present(selector='.table_block > table:nth-child(1)', timeout=20)
        
        if verbose:
            print("[SUCCESS] Hide.mn: Challenge solved or bypassed. Table is present.")
        
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
            print(f"[ERROR] Hide.mn: Failed to solve challenge or extract credentials: {e}")
        return {}

def scrape_from_hidemn(sb: BaseCase, verbose: bool = True) -> List[str]:
    """
    Scrapes hide.mn by first using a browser to solve Cloudflare, then
    switching to direct requests with the obtained session cookies.
    """
    if verbose:
        print("[RUNNING] 'Hide.mn' automation scraper has started.")
    
    all_proxies = set()
    session = requests.Session()
    
    try:
        initial_url = URL_TEMPLATE.format(offset=0)
        creds = _solve_challenge_and_get_creds(sb, initial_url, verbose)
        
        if not creds:
            print("[ERROR] Hide.mn: Could not get initial Cloudflare credentials. Aborting.")
            return []
            
        session.cookies.update(creds['cookies'])
        session.headers.update(creds['headers'])
        
        page_content = sb.get_page_source()
        initial_proxies = extract_proxies_from_content(page_content, verbose=False)
        all_proxies.update(initial_proxies)
        if verbose:
            print(f"[INFO]   ... Hide.mn: Found {len(initial_proxies)} proxies on first page. Total unique: {len(all_proxies)}.")

        offset = 64
        while True:
            url = URL_TEMPLATE.format(offset=offset)
            if verbose:
                print(f"[INFO] Hide.mn: Making direct request to page with offset {offset}...")
            
            try:
                response = session.get(url, timeout=20)
                response.raise_for_status()
                page_content = response.text

                if 'Verifying you are human' in page_content or 'challenges.cloudflare.com' in page_content:
                    if verbose:
                        print("[WARN] Hide.mn: Cloudflare challenge re-appeared. Re-solving with browser...")
                    
                    new_creds = _solve_challenge_and_get_creds(sb, url, verbose)
                    if not new_creds:
                        print("[ERROR] Hide.mn: Failed to re-solve challenge. Aborting.")
                        break
                    
                    session.cookies.update(new_creds['cookies'])
                    session.headers.update(new_creds['headers'])
                    page_content = sb.get_page_source()

                if "No proxies found" in page_content:
                    if verbose: print(f"[INFO] Hide.mn: Page reports no more proxies.")
                    break

                newly_found = extract_proxies_from_content(page_content, verbose=False)
                if not newly_found:
                    if verbose: print(f"[INFO]   ... No proxies found on this page. Assuming end of list.")
                    break
                    
                initial_count = len(all_proxies)
                all_proxies.update(newly_found)
                
                if verbose:
                    print(f"[INFO]   ... Hide.mn: Found {len(newly_found)} proxies. Total unique: {len(all_proxies)}.")

                if len(all_proxies) == initial_count:
                    if verbose: print("[INFO]   ... Hide.mn: No new unique proxies found. Stopping.")
                    break
                
                offset += 64
                time.sleep(DELAY_SECONDS)

            except requests.RequestException as e:
                if verbose:
                    print(f"[ERROR] Hide.mn: Request failed for offset {offset}: {e}. Stopping.")
                break

    except Exception as e:
        if verbose:
            print(f"[ERROR] A critical exception occurred in Hide.mn scraper: {e}")

    if verbose:
        print(f"[INFO] Hide.mn: Finished. Found a total of {len(all_proxies)} unique proxies.")
    
    return sorted(list(all_proxies))