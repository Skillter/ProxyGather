import time
from seleniumbase import Driver

def is_bypassed(driver):
    """Check if we've successfully bypassed the challenge"""
    try:
        title = driver.get_title().lower()
        body = driver.get_text("body").lower()
        
        # Check for common Cloudflare challenge indicators
        verification_texts = [
            "just a moment",
            "verify you are human",
            "checking your browser",
            "attention required",
            "ray id"
        ]
        
        for text in verification_texts:
            if text in title or text in body:
                return False
        return True
    except:
        return False

def main():
    # Initialize the driver with undetected Chrome mode
    driver = Driver(uc=True, headless=False)
    
    try:
        # Navigate to the target page
        print("Opening page...")
        driver.uc_open_with_reconnect("https://nopecha.com/demo/cloudflare", 3)
        
        # Wait a bit for the page to load
        time.sleep(3)
        
        # Attempt to bypass the captcha
        max_attempts = 3
        for attempt in range(max_attempts):
            if is_bypassed(driver):
                print("Already bypassed or no captcha present!")
                break
                
            print(f"Attempting to click captcha (attempt {attempt + 1}/{max_attempts})...")
            
            try:
                # Click the captcha using SeleniumBase's built-in method
                driver.uc_gui_click_captcha()
                
                # Wait for the result
                time.sleep(5)
                
                if is_bypassed(driver):
                    print("Successfully bypassed!")
                    break
                else:
                    print("Bypass not successful yet...")
                    
            except Exception as e:
                print(f"Error clicking captcha: {e}")
                time.sleep(2)
        
        # Keep the browser open for 10 seconds to see the result
        print("Keeping browser open for 10 seconds...")
        time.sleep(10)
        
    finally:
        # Clean up
        driver.quit()

if __name__ == "__main__":
    main()
