import requests
import time
from typing import Optional, Dict, Any
from functools import wraps

MAX_RETRIES = 3
RETRY_DELAY = 5
RATE_LIMIT_DELAY = 10

def retry_request(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        verbose = kwargs.get('verbose', False)
        url = kwargs.get('url', args[0] if args else 'unknown')

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                return func(*args, **kwargs)
            except requests.exceptions.HTTPError as e:
                if e.response.status_code in [403, 429, 503]:
                    if attempt < MAX_RETRIES:
                        delay = RATE_LIMIT_DELAY if e.response.status_code in [429, 503] else RETRY_DELAY
                        if verbose:
                            print(f"[RETRY] HTTP {e.response.status_code} for {url}. Attempt {attempt}/{MAX_RETRIES}, waiting {delay}s...")
                        time.sleep(delay)
                    else:
                        if verbose:
                            print(f"[ERROR] Max retries reached for {url}")
                        raise
                else:
                    if verbose:
                        print(f"[ERROR] HTTP {e.response.status_code} for {url}")
                    raise
            except requests.exceptions.RequestException as e:
                if attempt < MAX_RETRIES:
                    if verbose:
                        print(f"[RETRY] Request failed: {e}. Attempt {attempt}/{MAX_RETRIES}, waiting {RETRY_DELAY}s...")
                    time.sleep(RETRY_DELAY)
                else:
                    if verbose:
                        print(f"[ERROR] Max retries reached for {url}")
                    raise

        raise requests.exceptions.RequestException(f"Failed after {MAX_RETRIES} retries")

    return wrapper

@retry_request
def get_with_retry(url: str, headers: Optional[Dict[str, str]] = None, timeout: int = 15, verbose: bool = False, **kwargs) -> requests.Response:
    response = requests.get(url, headers=headers, timeout=timeout, **kwargs)
    response.raise_for_status()
    return response

@retry_request
def post_with_retry(url: str, data: Optional[Any] = None, headers: Optional[Dict[str, str]] = None, timeout: int = 15, verbose: bool = False, **kwargs) -> requests.Response:
    response = requests.post(url, data=data, headers=headers, timeout=timeout, **kwargs)
    response.raise_for_status()
    return response
