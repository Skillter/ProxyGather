import logging
import threading
import time
from seleniumbase import SB

class CaptchaManager:
    """
    A thread-safe manager to ensure only one browser instance at a time
    is attempting to solve a GUI-based CAPTCHA challenge.
    """
    def __init__(self):
        self._lock = threading.Lock()
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    def solve_challenge(self, sb: SB, tab_handle: str, scraper_name: str) -> bool:
        """
        Acquires a lock, focuses the correct tab, and performs the CAPTCHA-solving routine.
        """
        logging.info(f"[{scraper_name}] Waiting for CAPTCHA solver access...")
        with self._lock:
            logging.info(f"[{scraper_name}] Acquired lock. Solving CAPTCHA in its tab...")
            try:
                # Switch to the scraper's dedicated tab
                sb.switch_to_window(tab_handle)
                
                # Bring the browser window to the foreground to receive GUI events
                sb.bring_to_front()
                time.sleep(0.2) # Allow OS to switch focus

                # Check if the challenge is even present before acting
                challenge_iframe = 'iframe[src*="challenges.cloudflare.com"]'
                if not sb.is_element_visible(challenge_iframe, timeout=7):
                    logging.info(f"[{scraper_name}] No Cloudflare challenge detected.")
                    return True

                # Use the reliable GUI-based method
                sb.uc_gui_handle_captcha()

                # Verify success by waiting for the iframe to disappear
                sb.wait_for_element_not_visible(challenge_iframe, timeout=15)
                logging.info(f"[{scraper_name}] Successfully solved CAPTCHA.")
                return True
            except Exception as e:
                logging.error(f"[{scraper_name}] Failed to solve CAPTCHA: {e}")
                sb.save_screenshot(f"captcha_fail_{scraper_name}.png")
                return False