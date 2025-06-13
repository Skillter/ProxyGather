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


class ProxyChecker:
    def __init__(self):
        self.ip = self.get_ip()
        self.proxy_judges = [
            'http://proxyjudge.us/azenv.php',
            'http://mojeip.net.pl/asdfa/azenv.php'
        ]

    def get_ip(self):
        r = self.send_query(url='https://api.ipify.org/')

        if not r:
            return ""

        return r['response']

    def send_query(self, proxy=False, url=None, user=None, password=None):
        response = BytesIO()
        c = pycurl.Curl()

        c.setopt(c.URL, url or random.choice(self.proxy_judges))
        c.setopt(c.WRITEDATA, response)
        c.setopt(c.TIMEOUT, 5)

        if user is not None and password is not None:
            c.setopt(c.PROXYUSERPWD, f"{user}:{password}")            

        c.setopt(c.SSL_VERIFYHOST, 0)
        c.setopt(c.SSL_VERIFYPEER, 0)

        if proxy:
            c.setopt(c.PROXY, proxy)

        # Perform request
        try:
            c.perform()
        except Exception as e:
            # print(e)
            return False

        # Return False if the status is not 200
        if c.getinfo(c.HTTP_CODE) != 200:
            return False

        # Calculate the request timeout in milliseconds
        timeout = round(c.getinfo(c.CONNECT_TIME) * 1000)

        # Decode the response content
        response = response.getvalue().decode('iso-8859-1')

        return {
            'timeout': timeout,
            'response': response
        }

    def parse_anonymity(self, r):
        if self.ip in r:
            return 'Transparent'

        privacy_headers = [
            'VIA',
            'X-FORWARDED-FOR',
            'X-FORWARDED',
            'FORWARDED-FOR',
            'FORWARDED-FOR-IP',
            'FORWARDED',
            'CLIENT-IP',
            'PROXY-CONNECTION'
        ]

        if any([header in r for header in privacy_headers]):
            return 'Anonymous'

        return 'Elite'

    def get_country(self, ip):
        r = self.send_query(url='https://ip2c.org/' + ip)

        if r and r['response'][0] == '1':
            r = r['response'].split(';')
            return [r[3], r[1]]

        return ['-', '-']

    def check_proxy(self, proxy, check_country=True, check_address=False, user=None, password=None):
        protocols = {}
        timeout = 0

        # Test the proxy for each protocol
        for protocol in ['http', 'socks4', 'socks5']:
            r = self.send_query(proxy=protocol + '://' + proxy, user=user, password=password)

            # Check if the request failed
            if not r:
                continue

            protocols[protocol] = r
            timeout += r['timeout']

        # Check if the proxy failed all tests
        if (len(protocols) == 0):
            return False

        r = protocols[random.choice(list(protocols.keys()))]['response']

        # Get country
        if check_country:
            country = self.get_country(proxy.split(':')[0])

        # Check anonymity
        anonymity = self.parse_anonymity(r)

        # Check timeout
        timeout = timeout // len(protocols)

        # Check remote address
        if check_address:
            remote_regex = r'REMOTE_ADDR = (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
            remote_addr = re.search(remote_regex, r)
            if remote_addr:
                remote_addr = remote_addr.group(1)

        results = {
            'protocols': list(protocols.keys()),
            'anonymity': anonymity,
            'timeout': timeout
        }

        if check_country:
            results['country'] = country[0]
            results['country_code'] = country[1]

        if check_address:
            results['remote_address'] = remote_addr

        return results