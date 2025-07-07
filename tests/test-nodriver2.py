import asyncio
import nodriver as uc
import logging
import os




async def sophisticated_cloudflare_bypass():

    browser = None
    # target_url = "https://hide.mn/en/proxy-list/?start=192"
    target_url = "https://dashboard.proxyscrape.com/v2/sign-up"
    
    try:
        # print("test")
        browser = await uc.start(
            # browser_args=[],
            headless=False
        )

        page = await browser.get(target_url)
        await asyncio.sleep(6)  # Wait for the page to potentially load/present a challenge
        
        retry = 0
        while(retry <= 5):
            retry=+1
            await page.verify_cf("cf.png", True)
            print("done")
            await asyncio.sleep(10) 
        await asyncio.sleep(100) 


    except Exception as e:
        print(f"--- An Unhandled Error Occurred ---", exc_info=True)
    finally:
        if browser:
            await browser.stop()


if __name__ == "__main__":
    try:
        asyncio.run(sophisticated_cloudflare_bypass())
    except KeyboardInterrupt:
        print("Script execution cancelled by user.")