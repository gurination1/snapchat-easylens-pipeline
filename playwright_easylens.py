"""
Snapchat EasyLens Browser Automation (Playwright)
Handles browser navigation, UI interaction, prompt submission, inspection of generated 3D scenes, and capture of network calls.
"""

import asyncio
import os
import json
from playwright.async_api import async_playwright

COOKIE_STORAGE = os.getenv("SNAP_COOKIES_PATH", "/root/snapchat-lens/cookies.json")
GREEK_PROMPT = (
    "Create a Greek mythology lens inspired by Tiresias and Cassius: "
    "ancient marble temple ruins with glowing ethereal oracle runes, mystic golden laurel, "
    "and interactive mythical particle effects reacting to head movements."
)


async def run_browser_automation():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            executable_path="/usr/bin/chromium",
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--window-size=1280,800"
            ]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )

        # Load session cookies if available
        if os.path.exists(COOKIE_STORAGE):
            with open(COOKIE_STORAGE, "r") as f:
                cookies = json.load(f)
                await context.add_cookies(cookies)
                print(f"[LOADED] {len(cookies)} cookies injected from {COOKIE_STORAGE}")

        page = await context.new_page()

        # Listen to relevant EasyLens network traffic
        api_logs = []

        def handle_response(res):
            url = res.url
            if any(k in url for k in ["ailc", "snapml", "publish", "conversations", "get_lens"]):
                print(f"[API TRAFFIC] {res.request.method} {res.status} {url[:90]}")
                api_logs.append({"url": url, "status": res.status, "method": res.request.method})

        page.on("response", handle_response)

        print("[NAVIGATING] Loading EasyLens Home...")
        await page.goto("https://easylens.snapchat.com", wait_until="domcontentloaded")
        await page.wait_for_timeout(5000)

        # Take initial snapshot
        await page.screenshot(path="/root/snapchat-lens/easylens_home.png")
        print("[SCREENSHOT] Saved easylens_home.png")

        # Check if prompt textarea is present
        prompt_input = await page.query_selector("textarea, input[placeholder*='prompt'], input[placeholder*='Lens'], div[contenteditable='true']")
        if prompt_input:
            print("[UI FOUND] Found prompt input field, submitting Greek mythology concept...")
            await prompt_input.fill(GREEK_PROMPT)
            await page.wait_for_timeout(1000)

            # Look for send / submit button
            send_btn = await page.query_selector("button[aria-label*='Send'], button[type='submit'], button:has-text('Generate')")
            if send_btn:
                await send_btn.click()
                print("[PROMPT SUBMITTED] Waiting for AI lens generation...")
                await page.wait_for_timeout(15000)
                await page.screenshot(path="/root/snapchat-lens/easylens_generating.png")
        else:
            print("[NOTICE] Prompt input requires authenticated session. Cookies required.")

        # Save cookies
        current_cookies = await context.cookies()
        with open("/root/snapchat-lens/session_cookies_dump.json", "w") as f:
            json.dump(current_cookies, f, indent=2)
        print(f"[SAVED] Saved {len(current_cookies)} cookies to session_cookies_dump.json")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(run_browser_automation())
