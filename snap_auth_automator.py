"""
Snapchat Autonomous Authentication & Session Minting Engine
Runs 100% on GitHub Actions (or any headless Linux environment) behind Cloudflare WARP.
Handles:
1. Fast-path: Mint fresh Bearer ticket (hCgw...) from existing session cookies via /accounts/sso
2. Deep-path: Playwright stealth browser automation for username + password login
3. Dynamic cookie & ticket capture
4. Automatic self-updating of GitHub repository secrets via gh CLI
"""

import os
import sys
import json
import time
import random
import re
import base64
import asyncio
import subprocess
import requests
import imaplib
import email
import email.utils
import urllib.parse
from playwright.async_api import async_playwright

try:
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
except Exception:
    pass

SNAPML_BASE = "https://gcp.api.snapchat.com/lens-studio-web-snapml"
ACCOUNTS_BASE = "https://accounts.snapchat.com"
REPO = "gurination1/snapchat-easylens-pipeline"


def fetch_latest_snap_tiv_url(gmail_user: str, gmail_app_pwd: str, min_timestamp: float) -> str:
    """
    Polls Gmail via IMAP for a Snapchat Sign-In Verification email received after min_timestamp.
    Extracts and returns the 'Approve' link.
    """
    if not gmail_user or not gmail_app_pwd:
        return ""
    try:
        clean_pwd = gmail_app_pwd.replace(" ", "")
        mail = imaplib.IMAP4_SSL("imap.gmail.com", timeout=15)
        mail.login(gmail_user, clean_pwd)
        mail.select("inbox")
        status, messages = mail.search(None, '(FROM "snapchat")')
        if not messages or not messages[0]:
            status, messages = mail.search(None, '(SUBJECT "Snapchat")')
        if not messages or not messages[0]:
            mail.logout()
            return ""
        ids = messages[0].split()
        for mid in reversed(ids[-6:]):
            _, data = mail.fetch(mid, "(RFC822)")
            msg = email.message_from_bytes(data[0][1])
            date_tuple = email.utils.parsedate_tz(msg.get("Date"))
            msg_time = email.utils.mktime_tz(date_tuple) if date_tuple else 0
            if msg_time < min_timestamp:
                continue
            subject = msg.get("Subject", "")
            if any(w in subject.lower() for w in ["verification", "sign-in", "signin", "security", "snapchat"]):
                html = ""
                for part in msg.walk():
                    if part.get_content_type() == "text/html":
                        html = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                        break
                if not html and not msg.is_multipart():
                    html = msg.get_payload(decode=True).decode("utf-8", errors="ignore")
                anchors = re.findall(r"<a[^>]*href=[\"\x27]([^\"]+)[\"\x27][^>]*>(.*?)</a>", html, re.DOTALL)
                for href, text in anchors:
                    clean_text = re.sub(r"<[^>]+>", "", text).strip()
                    if "Approve" in clean_text or "tiv/landing" in href:
                        print(f"[GMAIL IMAP] Found Snapchat Approve link in message #{mid.decode()} ('{clean_text}')")
                        mail.logout()
                        return href
        mail.logout()
    except Exception as e:
        print(f"[GMAIL IMAP WARN] {e}")
    return ""


def get_gemini_api_keys() -> list:
    keys = []
    if os.getenv("GEMINI_API_KEY"):
        keys.append(os.getenv("GEMINI_API_KEY").strip())
    if os.getenv("GEMINI_API_KEYS"):
        for k in os.getenv("GEMINI_API_KEYS").split(","):
            k = k.strip()
            if k and k not in keys:
                keys.append(k)
    return keys


def solve_captcha_with_gemini(image_path: str, instruction: str) -> list:
    """Uses Gemini Vision API to solve reCAPTCHA image grids."""
    api_keys = get_gemini_api_keys()
    if not api_keys or not os.path.exists(image_path):
        return []

    try:
        with open(image_path, "rb") as f:
            b64_img = base64.b64encode(f.read()).decode("utf-8")
    except Exception:
        return []

    prompt = f"""You are an accessibility visual assistant.
Analyze this CAPTCHA grid image with user instruction: '{instruction}'.
Tiles are arranged in a grid numbered 1 to N from top-left to bottom-right (e.g. 1-9 for 3x3).
Return ONLY a raw JSON array of integer tile numbers that match the target object.
Example: [2, 4, 7]
Do NOT write markdown fences, explanations, or any other characters."""

    for k in api_keys:
        for model in ["gemini-flash-latest", "gemini-flash-lite-latest", "gemini-2.5-flash"]:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={k}"
            payload = {
                "contents": [{
                    "parts": [
                        {"text": prompt},
                        {"inlineData": {"mimeType": "image/png", "data": b64_img}}
                    ]
                }],
                "generationConfig": {"temperature": 0.1, "maxOutputTokens": 100}
            }
            try:
                r = requests.post(url, json=payload, timeout=25)
                if r.status_code == 200:
                    text = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                    m = re.search(r"\[[\d,\s]+\]", text)
                    if m:
                        tiles = json.loads(m.group(0))
                        print(f"[GEMINI CAPTCHA SOLVER] Recommended tiles: {tiles}")
                        return tiles
            except Exception as e:
                print(f"[GEMINI CAPTCHA WARN] {model} query error: {e}")
    return []

def solve_google_text_captcha_with_gemini(image_path: str) -> str:
    """Uses Gemini Vision API to transcribe distorted text CAPTCHA from Google login."""
    api_keys = get_gemini_api_keys()
    if not os.path.exists(image_path):
        return ""

    b64_img = ""
    try:
        with open(image_path, "rb") as f:
            b64_img = base64.b64encode(f.read()).decode("utf-8")
    except Exception:
        pass

    prompt = "Transcribe the distorted alphanumeric text shown in this CAPTCHA image. Return ONLY the lowercase characters with no spaces, punctuation, or explanations."
    if b64_img and api_keys:
        for k in api_keys:
            for model in ["gemini-flash-latest", "gemini-flash-lite-latest", "gemini-2.5-flash"]:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={k}"
                payload = {
                    "contents": [{
                        "parts": [
                            {"text": prompt},
                            {"inlineData": {"mimeType": "image/png", "data": b64_img}}
                        ]
                    }],
                    "generationConfig": {"temperature": 0.0}
                }
                try:
                    res = requests.post(url, json=payload, timeout=30)
                    if res.status_code == 200:
                        text = res.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                        clean = re.sub(r"[^a-zA-Z0-9]", "", text).lower()
                        if clean:
                            print(f"[GEMINI CAPTCHA OCR] Solved distorted text captcha via {model}: '{clean}'")
                            return clean
                except Exception as e:
                    print(f"[GEMINI CAPTCHA OCR WARN] {model} with key: {e}")

    # Fallback to local pytesseract OCR if Gemini is unreachable or rate-limited
    try:
        import pytesseract
        from PIL import Image
        pil_img = Image.open(image_path).convert("L")
        w, h = pil_img.size
        large_img = pil_img.resize((w * 3, h * 3), Image.Resampling.BICUBIC)
        for psm in [8, 13, 7]:
            ocr_text = pytesseract.image_to_string(
                large_img,
                config=f"--psm {psm} -c tessedit_char_whitelist=abcdefghijklmnopqrstuvwxyz0123456789"
            ).strip()
            clean_ocr = re.sub(r"[^a-zA-Z0-9]", "", ocr_text).lower()
            if len(clean_ocr) >= 3:
                print(f"[TESSERACT FALLBACK OCR] Solved text captcha (psm {psm}): '{clean_ocr}'")
                return clean_ocr
    except Exception as t_err:
        print(f"[TESSERACT OCR WARN] {t_err}")

    return ""


async def human_type(page, locator, text: str):
    """Simulates realistic human typing dynamics with randomized delays."""
    await locator.click()
    await page.wait_for_timeout(random.randint(250, 400))
    await page.keyboard.press("Control+A")
    await page.keyboard.press("Backspace")
    await page.wait_for_timeout(random.randint(150, 280))
    for ch in text:
        await page.keyboard.type(ch, delay=random.randint(50, 95))
        if random.random() < 0.12:
            await page.wait_for_timeout(random.randint(120, 260))
    await page.wait_for_timeout(random.randint(350, 650))


async def human_click(page, locator):
    """Simulates realistic human cursor movement and click timing."""
    box = await locator.bounding_box()
    if box:
        target_x = box["x"] + box["width"] * (0.3 + random.random() * 0.4)
        target_y = box["y"] + box["height"] * (0.3 + random.random() * 0.4)
        await page.mouse.move(target_x, target_y, steps=random.randint(8, 14))
        await page.wait_for_timeout(random.randint(180, 320))
        await page.mouse.down()
        await page.wait_for_timeout(random.randint(60, 130))
        await page.mouse.up()
    else:
        await locator.click()


def test_bearer_token(ticket: str, cookie_header: str = "") -> dict:
    """Verifies if a Bearer ticket is valid against Snapchat API."""
    url = f"{SNAPML_BASE}/api/me"
    headers = {
        "Authorization": f"Bearer {ticket}",
        "Origin": "https://easylens.snapchat.com",
        "Referer": "https://easylens.snapchat.com/",
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Mobile Safari/537.36",
        "x-snap-client-user-agent": "LensStudioWeb/2.57.0 PROD (K; android 10) Chrome/143 Core/377 AppId/easylens.snapchat.com"
    }
    if cookie_header:
        headers["Cookie"] = cookie_header
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            return res.json()
    except Exception as e:
        print(f"[VERIFY WARN] API test failed: {e}")
    return None


def mint_sso_ticket_from_cookies(cookie_header: str) -> str:
    """Fast-path: Calls accounts.snapchat.com/accounts/sso to mint fresh Bearer ticket."""
    if not cookie_header:
        return ""
    url = f"{ACCOUNTS_BASE}/accounts/sso"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
        "Origin": "https://easylens.snapchat.com",
        "Referer": "https://easylens.snapchat.com/",
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Mobile Safari/537.36",
        "Cookie": cookie_header
    }
    data = "client_id=web-ar-applier"
    try:
        print("[SSO FAST-PATH] Testing /accounts/sso with existing session cookies...")
        res = requests.post(url, headers=headers, data=data, timeout=12)
        if res.status_code == 200 and not res.text.strip().startswith("<"):
            raw = res.text.strip()
            try:
                ticket = base64.b64decode(raw).decode("utf-8").strip()
            except Exception:
                ticket = raw
            if ticket.startswith("hCgw"):
                print(f"[SSO FAST-PATH SUCCESS] Minted fresh Bearer ticket ({ticket[:16]}...)")
                return ticket
        print(f"[SSO FAST-PATH INFO] Cookie needs renewal (HTTP {res.status_code})")
    except Exception as e:
        print(f"[SSO FAST-PATH WARN] {e}")
    return ""


def update_github_secret(secret_name: str, secret_value: str):
    """Safely updates a GitHub repository secret using gh CLI if available."""
    if not secret_value:
        return
    token = os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN")
    if not token:
        print(f"[GITHUB SECRET] Skipping {secret_name} update (no GH_TOKEN in env)")
        return
    try:
        p = subprocess.run(
            ["gh", "secret", "set", secret_name, "--repo", REPO],
            input=secret_value.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True
        )
        print(f"[GITHUB SECRET] Updated {secret_name} successfully")
    except Exception as e:
        print(f"[GITHUB SECRET WARN] Failed to update {secret_name}: {e}")


try:
    from playwright_stealth import stealth_async
except ImportError:
    stealth_async = None


async def handle_google_secproxy_flow(page, gmail_addr: str, passwords: list, max_seconds: int = 150) -> bool:
    """
    Autonomous Google OAuth & SecProxy solver with multimodal Gemini Vision OCR:
    - Screen 1: Google Account chooser or Email entry (+ distorted text CAPTCHA)
    - Screen 2: Google Password entry (+ distorted text CAPTCHA retry)
    - Screen 3: OAuth Consent ("Continue", "Allow", "Yes, I agree", "#submit_approve_access")
    Returns True if redirected back to Snapchat.
    """
    print(f"\n[GOOGLE SECPROXY FLOW] Initiating Google Sign-in handler (Initial URL: {page.url[:85]})...", flush=True)
    g_pwd = passwords[0] if passwords else "DM id wale1"
    start_t = time.time()

    while time.time() - start_t < max_seconds:
        await page.wait_for_timeout(1000)
        curr_url = page.url

        # Success condition: redirected to Snapchat SSO or EasyLens
        if "accounts.snapchat.com" in curr_url or "easylens" in curr_url or "accounts/sso" in curr_url:
            print(f"[GOOGLE SECPROXY SUCCESS] Redirected back to Snapchat session URL: {curr_url[:85]}", flush=True)
            return True

        if "accounts.google.com" not in curr_url and "secproxy" not in curr_url:
            print(f"[GOOGLE SECPROXY INFO] URL transitioned off Google: {curr_url[:85]}", flush=True)
            return True

        # 1. Account chooser
        try:
            chooser = await page.query_selector(
                f"div[data-identifier*='{gmail_addr}'], div[data-email*='{gmail_addr}'], li:has-text('{gmail_addr}')"
            )
            if chooser and await chooser.is_visible():
                print("[GOOGLE SECPROXY] Selecting existing account...", flush=True)
                await chooser.click()
                await page.wait_for_timeout(2500)
                continue
        except Exception:
            pass

        # 2. Email entry
        try:
            em_inp = await page.query_selector("input#identifierId, input[name='identifier'], input[type='email']")
            if em_inp and await em_inp.is_visible():
                print(f"[GOOGLE SECPROXY] Entering email: {gmail_addr}", flush=True)
                # Check for email CAPTCHA
                em_cap = await page.query_selector("img#captchaimg, img[src*='Captcha'], img[src*='token=']")
                if em_cap and await em_cap.is_visible():
                    print("[GOOGLE SECPROXY] Detected distorted CAPTCHA on email screen!", flush=True)
                    await em_cap.screenshot(path="google_email_captcha_crop.png")
                    cap_ans = solve_google_text_captcha_with_gemini("google_email_captcha_crop.png")
                    if cap_ans:
                        cap_box = await page.query_selector("input[aria-label*='text you hear or see' i], input[placeholder*='Type the text' i], input[name='ca'], input#ca")
                        if not cap_box:
                            cap_box = await page.query_selector("xpath=//img[contains(@src, 'Captcha') or @id='captchaimg']/following::input[1]")
                        if cap_box and await cap_box.is_visible():
                            await cap_box.fill(cap_ans)
                await em_inp.fill(gmail_addr)
                await page.wait_for_timeout(300)
                next_btn = await page.query_selector("#identifierNext, button:has-text('Next')")
                if next_btn and await next_btn.is_visible():
                    await next_btn.click()
                    await page.wait_for_timeout(3500)
                    await page.screenshot(path="login_step4_google_email_submitted.png")
                continue
        except Exception as em_err:
            print(f"[GOOGLE SECPROXY WARN] Email step error: {em_err}", flush=True)

        # 3. Password entry & distorted CAPTCHA
        try:
            pwd_inp = await page.query_selector("input[type='password'], input[name='Passwd'], input[name='password']")
            if pwd_inp and await pwd_inp.is_visible():
                # Check for distorted CAPTCHA
                cap_img = await page.query_selector("img#captchaimg, img[src*='Captcha'], img[src*='token=']")
                if cap_img and await cap_img.is_visible():
                    print("[GOOGLE SECPROXY] Detected distorted CAPTCHA on password screen! Transcribing with Gemini Vision...", flush=True)
                    await cap_img.screenshot(path="google_pwd_captcha_crop.png")
                    captcha_text = solve_google_text_captcha_with_gemini("google_pwd_captcha_crop.png")
                    if captcha_text:
                        cap_box = await page.query_selector("input[aria-label*='text you hear or see' i], input[placeholder*='Type the text' i], input[name='ca'], input#ca")
                        if not cap_box:
                            cap_box = await page.query_selector("xpath=//img[contains(@src, 'Captcha') or @id='captchaimg']/following::input[1]")
                        if cap_box and await cap_box.is_visible():
                            print(f"[GOOGLE SECPROXY] Typing CAPTCHA text: '{captcha_text}'...", flush=True)
                            await cap_box.click()
                            await cap_box.fill(captcha_text)
                            await page.wait_for_timeout(300)

                # Fill password
                print(f"[GOOGLE SECPROXY] Typing password...", flush=True)
                await pwd_inp.click()
                await pwd_inp.fill(g_pwd)
                await page.wait_for_timeout(400)

                # Click password Next
                pwd_next = await page.query_selector("#passwordNext, button:has-text('Next')")
                if pwd_next and await pwd_next.is_visible():
                    print("[GOOGLE SECPROXY] Clicking password 'Next'...", flush=True)
                    await pwd_next.click()
                    await page.wait_for_timeout(4000)
                    await page.screenshot(path="login_step5_google_pwd_submitted.png")
                    continue
        except Exception as pwd_err:
            print(f"[GOOGLE SECPROXY WARN] Password step error: {pwd_err}", flush=True)

        # 4. Consent / Allow / Continue buttons
        try:
            consent_btn = await page.query_selector(
                "button:has-text('Continue'), button:has-text('Allow'), #submit_approve_access, button:has-text('Yes, I agree'), div[role='button']:has-text('Continue')"
            )
            if consent_btn and await consent_btn.is_visible():
                print("[GOOGLE SECPROXY] Submitting Google OAuth authorization 'Continue/Allow'...", flush=True)
                await consent_btn.click()
                await page.wait_for_timeout(3000)
                continue
        except Exception:
            pass

    return False


async def browser_login_flow(username: str, passwords: list, existing_cookie: str = "") -> dict:
    """
    Stealth Playwright automation flow:
    - Clean browser context (no poisoned stale session cookies)
    - Realistic Windows Chrome fingerprint + human typing & mouse dynamics
    - Gemini-powered visual puzzle solver fallback
    - Captures fresh SSO ticket & session cookies
    """
    print(f"\n=== LAUNCHING STEALTH BROWSER AUTH FLOW FOR {username} ===")
    captured_ticket = None
    captured_cookies = []

    async with async_playwright() as p:
        launch_args = [
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--disable-blink-features=AutomationControlled",
            "--disable-infobars",
            "--window-size=1920,1080"
        ]

        exec_path = os.getenv("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH")
        print(f"[BROWSER] Launching Chromium (exec_path: {exec_path or 'playwright-bundled'})...")
        launch_kwargs = {"headless": True, "args": launch_args}
        if exec_path:
            launch_kwargs["executable_path"] = exec_path

        browser = await p.chromium.launch(**launch_kwargs)
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
            locale="en-US",
            timezone_id="America/New_York"
        )

        # Inject stealth scripts
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            window.chrome = { runtime: {}, loadTimes: function() {}, csi: function() {}, app: {} };
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
        """)

        page = await context.new_page()
        if stealth_async:
            await stealth_async(page)
            print("[BROWSER] Applied playwright-stealth patches to page")

        # Capture browser console & JS errors
        page.on("console", lambda msg: print(f"[BROWSER CONSOLE {msg.type}] {msg.text}"))
        page.on("pageerror", lambda err: print(f"[BROWSER JS ERROR] {err}"))

        # Monitor all network responses for tickets, failures & sessions
        async def on_response(res):
            nonlocal captured_ticket
            url = res.url
            if res.status >= 400:
                print(f"[HTTP FAIL {res.status}] {res.request.method} {url[:110]}")
            if "accounts/sso" in url and res.status == 200:
                try:
                    text = await res.text()
                    if not text.strip().startswith("<"):
                        try:
                            dec = base64.b64decode(text.strip()).decode("utf-8").strip()
                        except Exception:
                            dec = text.strip()
                        if dec.startswith("hCgw"):
                            captured_ticket = dec
                            print(f"\n[NETWORK SNIFFER] Intercepted fresh Bearer ticket: {dec[:16]}...")
                except Exception:
                    pass

        page.on("response", on_response)

        login_start_time = time.time() - 30
        target_url = "https://accounts.snapchat.com/v2/login?continue=%2Faccounts%2Fsso%3Fclient_id%3Dweb-ar-applier"
        print(f"[NAVIGATING] {target_url}")
        await page.goto(target_url, wait_until="domcontentloaded", timeout=45000)
        await page.wait_for_timeout(3000)
        await page.screenshot(path="login_step0_initial.png")

        # Dismiss cookie banner if present
        try:
            cookie_btn = await page.query_selector("button:has-text('Accept All'), button:has-text('Accept all cookies'), button#accept-recommended-btn-handler")
            if cookie_btn and await cookie_btn.is_visible():
                await human_click(page, cookie_btn)
                await page.wait_for_timeout(500)
        except Exception:
            pass

        # Step 1: Fill Account Identifier (Username)
        login_user = "gman21478" if ("@" in username or "gurination" in username or not username) else username
        print(f"[STEP 1] Locating username field (human typing: {login_user})...")
        account_input = await page.wait_for_selector(
            "input[name='accountIdentifier'], input#accountIdentifier, input[type='text']",
            state="visible",
            timeout=15000
        )
        await human_type(page, account_input, login_user)
        await page.wait_for_timeout(300)
        curr_val = await account_input.evaluate("el => el.value")
        if curr_val != login_user:
            print(f"[STEP 1 WARN] Fill value mismatch ('{curr_val}' != '{login_user}'). Re-typing...")
            await human_type(page, account_input, login_user)
        await page.wait_for_timeout(500)
        await page.screenshot(path="login_step1_username.png")

        # Click Next
        print("[STEP 1] Clicking 'Next' button...")
        next_btn = await page.wait_for_selector(
            "button:has-text('Next'), button[type='submit']",
            state="visible",
            timeout=8000
        )
        await human_click(page, next_btn)

        # Step 2: Wait for Password input to become genuinely VISIBLE
        print("[STEP 2] Waiting for password input to become visible...")
        pwd_visible = False
        for wait_s in range(45):
            await page.wait_for_timeout(1000)
            if captured_ticket or "easylens" in page.url or "accounts/sso" in page.url:
                break
            try:
                el = await page.query_selector("input[type='password']")
                if el and await el.is_visible():
                    pwd_visible = True
                    break
            except Exception:
                pass

            # Random natural cursor motion
            if wait_s % 3 == 0:
                await page.mouse.move(random.randint(200, 800), random.randint(200, 600), steps=random.randint(5, 10))

            if "captcha" in page.url.lower():
                if wait_s % 10 == 0:
                    print(f"[STEP 2 FRAMES] {[f.url[:60] for f in page.frames]}")
                    try:
                        c_state = await page.evaluate("""() => ({
                            grecaptcha: typeof window.grecaptcha,
                            enterprise: typeof window.grecaptcha !== 'undefined' ? typeof window.grecaptcha.enterprise : 'none',
                            hcaptcha: typeof window.hcaptcha,
                            body: document.body ? document.body.innerText.replace(/\\s+/g, ' ').slice(0, 120) : ''
                        })""")
                        print(f"[CAPTCHA DIAGNOSTIC {wait_s}s] {c_state}")
                    except Exception:
                        pass

                # Check for anchor frame and click checkbox if available
                for frame in page.frames:
                    if "recaptcha" in frame.url and "anchor" in frame.url:
                        try:
                            checkbox = await frame.query_selector("#recaptcha-anchor, .recaptcha-checkbox")
                            if checkbox and await checkbox.is_visible():
                                print(f"[ANCHOR CLICK {wait_s}s] Clicking reCAPTCHA anchor checkbox...")
                                await human_click(page, checkbox)
                                await page.wait_for_timeout(2000)
                        except Exception as a_err:
                            print(f"[ANCHOR WARN] {a_err}")

                # Manually trigger grecaptcha execute if idle
                if wait_s in [5, 12, 20, 30]:
                    try:
                        trig_res = await page.evaluate("""() => {
                            let res = [];
                            if (typeof window.grecaptcha !== 'undefined') {
                                try {
                                    if (typeof window.grecaptcha.execute === 'function') {
                                        window.grecaptcha.execute();
                                        res.push('grecaptcha.execute()');
                                    }
                                } catch(e) { res.push('err:' + e.message); }
                                for (let i = 0; i < 5; i++) {
                                    try {
                                        window.grecaptcha.execute(i);
                                        res.push('widget_' + i);
                                    } catch(e) {}
                                }
                            }
                            return res.join(', ') || 'idle';
                        }""")
                        if trig_res != 'idle':
                            print(f"[CAPTCHA MANUAL TRIGGER {wait_s}s] {trig_res}")
                    except Exception:
                        pass

                # Check for bframe visual challenge
                for frame in page.frames:
                    if "bframe" in frame.url or "challenge" in frame.url:
                        print(f"[CAPTCHA PUZZLE DETECTED] Frame: {frame.url[:80]}")
                        try:
                            await frame.screenshot(path="captcha_puzzle.png")
                            instr_el = await frame.query_selector(".rc-imageselect-desc-wrapper, .rc-imageselect-instructions")
                            instr = await instr_el.inner_text() if instr_el else "Select matching tiles"
                            tiles_to_click = solve_captcha_with_gemini("captcha_puzzle.png", instr)
                            tile_els = await frame.query_selector_all(".rc-image-tile-wrapper, .rc-imageselect-tile")
                            for idx in tiles_to_click:
                                if 1 <= idx <= len(tile_els):
                                    await tile_els[idx - 1].click()
                                    await page.wait_for_timeout(random.randint(300, 600))
                            verify_btn = await frame.query_selector("#recaptcha-verify-button")
                            if verify_btn and tiles_to_click:
                                await verify_btn.click()
                                await page.wait_for_timeout(2000)
                        except Exception as puzzle_err:
                            print(f"[CAPTCHA PUZZLE WARN] {puzzle_err}")

                # If idle on security verification, click retry if available
                if wait_s in [15, 30]:
                    try:
                        retry_link = await page.query_selector("div[class*='actionButtons'] a, a:has-text('Try again'), button:has-text('Try again')")
                        if retry_link and await retry_link.is_visible():
                            print(f"[CAPTCHA RE-EXECUTE {wait_s}s] Clicking try again link...")
                            await human_click(page, retry_link)
                            await page.wait_for_timeout(1500)
                    except Exception:
                        pass

            if wait_s % 5 == 0:
                print(f"[STEP 2] Waiting for password screen ({wait_s}/45s)... URL: {page.url[:80]}")

        await page.screenshot(path="login_step2_password_screen.png")

        if not pwd_visible and not captured_ticket:
            curr_url = page.url
            print(f"[STEP 2 WARN] Password field not visible (URL: {curr_url}). Page Title: {await page.title()}")
            err_el = await page.query_selector("p[class*='error'], div[class*='error'], span[class*='error'], [data-testid*='error']")
            if err_el and await err_el.is_visible():
                print(f"[STEP 2 PAGE ERROR] {await err_el.inner_text()}")

        # Step 3: Try password candidates
        if pwd_visible and not captured_ticket:
            print(f"[STEP 3] Password field is VISIBLE. Testing {len(passwords)} password candidate(s)...")
            for attempt_idx, pwd in enumerate(passwords, 1):
                if captured_ticket:
                    break
                print(f"[STEP 3] Attempting password candidate #{attempt_idx}...")

                try:
                    pwd_el = await page.wait_for_selector("input[type='password']", state="visible", timeout=8000)
                except Exception:
                    pwd_el = None

                if not pwd_el and not captured_ticket:
                    print(f"[STEP 3 WARN] Visible password element not found for attempt #{attempt_idx}")
                    break

                if pwd_el and not captured_ticket:
                    await human_type(page, pwd_el, pwd)
                    await page.wait_for_timeout(300)
                    filled_val = await pwd_el.evaluate("el => el.value")
                    if filled_val != pwd:
                        print(f"[STEP 3 WARN] Password evaluation mismatch, re-typing...")
                        await human_type(page, pwd_el, pwd)
                    await page.wait_for_timeout(500)

                    submit_btn = await page.wait_for_selector(
                        "button:has-text('Next'), button[type='submit']:visible, button:has-text('Log In'), button:has-text('Sign In')",
                        state="visible",
                        timeout=8000
                    )
                    if submit_btn:
                        for _ in range(10):
                            if await submit_btn.is_enabled():
                                break
                            await page.wait_for_timeout(500)
                        await human_click(page, submit_btn)
                    else:
                        await page.keyboard.press("Enter")

                    # Wait for response, redirect, security verification, or error notice
                    rejected = False
                    for wait_i in range(40):
                        await page.wait_for_timeout(1000)
                        curr_url = page.url
                        if captured_ticket or "easylens" in curr_url or "accounts/sso" in curr_url:
                            print(f"[AUTH SUCCESS] Redirected to session URL: {curr_url}")
                            break

                        # Handle Snapchat TIV (Two-step Identity Verification - Email Approval)
                        if "/v2/tiv" in curr_url or "tiv" in curr_url.lower():
                            gmail_addr = os.getenv("GMAIL_ADDRESS", "gurination1@gmail.com").strip()
                            gmail_pwd = os.getenv("GMAIL_APP_PASSWORD", "").strip()
                            print("\n" + "=" * 65)
                            print("[TIV VERIFICATION DETECTED] Snapchat sent login confirmation email!")
                            print(f"Target Email: {gmail_addr}")
                            if gmail_pwd:
                                print("[AUTONOMOUS TIV] Gmail App Password detected - starting autonomous IMAP listener!")
                            else:
                                print("ACTION REQUIRED: Open your Gmail and tap 'Confirm Login' / 'Yes, this was me'.")
                            print("The browser is keeping a live session with GetTivStatus polling every 3s.")
                            print("Holding live session for up to 360 seconds (6 minutes)...")
                            print("=" * 65 + "\n")
                            await page.screenshot(path="login_step3_tiv_pending.png")

                            tiv_start_time = login_start_time
                            approved_urls = set()
                            approved_via_imap = False

                            for tiv_s in range(120):
                                await page.wait_for_timeout(1000)
                                curr_url = page.url
                                if captured_ticket or "easylens" in curr_url or "accounts/sso" in curr_url:
                                    print(f"\n[TIV APPROVED] Email approval confirmed! Redirecting to: {curr_url}")
                                    break

                                # Autonomous Gmail IMAP check every 3 seconds until approved
                                if gmail_pwd and not approved_via_imap and tiv_s % 3 == 0:
                                    tiv_link = fetch_latest_snap_tiv_url(gmail_addr, gmail_pwd, tiv_start_time)
                                    if tiv_link and tiv_link not in approved_urls:
                                        approved_urls.add(tiv_link)
                                        approved_via_imap = True
                                        print(f"\n[AUTONOMOUS TIV] Discovered Snapchat verification link in Gmail!")
                                        print(f"[AUTONOMOUS TIV] Navigating to approval landing in browser context: {tiv_link[:85]}...")
                                        approval_page = await context.new_page()
                                        try:
                                            await approval_page.goto(tiv_link, wait_until="domcontentloaded", timeout=25000)
                                            await approval_page.wait_for_timeout(2000)
                                            await approval_page.screenshot(path="login_step3_tiv_landing.png")

                                            # Try clicking the Approve button
                                            approve_btn = await approval_page.query_selector(
                                                "button:has-text('Approve'), #tiv-landing-approve-form button, .tiv-button"
                                            )
                                            if approve_btn and await approve_btn.is_visible():
                                                print("[AUTONOMOUS TIV] Clicking 'Approve' button...")
                                                await human_click(approval_page, approve_btn)
                                                await approval_page.wait_for_timeout(2000)
                                            else:
                                                print("[AUTONOMOUS TIV] Triggering form submit via JavaScript...")
                                                await approval_page.evaluate("""() => {
                                                    const f = document.getElementById('tiv-landing-approve-form');
                                                    if (f) { f.submit(); return true; }
                                                    return false;
                                                }""")
                                                await approval_page.wait_for_timeout(2000)

                                            # Also direct fetch fallback within landing page context
                                            await approval_page.evaluate("""() => {
                                                const root = document.getElementById('tiv-landing-root');
                                                if (root) {
                                                    const xsrf = root.getAttribute('data-xsrf') || '';
                                                    const nonce = root.getAttribute('data-nonce') || '';
                                                    fetch('/accounts/tiv/landing' + window.location.search, {
                                                        method: 'POST',
                                                        headers: {'Content-Type': 'application/x-www-form-urlencoded', 'X-XSRF-TOKEN': xsrf},
                                                        body: new URLSearchParams({'xsrf_token': xsrf, 'n': nonce, 's': '1'})
                                                    }).catch(() => {});
                                                }
                                            }""")
                                            await approval_page.wait_for_timeout(2000)
                                            await approval_page.screenshot(path="login_step3_tiv_approved.png")
                                            print("[AUTONOMOUS TIV] Approval dispatched successfully! Waiting for main session redirect...")
                                        except Exception as app_err:
                                            print(f"[AUTONOMOUS TIV WARN] Error submitting approval: {app_err}")
                                        finally:
                                            try:
                                                await approval_page.close()
                                            except Exception:
                                                pass

                                # Check for Google OAuth / SecProxy redirection
                                if "accounts.google.com" in curr_url or "secproxy" in curr_url:
                                    print(f"\n[GOOGLE SECPROXY] Detected Google Sign-in redirection (URL: {curr_url[:80]})! Launching solver...", flush=True)
                                    g_ok = await handle_google_secproxy_flow(page, gmail_addr, passwords, max_seconds=120)
                                    if g_ok or captured_ticket or "easylens" in page.url or "accounts/sso" in page.url:
                                        print("[TIV/GOOGLE SUCCESS] Authentication completed via Google SecProxy flow!", flush=True)
                                        break

                                if tiv_s % 15 == 0:
                                    print(f"[TIV WAITING {tiv_s}s/120s] Awaiting verification flow... URL: {curr_url[:80]}", flush=True)
                                    await page.screenshot(path="login_step3_tiv_waiting.png")

                            if not captured_ticket and ("accounts.google.com" in page.url or "secproxy" in page.url):
                                print("[TIV REDIRECT] Page transitioned to Google OAuth post-TIV, executing handler...", flush=True)
                                await handle_google_secproxy_flow(page, gmail_addr, passwords, max_seconds=90)

                            if captured_ticket or "easylens" in page.url or "accounts/sso" in page.url:
                                print("[TIV SUCCESS] Challenge approved successfully!", flush=True)
                                break
                            # Finish TIV step
                            break

                        # Handle security verification / captcha challenges
                        if "captcha" in curr_url.lower():
                            if wait_i % 5 == 0:
                                print(f"[SECURITY CHALLENGE] Security verification page active (URL: {curr_url[:90]}). Waiting for verification...")
                            # If on /v2/login with captchaChallenge, click Next if available
                            if "captchaChallenge" in curr_url:
                                try:
                                    ch_btn = await page.query_selector("button:has-text('Next'), button:has-text('Continue'), button:has-text('Verify')")
                                    if ch_btn and await ch_btn.is_visible() and await ch_btn.is_enabled():
                                        btn_text = (await ch_btn.inner_text()).strip()
                                        if any(w in btn_text.lower() for w in ["next", "continue", "verify"]) and "cancel" not in btn_text.lower():
                                            print(f"[SECURITY CHALLENGE] Submitting challenge button (text: '{btn_text}')...")
                                            await ch_btn.click()
                                            await page.wait_for_timeout(2000)
                                except Exception:
                                    pass

                            # If on /v2/captcha, wait for invisible verification to execute
                            if "/v2/captcha" in curr_url:
                                for frame in page.frames:
                                    if any(x in frame.url for x in ["hcaptcha.com", "recaptcha", "arkoselabs"]):
                                        print(f"[SECURITY CHALLENGE] Active verification frame: {frame.url[:80]}")

                        # Check for login errors
                        err = await page.query_selector("p[class*='error'], div[class*='error'], span[class*='error'], [data-testid*='error']")
                        if err and await err.is_visible():
                            err_text = await err.inner_text()
                            if any(w in err_text.lower() for w in ["incorrect", "wrong", "invalid", "try again", "reached the maximum"]):
                                print(f"[STEP 3 WARN] Password #{attempt_idx} rejected or limit hit: {err_text}")
                                rejected = True
                                break

                    await page.screenshot(path=f"login_step3_attempt_{attempt_idx}.png")

                    # Check page body in case accounts/sso returned ticket directly
                    if not captured_ticket and ("accounts/sso" in page.url or "easylens" in page.url):
                        try:
                            b_text = (await page.inner_text("body")).strip()
                            try:
                                dec_b = base64.b64decode(b_text).decode("utf-8").strip()
                            except Exception:
                                dec_b = b_text
                            if dec_b.startswith("hCgw"):
                                captured_ticket = dec_b
                                print(f"[PAGE BODY TICKET] Captured ticket directly from page text: {dec_b[:16]}...")
                        except Exception:
                            pass

                    if captured_ticket:
                        print("[STEP 3 SUCCESS] Authenticated successfully!")
                        break

                    # If captcha is still active, don't immediately fail to next password
                    if "captcha" in page.url.lower():
                        print(f"[SECURITY CHALLENGE] Still on challenge page ({page.url[:80]}), waiting extra 15s for completion...")
                        for _ in range(15):
                            await page.wait_for_timeout(1000)
                            if captured_ticket or "easylens" in page.url or "accounts/sso" in page.url:
                                print("[AUTH SUCCESS] Challenge resolved successfully!")
                                break
                        if captured_ticket:
                            break

        # Collect final cookies
        captured_cookies = await context.cookies()
        await browser.close()

        # Format cookie header
        cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in captured_cookies if "snapchat.com" in c.get("domain", "") or c.get("name", "").startswith("__Host-")])

        # If ticket was not intercepted from network event, attempt minting using fresh cookies
        if not captured_ticket and cookie_str:
            print("[POST-BROWSER SSO MINT] Attempting /accounts/sso ticket minting using captured session cookies...")
            minted = mint_sso_ticket_from_cookies(cookie_str)
            if minted:
                captured_ticket = minted
                print(f"[POST-BROWSER SSO SUCCESS] Minted ticket: {minted[:16]}...")

    return {
        "ticket": captured_ticket,
        "cookie_header": cookie_str,
        "cookies": captured_cookies
    }


def obtain_valid_snap_session(account_id: str = "1", username: str = None, password: str = None) -> dict:
    """
    Main entry point:
    Attempts fast-path minting; if expired/empty, runs full browser automation.
    Returns dict with verified 'ticket', 'cookie_header', and 'user'.
    """
    aid = str(account_id)
    token_secret = f"SNAP_SSO_TOKEN_ACC_{aid}" if aid != "1" else "SNAP_SSO_TOKEN"
    cookie_secret = f"SNAP_COOKIE_HEADER_ACC_{aid}" if aid != "1" else "SNAP_COOKIE_HEADER"
    accounts_cookie_secret = f"SNAP_ACCOUNTS_COOKIE_ACC_{aid}" if aid != "1" else "SNAP_ACCOUNTS_COOKIE"

    existing_token = os.getenv(token_secret) or (os.getenv("SNAP_SSO_TOKEN") if aid == "1" else "")
    existing_cookie = os.getenv(accounts_cookie_secret) or os.getenv(cookie_secret) or (os.getenv("SNAP_ACCOUNTS_COOKIE") if aid == "1" else "")

    # 1. Check if current SSO token is still valid
    if existing_token:
        print(f"[AUTH CHECK] Testing existing {token_secret} for Account #{aid}...")
        user = test_bearer_token(existing_token, existing_cookie)
        if user:
            print(f"[AUTH READY] Existing token is 100% valid! User: {user.get('displayName')} (@{user.get('username')})")
            return {"ticket": existing_token, "cookie_header": existing_cookie, "user": user}
        print(f"[AUTH CHECK] Existing token for Account #{aid} is expired (401).")

    # 2. Try fast-path minting using existing session cookies
    if existing_cookie:
        fresh_ticket = mint_sso_ticket_from_cookies(existing_cookie)
        if fresh_ticket:
            user = test_bearer_token(fresh_ticket, existing_cookie)
            if user:
                print(f"[AUTH READY] Fast-path refreshed token! User: {user.get('displayName')} (@{user.get('username')})")
                update_github_secret(token_secret, fresh_ticket)
                return {"ticket": fresh_ticket, "cookie_header": existing_cookie, "user": user}

    # 3. Deep-path: Autonomous browser login
    user_identifier = (
        username
        or os.getenv(f"SNAP_USERNAME_ACC_{aid}")
        or os.getenv(f"SNAP_USERNAME_{aid}")
        or (os.getenv("SNAP_USERNAME") if aid == "1" else None)
        or "gman21478"
    )
    if user_identifier in ("gurination1@gmail.com", "gurination1"):
        user_identifier = "gman21478"

    env_pass = (
        password
        or os.getenv(f"SNAP_PASSWORD_ACC_{aid}")
        or os.getenv(f"SNAP_PASSWORD_{aid}")
        or os.getenv("SNAP_PASSWORD", "")
    ).strip()

    candidates = ["DM id wale1", "fakeidwale1", "fakeidwale"]
    if env_pass and env_pass not in candidates:
        candidates.insert(0, env_pass)

    print(f"[AUTH LOGIN] Initiating browser login flow for Account #{aid} (Identifier: {user_identifier})...")
    result = asyncio.run(browser_login_flow(username=user_identifier, passwords=candidates, existing_cookie=existing_cookie))
    ticket = result.get("ticket")
    cookie_header = result.get("cookie_header")

    # If ticket wasn't captured from network, try minting with new cookies
    if not ticket and cookie_header:
        print("[AUTH RETRY] Browser login captured cookies; attempting /accounts/sso minting...")
        ticket = mint_sso_ticket_from_cookies(cookie_header)

    if ticket:
        user = test_bearer_token(ticket, cookie_header)
        if user:
            print(f"\n[AUTH COMPLETE SUCCESS] Authenticated as {user.get('displayName')} (@{user.get('username')})")
            # Update GitHub Secrets for permanent persistence across runs
            update_github_secret(token_secret, ticket)
            if cookie_header:
                update_github_secret(cookie_secret, cookie_header)
                update_github_secret(accounts_cookie_secret, cookie_header)
            return {"ticket": ticket, "cookie_header": cookie_header, "user": user}

    raise RuntimeError(f"Failed to obtain valid Snapchat authentication session for Account #{aid}!")


if __name__ == "__main__":
    session = obtain_valid_snap_session()
    print("\nSession Details:")
    print("Ticket prefix:", session["ticket"][:20])
    print("User info:", session["user"])
