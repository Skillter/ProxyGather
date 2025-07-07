from DrissionPage import ChromiumPage, ChromiumOptions
from DrissionPage.errors import ElementNotFoundError, WaitTimeoutError
import time

# --- Step 1: Configure the browser to evade detection ---
# This is the most critical part for bypassing advanced Cloudflare protection.
co = ChromiumOptions()

# This method automatically finds a free port and, crucially,
# loads a pre-configured arguments file to make the browser
# appear less like an automation tool.
co.auto_port() 
# You can also manually specify a path to a custom arguments file:
# co.set_argument_file(r'path/to/your/options.json')

# --- Step 2: Launch the browser with the new options ---
page = ChromiumPage(co)

# The actual URL you want to visit.
url = "https://hide.mn/en/proxy-list/?start=192#list"

try:
    print(f"Navigating to: {url}")
    page.get(url)

    # --- The "Find and Click" Strategy with Shadow DOM Piercing ---
    locator = 'css:#NMOK7 > div > div -> css:iframe -> css:input[type=checkbox]'
    
    print("Waiting for the interactive CAPTCHA checkbox...")
    
    # Wait for the element to be present and clickable
    checkbox = page.ele(locator, timeout=20)
    
    print("Checkbox found. Simulating human-like mouse click...")
    
    # --- Step 3: Use a more human-like click method ---
    # .click() is instant. .click.by_mouse() simulates cursor movement.
    checkbox.click.by_mouse()
    
    print("Successfully clicked the CAPTCHA checkbox.")

    # --- Wait for the Result ---
    print("Waiting for verification and page to load...")
    
    destination_element_locator = 'css:table.proxy__t'
    page.wait.ele_displayed(destination_element_locator, timeout=15)
    
    print("Successfully bypassed the challenge page!")
    print(f"Landed on destination page: {page.url}")
    
    # Now you can proceed to scrape the data
    proxy_table = page.ele(destination_element_locator)
    print(f"Found proxy table with {len(proxy_table.s('css:tbody tr'))} rows.")


except (ElementNotFoundError, WaitTimeoutError) as e:
    print(f"\n--- Automation Failed ---")
    print(f"Error: Could not find or interact with an element in time.")
    print(f"Details: {e}")
    print("\nTroubleshooting:")
    print("1. Cloudflare successfully detected automation. The anti-detection arguments are the best defense.")
    print("2. The page structure might have changed. Verify locators manually.")
    print("3. Consider using residential or rotating proxies if your IP is flagged.")
    page.save(save_name='failure_screenshot')
    print("Saved 'failure_screenshot.png' and '.html' for debugging.")


finally:
    print("\nClosing browser.")
    # page.quit()