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
    "ability", "above", "account", "across", "action", "active", "actor", "actual", 
    "address", "admit", "affect", "after", "again", "against", "agent", "agree", 
    "ahead", "album", "alive", "allow", "almost", "alone", "along", "alpha", 
    "always", "amazing", "among", "amount", "anchor", "angel", "animal", "another", 
    "answer", "anxious", "anyone", "apart", "apple", "apply", "archer", "argue", 
    "around", "arrive", "arrow", "article", "artist", "assume", "attack", "author", 
    "autumn", "awake", "award", "aware", "away", "axiom", "baby", "balance", 
    "banana", "basic", "basket", "battle", "beach", "beauty", "become", "before", 
    "begin", "behave", "behind", "believe", "below", "beside", "beta", "better", 
    "beyond", "bicycle", "blade", "blame", "blanket", "bless", "blind", "blood", 
    "blossom", "board", "bottle", "bottom", "bounce", "brain", "branch", "brave", 
    "bread", "break", "breeze", "bridge", "brief", "bright", "bring", "brother", 
    "brown", "brush", "build", "bullet", "butter", "cable", "cactus", "camera", 
    "campus", "cancel", "candy", "canvas", "carbon", "career", "carry", "catch", 
    "cause", "celeb", "center", "century", "certain", "chain", "chair", "chance", 
    "change", "chaos", "chapter", "charge", "chase", "cheese", "cherry", "choice", 
    "circle", "citizen", "claim", "classic", "clean", "clear", "clever", "client", 
    "climate", "clock", "close", "cloud", "cobra", "coffee", "collect", "college", 
    "color", "combine", "comfort", "common", "company", "compare", "complex", "concept", 
    "confirm", "connect", "contact", "contain", "content", "contest", "context", "control", 
    "cookie", "coral", "corner", "correct", "costume", "cotton", "couple", "course", 
    "cover", "craft", "crash", "create", "credit", "crime", "crisis", "critic", 
    "cross", "crowd", "cruise", "crystal", "culture", "current", "custom", "cycle", 
    "damage", "dance", "danger", "daughter", "decade", "decide", "declare", "deep", 
    "defend", "define", "degree", "delay", "deliver", "demand", "depend", "depth", 
    "desert", "design", "desire", "detail", "detect", "develop", "device", "diamond", 
    "digital", "dinner", "direct", "discover", "discuss", "display", "distance", "divide", 
    "doctor", "document", "double", "dragon", "drama", "dream", "dress", "drink", 
    "drive", "during", "eagle", "early", "earth", "easily", "eastern", "echo", 
    "ecology", "economy", "effect", "effort", "either", "electric", "elegant", "element", 
    "elite", "email", "emerge", "emotion", "empty", "enable", "energy", "engage", 
    "engine", "enjoy", "enough", "ensure", "enter", "entire", "entry", "equal", 
    "escape", "essay", "estate", "event", "every", "evidence", "exact", "example", 
    "except", "excite", "exist", "expand", "expect", "expert", "explain", "explore", 
    "express", "extend", "extra", "fabric", "factor", "family", "famous", "fantasy", 
    "father", "fault", "favorite", "feature", "federal", "feeling", "female", "fiction", 
    "field", "fight", "figure", "final", "finance", "finger", "finish", "flame", 
    "flavor", "flight", "float", "floor", "flower", "focus", "follow", "force", 
    "forest", "forget", "formal", "format", "forward", "found", "frame", "freedom", 
    "friend", "future", "galaxy", "gallery", "gamma", "garden", "garlic", "gather", 
    "general", "genius", "gentle", "ghost", "giant", "giggle", "glass", "global", 
    "glory", "glove", "golden", "govern", "grace", "grade", "grand", "grant", 
    "grape", "graph", "grass", "great", "green", "greet", "griffin", "group", 
    "guard", "guess", "guest", "guide", "guilty", "habit", "hammer", "happen"
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
    sb.open(REGISTER_URL)

    max_retries = 3
    for i in range (0, max_retries):
        i+=1
        if verbose: print(f"[INFO] Webshare: Starting new registration process. Try {i}/{max_retries}")
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
            if verbose: print(e)
        
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
                if verbose: print("[INFO] Webshare: reCAPTCHA detected but no challenge was needed.")
            
            else:
                if verbose: print("[INFO] Webshare: No reCAPTCHA detected on the page.")
                
        except Exception as e:
            if verbose: print(f"[ERROR] Webshare: Error during reCAPTCHA detection: {e}")
        
        time.sleep(4)
        if verbose: print("[INFO] Webshare: Getting page source")
        page_source = sb.get_page_source()
        if 'Cannot sign up with' in page_source \
            or 'suspicious email' in page_source \
            or 'please contact customer support team if you think otherwise' in page_source:
                
            print("[ERROR] Webshare: The email was deemed suspicious, retrying with a different one.")
        
            if verbose:
                filename = "Webshare-email-deemed-suspicious.html"
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(page_source)
                    print("[INFO] Webshare: The page content was written to " + filename)
            continue
        
        getstarted_button = 'button:contains("Let\'s Get Started")'
        try: 
            sb.wait_for_element_clickable(getstarted_button, timeout=7) # 7 plus 4 from earlier time.sleep
        except Exception as e:
            if verbose: print(e)


        if sb.is_element_clickable(getstarted_button):
            if verbose: print("[INFO] Webshare: 'Let's Get Started' button found and it's clickable. Clicking...")
            break
        elif sb.is_element_visible(getstarted_button):
            if verbose: print("[WARNING] Webshare: 'Let's Get Started' button found but it's not clickable. Trying to click anyway...")
            break
        elif sb.is_element_present(getstarted_button):
            if verbose: print("[WARNING] Webshare: 'Let's Get Started' button found but it's not visible. Trying to click anyway...")
            break
        else:
            print("[ERROR] Webshare: 'Let's Get Started' button not found.")
            if i < max_retries: print("[INFO] Webshare: Retrying the registration process")
            continue
        
        
        
        
        

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