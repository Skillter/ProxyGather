import requests
import re
import json
import time
from typing import List, Dict, Union, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, urljoin
from urllib.robotparser import RobotFileParser
from collections import defaultdict
import threading
from helper.request_utils import get_with_retry, post_with_retry

# Changed from a set to a list to enforce a prioritized order.
# Patterns are ordered from most specific/reliable to most generic/broad.
PATTERNS = [
    # --- High Priority: Very specific and low risk of false positives ---

    # A very selective regex for ProxyDB
    r'<td>\s*<a[^>]*>(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})</a>\s*</td>\s*<td>[\s\S]*?<a[^>]*>(\d{2,5})</a>',

    # 1. Matches `IP:PORT` inside quotes, common in JS/JSON.
    r'["\'](\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d{2,5})["\']',
    
    # 2. MODIFIED: Robustly matches IP and Port in table rows, even with non-adjacent columns and newlines.
    #    This now uses [\s\S]*? to match across newlines and correctly parse formatted HTML tables.
    r'<tr[^>]*>[\s\S]*?<td>\s*(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s*</td>[\s\S]*?<td>\s*(\d+)\s*</td>',
    
    # 3. Matches IP and Port in adjacent table cells, allowing for whitespace.
    r'<td>\s*(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s*</td>\s*<td>\s*(\d+)\s*</td>',
    # 4. A simpler version for adjacent table cells.
    r'<td>(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})<\/td>\s*<td>(\d+)<\/td>',
    # 5. Matches IP and Port separated by non-breaking spaces.
    r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})  (\d+)',

    # --- Medium Priority: Common formats, slightly higher risk ---
    # 6. Standard `IP:PORT` format, allowing for whitespace around the colon.
    r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s*:\s*(\d+)',
    # 7. The most common `IP:PORT` format without extra whitespace.
    r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d+)',
    # 8. IP and Port in adjacent HTML tags, a moderately reliable pattern.
    r'>\s*(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s*<[^>]+>(\d{2,5})<',
    
    # 9. MODIFIED: Looks for an IP near the word "port", now matching across newlines.
    r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})[\s\S]{0,50}?port\s*:\s*(\d+)',
    
    # --- Low Priority: Broad patterns, higher risk of false positives ---
    # 10. IP followed by whitespace or a hyphen, then the port.
    r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})[\s-]+(\d{2,5})',
    # 11. IP and Port separated by some unknown HTML tag.
    r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})<.*?>(\d+)<',
    # 12. MODIFIED: A smarter generic pattern. Looks for an IP, then a common separator (whitespace or < >), then a port.
    #     This avoids matching numbers inside HTML attributes like class="pp14".
    r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})[\s<>]+(\d{2,5})',
]

DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3',
}

PROXY_VALIDATION_REGEX = re.compile(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{1,5}$')

PAGINATED_RATELIMIT_DELAY = 0.8 # In seconds, before it was 1.5
DOMAIN_RATELIMIT_DELAY = 0.5 # Delay between requests to the same domain

# Thread-safe domain rate limiting
class DomainRateLimiter:
    def __init__(self, delay: float):
        self.delay = delay
        self.last_request_time = defaultdict(float)
        self.locks = defaultdict(threading.Lock)

    def wait_if_needed(self, domain: str):
        """Wait if necessary before making a request to this domain."""
        with self.locks[domain]:
            elapsed = time.time() - self.last_request_time[domain]
            if elapsed < self.delay:
                time.sleep(self.delay - elapsed)
            self.last_request_time[domain] = time.time()

class RobotsTxtChecker:
    """Thread-safe robots.txt checker with caching."""
    def __init__(self):
        self.cache = {}
        self.lock = threading.Lock()

    def is_allowed(self, url: str, user_agent: str = '*') -> bool:
        """Check if the URL is allowed by robots.txt."""
        parsed = urlparse(url)
        domain = f"{parsed.scheme}://{parsed.netloc}"

        with self.lock:
            if domain not in self.cache:
                rp = RobotFileParser()
                robots_url = urljoin(domain, '/robots.txt')
                try:
                    rp.set_url(robots_url)
                    rp.read()
                    self.cache[domain] = rp
                except Exception:
                    self.cache[domain] = None

        rp = self.cache[domain]
        if rp is None:
            return True

        return rp.can_fetch(user_agent, url)

def _recursive_json_search_and_extract(data: any, proxies_found: set):
    if isinstance(data, dict):
        for key in ['address', 'proxy', 'addr', 'ip_port']:
            proxy_str = data.get(key)
            if isinstance(proxy_str, str) and PROXY_VALIDATION_REGEX.match(proxy_str):
                proxies_found.add(proxy_str)
                return
        ip, port = None, None
        for ip_key in ['ip', 'ipAddress', 'host', 'ip_address']:
            if data.get(ip_key): ip = str(data[ip_key])
        for port_key in ['port']:
            if data.get(port_key): port = str(data[port_key])
        if ip and port:
            proxy_str = f"{ip}:{port}"
            if PROXY_VALIDATION_REGEX.match(proxy_str):
                proxies_found.add(proxy_str)
                return
        for value in data.values():
            _recursive_json_search_and_extract(value, proxies_found)
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, str) and PROXY_VALIDATION_REGEX.match(item):
                proxies_found.add(item)
            elif isinstance(item, (dict, list)):
                _recursive_json_search_and_extract(item, proxies_found)

def extract_proxies_from_content(content: str, verbose: bool = False) -> set:
    proxies_found = set()
    try:
        json_data = json.loads(content)
        _recursive_json_search_and_extract(json_data, proxies_found)
        if proxies_found and verbose: print("[DEBUG]  ... Found proxies via smart JSON parsing.")
    except (json.JSONDecodeError, TypeError): pass
    if not proxies_found:
        data_config_pattern = r'data-config="(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{1,5})"'
        matches = re.findall(data_config_pattern, content)
        if matches:
            proxies_found.update(matches)
            if verbose: print("[DEBUG]  ... Found proxies via 'data-config' attribute parsing.")
    if not proxies_found:
        for pattern in PATTERNS:
            try:
                matches = re.findall(pattern, content)
                for match in matches:
                    if isinstance(match, tuple) and len(match) >= 2:
                        proxies_found.add(f'{match[0]}:{match[1]}')
                    elif isinstance(match, str) and ":" in match:
                        proxies_found.add(match)
            except re.error: continue
        if verbose and proxies_found: print("[DEBUG]  ... Found proxies via general regex fallback.")
    return proxies_found

def _fetch_and_extract_single(url: str, payload: Union[Dict, None], headers: Union[Dict, None], verbose: bool, rate_limiter: DomainRateLimiter = None, robots_checker: RobotsTxtChecker = None) -> Tuple[set, bool]:
    merged_headers = DEFAULT_HEADERS.copy()
    if headers:
        merged_headers.update(headers)

    if robots_checker and not robots_checker.is_allowed(url, merged_headers.get('User-Agent', '*')):
        if verbose:
            print(f"[INFO] Skipping {url} - blocked by robots.txt")
        return set(), False

    if rate_limiter:
        domain = urlparse(url).netloc
        rate_limiter.wait_if_needed(domain)

    try:
        if payload:
            response = post_with_retry(url, data=payload, headers=merged_headers, timeout=15, verbose=verbose)
        else:
            response = get_with_retry(url, headers=merged_headers, timeout=15, verbose=verbose)
        return extract_proxies_from_content(response.text, verbose=verbose), True
    except requests.exceptions.HTTPError as e:
        if e.response and e.response.status_code in [403, 429, 503]:
            if verbose:
                print(f"[RETRY] HTTP {e.response.status_code} for {url} (will retry)")
            return set(), False
        if verbose:
            print(f"[ERROR] HTTP {e.response.status_code if e.response else 'error'} for {url}")
        return set(), True
    except requests.exceptions.RequestException as e:
        if verbose:
            print(f"[RETRY] Request failed for {url}: {e} (will retry)")
        return set(), False

def _scrape_paginated_url(base_url: str, base_payload: Union[Dict, None], base_headers: Union[Dict, None], verbose: bool, rate_limiter: DomainRateLimiter, robots_checker: RobotsTxtChecker = None) -> Tuple[set, bool]:
    """Scrapes a single paginated URL and returns (proxies, found_any)."""
    proxies = set()
    page_num = 1
    found_any = False

    if verbose: print(f"[INFO] General Scraper: Starting pagination for {base_url}")

    while True:
        current_url = base_url.replace("{page}", str(page_num))
        current_payload = None
        if base_payload:
            payload_str = json.dumps(base_payload)
            payload_str = payload_str.replace("{page}", str(page_num))
            current_payload = json.loads(payload_str)

        if verbose: print(f"[INFO]   ... Scraping page {page_num} ({current_url})")

        newly_scraped, success = _fetch_and_extract_single(current_url, current_payload, base_headers, verbose, rate_limiter, robots_checker)

        if newly_scraped:
            found_any = True
            initial_count = len(proxies)
            proxies.update(newly_scraped)

            if len(proxies) == initial_count:
                if verbose: print("[INFO]   ... No new unique proxies found. Ending pagination.")
                break
        else:
            if verbose: print(f"[INFO]   ... No proxies found on page {page_num}. Ending pagination.")
            break

        page_num += 1
        time.sleep(PAGINATED_RATELIMIT_DELAY)

    return proxies, found_any

def scrape_proxies(
    scrape_targets: List[Tuple[str, Union[Dict, None], Union[Dict, None]]],
    verbose: bool = False,
    max_workers: int = 10,
    respect_robots_txt: bool = False
) -> Tuple[List[str], List[str]]:
    """
    Scrapes proxies concurrently with domain-based rate limiting.
    Returns both the proxies and a list of successful source URLs.
    """
    all_proxies = set()
    successful_urls = set()
    single_req_targets = []
    paginated_targets = []

    rate_limiter = DomainRateLimiter(DOMAIN_RATELIMIT_DELAY)
    robots_checker = RobotsTxtChecker() if respect_robots_txt else None

    for url, payload, headers in scrape_targets:
        is_paginated = "{page}" in url or ("{page}" in json.dumps(payload) if payload else False)
        if is_paginated:
            paginated_targets.append((url, payload, headers))
        else:
            single_req_targets.append((url, payload, headers))

    if single_req_targets:
        print(f"[INFO] General Scraper: Found {len(single_req_targets)} single-request URLs")

        retry_attempts = {(url, json.dumps(payload) if payload else None, json.dumps(headers) if headers else None): 0
                          for url, payload, headers in single_req_targets}
        max_retries = 3

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_target = {
                executor.submit(_fetch_and_extract_single, url, payload, headers, verbose, rate_limiter, robots_checker): (url, payload, headers)
                for url, payload, headers in single_req_targets
            }

            while future_to_target:
                for future in as_completed(list(future_to_target.keys())):
                    url, payload, headers = future_to_target.pop(future)
                    key = (url, json.dumps(payload) if payload else None, json.dumps(headers) if headers else None)

                    try:
                        proxies_from_url, success = future.result()

                        if success:
                            if proxies_from_url:
                                if verbose: print(f"[INFO] General Scraper: Found {len(proxies_from_url)} proxies on {url}")
                                all_proxies.update(proxies_from_url)
                                successful_urls.add(url)
                        else:
                            retry_attempts[key] += 1
                            if retry_attempts[key] < max_retries:
                                if verbose:
                                    print(f"[INFO] Retrying {url} (attempt {retry_attempts[key] + 1}/{max_retries})")
                                time.sleep(2)
                                new_future = executor.submit(_fetch_and_extract_single, url, payload, headers, verbose, rate_limiter, robots_checker)
                                future_to_target[new_future] = (url, payload, headers)
                            else:
                                if verbose:
                                    print(f"[ERROR] Max retries reached for {url}")
                    except Exception as exc:
                        if verbose: print(f"[ERROR] An exception occurred while processing {url}: {exc}")

    if paginated_targets:
        print(f"[INFO] General Scraper: Found {len(paginated_targets)} paginated URLs. Scraping concurrently with domain rate limiting...")
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_url = {
                executor.submit(_scrape_paginated_url, base_url, base_payload, base_headers, verbose, rate_limiter, robots_checker): base_url
                for base_url, base_payload, base_headers in paginated_targets
            }
            for future in as_completed(future_to_url):
                base_url = future_to_url[future]
                try:
                    proxies_from_url, found_any = future.result()
                    if found_any:
                        if verbose: print(f"[INFO] General Scraper: Found {len(proxies_from_url)} total proxies from {base_url}")
                        all_proxies.update(proxies_from_url)
                        successful_urls.add(base_url)
                except Exception as exc:
                    if verbose: print(f"[ERROR] An exception occurred while processing {base_url}: {exc}")

    return sorted(list(all_proxies)), sorted(list(successful_urls))