import logging
from seleniumbase import BaseCase, SB

# Setup logging
logging.basicConfig(
    level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s'
)

# =================================================================
# REUSABLE HELPER FUNCTIONS
# These functions contain the core logic and can be called from anywhere.
# They accept the SeleniumBase instance (sb) as their main argument.
# =================================================================

def pass_cloudflare_challenge(sb: BaseCase) -> bool:
    """
    Attempts to solve a Cloudflare Turnstile challenge on the current page.
    This is now a standalone function.
    
    Args:
        sb: The SeleniumBase BaseCase instance.
    """
    logging.info("Attempting to bypass Cloudflare challenge...")
    try:
        # Use the sb object passed into the function
        sb.uc_gui_handle_captcha()
    except Exception as e:
        logging.error(f"An error occurred during uc_gui_handle_captcha: {e}")
        sb.save_screenshot("captcha_fail_screenshot.png")
        return False

    challenge_iframe = 'iframe[src*="challenges.cloudflare.com"]'
    try:
        sb.wait_for_element_not_visible(challenge_iframe, timeout=8)
        logging.info("SUCCESS: Cloudflare challenge appears to be passed.")
        return True
    except Exception:
        logging.error("Failed to bypass Cloudflare challenge after click.")
        sb.save_screenshot("challenge_still_present.png")
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

    # Correctly call the standalone helper function
    challenge_passed = pass_cloudflare_challenge(sb)

    if challenge_passed:
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
    # 'self' is the BaseCase instance when run via pytest
    run_cloudflare_bypass_on_demo_site(self)


# This block allows the original file to still be run directly
if __name__ == "__main__":
    # BaseCase.main(__name__, __file__, "--uc")
    with SB(uc=True, headed=True, disable_csp=True) as sb:
        # The 'sb' object is a fully initialized BaseCase instance.
        # Now you can pass it to your reusable function.
        sb.set_messenger_theme(theme="flat", location="top_center")
        sb.post_message("Starting bypass from main_script.py...")
        
        run_cloudflare_bypass_on_demo_site(sb)
        
        sb.post_message("Task complete!")