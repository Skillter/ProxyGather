import asyncio
from types import CoroutineType, NoneType
from typing import Any, Optional
import nodriver 
import logging
import sys
import time

from helper.window_manager import *

# async def wait_until_present(browser: drissionpage.ChromiumPage):


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


