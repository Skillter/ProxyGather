import re
import time
import requests
from typing import List

# The main lists available on ProxyNova
URLS = [
    "https://www.proxynova.com/proxy-server-list/",
    "https://www.proxynova.com/proxy-server-list/elite-proxies/",
    "https://www.proxynova.com/proxy-server-list/anonymous-proxies/",
    "https://www.proxynova.com/proxy-server-list/transparent-proxies/"
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
}

# Regex to find the row with proxy ID
ROW_REGEX = re.compile(r'<tr data-proxy-id="\d+">([\s\S]*?)</tr>')

# Regex to find the script content inside the IP cell
SCRIPT_REGEX = re.compile(r'<script>document\.write\((.*)\)</script>')

# Regex to find the port. It's either a number or inside an anchor tag.
PORT_REGEX = re.compile(r'(?:<a[^>]*>)?\s*(\d+)\s*(?:</a>)?')

class JSStringParser:
    """
    A lightweight recursive parser for the specific subset of JavaScript 
    string manipulations used by ProxyNova.
    """
    def __init__(self, expression):
        self.expr = expression.strip()
        self.pos = 0
        self.length = len(self.expr)

    def parse(self) -> str:
        result = self._parse_string_literal()
        while self.pos < self.length:
            if self.expr[self.pos] == '.':
                self.pos += 1
                result = self._parse_method_call(result)
            elif self.expr[self.pos] == ')':
                break
            else:
                self.pos += 1
        return result

    def _parse_string_literal(self) -> str:
        self._skip_whitespace()
        if self.pos >= self.length: return ""
        
        quote_char = self.expr[self.pos]
        if quote_char not in "\"'":
            return ""
        
        self.pos += 1
        start = self.pos
        while self.pos < self.length and self.expr[self.pos] != quote_char:
            if self.expr[self.pos] == '\\': 
                self.pos += 2
            else:
                self.pos += 1
        
        text = self.expr[start:self.pos]
        self.pos += 1
        return text

    def _parse_method_call(self, current_str: str) -> str:
        method_start = self.pos
        while self.pos < self.length and self.expr[self.pos] != '(':
            self.pos += 1
        
        method_name = self.expr[method_start:self.pos]
        self.pos += 1 # Skip '('
        
        args = []
        while self.pos < self.length and self.expr[self.pos] != ')':
            arg = self._parse_argument()
            args.append(arg)
            self._skip_whitespace()
            if self.pos < self.length and self.expr[self.pos] == ',':
                self.pos += 1
        
        self.pos += 1 # Skip ')'
        return self._apply_method(current_str, method_name, args)

    def _parse_argument(self):
        self._skip_whitespace()
        if self.pos >= self.length: return None
        
        if self.expr[self.pos] in "\"'":
            return self.parse() 
        else:
            start = self.pos
            while self.pos < self.length and self.expr[self.pos] not in ',)':
                self.pos += 1
            math_expr = self.expr[start:self.pos]
            try:
                return int(eval(math_expr, {"__builtins__":{}}))
            except:
                return 0

    def _apply_method(self, obj: str, method: str, args: list) -> str:
        if method == 'split': return obj
        if method == 'reverse': return obj[::-1]
        if method == 'join': return obj
        if method == 'repeat': 
            count = args[0] if args else 0
            return obj * count
        if method == 'substring':
            start = args[0] if len(args) > 0 else 0
            end = args[1] if len(args) > 1 else None
            return obj[start:end]
        if method == 'concat':
            other = args[0] if args else ""
            return obj + str(other)
        if method == 'substr':
            start = args[0] if len(args) > 0 else 0
            length = args[1] if len(args) > 1 else None
            if length is None: return obj[start:]
            return obj[start:start+length]
        return obj

    def _skip_whitespace(self):
        while self.pos < self.length and self.expr[self.pos].isspace():
            self.pos += 1

def _deobfuscate_ip(js_code: str) -> str:
    try:
        parser = JSStringParser(js_code)
        return parser.parse()
    except Exception:
        return ""

def scrape_from_proxynova(verbose: bool = True) -> List[str]:
    """
    Scrapes proxies from proxynova.com by parsing the HTML and executing 
    the JavaScript string obfuscation logic in Python.
    """
    if verbose:
        print("[RUNNING] 'ProxyNova' scraper has started.")

    all_proxies = set()
    
    for url in URLS:
        if verbose:
            print(f"[INFO] ProxyNova: Scraping {url}...")
            
        try:
            response = requests.get(url, headers=HEADERS, timeout=20)
            if response.status_code != 200:
                if verbose: print(f"[WARN] ProxyNova: HTTP {response.status_code} for {url}")
                continue
                
            html_content = response.text
            
            # Find all proxy rows
            rows = ROW_REGEX.findall(html_content)
            if not rows:
                if verbose: print(f"[INFO]   ... No proxy rows found on {url}")
                continue
                
            new_proxies_count = 0
            for row_html in rows:
                # 1. Extract IP script
                script_match = SCRIPT_REGEX.search(row_html)
                if not script_match:
                    continue
                
                js_code = script_match.group(1)
                ip = _deobfuscate_ip(js_code)
                
                # 2. Extract Port
                cells = row_html.split('<td')
                if len(cells) < 3: continue
                
                port_html = cells[2]
                port_match = PORT_REGEX.search(port_html)
                if not port_match:
                    continue
                
                port = port_match.group(1)
                
                if ip and port:
                    if ip.count('.') == 3:
                        proxy = f"{ip}:{port}"
                        if proxy not in all_proxies:
                            all_proxies.add(proxy)
                            new_proxies_count += 1
            
            if verbose:
                print(f"[INFO]   ... Found {new_proxies_count} proxies. Total unique: {len(all_proxies)}")
            
            time.sleep(1.5)

        except Exception as e:
            if verbose:
                print(f"[ERROR] ProxyNova: Failed to scrape {url}: {e}")

    if verbose:
        print(f"[INFO] ProxyNova: Finished. Found {len(all_proxies)} unique proxies.")

    return sorted(list(all_proxies))

