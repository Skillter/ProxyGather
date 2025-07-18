import time
from seleniumbase import BaseCase




def is_turnstile_challenge_present(sb: BaseCase, timeout: int = 5) -> bool:
    """
    Comprehensive detection of Cloudflare Turnstile challenges.
    Checks multiple indicators including iframes, scripts, DOM elements, and JS variables.
    """
    
    # Wait for the page to stabilize (better than sleep)
    sb.wait_for_ready_state_complete()
    
    # List of selectors to check
    turnstile_selectors = [
        # Direct Turnstile elements
        'iframe[src*="challenges.cloudflare.com"]',
        'iframe[src*="turnstile"]',
        'div.cf-turnstile',
        'div[class*="cf-turnstile"]',
        'div[id*="cf-turnstile"]',
        
        # Challenge containers
        'div[class*="challenge-container"]',
        'div[class*="challenge-wrapper"]',
        
        # Turnstile widget containers
        'div[data-turnstile-widget]',
        'div[data-cf-turnstile]',
        
        # Shadow DOM host elements
        'cf-turnstile',
        'cloudflare-app',
    ]
    
    # Check for any of the selectors
    for selector in turnstile_selectors:
        try:
            if sb.is_element_present(selector, timeout=0.5):
                return True
        except:
            continue
    
    # Check for Turnstile scripts in the page
    try:
        scripts_present = sb.execute_script("""
            const scripts = Array.from(document.scripts);
            return scripts.some(script => {
                const src = script.src || '';
                const content = script.textContent || '';
                return src.includes('turnstile') || 
                       src.includes('challenges.cloudflare.com') ||
                       content.includes('turnstile') ||
                       content.includes('cf-challenge');
            });
        """)
        if scripts_present:
            return True
    except:
        pass
    
    # Check for Turnstile-related global JavaScript variables
    try:
        js_vars_present = sb.execute_script("""
            return (
                typeof window.turnstile !== 'undefined' ||
                typeof window.cf !== 'undefined' ||
                typeof window.cfTurnstile !== 'undefined' ||
                typeof window.__CF !== 'undefined' ||
                typeof window.__cfRLUnblockHandlers !== 'undefined'
            );
        """)
        if js_vars_present:
            return True
    except:
        pass
    
    # Check for challenge-related text (multiple languages)
    challenge_texts = [
        "Verifying you are human",
        "Checking your browser",
        "Just a moment",
        "One more step",
        "Please wait",
        "Verify you are human",
        "Security check",
        "Verificando que eres humano",  # Spanish
        "Vérification que vous êtes humain",  # French
        "Überprüfung, ob Sie ein Mensch sind",  # German
    ]
    
    for text in challenge_texts:
        try:
            if sb.is_text_visible(text, timeout=0.5):
                # Additional check: ensure it's not just random page content
                page_title = sb.get_title().lower()
                if any(keyword in page_title for keyword in ['cloudflare', 'attention', 'just a moment']):
                    return True
                # Check if the text is in a challenge-like container
                if sb.is_element_present('div[class*="challenge"]', timeout=0.5):
                    return True
        except:
            continue
    
    # Check for Turnstile in shadow DOM
    try:
        shadow_check = sb.execute_script("""
            function checkShadowDOM(element) {
                if (element.shadowRoot) {
                    const shadowContent = element.shadowRoot.innerHTML;
                    if (shadowContent.includes('turnstile') || 
                        shadowContent.includes('cf-challenge')) {
                        return true;
                    }
                    // Recursively check shadow DOM children
                    const shadowElements = element.shadowRoot.querySelectorAll('*');
                    for (let el of shadowElements) {
                        if (checkShadowDOM(el)) return true;
                    }
                }
                return false;
            }
            
            const allElements = document.querySelectorAll('*');
            for (let element of allElements) {
                if (checkShadowDOM(element)) return true;
            }
            return false;
        """)
        if shadow_check:
            return True
    except:
        pass
    
    # Check meta tags for Cloudflare indicators
    try:
        meta_check = sb.execute_script("""
            const metas = document.getElementsByTagName('meta');
            for (let meta of metas) {
                const content = (meta.content || '').toLowerCase();
                const name = (meta.name || '').toLowerCase();
                if (content.includes('cloudflare') || 
                    name.includes('cf-') ||
                    content.includes('turnstile')) {
                    return true;
                }
            }
            return false;
        """)
        if meta_check:
            return True
    except:
        pass
    
    # Check for invisible/hidden Turnstile challenges
    try:
        hidden_elements = sb.execute_script("""
            const elements = document.querySelectorAll('div, iframe');
            for (let el of elements) {
                const style = window.getComputedStyle(el);
                const classes = el.className || '';
                const id = el.id || '';
                
                // Check if element is related to Turnstile but hidden
                if ((classes.includes('turnstile') || 
                     id.includes('turnstile') ||
                     classes.includes('cf-')) &&
                    (style.display === 'none' || 
                     style.visibility === 'hidden' ||
                     parseFloat(style.opacity) === 0)) {
                    return true;
                }
            }
            return false;
        """)
        if hidden_elements:
            return True
    except:
        pass
    
    # Final check: Look for Cloudflare Ray ID (indicates CF protection)
    try:
        if sb.is_element_present('div[class*="ray-id"]', timeout=0.5):
            # If Ray ID is present with challenge elements
            if sb.is_element_present('div[class*="challenge"]', timeout=0.5):
                return True
    except:
        pass
    
    return False


def wait_for_turnstile_completion(sb: BaseCase, max_wait: int = 30) -> bool:
    """
    Waits for Turnstile challenge to complete.
    Returns True if challenge was completed, False if timeout.
    """
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        # Check if we're still on a challenge page
        if not is_turnstile_challenge_present(sb, timeout=2):
            # Additional check: ensure we've navigated away from challenge
            try:
                current_url = sb.get_current_url()
                if 'challenges.cloudflare.com' not in current_url:
                    return True
            except:
                pass
        
        # Check for completion indicators
        try:
            completion_check = sb.execute_script("""
                return (
                    // Check if turnstile callback was executed
                    window.__cfTurnstileCompleted === true ||
                    // Check for success token
                    document.querySelector('input[name="cf-turnstile-response"]')?.value?.length > 0 ||
                    // Check for completion classes
                    document.querySelector('.cf-turnstile-success') !== null
                );
            """)
            if completion_check:
                sb.sleep(0.5)  # Brief wait for redirect
                return True
        except:
            pass
        
        sb.sleep(0.5)
    
    return False

