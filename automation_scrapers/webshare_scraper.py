import time
import requests
import re
import undetected_chromedriver as uc
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from typing import List, Dict, Optional
import random
import string
import json
import os

# --- Configuration ---
LOGIN_URL = "https://dashboard.webshare.io/login"
REGISTER_URL = "https://dashboard.webshare.io/register/?source=nav_register"
PROXY_LIST_API_URL = "https://proxy.webshare.io/api/v2/proxy/list/?mode=direct&page=1&page_size=10"
CREDENTIALS_FILE = "credentials.json"

# --- EXPANDED: Much larger and more diverse wordlist ---
USERNAME_WORDS = [
    # Tech/Sci-Fi
    "shadow", "viper", "glitch", "nexus", "pulse", "void", "nova", "cobra",
    "raven", "bolt", "phantom", "wraith", "serpent", "hawk", "blade", "storm",
    "titan", "golem", "echo", "cipher", "vector", "quark", "hydro", "pyro",
    "aero", "terra", "luna", "solar", "cyborg", "laser", "plasma", "droid",
    "matrix", "nebula", "comet", "orbit", "ryzen", "intel", "core", "volta",
    
    # Fantasy/Mythical
    "dragon", "griffin", "sphinx", "wizard", "mage", "sorcerer", "warlock",
    "elf", "orc", "goblin", "troll", "nymph", "siren", "phoenix", "hydra",
    "kraken", "cyclops", "minotaur", "centaur", "pixie", "sprite", "banshee",
    
    # Nature/Animals
    "wolf", "tiger", "panther", "jaguar", "cougar", "lynx", "falcon", "eagle",
    "hornet", "wasp", "spider", "scorpion", "shark", "whale", "orca",
    "forest", "mountain", "river", "ocean", "desert", "jungle", "canyon",
    "meadow", "stream", "pebble", "boulder", "root", "branch",
    
    # Abstract/Concepts
    "king", "queen", "ace", "jack", "joker", "spade", "omega", "alpha", "beta",
    "delta", "gamma", "sigma", "theta", "zeta", "axiom", "enigma", "paradox",
    "vertex", "zenith", "nadir", "karma", "chaos", "order", "logic", "fate",
    
    # Objects/Misc
    "anchor", "compass", "hammer", "anvil", "shield", "sword", "arrow", "bow",
    "needle", "thread", "key", "lock", "chain", "gear", "engine", "piston"
]

def _generate_random_email():
    """Generates a plausible, word-based random email address."""
    word1 = random.choice(USERNAME_WORDS)
    word2 = random.choice(USERNAME_WORDS)
    while word1 == word2:
        word2 = random.choice(USERNAME_WORDS)
    return f"{word1}{word2}@gmail.com"

def _generate_random_password():
    """Generates a random password."""
    return f"TestPass_{''.join(random.choices(string.ascii_lowercase + string.digits, k=10))}!"

def _load_credentials() -> Dict:
    """Loads credentials from the JSON file."""
    if not os.path.exists(CREDENTIALS_FILE):
        return {}
    try:
        with open(CREDENTIALS_FILE, 'r') as f:
            return json.load(f)
    except (IOError, json.JSONDecodeError):
        return {}

def _save_credentials(creds: Dict):
    """Saves the credentials dictionary to the JSON file."""
    try:
        with open(CREDENTIALS_FILE, 'w') as f:
            json.dump(creds, f, indent=4)
    except IOError as e:
        print(f"[ERROR] Could not save credentials to '{CREDENTIALS_FILE}': {e}")

def _try_direct_api_call(creds: Dict, verbose: bool) -> Optional[List[str]]:
    """Attempts to fetch proxies directly using saved cookies."""
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

def _login(driver, wait, creds: Dict, verbose: bool) -> bool:
    """Attempts to log in with existing credentials."""
    if verbose: print(f"[INFO] Webshare: Attempting to log in as {creds['email']}...")
    try:
        driver.get(LOGIN_URL)
        email_input = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'input[data-testid="email-input"]')))
        password_input = driver.find_element(By.CSS_SELECTOR, 'input[data-testid="password-input"]')
        login_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[data-testid="signin-button"]')))
        
        if verbose: print("[INFO] Webshare: Login form ready. Entering credentials...")
        email_input.send_keys(creds['email'])
        time.sleep(0.5)
        password_input.send_keys(creds['password'])
        time.sleep(0.5)
        login_button.click()

        WebDriverWait(driver, 10).until(EC.url_contains('/proxy/list'))
        if verbose: print("[SUCCESS] Webshare: Login successful.")
        return True
            
    except Exception as e:
        if verbose: print(f"[WARN] Webshare: An error occurred during login attempt: {e}. Will try to register.")
        return False

def _register(driver, wait, verbose: bool) -> Dict:
    """Performs the registration process."""
    if verbose: print("[INFO] Webshare: Starting new registration process.")
    driver.get(REGISTER_URL)
    email_input = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'input[data-testid="email-input"]')))
    password_input = driver.find_element(By.CSS_SELECTOR, 'input[data-testid="password-input"]')
    signup_button = driver.find_element(By.CSS_SELECTOR, 'button[data-testid="signup-button"]')
    email = _generate_random_email()
    password = _generate_random_password()
    
    if verbose: print(f"[INFO] Webshare: Simulating typing for new account: {email}")
    email_input.send_keys(email)
    time.sleep(0.5)
    password_input.send_keys(password)
    time.sleep(1)
    signup_button.click()

    print("\n" + "="*70 + "\nACTION REQUIRED: Please solve the CAPTCHA in the browser.\n" + "="*70 + "\n")

    start_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "div.MuiDialog-root button.MuiButton-root")))
    if verbose: print("[INFO] Webshare: 'Let's Get Started' button found. Clicking...")
    time.sleep(1)
    start_button.click()
    
    wait.until(EC.url_contains('/proxy/list'))
    if verbose: print("[SUCCESS] Webshare: Registration and onboarding complete.")
    return {'email': email, 'password': password}

def scrape_from_webshare(verbose: bool = True) -> List[str]:
    """
    Tries to use a saved session first. If that fails, logs in with saved
    credentials. If that fails, registers a new account.
    """
    if verbose: print("[RUNNING] 'Webshare.io' automation scraper has started.")
    all_credentials = _load_credentials()
    webshare_data = all_credentials.get('webshare')

    if webshare_data and 'cookies' in webshare_data:
        proxies = _try_direct_api_call(webshare_data, verbose)
        if proxies is not None:
            return proxies
    
    driver = None
    try:
        if verbose: print("[INFO] Webshare: Initializing automated browser to get a new session...")
        options = uc.ChromeOptions()
        options.add_argument("--window-size=1920,1080")
        driver = uc.Chrome(options=options, use_subprocess=True)
        wait = WebDriverWait(driver, 120)
        
        logged_in = False
        if webshare_data and 'email' in webshare_data:
            logged_in = _login(driver, wait, webshare_data, verbose)

        new_session_data = {}
        if not logged_in:
            new_session_data = _register(driver, wait, verbose)
        else:
            new_session_data = webshare_data

        if verbose: print("[INFO] Webshare: Extracting fresh authentication cookies...")
        time.sleep(2)
        cookies = driver.get_cookies()
        auth_cookies = {cookie['name']: cookie['value'] for cookie in cookies}
        
        if 'newDesignLoginToken' not in auth_cookies:
            raise ValueError("Login succeeded, but could not find the necessary API token in cookies.")
            
        new_session_data['cookies'] = auth_cookies
        all_credentials['webshare'] = new_session_data
        _save_credentials(all_credentials)
        if verbose: print(f"[INFO] Webshare: Session for {new_session_data['email']} saved to {CREDENTIALS_FILE}.")
        
        return _try_direct_api_call(new_session_data, verbose) or []

    except Exception as e:
        print(f"[ERROR] Webshare scraper failed: {e}")
        return []

    finally:
        if driver:
            if verbose: print("[INFO] Webshare: Shutting down the browser.")
            driver.quit()