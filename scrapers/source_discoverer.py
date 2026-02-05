import re
import json
from typing import List, Set, Any
from urllib.parse import urljoin, urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from helper.request_utils import get_with_retry

# Matches href attributes to extract potential links from HTML
HREF_REGEX = re.compile(r'href=["\']([^"\']+)["\']', re.IGNORECASE)
# Matches [number] prefix like [25] or [15]
PAGE_COUNT_PREFIX = re.compile(r'^\[\d+\](.+)$')
# Fallback regex to extract http/https URLs from any text
URL_REGEX = re.compile(r'https?://[^\s<>"\'\)\]\}]+')
# Pattern to match raw.githubusercontent.com URLs for jsdelivr conversion
RAW_GITHUB_REGEX = re.compile(r'https?://raw\.githubusercontent\.com/([^/]+)/([^/]+)/(.+)$')

# Domains that are known to be dead, require specific automation, or are just noise (search engines)
IGNORED_DOMAINS = {
    'internet.limited',       # Dead / DNS failures
    'www.proxy-list.download', # Consistent timeouts
    'hidemy.name',            # Requires browser automation/Cloudflare bypass (not supported in general scraper)
    'free-proxy-list.com',    # SSL Errors
    'openproxy.space',        # Often fails/blocks bots
    'google.com', 'bing.com', 'yahoo.com', 'yandex.ru', 'baidu.com',
    'instagram.com', 'tiktok.com', 'youtube.com', 'facebook.com', 'twitter.com', 'linkedin.com',
    't.me', 'discord.gg',     # Chat apps require specific parsing
    'vpnoverview.com',        # Blog articles, not raw lists
    'smallseotools.com',    
    'netzwelt.de',
    'whoer.io',               # Connection timeouts
    'proxylistplus.com', 'list.proxylistplus.com' # All of their proxies are dead
}

def is_url_allowed(url: str) -> bool:
    """Checks if the URL's domain is in the ignored list."""
    try:
        parsed = urlparse(url)
        netloc = parsed.netloc.lower()
        
        # Remove port if present
        if ':' in netloc:
            netloc = netloc.split(':')[0]
            
        # Remove 'www.' prefix
        if netloc.startswith('www.'):
            netloc = netloc[4:]
        
        if netloc in IGNORED_DOMAINS:
            return False
            
        return True
    except Exception:
        return False

def convert_to_jsdelivr_url(url: str) -> str:
    """
    Converts raw.githubusercontent.com URLs to fastly.jsdelivr.net equivalents.
    Example: https://raw.githubusercontent.com/user/repo/refs/heads/main/path
    becomes: https://fastly.jsdelivr.net/gh/user/repo@main/path
    """
    match = RAW_GITHUB_REGEX.match(url)
    if match:
        user = match.group(1)
        repo = match.group(2)
        rest = match.group(3)

        # Remove 'refs/heads/' or 'refs/tags/' if present
        if rest.startswith('refs/heads/'):
            branch = rest[len('refs/heads/'):].split('/')[0]
            path = rest[len('refs/heads/' + branch):].lstrip('/')
        elif rest.startswith('refs/tags/'):
            branch = rest[len('refs/tags/'):].split('/')[0]
            path = rest[len('refs/tags/' + branch):].lstrip('/')
        else:
            # First segment is the branch
            parts = rest.split('/', 1)
            branch = parts[0]
            path = parts[1] if len(parts) > 1 else ''

        return f'https://fastly.jsdelivr.net/gh/{user}/{repo}@{branch}/{path}'.rstrip('/')

    return url

def _extract_url_from_line(line: str) -> str:
    """
    Extracts a clean URL from a line, handling:
    - Lines with [js] prefix (returns None)
    - Lines with [count] prefix like [25]https://...
    - Plain URLs
    """
    line = line.strip()

    # Skip lines that require JavaScript
    if '[js]' in line:
        return None

    # Extract URL from lines with page count prefix like [25]https://...
    match = PAGE_COUNT_PREFIX.match(line)
    if match:
        return match.group(1).strip()

    # If line starts with http/https, return it as-is
    if line.startswith(('http://', 'https://')):
        return line

    return None

def _extract_urls_from_json(data: Any) -> Set[str]:
    """
    Recursively extracts all http/https URLs from JSON data.
    Handles nested objects and arrays.
    """
    urls = set()
    if isinstance(data, dict):
        for value in data.values():
            urls.update(_extract_urls_from_json(value))
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, str) and item.startswith(('http://', 'https://')):
                urls.add(item)
            elif isinstance(item, (dict, list)):
                urls.update(_extract_urls_from_json(item))
    return urls

def _fetch_and_extract_links(url: str, verbose: bool) -> Set[str]:
    """
    Fetches a single URL and extracts all valid http/https links from it.
    Handles JSON responses, HTML pages, and plain text URL lists.
    """
    links = set()
    try:
        if verbose:
            print(f"[INFO] Discovery: Fetching source {url}...", flush=True)

        # Use a shorter timeout for discovery to avoid hanging
        response = get_with_retry(url, timeout=15, verbose=verbose)

        # Try parsing as JSON first
        try:
            json_data = json.loads(response.text)
            if verbose:
                print(f"[INFO] Discovery: Response is JSON, extracting URLs from arrays.", flush=True)
            links.update(_extract_urls_from_json(json_data))
        except (json.JSONDecodeError, TypeError):
            # Not JSON, proceed with other extraction methods
            pass

        # Extract hrefs from HTML content
        found_hrefs = HREF_REGEX.findall(response.text)
        for href in found_hrefs:
            full_url = urljoin(url, href)
            if full_url.startswith(('http://', 'https://')):
                links.add(full_url)

        # Parse line by line for plain text URL lists
        for line in response.text.splitlines():
            extracted_url = _extract_url_from_line(line)
            if extracted_url and extracted_url.startswith(('http://', 'https://')):
                links.add(extracted_url)

        # Fallback: regex to catch any URLs we might have missed
        if not links or verbose:
            fallback_urls = URL_REGEX.findall(response.text)
            for fallback_url in fallback_urls:
                # Filter out lines that contain [js]
                if '[js]' not in response.text[response.text.find(fallback_url)-20:response.text.find(fallback_url)+20] if fallback_url in response.text else True:
                    links.add(fallback_url)

    except Exception as e:
        if verbose:
            print(f"[WARN] Discovery failed for {url}: {e}", flush=True)
    return links

def discover_urls_from_file(filename: str, verbose: bool = False, threads: int = 20) -> List[str]:
    """
    Reads a list of seed URLs from a file, fetches them concurrently, 
    and returns a list of all discovered links found on those pages.
    """
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            target_urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    except FileNotFoundError:
        # It's not an error if the file doesn't exist, just return empty
        return []

    if not target_urls:
        return []

    if verbose:
        print(f"[INFO] Discovery: Processing {len(target_urls)} seed URLs from '{filename}'...", flush=True)

    discovered = set()

    # Use threading to speed up the fetching of seed pages
    with ThreadPoolExecutor(max_workers=threads) as executor:
        future_to_url = {executor.submit(_fetch_and_extract_links, url, verbose): url for url in target_urls}

        for future in as_completed(future_to_url):
            try:
                # Add all links found on this page to the set
                discovered.update(future.result())
            except Exception:
                pass

    # Convert raw.githubusercontent.com URLs to fastly.jsdelivr.net
    # AND filter out ignored domains
    converted_urls = set()
    for url in discovered:
        if is_url_allowed(url):
            converted_urls.add(convert_to_jsdelivr_url(url))
        elif verbose:
            # Optional: log what we are skipping to debug
            # print(f"[DEBUG] Discovery: Skipping ignored domain in {url}")
            pass

    if verbose:
        print(f"[INFO] Discovery: Found {len(converted_urls)} potential target URLs (after filtering).", flush=True)

    return sorted(list(converted_urls))

