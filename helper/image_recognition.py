import logging
import os
import sys
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def find(template_image_path: str, confidence: float = 0.9, screenshot_path: str = None) -> tuple[int, int] | None:
    """
    Finds a template image on the screen or in a given screenshot file.

    Args:
        template_image_path (str): The file path to the image to find (the "needle").
        confidence (float): The confidence threshold for the match (0.0 to 1.0).
        screenshot_path (str, optional): Path to a screenshot to use for the search.
                                         If None, a new screenshot will be taken.

    Returns:
        tuple[int, int] | None: The (x, y) coordinates of the center of the found image.
    """
    try:
        import cv2
        import numpy as np
    except ImportError as e:
        logging.error(f"Missing dependency for image recognition: {e}. Please install opencv-python and numpy.")
        return None

    if not os.path.exists(template_image_path):
        logging.error(f"Template image not found at path: {template_image_path}")
        return None

    try:
        haystack_img = None
        if screenshot_path and os.path.exists(screenshot_path):
            logging.info(f"Loading screenshot from file: {screenshot_path}")
            haystack_img = cv2.imread(screenshot_path)
        else:
            # fallback to taking a screenshot if no file is provided
            try:
                import pyautogui
                logging.info("Taking screenshot...")
                screenshot_pil = pyautogui.screenshot()
                haystack_img = cv2.cvtColor(np.array(screenshot_pil), cv2.COLOR_RGB2BGR)
            except Exception as e:
                logging.critical(f"Failed to take screenshot with pyautogui: {e}", exc_info=True)
                return None

        if haystack_img is None:
            logging.error("Could not load or take a screenshot (haystack).")
            return None

        needle_img = cv2.imread(template_image_path)
        if needle_img is None:
            logging.error("Failed to load template image. Check file integrity.")
            return None
            
        needle_h, needle_w = needle_img.shape[:2]

        result = cv2.matchTemplate(haystack_img, needle_img, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        
        logging.info(f"Best match confidence: {max_val:.4f}")

        if max_val >= confidence:
            center_x = max_loc[0] + needle_w // 2
            center_y = max_loc[1] + needle_h // 2
            logging.info(f"SUCCESS: Image found at top-left: {max_loc}, center: ({center_x}, {center_y})")
            return (center_x, center_y)
        else:
            logging.warning(f"Image not found on screen with sufficient confidence (found {max_val:.4f}, need {confidence}).")
            return None

    except Exception as e:
        logging.critical(f"An unexpected error occurred during find: {e}", exc_info=True)
        return None


def find_and_click(template_image_path: str, confidence: float = None, screenshot_path: str = None) -> tuple[int, int] | None:
    """
    Finds a template image and clicks its center.

    Args:
        template_image_path (str): The file path to the image to find.
        confidence (float): The confidence threshold for the match.
        screenshot_path (str, optional): Path to a screenshot to use for the search.

    Returns:
        The (x, y) coordinates of the click if successful, otherwise None.
    """
    try:
        from pynput.mouse import Button, Controller
    except ImportError as e:
        logging.error(f"Missing dependency for mouse control: {e}. Please install pynput.")
        return None
    
    mouse = Controller()

    # pass the screenshot path to the find function
    target_location = find(template_image_path, confidence, screenshot_path)

    if not target_location:
        return None

    try:
        logging.info(f"Moving mouse to ({target_location[0]}, {target_location[1]}) and clicking...")
        original_position = mouse.position
        mouse.position = (target_location[0], target_location[1])
        mouse.click(Button.left, 1)
        mouse.position = original_position
        return (target_location[0], target_location[1])
    except Exception as e:
        logging.critical(f"An unexpected error occurred during click: {e}", exc_info=True)
        return None