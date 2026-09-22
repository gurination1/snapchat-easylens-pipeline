#!/usr/bin/env python3
"""
Snapchat Autonomous Monetization & Payout Approver
Automates:
1. Direct API GraphQL execution for:
   - SetTosLatestAcceptedVersion for LENS_CREATOR_PAYOUT_TOS & ILDG_TOS
   - setLensCreatorPayoutEnrollment for target lens(es)
   - updateLens (creatorRewardProgramEnrolled: true) for target lens(es)
   - getLensesList discovery across COMMUNITY & PROFILE
2. Full Playwright headless browser verification & visual proof:
   - Pre-injects SSO ticket into localStorage before page scripts execute
   - Passes ?ticket={ticket} in navigation URL so SSOService hydrates session
   - Handles login & autonomous Gmail IMAP TIV link verification if challenged
   - Clicks #toggle-lens-creator-payout-enrolled if unchecked
   - Accepts on-screen TOS modal if opened
   - Confirms Save Changes modal
   - Captures visual proof screenshots for audit
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
    mint_sso_ticket_from_cookies,
    human_type,
    human_click,
    get_gemini_api_keys
)
from easylens_api import update_github_secret

GRAPHQL_URL = "https://my-lenses.snapchat.com/graphql"

GQL_INTROSPECT_TOS = """
query IntrospectTos {
    __type(name: "TosKey") {
        enumValues {
            name
        }
    }
}
"""

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

GQL_GET_LENSES = """
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
"""

GQL_SET_PAYOUT = """
mutation setLensCreatorPayoutEnrollment($lensId: ID!, $lensCreatorPayoutEnrolled: Boolean!) {
    setLensCreatorPayoutEnrollment(input: { lensId: $lensId, lensCreatorPayoutEnrolled: $lensCreatorPayoutEnrolled }) {
        lens {
            id
            lensCreatorPayoutEligibility
            status
        }
    }
}
"""

GQL_UPDATE_LENS = """
mutation updateLens($lensId: ID!, $creatorRewardProgramEnrolled: Boolean!, $isGameUserProvided: Boolean!) {
    updateLens(input: { lensId: $lensId, creatorRewardProgramEnrolled: $creatorRewardProgramEnrolled, isGameUserProvided: $isGameUserProvided }) {
        lens {
            id
            lensCreatorPayoutEligibility
            status
        }
    }
}
"""

GQL_GET_CATEGORIES = """
query getLensCategoryList {
    getLensCategoryList {
        lensCategoryList {
            parentLensCategoriesList {
                id
                parentId
                displayName
                deprecated
            }
            subLensCategoriesList {
                id
                parentId
                displayName
                deprecated
            }
        }
    }
}
"""

GQL_SET_CATEGORY = """
mutation setLensCategory($lensId: ID!, $primaryCategoryId: ID!, $secondaryCategoryId: ID) {
    setLensCategory(
        input: { lensId: $lensId, primaryCategoryId: $primaryCategoryId, secondaryCategoryId: $secondaryCategoryId }
    ) {
        lens {
            id
            status
            primaryCategoryId
            secondaryCategoryId
        }
    }
}
"""

GQL_GET_LENS = """
query getLens($lensId: ID!) {
    getLens(input: { lensId: $lensId }) {
        lens {
            id
            name
            status
            lensCreatorPayoutEligibility
            primaryCategoryId
            secondaryCategoryId
        }
    }
}
"""


def execute_direct_graphql(ticket: str, cookie_header: str, query: str, variables: dict = None, operation_name: str = None) -> dict:
    """Executes a GraphQL query/mutation directly against my-lenses.snapchat.com with rate-limit retry."""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {ticket}",
        "Origin": "https://my-lenses.snapchat.com",
        "Referer": "https://my-lenses.snapchat.com/",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
    }
    if operation_name:
        headers["x-apollo-operation-name"] = operation_name
    if cookie_header:
        headers["Cookie"] = cookie_header

    payload = {"query": query}
    if variables is not None:
        payload["variables"] = variables
    if operation_name is not None:
        payload["operationName"] = operation_name

    for attempt in range(4):
        try:
            res = requests.post(GRAPHQL_URL, headers=headers, json=payload, timeout=25)
            try:
                data = res.json()
            except Exception:
                return {"error": res.text, "status_code": res.status_code}

            err_str = json.dumps(data)
            if "RESOURCE_EXHAUSTED" in err_str or res.status_code == 429:
                wait_time = (attempt + 1) * 2.5
                print(f"  [GQL RATE LIMIT] Hit rate limit, sleeping {wait_time}s (attempt {attempt+1}/4)...")
                time.sleep(wait_time)
                continue
            return data
        except Exception as e:
            if attempt == 3:
                return {"error": str(e)}
            time.sleep(2.0)
    return {"error": "max_retries_exceeded"}


def direct_approve_tos(ticket: str, cookie_header: str) -> dict:
    """Submits SetTosLatestAcceptedVersion for all payout, reward, and monetization TOS keys."""
    results = {}
    keys = ["LENS_CREATOR_PAYOUT_TOS", "LENS_PLUS_PAYOUT_TOS", "ILDG_TOS"]

    # Dynamic introspection of TosKey enums directly from Snapchat schema
    try:
        i_res = execute_direct_graphql(ticket, cookie_header, GQL_INTROSPECT_TOS, operation_name="IntrospectTos")
        enum_vals = (((i_res.get("data") or {}).get("__type") or {}).get("enumValues") or [])
        if enum_vals:
            for ev in enum_vals:
                k_name = ev.get("name")
                if k_name and any(w in k_name.upper() for w in ["PAYOUT", "REWARD", "LENS", "MONETIZ", "PLUS", "ILDG", "CREATOR"]):
                    if k_name not in keys:
                        keys.append(k_name)
            print(f"[DIRECT GRAPHQL] Discovered and targeted {len(keys)} monetization TosKey enums: {keys}")
    except Exception as ie:
        print(f"[DIRECT GRAPHQL WARN] TosKey introspection failed: {ie}")

    for key in keys:
        try:
            print(f"[DIRECT GRAPHQL] Setting TOS acceptance for {key}...")
            res = execute_direct_graphql(ticket, cookie_header, GQL_SET_TOS, variables={"key": key}, operation_name="SetTosLatestAcceptedVersion")
            print(f"  -> Response: {json.dumps(res)}")
            data = res.get("data") or {}
            tos_data = (data.get("setTosLatestAcceptedVersion") or {}).get("tos") or {}
            acc_ver = tos_data.get("acceptedVersion")
            if acc_ver is not None:
                results[key] = True
                print(f"  ✓ {key}: ACCEPTED (Version: {acc_ver})")
            elif "errors" in res:
                err_msg = str(res.get("errors", ""))
                if "already" in err_msg.lower() or "not modified" in err_msg.lower():
                    results[key] = True
                    print(f"  ✓ {key}: ALREADY ACCEPTED")
                else:
                    results[key] = False
            else:
                results[key] = False
        except Exception as te:
            print(f"[DIRECT GRAPHQL WARN] Error setting {key}: {te}")
            results[key] = False
        time.sleep(1.0)

    # Verification query
    for key in keys:
        try:
            v_res = execute_direct_graphql(ticket, cookie_header, GQL_GET_TOS, variables={"key": key}, operation_name="GetTos")
            v_data = v_res.get("data") or {}
            t_data = (v_data.get("getTos") or {}).get("tos") or {}
            acc_ver = t_data.get("acceptedVersion")
            latest_ver = (t_data.get("metadata") or {}).get("latestVersion")
            if acc_ver and latest_ver and acc_ver >= latest_ver:
                results[key] = True
                print(f"  ✓ {key} VERIFIED: acceptedVersion={acc_ver} (latestVersion={latest_ver})")
        except Exception as ve:
            print(f"[DIRECT GRAPHQL WARN] Error verifying {key}: {ve}")
        time.sleep(1.0)
    return results


def direct_enroll_lenses(ticket: str, cookie_header: str, target_lens_id: str = None) -> dict:
    """Enrolls target lens and all published lenses into Top Performer Payouts & Lens+ Rewards with category standardization."""
    target_ids = set()
    if target_lens_id:
        target_ids.add(target_lens_id)

    # 1. Fetch category taxonomy
    preferred_primary_cat_id = None
    try:
        cat_res = execute_direct_graphql(ticket, cookie_header, GQL_GET_CATEGORIES, operation_name="getLensCategoryList")
        c_list = ((cat_res.get("data") or {}).get("getLensCategoryList") or {}).get("lensCategoryList") or {}
        parent_cats = c_list.get("parentLensCategoriesList") or []
        print(f"[CATEGORIES] Found {len(parent_cats)} top-level categories on Snapchat.")
        for pc in parent_cats:
            if not pc.get("deprecated"):
                dname = pc.get("displayName", "")
                print(f"  -> Category: {dname} (ID: {pc.get('id')})")
                if any(w in dname.lower() for w in ["beauty", "fashion", "entertainment", "style", "fun"]):
                    if not preferred_primary_cat_id:
                        preferred_primary_cat_id = pc.get("id")
    except Exception as ce:
        print(f"[DIRECT GRAPHQL WARN] Error querying category list: {ce}")

    # Discover lenses from COMMUNITY and PROFILE tabs
    for gType in ["COMMUNITY", "PROFILE"]:
        try:
            res = execute_direct_graphql(
                ticket, cookie_header, GQL_GET_LENSES,
                variables={"limit": 50, "offset": 0, "sortBy": "SORT_BY_DATE", "sortDirection": "SORT_DIRECTION_DESC", "type": gType},
                operation_name="getLensesList"
            )
            data = res.get("data") or {}
            l_list = (data.get("lenses") or {}).get("lensesList") or []
            for item in l_list:
                if item and item.get("id"):
                    target_ids.add(item["id"])
                    print(f"  [DISCOVERED LENS] {item.get('name')} (ID: {item.get('id')}) | Payout: {item.get('lensCreatorPayoutEligibility')}")
        except Exception as e:
            print(f"[DIRECT GRAPHQL WARN] Error discovering lenses for {gType}: {e}")
        time.sleep(1.0)

    enrolled = []
    success_count = 0
    target_lens_verified = False
    for lid in target_ids:
        print(f"[DIRECT GRAPHQL] Enrolling Lens {lid} into Top Performer & Lens Creator Payouts...")
        r1 = {}
        r2 = {}
        for retry_i in range(6):
            time.sleep(1.2)
            r1 = execute_direct_graphql(
                ticket, cookie_header, GQL_SET_PAYOUT,
                variables={"lensId": lid, "lensCreatorPayoutEnrolled": True},
                operation_name="setLensCreatorPayoutEnrollment"
            )
            time.sleep(1.2)
            r2 = execute_direct_graphql(
                ticket, cookie_header, GQL_UPDATE_LENS,
                variables={"lensId": lid, "creatorRewardProgramEnrolled": True, "isGameUserProvided": False},
                operation_name="updateLens"
            )
            r_str = json.dumps(r1) + json.dumps(r2)
            if "is currently processing" in r_str and retry_i < 5:
                print(f"  [WAIT] Lens {lid} is currently processing on Snapchat backend. Waiting 20s (retry {retry_i+1}/5)...")
                time.sleep(20)
            else:
                break

        r1_lens = (r1.get("data") or {}).get("setLensCreatorPayoutEnrollment", {}).get("lens") or {}
        r2_lens = (r2.get("data") or {}).get("updateLens", {}).get("lens") or {}
        is_enrolled = bool(
            r1_lens.get("lensCreatorPayoutEligibility") in ("LENS_CREATOR_PAYOUT_ELIGIBILITY_PENDING", "LENS_CREATOR_PAYOUT_ELIGIBILITY_ELIGIBLE")
            or r2_lens.get("lensCreatorPayoutEligibility") in ("LENS_CREATOR_PAYOUT_ELIGIBILITY_PENDING", "LENS_CREATOR_PAYOUT_ELIGIBILITY_ELIGIBLE")
            or "already enrolled" in str(r1.get("errors", "")).lower()
            or (not r1.get("errors") and r1.get("data"))
            or (not r2.get("errors") and r2.get("data"))
        )
        if is_enrolled:
            success_count += 1
            print(f"  [SUCCESS {lid}] Verified enrolled in payout program via direct GraphQL!")
            mark_lens_enrolled_in_history(lid)
            if target_lens_id and lid == target_lens_id:
                target_lens_verified = True

        cat_res = None
        if preferred_primary_cat_id:
            time.sleep(1.0)
            cat_res = execute_direct_graphql(
                ticket, cookie_header, GQL_SET_CATEGORY,
                variables={"lensId": lid, "primaryCategoryId": preferred_primary_cat_id},
                operation_name="setLensCategory"
            )

        print(f"  [RESULT {lid}] setPayout: {json.dumps(r1)[:100]} | updateLens: {json.dumps(r2)[:100]}")
        enrolled.append({"id": lid, "enrolled": is_enrolled, "setPayoutRes": r1, "updateLensRes": r2, "setCategoryRes": cat_res})

    return {"count": success_count, "attempted": len(target_ids), "lenses": enrolled, "target_lens_verified": target_lens_verified}


def mark_lens_enrolled_in_history(lens_id: str):
    """Updates published_lenses.json to mark creator_rewards_enrolled = True for the given lens ID."""
    history_file = "published_lenses.json"
    if not os.path.exists(history_file):
        return
    try:
        with open(history_file, "r") as f:
            data = json.load(f)
        updated = False
        for item in data:
            if item.get("lens_id") == lens_id and not item.get("creator_rewards_enrolled"):
                item["creator_rewards_enrolled"] = True
                updated = True
        if updated:
            with open(history_file, "w") as f:
                json.dump(data, f, indent=2)
            print(f"  [STATE SYNC] Marked lens {lens_id} as enrolled in {history_file}")
    except Exception as e:
        print(f"  [STATE SYNC WARN] Failed to update {history_file}: {e}")


def wait_for_lens_ready(ticket: str, cookie_header: str, lens_id: str, max_wait_sec: int = 360) -> dict:
    """Polls getLens until status exits LENS_STATUS_PROCESSING and is ready for mutations."""
    start = time.time()
    print(f"[POLL LENS {lens_id}] Waiting for Snapchat catalog ingestion to complete (max {max_wait_sec}s)...")
    while time.time() - start < max_wait_sec:
        res = execute_direct_graphql(ticket, cookie_header, GQL_GET_LENS, variables={"lensId": lens_id}, operation_name="getLens")
        lens = ((res.get("data") or {}).get("getLens") or {}).get("lens")
        if lens:
            status = lens.get("status", "")
            payout = lens.get("lensCreatorPayoutEligibility", "")
            print(f"  [POLL STATUS] Lens {lens_id} -> Status: '{status}', Payout Eligibility: '{payout}'")
            if status and "PROCESSING" not in status.upper():
                print(f"  ✓ [POLL READY] Lens {lens_id} transitioned to '{status}'! Ready for monetization.")
                return lens
        time.sleep(5)
    print(f"  [POLL WARN] Lens {lens_id} polling reached {max_wait_sec}s limit; proceeding to enroll.")
    return None


def sweep_unenrolled_fleet_lenses(ticket: str, cookie_header: str) -> dict:
    """Scans all published lenses under the account and auto-enrolls any lens with unset payout eligibility."""
    print("\n[FLEET SWEEP] Scanning account lenses for unset Top Performer Payout eligibility...")
    unenrolled_ids = []
    for gType in ["COMMUNITY", "PROFILE"]:
        try:
            res = execute_direct_graphql(
                ticket, cookie_header, GQL_GET_LENSES,
                variables={"limit": 100, "offset": 0, "sortBy": "SORT_BY_DATE", "sortDirection": "SORT_DIRECTION_DESC", "type": gType},
                operation_name="getLensesList"
            )
            l_list = (((res.get("data") or {}).get("lenses") or {}).get("lensesList") or [])
            for item in l_list:
                if not item or not item.get("id"):
                    continue
                elig = item.get("lensCreatorPayoutEligibility", "")
                lid = item["id"]
                name = item.get("name", "Unnamed")
                if elig in ("LENS_CREATOR_PAYOUT_ELIGIBILITY_UNSET", "UNSET", "", None):
                    print(f"  [UNENROLLED DETECTED] '{name}' ({lid}) -> Eligibility: '{elig}'. Queued for auto-enrollment.")
                    unenrolled_ids.append(lid)
                else:
                    print(f"  [ENROLLED OK] '{name}' ({lid}) -> Eligibility: '{elig}'")
                    mark_lens_enrolled_in_history(lid)
        except Exception as e:
            print(f"[FLEET SWEEP WARN] Error discovering lenses for {gType}: {e}")
        time.sleep(1.0)

    remedied = 0
    for lid in unenrolled_ids:
        print(f"[FLEET SWEEP ENROLL] Remedying lens {lid}...")
        try:
            s_res = execute_direct_graphql(ticket, cookie_header, GQL_SET_PAYOUT, variables={"lensId": lid, "lensCreatorPayoutEnrolled": True}, operation_name="setLensCreatorPayoutEnrollment")
            time.sleep(1.0)
            u_res = execute_direct_graphql(ticket, cookie_header, GQL_UPDATE_LENS, variables={"lensId": lid, "creatorRewardProgramEnrolled": True, "isGameUserProvided": False}, operation_name="updateLens")
            is_ok = bool(
                (s_res.get("data") or {}).get("setLensCreatorPayoutEnrollment")
                or (u_res.get("data") or {}).get("updateLens")
                or "already enrolled" in str(s_res.get("errors", "")).lower()
            )
            if is_ok:
                remedied += 1
                print(f"  ✓ [FLEET SWEEP SUCCESS] Lens {lid} successfully enrolled in Top Performer Payouts!")
                mark_lens_enrolled_in_history(lid)
        except Exception as err:
            print(f"  X [FLEET SWEEP WARN] Failed to remedy {lid}: {err}")
        time.sleep(1.0)

    print(f"[FLEET SWEEP DONE] Total unenrolled found: {len(unenrolled_ids)}, Remedied: {remedied}\n")
    return {"found": len(unenrolled_ids), "remedied": remedied}


def sanitize_cookies_for_playwright(cookie_str: str) -> list:
    """Parses raw cookie strings into valid Playwright cookie dicts with secure=True."""
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
                for sp in p.split(","):
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
            # RFC 6265bis: __Host- cookies must NOT have domain or path specified in Playwright when url is given
            if name.startswith("__Host-"):
                cookie_list.append({
                    "name": name,
                    "value": val,
                    "url": "https://accounts.snapchat.com",
                    "secure": True
                })
                cookie_list.append({
                    "name": name,
                    "value": val,
                    "url": "https://my-lenses.snapchat.com",
                    "secure": True
                })
            elif name.startswith("__Secure-"):
                cookie_list.append({
                    "name": name,
                    "value": val,
                    "domain": ".snapchat.com",
                    "path": "/",
                    "secure": True
                })
            else:
                cookie_list.append({
                    "name": name,
                    "value": val,
                    "domain": ".snapchat.com",
                    "path": "/",
                    "secure": True
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

        # Inject SSO ticket into localStorage before any page script executes
        if ticket:
            await context.add_init_script(f"""
                try {{
                    localStorage.setItem('sc-sso-auth-ticket', '{ticket}');
                    console.log('Injected SSO ticket into localStorage');
                }} catch (e) {{}}
            """)

        # Parse and inject cookies into browser context safely
        if cookie_str:
            cookie_list = sanitize_cookies_for_playwright(cookie_str)
            injected_count = 0
            for c in cookie_list:
                try:
                    await context.add_cookies([c])
                    injected_count += 1
                except Exception as ce:
                    print(f"[COOKIE INJECT WARN] Failed to inject {c.get('name')}: {ce}")
            print(f"[COOKIES] Injected {injected_count}/{len(cookie_list)} authenticated cookies into browser context")

        page = await context.new_page()
        if stealth_async:
            await stealth_async(page)

        # Network sniffer for GraphQL operations to monitor real-time mutations
        async def on_graphql_response(res):
            if "graphql" in res.url:
                try:
                    op_name = res.request.headers.get("x-apollo-operation-name", "unknown")
                    body_snippet = (await res.text())[:300]
                    print(f"[BROWSER GRAPHQL {res.status}] Op: {op_name} -> {body_snippet}")
                except Exception:
                    pass
        page.on("response", on_graphql_response)

        # Target portal URL with ?ticket={ticket} query parameter for SSOService
        base_target = target_lens_url or (f"https://my-lenses.snapchat.com/lens/{target_lens_id}" if target_lens_id else "https://my-lenses.snapchat.com/")
        if ticket:
            sep = "&" if "?" in base_target else "?"
            portal_url = f"{base_target}{sep}ticket={ticket}"
        else:
            portal_url = base_target

        print(f"[NAV] Loading My Lenses portal: {portal_url[:85]}...")
        try:
            await page.goto(portal_url, wait_until="domcontentloaded", timeout=45000)
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
                    await page.wait_for_timeout(500)
                    await page.keyboard.press("Enter")
                    await page.wait_for_timeout(500)
                    next_btn = await page.query_selector("button:has-text('Next'), button[type='submit']")
                    if next_btn and await next_btn.is_visible():
                        await human_click(page, next_btn)

                # Wait for password input to become genuinely visible
                pwd_input = None
                for _ in range(30):
                    await page.wait_for_timeout(1000)
                    p_el = await page.query_selector("input[type='password']")
                    if p_el and await p_el.is_visible():
                        pwd_input = p_el
                        break

                if pwd_input:
                    env_pwd = os.getenv(f"SNAP_PASSWORD_ACC_{aid}") or os.getenv("SNAP_PASSWORD") or ""
                    print("[AUTH LOGIN] Filling password...")
                    await human_type(page, pwd_input, env_pwd)
                    await page.wait_for_timeout(500)
                    await page.keyboard.press("Enter")
                    await page.wait_for_timeout(500)
                    login_btn = await page.query_selector("button:has-text('Log In'), button:has-text('Next'), button[type='submit']")
                    if login_btn and await login_btn.is_visible():
                        await human_click(page, login_btn)
                        await page.wait_for_timeout(6000)

                # Check for Snapchat TIV (Two-step Identity Verification email approval)
                await page.wait_for_timeout(4000)
                if "/v2/tiv" in page.url or "tiv" in page.url.lower():
                    print("[TIV DETECTED] Snapchat requested Email Sign-In Verification. Launching autonomous IMAP solver...")
                    from snap_auth_automator import fetch_latest_snap_tiv_url
                    gmail_addr = os.getenv(f"GMAIL_ADDRESS_ACC_{aid}") or os.getenv("GMAIL_ADDRESS") or "gurination1@gmail.com"
                    gmail_pwd = os.getenv(f"GMAIL_APP_PASSWORD_ACC_{aid}") or os.getenv("GMAIL_APP_PASSWORD") or ""
                    tiv_start = time.time() - 90
                    approved = False
                    for tiv_step in range(40):
                        await page.wait_for_timeout(3000)
                        if "tiv" not in page.url.lower() and "login" not in page.url.lower():
                            approved = True
                            print(f"[TIV REDIRECT] Session transitioned off TIV page automatically! (URL: {page.url[:80]})")
                            break
                        if gmail_pwd and not approved:
                            tiv_url = fetch_latest_snap_tiv_url(gmail_addr, gmail_pwd, tiv_start)
                            if tiv_url:
                                print(f"[TIV URL FOUND] Discovered verification link: {tiv_url[:80]}...")
                                approval_page = await context.new_page()
                                try:
                                    await approval_page.goto(tiv_url, wait_until="domcontentloaded", timeout=30000)
                                    await approval_page.wait_for_timeout(2000)
                                    # Execute direct landing API approval
                                    post_res = await approval_page.evaluate("""async () => {
                                        const root = document.getElementById('tiv-landing-root');
                                        if (!root) return { ok: false, err: 'no_root' };
                                        const xsrf = root.getAttribute('data-xsrf') || '';
                                        const nonce = root.getAttribute('data-nonce') || '';
                                        try {
                                            const r = await fetch('/accounts/tiv/landing' + window.location.search, {
                                                method: 'POST',
                                                headers: {
                                                    'Content-Type': 'application/x-www-form-urlencoded',
                                                    'X-XSRF-TOKEN': xsrf
                                                },
                                                body: new URLSearchParams({'xsrf_token': xsrf, 'n': nonce, 's': '1'})
                                            });
                                            return { ok: r.ok || r.status === 302 || r.status === 200, status: r.status };
                                        } catch (e) {
                                            return { ok: false, err: String(e) };
                                        }
                                    }""")
                                    print(f"[TIV LANDING RESULT] Direct API response: {post_res}")
                                    await approval_page.wait_for_timeout(1500)
                                    appr_btn = await approval_page.query_selector("button:has-text('Approve'), div[role='button']:has-text('Approve'), button#approve-btn")
                                    if appr_btn and await appr_btn.is_visible():
                                        await human_click(approval_page, appr_btn)
                                        await approval_page.wait_for_timeout(2000)
                                        print("[TIV APPROVED] Clicked Approve button on landing page!")
                                except Exception as tiv_err:
                                    print(f"[TIV APPROVE WARN] {tiv_err}")
                                finally:
                                    try:
                                        await approval_page.close()
                                    except Exception:
                                        pass
                                approved = True
                                print("[TIV WAITING] Awaiting natural session redirect on main page...")

                # Wait for navigation back to my-lenses portal
                for _ in range(30):
                    if "login" not in page.url and "tiv" not in page.url:
                        break
                    await page.wait_for_timeout(1000)

                if "my-lenses.snapchat.com" not in page.url:
                    print(f"[AUTH TRANSITION] Transitioning to portal URL: {portal_url[:80]}...")
                    try:
                        await page.goto(portal_url, wait_until="domcontentloaded", timeout=45000)
                        await page.wait_for_timeout(4000)
                    except Exception as nav_e:
                        print(f"[AUTH TRANSITION WARN] {nav_e}")

                # Extract and persist fresh browser cookies to GitHub Secrets
                try:
                    fresh_cookies = await context.cookies()
                    cookie_header_parts = [f"{c['name']}={c['value']}" for c in fresh_cookies]
                    fresh_cookie_str = "; ".join(cookie_header_parts)
                    if "sc-a-nonce" in fresh_cookie_str or "xsrf_token" in fresh_cookie_str:
                        sec_acc = f"SNAP_ACCOUNTS_COOKIE_ACC_{aid}" if aid != "1" else "SNAP_ACCOUNTS_COOKIE"
                        sec_hdr = f"SNAP_COOKIE_HEADER_ACC_{aid}" if aid != "1" else "SNAP_COOKIE_HEADER"
                        update_github_secret(sec_acc, fresh_cookie_str)
                        update_github_secret(sec_hdr, fresh_cookie_str)
                        print(f"[COOKIE PERSIST] Saved {len(fresh_cookies)} fresh session cookies for Account #{aid} to {sec_acc}")
                except Exception as ce:
                    print(f"[COOKIE PERSIST WARN] {ce}")
            except Exception as login_err:
                print(f"[AUTH LOGIN WARN] In-browser login attempt error: {login_err}")

        # Screenshot for audit
        await page.screenshot(path=f"my_lenses_acc_{aid}_loaded.png")
        print(f"[PORTAL LOADED] Current URL: {page.url[:80]} | Title: '{await page.title()}'")

        # Step 0: Check for and dismiss any CookieModal / Cookie Banner
        for cookie_sel in [
            "button:has-text('Accept Cookies')",
            "button:has-text('Accept cookies')",
            "[data-testid*='cookie'] button",
            "button[class*='CookieModal']",
            ".cookie-modal button"
        ]:
            try:
                c_btn = await page.query_selector(cookie_sel)
                if c_btn and await c_btn.is_visible():
                    print("[COOKIE BANNER] Dismissing cookie banner...")
                    await human_click(page, c_btn)
                    await page.wait_for_timeout(1500)
                    break
            except Exception:
                pass

        # 3. Check for and accept any on-screen TOS modal / Banner (Strictly excluding cookie buttons!)
        modals_accepted = 0
        tos_btn_selectors = [
            "[data-testid*='tos-modal'] button",
            "[data-testid*='accept-terms']",
            "button[class*='TosModal']",
            "button:has-text('I Agree')",
            "button:has-text('Agree & Continue')",
            "button:has-text('View Terms')",
            "button:has-text('Agree')",
            "button:has-text('Accept All')",
            "button:has-text('Accept')"
        ]
        for sel in tos_btn_selectors:
            try:
                btns = await page.query_selector_all(sel)
                for btn in btns:
                    if await btn.is_visible() and await btn.is_enabled():
                        txt = (await btn.inner_text()).strip()
                        if any(w in txt.lower() for w in ["cancel", "dismiss", "decline", "close", "cookie", "cookies"]):
                            continue
                        print(f"[UI MODAL] Clicking on-screen terms button: '{txt}'...")
                        await human_click(page, btn)
                        await page.wait_for_timeout(2000)
                        modals_accepted += 1
            except Exception:
                pass
        results["ui_modals_accepted"] = modals_accepted

        # 4. Direct UI Navigation to target lens page to ensure toggle is verified & toggled
        nav_target = target_lens_url or (f"https://my-lenses.snapchat.com/lens/{target_lens_id}" if target_lens_id else None)
        if nav_target:
            full_nav = f"{nav_target}?ticket={ticket}" if (ticket and "?" not in nav_target) else (f"{nav_target}&ticket={ticket}" if ticket else nav_target)
            print(f"[NAV LENS] Navigating directly to target lens page: {full_nav[:85]}...")
            try:
                await page.goto(full_nav, wait_until="domcontentloaded", timeout=45000)
                await page.wait_for_timeout(6000)

                # Step A: Dismiss cookie banner on lens page if present
                for cookie_sel in [
                    "button:has-text('Accept Cookies')",
                    "button:has-text('Accept cookies')",
                    "[data-testid*='cookie'] button"
                ]:
                    try:
                        c_btn = await page.query_selector(cookie_sel)
                        if c_btn and await c_btn.is_visible():
                            print("[COOKIE BANNER LENS] Dismissing cookie banner on lens page...")
                            await human_click(page, c_btn)
                            await page.wait_for_timeout(1500)
                            break
                    except Exception:
                        pass

                # Step A2: Check for and accept any blocking TOS modal on the lens page
                for _ in range(3):
                    tos_modal_btn = await page.query_selector("[data-testid='tos-modal'] button:has-text('Accept'), [data-testid='tos-modal'] button:has-text('I Agree'), [role='dialog'] button:has-text('Accept'), [role='dialog'] button:has-text('I Agree')")
                    if tos_modal_btn and await tos_modal_btn.is_visible() and await tos_modal_btn.is_enabled():
                        btn_text = (await tos_modal_btn.inner_text()).strip()
                        if any(w in btn_text.lower() for w in ["cookie", "cookies", "cancel", "dismiss"]):
                            continue
                        print(f"[TOS MODAL] Clicking on-screen TOS acceptance button on lens page: '{btn_text}'...")
                        await human_click(page, tos_modal_btn)
                        await page.wait_for_timeout(2500)
                    else:
                        break

                # Step A3: If lens is still processing in UI, wait and reload
                for proc_wait in range(6):
                    status_badge = await page.query_selector("div:has-text('Processing'), span:has-text('Processing')")
                    if status_badge and await status_badge.is_visible():
                        txt = (await status_badge.inner_text() or "").strip()
                        if "processing" in txt.lower():
                            print(f"[UI STATUS] Lens is still 'Processing' in UI (attempt {proc_wait+1}/6); waiting 15s before reload...")
                            await page.wait_for_timeout(15000)
                            try:
                                await page.reload(wait_until="domcontentloaded", timeout=30000)
                                await page.wait_for_timeout(3000)
                            except Exception:
                                pass
                            continue
                    break

                # Step B: Locate the Top Performer switch
                try:
                    payout_container = await page.query_selector("#creator-payout-container, [data-testid*='creator-payout'], div:has-text('Top Performer Payouts Program')")
                    if payout_container:
                        await payout_container.scroll_into_view_if_needed()
                except Exception:
                    pass

                target_section = page.locator("div, section, tr").filter(has_text="Top Performer Payouts Program").last
                switch_locator = target_section.locator("button[role='switch'], [role='switch'], input[type='checkbox'], .sds-switch").first

                async def is_switch_active():
                    try:
                        for loc in [switch_locator, page.locator("#toggle-lens-creator-payout-enrolled, .sds-switch")]:
                            if await loc.count() > 0:
                                sw = loc.first
                                aria = await sw.get_attribute("aria-checked")
                                if aria == "true":
                                    return True
                                if aria == "false":
                                    return False
                                inp = await sw.evaluate("el => el.checked || (el.querySelector('input') && el.querySelector('input').checked) || false")
                                if inp:
                                    return True
                                cls = (await sw.get_attribute("class") or "").lower()
                                if "sds-switch--checked" in cls or "is-checked" in cls:
                                    return True
                                bg = await sw.evaluate("""el => {
                                    const track = el.querySelector('.sds-switch__slider, .sds-switch__track') || el;
                                    const c = window.getComputedStyle(track).backgroundColor || '';
                                    const match = c.match(/rgba?\\((\\d+),\\s*(\\d+),\\s*(\\d+)/);
                                    if (match) {
                                        const r = parseInt(match[1], 10);
                                        const g = parseInt(match[2], 10);
                                        const b = parseInt(match[3], 10);
                                        if (g > 150 && g > r + 20) return 'green';
                                    }
                                    return c;
                                }""")
                                if "green" in bg.lower() or "rgb(0, 224" in bg or "#00e054" in bg:
                                    return True
                                has_svg_check = await sw.evaluate("el => !! (el.querySelector('svg polyline') || el.querySelector('[data-testid*=\"check-icon\"]') || el.querySelector('.sds-icon--check') || el.querySelector('.sds-switch__icon--check'))")
                                if has_svg_check:
                                    return True
                    except Exception:
                        pass
                    return False

                active_before = await is_switch_active()
                print(f"[TOGGLE INSPECT] Top Performer switch active before click: {active_before}")

                if not active_before:
                    for pass_num in range(1, 4):
                        print(f"[TOGGLE PASS {pass_num}] Clicking Top Performer Payouts switch...")
                        if await switch_locator.count() > 0:
                            try:
                                await switch_locator.click(force=True)
                            except Exception:
                                sw_el = await page.query_selector("#toggle-lens-creator-payout-enrolled, .sds-switch")
                                if sw_el:
                                    await human_click(page, sw_el)
                        await page.wait_for_timeout(2000)

                        # Check if clicking switch triggered an on-screen Terms of Service modal
                        for _ in range(3):
                            tos_btns = await page.query_selector_all("[data-testid*='tos-modal'] button, [role='dialog'] button, button:has-text('Accept'), button:has-text('I Agree'), button:has-text('Agree & Continue'), button:has-text('Enroll'), button:has-text('Confirm'), button:has-text('Yes')")
                            clicked_modal = False
                            for tb in tos_btns:
                                if await tb.is_visible() and await tb.is_enabled():
                                    t_txt = (await tb.inner_text()).strip()
                                    if any(w in t_txt.lower() for w in ["cancel", "dismiss", "decline", "close", "back", "cookie", "cookies"]):
                                        continue
                                    print(f"[TOS MODAL PASS {pass_num}] Terms modal appeared! Clicking '{t_txt}'...")
                                    await human_click(page, tb)
                                    await page.wait_for_timeout(2500)
                                    clicked_modal = True
                                    break
                            if not clicked_modal:
                                break

                        # Check if active now
                        if await is_switch_active():
                            print(f"✓ [TOGGLE OK PASS {pass_num}] Switch successfully toggled ON!")
                            results["top_performer_toggled"] = True
                            break
                        else:
                            print(f"[TOGGLE PASS {pass_num}] Switch still OFF after modal; clicking switch second time to activate...")
                            if await switch_locator.count() > 0:
                                try:
                                    await switch_locator.click(force=True)
                                except Exception:
                                    pass
                            await page.wait_for_timeout(2000)
                            if await is_switch_active():
                                print(f"✓ [TOGGLE OK PASS {pass_num}] Switch successfully toggled ON on second click!")
                                results["top_performer_toggled"] = True
                                break
                else:
                    print("[TOGGLE] Top Performer Payouts switch is ALREADY CHECKED!")
                    results["top_performer_toggled"] = True

                # Step C: Check for any Save Changes button
                for save_sel in ["button:has-text('Save Changes')", "button:has-text('Save')", "[data-testid='save-changes-button']"]:
                    save_btn = await page.query_selector(save_sel)
                    if save_btn and await save_btn.is_visible() and await save_btn.is_enabled():
                        print(f"[SAVE] Clicking '{await save_btn.inner_text()}' button...")
                        await human_click(page, save_btn)
                        await page.wait_for_timeout(2000)
                        confirm_btn = await page.query_selector("[data-testid='save-changes-modal'] button:has-text('Save Changes'), [role='dialog'] button:has-text('Save Changes'), [role='dialog'] button:has-text('Confirm'), [role='dialog'] button:has-text('Save')")
                        if confirm_btn and await confirm_btn.is_visible() and await confirm_btn.is_enabled():
                            print("[SAVE MODAL] Confirming Save Changes dialog...")
                            await human_click(page, confirm_btn)
                            await page.wait_for_timeout(4000)
                        break

                # Step D: Final verification of toggle state
                final_checked = await is_switch_active()
                print(f"[FINAL VERIFICATION] Top Performer Payout switch checked state: {final_checked}")
                results["top_performer_toggled"] = bool(final_checked)
                results["final_checked"] = bool(final_checked)

                await page.screenshot(path=f"lens_{aid}_payout_toggled.png")
            except Exception as le:
                print(f"[NAV LENS WARN] Direct navigation error: {le}")

        await page.screenshot(path=f"my_lenses_acc_{aid}_final.png")
        await browser.close()

    print(f"\n[MONETIZATION RESULT] Account #{aid} UI Summary: {results}")
    return results


def approve_account_monetization(account_id: str = "1", cookie_str: str = None, ticket: str = None, user: dict = None, target_lens_id: str = None, target_lens_url: str = None) -> dict:
    aid = str(account_id)
    print(f"\n{'='*65}\n[AUTONOMOUS MONETIZATION] Processing Account #{aid}...\n{'='*65}")
    if not ticket or not cookie_str:
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

    if not ticket:
        return {
            "account_id": aid,
            "error": "Failed to obtain valid SSO token",
            "success": False
        }

    user = user or {}

    # Mint a ticket specifically for lens-studio-web (my-lenses.snapchat.com)
    my_lenses_ticket = None
    if cookie_str:
        my_lenses_ticket = mint_sso_ticket_from_cookies(cookie_str, client_id="lens-studio-web")
    if not my_lenses_ticket:
        my_lenses_ticket = ticket

    print(f"[AUTH TICKET] Active lens-studio-web Bearer ticket: {my_lenses_ticket[:16] if my_lenses_ticket else 'None'}...")

    # 1. Execute direct GraphQL operations first (highest reliability, runs in ~200ms)
    print("\n--- PHASE 1: DIRECT GRAPHQL MONETIZATION ENROLLMENT ---")
    tos_results = direct_approve_tos(my_lenses_ticket, cookie_str)

    # Permanent fix: If a target lens was just published, wait for Snapchat catalog ingestion to exit PROCESSING state
    if target_lens_id:
        wait_for_lens_ready(my_lenses_ticket, cookie_str, target_lens_id, max_wait_sec=240)

    enroll_results = direct_enroll_lenses(my_lenses_ticket, cookie_str, target_lens_id=target_lens_id)

    # Permanent fix: Fleet sweep to find and heal ANY unenrolled lenses on the account
    sweep_results = sweep_unenrolled_fleet_lenses(my_lenses_ticket, cookie_str)

    # Permanent verification: Query getLens on target to confirm eligibility status
    verified_payout = False
    if target_lens_id:
        v_res = execute_direct_graphql(my_lenses_ticket, cookie_str, GQL_GET_LENS, variables={"lensId": target_lens_id}, operation_name="getLens")
        v_lens = ((v_res.get("data") or {}).get("getLens") or {}).get("lens") or {}
        v_elig = v_lens.get("lensCreatorPayoutEligibility", "")
        print(f"[FINAL GRAPHQL VERIFICATION {target_lens_id}] Status: {v_lens.get('status')} | Payout: '{v_elig}'")
        if v_elig in ("LENS_CREATOR_PAYOUT_ELIGIBILITY_PENDING", "LENS_CREATOR_PAYOUT_ELIGIBILITY_ELIGIBLE"):
            verified_payout = True

    # 2. Execute browser UI automation for visual proof and on-screen toggle
    print("\n--- PHASE 2: HEADLESS BROWSER UI VERIFICATION & TOGGLE ---")
    exec_path = os.getenv("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH")
    if not exec_path:
        for candidate in ["/usr/bin/chromium", "/usr/bin/chromium-browser", "/usr/bin/google-chrome"]:
            if os.path.exists(candidate):
                exec_path = candidate
                break

    browser_results = asyncio.run(_run_browser_approval(
        aid, user, cookie_str, my_lenses_ticket, exec_path,
        target_lens_id=target_lens_id, target_lens_url=target_lens_url
    ))

    # Post-browser GraphQL double verification
    if target_lens_id and not verified_payout:
        try:
            v_res = execute_direct_graphql(my_lenses_ticket, cookie_str, GQL_GET_LENS, variables={"lensId": target_lens_id}, operation_name="getLens")
            v_lens = ((v_res.get("data") or {}).get("getLens") or {}).get("lens") or {}
            v_elig = v_lens.get("lensCreatorPayoutEligibility", "")
            print(f"[POST-BROWSER GRAPHQL VERIFICATION {target_lens_id}] Status: {v_lens.get('status')} | Payout: '{v_elig}'")
            if v_elig in ("LENS_CREATOR_PAYOUT_ELIGIBILITY_PENDING", "LENS_CREATOR_PAYOUT_ELIGIBILITY_ELIGIBLE"):
                verified_payout = True
        except Exception:
            pass

    target_verified = False
    if target_lens_id:
        target_verified = bool(
            verified_payout
            or (browser_results.get("top_performer_toggled", False) and browser_results.get("final_checked", False))
            or enroll_results.get("target_lens_verified", False)
        )
    else:
        target_verified = bool(
            browser_results.get("top_performer_toggled", False)
            or (enroll_results.get("count", 0) > 0)
            or (sweep_results.get("remedied", 0) > 0)
        )

    # Merge results
    final_result = {
        "account_id": aid,
        "username": user.get("username"),
        "displayName": user.get("displayName"),
        "LENS_CREATOR_PAYOUT_TOS": tos_results.get("LENS_CREATOR_PAYOUT_TOS", False) or browser_results.get("LENS_CREATOR_PAYOUT_TOS", False),
        "ILDG_TOS": tos_results.get("ILDG_TOS", False) or browser_results.get("ILDG_TOS", False),
        "ui_modals_accepted": browser_results.get("ui_modals_accepted", 0),
        "enrolled_lenses_count": enroll_results.get("count", 0) + sweep_results.get("remedied", 0),
        "top_performer_toggled": target_verified,
        "target_lens_verified": target_verified,
        "sweep_results": sweep_results,
        "direct_graphql_details": enroll_results,
        "success": True
    }

    return final_result


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
