import re
import requests

# Define the possible patterns for scraping proxies
patterns = [
    r'<td>(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})<\/td>\s*<td>(\d+)<\/td>',
    r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d+)',
    r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})&nbsp;&nbsp;(\d+)',
    r'<td>\s*(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s*</td>\s*<td>\s*(\d+)\s*</td>',
    r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}).*?(\d{2,5})',
    r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})[^0-9]*(\d+)',
    r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s*:\s*(\d+)',
    r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})[\s-]+(\d{2,5})',
    r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})<.*?>(\d+)<',
    r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}).*?port\s*:\s*(\d+)',
    r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s*:\s*(\d+)',
    r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})[\s-]+(\d{2,5})',
    r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})<.*?>(\d+)<',
    r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}).*?port\s*:\s*(\d+)',
]

url = input('Enter the URL of the proxy site: ')

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
}

response = requests.get(url, headers=headers)

proxies = []
for pattern in patterns:
    matches = re.findall(pattern, response.text)
    if matches:
        print(f'Using pattern: {pattern}')
        for match in matches:
            ip, port = match
            proxy = f'{ip}:{port}'
            proxies.append(proxy)
        break

if not proxies:
    print('Error: Could not find any proxies.')
else:
    print(f'Found {len(proxies)} proxies:')
    for proxy in proxies:
        print(proxy)
