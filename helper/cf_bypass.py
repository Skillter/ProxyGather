import asyncio
from types import CoroutineType, NoneType
from typing import Any, Optional
import DrissionPage as drissionpage
import nodriver 
import logging
import sys
import time

from helper.window_manager import *

async def wait_until_present(tab: nodriver.Tab):
    """
    Waits for a Cloudflare Turnstile checkbox to be present, visible, and enabled.

    Args:
        browser: The nodriver.Browser instance.

    The function will poll for the checkbox within its iframe and timeout after 15 seconds
    if the checkbox does not become ready for interaction.
    """
    # Selector for the Cloudflare Turnstile iframe
    iframe_selector = 'iframe[src*="challenges.cloudflare.com"]'
    # Selector for the checkbox inside the iframe
    checkbox_selector = 'input[type="checkbox"]'
    timeout = 15
    

    try:
        if not tab:
            logging.error("The provided tab is invalid.")
            return

        logging.info(f"Waiting for captcha to be ready (timeout: {timeout}s)...")
        
        # Use asyncio.timeout for a clean 15-second overall timeout
        async with asyncio.timeout(timeout):
            checkbox_ready = False
            while not checkbox_ready:
                try:
                    # 1. Find the iframe. Use a short timeout to allow for quick polling.
                    iframe_element = await tab.find(iframe_selector, timeout=1)
                    
                    iframe_page = await tab.find(iframe_element)

                    # 2. Find the checkbox within the iframe.
                    checkbox = await iframe_page.find(checkbox_selector, timeout=1)
                    
                    # 3. Check if the checkbox is visible and enabled.
                    if await checkbox.is_displayed() and await checkbox.is_enabled():
                        logging.info("SUCCESS: Captcha checkbox is ready to be clicked.")
                        
                        # ---
                        # --- NEXT CODE EXECUTES HERE (ON SUCCESS)
                        # --- For example, you can now click the checkbox:
                        # await checkbox.click()
                        # logging.info("Checkbox clicked.")
                        # ---
                        
                        checkbox_ready = True # Exit the while loop
                        return # Exit the function successfully

                    else:
                        # The checkbox element exists but isn't interactable yet.
                        logging.info("Captcha found, but not yet visible or enabled. Waiting...")

                except (asyncio.TimeoutError):
                    # This is expected and normal if the iframe/checkbox hasn't loaded.
                    logging.info("Captcha not found yet, polling...")
                
                # Wait for a short duration before the next poll.
                await asyncio.sleep(0.5)
        
    except asyncio.TimeoutError:
        logging.warning(f"TIMEOUT: Captcha did not become ready within {timeout} seconds.")
    
    except Exception as e:
        logging.error(f"An unexpected error occurred while waiting for the captcha: {e}")

    # ---
    # --- NEXT CODE EXECUTES HERE (IF A TIMEOUT OR ERROR OCCURRED)
    # --- Your script will continue from here if the checkbox was not successfully found and ready.
    # ---
    logging.info("Continuing script execution after the wait period.")

# async def wait_until_present(browser: drissionpage.ChromiumPage):
#     raise NotImplementedError()

async def pass_cf(pid: int = None):
    """
    Automatically passes the cloudflare check present on the website,
    using image recognition and system simulated click.

    Requires visible window (no headless mode).

    If pid(process id) is passed and the system is Windows, it will try to hide the window, and only show it for a split second when its needed. 
    """
    template_image = "tests/cf.old.png" # TODO: Detect the type of the captcha and assign the correct image


    try:
        # 1. Move off-screen for the time being
        move_offscreen(pid)

        retry = 0
        max_retries = 5
        while retry < max_retries:
            logging.info(f"Attempt {retry + 1}/{max_retries} to find and click the Cloudflare challenge.")
            
            found_location = None
            # 2-5. Use the context manager to handle window visibility for the click operation
            with ManageWindowVisibilityByPID(pid):
                # Inside this block, the window is visible and on-screen
                found_location = find_and_click(template_image, confidence=0.8)
                await asyncio.sleep(0.02)
            if found_location:
                logging.info(f"Successfully found and clicked the challenge at: {found_location}")
                retry += 1
                break  # TODO: if the user moved the cursor too fast, the click can get mispositioned and fail
            else:
                logging.warning("Could not find the challenge image on the screen.")
                retry += 1

            await asyncio.sleep(1) # wait 1 sec every try
        
        if retry == max_retries:
            logging.error("Failed to solve the Cloudflare challenge after multiple retries.")
        

    except Exception as e:
        logging.error("--- An Unhandled Error Occurred ---", exc_info=True)


