import asyncio
import logging
import os
import sys
import time
import platform
from typing import Optional, Tuple

# Browser automation imports
from DrissionPage import ChromiumPage, ChromiumOptions

# Image recognition imports
import pyautogui
import cv2
import numpy as np
from pynput.mouse import Button, Controller

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Platform-specific imports and setup
IS_WINDOWS = platform.system() == 'Windows'
IS_LINUX = platform.system() == 'Linux'

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
    def __init__(self, use_virtual_display: bool = None, display_size: Tuple[int, int] = (400, 400)):
        """
        Initialize browser automation with optional virtual display.
        
        Args:
            use_virtual_display: Whether to use virtual display. If None, auto-detect based on platform.
            display_size: Size of virtual display (only used on Linux)
        """
        self.display_size = display_size
        self.display = None
        self.page = None
        
        # Auto-detect virtual display usage
        if use_virtual_display is None:
            self.use_virtual_display = IS_LINUX and VIRTUAL_DISPLAY_AVAILABLE
        else:
            self.use_virtual_display = use_virtual_display and IS_LINUX and VIRTUAL_DISPLAY_AVAILABLE
            
        if IS_WINDOWS and use_virtual_display:
            logging.info("Virtual display requested on Windows - will run in normal mode")
            self.use_virtual_display = False
        
    def __enter__(self):
        """Start virtual display if needed when entering context."""
        if self.use_virtual_display:
            logging.info(f"Starting virtual display with size {self.display_size}")
            self.display = Display(visible=False, size=self.display_size)
            self.display.start()
            time.sleep(1)  # Give display time to initialize
            
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Clean up resources when exiting context."""
        if self.page:
            try:
                self.page.quit()
            except:
                pass
                
        if self.display:
            self.display.stop()
            
    def create_browser(self, headless: bool = False) -> ChromiumPage:
        """
        Create and configure DrissionPage browser instance.
        
        Args:
            headless: Whether to run browser in headless mode
            
        Returns:
            Configured ChromiumPage instance
        """
        # Configure browser options
        co = ChromiumOptions()
        
        if headless:
            co.headless()
        
        # Common options for stability
        co.set_argument('--no-sandbox')
        co.set_argument('--disable-dev-shm-usage')
        co.set_argument('--disable-blink-features=AutomationControlled')
        co.set_argument('--window-size=' + str(self.display_size[0]) + ',' + str(self.display_size[1]) )
        
        # Set window size
        # co.set_window_size(self.display_size[0], self.display_size[1])
        
        # Create browser instance
        self.page = ChromiumPage(co)
        logging.info(f"Browser created (headless={headless}, virtual_display={self.use_virtual_display})")
        
        return self.page
        
    def find(self, template_image_path: str, confidence: float = 0.9) -> Optional[Tuple[int, int]]:
        """
        Finds a template image on the screen.
        
        Args:
            template_image_path: Path to the template image
            confidence: Match confidence threshold (0.0 to 1.0)
            
        Returns:
            Center coordinates of found image or None
        """
        if not os.path.exists(template_image_path):
            logging.error(f"Template image not found: {template_image_path}")
            return None
            
        try:
            # Take screenshot
            logging.info("Taking screenshot...")
            screenshot_pil = pyautogui.screenshot()
            haystack_img = cv2.cvtColor(np.array(screenshot_pil), cv2.COLOR_RGB2BGR)
            
            # Load template image
            needle_img = cv2.imread(template_image_path)
            if needle_img is None:
                logging.error("Failed to load template image")
                return None
                
            needle_h, needle_w = needle_img.shape[:2]
            logging.info(f"Template dimensions: {needle_w}x{needle_h}")
            
            # Perform template matching
            result = cv2.matchTemplate(haystack_img, needle_img, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            
            logging.info(f"Best match confidence: {max_val:.4f}")
            
            if max_val >= confidence:
                center_x = max_loc[0] + needle_w // 2
                center_y = max_loc[1] + needle_h // 2
                logging.info(f"Image found at center: ({center_x}, {center_y})")
                return (center_x, center_y)
            else:
                logging.warning(f"Image not found with sufficient confidence")
                return None
                
        except Exception as e:
            logging.error(f"Error during image search: {e}", exc_info=True)
            return None
            
    def find_and_click(self, template_image_path: str, confidence: float = 0.9) -> Optional[Tuple[int, int]]:
        """
        Finds and clicks on a template image.
        
        Args:
            template_image_path: Path to the template image
            confidence: Match confidence threshold
            
        Returns:
            Click coordinates or None
        """
        location = self.find(template_image_path, confidence)
        if not location:
            return None
            
        try:
            mouse = Controller()
            logging.info(f"Clicking at {location}")
            
            # Save current position
            original_position = mouse.position
            
            # Move and click
            mouse.position = location
            time.sleep(0.1)  # Small delay for stability
            mouse.click(Button.left, 1)
            
            # Restore position
            mouse.position = original_position
            
            return location
            
        except Exception as e:
            logging.error(f"Error during click: {e}", exc_info=True)
            return None
            
    async def handle_cloudflare_dom(self) -> bool:
        """
        Handle Cloudflare challenge using DOM manipulation.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Wait for page to be ready
            self.page.wait(1)
            
            # Find the challenge elements
            challenge_solution = self.page.ele("@name=cf-turnstile-response", timeout=5)
            if not challenge_solution:
                logging.info("No Cloudflare challenge found")
                return True
                
            logging.info("Found Cloudflare challenge, attempting to solve via DOM...")
            
            # Navigate through the shadow DOM
            challenge_wrapper = challenge_solution.parent()
            challenge_iframe = challenge_wrapper.shadow_root.ele("tag:iframe")
            challenge_iframe_body = challenge_iframe.ele("tag:body").shadow_root
            challenge_button = challenge_iframe_body.ele("tag:input")
            
            # Click the challenge button
            challenge_button.click()
            logging.info("Clicked Cloudflare challenge button")
            
            # Wait for verification
            await asyncio.sleep(15)
            
            # Check if challenge is gone
            try:
                self.page.ele("@name=cf-turnstile-response", timeout=2)
                return False  # Challenge still present
            except:
                return True  # Challenge passed
                
        except Exception as e:
            logging.error(f"Error handling Cloudflare via DOM: {e}")
            return False
            
    async def pass_cloudflare_challenge(self, max_retries: int = 5) -> bool:
        """
        Attempt to pass Cloudflare challenge using multiple methods.
        
        Args:
            max_retries: Maximum number of attempts
            
        Returns:
            True if successful, False otherwise
        """
        # First try DOM method
        if await self.handle_cloudflare_dom():
            return True
            
        # Fall back to image recognition
        template_image = "tests/cf.old.png"
        
        if not os.path.exists(template_image):
            logging.error(f"Template image not found: {template_image}")
            return False
            
        for attempt in range(max_retries):
            logging.info(f"Cloudflare challenge attempt {attempt + 1}/{max_retries} (image recognition)")
            
            # Try to find and click the challenge
            location = self.find_and_click(template_image, confidence=0.8)
            
            if location:
                logging.info(f"Successfully clicked challenge at {location}")
                await asyncio.sleep(2)
                
                # Check if challenge passed
                try:
                    self.page.ele("@name=cf-turnstile-response", timeout=2)
                except:
                    logging.info("Cloudflare challenge passed!")
                    return True
            else:
                logging.warning("Could not find challenge image")
                
            await asyncio.sleep(1)
            
        logging.error("Failed to pass Cloudflare challenge after all attempts")
        return False
        
    def save_screenshot(self, filename: str = "screenshot.png"):
        """Save a screenshot of the current page."""
        try:
            if self.page:
                # Use DrissionPage's screenshot method
                self.page.get_screenshot(filename)
                logging.info(f"Screenshot saved to {filename}")
            else:
                # Fall back to pyautogui
                screenshot = pyautogui.screenshot()
                screenshot.save(filename)
                logging.info(f"Screenshot saved to {filename} (via pyautogui)")
        except Exception as e:
            logging.error(f"Error saving screenshot: {e}")

# Example usage
async def main():
    """Main automation example."""
    # Detect platform and configure accordingly
    use_virtual = IS_LINUX  # Only use virtual display on Linux
    
    with BrowserAutomation(use_virtual_display=use_virtual) as automation:
        try:
            # Create browser (not headless when using image recognition)
            browser = automation.create_browser(headless=False)
            
            # Navigate to a website
            logging.info("Navigating to example website...")
            browser.get("https://nopecha.com/demo/cloudflare")
            
            # Wait for page to load
            browser.wait(3)
            
            # Handle potential Cloudflare challenge
            if await automation.pass_cloudflare_challenge():
                logging.info("Successfully passed any challenges")
            
            # Take a screenshot for debugging
            automation.save_screenshot("automation_result.png")
            
            # Example: Find and interact with elements
            # Using DrissionPage's powerful selectors
            title = browser.title
            logging.info(f"Page title: {title}")
            
            # Find elements by various methods
            # element = browser.ele("@id=some-id")  # By ID
            # element = browser.ele("@class=some-class")  # By class
            # element = browser.ele("text=Some Text")  # By text content
            
            # Wait a bit before closing
            await asyncio.sleep(2)
            
        except Exception as e:
            logging.error(f"Error during automation: {e}", exc_info=True)
            automation.save_screenshot("error_screenshot.png")

# Platform-specific setup function
def setup_environment():
    """Setup environment based on platform."""
    if IS_WINDOWS:
        logging.info("Running on Windows - no virtual display needed")
        # Windows-specific setup if needed
    elif IS_LINUX:
        logging.info("Running on Linux - virtual display available")
        if not VIRTUAL_DISPLAY_AVAILABLE:
            logging.warning("Install pyvirtualdisplay for virtual display support:")
            logging.warning("pip install pyvirtualdisplay")
    else:
        logging.info(f"Running on {platform.system()}")

if __name__ == "__main__":
    # Setup environment
    setup_environment()
    
    # Check for required files
    if not os.path.exists("tests/cf.old.png"):
        logging.warning("Template image 'tests/cf.old.png' not found.")
        logging.warning("Please provide the Cloudflare challenge button image for image recognition fallback.")
    
    # Run the automation
    asyncio.run(main())
