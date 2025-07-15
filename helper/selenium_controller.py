import logging
import time
from seleniumbase import BaseCase, SB

# Setup logging
logging.basicConfig(
    level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s'
)

def pass_cloudflare_challenge(sb: BaseCase) -> bool:
    """
    Attempts to solve a Cloudflare Turnstile challenge using the focus-dependent
    GUI-based method. This is the centralized solver function.
    
    Args:
        sb: The SeleniumBase BaseCase instance.
    Returns:
        True if the challenge was passed or not present, False otherwise.
    """
    logging.info("Attempting to bypass Cloudflare challenge (GUI method)...")
    try:
        # If the challenge isn't there to begin with, we succeed.
        challenge_iframe = 'iframe[src*="challenges.cloudflare.com"]'
        if not sb.is_element_visible(challenge_iframe, timeout=7):
            logging.info("No Cloudflare challenge detected. Proceeding.")
            return True

        # Bring the current browser window to the front to ensure it gets the click.
        sb.bring_to_front()
        time.sleep(0.2)  # Small delay to allow the OS to switch focus
        
        # Use the original, reliable GUI-based method
        sb.uc_gui_handle_captcha()

        # The best confirmation of success is the iframe disappearing.
        sb.wait_for_element_not_visible(challenge_iframe, timeout=15)
        
        logging.info("Successfully solved Cloudflare challenge.")
        return True

    except Exception as e:
        # If an error occurred, do a final check. Maybe the challenge was already gone.
        if not sb.is_element_present('iframe[src*="challenges.cloudflare.com"]'):
            logging.info("Challenge was not present after error. Assuming success.")
            return True
        
        logging.error(f"Failed to solve Cloudflare challenge with GUI method: {e}")
        sb.save_screenshot("captcha_gui_fail.png")
        return False

def run_cloudflare_bypass_on_demo_site(sb: BaseCase):
    """
    Navigates to the demo site and attempts to solve the Cloudflare challenge.
    
    Args:
        sb: The SeleniumBase BaseCase instance.
    """
    if not sb.undetectable:
        logging.warning("Test is not running in UC Mode. Creating new UC driver.")
        sb.get_new_driver(undetectable=True)

    logging.info("Navigating to test page...")
    sb.uc_open_with_reconnect("https://nopecha.com/demo/cloudflare", 3)

    sb.set_messenger_theme(theme="flat", location="top_center")
    sb.post_message("Page loaded. Attempting bypass...")
    
    if pass_cloudflare_challenge(sb):
        logging.info(f"Successfully landed on page: {sb.get_title()}")
        sb.post_message("Cloudflare Challenge Bypassed!", duration=3)
    else:
        logging.error("Could not complete the main task.")
        sb.fail("Could not bypass the Cloudflare challenge.")

    logging.info("Example finished. Browser will be open for 3 more seconds.")
    sb.sleep(3)

def test_cloudflare_bypass_on_demo_site(self):
    """
    This is the main test method.
    It now simply calls our reusable helper function.
    """
    run_cloudflare_bypass_on_demo_site(self)

if __name__ == "__main__":
    with SB(uc=True, headed=True, disable_csp=True) as sb:
        run_cloudflare_bypass_on_demo_site(sb)
    print("did the browser close now?")
    time.sleep(10)