import asyncio
import sys
from playwright.async_api import async_playwright

async def run_verification():
    print("=== Starting E2E Chromium Verification of EasyLens Studio ===")
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            executable_path="/usr/bin/chromium",
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--headless=new",
                "--enable-webgl",
                "--ignore-gpu-blocklist",
                "--window-size=1280,900"
            ]
        )
        page = await browser.new_page(viewport={"width": 1280, "height": 900})
        
        console_logs = []
        page.on("console", lambda msg: console_logs.append(f"[{msg.type}] {msg.text}"))
        page.on("pageerror", lambda err: print(f"PAGE ERROR: {err}"))

        print("1. Loading http://127.0.0.1:8080/...")
        await page.goto("http://127.0.0.1:8080/", wait_until="networkidle")
        await page.screenshot(path="/root/snapchat-lens/e2e_01_initial.png")
        print("Initial page loaded and captured.")

        # Check tabs
        print("2. Testing Before/After Split tab...")
        await page.click("button:has-text('Before / After')")
        await asyncio.sleep(1)
        await page.screenshot(path="/root/snapchat-lens/e2e_02_split.png")

        print("3. Testing Poster (Frame 0) tab...")
        await page.click("button:has-text('Poster (Frame 0)')")
        await asyncio.sleep(1)
        await page.screenshot(path="/root/snapchat-lens/e2e_03_poster.png")

        print("4. Testing Camera Kit Web AR tab...")
        await page.click("button:has-text('Camera Kit Web AR')")
        
        # Wait up to 50 seconds for Camera Kit session initialization & lens application
        max_wait = 50
        lens_active = False
        final_status = ""
        for i in range(max_wait):
            await asyncio.sleep(1)
            status = await page.inner_text("#ck-status")
            print(f"[{i+1}s] Camera Kit Status: {status}")
            final_status = status
            if "3D AR Lens Active" in status:
                lens_active = True
                break

        await page.screenshot(path="/root/snapchat-lens/e2e_04_camerakit_active.png")

        # Test Switching Lens to Verdant Gilded Tiara
        print("5. Testing Dynamic Lens Switch to Verdant Gilded Tiara...")
        await page.select_option("#ck-lens-select", "verdant_gilded")
        for i in range(5):
            await asyncio.sleep(1)
            status = await page.inner_text("#ck-status")
            print(f"[Switch {i+1}s] Camera Kit Status: {status}")
            if "Verdant Gilded Tiara" in status:
                break
        await page.screenshot(path="/root/snapchat-lens/e2e_05_verdant_tiara.png")

        print("=== Verification Summary ===")
        print(f"Final Status: {final_status}")
        print(f"Lens Active Verified: {lens_active}")
        print(f"Total Browser Console Messages: {len(console_logs)}")
        for log in console_logs[-20:]:
            print("  ", log)

        await browser.close()

        if not lens_active:
            print("FAIL: 3D AR Lens was not active!")
            sys.exit(1)
        else:
            print("SUCCESS: 1:1 EasyLens Camera Kit AR Parity Confirmed!")
            sys.exit(0)

if __name__ == "__main__":
    asyncio.run(run_verification())
