#!/usr/bin/env python3
"""
Snapchat Autonomous Monetization & Payout Approver
Automates:
1. Session authentication for target account(s)
2. Loading My Lenses (https://my-lenses.snapchat.com)
3. Executing GraphQL SetTosLatestAcceptedVersion for:
   - LENS_CREATOR_PAYOUT_TOS (Lens Creator Rewards / Payout Terms)
   - ILDG_TOS (Interactive Lens Developer Guidelines)
4. Dismissing / Accepting on-screen Terms Modals & Payout Banners
5. Verifying acceptance status via GetTos query
"""

import os
import sys
import json
import time
import asyncio
import argparse
import requests
from playwright.async_api import async_playwright

try:
    from playwright_stealth import stealth_async
except ImportError:
    stealth_async = None

from snap_auth_automator import (
    obtain_valid_snap_session,
    human_type,
    human_click,
    get_gemini_api_keys
)

GQL_SET_TOS = """
mutation SetTosLatestAcceptedVersion($key: TosKey!) {
    setTosLatestAcceptedVersion(input: { key: $key }) {
        tos {
            key
            acceptedVersion
        }
    }
}
"""

GQL_GET_TOS = """
query GetTos($key: TosKey!) {
    getTos(input: { key: $key }) {
        tos {
            key
            acceptedVersion
            metadata {
                latestVersion
            }
        }
    }
}
"""


def sanitize_cookies_for_playwright(cookie_str: str) -> list:
    """
    Parses raw cookie strings (from headers or DevTools) into valid Playwright cookie objects.
    Filters out reserved attributes (Path, Domain, Expires, SameSite, Secure, HttpOnly, etc.)
    and injects cookies safely without triggering CDP protocol errors.
    """
    if not cookie_str:
        return []

    reserved = {"path", "domain", "expires", "max-age", "samesite", "secure", "httponly", "priority"}
    cookie_list = []
    seen = set()

    for line in cookie_str.splitlines():
        parts = []
        for p in line.split(";"):
            p = p.strip()
            if not p:
                continue
            if "," in p:
                subparts = p.split(",")
                for sp in subparts:
                    sp = sp.strip()
                    if "=" in sp:
                        parts.append(sp)
            else:
                if "=" in p:
                    parts.append(p)

        for part in parts:
            if "=" not in part:
                continue
            name, val = part.split("=", 1)
            name = name.strip()
            val = val.strip()

            if not name or name.lower() in reserved or name in seen:
                continue

            if any(bad in name for bad in [" ", "\t", ";", ",", "\n", "\r"]):
                continue

            seen.add(name)
            cookie_list.append({
                "name": name,
                "value": val,
                "domain": ".snapchat.com",
                "path": "/"
            })

    return cookie_list


async def _run_browser_approval(aid: str, user: dict, cookie_str: str, ticket: str, exec_path: str, target_lens_id: str = None, target_lens_url: str = None) -> dict:
    results = {
        "account_id": aid,
        "username": user.get("username"),
        "displayName": user.get("displayName"),
        "LENS_CREATOR_PAYOUT_TOS": False,
        "ILDG_TOS": False,
        "ui_modals_accepted": 0,
        "enrolled_lenses_count": 0,
        "top_performer_toggled": False,
        "errors": []
    }

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path=exec_path,
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-blink-features=AutomationControlled",
                "--window-size=1920,1080"
            ]
        )

        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
            locale="en-US",
            extra_http_headers={"Cookie": cookie_str} if cookie_str else {}
        )

        # Parse and inject cookies into browser context safely
        if cookie_str:
            cookie_list = sanitize_cookies_for_playwright(cookie_str)
            injected_count = 0
            for c in cookie_list:
                try:
                    await context.add_cookies([c])
                    injected_count += 1
                except Exception:
                    pass
            print(f"[COOKIES] Injected {injected_count}/{len(cookie_list)} authenticated cookies into browser context")

        page = await context.new_page()
        if stealth_async:
            await stealth_async(page)

        # Navigate to My Lenses
        target_url = "https://my-lenses.snapchat.com/"
        print(f"[NAV] Loading My Lenses portal: {target_url}...")
        try:
            await page.goto(target_url, wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_timeout(5000)
        except Exception as e:
            print(f"[NAV WARN] Initial load: {e}")

        # Check if redirected to login; if so, attempt automated browser login
        if "accounts.snapchat.com/v2/login" in page.url or "login" in page.url:
            print("[AUTH NOTICE] Page redirected to login screen. Attempting automated login flow...")
            try:
                login_user = user.get("username") or os.getenv(f"SNAP_USERNAME_ACC_{aid}") or os.getenv("SNAP_USERNAME") or "gman21478"
                if str(aid) == "1" and ("@" in login_user or "gurination1" in login_user or not login_user):
                    login_user = "gman21478"

                account_input = await page.wait_for_selector(
                    "input[name='accountIdentifier'], input#accountIdentifier, input[type='text']",
                    state="visible",
                    timeout=8000
                )
                if account_input:
                    print(f"[AUTH LOGIN] Filling username: {login_user}...")
                    await human_type(page, account_input, login_user)
                    await page.wait_for_timeout(400)
                    next_btn = await page.query_selector("button:has-text('Next'), button[type='submit']")
                    if next_btn:
                        await human_click(page, next_btn)
                        await page.wait_for_timeout(3000)

                # Wait for password input
                pwd_input = await page.wait_for_selector("input[type='password']", state="visible", timeout=12000)
                if pwd_input:
                    env_pwd = os.getenv(f"SNAP_PASSWORD_ACC_{aid}") or os.getenv("SNAP_PASSWORD") or "DM id wale1"
                    print("[AUTH LOGIN] Filling password...")
                    await human_type(page, pwd_input, env_pwd)
                    await page.wait_for_timeout(400)
                    login_btn = await page.query_selector("button:has-text('Log In'), button:has-text('Next'), button[type='submit']")
                    if login_btn:
                        await human_click(page, login_btn)
                        await page.wait_for_timeout(6000)

                # Wait for navigation back to my-lenses
                if "login" in page.url:
                    await page.wait_for_timeout(5000)
                if "my-lenses.snapchat.com" not in page.url:
                    await page.goto("https://my-lenses.snapchat.com/", wait_until="domcontentloaded", timeout=45000)
                    await page.wait_for_timeout(4000)
            except Exception as login_err:
                print(f"[AUTH LOGIN WARN] In-browser login attempt error: {login_err}")

        # Screenshot for audit
        await page.screenshot(path=f"my_lenses_acc_{aid}_loaded.png")
        print(f"[PORTAL LOADED] Current URL: {page.url[:80]} | Title: '{await page.title()}'")

        # 3. Check for and accept any on-screen TOS modal / Banner
        modals_accepted = 0
        tos_btn_selectors = [
            "button:has-text('Accept')",
            "button:has-text('I Agree')",
            "button:has-text('Agree & Continue')",
            "button:has-text('Agree')",
            "button:has-text('View Terms')",
            "[data-testid*='tos-accept']",
            "[data-testid*='accept-terms']",
            "button[class*='TosModal']",
            "button:has-text('Accept All')"
        ]
        for sel in tos_btn_selectors:
            try:
                btns = await page.query_selector_all(sel)
                for btn in btns:
                    if await btn.is_visible() and await btn.is_enabled():
                        txt = (await btn.inner_text()).strip()
                        if not any(w in txt.lower() for w in ["cancel", "dismiss", "decline", "close"]):
                            print(f"[UI MODAL] Clicking on-screen terms button: '{txt}'...")
                            await human_click(page, btn)
                            await page.wait_for_timeout(2000)
                            modals_accepted += 1
            except Exception:
                pass
        results["ui_modals_accepted"] = modals_accepted

        # 4. Programmatic GraphQL Mutation execution directly in browser context
        print("[GRAPHQL MUTATION] Dispatching SetTosLatestAcceptedVersion for LENS_CREATOR_PAYOUT_TOS & ILDG_TOS...")
        gql_script = """
        async () => {
            const keys = ["LENS_CREATOR_PAYOUT_TOS", "ILDG_TOS"];
            const out = {};
            for (const key of keys) {
                try {
                    const res = await fetch("/graphql", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            operationName: "SetTosLatestAcceptedVersion",
                            query: `
                                mutation SetTosLatestAcceptedVersion($key: TosKey!) {
                                    setTosLatestAcceptedVersion(input: { key: $key }) {
                                        tos {
                                            key
                                            acceptedVersion
                                        }
                                    }
                                }
                            `,
                            variables: { key: key }
                        })
                    });
                    const data = await res.json();
                    out[key] = data;
                } catch (err) {
                    out[key] = { error: err.message };
                }
            }
            return out;
        }
        """
        try:
            gql_result = await page.evaluate(gql_script)
            print(f"[GRAPHQL RESPONSE] {json.dumps(gql_result)}")

            for k in ["LENS_CREATOR_PAYOUT_TOS", "ILDG_TOS"]:
                resp = gql_result.get(k, {})
                if resp.get("data", {}).get("setTosLatestAcceptedVersion", {}).get("tos", {}).get("acceptedVersion") is not None:
                    results[k] = True
                    print(f"  ✓ {k}: ACCEPTED (Version: {resp['data']['setTosLatestAcceptedVersion']['tos']['acceptedVersion']})")
                elif "errors" in resp:
                    print(f"  ! {k} response: {resp.get('errors')}")
                    # Even if error (e.g. already accepted), mark true if message indicates already accepted
                    err_msg = str(resp.get("errors", ""))
                    if "already" in err_msg.lower() or "not modified" in err_msg.lower():
                        results[k] = True
                        print(f"  ✓ {k}: ALREADY ACCEPTED")
        except Exception as ge:
            print(f"[GRAPHQL EVAL WARN] {ge}")
            results["errors"].append(str(ge))

        # 5. Query verification
        verify_script = """
        async () => {
            const keys = ["LENS_CREATOR_PAYOUT_TOS", "ILDG_TOS"];
            const out = {};
            for (const key of keys) {
                try {
                    const res = await fetch("/graphql", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            operationName: "GetTos",
                            query: `
                                query GetTos($key: TosKey!) {
                                    getTos(input: { key: $key }) {
                                        tos {
                                            key
                                            acceptedVersion
                                            metadata {
                                                latestVersion
                                            }
                                        }
                                    }
                                }
                            `,
                            variables: { key: key }
                        })
                    });
                    const data = await res.json();
                    out[key] = data;
                } catch (err) {
                    out[key] = { error: err.message };
                }
            }
            return out;
        }
        """
        try:
            verify_res = await page.evaluate(verify_script)
            print(f"[VERIFICATION QUERY] {json.dumps(verify_res)}")
            for k in ["LENS_CREATOR_PAYOUT_TOS", "ILDG_TOS"]:
                t_data = verify_res.get(k, {}).get("data", {}).get("getTos", {}).get("tos", {})
                acc_ver = t_data.get("acceptedVersion")
                latest_ver = (t_data.get("metadata") or {}).get("latestVersion")
                if acc_ver and latest_ver and acc_ver >= latest_ver:
                    results[k] = True
                    print(f"  ✓ {k} VERIFIED: acceptedVersion={acc_ver} (latestVersion={latest_ver})")
        except Exception as ve:
            print(f"[VERIFY WARN] {ve}")

        # 6. Automatic Enrollment of published lenses into Lens Creator Rewards / Lens+ Payouts
        enroll_script = """
        async (specificLensId) => {
            const out = { enrolled_count: 0, lenses: [] };
            const targetIds = new Set();
            if (specificLensId) targetIds.add(specificLensId);

            // Fetch lenses from GraphQL using valid enum types
            for (const gType of ["COMMUNITY", "PROFILE"]) {
                try {
                    const res = await fetch("/graphql", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            operationName: "getLensesList",
                            query: `
                                query getLensesList($limit: Int!, $offset: Int!, $sortBy: SortBy!, $sortDirection: MyLensesSortDirection!, $type: GetLensesType!) {
                                    lenses: getMyLensesLenses(input: { limit: $limit, offset: $offset, sortBy: $sortBy, sortDirection: $sortDirection, type: $type }) {
                                        lensesList {
                                            id
                                            name
                                            lensCreatorPayoutEligibility
                                            exclusiveLensStatus
                                        }
                                    }
                                }
                            `,
                            variables: {
                                limit: 50,
                                offset: 0,
                                sortBy: "SORT_BY_DATE",
                                sortDirection: "SORT_DIRECTION_DESC",
                                type: gType
                            }
                        })
                    });
                    const data = await res.json();
                    const list = data?.data?.lenses?.lensesList || [];
                    for (const l of list) {
                        if (l && l.id) targetIds.add(l.id);
                    }
                } catch (err) {
                    out["fetch_error_" + gType] = err.message;
                }
            }

            for (const lid of targetIds) {
                try {
                    // 1. setLensCreatorPayoutEnrollment
                    const r1 = await fetch("/graphql", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            operationName: "setLensCreatorPayoutEnrollment",
                            query: `
                                mutation setLensCreatorPayoutEnrollment($lensId: ID!, $lensCreatorPayoutEnrolled: Boolean!) {
                                    setLensCreatorPayoutEnrollment(input: { lensId: $lensId, lensCreatorPayoutEnrolled: $lensCreatorPayoutEnrolled }) {
                                        lens {
                                            id
                                            lensCreatorPayoutEligibility
                                            status
                                        }
                                    }
                                }
                            `,
                            variables: { lensId: lid, lensCreatorPayoutEnrolled: true }
                        })
                    });
                    const d1 = await r1.json();

                    // 2. updateLens (creatorRewardProgramEnrolled: true)
                    const r2 = await fetch("/graphql", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            operationName: "updateLens",
                            query: `
                                mutation updateLens($lensId: ID!, $creatorRewardProgramEnrolled: Boolean!, $isGameUserProvided: Boolean!) {
                                    updateLens(input: { lensId: $lensId, creatorRewardProgramEnrolled: $creatorRewardProgramEnrolled, isGameUserProvided: $isGameUserProvided }) {
                                        lens {
                                            id
                                            lensCreatorPayoutEligibility
                                            status
                                        }
                                    }
                                }
                            `,
                            variables: { lensId: lid, creatorRewardProgramEnrolled: true, isGameUserProvided: false }
                        })
                    });
                    const d2 = await r2.json();

                    out.enrolled_count++;
                    out.lenses.push({ id: lid, setPayoutRes: d1, updateLensRes: d2 });
                } catch (err) {
                    out.lenses.push({ id: lid, error: err.message });
                }
            }
            return out;
        }
        """
        try:
            enroll_res = await page.evaluate(enroll_script, target_lens_id)
            print(f"[LENS ENROLLMENT] Payout & Top Performer enrollment processed for {enroll_res.get('enrolled_count', 0)} lenses: {json.dumps(enroll_res)}")
            results["enrolled_lenses_count"] = enroll_res.get("enrolled_count", 0)
        except Exception as ee:
            print(f"[LENS ENROLLMENT WARN] {ee}")

        # 7. Direct UI Navigation to target lens page to ensure toggle-lens-creator-payout-enrolled is verified & toggled
        nav_target = target_lens_url or (f"https://my-lenses.snapchat.com/lens/{target_lens_id}" if target_lens_id else None)
        if nav_target:
            print(f"[NAV LENS] Navigating directly to target lens page: {nav_target}...")
            try:
                await page.goto(nav_target, wait_until="domcontentloaded", timeout=45000)
                await page.wait_for_timeout(6000)

                # Look for Top Performer Payouts switch or green checkmark
                switches = await page.query_selector_all("#toggle-lens-creator-payout-enrolled, [id*='creator-payout'], .sds-switch, [role='switch']")
                switch_toggled = False
                for sw in switches:
                    is_checked = (
                        await sw.get_attribute("aria-checked") == "true"
                        or "checked" in (await sw.get_attribute("class") or "").lower()
                    )
                    if not is_checked:
                        print("[TOGGLE] Found unchecked Top Performer Payouts switch. Clicking switch...")
                        await human_click(page, sw)
                        await page.wait_for_timeout(2000)
                        switch_toggled = True
                        results["top_performer_toggled"] = True
                        break
                    else:
                        print("[TOGGLE] Top Performer Payouts switch is ALREADY CHECKED!")
                        results["top_performer_toggled"] = True

                # Check if TOS acceptance modal popped up after toggle
                tos_modal_btn = await page.query_selector("[data-testid='tos-modal'] button:has-text('Accept'), [data-testid='tos-modal'] button:has-text('I Agree'), button:has-text('Accept'), button:has-text('I Agree')")
                if tos_modal_btn and await tos_modal_btn.is_visible() and await tos_modal_btn.is_enabled():
                    print("[TOS MODAL] Clicking on-screen TOS acceptance button...")
                    await human_click(page, tos_modal_btn)
                    await page.wait_for_timeout(2000)

                # Click header Save Changes button
                save_btn = await page.query_selector("button[data-testid='save-changes-button'], button:has-text('Save Changes'), button:has-text('Save'), button:has-text('Update')")
                if save_btn and await save_btn.is_visible() and await save_btn.is_enabled():
                    print("[SAVE] Clicking Save Changes button...")
                    await human_click(page, save_btn)
                    await page.wait_for_timeout(2000)

                    # Click confirmation inside SaveChangesModal if present
                    confirm_btn = await page.query_selector("[data-testid='save-changes-modal'] button:has-text('Save Changes'), .sds-modal button:has-text('Save Changes'), [role='dialog'] button:has-text('Save Changes')")
                    if confirm_btn and await confirm_btn.is_visible() and await confirm_btn.is_enabled():
                        print("[SAVE MODAL] Clicking Save Changes confirmation button...")
                        await human_click(page, confirm_btn)
                        await page.wait_for_timeout(4000)

                await page.screenshot(path=f"lens_{aid}_payout_toggled.png")
            except Exception as le:
                print(f"[NAV LENS WARN] Direct navigation error: {le}")

        await page.screenshot(path=f"my_lenses_acc_{aid}_final.png")
        await browser.close()

    print(f"\n[MONETIZATION RESULT] Account #{aid} Approval Summary: {results}")
    return results


def approve_account_monetization(account_id: str = "1", cookie_str: str = None, ticket: str = None, user: dict = None, target_lens_id: str = None, target_lens_url: str = None) -> dict:
    aid = str(account_id)
    print(f"\n{'='*65}\n[AUTONOMOUS MONETIZATION] Processing Account #{aid}...\n{'='*65}")
    if not cookie_str:
        session_data = obtain_valid_snap_session(account_id=aid)
        if not session_data:
            return {
                "account_id": aid,
                "error": "Failed to obtain valid session",
                "success": False
            }
        cookie_str = session_data.get("cookie_header") or session_data.get("cookie_str", "")
        ticket = ticket or session_data.get("ticket", "")
        user = user or session_data.get("user") or {}

    if not cookie_str:
        return {
            "account_id": aid,
            "error": "Failed to obtain valid session cookies",
            "success": False
        }

    user = user or {}
    exec_path = os.getenv("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH")
    if not exec_path:
        for candidate in ["/usr/bin/chromium", "/usr/bin/chromium-browser", "/usr/bin/google-chrome"]:
            if os.path.exists(candidate):
                exec_path = candidate
                break

    return asyncio.run(_run_browser_approval(aid, user, cookie_str, ticket or "", exec_path, target_lens_id=target_lens_id, target_lens_url=target_lens_url))


def main():
    parser = argparse.ArgumentParser(description="Approve Snapchat Lens Creator Rewards & Top Performer Payouts.")
    parser.add_argument("--account", type=str, default="all", choices=["1", "2", "3", "4", "5", "all"], help="Account ID or 'all'")
    parser.add_argument("--lens-id", type=str, default=None, help="Specific Lens ID to enroll in Top Performer Payouts")
    parser.add_argument("--lens-url", type=str, default=None, help="Direct URL to Lens page on my-lenses.snapchat.com")
    args = parser.parse_args()

    target_accounts = ["1", "2", "3", "4", "5"] if args.account == "all" else [args.account]

    overall_results = {}
    for aid in target_accounts:
        try:
            res = approve_account_monetization(aid, target_lens_id=args.lens_id, target_lens_url=args.lens_url)
            overall_results[aid] = res
        except Exception as e:
            print(f"[FATAL APPROVAL ERROR] Account #{aid}: {e}")
            overall_results[aid] = {"account_id": aid, "error": str(e), "success": False}

    print("\n" + "="*65)
    print("=== FLEET MONETIZATION APPROVAL SUMMARY ===")
    print("="*65)
    for aid, res in overall_results.items():
        payout_tos = res.get("LENS_CREATOR_PAYOUT_TOS", False)
        enrolled_count = res.get("enrolled_lenses_count", 0)
        toggled = res.get("top_performer_toggled", False)
        print(f"Account #{aid} (@{res.get('username', 'user')}): Payout TOS = {payout_tos} | Enrolled Lenses = {enrolled_count} | Top Performer Toggled = {toggled}")

    with open("monetization_approval_status.json", "w") as f:
        json.dump(overall_results, f, indent=2)
    print("\nSaved summary to monetization_approval_status.json")


if __name__ == "__main__":
    main()
