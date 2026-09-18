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


async def browser_login_flow(username: str, passwords: list) -> dict:
    """Executes stealth Playwright browser login and captures fresh cookies + ticket."""
    print(f"\n=== LAUNCHING STEALTH BROWSER AUTH FLOW FOR {username} ===")
    captured_ticket = ""
    captured_cookies = []

    async with async_playwright() as p:
        # Launch Chromium with stealth flags
        launch_args = [
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-blink-features=AutomationControlled",
            "--disable-infobars",
            "--window-size=1280,800"
        ]

        # Use system chromium if available (Linux / Docker / CI)
        exec_path = None
        for candidate in ["/usr/bin/chromium-browser", "/usr/bin/chromium", "/usr/bin/google-chrome"]:
            if os.path.exists(candidate):
                exec_path = candidate
                break

        print(f"[BROWSER] Launching Chromium (exec_path: {exec_path or 'playwright-bundled'})...")
        launch_kwargs = {"headless": True, "args": launch_args}
        if exec_path:
            launch_kwargs["executable_path"] = exec_path

        browser = await p.chromium.launch(**launch_kwargs)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        )

        # Inject stealth scripts to mask automation signatures
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {}, loadTimes: function() {}, csi: function() {}, app: {} };
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
        """)

        page = await context.new_page()

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
        await page.goto(target_url, wait_until="networkidle", timeout=30000)
        await page.screenshot(path="login_step0_initial.png")

        # Step 1: Fill Account Identifier (Email / Username)
        print("[STEP 1] Locating username / email field...")
        account_input = await page.wait_for_selector(
            "input[name='accountIdentifier'], input#accountIdentifier, input[type='text']",
            timeout=15000
        )
        if not account_input:
            raise RuntimeError("Could not find account identifier input field!")

        await account_input.click()
        await account_input.fill("")
        await page.keyboard.type(username, delay=60)
        await account_input.dispatch_event("input")
        await account_input.dispatch_event("change")
        await page.wait_for_timeout(500)
        await page.screenshot(path="login_step1_username.png")

        # Click Next
        print("[STEP 1] Clicking 'Next' button...")
        next_btn = await page.query_selector("button[type='submit'], button:has-text('Next')")
        if next_btn:
            await next_btn.click()
        else:
            await page.keyboard.press("Enter")

        # Step 2: Wait for Password field or Challenge
        print("[STEP 2] Waiting for password input field...")
        password_input = None
        for _ in range(25):
            await page.wait_for_timeout(1000)
            password_input = await page.query_selector("input[type='password'], input[name='password']")
            if password_input:
                break

        await page.screenshot(path="login_step2_password_screen.png")

        if not password_input:
            print("[STEP 2 WARN] Password field not immediately visible. Checking page title & text...")
            print("Current URL:", page.url)
            print("Page Title:", await page.title())

        # Try password candidates
        if password_input:
            for attempt_idx, pwd in enumerate(passwords, 1):
                print(f"[STEP 2] Attempting password #{attempt_idx}...")
                await password_input.click()
                await password_input.fill("")
                await page.keyboard.type(pwd, delay=60)
                await password_input.dispatch_event("input")
                await password_input.dispatch_event("change")
                await page.wait_for_timeout(500)

                submit_btn = await page.query_selector("button[type='submit'], button:has-text('Log In'), button:has-text('Sign In')")
                if submit_btn:
                    await submit_btn.click()
                else:
                    await page.keyboard.press("Enter")

                # Wait for response or navigation
                for wait_i in range(12):
                    await page.wait_for_timeout(1000)
                    if captured_ticket or "easylens" in page.url or "accounts/sso" in page.url:
                        break
                    # Check for incorrect password error message
                    err = await page.query_selector("p[class*='error'], div[class*='error'], span[class*='error']")
                    if err:
                        err_text = await err.inner_text()
                        if "incorrect" in err_text.lower() or "wrong" in err_text.lower():
                            print(f"[STEP 2 WARN] Password #{attempt_idx} rejected: {err_text}")
                            break

                await page.screenshot(path=f"login_step3_attempt_{attempt_idx}.png")
                if captured_ticket:
                    print("[STEP 2 SUCCESS] Authenticated successfully!")
                    break

        # Collect final cookies
        captured_cookies = await context.cookies()
        await browser.close()

    # Format cookie header
    cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in captured_cookies if "snapchat.com" in c.get("domain", "")])

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
    username = os.getenv("SNAP_USERNAME", "gurination1@gmail.com")
    # List password candidates: primary (fakeidwale1) and literal fallback (DM id wale1)
    env_pass = os.getenv("SNAP_PASSWORD", "")
    passwords = [p for p in [env_pass, "fakeidwale1", "DM id wale1", "fakeidwale"] if p]

    result = asyncio.run(browser_login_flow(username=username, passwords=passwords))
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
