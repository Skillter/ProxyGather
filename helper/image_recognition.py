import asyncio
import nodriver as uc
import logging
import os
import pyautogui
import cv2
import numpy as np
import sys
import time
import ctypes
from pynput.mouse import Button, Controller

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def find(template_image_path: str, confidence: float = 0.9) -> tuple[int, int] | None:
    """
    Finds a template image on the screen and returns the location.

    Args:
        template_image_path (str): The file path to the image to find (the "needle").
        confidence (float): The confidence threshold for the match (0.0 to 1.0). 
                              A higher value means a more exact match is required.
                              Defaults to 0.9.

    Returns:
        tuple[int, int] | None: The (x, y) coordinates of the center of the found image if successful,
                                otherwise None.
    """

    # 1. Check if the template image exists
    if not os.path.exists(template_image_path):
        logging.error(f"Template image not found at path: {template_image_path}")
        return None

    try:
        # 2. Take a screenshot of the entire screen (the "haystack")
        logging.info("Taking screenshot...")
        screenshot_pil = pyautogui.screenshot()
        # Convert the PIL Image to a NumPy array in BGR format for OpenCV
        haystack_img = cv2.cvtColor(np.array(screenshot_pil), cv2.COLOR_RGB2BGR)

        # 3. Load the template image (the "needle")
        logging.info(f"Loading template image: {template_image_path}")
        needle_img = cv2.imread(template_image_path)
        if needle_img is None:
            logging.error("Failed to load template image. Check file integrity.")
            return None
            
        needle_h, needle_w = needle_img.shape[:2]
        logging.info(f"Template dimensions: Width={needle_w}, Height={needle_h}")

        # 4. Perform template matching
        logging.info("Searching for template on screen...")
        # TM_CCOEFF_NORMED is a reliable method that provides a normalized correlation score
        result = cv2.matchTemplate(haystack_img, needle_img, cv2.TM_CCOEFF_NORMED)
        
        # 5. Get the location of the best match
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
        
        logging.info(f"Best match confidence: {max_val:.4f}")

        # 6. Check if the match meets the confidence threshold
        if max_val >= confidence:
            # Get the top-left corner of the matched area
            top_left = max_loc
            
            # Calculate the center of the found area
            center_x = top_left[0] + needle_w // 2
            center_y = top_left[1] + needle_h // 2
            
            logging.info(f"SUCCESS: Image found at top-left: {top_left}, center: ({center_x}, {center_y})")

            return (center_x, center_y)
        else:
            logging.warning(f"Image not found on screen with sufficient confidence (found {max_val:.4f}, need {confidence}).")
            return None

    except Exception as e:
        logging.critical(f"An unexpected error occurred: {e}", exc_info=True)
        return None


def find_and_click(template_image_path: str, confidence: float = None) -> tuple[int, int] | None:
    """
    Finds a template image on the screen and clicks its center.

    Args:
        template_image_path (str): The file path to the image to find (the "needle").
        confidence (float): The confidence threshold for the match (0.0 to 1.0). 
                              A higher value means a more exact match is required.
                              Defaults to 0.9.

    Returns:
        tuple[int, int] | None: The (x, y) coordinates of the center of the found image if successful,
                                otherwise None.
    """
    mouse = Controller()

    target_location: tuple[int, int]

    if confidence is None:
        target_location = find(template_image_path)
    else:
        target_location = find(template_image_path, confidence)

    try:
        # Move the mouse and click
        
        logging.info(f"Moving mouse to ({target_location[0]}, {target_location[1]}) and clicking...")

        original_position = mouse.position
        mouse.position = (target_location[0], target_location[1])
        mouse.click(Button.left, 1)
        mouse.position = original_position

        return (target_location[0], target_location[1])

    except Exception as e:
        logging.critical(f"An unexpected error occurred: {e}", exc_info=True)
        return None
