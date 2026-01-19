import time
import requests
from typing import List
from urllib.robotparser import RobotFileParser

API_URL = "https://proxy-daily.com/api/serverside/proxies"
ROBOTS_URL = "https://proxy-daily.com/robots.txt"
BATCH_SIZE = 100  # Server likely limits response size, so we paginate

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'X-Requested-With': 'XMLHttpRequest',
    'Referer': 'https://proxy-daily.com/'
}

def scrape_from_proxydaily(verbose: bool = True, compliant_mode: bool = False) -> List[str]:
    """
    Scrapes proxies from proxy-daily.com by mimicking the DataTables server-side API call.
    Handles pagination to fetch all available records.
    
    Args:
        verbose: Print status messages.
        compliant_mode: If True, checks robots.txt and ONLY fetches the first page (one request).
    """
    if verbose:
        print("[RUNNING] 'Proxy-Daily' scraper has started.")

    # --- Compliance Check ---
    if compliant_mode:
        if verbose:
            print("[INFO] Proxy-Daily: Running in COMPLIANT mode. Checking robots.txt...")
        
        rp = RobotFileParser()
        try:
            rp.set_url(ROBOTS_URL)
            rp.read()
            if not rp.can_fetch("*", API_URL):
                if verbose:
                    print(f"[WARN] Proxy-Daily: blocked by robots.txt ({API_URL}). Stopping.")
                return []
            if verbose:
                print("[INFO] Proxy-Daily: Allowed by robots.txt. Being polite (waiting 2s)...")
            time.sleep(2)
        except Exception as e:
            if verbose:
                print(f"[WARN] Proxy-Daily: Could not fetch robots.txt: {e}. Proceeding with caution.")

    all_proxies = set()
    
    # Base DataTables parameters
    params = {
        'draw': '1',
        'length': str(BATCH_SIZE), 
        'search[value]': '',
        'search[regex]': 'false',
    }

    # Add column definitions
    columns = ['ip', 'port', 'protocol', 'speed', 'anonymity', 'country']
    for i, col_name in enumerate(columns):
        params[f'columns[{i}][data]'] = col_name
        params[f'columns[{i}][name]'] = col_name
        params[f'columns[{i}][searchable]'] = 'true'
        params[f'columns[{i}][orderable]'] = 'false'
        params[f'columns[{i}][search][value]'] = ''
        params[f'columns[{i}][search][regex]'] = 'false'

    start = 0
    total_records = None # Will be set after first request

    while True:
        # Update dynamic parameters
        params['start'] = str(start)
        params['_'] = str(int(time.time() * 1000))

        if verbose:
            print(f"[INFO] Proxy-Daily: Fetching proxies starting at index {start}...")

        try:
            response = requests.get(API_URL, headers=HEADERS, params=params, timeout=20)
            response.raise_for_status()
            data = response.json()
            
            # Update total records on first run
            if total_records is None:
                total_records = data.get('recordsTotal', 0)
                if verbose and not compliant_mode:
                    print(f"[INFO] Proxy-Daily: Total records available: {total_records}")

            items = data.get('data', [])
            if not items:
                if verbose:
                    print("[INFO] Proxy-Daily: No more items returned. Stopping.")
                break

            for item in items:
                ip = item.get('ip')
                port = item.get('port')
                if ip and port:
                    all_proxies.add(f"{ip}:{port}")
            
            if verbose:
                print(f"[INFO]   ... Parsed {len(items)} items. Total unique: {len(all_proxies)}")

            # --- Compliance Exit ---
            if compliant_mode:
                if verbose:
                    print("[INFO] Proxy-Daily: Stopping after first page (Compliance Mode).")
                break
            # ---------------------

            # Prepare for next page
            start += BATCH_SIZE
            
            # Stop if we've reached the known total
            if start >= total_records:
                if verbose:
                    print("[INFO] Proxy-Daily: Reached end of records.")
                break

            # Polite delay between pagination requests
            time.sleep(1) 

        except Exception as e:
            if verbose:
                print(f"[ERROR] Proxy-Daily: Failed to fetch data at index {start}: {e}")
            break

    if verbose:
        print(f"[INFO] Proxy-Daily: Finished. Found {len(all_proxies)} unique proxies.")

    return sorted(list(all_proxies))

