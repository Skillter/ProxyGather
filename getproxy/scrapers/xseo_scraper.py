import requests
import re
from typing import List, Dict

# URL and payload for the target site
URL = "https://xseo.in/proxylist"
PAYLOAD = {"submit": "Показать по 150 прокси на странице"}

# Standard headers to mimic a browser
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3',
    'Referer': 'https://xseo.in/proxylist'
}

# Regex to find the script defining port variables.
# Example: <script type="text/javascript">h=0;i=1;d=2;c=3;u=4;f=5;s=6;t=7;r=8;k=9;</script>
VAR_SCRIPT_REGEX = re.compile(r'<script type="text/javascript">([a-z=\d;]+)</script>')

# Regex to find individual variable assignments inside the script.
VAR_ASSIGN_REGEX = re.compile(r'([a-z])=(\d)')

# Regex to find the IP and the port-building script.
# This looks for an IP, then non-greedily matches any characters until it finds the document.write call.
# This is more robust against changes in HTML tags between the IP and the script.
PROXY_LINE_REGEX = re.compile(
    r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # Capture IP address
    r'.*?'                                  # Match intervening HTML tags non-greedily
    r'document\.write\(""\+(.*?)\)</script>' # Capture the variable string like 'f+h+h+i+d'
)

def _parse_port_variables(html: str) -> Dict[str, str]:
    """Finds and parses the JavaScript variables used for port obfuscation."""
    var_map = {}
    match = VAR_SCRIPT_REGEX.search(html)
    if match:
        script_content = match.group(1)
        assignments = VAR_ASSIGN_REGEX.findall(script_content)
        var_map = dict(assignments)
    return var_map

def scrape_from_xseo(verbose: bool = True) -> List[str]:
    """
    Scrapes proxies from xseo.in, decoding the JavaScript-obfuscated port numbers.

    Args:
        verbose: If True, prints detailed status messages.

    Returns:
        A list of unique proxy strings in 'ip:port' format.
    """
    if verbose:
        print("[RUNNING] 'XSEO.in' scraper has started.")
    
    all_proxies = set()

    try:
        if verbose:
            print(f"[INFO] XSEO.in: Sending POST request to {URL}")
        
        # This site expects form data, not a JSON payload.
        response = requests.post(URL, headers=HEADERS, data=PAYLOAD, timeout=20)
        response.raise_for_status()
        html_content = response.text

        # 1. Extract the variable-to-digit mapping
        var_map = _parse_port_variables(html_content)
        if not var_map:
            raise Exception("Could not find or parse the port variable definitions script.")
        
        if verbose:
            print(f"[INFO] XSEO.in: Successfully parsed port variables: {var_map}")

        # 2. Find all proxy lines and decode their ports
        proxy_matches = PROXY_LINE_REGEX.findall(html_content)
        if not proxy_matches:
            if verbose:
                print("[WARN] XSEO.in: Could not find any proxy entries matching the expected pattern.")
            return []

        if verbose:
            print(f"[INFO] XSEO.in: Found {len(proxy_matches)} potential proxy entries.")

        for ip, port_vars_str in proxy_matches:
            port_vars = port_vars_str.split('+')
            port_digits = [var_map.get(var) for var in port_vars]

            # Check if any variable was not found in our map
            if any(digit is None for digit in port_digits):
                if verbose:
                    print(f"[WARN] XSEO.in: Could not decode port for IP {ip}. Vars: '{port_vars_str}'")
                continue
            
            port = "".join(port_digits)
            all_proxies.add(f"{ip}:{port}")

    except requests.exceptions.RequestException as e:
        raise Exception(f"Failed to fetch data from XSEO.in: {e}") from e
    except Exception as e:
        raise Exception(f"An error occurred during XSEO.in scraping: {e}") from e

    if verbose:
        print(f"[INFO] XSEO.in: Finished. Found {len(all_proxies)} unique proxies.")

    return sorted(list(all_proxies))