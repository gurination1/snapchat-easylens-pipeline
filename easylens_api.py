"""
Snapchat EasyLens (LensStudioWeb) Automation Client
Implements reverse-engineered API flow extracted from easylens HAR and chunk bundles.
"""

import os
import json
import time
import uuid
import subprocess
import requests

AILC_BASE = "https://gcp.api.snapchat.com/lens-studio-web-ailc"
BOLT_BASE = "https://aws.api.snapchat.com/lens-studio-web-bolt"
SNAPML_BASE = "https://gcp.api.snapchat.com/lens-studio-web-snapml"


ACCOUNTS_BASE = "https://accounts.snapchat.com"
REPO = "gurination1/snapchat-easylens-pipeline"


def update_github_secret(secret_name: str, secret_value: str, repo: str = REPO):
    """Safely updates a GitHub repository secret using gh CLI if available."""
    if not secret_value:
        return
    token = os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN")
    if not token:
        return
    try:
        subprocess.run(
            ["gh", "secret", "set", secret_name, "--repo", repo],
            input=secret_value.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True
        )
        print(f"[GITHUB SECRET] Persisted {secret_name} successfully")
    except Exception as e:
        print(f"[GITHUB SECRET WARN] {secret_name}: {e}")


RETRIABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}


class EasyLensClient:
    def __init__(self, sso_token: str = "", cookie_header: str = "", accounts_cookie: str = ""):
        self.sso_token = sso_token
        self.accounts_cookie = accounts_cookie or cookie_header
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {sso_token}" if sso_token else "",
            "Origin": "https://easylens.snapchat.com",
            "Referer": "https://easylens.snapchat.com/",
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Mobile Safari/537.36",
            "x-snap-client-user-agent": "LensStudioWeb/2.56.0 PROD (K; android 10) Chrome/143 Core/372 AppId/easylens.snapchat.com",
            "sec-ch-ua": '"Quetta";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
            "sec-ch-ua-mobile": "?1",
            "sec-ch-ua-platform": '"Android"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site"
        })
        if cookie_header:
            self.session.headers["Cookie"] = cookie_header

    def _request_with_retry(self, method: str, url: str, max_retries: int = 4, backoff_base: float = 2.0, **kwargs) -> requests.Response:
        """Robust request wrapper with exponential backoff and automatic 401 SSO ticket refresh"""
        last_exception = None
        res = None
        for attempt in range(max_retries):
            try:
                res = self.session.request(method, url, **kwargs)
                if res.status_code == 401:
                    print(f"[AUTH 401] {url} returned 401. Triggering self-healing SSO refresh (attempt {attempt+1}/{max_retries})...")
                    new_ticket = self.refresh_sso_ticket()
                    if new_ticket:
                        continue
                if res.status_code in RETRIABLE_STATUS_CODES:
                    wait_time = backoff_base ** attempt
                    print(f"[HTTP {res.status_code}] Retrying {method} {url} in {wait_time:.1f}s (attempt {attempt+1}/{max_retries})...")
                    time.sleep(wait_time)
                    continue
                return res
            except (requests.RequestException, ConnectionError, TimeoutError) as e:
                last_exception = e
                wait_time = backoff_base ** attempt
                print(f"[NET ERROR] {e}. Retrying {method} {url} in {wait_time:.1f}s (attempt {attempt+1}/{max_retries})...")
                time.sleep(wait_time)
        if last_exception:
            raise last_exception
        return res

    def refresh_sso_ticket(self) -> str:
        """Calls accounts.snapchat.com/accounts/sso with persistent session cookies to mint a new Bearer ticket"""
        import base64
        url = f"{ACCOUNTS_BASE}/accounts/sso"
        cookie = self.accounts_cookie or self.session.headers.get("Cookie", "")
        headers = {
            "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
            "Origin": "https://easylens.snapchat.com",
            "Referer": "https://easylens.snapchat.com/",
            "User-Agent": self.session.headers.get("User-Agent"),
            "Cookie": cookie
        }
        data = "client_id=web-ar-applier"
        try:
            print("[SSO] Requesting fresh Bearer ticket from accounts.snapchat.com/accounts/sso...")
            res = requests.post(url, headers=headers, data=data, timeout=15)
            if res.status_code == 200 and not res.text.strip().startswith("<"):
                ticket = base64.b64decode(res.text).decode("utf-8").strip()
                if ticket.startswith("hCgw"):
                    print(f"[SSO SUCCESS] Minted fresh Bearer ticket: {ticket[:16]}...")
                    self.sso_token = ticket
                    self.session.headers["Authorization"] = f"Bearer {ticket}"
                    update_github_secret("SNAP_SSO_TOKEN", ticket)
                    return ticket
            print(f"[SSO WARN] Refresh response status {res.status_code} (body starts: {res.text[:60]})")
        except Exception as e:
            print(f"[SSO ERROR] Refresh exception: {e}")
        return ""

    def verify_auth(self):
        url = f"{SNAPML_BASE}/api/me"
        if not self.sso_token and self.accounts_cookie:
            self.refresh_sso_ticket()

        res = self._request_with_retry("GET", url, timeout=15)
        if res.status_code == 200:
            user_data = res.json()
            print(f"[AUTH OK] User: {user_data.get('displayName')} (@{user_data.get('username')})")
            return user_data

        raise RuntimeError(f"Auth failed ({res.status_code}): {res.text}")

    def create_conversation(self):
        url = f"{AILC_BASE}/assistant/new_conversation_v2"
        payload = {
            "contentful_stage": "master",
            "contentful_environment": "master",
            "model_ver": "",
            "client": "web",
            "plugin_ver": "1.0",
            "supports_planning": True,
            "supports_reasoning_summaries": True,
            "supports_tool_calls": False
        }
        res = self._request_with_retry("POST", url, json=payload, timeout=20)
        res.raise_for_status()
        data = res.json()
        cid = data.get("conversation_id")
        print(f"[CONVERSATION CREATED] ID: {cid}")
        return cid

    def send_prompt(self, conversation_id: str, prompt: str):
        url = f"{AILC_BASE}/assistant/v1/conversations/{conversation_id}/perform_action"
        payload = {
            "action": "SendPrompt",
            "action_id": str(uuid.uuid4()),
            "expected_version": 0,
            "payload": {
                "prompt": prompt,
                "attachments": []
            }
        }
        res = self._request_with_retry("POST", url, json=payload, timeout=20)
        res.raise_for_status()
        print(f"[PROMPT SENT] Action submitted successfully: {prompt}")
        return res.json()

    def poll_lens(self, conversation_id: str, max_wait_sec: int = 180, poll_interval: int = 5):
        url = f"{AILC_BASE}/assistant/get_lens?conversation_id={conversation_id}"
        start_time = time.time()
        print(f"[POLLING] Waiting for lens generation (timeout: {max_wait_sec}s)...")
        while time.time() - start_time < max_wait_sec:
            res = self._request_with_retry("GET", url, timeout=15)
            if res.status_code == 200:
                lens = res.json()
                archive_url = lens.get("download_url") or (lens.get("lens_bundle_data") or {}).get("lens_archive_url")
                if archive_url:
                    print("[LENS GENERATED SUCCESS]")
                    print(f"Lens Name: {lens.get('lens_name')}")
                    print(f"Checkpoint ID: {lens.get('checkpoint_id')}")
                    print(f"Archive URL: {archive_url}")
                    print(f"Checksum: {lens.get('checksum')}")
                    print(f"Icon URL: {lens.get('lens_icon_download_url')}")
                    return lens
            time.sleep(poll_interval)
        raise TimeoutError("Lens generation polling timed out.")

    def publish_lens(self, conversation_id: str, lens_name: str, tags: list, preview_url: str = None, icon_url: str = None):
        url = f"{AILC_BASE}/assistant/publish"
        payload = {
            "conversation_id": conversation_id,
            "lens_name": lens_name,
            "tags": tags,
            "source_application": "LensStudioWeb",
            "remixable": True,
            "lens_visibility": "PUBLIC"
        }
        if preview_url:
            payload["lens_preview_url"] = preview_url
        if icon_url:
            payload["lens_icon_url"] = icon_url

        res = self._request_with_retry("POST", url, json=payload, timeout=25)
        res.raise_for_status()
        data = res.json()
        print(f"[PUBLISH SUBMITTED] Response: {json.dumps(data)}")
        return data

    def get_publish_status(self, checkpoint_id: str, max_wait_sec: int = 120):
        url = f"{AILC_BASE}/assistant/me/lenses?page_number=1&page_size=20&filter_by=submitted"
        start = time.time()
        while time.time() - start < max_wait_sec:
            res = self._request_with_retry("GET", url, timeout=15)
            if res.status_code == 200:
                data = res.json()
                for item in data.get("items", []):
                    if item.get("checkpoint_id") == checkpoint_id:
                        status = item.get("status")
                        print(f"[PUBLISH STATUS] Status: {status}, Lens ID: {item.get('lens_central_lens_id')}")
                        return item
            time.sleep(4)
        return None
