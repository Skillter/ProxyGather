import time
from DrissionPage import ChromiumPage, ChromiumOptions
from DrissionPage._functions.elements import ChromiumElementsList
from typing import cast, List, Any
import sys

def main():
    co = ChromiumOptions()
    # co.set_argument("--headless", "new")
    # co.set_argument('--no-sandbox')
        
    page = ChromiumPage(co)

    page.get("https://nowsecure.nl")
    # captcha_text_list = page.eles("span:text:Verify you are human", timeout=6)
    # print(captcha_text_list)
    # captcha_text_ele = page.ele("span:text:Verify you are human", timeout=6)
    # print(captcha_text_ele)
    # for i, captcha_text in enumerate(captcha_text_list):
    #     print(captcha_text_list.__getitem__(i))
    #     print(captcha_text_list.__getitem__(i).parent("label", timeout=2))
    #     print(captcha_text_list.__getitem__(i).parent("label", timeout=2).ele("input", timeout=2))
    #     captcha_text_list.__getitem__(i).parent("label", timeout=2).ele("input", timeout=2).click()

    captcha_text = page.ele("text:Verify you are human", timeout=6)
    print(captcha_text.inner_html)
    print(captcha_text.xpath)
    print(captcha_text.css_path)
    print(captcha_text.attrs)
    print(captcha_text.get_screenshot("test.png"))
    # print(captcha_text.raw_text)


    page.get_screenshot('Test-DrissionPage.png')
    # page.quit()

if __name__ == '__main__':
    main()