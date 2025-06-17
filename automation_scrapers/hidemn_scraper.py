import time
import undetected_chromedriver as uc
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
from typing import List

from CloudflareBypassForScraping.CloudflareBypasser import CloudflareBypasser


# --- Import our powerful, centralized extraction function ---
from scrapers.proxy_scraper import extract_proxies_from_content

# --- Configuration ---
URL_TEMPLATE = "https://hide.mn/en/proxy-list/?start={offset}"
DELAY_SECONDS = 2.0

def scrape_from_hidemn(verbose: bool = True) -> List[str]:
    """
    NOT WORKING.
    hide.mn uses Cloudflare's turnstile; an advanced anti-bot security measure.
    A robust semi-automated scraper for hide.mn. It waits for the user
    to solve the advanced Cloudflare challenge and then scrapes the content.
    """
    if verbose:
        print("[RUNNING] 'Hide.mn' semi-automated scraper has started.")
    
    all_proxies = set()
    driver = None
    offset = 0
    
    try:
        if verbose:
            print("[INFO] Hide.mn: Initializing browser in VISIBLE mode.")
        
        options = uc.ChromeOptions()
        options.add_argument("--window-size=1920,1080")
        driver = uc.Chrome(options=options, use_subprocess=True)
        # using a very long wait time to give the user plenty of time
        wait = WebDriverWait(driver, 120) 

        print("\n" + "="*70)
        print("ACTION REQUIRED: A browser window will open.")
        print("This website uses an advanced anti-bot system (Cloudflare PAT).")
        print("On each page, please click the 'Verify you are human' checkbox.")
        print("The script will automatically detect your success and continue.")
        print("="*70 + "\n")
        # time.sleep(5)

        # while True:
        url = URL_TEMPLATE.format(offset=offset)
        #     if verbose:
        #         print(f"[INFO] Hide.mn: Navigating to page with offset {offset}...")
            
        driver.get(url)
            # WebDriverWait(driver, 120000)


     

        try:
            # Wait for the CAPTCHA iframe to be visible
            time.sleep(10)
            max_wait = 40
            start_time = time.time()
            while time.time() - start_time < max_wait:
                # if driver.is_element_present('iframe[title*="challenge"]'):
                print("CAPTCHA iframe found")

                # Use uc_gui_handle_cf() to handle the CAPTCHA
                # driver.uc_gui_handle_cf("iframe[title*='challenge']")
                driver.uc_gui_click_cf("iframe[title*='challenge']")
                print("Used uc_gui_handle_cf() to handle CAPTCHA")
                # return True
                time.sleep(1)

            print("No CAPTCHA iframe found, assuming automatic verification")
            # return True

        except Exception as e:
            print(f"Error handling CAPTCHA challenge: {e}")
            # return False


        

        # cf_bypasser = CloudflareBypasser(driver)
        # cf_bypasser.bypass()
        time.sleep(10)
            # # --- The definitive workflow for a manual-click helper ---
            # try:
            #     # 1. Wait for the iframe to appear, so we know the challenge is ready
            #     iframe_selector = (By.CSS_SELECTOR, 'iframe[src*="challenges.cloudflare.com"]')
            #     if verbose:
            #         print("[INFO] Hide.mn: Waiting for the Cloudflare challenge to appear...")
            #     wait.until(EC.presence_of_element_located(iframe_selector))
                
            #     # 2. Tell the user it's their turn
            #     if verbose:
            #         print("[ACTION] Hide.mn: Challenge is ready. Please click the checkbox in the browser.")
                
            #     # 3. Wait for the result of the user's click: the iframe disappearing
            #     wait.until(EC.invisibility_of_element_located(iframe_selector))
            #     if verbose:
            #         print("[SUCCESS] Hide.mn: Challenge solved! Thank you.")

            # except TimeoutException:
            #     # if the iframe never appeared, maybe we got lucky
            #     if verbose:
            #         print("[INFO] Hide.mn: No Cloudflare challenge was detected. Proceeding...")
            # except Exception as e:
            #     print(f"[WARN] Hide.mn: An error occurred during the challenge phase: {e}")

            # # 4. Now that the challenge is gone, wait for the actual content
            # if verbose:
            #     print("[INFO] Hide.mn: Waiting for proxy table to load...")
            # try:
            #     final_wait = WebDriverWait(driver, 20)
            #     final_wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'table.proxy__t')))
            # except TimeoutException:
            #      if verbose:
            #         print("[ERROR] Hide.mn: Timed out waiting for proxy table. Stopping.")
            #      break

            # page_content = driver.page_source
            
            # if "No proxies found" in page_content:
            #     if verbose:
            #         print(f"[INFO] Hide.mn: Page reports no more proxies. Stopping scrape.")
            #     break

            # newly_found = extract_proxies_from_content(page_content, verbose=False)
            
            # if not newly_found:
            #     if verbose:
            #         print(f"[INFO]   ... No proxies found on this page. Assuming end of list.")
            #     break
                
            # initial_count = len(all_proxies)
            # all_proxies.update(newly_found)
            
            # if verbose:
            #     print(f"[INFO]   ... Found {len(newly_found)} proxies on this page. Total unique: {len(all_proxies)}.")

            # if len(all_proxies) == initial_count and offset > 0:
            #     if verbose:
            #         print("[INFO]   ... No new unique proxies found. Stopping to prevent infinite loop.")
            #     break
            
            # offset += 64
            # time.sleep(DELAY_SECONDS)
    except Exception as e:
        print(f"[ERROR] Hide.mn scraper failed: {e}")
    

    finally:
        if driver:
            if verbose:
                print("[INFO] Hide.mn: Shutting down the browser.")
            driver.quit()

    if verbose:
        print(f"[INFO] Hide.mn: Finished. Found a total of {len(all_proxies)} unique proxies.")
    
    return sorted(list(all_proxies))