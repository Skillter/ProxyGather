import asyncio
import logging
import os
import time
import platform
from typing import Optional, Tuple

# browser automation imports
from DrissionPage import ChromiumPage, ChromiumOptions, Chromium

# helper imports
from helper.image_recognition import find_and_click
from helper.window_manager import ManageWindowVisibilityByPID

# setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# platform-specific setup
IS_WINDOWS = platform.system() == 'Windows'
IS_LINUX = platform.system() == 'Linux'

def is_display_running() -> bool:
    """Checks if a display server is running on Linux."""
    if not IS_LINUX:
        return True
    return os.environ.get('DISPLAY') is not None

if IS_LINUX:
    try:
        from pyvirtualdisplay import Display
        VIRTUAL_DISPLAY_AVAILABLE = True
    except ImportError:
        VIRTUAL_DISPLAY_AVAILABLE = False
        logging.warning("pyvirtualdisplay not available. Image recognition will fail.")
else:
    VIRTUAL_DISPLAY_AVAILABLE = False

class DrissionController:
    """
    Manages a single, persistent DrissionPage browser instance.
    Handles virtual display on Linux and provides helpers for browser automation.
    """
    def __init__(self, use_virtual_display: bool = None, display_size: Tuple[int, int] = (800, 600)):
        self.display_size = display_size
        self.display = None
        self.browser: Optional[Chromium] = None

        if use_virtual_display is None:
            if IS_LINUX and not is_display_running() and VIRTUAL_DISPLAY_AVAILABLE:
                logging.info("Auto-detected Linux without a display. Will start a virtual one.")
                self.use_virtual_display = True
            else:
                self.use_virtual_display = False
        else:
            self.use_virtual_display = use_virtual_display and IS_LINUX and VIRTUAL_DISPLAY_AVAILABLE
            if use_virtual_display and is_display_running():
                logging.warning("A display is already running, but a virtual one was also requested.")

    def __enter__(self):
        """Starts the virtual display if required."""
        if self.use_virtual_display:
            logging.info(f"Starting virtual display with size {self.display_size}")
            self.display = Display(visible=False, size=self.display_size)
            self.display.start()
            time.sleep(1)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Cleans up resources by closing the browser and stopping the virtual display."""
        logging.info("Cleaning up resources...")
        self.close_browser()
        if self.display:
            self.display.stop()

    def get_browser(self, expect_captcha: bool = False, headless: bool = True) -> Chromium:
        """
        Returns the existing browser instance or creates a new one.
        """
        if self.browser and self.browser._is_exists:
            logging.info("Returning existing browser instance.")
            return self.browser

        actual_headless = headless and not expect_captcha
        if expect_captcha and headless:
            logging.warning("Captcha expected, forcing non-headless mode for image recognition.")

        co = ChromiumOptions()
        if actual_headless:
            co.headless()
        
        co.set_argument('--no-sandbox')
        co.set_argument('--disable-dev-shm-usage')
        co.set_argument('--disable-blink-features=AutomationControlled')
        co.set_argument(f'--window-size={self.display_size[0]},{self.display_size[1]}')
        
        logging.info(f"Creating new browser instance (Headless: {actual_headless})")
        self.browser = Chromium(co)
        return self.browser

    def close_browser(self):
        """Closes the browser instance if it's running."""
        if self.browser and self.browser._is_exists:
            logging.info("Closing browser instance.")
            self.browser.quit()
            self.browser = None

    def save_screenshot(self, page: ChromiumPage, filename: str = "temp_screenshot.png") -> Optional[str]:
        """Saves a screenshot of the current page using the browser's own method."""
        try:
            page.get_screenshot(path=filename, full_page=False)
            logging.info(f"Screenshot saved to {filename}")
            return filename
        except Exception as e:
            logging.error(f"Failed to save screenshot using browser method: {e}")
            return None

    async def pass_cloudflare_challenge(self, page: ChromiumPage, max_retries: int = 3) -> bool:
        """
        Attempts to solve a Cloudflare Turnstile challenge on a given page.
        """
        logging.info("Attempting to bypass Cloudflare challenge...")
        
        try:
            logging.info("Trying DOM-based bypass...")
            challenge_iframe = page.ele('xpath://iframe[contains(@src, "challenges.cloudflare.com")]', timeout=5)
            if challenge_iframe:
                checkbox = challenge_iframe.shadow_root.ele('tag:input[type=checkbox]')
                checkbox.click()
                logging.info("Clicked the checkbox via DOM.")
                await asyncio.sleep(5)
                if not page.ele('xpath://iframe[contains(@src, "challenges.cloudflare.com")]', timeout=2):
                    logging.info("SUCCESS: Cloudflare challenge passed (DOM method).")
                    return True
        except Exception as e:
            logging.warning(f"DOM-based bypass failed: {e}. Falling back to image recognition.")


        if not self.browser or not self.browser.process_id:
            logging.error("Cannot use image recognition without a running browser instance.")
            return False
            
        logging.info("Trying image-based bypass...")
        template_image = "tests/checkmark-white.png"
        if not os.path.exists(template_image):
            logging.error(f"Template image not found: {template_image}")
            return False

        for attempt in range(max_retries):
            logging.info(f"Image recognition attempt {attempt + 1}/{max_retries}...")
            
            # use the browser's own screenshot function
            screenshot_file = self.save_screenshot(page, f"temp_attempt_{attempt}.png")
            if not screenshot_file:
                await asyncio.sleep(1)
                continue

            click_location = None
            with ManageWindowVisibilityByPID(self.browser.process_id):
                # tell find_and_click to use our reliable screenshot
                click_location = find_and_click(template_image, confidence=0.8, screenshot_path=screenshot_file)
            
            # os.remove(screenshot_file) # clean up the temp file

            if click_location:
                logging.info("Clicked challenge with image recognition. Waiting for result...")
                await asyncio.sleep(8)
                if not page.ele('xpath://iframe[contains(@src, "challenges.cloudflare.com")]', timeout=2):
                    logging.info("SUCCESS: Cloudflare challenge passed (Image method).")
                    return True
            else:
                logging.warning("Could not find challenge image on screen.")
                await asyncio.sleep(1)

        logging.error("Failed to bypass Cloudflare challenge after all attempts.")
        return False

async def main():
    """Example of how to use the DrissionController."""
    with DrissionController() as controller:
        try:
            browser = controller.get_browser(expect_captcha=True, headless=False)
            tab = browser.new_tab()
            logging.info("Navigating to test page...")
            tab.get("https://nopecha.com/demo/cloudflare")
            
            challenge_passed = await controller.pass_cloudflare_challenge(tab)
            
            if challenge_passed:
                logging.info(f"Successfully landed on page: {tab.title}")
            else:
                logging.error("Could not complete the main task.")

            logging.info("Example finished. Browser will be open for 10 more seconds.")
            await asyncio.sleep(10)

        except Exception as e:
            logging.error(f"An error occurred in the main script: {e}", exc_info=True)

if __name__ == "__main__":
    if not os.path.exists("tests/checkmark-white.png"):
        logging.warning("Template image 'tests/checkmark-white.png' not found. Image recognition will fail.")
    
    asyncio.run(main())