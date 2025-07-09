import asyncio
from types import CoroutineType, NoneType
from typing import Any, Optional
import nodriver as uc
import logging
import sys
import time


# --- OS-Specific Imports with error handling ---
if sys.platform == 'win32':
    try:
        import win32gui
        import win32con
        import win32process
        import ctypes
    except ImportError:
        print("Please run 'pip install pywin32' for Windows-specific functionality.")
        sys.exit(1)

from helper.image_recognition import find_and_click

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


offscreen_position = [0, 3000]

# --- OS-Specific Helper Code ---

def is_admin() -> bool:
    """Checks for Administrator privileges on Windows."""
    if sys.platform == 'win32':
        try:
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            return False
    return False

def _find_hwnd_for_pid(target_pid: int) -> Optional[int]:
    """Iterate through windows to find the one matching the target PID."""
    found_hwnd = None
    
    def callback(hwnd, _):
        nonlocal found_hwnd
        # Ensure it's a visible, top-level window.
        if not win32gui.IsWindowVisible(hwnd) or win32gui.GetParent(hwnd) != 0:
            return True # Continue enumeration

        _, process_id = win32process.GetWindowThreadProcessId(hwnd)
        if process_id == target_pid:
            found_hwnd = hwnd
            return False  # Stop enumeration
        return True # Continue enumeration

    win32gui.EnumWindows(callback, None)
    return found_hwnd

class ManageWindowVisibilityByPID:
    """
    Context manager to robustly manage a window's visibility for GUI automation using its PID.
    
    This is designed for Windows and will:
    1. Find the window handle (HWND) from the provided PID.
    2. On entering the context, save the window's current position.
    3. Move the window to a predictable on-screen location (0,0) and bring it to the foreground.
    4. On exiting the context, restore the window to its original position.
    """
    def __init__(self, pid: int):
        if sys.platform != 'win32':
            raise NotImplementedError("This class is only implemented for Windows.")
        self.pid = pid
        self.hwnd = None
        self.original_placement = None

    def __enter__(self):
        logging.info(f"Attempting to manage visibility for window with PID: {self.pid}")
        self.hwnd = _find_hwnd_for_pid(self.pid)
        
        if not self.hwnd:
            logging.warning(f"Could not find window for PID {self.pid}. Cannot manage visibility.")
            return self

        logging.info(f"Found window handle (HWND): {self.hwnd}.")
        try:
            self.original_placement = win32gui.GetWindowPlacement(self.hwnd)
            
            logging.info("Temporarily moving window on-screen to (0,0) for interaction.")
            # Set to a normal state at a fixed on-screen position
            win32gui.SetWindowPlacement(self.hwnd, (0, 1, (-1, -1), (-1, -1), (0, 0, 800, 600)))
            win32gui.SetForegroundWindow(self.hwnd)
            time.sleep(0.4) # Allow time for window to redraw and gain focus (0.3 works on my machine)
        except win32gui.error as e:
            logging.error(f"Error managing window: {e}. It might have been closed.")
            self.hwnd = None # Invalidate handle on error
        
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        if self.hwnd and self.original_placement:
            logging.info("Restoring window to its original position...")
            try:
                # win32gui.SetWindowPlacement(self.hwnd, self.original_placement)
                move_offscreen(self.pid)

            except win32gui.error:
                # The window might have been closed in the meantime.
                logging.warning(f"Could not restore window position for HWND {self.hwnd}, it may no longer exist.")

def move_offscreen(pid: int):
    """Moves the browser window off-screen using its PID (Windows-only)."""
    if sys.platform == 'win32':
        logging.info(f"Attempting to find window for browser process with PID: {pid}")
        hwnd = _find_hwnd_for_pid(pid)
        
        if hwnd:
            logging.info(f"Found window handle (HWND): {hwnd}. Moving it off-screen to {offscreen_position}.")
            logging.info(str(offscreen_position[0]) + " " + str(offscreen_position[1]))
            

            rect = win32gui.GetWindowRect(hwnd)
            width = rect[2] - rect[0]
            height = rect[3] - rect[1]

            # First, make sure the window is not maximized
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

            # Then move it off-screen
            win32gui.SetWindowPos(
                hwnd,
                0,
                offscreen_position[0],
                offscreen_position[1],
                0,
                0,
                win32con.SWP_NOSIZE | win32con.SWP_NOZORDER | win32con.SWP_NOOWNERZORDER
            )



        else:
            logging.warning(f"Could not find window handle for PID {pid}. Window will not be moved.")
    else:
        logging.info("Off-screen window positioning is currently only implemented for Windows.")

