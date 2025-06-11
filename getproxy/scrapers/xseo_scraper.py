
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
    It now scrapes from multiple predefined URLs on the site.

    Args:
        verbose: If True, prints detailed status messages.

    Returns:
        A list of unique proxy strings in 'ip:port' format.
    """
    if verbose:
        print("[RUNNING] 'XSEO.in' scraper has started.")
    
    all_proxies = set()

    # --- MODIFIED: Loop over all URLs defined for this scraper ---
    for url in URLS_TO_SCRAPE:
        try:
            if verbose:
                print(f"[INFO] XSEO.in: Sending POST request to {url}")
            
            # This site expects form data, not a JSON payload.
            response = requests.post(url, headers=HEADERS, data=PAYLOAD, timeout=20)
            response.raise_for_status()
            html_content = response.text

            # 1. Extract the variable-to-digit mapping for the current page
            var_map = _parse_port_variables(html_content)
            if not var_map:
                if verbose:
                    print(f"[WARN] XSEO.in: Could not find or parse the port variables script on {url}. Skipping URL.")
                continue # Move to the next URL
            
            if verbose:
                print(f"[INFO] XSEO.in: Successfully parsed port variables for {url}.")

            # 2. Find all proxy lines and decode their ports
            proxy_matches = PROXY_LINE_REGEX.findall(html_content)
            if not proxy_matches:
                if verbose:
                    print(f"[WARN] XSEO.in: Could not find any proxy entries on {url}.")
                continue # Nothing to do on this page

            if verbose:
                print(f"[INFO] XSEO.in: Found {len(proxy_matches)} potential proxy entries on {url}.")
            
            page_proxies = set()
            for ip, port_vars_str in proxy_matches:
                port_vars = port_vars_str.split('+')
                port_digits = [var_map.get(var) for var in port_vars]

                # Check if any variable was not found in our map
                if any(digit is None for digit in port_digits):
                    if verbose:
                        print(f"[WARN] XSEO.in: Could not decode port for IP {ip} on {url}. Vars: '{port_vars_str}'")
                    continue
                
                port = "".join(port_digits)
                page_proxies.add(f"{ip}:{port}")

            if verbose:
                new_count = len(page_proxies - all_proxies)
                print(f"[INFO] XSEO.in: Decoded {len(page_proxies)} proxies from {url}, {new_count} are new.")
            
            all_proxies.update(page_proxies)

        except requests.exceptions.RequestException as e:
            if verbose:
                print(f"[ERROR] XSEO.in: Failed to fetch or process data from {url}: {e}")
            continue # Move to the next URL
        except Exception as e:
            if verbose:
                print(f"[ERROR] XSEO.in: An unexpected error occurred while scraping {url}: {e}")
            continue

    if verbose:
        print(f"[INFO] XSEO.in: Finished. Found {len(all_proxies)} unique proxies from {len(URLS_TO_SCRAPE)} URLs.")

    return sorted(list(all_proxies))