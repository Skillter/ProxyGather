import asyncio
from types import CoroutineType, NoneType
from typing import Any, Optional
import nodriver as uc
import logging
import sys
import time
from helper.image_recognition import find_and_click
import helper.window_manager as window_manager
import helper.cf_bypass as cf_bypass

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


async def sophisticated_cloudflare_bypass():
    browser = None
    target_url = "https://hide.mn/en/proxy-list/?start=192"

    browser_args = ['--window-size=400,400']
    if sys.platform == 'win32':
        browser_args.append('--window-position=0,6000')
    
    
    try:
        browser = await uc.start(browser_args=browser_args, headless=False)

        # 1. Move off-screen immediately after launch
        pid = browser._process_pid
        cf_bypass.move_offscreen(pid)

        page = await browser.get(target_url)
        # await asyncio.sleep(10) # Wait for potential challenge to appear

        await cf_bypass.wait_until_present(browser)
        await cf_bypass.pass_cf(pid)
        
        logging.info("Process finished. Waiting a bit before closing.")







        # --- Temporary code for debugging ---
        if sys.platform == 'win32':
            try:
                import win32gui
                import win32con
                import win32process
                import ctypes
            except ImportError:
                print("Please run 'pip install pywin32' for Windows-specific functionality.")
                sys.exit(1)
            await asyncio.sleep(3)
            hwnd = window_manager._find_hwnd_for_pid(pid)
            win32gui.SetWindowPlacement(hwnd, (0, 1, (-1, -1), (-1, -1), (0, 0, 800, 600)))
            win32gui.SetForegroundWindow(hwnd)
            await asyncio.sleep(0.4) # Allow time for window to redraw and gain focus (0.3 works on my machine)
      
        await asyncio.sleep(100) # Keep browser open to verify

    except Exception as e:
        logging.error("--- An Unhandled Error Occurred ---", exc_info=True)
    finally:
        if browser and not isinstance(browser, NoneType):
            await browser.stop()


if __name__ == "__main__":
    if sys.platform == 'win32' and not window_manager.is_admin():
        logging.warning("Script is not running with Administrator privileges. GUI automation might fail.")

    try:
        asyncio.run(sophisticated_cloudflare_bypass())
    except KeyboardInterrupt:
        print("\nScript execution cancelled by user.")