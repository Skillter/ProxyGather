import asyncio
import nodriver as uc
import logging
import os

# Configure logging to provide clear, structured output.
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# For deeper debugging of nodriver itself, you can uncomment the following line
# logging.getLogger("nodriver").setLevel(logging.DEBUG)

async def sophisticated_cloudflare_bypass():
    """
    A sophisticated and failure-resistant Cloudflare bypass script using nodriver.
    This script includes detailed logging, retry mechanisms, and error handling.
    """
    browser = None
    target_url = "https://hide.mn/en/proxy-list/?start=192"
    page_content_after_bypass = ""

    logger.info("--- Starting Cloudflare Bypass Script ---")

    try:
        # --- 1. Browser Configuration ---
        logger.info("Configuring browser...")
        # Using a specific, realistic user-agent is crucial.
        user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36'

        browser_args = [
            f'--user-agent={user_agent}',
            '--window-size=1920,1080',
            '--no-sandbox',
            '--disable-dev-shm-usage',
            '--disable-gpu',
            '--log-level=0'
        ]

        # --- 2. Browser Initialization ---
        logger.info("Launching browser...")
        browser = await uc.start(
            browser_args=browser_args,
            headless=False
        )
        logger.info("Browser launched successfully.")

        page = await browser.get(target_url)
        logger.info(f"Initial navigation to {target_url} requested.")

        # --- 3. Main Bypass Loop with Retry ---
        max_retries = 5
        for attempt in range(max_retries):
            logger.info(f"--- Bypass Attempt {attempt + 1} of {max_retries} ---")
            await asyncio.sleep(4)  # Wait for the page to potentially load/present a challenge

            page_content = await page.get_content()
            logger.debug(f"Page content length for attempt {attempt + 1}: {len(page_content)}")

            await page.verify_cf("cf.png", True)
            await asyncio.sleep(5)

            # --- 4. Challenge Detection ---
            if "Just a moment..." in page_content or "Verify you are human" in page_content:
                logger.info("Cloudflare challenge page detected.")

                # Try to find the Turnstile iframe. This is a common element in modern CF challenges.
                iframe = await page.select('iframe[src*="challenges.cloudflare.com"]')

                if iframe:
                    logger.info("Found Cloudflare Turnstile iframe. Waiting for automatic resolution...")
                    await asyncio.sleep(10) # Give it a generous amount of time to solve
                else:
                    logger.warning("No Turnstile iframe found. Checking for legacy checkbox...")
                    checkbox = await page.select('input[type=checkbox]')
                    if checkbox:
                        logger.info("Found legacy checkbox challenge. Attempting to click.")
                        try:
                            await checkbox.click()
                            logger.info("Checkbox clicked. Waiting for redirection...")
                            await asyncio.sleep(8)
                        except Exception as e:
                            logger.error(f"Failed to click checkbox on attempt {attempt + 1}: {e}")
                            await page.save_screenshot(f"failure_screenshot_attempt_{attempt + 1}.png")
                    else:
                        logger.warning("No known challenge element found. Waiting to see if page resolves on its own.")
                        await asyncio.sleep(5)

            # --- 5. Verification ---
            logger.info("Verifying bypass status...")
            page_content_after_bypass = await page.get_content()
            if "Just a moment..." not in page_content_after_bypass and "Verify you are human" not in page_content_after_bypass:
                logger.info("SUCCESS: Cloudflare bypass appears successful!")
                logger.info(f"Final Page Title: {await page.evaluate('document.title')}")
                logger.info("--- Script Finished Successfully ---")
                # The final content is now in page_content_after_bypass if you need to use it.
                return
            else:
                logger.warning(f"Still on challenge page after attempt {attempt + 1}.")
                if attempt < max_retries - 1:
                    logger.info("Reloading page and retrying...")
                    await page.reload()
                else:
                    logger.error("All bypass attempts failed.")
                    await page.save_screenshot("cloudflare_bypass_failed_final.png")
                    logger.info("Final failure screenshot saved.")

    except Exception as e:
        logger.critical(f"--- An Unhandled Error Occurred ---", exc_info=True)
        if browser:
            try:
                if 'page' in locals() and page:
                    await page.save_screenshot("error_screenshot.png")
                    logger.info("Saved error screenshot to 'error_screenshot.png'")
            except Exception as se:
                logger.error(f"Could not save screenshot during error handling: {se}")
    finally:
        # --- 6. Cleanup ---
        if browser:
            logger.info("--- Cleaning up and closing browser ---")
            await browser.close()
            logger.info("Browser closed.")

if __name__ == "__main__":
    try:
        asyncio.run(sophisticated_cloudflare_bypass())
    except KeyboardInterrupt:
        logger.info("Script execution cancelled by user.")