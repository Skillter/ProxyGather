# Sourced and modified from: https://github.com/ricerati/proxy-checker-python/blob/master/proxy_checker/proxy_checker.py
# 
# MIT License

# Copyright (c) 2020 Ricerati

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.


import pycurl
from io import BytesIO
import re
import random
import json
import time


class ProxyChecker:
    JUDGE_RETRY_ATTEMPTS = 3
    
    # --- A lot of proxies don't pass Google because google sees abused proxies ---
    # --- Mozilla either doesn't check or is easier to pass ---
    # --- Google will yield better quality, less abused proxies, but lesser amount ---
    # LIVENESS_CHECK_URL = "http://www.google.com/"
    # LIVENESS_CHECK_STRING = "Google"
    LIVENESS_CHECK_URL = "https://addons.mozilla.org/en-US/firefox/"
    LIVENESS_CHECK_STRING = "Firefox"

    def __init__(self, timeout: float = 10.0, verbose: bool = False):
        self.timeout_ms = int(timeout * 1000)
        self.verbose = verbose 
        
        initial_judges = [
            'http://proxyjudge.us/azenv.php',
            'http://mojeip.net.pl/asdfa/azenv.php',
            'http://azenv.net/',
            'http://www.proxy-listen.de/azenv.php',
            'http://httpheader.net/azenv.php',
            'http://pascal.hoez.hu/proxy.php',
            'https://www.proxyjudge.info/azenv.php',
            'http://proxy.web-hosting.com/azenv.php'
        ]

        print("[INFO] Checking the health and content of proxy judges...")
        self.live_judges = []
        for judge in initial_judges:
            result = self._send_query_internal(url=judge)
            if isinstance(result, dict) and 'REMOTE_ADDR' in result.get('response', ''):
                self.live_judges.append(judge)
                print(f"[INFO]   ... Judge is VALID: {judge}")
            elif self.verbose:
                print(f"[WARN]   ... Judge is DEAD or returned INVALID content: {judge}")
        
        if not self.live_judges:
            print("\n[CRITICAL] No valid proxy judges found. Cannot perform checks.")
            self.ip = ""
            return
            
        print(f"[INFO] Using {len(self.live_judges)} valid proxy judges for all checks.")
        self.ip = self.get_ip()

    def get_ip(self):
        r = self._send_query_internal(url='https://api.ipify.org/')
        return r['response'] if r else ""

    def _send_query_internal(self, proxy=False, url=None, user=None, password=None):
        response = BytesIO()
        c = pycurl.Curl()

        if not url and not self.live_judges:
            return None
            
        request_url = url or random.choice(self.live_judges)
        c.setopt(c.URL, request_url)
        c.setopt(c.WRITEDATA, response)
        
        c.setopt(c.TIMEOUT_MS, self.timeout_ms if proxy else 5000)

        browser_user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36'
        c.setopt(pycurl.USERAGENT, browser_user_agent)
        
        c.setopt(c.FOLLOWLOCATION, True)
        c.setopt(pycurl.ENCODING, '')

        if user is not None and password is not None:
            c.setopt(c.PROXYUSERPWD, f"{user}:{password}")            

        c.setopt(c.SSL_VERIFYHOST, 0)
        c.setopt(c.SSL_VERIFYPEER, 0)

        if proxy:
            c.setopt(c.PROXY, proxy)

        try:
            c.perform()
        except Exception as e:
            return None

        http_code = c.getinfo(c.HTTP_CODE)

        if http_code == 200:
            timeout = round(c.getinfo(c.CONNECT_TIME) * 1000)
            return {'timeout': timeout, 'response': response.getvalue().decode('iso-8859-1'), 'judge': request_url}
        else:
            return http_code

    def get_country(self, ip):
        r = self._send_query_internal(url='https://ip2c.org/' + ip)
        if isinstance(r, dict) and r['response'] and r['response'][0] == '1':
            parts = r['response'].split(';')
            return [parts[3], parts[1]]
        return ['-', '-']

    def _parse_anonymity(self, r):
        if self.ip in r:
            return 'Transparent'
        privacy_headers = ['VIA', 'X-FORWARDED-FOR', 'X-FORWARDED', 'FORWARDED-FOR', 'FORWARDED-FOR-IP', 'FORWARDED', 'CLIENT-IP', 'PROXY-CONNECTION']
        if any([header in r for header in privacy_headers]):
            return 'Anonymous'
        return 'Elite'

    def check_proxy(self, proxy, check_country=True, check_address=False, user=None, password=None):
        is_live = False
        for protocol in ['http', 'socks4', 'socks5']:
            result = self._send_query_internal(proxy=f"{protocol}://{proxy}", url=self.LIVENESS_CHECK_URL)
            
            if isinstance(result, dict):
                if self.LIVENESS_CHECK_STRING in result.get('response', ''):
                    is_live = True
                    break
                elif self.verbose:
                    print(f"\n[HIJACK?] Proxy {proxy} connected to Google but returned unexpected content.")
                return False
            
            elif result is None:
                continue

            elif isinstance(result, int):
                if self.verbose:
                    if result == 407:
                        print(f"\n[AUTH FAILED] Proxy {proxy} requires a password (on Google check).")
                    else:
                        print(f"\n[GOOGLE FAILED] Proxy {proxy} failed liveness check, returned HTTP {result}.")
                return False

        if not is_live:
            return False

        protocols = {}
        timeout = 0
        for protocol in ['http', 'socks4', 'socks5']:
            for attempt in range(self.JUDGE_RETRY_ATTEMPTS):
                result = self._send_query_internal(proxy=f"{protocol}://{proxy}", user=user, password=password)
                
                if isinstance(result, dict):
                    protocols[protocol] = result
                    timeout += result['timeout']
                    break 

                if result is None:
                    break

                if isinstance(result, int):
                    if attempt == self.JUDGE_RETRY_ATTEMPTS - 1 and self.verbose:
                        if result == 407:
                            print(f"\n[AUTH FAILED] Proxy {proxy} requires a password.")
                        elif result == 404:
                            print(f"\n[HIJACK?] Proxy {proxy} returned HTTP 404 from judge, may be a hijacking proxy.")
                        else:
                            print(f"\n[JUDGE FAILED] Proxy {proxy} failed all retries, last error from judge was HTTP {result}.")
                    else:
                        time.sleep(0.1)
        
        if not protocols:
            return False

        r = protocols[random.choice(list(protocols.keys()))]['response']
        
        if check_country:
            country = self.get_country(proxy.split(':')[0])

        anonymity = self._parse_anonymity(r)
        avg_timeout = timeout // len(protocols)

        final_result = {
            'protocols': list(protocols.keys()),
            'anonymity': anonymity,
            'timeout': avg_timeout
        }

        if check_country:
            final_result['country'] = country[0]
            final_result['country_code'] = country[1]

        if check_address:
            remote_regex = r'REMOTE_ADDR = (\d{1,3}\.\d{1,3}\.\d{1,3}\d{1,3})'
            remote_addr = re.search(remote_regex, r)
            if remote_addr:
                final_result['remote_address'] = remote_addr.group(1)

        return final_result