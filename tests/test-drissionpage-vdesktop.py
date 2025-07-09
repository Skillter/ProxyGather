import asyncio
import logging
import os
import sys
import time
import platform
from typing import Optional, Tuple

# Browser automation imports
from DrissionPage import ChromiumPage, ChromiumOptions

# --- LIBRARIES ARE MOVED BACK TO WHERE THEY BELONG ---
# We cannot import them here because a display is not guaranteed to be ready.
# -----------------------------------------------------

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Platform-specific setup
IS_WINDOWS = platform.system() == 'Windows'
IS_LINUX = platform.system() == 'Linux'

def is_display_running() -> bool:
    if not IS_LINUX:
        return True
    display_var = os.environ.get('DISPLAY')
    if not display_var:
        logging.info("DISPLAY environment variable not set. Assuming no display is running.")
        return False
    try:
        display_num = display_var.split(':')[1].split('.')[0]
        socket_path = f"/tmp/.X11-unix/X{display_num}"
        if os.path.exists(socket_path):
            logging.info(f"Existing display found at {display_var} (socket: {socket_path}).")
            return True
        else:
            logging.warning(f"DISPLAY is set to {display_var}, but socket {socket_path} not found.")
            return False
    except IndexError:
        logging.warning(f"Could not parse display number from DISPLAY variable: {display_var}")
        return False

if IS_LINUX:
    try:
        from pyvirtualdisplay import Display
        VIRTUAL_DISPLAY_AVAILABLE = True
    except ImportError:
        VIRTUAL_DISPLAY_AVAILABLE = False
        logging.warning("pyvirtualdisplay not available. Running without virtual display.")
else:
    VIRTUAL_DISPLAY_AVAILABLE = False

class BrowserAutomation:
    def __init__(self, use_virtual_display: bool = None, display_size: Tuple[int, int] = (1920, 1080)):
        self.display_size = display_size
        self.display = None
        self.page = None
        if use_virtual_display is None:
            if IS_LINUX and not is_display_running():
                if VIRTUAL_DISPLAY_AVAILABLE:
                    logging.info("Auto-detected Linux without a display. Will attempt to start a virtual one.")
                    self.use_virtual_display = True
                else:
                    logging.warning("Auto-detected Linux without a display, but pyvirtualdisplay is not installed. Image recognition will fail.")
                    self.use_virtual_display = False
            else:
                self.use_virtual_display = False
        else:
            self.use_virtual_display = use_virtual_display and IS_LINUX and VIRTUAL_DISPLAY_AVAILABLE
            if use_virtual_display and is_display_running():
                logging.warning("A display is already running, but a virtual display was explicitly requested.")

    def __enter__(self):
        if self.use_virtual_display:
            logging.info(f"Starting virtual display with size {self.display_size}")
            try:
                self.display = Display(visible=False, size=self.display_size)
                self.display.start()
                time.sleep(1)
            except Exception as e:
                logging.error(f"Failed to start virtual display: {e}")
                self.use_virtual_display = False
                raise
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.page:
            try: self.page.quit()
            except: pass
        if self.display:
            self.display.stop()

    def create_browser(self, headless: bool = False) -> ChromiumPage:
        # This method is fine, no imports needed here
        co = ChromiumOptions()
        if headless: co.headless()
        co.set_argument('--no-sandbox')
        co.set_argument('--disable-dev-shm-usage')
        co.set_argument('--disable-blink-features=AutomationControlled')
        co.set_argument('--window-size=' + str(self.display_size[0]) + ',' + str(self.display_size[1]))
        self.page = ChromiumPage(co)
        logging.info(f"Browser created (headless={headless}, virtual_display_active={self.use_virtual_display})")
        return self.page

    def find(self, template_image_path: str, confidence: float = 0.9) -> Optional[Tuple[int, int]]:
        # --- LAZY IMPORTS RESTORED ---
        import pyautogui
        import cv2
        import numpy as np
        # ---
        if not os.path.exists(template_image_path):
            logging.error(f"Template image not found: {template_image_path}")
            return None
        try:
            logging.info("Taking screenshot...")
            screenshot_pil = pyautogui.screenshot()
            haystack_img = cv2.cvtColor(np.array(screenshot_pil), cv2.COLOR_RGB2BGR)
            needle_img = cv2.imread(template_image_path)
            if needle_img is None: return None
            needle_h, needle_w = needle_img.shape[:2]
            result = cv2.matchTemplate(haystack_img, needle_img, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            logging.info(f"Best match confidence: {max_val:.4f}")
            if max_val >= confidence:
                center_x = max_loc[0] + needle_w // 2
                center_y = max_loc[1] + needle_h // 2
                logging.info(f"Image found at center: ({center_x}, {center_y})")
                return (center_x, center_y)
            else:
                return None
        except Exception as e:
            logging.error(f"Error during image search: {e}", exc_info=True)
            return None

    def find_and_click(self, template_image_path: str, confidence: float = 0.9) -> Optional[Tuple[int, int]]:
        # --- LAZY IMPORTS RESTORED ---
        from pynput.mouse import Button, Controller
        # ---
        location = self.find(template_image_path, confidence)
        if not location: return None
        try:
            mouse = Controller()
            original_position = mouse.position
            mouse.position = location
            time.sleep(0.1)
            mouse.click(Button.left, 1)
            mouse.position = original_position
            return location
        except Exception as e:
            logging.error(f"Error during click: {e}", exc_info=True)
            return None

    def save_screenshot(self, filename: str = "screenshot.png"):
        # --- LAZY IMPORTS RESTORED ---
        import pyautogui
        # ---
        try:
            if self.page and self.page.session.is_alive:
                self.page.get_screenshot(path=filename, full_page=True)
                logging.info(f"Screenshot saved to {filename}")
            else:
                pyautogui.screenshot(filename)
                logging.info(f"Screenshot saved to {filename} (via pyautogui)")
        except Exception as e:
            logging.error(f"Error saving screenshot: {e}")

    # ... The other methods (handle_cloudflare_dom, pass_cloudflare_challenge) are fine ...
    async def handle_cloudflare_dom(self) -> bool:
        try:
            self.page.wait(1)
            challenge_solution = self.page.ele("@name=cf-turnstile-response", timeout=5)
            if not challenge_solution: return True
            logging.info("Found Cloudflare challenge, attempting to solve via DOM...")
            challenge_wrapper = challenge_solution.parent()
            challenge_iframe = challenge_wrapper.shadow_root.ele("tag:iframe")
            challenge_iframe_body = challenge_iframe.ele("tag:body").shadow_root
            challenge_button = challenge_iframe_body.ele("tag:input")
            challenge_button.click()
            await asyncio.sleep(15)
            try:
                self.page.ele("@name=cf-turnstile-response", timeout=2)
                return False
            except:
                return True
        except Exception as e:
            logging.error(f"Error handling Cloudflare via DOM: {e}")
            return False
            
    async def pass_cloudflare_challenge(self, max_retries: int = 5) -> bool:
        if await self.handle_cloudflare_dom(): return True
        template_image = "tests/cf.old.png"
        if not os.path.exists(template_image): return False
        for attempt in range(max_retries):
            location = self.find_and_click(template_image, confidence=0.8)
            if location:
                await asyncio.sleep(2)
                try:
                    self.page.ele("@name=cf-turnstile-response", timeout=2)
                except:
                    return True
            await asyncio.sleep(1)
        return False

async def main():
    with BrowserAutomation(use_virtual_display=None) as automation:
        try:
            browser = automation.create_browser(headless=False)
            browser.get("https://nopecha.com/demo/cloudflare")
            browser.wait(3)
            if await automation.pass_cloudflare_challenge():
                logging.info("Successfully passed any challenges")
            automation.save_screenshot("automation_result.png")
            logging.info(f"Page title: {browser.title}")
            await asyncio.sleep(2)
        except Exception as e:
            logging.error(f"Error during automation: {e}", exc_info=True)
            automation.save_screenshot("error_screenshot.png")

if __name__ == "__main__":
    if not os.path.exists("tests/cf.old.png"):
        logging.warning("Template image 'tests/cf.old.png' not found.")
    asyncio.run(main())