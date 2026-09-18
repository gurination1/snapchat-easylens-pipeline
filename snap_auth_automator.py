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
import base64
import asyncio
import subprocess
import requests
from playwright.async_api import async_playwright

SNAPML_BASE = "https://gcp.api.snapchat.com/lens-studio-web-snapml"
ACCOUNTS_BASE = "https://accounts.snapchat.com"
REPO = "gurination1/snapchat-easylens-pipeline"


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
            # Response may be base64-encoded or raw text
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


async def browser_login_flow(username: str, passwords: list, existing_cookie: str = "") -> dict:
    """
    Stealth Playwright automation flow:
    1. Seeds existing cookies if present to test direct session resumption
    2. Navigates to accounts.snapchat.com/v2/login?continue=/accounts/sso
    3. Types username/email and clicks Next (with visibility check)
    4. Waits for password field to become genuinely visible (not hidden in DOM)
    5. Enters password candidates (DM id wale1 priority)
    6. Network listener captures minted Bearer ticket (hCgw...) and updated session cookies
    """
    print(f"\n=== LAUNCHING STEALTH BROWSER AUTH FLOW FOR {username} ===")
    captured_ticket = None
    captured_cookies = []

    async with async_playwright() as p:
        # Launch Chromium with robust CI & stealth flags
        launch_args = [
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--disable-blink-features=AutomationControlled",
            "--disable-infobars",
            "--window-size=1280,800"
        ]

        # Prefer Playwright bundled Chromium; only use external exec_path if explicitly set
        exec_path = os.getenv("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH")
        print(f"[BROWSER] Launching Chromium (exec_path: {exec_path or 'playwright-bundled'})...")
        launch_kwargs = {"headless": True, "args": launch_args}
        if exec_path:
            launch_kwargs["executable_path"] = exec_path

        browser = await p.chromium.launch(**launch_kwargs)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            locale="en-US",
            timezone_id="America/New_York"
        )

        # Seed existing non-session cookies into browser context if available
        if existing_cookie:
            try:
                cookie_objs = []
                for part in existing_cookie.split(";"):
                    if "=" in part:
                        k, v = part.strip().split("=", 1)
                        k = k.strip()
                        v = v.strip()
                        # Do NOT seed expired session auth tokens into browser!
                        if any(s in k.lower() for s in ["sc-a-session", "sc-sub-session", "session"]):
                            continue
                        if k.startswith("__Host-"):
                            cookie_objs.append({
                                "name": k,
                                "value": v,
                                "url": "https://accounts.snapchat.com",
                                "secure": True
                            })
                        else:
                            cookie_objs.append({
                                "name": k,
                                "value": v,
                                "domain": ".snapchat.com",
                                "path": "/"
                            })
                if cookie_objs:
                    await context.add_cookies(cookie_objs)
                    print(f"[BROWSER] Pre-seeded {len(cookie_objs)} non-session cookies into browser context")
            except Exception as e:
                print(f"[BROWSER WARN] Could not seed cookies: {e}")

        # Inject stealth scripts
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
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

        # Monitor all network responses for tickets & sessions
        async def on_response(res):
            nonlocal captured_ticket
            url = res.url
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

        target_url = "https://accounts.snapchat.com/v2/login?continue=%2Faccounts%2Fsso%3Fclient_id%3Dweb-ar-applier"
        print(f"[NAVIGATING] {target_url}")
        await page.goto(target_url, wait_until="domcontentloaded", timeout=45000)
        await page.wait_for_timeout(3000)
        await page.screenshot(path="login_step0_initial.png")

        # Check if pre-seeded cookies immediately authorized session
        if captured_ticket or "easylens" in page.url:
            print("[AUTH SUCCESS] Existing session cookies automatically authenticated!")
            captured_cookies = await context.cookies()
            await browser.close()
            cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in captured_cookies if "snapchat.com" in c.get("domain", "") or c.get("name", "").startswith("__Host-")])
            return {"ticket": captured_ticket, "cookie_header": cookie_str, "cookies": captured_cookies}

        # Dismiss cookie banner if present
        try:
            cookie_btn = await page.query_selector("button:has-text('Accept All'), button:has-text('Accept all cookies'), button#accept-recommended-btn-handler")
            if cookie_btn and await cookie_btn.is_visible():
                await cookie_btn.click()
                await page.wait_for_timeout(500)
        except Exception:
            pass

        # Step 1: Fill Account Identifier (Username)
        login_user = "gman21478" if ("@" in username or "gurination" in username or not username) else username
        print(f"[STEP 1] Locating username / email field (attempting: {login_user})...")
        account_input = await page.wait_for_selector(
            "input[name='accountIdentifier'], input#accountIdentifier, input[type='text']",
            state="visible",
            timeout=15000
        )
        await account_input.click()
        await account_input.fill(login_user)
        await page.wait_for_timeout(300)
        curr_val = await account_input.evaluate("el => el.value")
        if curr_val != login_user:
            print(f"[STEP 1 WARN] Fill value mismatch ('{curr_val}' != '{login_user}'). Typing via keyboard...")
            await account_input.click()
            await page.keyboard.press("Control+A")
            await page.keyboard.press("Backspace")
            await page.keyboard.type(login_user, delay=50)
        await page.wait_for_timeout(500)
        await page.screenshot(path="login_step1_username.png")

        # Click Next
        print("[STEP 1] Clicking 'Next' button...")
        next_btn = await page.wait_for_selector(
            "button:has-text('Next'), button[type='submit']",
            state="visible",
            timeout=8000
        )
        await next_btn.click()

        # Step 2: Wait for Password input to become genuinely VISIBLE
        print("[STEP 2] Waiting for password input to become visible...")
        pwd_visible = False
        for wait_s in range(30):
            await page.wait_for_timeout(1000)
            if captured_ticket or "easylens" in page.url:
                break
            try:
                el = await page.query_selector("input[type='password']")
                if el and await el.is_visible():
                    pwd_visible = True
                    break
            except Exception:
                pass
            if wait_s % 5 == 0:
                print(f"[STEP 2] Waiting for password screen ({wait_s}/30s)... URL: {page.url[:80]}")

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
                    await pwd_el.click()
                    await pwd_el.fill(pwd)
                    await page.wait_for_timeout(300)
                    filled_val = await pwd_el.evaluate("el => el.value")
                    if filled_val != pwd:
                        print(f"[STEP 3 WARN] Fill value mismatch ('{filled_val}' != '{pwd}'), re-typing...")
                        await pwd_el.click()
                        await page.keyboard.press("Control+A")
                        await page.keyboard.press("Backspace")
                        await page.keyboard.type(pwd, delay=50)
                    await page.wait_for_timeout(500)

                    submit_btn = await page.wait_for_selector(
                        "button:has-text('Next'), button[type='submit']:visible, button:has-text('Log In'), button:has-text('Sign In'), button:has-text('Log in')",
                        state="visible",
                        timeout=8000
                    )
                    if submit_btn:
                        for _ in range(10):
                            if await submit_btn.is_enabled():
                                break
                            await page.wait_for_timeout(500)
                        await submit_btn.click()
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

    return {
        "ticket": captured_ticket,
        "cookie_header": cookie_str,
        "cookies": captured_cookies
    }


def obtain_valid_snap_session() -> dict:
    """
    Main entry point:
    Attempts fast-path minting; if expired/empty, runs full browser automation.
    Returns dict with verified 'ticket', 'cookie_header', and 'user'.
    """
    existing_cookie = os.getenv("SNAP_ACCOUNTS_COOKIE") or os.getenv("SNAP_COOKIE_HEADER", "")
    existing_token = os.getenv("SNAP_SSO_TOKEN", "")

    # 1. Check if current SSO token is still valid
    if existing_token:
        print("[AUTH CHECK] Testing existing SNAP_SSO_TOKEN...")
        user = test_bearer_token(existing_token, existing_cookie)
        if user:
            print(f"[AUTH READY] Existing token is 100% valid! User: {user.get('displayName')} (@{user.get('username')})")
            return {"ticket": existing_token, "cookie_header": existing_cookie, "user": user}
        print("[AUTH CHECK] Existing SNAP_SSO_TOKEN is expired (401).")

    # 2. Try fast-path minting using existing session cookies
    if existing_cookie:
        fresh_ticket = mint_sso_ticket_from_cookies(existing_cookie)
        if fresh_ticket:
            user = test_bearer_token(fresh_ticket, existing_cookie)
            if user:
                print(f"[AUTH READY] Fast-path refreshed token! User: {user.get('displayName')} (@{user.get('username')})")
                update_github_secret("SNAP_SSO_TOKEN", fresh_ticket)
                return {"ticket": fresh_ticket, "cookie_header": existing_cookie, "user": user}

    # 3. Deep-path: Autonomous browser login
    username = os.getenv("SNAP_USERNAME", "gman21478")
    if "@" in username or "gurination" in username:
        username = "gman21478"

    env_pass = os.getenv("SNAP_PASSWORD", "").strip()
    candidates = [
        "DM id wale1",
    ]
    if env_pass and env_pass not in candidates:
        candidates.append(env_pass)

    result = asyncio.run(browser_login_flow(username=username, passwords=candidates, existing_cookie=existing_cookie))
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
            update_github_secret("SNAP_SSO_TOKEN", ticket)
            if cookie_header:
                update_github_secret("SNAP_COOKIE_HEADER", cookie_header)
                update_github_secret("SNAP_ACCOUNTS_COOKIE", cookie_header)
            return {"ticket": ticket, "cookie_header": cookie_header, "user": user}

    raise RuntimeError("Failed to obtain valid Snapchat authentication session!")


if __name__ == "__main__":
    session = obtain_valid_snap_session()
    print("\nSession Details:")
    print("Ticket prefix:", session["ticket"][:20])
    print("User info:", session["user"])
