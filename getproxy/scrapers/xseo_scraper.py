import requests
import re
from typing import List, Dict

# --- MODIFIED: Changed from a single URL to a list of URLs to scrape ---
URLS_TO_SCRAPE = [
    "https://xseo.in/proxylist",
    "https://xseo.in/freeproxy",
]
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

# --- ADDED: Regex for standard, non-obfuscated proxies ---
# This acts as a fallback in case the site changes its format.
PLAIN_TEXT_PROXY_REGEX = re.compile(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d{2,5})')

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
    Scrapes proxies from xseo.in.
    
    This scraper now works in two stages for maximum resilience:
    1. It attempts to decode the JavaScript-obfuscated port numbers.
    2. It also scans for standard, plain-text 'IP:Port' proxies as a fallback.

    Args:
        verbose: If True, prints detailed status messages.

    Returns:
        A list of unique proxy strings in 'ip:port' format.
    """
    if verbose:
        print("[RUNNING] 'XSEO.in' scraper has started.")
    
    all_proxies = set()

    for url in URLS_TO_SCRAPE:
        try:
            if verbose:
                print(f"[INFO] XSEO.in: Sending POST request to {url}")
            
            response = requests.post(url, headers=HEADERS, data=PAYLOAD, timeout=20)
            response.raise_for_status()
            html_content = response.text
            
            # --- MODIFIED: Implement a two-pass scraping strategy ---
            proxies_from_url = set()
            
            # --- Pass 1: Handle JavaScript Obfuscation (the primary method) ---
            var_map = _parse_port_variables(html_content)
            if var_map:
                if verbose:
                    print(f"[INFO] XSEO.in: Successfully parsed port variables on {url}.")
                
                obfuscated_matches = PROXY_LINE_REGEX.findall(html_content)
                decoded_count = 0
                for ip, port_vars_str in obfuscated_matches:
                    port_vars = port_vars_str.split('+')
                    port_digits = [var_map.get(var) for var in port_vars]

                    if any(digit is None for digit in port_digits):
                        if verbose:
                            print(f"[WARN] XSEO.in: Could not decode port for IP {ip} on {url}. Vars: '{port_vars_str}'")
                        continue
                    
                    port = "".join(port_digits)
                    proxies_from_url.add(f"{ip}:{port}")
                    decoded_count += 1
                
                if verbose and decoded_count > 0:
                    print(f"[INFO] XSEO.in: Decoded {decoded_count} obfuscated proxies from {url}.")
            else:
                if verbose:
                    print(f"[INFO] XSEO.in: No JavaScript port obfuscation found on {url}. Checking for plain text.")

            # --- Pass 2: Handle Plain Text Proxies (the fallback method) ---
            plain_text_matches = PLAIN_TEXT_PROXY_REGEX.findall(html_content)
            plain_text_found = set()
            for ip, port in plain_text_matches:
                plain_text_found.add(f"{ip}:{port}")
            
            if verbose and plain_text_found:
                # To avoid confusion, only report newly found plain-text proxies
                new_plain_text = len(plain_text_found - proxies_from_url)
                if new_plain_text > 0:
                    print(f"[INFO] XSEO.in: Found {new_plain_text} additional plain text proxies on {url}.")
            
            # Combine results from both passes for this URL
            proxies_from_url.update(plain_text_found)

            if verbose:
                if not proxies_from_url:
                    print(f"[WARN] XSEO.in: Could not find any proxies on {url} using either method.")
                else:
                    new_count = len(proxies_from_url - all_proxies)
                    print(f"[INFO] XSEO.in: Found {len(proxies_from_url)} total proxies on {url}, {new_count} are new.")
            
            all_proxies.update(proxies_from_url)

        except requests.exceptions.RequestException as e:
            if verbose:
                print(f"[ERROR] XSEO.in: Failed to fetch or process data from {url}: {e}")
            continue
        except Exception as e:
            if verbose:
                print(f"[ERROR] XSEO.in: An unexpected error occurred while scraping {url}: {e}")
            continue

    if verbose:
        print(f"[INFO] XSEO.in: Finished. Found {len(all_proxies)} unique proxies from {len(URLS_TO_SCRAPE)} URLs.")

    return sorted(list(all_proxies))