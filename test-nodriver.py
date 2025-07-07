import asyncio
import time
import nodriver as uc

async def main():
    print("[DEBUG] Starting browser...")
    browser = await uc.start(
        headless=False,  # Visible for debugging
        browser_args=['--window-size=1200,800'],
    )
    print("[DEBUG] Browser started")

    try:
        # Create a new tab
        print("[DEBUG] Creating new tab...")
        tab = await browser.get("about:blank")
        print("[DEBUG] Tab created")
        
        # Replace with your target URL
        url = "https://hide.mn/en/proxy-list/?start=192"
        print(f"[DEBUG] Navigating to URL: {url}")
        await tab.get(url)
        print("[DEBUG] URL loaded. Waiting for page to stabilize...")
        
        # Wait for page to load
        await asyncio.sleep(5)
        print("[DEBUG] Waited 5 seconds for initial load")

        # Check current page content
        print("[DEBUG] Checking page source...")
        page_source = await tab.get_content()
        print(f"[DEBUG] Page source length: {len(page_source)}")
        
        # Check if we're on a challenge page
        if "Just a moment..." in page_source:
            print("[DEBUG] Cloudflare challenge detected!")
            
            # Wait for Turnstile to load
            print("[DEBUG] Waiting for Turnstile to initialize...")
            await asyncio.sleep(3)
            
            # Try to find the Turnstile iframe
            print("[DEBUG] Looking for Turnstile iframe...")
            try:
                # First, let's check all iframes on the page
                iframes = await tab.find_all('iframe')
                print(f"[DEBUG] Found {len(iframes)} iframe(s) on page")
                
                turnstile_iframe = None
                for i, iframe in enumerate(iframes):
                    try:
                        src = iframe.attrs.get('src', '')
                        print(f"[DEBUG] Iframe {i}: src = {src[:100] if src else 'No src'}")
                        if 'challenges.cloudflare.com/turnstile' in src:
                            turnstile_iframe = iframe
                            print(f"[DEBUG] Found Turnstile iframe at index {i}")
                            break
                    except Exception as e:
                        print(f"[DEBUG] Error checking iframe {i}: {e}")
                
                if turnstile_iframe:
                    print("[DEBUG] Attempting to interact with Turnstile...")
                    
                    # Try clicking directly on the iframe area
                    try:
                        print("[DEBUG] Getting iframe position...")
                        # Get iframe bounds
                        iframe_rect = await turnstile_iframe.get_position()
                        print(f"[DEBUG] Iframe position: {iframe_rect}")
                        
                        # Click in the center of the iframe
                        click_x = iframe_rect['x'] + iframe_rect['width'] / 2
                        click_y = iframe_rect['y'] + iframe_rect['height'] / 2
                        print(f"[DEBUG] Clicking at coordinates: ({click_x}, {click_y})")
                        
                        await tab.mouse.click(click_x, click_y)
                        print("[DEBUG] Clicked on iframe area")
                        
                    except Exception as e:
                        print(f"[ERROR] Failed to click iframe: {e}")
                        
                        # Alternative approach: try to find clickable element
                        print("[DEBUG] Trying alternative approach...")
                        clickable = await tab.find('div#NMOK7')
                        if clickable:
                            print("[DEBUG] Found challenge container, clicking...")
                            await clickable.click()
                        
                else:
                    print("[WARNING] No Turnstile iframe found")
                    
                    # Check if there's a clickable challenge element
                    print("[DEBUG] Looking for alternative challenge elements...")
                    challenge_container = await tab.find('div#NMOK7')
                    if challenge_container:
                        print("[DEBUG] Found challenge container div")
                        await challenge_container.click()
                        print("[DEBUG] Clicked challenge container")
                
                # Wait for verification
                print("[DEBUG] Waiting for verification to complete...")
                start_time = time.time()
                verified = False
                
                while time.time() - start_time < 60:
                    await asyncio.sleep(2)
                    
                    # Check if we're still on challenge page
                    current_url = tab.url
                    print(f"[DEBUG] Current URL: {current_url}")
                    
                    # Check page content
                    page_content = await tab.get_content()
                    
                    # Check for success indicators
                    if "Verification successful" in page_content:
                        print("[DEBUG] Found 'Verification successful' text!")
                        verified = True
                        break
                    
                    # Check if we've been redirected away from challenge
                    if "Just a moment..." not in page_content:
                        print("[DEBUG] Challenge page no longer detected")
                        verified = True
                        break
                    
                    # Check for hidden token
                    try:
                        token_input = await tab.find('input[name="cf-turnstile-response"]')
                        if token_input:
                            token_value = await token_input.get_attribute('value')
                            if token_value:
                                print(f"[DEBUG] Token found: {token_value[:30]}...")
                                verified = True
                                break
                    except:
                        pass
                    
                    print(f"[DEBUG] Still waiting... ({int(time.time() - start_time)}s elapsed)")
                
                if verified:
                    print("[SUCCESS] Verification completed!")
                    await asyncio.sleep(5)  # Wait for redirect
                    
                    # Check final page
                    final_content = await tab.get_content()
                    print(f"[DEBUG] Final page length: {len(final_content)}")
                    
                    # Try to extract proxy data if available
                    if "proxy" in final_content.lower():
                        print("[DEBUG] Proxy content detected on page")
                        # Save screenshot
                        await tab.save_screenshot("success.png")
                        print("[DEBUG] Screenshot saved as success.png")
                else:
                    print("[ERROR] Verification timeout!")
                    await tab.save_screenshot("timeout.png")
                    
            except Exception as e:
                print(f"[ERROR] Exception during challenge handling: {e}")
                import traceback
                traceback.print_exc()
                await tab.save_screenshot("error.png")
                
        else:
            print("[DEBUG] No Cloudflare challenge detected")
            print("[DEBUG] Page loaded successfully")
            
            # Check if we have proxy content
            if "proxy" in page_source.lower():
                print("[DEBUG] Proxy list content found!")
            else:
                print("[WARNING] Expected content not found")
                
        # Keep browser open for inspection
        print("\n[DEBUG] Browser will remain open. Press Ctrl+C to exit...")
        await asyncio.sleep(300)  # Keep alive for 5 minutes
        
    except KeyboardInterrupt:
        print("\n[DEBUG] Keyboard interrupt received")
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("[DEBUG] Closing browser...")
        await browser.stop()
        print("[DEBUG] Browser closed")

if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())
