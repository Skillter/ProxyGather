import time
import requests
from typing import List, Dict, Optional
import random
import string
import json
import os
from seleniumbase import BaseCase
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import NoSuchWindowException, NoSuchElementException

LOGIN_URL = "https://dashboard.webshare.io/login"
REGISTER_URL = "https://dashboard.webshare.io/register/?source=nav_register"
PROXY_LIST_API_URL = "https://proxy.webshare.io/api/v2/proxy/list/?mode=direct&page=1&page_size=10"
CREDENTIALS_FILE = "credentials.json"

USERNAME_WORDS = [
    "shadow", "viper", "glitch", "nexus", "pulse", "void", "nova", "cobra",
    "raven", "bolt", "phantom", "wraith", "serpent", "hawk", "blade", "storm",
    "titan", "golem", "echo", "cipher", "vector", "quark", "hydro", "pyro",
    "aero", "terra", "luna", "solar", "cyborg", "laser", "plasma", "droid",
    "matrix", "nebula", "comet", "orbit", "ryzen", "intel", "core", "volta",
    "dragon", "griffin", "sphinx", "wizard", "mage", "sorcerer", "warlock",
    "elf", "orc", "goblin", "troll", "nymph", "siren", "phoenix", "hydra",
    "kraken", "cyclops", "minotaur", "centaur", "pixie", "sprite", "banshee",
    "wolf", "tiger", "panther", "jaguar", "cougar", "lynx", "falcon", "eagle",
    "hornet", "wasp", "spider", "scorpion", "shark", "whale", "orca",
    "forest", "mountain", "river", "ocean", "desert", "jungle", "canyon",
    "meadow", "stream", "pebble", "boulder", "root", "branch",
    "king", "queen", "ace", "jack", "joker", "spade", "omega", "alpha", "beta",
    "delta", "gamma", "sigma", "theta", "zeta", "axiom", "enigma", "paradox",
    "vertex", "zenith", "nadir", "karma", "chaos", "order", "logic", "fate",
    "anchor", "compass", "hammer", "anvil", "shield", "sword", "arrow", "bow",
    "needle", "thread", "key", "lock", "chain", "gear", "engine", "piston"
]

def _generate_random_email():
    word1 = random.choice(USERNAME_WORDS)
    word2 = random.choice(USERNAME_WORDS)
    while word1 == word2:
        word2 = random.choice(USERNAME_WORDS)
    return f"{word1}{word2}@gmail.com"

def _generate_random_password():
    return f"TestPass_{''.join(random.choices(string.ascii_lowercase + string.digits, k=10))}!"

def _load_credentials() -> Dict:
    if not os.path.exists(CREDENTIALS_FILE):
        return {}
    try:
        with open(CREDENTIALS_FILE, 'r') as f:
            return json.load(f)
    except (IOError, json.JSONDecodeError):
        return {}

def _save_credentials(creds: Dict):
    try:
        with open(CREDENTIALS_FILE, 'w') as f:
            json.dump(creds, f, indent=4)
    except IOError as e:
        print(f"\n[ERROR] Could not save credentials to '{CREDENTIALS_FILE}': {e}")

def _try_direct_api_call(creds: Dict, verbose: bool) -> Optional[List[str]]:
    if verbose: print("[INFO] Webshare: Found saved session. Attempting direct API call...")
    try:
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36',
            'Authorization': f"Token {creds['cookies']['newDesignLoginToken']}",
            'origin': 'https://dashboard.webshare.io',
            'referer': 'https://dashboard.webshare.io/',
        })
        for name, value in creds['cookies'].items():
            session.cookies.set(name, value)
            
        response = session.get(PROXY_LIST_API_URL, timeout=15)
        response.raise_for_status()
        proxy_data = response.json()
        
        found_proxies = proxy_data.get('results', [])
        if not found_proxies:
            if verbose: print("[WARN] Webshare: Direct API call successful but no proxies returned.")
            return []
        
        all_proxies = set()
        for proxy_info in found_proxies:
            username = proxy_info.get('username')
            password = proxy_info.get('password')
            ip = proxy_info.get('proxy_address')
            port = proxy_info.get('port')
            if all([username, password, ip, port]):
                all_proxies.add(f"{username}:{password}@{ip}:{port}")
        
        if verbose: print("[SUCCESS] Webshare: Direct API call successful. Browser not needed.")
        return sorted(list(all_proxies))
        
    except (requests.exceptions.RequestException, KeyError) as e:
        if verbose: print(f"[INFO] Webshare: Direct API call failed (session likely expired). Falling back to browser login. Error: {e}")
        return None

def _login(sb: BaseCase, creds: Dict, verbose: bool) -> bool:
    if verbose: print(f"[INFO] Webshare: Attempting to log in as {creds['email']}...")
    try:
        sb.open(LOGIN_URL)
        sb.wait_for_element("input#email-input")
        sb.type("input#email-input", creds['email'])
        sb.type("input[data-testid=password-input]", creds['password'])
        sb.click("button[data-testid=signin-button]")
        
        wait = WebDriverWait(sb.driver, 15)
        wait.until(lambda driver: '/proxy/list' in driver.current_url)

        if '/proxy/list' not in sb.get_current_url():
            raise Exception("Login failed, page did not redirect to proxy list.")
        if verbose: print("[SUCCESS] Webshare: Login successful.")
        return True
    except Exception as e:
        if verbose: print(f"[WARN] Webshare: An error occurred during login attempt: {e}. Will try to register.")
        return False

def _register(sb: BaseCase, verbose: bool) -> Dict:
    if verbose: print("[INFO] Webshare: Starting new registration process.")
    sb.open(REGISTER_URL)
    sb.wait_for_element("input#email-input")

    email = _generate_random_email()
    password = _generate_random_password()
    
    if verbose: print(f"[INFO] Webshare: Simulating typing for new account: {email}")
    sb.type("input#email-input", email)
    sb.type("input[data-testid=password-input]", password)
    sb.click("button[data-testid=signup-button]")

    # time.sleep(2)  # Allow time for captcha to potentially load
    
    # Google reCAPTCHA detection selectors
    recaptcha_challenge_iframe = 'iframe[src*="google.com/recaptcha/api2/bframe"]'
    recaptcha_anchor_iframe = 'iframe[src*="google.com/recaptcha/api2/anchor"]'
    recaptcha_badge = '.grecaptcha-badge'

    # wait for recaptcha
    try: 
        sb.wait_for_element_visible(recaptcha_challenge_iframe, timeout=10)
    except Exception as e: 
        print(e)
    
    try:
        if sb.is_element_visible(recaptcha_challenge_iframe):
            if verbose: print("[INFO] Webshare: Google reCAPTCHA challenge detected and visible.")
            try:
                # Wait for the challenge to disappear (indicating success)
                sb.wait_for_element_not_visible(recaptcha_challenge_iframe, timeout=120)
                if verbose: print("[INFO] Webshare: reCAPTCHA challenge disappeared.")
            except Exception as e:
                if verbose: print(f"[WARN] Webshare: reCAPTCHA challenge never disappeared: {e}")
        
        elif sb.is_element_present(recaptcha_badge) or sb.is_element_present(recaptcha_anchor_iframe):
            if verbose: print("[INFO] Webshare: reCAPTCHA detected but no challenge shown yet.")
        
        else:
            if verbose: print("[INFO] Webshare: No reCAPTCHA detected on the page.")
            
    except Exception as e:
        if verbose: print(f"[ERROR] Webshare: Error during reCAPTCHA detection: {e}")
        
        
    getstarted_button = 'button:contains("Let\'s Get Started")'
    sb.wait_for_element_clickable(getstarted_button, timeout=10)
    if sb.wait_for_element_clickable(getstarted_button):
        if verbose: print("[INFO] Webshare: 'Let's Get Started' button found and it's clickable.")
    elif sb.wait_for_element(getstarted_button):
        if verbose: print("[INFO] Webshare: 'Let's Get Started' button found but it's not clickable.")
    elif sb.wait_for_element_present(getstarted_button):
        if verbose: print("[INFO] Webshare: 'Let's Get Started' button found but it's not visible.")
    else:
        if verbose: print("[INFO] Webshare: 'Let's Get Started' button not found.")
    sb.click('button:contains("Let\'s Get Started")')

    
    wait = WebDriverWait(sb.driver, 25)
    wait.until(lambda driver: '/proxy/list' in driver.current_url)

    if '/proxy/list' not in sb.get_current_url():
        raise Exception("Registration failed, page did not redirect to proxy list.")

    if verbose: print("[SUCCESS] Webshare: Registration and onboarding complete.")
    return {'email': email, 'password': password}

def scrape_from_webshare(sb: BaseCase, verbose: bool = True) -> List[str]:
    """
    Scrapes Webshare using its own dedicated browser instance.
    """
    if verbose: print("[RUNNING] 'Webshare.io' automation scraper has started.")
    
    all_credentials = _load_credentials()
    webshare_data = all_credentials.get('webshare')

    if webshare_data and 'cookies' in webshare_data:
        proxies = _try_direct_api_call(webshare_data, verbose)
        if proxies is not None:
            return proxies
    
    try:
        logged_in = False
        if webshare_data and 'email' in webshare_data:
            logged_in = _login(sb, webshare_data, verbose)

        new_session_data = {}
        if not logged_in:
            new_session_data = _register(sb, verbose)
        else:
            new_session_data = webshare_data

        # Check if browser is still active before proceeding
        if not sb.driver.window_handles:
             raise NoSuchWindowException("Browser window was closed during login/registration.")

        if verbose: print("[INFO] Webshare: Extracting fresh authentication cookies...")
        time.sleep(2)
        cookies = sb.get_cookies()
        auth_cookies = {cookie['name']: cookie['value'] for cookie in cookies}
        
        if 'newDesignLoginToken' not in auth_cookies:
            raise ValueError("Login succeeded, but could not find the necessary API token in cookies.")
            
        new_session_data['cookies'] = auth_cookies
        all_credentials['webshare'] = new_session_data
        _save_credentials(all_credentials)
        if verbose: print(f"[INFO] Webshare: Session for {new_session_data['email']} saved.")
        
        return _try_direct_api_call(new_session_data, verbose) or []

    except NoSuchWindowException:
        if verbose:
            print(f"[ERROR] Webshare scraper failed because the browser window was closed unexpectedly.")
        return []
    except Exception as e:
        if verbose:
            print(f"[ERROR] Webshare scraper failed: {e}")
        return []