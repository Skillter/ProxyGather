import re
from typing import List, Set
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed
from helper.request_utils import get_with_retry

# Matches href attributes to extract potential links from HTML
HREF_REGEX = re.compile(r'href=["\']([^"\']+)["\']', re.IGNORECASE)
# Matches [number] prefix like [25] or [15]
PAGE_COUNT_PREFIX = re.compile(r'^\[\d+\](.+)$')

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

def _fetch_and_extract_links(url: str, verbose: bool) -> Set[str]:
    """
    Fetches a single URL and extracts all valid http/https links from it.
    Handles both HTML pages and plain text URL lists.
    """
    links = set()
    try:
        if verbose:
            print(f"[INFO] Discovery: Fetching source {url}...", flush=True)

        # Use a shorter timeout for discovery to avoid hanging
        response = get_with_retry(url, timeout=15, verbose=verbose)

        # First try to extract hrefs from HTML content
        found_hrefs = HREF_REGEX.findall(response.text)
        for href in found_hrefs:
            full_url = urljoin(url, href)
            if full_url.startswith(('http://', 'https://')):
                links.add(full_url)

        # Also parse line by line for plain text URL lists
        for line in response.text.splitlines():
            extracted_url = _extract_url_from_line(line)
            if extracted_url and extracted_url.startswith(('http://', 'https://')):
                links.add(extracted_url)

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
                
    if verbose:
        print(f"[INFO] Discovery: Found {len(discovered)} potential target URLs.", flush=True)

    return sorted(list(discovered))

