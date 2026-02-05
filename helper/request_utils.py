import requests
from typing import Optional, Dict, Any

# Disable SSL certificate verification warnings
from urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

def get_with_retry(url: str, headers: Optional[Dict[str, str]] = None, timeout: int = 15, verbose: bool = False, **kwargs) -> requests.Response:
    response = requests.get(url, headers=headers, timeout=timeout, verify=False, **kwargs)
    response.raise_for_status()
    return response

def post_with_retry(url: str, data: Optional[Any] = None, headers: Optional[Dict[str, str]] = None, timeout: int = 15, verbose: bool = False, **kwargs) -> requests.Response:
    response = requests.post(url, data=data, headers=headers, timeout=timeout, verify=False, **kwargs)
    response.raise_for_status()
    return response
